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
Session resolvers:
    SessionResolver     Abstract base class for all session resolvers.
    HOLResolver         Resolver for Isabelle/HOL distribution source trees.
    AFPResolver         Resolver for AFP-style repositories.
    RootFileResolver    Resolver backed by an Isabelle ROOT file.
    CombinedResolver    Routes between HOL and AFP resolvers by entry name.
    HOL                 Pre-built HOLResolver() singleton.
    AFP                 Pre-built AFPResolver() singleton.
"""

from isabelle_connector.isabelle_connector import IsabelleConnector
from isabelle_connector.isabelle_types import Theory, TheoryOutcome
from isabelle_connector.session_resolver import (
    AFP,
    HOL,
    AFPResolver,
    CombinedResolver,
    HOLResolver,
    RootFileResolver,
    SessionResolver,
)
from isabelle_connector.utils import (
    get_theory,
    infer_import_name,
    infer_session_name,
    list_theory_files,
    temp_theory,
)
from loguru import logger

__all__ = [
    # Core
    "IsabelleConnector",
    "Theory",
    "TheoryOutcome",
    # Utilities
    "temp_theory",
    "get_theory",
    "list_theory_files",
    # Session resolvers
    "SessionResolver",
    "HOLResolver",
    "AFPResolver",
    "RootFileResolver",
    "CombinedResolver",
    "HOL",
    "AFP",
    # Utilities
    "infer_session_name",
    "infer_import_name",
]

logger.disable("isabelle_connector")
