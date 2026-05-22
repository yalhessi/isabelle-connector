from isabelle_connector.isabelle_types import Theory
from isabelle_connector.utils import (
    afp_session,
    get_theory,
    hol_session,
    parse_root_sessions,
    session_from_root,
)


def test_hol_session_matches_known_hol_tree_cases():
    assert hol_session("Main") == "HOL"
    assert hol_session("HOL-IMP.Big_Step") == "HOL-IMP"
    assert hol_session("IMP/AExp") == "HOL-IMP"
    assert hol_session("HOLCF/IOA/ABP/Correctness") == "IOA-ABP"
    assert hol_session("HOLCF/Domain") == "HOLCF"
    assert hol_session("Decision_Procs/MIR") == "HOL-Decision_Procs"
    assert hol_session(Theory(name="MicroJava/BV/BVSpec", working_directory=".")) == "HOL-MicroJava"


def test_afp_session_matches_known_afp_special_cases():
    assert afp_session("AutoCorres2/main/AutoCorres_Main") == "AutoCorres2_Main"
    assert afp_session("AutoCorres2/tests/Simpl") == "AutoCorres2_Test"
    assert afp_session("Ordinary_Differential_Equations/Numerics/Numerics") == (
        "HOL-ODE-Numerics"
    )
    assert afp_session("Ordinary_Differential_Equations/Ex/Lorenz/C0/Lorenz_C0") == (
        "Lorenz_C0"
    )
    assert afp_session("UTP/toolkit/utp") == "UTP-Toolkit"
    assert afp_session("Category3/Functor") == "Category3"
    assert afp_session("Category3.Functor") == "Category3"


def test_session_from_root_uses_deepest_matching_directory(tmp_path):
    root = tmp_path / "ROOT"
    root.write_text(
        """
session HOL =
session "HOL-IMP" in IMP =
session "IOA-ABP" in "HOLCF/IOA/ABP" =
""",
        encoding="utf-8",
    )

    assert parse_root_sessions(root) == {
        "": "HOL",
        "IMP": "HOL-IMP",
        "HOLCF/IOA/ABP": "IOA-ABP",
    }
    assert session_from_root("IMP/AExp", root) == "HOL-IMP"
    assert session_from_root("HOLCF/IOA/ABP/Correctness", root) == "IOA-ABP"
    assert session_from_root("Main", root) == "HOL"


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

    thy = get_theory(theory_file, tmp_path, session_resolver=afp_session)

    assert thy.name == "Category3/Functor"
    assert thy.session == "Category3"
