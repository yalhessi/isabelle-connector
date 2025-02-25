import os

from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class Theory:
    """A theory."""

    name: str
    working_directory: str
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
        with open(
            os.path.join(self.working_directory, f"{self.name}.thy"),
            "w",
            encoding="utf8",
        ) as theory_file:
            theory_file.write(content)


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
