from dataclasses import dataclass, field
from functools import partial
import logging
import os
from pprint import pprint
import tempfile
from typing import Any
from uuid import uuid4

from isabelle_client.isabelle__client import IsabelleClient
from isabelle_client.socket_communication import IsabelleResponse
from isabelle_client.utils import (
    get_isabelle_client,
    start_isabelle_server,
)
from isabelle_connector.decorators import timing
from isabelle_connector.isabelle_types import IsabelleMessage, Theory
from isabelle_connector.parse import (
    extract_messages_from_responses,
    extract_ml_values_from_messages,
)
from isabelle_connector.utils import flatten, temp_theory
import nest_asyncio
from parallelbar import progress_map

# To allow nested event loops in Pytest and notebooks
nest_asyncio.apply()


@dataclass
class IsabelleConnector:
    r"""
    An interactive connector to the Isabelle server, hiding server interactions.
    Based on:
    https://github.com/inpefess/isabelle-client/blob/master/isabelle_client/isabelle_connector.py

    An IsabelleConnect object manages a connection to an Isabelle server instance,
    allowing users to send theories to be processed and parse results. It handles
    session management, and parallel processing of theories.

    :param name: Name of the Isabelle server instance.
    :param session_name: Name of the Isabelle session to use.
    :param session_dirs: list of directories for the Isabelle session.
    :param working_directory: Working directory for temporary files.
    :param debug: Whether to enable debug logging.
    """

    name: str = "lemexp"
    session_dict: dict[str, list[str]] = field(default_factory=dict)
    session_counter: dict[str, int] = field(default_factory=dict)
    # session_name: str = "HOL"
    # session_id: str = ""
    session_dirs: list[str] = field(
        default_factory=lambda: ["$ISABELLE_HOME/src/HOL", "$AFP_BASE/thys"]
    )
    working_directory: str = ""
    debug: bool = False

    def __post_init__(self):
        if not self.working_directory:
            self.working_directory = os.path.join(tempfile.mkdtemp(), str(uuid4()))

        self.start_connection()

    def start_connection(self):
        # Start Isabelle server and client
        server_info, self._server_process = start_isabelle_server(
            log_file=os.path.join(self.working_directory, "isabelle-server.log"),
            name=self.name,
        )
        self._client = get_isabelle_client(server_info=server_info)
        if self.debug:
            self._client.logger = logging.getLogger()
            self._client.logger.setLevel(logging.INFO)
            self._client.logger.addHandler(
                logging.FileHandler(os.path.join(self.working_directory, "session.log"))
            )

    def prepare_sessions(self, thys: list[Theory]):
        assert all(thy.session for thy in thys), (
            "All theories must have a session specified"
        )
        sessions = dict.fromkeys(
            {thy.session for thy in thys if thy.session not in self.session_dict}, None
        )
        for i, session in enumerate(sessions.keys()):
            print(f"Starting session {i + 1} / {len(sessions)}: {session}")
            session_id = self._client.session_start(session, dirs=self.session_dirs)
            self.session_dict[session] = [session_id]
            self.session_counter[session] = 0
        for thy in thys:
            if (
                self.session_counter[thy.session]
                and self.session_counter[thy.session] % 1000 == 0
            ):
                print(
                    f"Adding new session for {thy.session} after {self.session_counter[thy.session]} theories"
                )
                session_id = self._client.session_start(
                    thy.session, dirs=self.session_dirs
                )
                self.session_dict[thy.session].append(session_id)
            thy.session_id = self.session_dict[thy.session][-1]
            self.session_counter[thy.session] += 1

    @staticmethod
    def use_theories_helper(
        thys: list[Theory],
        client: IsabelleClient,
        **kwargs,
    ) -> list[IsabelleResponse]:
        return client.use_theories(
            theories=[thy.name for thy in thys],
            master_dir=thys[0].working_directory,
            session_id=thys[0].session_id,
            **kwargs,
        )

    @timing
    def use_theories(
        self,
        thys: list[Theory],
        batch_size=1,
        rm_if_temp: bool = True,
        use_cache: bool = True,
        **kwargs,
    ) -> dict[str, list[Any]]:
        # Skip processing theories that have cached results
        values = {thy.name: "" for thy in thys}
        messages: dict[Theory, list[IsabelleMessage]] = {}
        unprocessed_thys = []
        for theory in thys:
            if theory.is_temp:
                theory.write_to_file()
            if use_cache and theory.cache_exists():
                messages[theory] = theory.read_cache()
            else:
                unprocessed_thys.append(theory)
        print(
            f"Using cached results for {len(thys) - len(unprocessed_thys)} / {len(thys)} theories"
        )

        if unprocessed_thys:
            # Prepare sessions for theories that need processing
            self.prepare_sessions(unprocessed_thys)

            # Process theories in batches
            in_batch_mode = batch_size > 1
            n_cpu = os.cpu_count() if not in_batch_mode else 1
            tasks = [batch for batch in batch_thys(unprocessed_thys, batch_size)]
            func = partial(
                IsabelleConnector.use_theories_helper, client=self._client, **kwargs
            )
            responses = flatten(
                progress_map(
                    func, tasks, n_cpu=n_cpu, chunk_size=1, need_serialize=False
                )  # type: ignore
            )
            new_messages = extract_messages_from_responses(unprocessed_thys, responses)
            messages.update(new_messages)

        values, errs = extract_ml_values_from_messages(messages)

        print(
            f"Successful values from {len([v for v in values.values() if v])} / {len(thys)} theories"
        )

        if rm_if_temp:
            for theory in thys:
                try:
                    del theory  # triggers __del__ to remove temp files
                except Exception as e:
                    print(f"Failed to remove temp files: {e}")
                    errs[theory] = [str(e)]

        return values, errs


def batch_thys(theories, batch_size=100):
    for i in range(0, len(theories), batch_size):
        yield theories[i : i + batch_size]


if __name__ == "__main__":
    root_dir = "/isabelle/src/HOL"
    query = 'ML\\<open> let val res = "Hello, World!" in res end \\<close>'

    isabelle = IsabelleConnector(working_directory=root_dir)
    pprint(
        isabelle.use_theories(
            [
                temp_theory(
                    working_directory=root_dir,
                    queries=[query],
                    imports=[],
                    name="Test",
                )
            ],
            rm_after=False,
        )
    )
