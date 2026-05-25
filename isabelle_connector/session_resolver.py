"""Session name resolvers for Isabelle theories.

Each resolver is a callable class that maps a theory name or :class:`Theory`
object to the Isabelle session it belongs to.  Pass one as the
``session_resolver`` argument to :func:`~isabelle_connector.utils.get_theory`,
or call it directly.

Usage::

    from isabelle_connector.session_resolver import HOLResolver, AFPResolver

    # Explicit ROOT-file-backed resolver (most accurate for HOL sources)
    resolver = HOLResolver(root_file="/path/to/Isabelle/src/HOL/ROOT")
    resolver("IMP/Big_Step")   # -> "HOL-IMP"

    # Heuristic resolver for the Isabelle distribution (no ROOT file needed)
    resolver = HOLResolver()
    resolver("HOLCF/IOA/ABP/Correctness")  # -> "IOA-ABP"

    # AFP convention resolver
    resolver = AFPResolver()
    resolver("Category3/Functor")            # -> "Category3"
    resolver("UTP/toolkit/utp")              # -> "UTP-Toolkit"
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from isabelle_connector.isabelle_types import Theory

# A theory may be passed as a Theory object or a plain name/path string.
TheoryLike = "Theory | str"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _theory_name(theory: "Theory | str") -> str:
    from isabelle_connector.isabelle_types import Theory as _Theory
    name = theory.name if isinstance(theory, _Theory) else str(theory)
    return name.removesuffix(".thy").strip("/")


_SESSION_RE = re.compile(
    r"^\s*session\s+"
    r'(?:"([^"]+)"|(\S+))'                    # quoted or unquoted session name
    r"(?:\s+\([^)]*\))?"                       # optional groups like (main)
    r'(?:\s+in\s+(?:"([^"]+)"|(\S+)))?'       # optional: in "dir" or in dir
    r"\s*=",
    re.MULTILINE,
)


def _parse_root_file(root_file: Path) -> dict[str, str]:
    """Return ``{relative_dir: session_name}`` from an Isabelle ROOT file."""
    content = root_file.read_text(encoding="utf-8")
    result: dict[str, str] = {}
    for m in _SESSION_RE.finditer(content):
        name = m.group(1) or m.group(2)
        directory = m.group(3) or m.group(4) or ""
        result[directory] = name
    return result


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class SessionResolver(ABC):
    """Abstract base for session name resolvers.

    Subclasses implement :meth:`__call__`, making every resolver directly
    usable as a ``session_resolver=`` argument to
    :func:`~isabelle_connector.utils.get_theory`.
    """

    @abstractmethod
    def __call__(self, theory: "Theory | str") -> str:
        """Return the Isabelle session name for *theory*."""


# ---------------------------------------------------------------------------
# Concrete resolvers
# ---------------------------------------------------------------------------

class RootFileResolver(SessionResolver):
    """Resolve sessions by parsing an Isabelle ROOT file.

    This is the most accurate resolver for any source tree whose ROOT file is
    available.  It builds a ``{relative_directory: session_name}`` map from
    the ROOT file on construction and then looks up each theory by walking
    up its directory path.

    Examples::

        r = RootFileResolver("/path/to/HOL/ROOT")
        r("IMP/Big_Step")              # -> "HOL-IMP"
        r("HOLCF/IOA/ABP/Correctness") # -> "IOA-ABP"
        r("Main")                      # -> "HOL"
    """

    def __init__(self, root_file) -> None:
        self._root_file = Path(root_file)
        self._sessions_map: dict[str, str] = _parse_root_file(self._root_file)

    @property
    def sessions_map(self) -> dict[str, str]:
        """A copy of the ``{relative_dir: session_name}`` mapping."""
        return dict(self._sessions_map)

    def __call__(self, theory: "Theory | str", *, default: str = "HOL") -> str:
        name = _theory_name(theory)
        candidate = name.rsplit("/", 1)[0] if "/" in name else ""
        while True:
            if candidate in self._sessions_map:
                return self._sessions_map[candidate]
            if not candidate:
                break
            candidate = candidate.rsplit("/", 1)[0] if "/" in candidate else ""
        return self._sessions_map.get("", default)


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


class HOLResolver(SessionResolver):
    """Resolve sessions for theories in the Isabelle/HOL distribution source tree.

    When a ``root_file`` is supplied the resolution delegates entirely to a
    :class:`RootFileResolver`, which is accurate for every HOL sub-session.
    Without a ROOT file, a built-in prefix table plus a ``HOL-<dir>`` heuristic
    is used (matches the convention used in the extraction notebooks).

    Examples::

        # With ROOT file (preferred):
        r = HOLResolver(root_file="/path/to/Isabelle/src/HOL/ROOT")
        r("IMP/Big_Step")   # -> "HOL-IMP"

        # Without ROOT file (heuristic):
        r = HOLResolver()
        r("Main")                       # -> "HOL"
        r("HOL-IMP.Big_Step")           # -> "HOL-IMP"
        r("IMP/AExp")                   # -> "HOL-IMP"
        r("HOLCF/IOA/ABP/Correctness")  # -> "IOA-ABP"
    """

    def __init__(self, root_file=None) -> None:
        self._delegate: RootFileResolver | None = (
            RootFileResolver(root_file) if root_file is not None else None
        )

    def __call__(self, theory: "Theory | str") -> str:
        if self._delegate is not None:
            return self._delegate(theory)

        name = _theory_name(theory)

        # Dot-notation: "HOL-IMP.Big_Step" -> "HOL-IMP"
        if "/" not in name:
            if "." in name:
                prefix = name.split(".", 1)[0]
                if prefix == "HOL" or prefix.startswith("HOL-"):
                    return prefix
            return "HOL"

        path, _ = name.rsplit("/", 1)

        # HOLCF/IOA sub-sessions: HOLCF/IOA/ABP -> IOA-ABP
        if path.startswith("HOLCF/IOA"):
            return "-".join(path.split("/")[1:])
        # Other HOLCF sub-sessions: HOLCF/Library -> HOLCF-Library
        if path.startswith("HOLCF"):
            return "-".join(path.split("/"))

        for prefix, session in _HOL_SESSION_PREFIXES:
            if path.startswith(prefix):
                return session

        # General rule: IMP -> HOL-IMP, Analysis/Metric -> HOL-Analysis-Metric
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


class AFPResolver(SessionResolver):
    """Resolve sessions for theories following Archive of Formal Proofs (AFP) conventions.

    Most AFP entries use the top-level directory as the session name.  Known
    multi-session entries (AutoCorres2, Ordinary_Differential_Equations, UTP,
    …) are handled via an explicit prefix table.

    Examples::

        r = AFPResolver()
        r("Category3/Functor")                               # -> "Category3"
        r("AutoCorres2/main/AutoCorres_Main")                # -> "AutoCorres2_Main"
        r("Ordinary_Differential_Equations/Numerics/Foo")   # -> "HOL-ODE-Numerics"
        r("UTP/toolkit/utp")                                 # -> "UTP-Toolkit"
    """

    def __call__(self, theory: "Theory | str") -> str:
        name = _theory_name(theory)
        for prefix, session in _AFP_SESSION_PREFIXES:
            if name.startswith(prefix):
                return session
        # AFP default: top-level directory = session, or dot-notation prefix
        if "/" in name:
            return name.split("/", 1)[0]
        if "." in name:
            return name.split(".", 1)[0]
        return "HOL"


class CombinedResolver(SessionResolver):
    """Route to :class:`AFPResolver` or :class:`HOLResolver` based on theory name.

    Routing is decided by checking whether the theory's top-level path
    component (the AFP entry directory) is in a known set of AFP entry names.
    Anything not in that set is resolved as a HOL theory.

    The AFP entry set is most easily built from the AFP ROOT file::

        r = CombinedResolver.from_afp_root(
            afp_root_file="/path/to/AFP/thys/ROOT",
            hol_root_file="/path/to/Isabelle/src/HOL/ROOT",  # optional
        )
        r("Category3/Functor")   # -> "Category3"  (AFP)
        r("IMP/Big_Step")        # -> "HOL-IMP"    (HOL)

    You can also pass the AFP entry names directly::

        r = CombinedResolver(afp_entries={"Category3", "HOL-CSP", ...})
    """

    def __init__(
        self,
        afp_entries: set[str],
        hol_root_file=None,
    ) -> None:
        self._afp_entries = afp_entries
        self._hol = HOLResolver(root_file=hol_root_file)
        self._afp = AFPResolver()

    @classmethod
    def from_afp_root(cls, afp_root_file, hol_root_file=None) -> "CombinedResolver":
        """Build a resolver from an AFP ROOT file.

        Parses *afp_root_file* to collect all top-level AFP entry directory
        names, then constructs a :class:`CombinedResolver` using those as the
        AFP entry set.
        """
        sessions_map = _parse_root_file(Path(afp_root_file))
        # Top-level component of each in-dir recorded in the ROOT file
        afp_entries = {d.split("/")[0] for d in sessions_map if d}
        return cls(afp_entries, hol_root_file=hol_root_file)

    @classmethod
    def from_defaults(cls) -> "CombinedResolver":
        """Build a resolver using the standard Isabelle and AFP ROOT files.

        Expands ``$ISABELLE_HOME/src/HOL/ROOT`` and ``$AFP_BASE/thys/ROOT``
        from the environment.  Raises :exc:`OSError` if either variable is
        unset or the file does not exist.
        """
        import os

        isabelle_home = os.environ.get("ISABELLE_HOME", "")
        afp_base = os.environ.get("AFP_BASE", "")
        hol_root = Path(isabelle_home) / "src" / "HOL" / "ROOT"
        afp_root = Path(afp_base) / "thys" / "ROOT"
        for p in (hol_root, afp_root):
            if not p.exists():
                raise OSError(f"ROOT file not found: {p}")
        return cls.from_afp_root(afp_root_file=afp_root, hol_root_file=hol_root)

    def __call__(self, theory: "Theory | str") -> str:
        name = _theory_name(theory)
        top = name.split("/", 1)[0].split(".", 1)[0]
        if top in self._afp_entries:
            return self._afp(theory)
        return self._hol(theory)


# ---------------------------------------------------------------------------
# Module-level convenience singletons
# ---------------------------------------------------------------------------

#: Default HOL resolver using the built-in heuristic (no ROOT file).
HOL = HOLResolver()

#: Default AFP resolver.
AFP = AFPResolver()
