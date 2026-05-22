import os
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Optional
from uuid import uuid4

from isabelle_connector.isabelle_types import Theory
from isabelle_connector.session_resolver import RootFileResolver

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
            returning a session name (e.g. ``HOLResolver()``, ``AFP``).
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
        resolved_session = RootFileResolver(root_file)(theory_name)
    elif (root_path / "ROOT").is_file():
        resolved_session = RootFileResolver(root_path / "ROOT")(theory_name)
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
        :class:`~isabelle_connector.session_resolver.RootFileResolver` via
        the ``root_file`` argument of :func:`get_theory` for reliable HOL session
        resolution.

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
