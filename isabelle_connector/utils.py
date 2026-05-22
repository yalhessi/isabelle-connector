import os
import re
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Optional
from uuid import uuid4

from isabelle_connector.isabelle_types import Theory

TheoryLike = Theory | str


def _get_or_create_theory_name(theory_name: Optional[str]) -> str:
    return "Temp" + str(uuid4()).replace("-", "") if theory_name is None else theory_name


def get_working_dirs(dataset_dir):
    return [wd for wd in os.listdir(dataset_dir) if os.path.isdir(os.path.join(dataset_dir, wd))]


def list_theory_files(root_dir):
    import glob

    theory_files = glob.glob(os.path.join(root_dir, "**/*.thy"), recursive=True)
    if not theory_files:
        warnings.warn(f"No theory files found in {root_dir}")
    return theory_files


def temp_theory(**kwargs):
    if "name" not in kwargs:
        kwargs["name"] = _get_or_create_theory_name(None)
    if "is_temp" not in kwargs:
        kwargs["is_temp"] = True
    return Theory(**kwargs)


def _theory_name(theory: TheoryLike) -> str:
    name = theory.name if isinstance(theory, Theory) else str(theory)
    return name.removesuffix(".thy").strip("/")


def parse_root_sessions(root_file) -> dict[str, str]:
    """Parse an Isabelle ROOT file and return a mapping of subdirectory to session name.

    Each entry maps a directory path (relative to the ROOT file's parent directory)
    to the session name declared in that directory.  Sessions without an explicit
    ``in`` clause are mapped to the empty string ``""`` (i.e. the ROOT file's own
    directory).

    This is the reliable way to resolve session names for HOL source trees, where
    the directory name does not match the session name (e.g. ``IMP/`` → ``"HOL-IMP"``).

    Examples::

        sessions = parse_root_sessions("/path/to/HOL/ROOT")
        sessions["IMP"]      # -> "HOL-IMP"
        sessions["Analysis"] # -> "HOL-Analysis"
        sessions[""]         # -> "HOL"

    Args:
        root_file: Path to an Isabelle ROOT file.

    Returns:
        Dictionary mapping relative subdirectory paths to session names.
    """
    root_file = Path(root_file)
    content = root_file.read_text(encoding="utf-8")

    # Matches lines of the form:
    #   session ["]Name["] [(groups)] [in ["]dir["]] =
    _SESSION_RE = re.compile(
        r"^\s*session\s+"
        r'(?:"([^"]+)"|(\S+))'           # quoted or unquoted session name
        r"(?:\s+\([^)]*\))?"             # optional groups like (main) or (timing)
        r'(?:\s+in\s+(?:"([^"]+)"|(\S+)))?'  # optional: in "dir" or in dir
        r"\s*=",
        re.MULTILINE,
    )

    result: dict[str, str] = {}
    for m in _SESSION_RE.finditer(content):
        name = m.group(1) or m.group(2)
        directory = m.group(3) or m.group(4) or ""
        result[directory] = name

    return result


def session_from_root(theory_name: TheoryLike, root_file, *, default: str = "HOL") -> str:
    """Resolve a theory's session by walking up directories from an Isabelle ROOT file.

    This is the preferred resolver for Isabelle distribution sources.  It
    handles cases where the physical directory name differs from the session
    name, such as ``IMP/AExp`` belonging to ``HOL-IMP``.
    """
    sessions_map = parse_root_sessions(root_file)
    name = _theory_name(theory_name)
    theory_subdir = name.rsplit("/", 1)[0] if "/" in name else ""

    candidate = theory_subdir
    while True:
        if candidate in sessions_map:
            return sessions_map[candidate]
        if not candidate:
            break
        candidate = candidate.rsplit("/", 1)[0] if "/" in candidate else ""

    return sessions_map.get("", default)


_HOL_SESSION_PREFIXES: tuple[tuple[str, str], ...] = (
    ("MicroJava", "HOL-MicroJava"),
    ("Decision_Procs", "HOL-Decision_Procs"),
    ("Corec_Examples", "HOL-Corec_Examples"),
    ("Types_To_Sets", "HOL-Types_To_Sets"),
    ("SPARK/Examples", "HOL-SPARK-Examples"),
    ("UNITY", "HOL-UNITY"),
    ("Imperative_HOL", "HOL-Imperative_HOL"),
    ("Datatype_Examples", "HOL-Datatype_Examples"),
    ("Auth", "HOL-Auth"),
    ("Matrix_LP", "HOL-Matrix_LP"),
)


def hol_session(theory: TheoryLike, *, root_file=None) -> str:
    """Infer the Isabelle/HOL distribution session for a theory.

    Prefer passing ``root_file=.../src/HOL/ROOT`` when available.  Without a
    ROOT file this falls back to the historical HOL source-tree heuristic used
    by the extraction notebooks.
    """
    if root_file is not None:
        return session_from_root(theory, root_file)

    name = _theory_name(theory)
    if "/" not in name:
        if "." in name:
            prefix = name.split(".", 1)[0]
            if prefix == "HOL" or prefix.startswith("HOL-"):
                return prefix
        return "HOL"

    path, _base_name = name.rsplit("/", 1)
    if path.startswith("HOLCF/IOA"):
        return "-".join(path.split("/")[1:])
    if path.startswith("HOLCF"):
        return "-".join(path.split("/"))
    for prefix, session in _HOL_SESSION_PREFIXES:
        if path.startswith(prefix):
            return session
    return "-".join(["HOL"] + path.split("/"))


