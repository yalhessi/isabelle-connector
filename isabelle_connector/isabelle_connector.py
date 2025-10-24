import ast
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from functools import partial
from pprint import pprint
from typing import Any, Optional
from uuid import uuid4
import warnings

import nest_asyncio
from isabelle_client.isabelle__client import IsabelleClient
from isabelle_client.socket_communication import IsabelleResponse
from isabelle_client.utils import (
    get_isabelle_client,
    start_isabelle_server,
)
from parallelbar import progress_map
from tqdm import tqdm

from isabelle_connector.decorators import timing
from isabelle_connector.isabelle_theory import Theory
from isabelle_connector.isabelle_utils import temp_theory
from isabelle_connector.utils import flatten

# To allow nested event loops in Pytest
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
            
        # Start a fresh session for the client
        # self.refresh_session(self.session_name)        

    # def refresh_session(self, session_name):
    #     if self.session_id:
    #         self._client.session_stop(self.session_id)
    #     session_id = self._client.session_start(
    #         session_name, dirs=self.session_dirs
    #     )
    #     self.session_dict[session_name] = session_id
        
    def prepare_sessions(self, thys: list[Theory]):
        # for thy in thys:
        #     if not thy.session:
        #         thy.session = self.session_name
        sessions = dict.fromkeys({thy.session for thy in thys if thy.session not in self.session_dict}, None)
        for i, session in enumerate(sessions.keys()):
            print(f"Starting session {i + 1} / {len(sessions)}: {session}")
            session_id = self._client.session_start(
                session, dirs=self.session_dirs
            )
            self.session_dict[session] = [session_id]
            self.session_counter[session] = 0
        for thy in thys:
            if self.session_counter[thy.session] and self.session_counter[thy.session] % 1000 == 0:
                print(f"Adding new session for {thy.session} after {self.session_counter[thy.session]} theories")
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
        recache: bool = False,
        **kwargs,
    ) -> dict[str, list[Any]]:
        # Skip processing theories that have cached results
        results = {thy.name: "" for thy in thys}
        messages : dict[str, list[str]] = {thy.name: [] for thy in thys}
        # responses : list[IsabelleResponse] = []
        unprocessed_thys = []
        for theory in thys:
            if theory.is_temp:
                theory.write_to_file()
            if use_cache and theory.cache_exists():
                messages[theory.name] = theory.read_cache()
            else:
                unprocessed_thys.append(theory)
        print(f"Using cached results for {len(thys) - len(unprocessed_thys)} / {len(thys)} theories")

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
                progress_map(func, tasks, n_cpu=n_cpu, chunk_size=1, need_serialize=False)  # type: ignore
            )
            new_messages = extract_messages_from_responses(thys, responses)
            messages.update(new_messages)
        results, errs = parse_messages(thys, messages)
        # print(f"responses: {responses}")
        # if in_batch_mode:
        #     tasks = [batch for batch in batch_thys(unprocessed_thys, batch_size)]
        #     func = partial(
        #         parallel_use_theories_purgeable,
        #         isabelle=self,
        #         **kwargs,
        #     )
        #     responses += flatten(tqdm(map(func, tasks), total=len(tasks)))

        # else:
        #     # TODO: start ncpu sessions, and use them in parallel
        #     tasks = [batch for batch in batch_thys(unprocessed_thys, batch_size)]
        #     func = partial(
        #         parallel_use_theories,
        #         client=self._client,
        #         session_id=self.session_id,
        #         session_dirs=self.session_dirs,
        #         **kwargs,
        #     )

        #     responses += flatten(
        #         progress_map(func, tasks, n_cpu=8, chunk_size=1, need_serialize=True)  # type: ignore
        #     )

        # print(f"Responses: {responses}")
        # print(f"Results: {results}")
        # return
        # results, errs = parse_isabelle_response(thys, responses, recache=recache)
        # results, errs = {}, {}

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
                    errs[theory.name] = [str(e)]

        return results, errs


def batch_thys(theories, batch_size=100):
    for i in range(0, len(theories), batch_size):
        yield theories[i : i + batch_size]


