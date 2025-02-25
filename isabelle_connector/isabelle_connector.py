import json
import logging
import os
import tempfile
from dataclasses import dataclass
from functools import partial
from pprint import pprint
from typing import Any, Dict, List, Optional
from uuid import uuid4

from isabelle_client.utils import get_isabelle_client, start_isabelle_server
from tqdm import tqdm

from isabelle_connector.decorators import file_cache, timing
from isabelle_connector.isabelle_theory import Theory, TheoryResult
from isabelle_connector.isabelle_utils import temp_theory
from isabelle_connector.utils import flatten


@dataclass
class IsabelleConnector:
    r"""
    An interactive connector to the Isabelle server, hiding server interactions.
    Based on:
    https://github.com/inpefess/isabelle-client/blob/master/isabelle_client/isabelle_connector.py
    """

    name: str = "lemexp"
    working_directory: Optional[str] = None

    def __post_init__(self):
        self.working_directory = _get_or_create_working_directory(
            self.working_directory
        )

        server_info, self._server_process = start_isabelle_server(
            log_file=os.path.join(self.working_directory, "isabelle-server.log"),
            name=self.name,
        )

        self._client = get_isabelle_client(server_info=server_info)
        self._client.logger = logging.getLogger()
        self._client.logger.setLevel(logging.INFO)
        self._client.logger.addHandler(
            logging.FileHandler(os.path.join(self.working_directory, "session.log"))
        )

        # self.session_id = self._client.session_start("HOL")
        self.session_id = None

    @timing
    def use_theories(
        self,
        thys: List[Theory],
        batch_size=None,
        rm_after: bool = True,
        purge_after=True,
        rerun_failed=False,
        verbose=False,
        disable_cache=True,
        recache=False,
        **kwargs,
    ) -> Dict[str, List[Any]]:
        @file_cache(
            verbose=verbose,
            disable=disable_cache,
            recache=recache,
            ignore_params=["isabelle", "purge_after"],
        )
        def _use_theories(thys: List[str], isabelle, purge_after=True):
            if "watchdog_timeout" not in kwargs:
                kwargs["watchdog_timeout"] = 120
            res = isabelle._client.use_theories(
                theories=thys,
                master_dir=isabelle.working_directory,
                session_id=isabelle.session_id,
                **kwargs,
            )
            if purge_after:
                isabelle._client.purge_theories(
                    theories=thys, session_id=isabelle.session_id
                )
            return res

        thy_names = [thy.name for thy in thys]

        for theory in thys:
            if theory.is_temp:
                theory.write_to_file()

        # start = time.time()
        if batch_size:
            tasks = [
                [thy.name for thy in batch] for batch in batch_thys(thys, batch_size)
            ]
            func = partial(
                _use_theories,
                isabelle=self,
                purge_after=purge_after,
            )
            responses = flatten(tqdm(map(func, tasks), total=len(tasks)))
        else:
            responses = _use_theories(
                thy_names,
                self,
            )
        # end = time.time()
        # print(f"Finished in {end - start} seconds")

        results = parse_isabelle_response(thys, responses)

        if rerun_failed:
            failed_thys = [
                thy for thy, result in zip(thys, results.values()) if not result
            ]
            failed_results = self.use_theories(
                failed_thys,
                batch_size=1,
                recache=True,
                rerun_failed=False,
                rm_after=False,
                purge_after=purge_after,
                disable_cache=disable_cache,
                **kwargs,
            )

            results = results | failed_results
            # for theory, result in zip(thys, results.values()):
            #     if not result:
            #         results.update(self.use_theory(theory))

        try:
            for theory in thys:
                if theory.is_temp and rm_after:
                    os.remove(
                        os.path.join(theory.working_directory, f"{theory.name}.thy")
                    )
        except Exception as e:
            print(f"Failed to remove temp files: {e}")

        return results

    # @timing
    def use_theory(self, theory: Theory, **kwargs) -> TheoryResult:
        return self.use_theories([theory], **kwargs)


def _get_or_create_working_directory(working_directory: Optional[str]) -> str:
    new_working_directory = (
        working_directory
        if working_directory is not None
        else os.path.join(tempfile.mkdtemp(), str(uuid4()))
    )
    if not os.path.exists(new_working_directory):
        os.mkdir(new_working_directory)
    return new_working_directory


def batch_thys(theories, batch_size=100):
    for i in range(0, len(theories), batch_size):
        yield theories[i : i + batch_size]


def parse_ml_value(message):
    # clean up the message
    cleaned_message = (
        message.replace("\n", " ").replace("true", "True").replace("false", "False")
    )
    try:
        val = eval(cleaned_message.split("=", 1)[1].rsplit(":", 1)[0].strip())
        return val, True
    except Exception as e:
        return message, False



def parse_isabelle_response(thys, responses):
    thy_dict = {thy.name: [] for thy in thys}
    for response in responses:
        if response.response_type == "FAILED":
            data = json.loads(response.response_body)
            assert data["kind"] == "error"
            return {thy.name: [data["message"]] for thy in thys}

        elif response.response_type == "FINISHED":
            data = json.loads(response.response_body)
            for node in data["nodes"]:
                name = node["theory_name"].removeprefix("Draft.")

                if name not in thy_dict:
                    continue

                for message in node["messages"]:
                    if message["kind"] == "writeln":
                        ml_val, success = parse_ml_value(message["message"])
                        if success:
                            thy_dict[name].append(ml_val)
                    elif message["kind"] == "error":
                        thy_dict[name].append(message["message"])
    return thy_dict


if __name__ == "__main__":
    root_dir = "/isabelle/src/HOL"
    query = 'ML\\<open> let val res = "Hello, World!" in res end \\<close>'

    isabelle = IsabelleConnector(working_directory=root_dir)
    pprint(
        isabelle.use_theory(
            temp_theory(
                working_directory=root_dir,
                queries=[query],
                imports=[],
                name="Test",
            ),
            rm_after=False,
        )
    )
