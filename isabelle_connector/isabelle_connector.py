import logging
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
from parallelbar import progress_map

from isabelle_connector.isabelle_types import IsabelleMessage, Theory, TheoryOutcome
from isabelle_connector.parse import extract_messages_from_responses
from isabelle_connector.session_manager import SessionManager
from isabelle_connector.utils import flatten_dict

# To allow nested event loops in Pytest and notebooks
nest_asyncio.apply()

logger = logging.getLogger(__name__)


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
    max_open_sessions: int = 5
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
        server_info, self._server_process = start_isabelle_server(
            log_file=os.path.join(self.working_directory, "isabelle-server.log"),
            name=self.name,
        )
        self._client: IsabelleClient = get_isabelle_client(server_info=server_info)
        if self.debug:
            handler = logging.FileHandler(os.path.join(self.working_directory, "session.log"))
            handler.setLevel(logging.DEBUG)
            logging.getLogger("isabelle_client").addHandler(handler)
            logging.getLogger("isabelle_client").setLevel(logging.DEBUG)

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
        :param batch_size: How many theories to submit per ``use_theories``
            call.  ``1`` (default) maximises parallelism; larger values
            reduce round-trips when theories share a session and directory.
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
        logger.info("Cache: %d / %d theories already cached", n_cached, len(thys))

        # --- Assign session IDs (with rotation) per theory, then group ---
        if unprocessed:
            theory_session_ids = {
                thy: self._session_manager.session_id_for(thy.session) for thy in unprocessed
            }
            groups = _group_theories(unprocessed, theory_session_ids)

            for (session_id, _working_dir), group in groups.items():
                batches = list(_batch_thys(group, batch_size))
                if batch_size > 1:
                    for batch in batches:
                        messages.update(_use_theories_batch(batch, self._client, session_id))
                else:
                    func = partial(
                        _use_theories_batch,
                        client=self._client,
                        session_id=session_id,
                    )
                    messages.update(
                        flatten_dict(
                            progress_map(
                                func,
                                batches,
                                n_cpu=os.cpu_count(),
                                chunk_size=1,
                                need_serialize=False,
                            )  # type: ignore[no-untyped-call]
                        )
                    )

        outcomes = {thy: TheoryOutcome.from_messages(msgs) for thy, msgs in messages.items()}

        n_ok = sum(1 for o in outcomes.values() if o.ok)
        logger.info("Outcomes: %d / %d theories error-free", n_ok, len(thys))

        if rm_after:
            for thy in thys:
                try:
                    thy.delete()
                except Exception as exc:
                    logger.warning("Failed to remove temp file for %s: %s", thy.name, exc)

        return outcomes


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _group_theories(
    thys: list[Theory],
    theory_session_ids: dict[Theory, str],
) -> dict[tuple[str, str], list[Theory]]:
    """Group theories by (session_id, working_directory).

    All theories in a group share a session and on-disk location, so they
    can be submitted together in a single ``use_theories`` call.
    """
    groups: dict[tuple[str, str], list[Theory]] = {}
    for thy in thys:
        key = (theory_session_ids[thy], thy.working_directory)
        groups.setdefault(key, []).append(thy)
    return groups


def _batch_thys(theories: list[Theory], batch_size: int):
    for i in range(0, len(theories), batch_size):
        yield theories[i : i + batch_size]


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
