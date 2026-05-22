import logging
from collections import deque

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages Isabelle session lifetimes for an IsabelleClient.

    For each logical session name (e.g. ``"HOL"``, ``"HOL-Analysis"``),
    maintains a pool of server-side session IDs and rotates to a fresh one
    every *rotation_size* theory-file uses to avoid unbounded server-side
    state accumulation.

    A global *max_sessions* cap limits the total number of concurrently-open
    sessions across all session names.  When starting a new session would
    exceed the cap, the oldest open session (regardless of name) is stopped
    first.

    Sessions are started lazily on first use and stopped explicitly via
    :meth:`close`.
    """

    def __init__(
        self,
        client,
        session_dirs: list[str],
        rotation_size: int = 1000,
        max_sessions: int = 50,
    ):
        self._client = client
        self.session_dirs = session_dirs
        self.rotation_size = rotation_size
        self.max_sessions = max_sessions
        # session_name -> list of currently-active session IDs
        self._sessions: dict[str, list[str]] = {}
        # session_name -> number of theories dispatched so far
        self._counters: dict[str, int] = {}
        # global insertion-order queue of (session_name, session_id)
        self._open_order: deque[tuple[str, str]] = deque()

    def session_id_for(self, session_name: str) -> str:
        """Return an active session ID for *session_name*.

        Starts a new Isabelle session the first time *session_name* is seen,
        and again every *rotation_size* calls (one call per theory processed)
        to bound server-side resource accumulation.  When the global
        *max_sessions* cap would be exceeded, the oldest open session is
        stopped first.
        """
        if session_name not in self._sessions:
            sid = self._open_session(session_name)
            self._sessions[session_name] = [sid]
            self._counters[session_name] = 0

        count = self._counters[session_name]
        if count > 0 and count % self.rotation_size == 0:
            logger.info("Rotating session '%s' after %d theories", session_name, count)
            sid = self._open_session(session_name)
            self._sessions[session_name].append(sid)

        self._counters[session_name] += 1
        return self._sessions[session_name][-1]

    def active_sessions(self) -> dict[str, list[str]]:
        """Return a snapshot of ``{session_name: [session_ids]}``."""
        return {name: list(ids) for name, ids in self._sessions.items()}

    def close(self) -> None:
        """Stop all managed sessions and release their resources."""
        while self._open_order:
            name, sid = self._open_order.popleft()
            self._stop_session(name, sid)
        self._sessions.clear()
        self._counters.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_session(self, session_name: str) -> str:
        """Start a new session, evicting the oldest open one if at cap."""
        if len(self._open_order) >= self.max_sessions:
            oldest_name, oldest_sid = self._open_order.popleft()
            self._sessions[oldest_name].remove(oldest_sid)
            self._stop_session(oldest_name, oldest_sid)
        sid = self._start_session(session_name)
        self._open_order.append((session_name, sid))
        return sid

    def _start_session(self, session_name: str) -> str:
        logger.info("Starting Isabelle session: %s", session_name)
        return self._client.session_start(session_name, dirs=self.session_dirs)

    def _stop_session(self, session_name: str, session_id: str) -> None:
        try:
            self._client.session_stop(session_id)
        except Exception as exc:
            logger.warning("Failed to stop session '%s' (%s): %s", session_name, session_id, exc)
