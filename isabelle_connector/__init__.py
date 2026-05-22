"""isabelle-connector — seamless Python interface to the Isabelle theorem prover.

Public API
----------
Core classes:
    IsabelleConnector   Manages the server connection and processes theories.
    Theory              Represents an Isabelle theory (existing or constructed on the fly).
    TheoryOutcome       Structured result of processing a single Theory.

Utilities:
    temp_theory         Convenience constructor for in-memory temporary theories.
    get_theory          Wrap an existing on-disk .thy file as a Theory object.
    list_theory_files   Recursively enumerate .thy files under a directory.
    hol_session         Infer sessions for theories in Isabelle's HOL tree.
    afp_session         Infer sessions for theories in AFP-style trees.
    session_from_root   Resolve sessions from an Isabelle ROOT file.
    parse_root_sessions Parse an Isabelle ROOT file into a {subdir: session} map.
    infer_session_name  Infer session name from a theory path (AFP convention only).
    infer_import_name   Convert a relative theory path to a qualified import string.
"""

from isabelle_connector.isabelle_connector import IsabelleConnector
from isabelle_connector.isabelle_types import Theory, TheoryOutcome
from isabelle_connector.utils import (
    afp_session,
    get_theory,
    hol_session,
    infer_import_name,
    infer_session_name,
    list_theory_files,
    parse_root_sessions,
    session_from_root,
    temp_theory,
)

__all__ = [
    # Core
    "IsabelleConnector",
    "Theory",
    "TheoryOutcome",
    # Utilities
    "temp_theory",
    "get_theory",
    "list_theory_files",
    "hol_session",
    "afp_session",
    "session_from_root",
    "parse_root_sessions",
    "infer_session_name",
    "infer_import_name",
]
