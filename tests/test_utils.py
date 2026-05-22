import pytest

from isabelle_connector.isabelle_types import Theory
from isabelle_connector.session_resolver import (
    AFP,
    HOL,
    AFPResolver,
    HOLResolver,
    RootFileResolver,
)
from isabelle_connector.utils import (
    get_theory,
)

_ROOT_SNIPPET = """
session HOL =
session "HOL-IMP" in IMP =
session "IOA-ABP" in "HOLCF/IOA/ABP" =
"""


def test_get_theory_resolves_session_from_root_file(tmp_path):
    root = tmp_path / "ROOT"
    root.write_text(
        """
session HOL =
session "HOL-IMP" in IMP =
""",
        encoding="utf-8",
    )
    theory_file = tmp_path / "IMP" / "AExp.thy"
    theory_file.parent.mkdir()
    theory_file.write_text("theory AExp imports Main begin end\n", encoding="utf-8")

    thy = get_theory(theory_file, tmp_path)

    assert thy.name == "IMP/AExp"
    assert thy.session == "HOL-IMP"


def test_get_theory_accepts_explicit_session_resolver(tmp_path):
    theory_file = tmp_path / "Category3" / "Functor.thy"
    theory_file.parent.mkdir()
    theory_file.write_text("theory Functor imports Main begin end\n", encoding="utf-8")

    thy = get_theory(theory_file, tmp_path, session_resolver=AFP)

    assert thy.name == "Category3/Functor"
    assert thy.session == "Category3"


# ---------------------------------------------------------------------------
# Class-based resolver tests
# ---------------------------------------------------------------------------


class TestRootFileResolver:
    @pytest.fixture()
    def resolver(self, tmp_path):
        root = tmp_path / "ROOT"
        root.write_text(_ROOT_SNIPPET, encoding="utf-8")
        return RootFileResolver(root)

    def test_resolves_by_directory(self, resolver):
        assert resolver("IMP/AExp") == "HOL-IMP"

    def test_resolves_deep_path(self, resolver):
        assert resolver("HOLCF/IOA/ABP/Correctness") == "IOA-ABP"

    def test_falls_back_to_root_session(self, resolver):
        assert resolver("Main") == "HOL"

    def test_sessions_map_property(self, resolver):
        assert resolver.sessions_map == {"": "HOL", "IMP": "HOL-IMP", "HOLCF/IOA/ABP": "IOA-ABP"}

    def test_accepts_theory_object(self, resolver):
        assert resolver(Theory(name="IMP/Big_Step", working_directory=".")) == "HOL-IMP"


class TestHOLResolver:
    def test_bare_name_is_hol(self):
        assert HOLResolver()("Main") == "HOL"

    def test_dot_notation_extracts_session(self):
        assert HOLResolver()("HOL-IMP.Big_Step") == "HOL-IMP"

    def test_slash_path_heuristic(self):
        assert HOLResolver()("IMP/AExp") == "HOL-IMP"

    def test_holcf_ioa_path(self):
        assert HOLResolver()("HOLCF/IOA/ABP/Correctness") == "IOA-ABP"

    def test_holcf_path(self):
        assert HOLResolver()("HOLCF/Domain") == "HOLCF"

    def test_known_prefix_table_entry(self):
        assert HOLResolver()("Decision_Procs/MIR") == "HOL-Decision_Procs"

    def test_accepts_theory_object(self):
        assert HOLResolver()(Theory(name="MicroJava/BV/BVSpec", working_directory=".")) == "HOL-MicroJava"

    def test_delegates_to_root_file_when_provided(self, tmp_path):
        root = tmp_path / "ROOT"
        root.write_text(_ROOT_SNIPPET, encoding="utf-8")
        assert HOLResolver(root_file=root)("IMP/AExp") == "HOL-IMP"

    def test_singleton_hol_works(self):
        assert HOL("Main") == "HOL"
        assert HOL("IMP/AExp") == "HOL-IMP"


class TestAFPResolver:
    def test_simple_entry(self):
        assert AFPResolver()("Category3/Functor") == "Category3"

    def test_dot_notation(self):
        assert AFPResolver()("Category3.Functor") == "Category3"

    def test_multi_session_prefix(self):
        assert AFPResolver()("AutoCorres2/main/AutoCorres_Main") == "AutoCorres2_Main"
        assert AFPResolver()("AutoCorres2/tests/Simpl") == "AutoCorres2_Test"

    def test_ode_numerics(self):
        assert AFPResolver()("Ordinary_Differential_Equations/Numerics/Foo") == "HOL-ODE-Numerics"

    def test_utp_toolkit(self):
        assert AFPResolver()("UTP/toolkit/utp") == "UTP-Toolkit"

    def test_singleton_afp_works(self):
        assert AFP("Category3/Functor") == "Category3"

    def test_resolver_usable_as_get_theory_callback(self, tmp_path):
        theory_file = tmp_path / "Category3" / "Functor.thy"
        theory_file.parent.mkdir()
        theory_file.write_text("theory Functor imports Main begin end\n", encoding="utf-8")
        thy = get_theory(theory_file, tmp_path, session_resolver=AFPResolver())
        assert thy.session == "Category3"

