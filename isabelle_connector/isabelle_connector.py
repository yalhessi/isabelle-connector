import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from functools import partial
from pprint import pprint
from typing import Any, Dict, List, Optional
from uuid import uuid4

from isabelle_client.isabelle__client import IsabelleClient
from isabelle_client.socket_communication import IsabelleResponse
from isabelle_client.utils import (
    get_isabelle_client,
    start_isabelle_server,
)
from isabelle_connector.decorators import file_cache, timing
from isabelle_connector.isabelle_theory import Theory
from isabelle_connector.isabelle_utils import temp_theory
from isabelle_connector.utils import flatten
from parallelbar import progress_map
from tqdm import tqdm


@dataclass
class IsabelleConnector:
    r"""
    An interactive connector to the Isabelle server, hiding server interactions.
    Based on:
    https://github.com/inpefess/isabelle-client/blob/master/isabelle_client/isabelle_connector.py
    """

    name: str = "lemexp"
    session_name: str = "HOL"
    session_dirs: List[str] = field(
        default_factory=lambda: ["$ISABELLE_HOME/src/HOL", "$AFP_BASE/thys"]
    )
    working_directory: Optional[str] = None
    debug: bool = False

    def __post_init__(self):
        if not self.working_directory:
            self.working_directory = os.path.join(tempfile.mkdtemp(), str(uuid4()))

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

        self.start_new_session()
        # self.session_id = self._client.session_start(self.session_name)

    def start_new_session(self):
        self.session_id = self._client.session_start(
            self.session_name, dirs=self.session_dirs
        )

    def refresh_session(self):
        self._client.session_stop(self.session_id)
        self.start_new_session()
        # self.session_id = self._client.session_start(self.session_name)

    @timing
    def use_theories(
        self,
        thys: List[Theory],
        batch_size=None,
        rm_if_temp: bool = True,
        **kwargs,
    ) -> Dict[str, List[Any]]:
        for theory in thys:
            if theory.is_temp:
                theory.write_to_file()

        if not batch_size:
            batch_size = 1

        in_batch_mode = batch_size > 1
        if in_batch_mode:
            tasks = [batch for batch in batch_thys(thys, batch_size)]
            func = partial(
                parallel_use_theories_purgeable,
                isabelle=self,
                **kwargs,
            )
            responses = flatten(tqdm(map(func, tasks), total=len(tasks)))

        else:
            # TODO: start ncpu sessions, and use them in parallel
            tasks = [batch for batch in batch_thys(thys, batch_size)]
            func = partial(
                parallel_use_theories,
                client=self._client,
                session_id=self.session_id,
                session_dirs=self.session_dirs,
                **kwargs,
            )

            responses: List[IsabelleResponse] = flatten(
                progress_map(func, tasks, n_cpu=8, chunk_size=1, need_serialize=True)  # type: ignore
            )

        results, errs = parse_isabelle_response(thys, responses)

        print(
            f"Successful values from {len([v for v in results.values() if v])} / {len(thys)} theories"
        )

        for theory in thys:
            if theory.is_temp and rm_if_temp:
                try:
                    thy_path = os.path.join(
                        theory.working_directory, f"{theory.name}.thy"
                    )
                    os.remove(thy_path)
                except Exception as e:
                    print(f"Failed to remove temp files: {e}")

        return results


def batch_thys(theories, batch_size=100):
    for i in range(0, len(theories), batch_size):
        yield theories[i : i + batch_size]


def parse_ml_value(message):
    # clean up the message
    cleaned_message = message.replace("true", "True").replace("false", "False")
    val_name, val_rest = cleaned_message.split("=", 1)
    val_value, val_type = (elem.strip() for elem in val_rest.rsplit(":", 1))
    try:
        val = eval(val_value)
        return val, True
    except Exception as e:
        return cleaned_message, False


def is_ml_value(message):
    return message.startswith("val ")


def parse_isabelle_response(thys, responses):
    thy_dict = {thy.name: [] for thy in thys}
    errs = {}
    for response in responses:
        if response.response_type == "FAILED":
            continue
            # data = json.loads(response.response_body)
            # assert data["kind"] == "error"
            # return {thy.name: [data["message"]] for thy in thys}

        elif response.response_type == "FINISHED":
            data = json.loads(response.response_body)
            for node in data["nodes"]:
                name = node["theory_name"].removeprefix("Draft.")

                if name not in thy_dict:
                    continue

                for message in node["messages"]:
                    if message["kind"] == "writeln":
                        clean_message = message["message"].replace("\n", " ")
                        if is_ml_value(clean_message):
                            ml_val, success = parse_ml_value(clean_message)
                            if success:
                                thy_dict[name].append(ml_val)
                    elif message["kind"] == "error":
                        if name not in errs:
                            errs[name] = []
                        errs[name].append(message["message"])
    return thy_dict, errs


theory_counter = 0


@file_cache(
    disable=False,
    verbose=False,
    ignore_params=["isabelle"],
)
def parallel_use_theories_purgeable(
    thys: List[Theory], isabelle: IsabelleConnector, **kwargs
):
    global theory_counter
    res = isabelle._client.use_theories(
        theories=[thy.name for thy in thys],
        master_dir=thys[0].working_directory,
        session_id=isabelle.session_id,
        **kwargs,
    )
    theory_counter += len(thys)
    if theory_counter % 1000 == 0:
        isabelle.refresh_session()
    return res


@file_cache(
    disable=False,
    verbose=False,
    ignore_params=["client", "session_id"],
)
def parallel_use_theories(
    thys: List[Theory], client: IsabelleClient, session_id: str, **kwargs
):
    res = client.use_theories(
        theories=[thy.name for thy in thys],
        master_dir=thys[0].working_directory,
        session_id=session_id,
        **kwargs,
    )
    return res


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
