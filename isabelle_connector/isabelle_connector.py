import os
import tempfile
from dataclasses import dataclass, field
from functools import partial
from uuid import uuid4

import nest_asyncio
from isabelle_client.isabelle__client import IsabelleClient
from isabelle_client.utils import (
    get_isabelle_client,
    start_isabelle_server,
)
from loguru import logger
from parallelbar import progress_map

from isabelle_connector.isabelle_types import IsabelleMessage, Theory, TheoryOutcome
from isabelle_connector.logging_utils import DEFAULT_FILE_FORMAT, intercept_stdlib_logging
from isabelle_connector.parse import extract_messages_from_responses
from isabelle_connector.session_manager import SessionManager
from isabelle_connector.utils import flatten_dict

# To allow nested event loops in Pytest and notebooks
nest_asyncio.apply()


@dataclass
class IsabelleConnector:
    r"""Interactive connector to the Isabelle server.

    Manages a connection to an Isabelle server instance, allowing users to
    send theories for processing and receive structured results.  Handles
    session lifetime, rotation, caching, and parallel dispatch.

    Intended use as a context manager::

        with IsabelleConnector() as isabelle:
            outcomes = isabelle.use_theories([thy])

    Or manually::

        isabelle = IsabelleConnector()
        try:
            outcomes = isabelle.use_theories([thy])
        finally:
            isabelle.close()

    :param name: Label for the Isabelle server instance.
    :param session_dirs: Directories searched when starting sessions.
    :param working_directory: Directory for temp files and server logs.
        Created automatically if empty.
    :param session_rotation_size: Start a fresh session after this many
        theory-file uses, to bound server-side state accumulation.
    :param max_open_sessions: Maximum number of concurrently-open server
        sessions per session name.  When the cap is reached during rotation
        the oldest session is stopped before the new one is started.
    :param debug: Enable verbose socket-level logging.
    """

    name: str = "lemexp"
    session_dirs: list[str] = field(
        default_factory=lambda: ["$ISABELLE_HOME/src/HOL", "$AFP_BASE/thys"]
    )
    working_directory: str = ""
    session_rotation_size: int = 1000
    max_open_sessions: int = 100
    # server_restart_interval: int = 50
    debug: bool = False

    def __post_init__(self):
        if not self.working_directory:
            self.working_directory = os.path.join(tempfile.mkdtemp(), str(uuid4()))
        self._connect()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def _connect(self):
        os.makedirs(self.working_directory, exist_ok=True)
        if self.debug:
            logger.enable("isabelle_connector")
            intercept_stdlib_logging()
            logger.add(
                os.path.join(self.working_directory, "session.log"),
                level="DEBUG",
                format=DEFAULT_FILE_FORMAT,
                enqueue=True,
            )
        server_info, self._server_process = start_isabelle_server(
            log_file=os.path.join(self.working_directory, "isabelle-server.log"),
            name=self.name,
        )
        self._client: IsabelleClient = get_isabelle_client(server_info=server_info)

        self._session_manager = SessionManager(
            client=self._client,
            session_dirs=self.session_dirs,
            rotation_size=self.session_rotation_size,
            max_sessions=self.max_open_sessions,
        )

    def close(self) -> None:
        """Stop all managed sessions and terminate the Isabelle server."""
        if hasattr(self, "_session_manager"):
            self._session_manager.close()
        if hasattr(self, "_server_process") and self._server_process is not None:
            try:
                self._server_process.terminate()
            except ProcessLookupError:
                pass
            finally:
                self._server_process = None

    def _restart_server(self) -> None:
        """Kill the Isabelle server process and reconnect.

        Faster than stopping sessions individually: terminating the process
        reclaims all session RAM in one shot.  The session manager's state
        is cleared so subsequent :meth:`session_id_for` calls open fresh
        sessions against the new server.
        """
        logger.info(
            "Restarting Isabelle server after {} total sessions opened",
            self._session_manager._total_sessions_opened,
        )
        if self._server_process is not None:
            try:
                self._server_process.terminate()
            except ProcessLookupError:
                pass
            self._server_process = None
        server_info, self._server_process = start_isabelle_server(
            log_file=os.path.join(self.working_directory, "isabelle-server.log"),
            name=self.name,
        )
        self._client = get_isabelle_client(server_info=server_info)
        self._session_manager.force_clear(self._client)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def use_theories(
        self,
        thys: list[Theory],
        *,
        batch_size: int = 1,
        rm_after: bool = True,
        use_cache: bool = True,
        recache: bool = False,
    ) -> dict[Theory, TheoryOutcome]:
        """Process *thys* through Isabelle and return per-theory outcomes.

        :param thys: Theories to process.  Temp theories are written to disk
            automatically before submission.
        :param batch_size: How many theories each parallel worker handles.
        :param rm_after: Delete temp theory files after processing.
        :param use_cache: Return cached results for theories whose content
            has not changed since the last run.
        :param recache: Invalidate existing caches and recompute.
        :returns: Mapping from each input ``Theory`` to its
            :class:`TheoryOutcome`.
        """
        # --- Write temp files and load cache ---
        messages: dict[Theory, list[IsabelleMessage]] = {}
        unprocessed: list[Theory] = []
        for thy in thys:
            if thy.is_temp:
                thy.write_to_file()
            if recache:
                thy.delete_cache()
            cached = thy.read_cache() if use_cache and not recache else None
            if cached is not None:
                messages[thy] = cached
            else:
                unprocessed.append(thy)

        n_cached = len(thys) - len(unprocessed)
        logger.info("Cache: {} / {} theories already cached", n_cached, len(thys))

        # --- Assign session IDs (with rotation) per theory ---
        if unprocessed:
            waves = (
                _make_waves(unprocessed, self.max_open_sessions)
                if self.max_open_sessions > 0
                else [unprocessed]
            )
            for i, wave in enumerate(waves):
                if i > 0:
                    self._restart_server()
                self._session_manager.begin_batch([thy.session for thy in wave])
                theory_session_ids = {
                    thy: self._session_manager.session_id_for(thy.session) for thy in wave
                }
                batches = [
                    [(thy, theory_session_ids[thy]) for thy in wave[j : j + batch_size]]
                    for j in range(0, len(wave), batch_size)
                ]
                func = partial(_use_theory_batch, client=self._client)
                results = progress_map(  # type: ignore[no-untyped-call]
                    func,
                    batches,
                    n_cpu=os.cpu_count(),
                    chunk_size=1,
                    need_serialize=False,
                )
                messages.update(flatten_dict(results))  # type: ignore[arg-type]

        outcomes = {thy: TheoryOutcome.from_messages(msgs) for thy, msgs in messages.items()}

        n_ok = sum(1 for o in outcomes.values() if o.ok)
        logger.info("Outcomes: {} / {} theories error-free", n_ok, len(thys))

        if rm_after:
            for thy in thys:
                try:
                    thy.delete()
                except Exception as exc:
                    logger.warning("Failed to remove temp file for {}: {}", thy.name, exc)

        return outcomes


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _make_waves(thys: list[Theory], max_sessions: int) -> list[list[Theory]]:
    """Split *thys* into waves, each introducing at most *max_sessions* unique session names.

    Theories are kept in their original order within each wave; a new wave
    begins whenever adding the next theory would exceed the session cap.
    """
    waves: list[list[Theory]] = []
    current_wave: list[Theory] = []
    current_sessions: set[str] = set()
    for thy in thys:
        if thy.session not in current_sessions and len(current_sessions) >= max_sessions:
            waves.append(current_wave)
            current_wave = []
            current_sessions = set()
        current_wave.append(thy)
        current_sessions.add(thy.session)
    if current_wave:
        waves.append(current_wave)
    return waves


def _use_theory_batch(
    args: list[tuple[Theory, str]],
    client: IsabelleClient,
) -> dict[Theory, list[IsabelleMessage]]:
    """Process a batch of (theory, session_id) pairs, grouping by session within the batch."""
    by_session: dict[str, list[Theory]] = {}
    for thy, session_id in args:
        by_session.setdefault(session_id, []).append(thy)
    results: dict[Theory, list[IsabelleMessage]] = {}
    for session_id, thys in by_session.items():
        results.update(_use_theories_batch(thys, client, session_id))
    return results


def _use_theory(
    args: tuple[Theory, str],
    client: IsabelleClient,
) -> dict[Theory, list[IsabelleMessage]]:
    thy, session_id = args
    return _use_theories_batch([thy], client, session_id)


def _use_theories_batch(
    thys: list[Theory],
    client: IsabelleClient,
    session_id: str,
) -> dict[Theory, list[IsabelleMessage]]:
    responses = client.use_theories(
        theories=[thy.name for thy in thys],
        master_dir=thys[0].working_directory,
        session_id=session_id,
    )
    return extract_messages_from_responses(thys, responses)