_AFP_SESSION_PREFIXES: tuple[tuple[str, str], ...] = (
    ("AutoCorres2/main", "AutoCorres2_Main"),
    ("AutoCorres2/tests", "AutoCorres2_Test"),
    ("Ordinary_Differential_Equations/Refinement", "HOL-ODE-Numerics"),
    ("Ordinary_Differential_Equations/Numerics", "HOL-ODE-Numerics"),
    ("Ordinary_Differential_Equations/Ex/Lorenz/C0", "Lorenz_C0"),
    ("Ordinary_Differential_Equations/Ex/Lorenz/C1", "Lorenz_C1"),
    ("Ordinary_Differential_Equations/Ex/Lorenz", "Lorenz_Approximation"),
    ("Ordinary_Differential_Equations/Ex/ARCH_COMP", "HOL-ODE-ARCH-COMP"),
    ("Ordinary_Differential_Equations/Ex", "HOL-ODE-Examples"),
    ("UTP/toolkit", "UTP-Toolkit"),
)


def afp_session(theory: TheoryLike) -> str:
    """Infer the AFP session for a theory using AFP path conventions.

    Most AFP entries use the top-level directory as the session name.  The
    special cases mirror the extraction notebooks where an AFP entry declares
    multiple sessions below one top-level directory.
    """
    name = _theory_name(theory)
    for prefix, session in _AFP_SESSION_PREFIXES:
        if name.startswith(prefix):
            return session
    return infer_session_name(name) or "HOL"


def get_theory(
    theory_file,
    root_dir,
    *,
    session: str | None = None,
    root_file=None,
    session_resolver: Callable[[str], str] | None = None,
):
    """Construct a :class:`Theory` object for a ``.thy`` file on disk.

    Session resolution priority:

    1. The explicit ``session`` keyword argument (highest priority).
    2. A custom ``session_resolver`` callable.
    3. ROOT-file lookup via ``root_file`` — parses the given Isabelle ROOT file
       to map subdirectories to their declared session names.  Use this for HOL
       source trees where directory names do not match session names.
    4. Automatic ``ROOT`` lookup when ``root_dir / "ROOT"`` exists.
    5. :func:`infer_session_name` heuristic — works for AFP-style repositories
       where the top-level directory is the session name.
    6. Fall back to ``"HOL"`` when none of the above yield a result.

    Args:
        theory_file: Path to the ``.thy`` file (string or path-like).
        root_dir: Root directory that theories are relative to.
        session: Explicit session name; overrides all inference when provided.
        session_resolver: Callable receiving the relative theory name and
            returning a session name.  For example, ``hol_session`` or
            ``afp_session``.
        root_file: Path to an Isabelle ROOT file for accurate session lookup.
    """
    root_path = Path(root_dir)
    root_dir = str(root_path)
    theory_name = str(theory_file).removesuffix(".thy").removeprefix(root_dir).strip("/")

    resolved_session: str
    if session is not None:
        resolved_session = session
    elif session_resolver is not None:
        resolved_session = session_resolver(theory_name)
    elif root_file is not None:
        resolved_session = session_from_root(theory_name, root_file)
    elif (root_path / "ROOT").is_file():
        resolved_session = session_from_root(theory_name, root_path / "ROOT")
    else:
        resolved_session = infer_session_name(theory_name) or "HOL"

    return Theory(
        name=theory_name,
        working_directory=root_dir,
        session=resolved_session,
        imports=[],
        queries=[],
        is_temp=False,
    )


def infer_session_name(theory_name: str) -> str | None:
    """Infer the Isabelle session name from a theory name using the AFP convention.

    Works for AFP-style repositories where the top-level directory is the session
    name (e.g. ``Category3/Functor`` → ``"Category3"``), and for fully-qualified
    dot-notation names (e.g. ``HOL-IMP.Big_Step`` → ``"HOL-IMP"``).

    .. warning::

        This heuristic does **not** work for HOL source trees where the
        subdirectory name differs from the session name (e.g. the directory
        ``IMP/`` declares session ``"HOL-IMP"`` in a ROOT file).  Use
        :func:`parse_root_sessions` with the ``root_file`` argument of
        :func:`get_theory` for reliable HOL session resolution.

    Examples::

        infer_session_name("Category3/Functor")  # -> "Category3"  (AFP)
        infer_session_name("HOL-IMP.Big_Step")   # -> "HOL-IMP"   (dot notation)
        infer_session_name("Main")               # -> None
    """
    name = str(theory_name).strip()
    if "/" in name:
        return name.split("/", 1)[0]
    if "." in name:
        return name.split(".", 1)[0]
    return None


def infer_import_name(theory_name: str) -> str:
    """Convert a relative theory path to a qualified Isabelle import string.

    Examples::

        infer_import_name("Category3/Functor")  # -> "Category3.Functor"
        infer_import_name("HOL-IMP.Big_Step")   # -> "HOL-IMP.Big_Step" (unchanged)
        infer_import_name("Main")               # -> "Main" (unchanged)
    """
    name = str(theory_name).strip()
    if "/" not in name:
        return name
    parts = name.split("/")
    return f"{parts[0]}.{parts[-1]}"


def merge_thys(theories):
    theory = temp_theory(
        name="Merged" + _get_or_create_theory_name(None),
        working_directory=theories[0].working_directory,
        imports=[],
        queries=[],
        is_temp=True,
    )
    imports = set()
    for thy in theories:
        for imprt in thy.imports:
            imports.add(imprt)
        theory.queries.extend(thy.queries)
    theory.imports = list(imports)
    return theory


def flatten(l: list) -> list:
    return [item for sublist in l for item in sublist]


def flatten_dict(d_list: list[dict]) -> dict:
    return {k: v for d in d_list for k, v in d.items()}


def path_to_theory_name(path):
    import re

    # remove all special characters
    return re.sub(r"\W+", "_", path).strip("_")
