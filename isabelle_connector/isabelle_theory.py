import pickle
import os
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any, List

from isabelle_client import IsabelleResponse


@dataclass
class Theory:
    """A theory."""

    name: str
    working_directory: str
    session: str = "HOL"
    session_id: str = ""
    imports: List[str] = field(default_factory=list)
    queries: List[str] = field(default_factory=list)
    is_temp: bool = False

    def __repr__(self) -> str:
        imports_str = " ".join(f'"{imprt}"' for imprt in self.imports)
        body = "\n".join(self.queries)
        content = f"""theory {self.name}
            imports Main {imports_str} begin
            declare [[show_markup = false]]
            declare [[show_consts = true]]
            declare [[show_abbrevs = true]]
            declare [[names_long = false]]
            declare [[ML_print_depth=1000000]]
            declare [[syntax_ambiguity_warning = false]]
            {body}
            end"""
        return content

    def add_ml_block(self, code: str) -> None:
        self.queries.append(f"ML\\<open>\n{code}\n\\<close>\n")

    def write_to_file(
        self,
    ) -> None:
        content = repr(self)
        os.makedirs(self.working_directory, exist_ok=True)
        with open(
            os.path.join(self.working_directory, f"{self.name}.thy"),
            "w",
            encoding="utf8",
        ) as theory_file:
            theory_file.write(content)
    
    def cache_exists(self) -> bool:
        cache_file_name = f"{self.working_directory}/{self.name}.thy.result"
        if os.path.exists(cache_file_name):
            content = repr(self)
            content_hash = hashlib.sha256(content.encode("utf8")).hexdigest()
            with open(cache_file_name, "rb") as cache_file:
                cache_hash = pickle.load(cache_file).strip()
                # the first line is the hash
                # cache_hash = cache_file.readline().decode("utf8").strip()
                return content_hash == cache_hash
        return False
    
    def read_cache(self) -> List[str]:
        cache_file_name = f"{self.working_directory}/{self.name}.thy.result"
        with open(cache_file_name, "rb") as cache_file:
            # skip the first line (the hash)
            _ = pickle.load(cache_file)
            # return IsabelleResponse(**json.load(cache_file))
            return pickle.load(cache_file)

    def write_cache(self, response: List[str]):
        if self.cache_exists():
            return

        # Cache the output of using a theory file
        cache_file_name = f"{self.working_directory}/{self.name}.thy.result"
        with open(cache_file_name, "wb") as cache_file:
            pickle.dump(hashlib.sha256(repr(self).encode("utf8")).hexdigest() + "\n", cache_file)
            pickle.dump(response, cache_file)

@dataclass
class TheoryResult:
    """Isabelle result."""

    data: str
    output: List[str]
    errs: List[str]
    results: Any = None

    def __post_init__(self):
        self.eval_results()

    def eval_results(self):
        """
        Read the results of the theory.
        """
        self.result = eval(self.output[-1].split("=", 1)[1].rsplit(":", 1)[0].strip())