def parse_ml_value(message):
    # clean up the message
    cleaned_message = message.replace("true", "True").replace("false", "False")
    val_name, val_rest = cleaned_message.split("=", 1)
    val_value, val_type = (elem.strip() for elem in val_rest.rsplit(":", 1))
    try:
        # silence syntax warnings during literal_eval (e.g., for \<open>)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=SyntaxWarning)
            val = ast.literal_eval(val_value)
        return val, True
    except Exception as e:
        return cleaned_message, False


def is_ml_value(message):
    return message.startswith("val ")

def extract_messages_from_responses(thys: list[Theory], responses) -> dict[str, list[str]]:
    messages = {thy.name: [] for thy in thys}
    for response in responses:
        match response.response_type:
            case "FINISHED":
                data = json.loads(response.response_body)
                for node in data["nodes"]:
                    name = node["theory_name"].removeprefix("Draft.")
                    if name not in messages:
                        continue
                    curr_thy = thys[[thy.name for thy in thys].index(name)]
                    curr_thy.write_cache(node["messages"])
                    messages[name] = node["messages"]
            case "ERROR" | "FAILED":
                warnings.warn(f"Received ERROR response: {response.response_body}")
            case _:
                continue
    return messages


def parse_messages(thys: list[Theory], messages: dict[str, list[str]]):
    thy_dict = {thy.name: [] for thy in thys}
    errs = {}
    for thy in thys:
        for message in messages[thy.name]:
            if message["kind"] == "writeln":
                clean_message = message["message"].replace("\n", " ")
                if is_ml_value(clean_message):
                    ml_val, success = parse_ml_value(clean_message)
                    if success:
                        thy_dict[thy.name].append(ml_val)
            elif message["kind"] == "error":
                if thy.name not in errs:
                    errs[thy.name] = []
                errs[thy.name].append(message["message"])
    return thy_dict, errs
    # for response in responses:
    #     match response.response_type:
    #         case "FAILED":
    #             continue
    #         case "FINISHED":                
    #             data = json.loads(response.response_body)
    #             for node in data["nodes"]:
    #                 name = node["theory_name"].removeprefix("Draft.")

    #                 if name not in thy_dict:
    #                     continue

    #                 curr_thy = thys[[thy.name for thy in thys].index(name)]
    #                 curr_thy.write_cache(node["messages"])
                    
    #                 for message in node["messages"]:
    #                     if message["kind"] == "writeln":
    #                         clean_message = message["message"].replace("\n", " ")
    #                         if is_ml_value(clean_message):
    #                             ml_val, success = parse_ml_value(clean_message)
    #                             if success:
    #                                 thy_dict[name].append(ml_val)
    #                     elif message["kind"] == "error":
    #                         if name not in errs:
    #                             errs[name] = []
    #                         errs[name].append(message["message"])
    #         case "ERROR":
    #             warnings.warn(f"Received ERROR response: {response.response_body}")
    # return thy_dict, errs


# theory_counter = 0


# @file_cache(
#     disable=False,
#     verbose=False,
#     ignore_params=["isabelle"],
# )
# def parallel_use_theories_purgeable(
#     thys: list[Theory], isabelle: IsabelleConnector, **kwargs
# ):
#     global theory_counter
#     res = isabelle._client.use_theories(
#         theories=[thy.name for thy in thys],
#         master_dir=thys[0].working_directory,
#         session_id=isabelle.session_id,
#         **kwargs,
#     )
#     theory_counter += len(thys)
#     if theory_counter % 1000 == 0:
#         isabelle.refresh_session()
#     return res


# @file_cache(
#     disable=False,
#     verbose=False,
#     ignore_params=["client", "session_id"],
# )
# def parallel_use_theories(
#     thys: list[Theory], client: IsabelleClient, session_id: str, **kwargs
# ):
#     res = client.use_theories(
#         theories=[thy.name for thy in thys],
#         master_dir=thys[0].working_directory,
#         session_id=session_id,
#         **kwargs,
#     )
#     return res

@dataclass
class IsabelleMessage:
    kind: str
    message: str
    pos: Optional[Any] = None

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
