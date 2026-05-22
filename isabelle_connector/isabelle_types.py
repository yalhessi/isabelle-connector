import hashlib
import os
import pickle
import tempfile
import warnings
from dataclasses import dataclass, field
from typing import Any

# Isabelle messages inside of IsabelleResponse
type IsabelleMessage = dict[str, Any]

_CACHE_READ_ERRORS = (
    AttributeError,
    EOFError,
    OSError,
    TypeError,
    ValueError,
    pickle.UnpicklingError,
)

_THEORY_PREAMBLE = [
    "declare [[show_markup = false]]",
    "declare [[show_consts = true]]",
    "declare [[show_abbrevs = true]]",
    "declare [[names_long = false]]",
    "declare [[ML_print_depth=1000000]]",
    "declare [[syntax_ambiguity_warning = false]]",
]


def _is_ml_value(message: str) -> bool:
    return message.startswith("val ")


def _parse_ml_value(message: str) -> tuple[Any, bool]:
    """Try to parse an Isabelle ML value line into a Python object.

    Returns ``(value, True)`` on success or ``(raw_message, False)`` when
    ``ast.literal_eval`` cannot interpret the value.
    """
    import ast

    cleaned = message.replace("true", "True").replace("false", "False")
    _name, rest = cleaned.split("=", 1)
    value_str, _type = (part.strip() for part in rest.rsplit(":", 1))
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=SyntaxWarning)
            return ast.literal_eval(value_str), True
    except Exception:
        return cleaned, False


@dataclass
class Theory:
    """A theory."""

    name: str
    working_directory: str
    session: str = "HOL"
    imports: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    is_temp: bool = False

    def __hash__(self) -> int:
        return hash(self.name)

    def to_theory_text(self) -> str:
        """Render this theory as Isabelle source text."""
        imports_str = " ".join(f'"{i}"' for i in self.imports)
        lines = [
            f"theory {self.name}",
            f"  imports {imports_str}",
            "begin",
            *_THEORY_PREAMBLE,
            *self.queries,
            "end",
        ]
        return "\n".join(lines) + "\n"

    def delete(self) -> None:
        if self.is_temp:
            try:
                os.remove(os.path.join(self.working_directory, f"{self.name}.thy"))
            except FileNotFoundError:
                warnings.warn(f"Temp file {self.name}.thy not found for deletion.")

    def add_ml_block(self, code: str) -> None:
        self.queries.append(f"ML\\<open>\n{code}\n\\<close>\n")

    def write_to_file(self) -> None:
        content = self.to_theory_text()
        os.makedirs(self.working_directory, exist_ok=True)
        with open(
            os.path.join(self.working_directory, f"{self.name}.thy"),
            "w",
            encoding="utf8",
        ) as theory_file:
            theory_file.write(content)

    def _cache_file_name(self) -> str:
        return os.path.join(self.working_directory, f"{self.name}.thy.result")

    def _content_hash(self) -> str:
        return hashlib.sha256(self.to_theory_text().encode("utf8")).hexdigest()

    def _delete_invalid_cache(self, cache_file_name: str, exc: Exception) -> None:
        warnings.warn(
            f"Ignoring invalid cache file {cache_file_name}: {exc}",
            stacklevel=2,
        )
        try:
            os.remove(cache_file_name)
        except FileNotFoundError:
            pass

    def cache_exists(self) -> bool:
        cache_file_name = self._cache_file_name()
        if os.path.exists(cache_file_name):
            try:
                with open(cache_file_name, "rb") as cache_file:
                    cache_hash = pickle.load(cache_file)
            except _CACHE_READ_ERRORS as exc:
                self._delete_invalid_cache(cache_file_name, exc)
                return False
            if not isinstance(cache_hash, str):
                self._delete_invalid_cache(
                    cache_file_name, TypeError("Cache header is not a string hash")
                )
                return False
            return self._content_hash() == cache_hash.strip()
        return False

    def read_cache(self) -> list[IsabelleMessage] | None:
        cache_file_name = self._cache_file_name()
        if not os.path.exists(cache_file_name):
            return None

        try:
            with open(cache_file_name, "rb") as cache_file:
                cache_hash = pickle.load(cache_file)
                response = pickle.load(cache_file)
        except _CACHE_READ_ERRORS as exc:
            self._delete_invalid_cache(cache_file_name, exc)
            return None

        if not isinstance(cache_hash, str):
            self._delete_invalid_cache(
                cache_file_name, TypeError("Cache header is not a string hash")
            )
            return None

        if self._content_hash() != cache_hash.strip():
            return None

        return response

    def write_cache(self, response: list[IsabelleMessage]):
        if self.cache_exists():
            return

        # Cache the output of using a theory file
        cache_file_name = self._cache_file_name()
        os.makedirs(self.working_directory, exist_ok=True)
        fd, temp_cache_file = tempfile.mkstemp(
            dir=self.working_directory,
            prefix="thy-cache-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "wb") as cache_file:
                pickle.dump(self._content_hash() + "\n", cache_file)
                pickle.dump(response, cache_file)
            os.replace(temp_cache_file, cache_file_name)
        finally:
            try:
                os.remove(temp_cache_file)
            except FileNotFoundError:
                pass

    def delete_cache(self):
        cache_file_name = self._cache_file_name()
        try:
            os.remove(cache_file_name)
        except FileNotFoundError:
            warnings.warn(f"Cache file {cache_file_name} not found for deletion.")


@dataclass
class TheoryOutcome:
    """The parsed result of processing a single Theory through Isabelle."""

    values: list[Any]
    output: list[str]
    errors: list[str]

    @classmethod
    def from_messages(cls, messages: list[IsabelleMessage]) -> "TheoryOutcome":
        """Build a ``TheoryOutcome`` from raw Isabelle PIDE messages."""
        values: list[Any] = []
        output: list[str] = []
        errors: list[str] = []
        for message in messages:
            match message["kind"]:
                case "writeln":
                    text = message["message"]
                    output.append(text)
                    clean = text.replace("\n", " ")
                    if _is_ml_value(clean):
                        val, success = _parse_ml_value(clean)
                        if success:
                            values.append(val)
                case "error":
                    errors.append(message["message"])
        return cls(values=values, output=output, errors=errors)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def value(self) -> Any:
        """Last parsed ML value, or ``None`` if there were none."""
        return self.values[-1] if self.values else None
