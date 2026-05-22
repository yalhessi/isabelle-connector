import pytest

from example.data_extraction import (
    ExtractionConfig,
    equivalence_theory_from_assumptions,
    freshen_placeholder_vars,
    lemma_object_to_body,
    rediscover_conjecture,
    roughspec,
    roughspec_with_match_lemma,
)
from isabelle_connector.isabelle_connector import IsabelleConnector
from isabelle_connector.isabelle_types import Theory
from isabelle_connector.utils import temp_theory


@pytest.mark.integration
def test_use_thy():
    isabelle = IsabelleConnector(name="test", working_directory=".")
    # Top-level val binding produces "val res = ... : string" in writeln output
    query = 'ML\\<open> val res = "Hello, World!" \\<close>'
    test_thy = temp_theory(
        working_directory=".",
        queries=[query],
        imports=["Main"],
        name="Test",
    )

    outcomes = isabelle.use_theories(
        [test_thy],
        rm_after=True,
    )
    assert outcomes[test_thy].values == ["Hello, World!"]


def test_rediscover_conjecture_uses_safe_fact_lookup(tmp_path):
    src = Theory(name="Library/Landau_Symbols", working_directory=str(tmp_path))
    configs = ExtractionConfig(imports=["Lemmanaid.RoughSpec", "Lemmanaid.ExtractLemmas"], working_directory=str(tmp_path))

    thy = rediscover_conjecture("Landau_Symbols.asymp_equiv_add_rightI", src, configs)
    body = "\n".join(thy.queries)

    assert "@{thm" not in body
    assert "Extract_Lemmas.get_persisted_thm" in body
    assert "Proof_Context.get_thm" not in body
    assert "Global_Theory.all_thms_of" not in body
    assert '"inaccessible_fact"' in body


def test_roughspec_with_match_lemma_uses_safe_fact_lookup(tmp_path):
    src = Theory(name="Library/Landau_Symbols", working_directory=str(tmp_path))
    configs = ExtractionConfig(imports=["Lemmanaid.RoughSpec", "Lemmanaid.ExtractLemmas"], working_directory=str(tmp_path))

    thy = roughspec_with_match_lemma(
        template="?H1 x_1 = x_1",
        consts=["Set.Collect"],
        gold_standard="Landau_Symbols.asymp_equiv_add_rightI",
        thy=src,
        configs=configs,
    )
    body = "\n".join(thy.queries)

    assert "@{thm" not in body
    assert "Extract_Lemmas.get_persisted_thm" in body
    assert "Proof_Context.get_thm" not in body
    assert "Global_Theory.all_thms_of" not in body
    assert "declare [[ML_catch_all]]" in body
    assert '"inaccessible_fact"' in body
    assert '"malformed_template"' in body
    assert "Poly_Template.read_from_string" in body
    assert "templateCandidatesPolyWithCommands" in body
    assert "lemmas_terms = map (Print_Mode.setmp [] (Syntax.string_of_term" not in body


def test_lemma_object_to_body_uses_safe_fact_lookup(tmp_path):
    src = Theory(name="Library/Landau_Symbols", working_directory=str(tmp_path))
    configs = ExtractionConfig(imports=["Lemmanaid.RoughSpec", "Lemmanaid.ExtractLemmas"], working_directory=str(tmp_path))

    thy = lemma_object_to_body("Landau_Symbols.asymp_equiv_add_rightI", src, configs)
    body = "\n".join(thy.queries)

    assert "@{thm" not in body
    assert "Extract_Lemmas.get_persisted_thm" in body
    assert "Proof_Context.get_thm" not in body
    assert "Global_Theory.all_thms_of" not in body
    assert "<inaccessible_fact>" in body
    assert "Syntax_Trans.no_bracketsN" in body


def test_lemma_object_to_body_includes_historical_printer_compatibility(tmp_path):
    theory_dir = tmp_path / "Octonions"
    theory_dir.mkdir()
    (theory_dir / "Octonions.thy").write_text("", encoding="utf-8")
    (theory_dir / "Cross_Product_7.thy").write_text("", encoding="utf-8")

    src = Theory(name="Octonions/Octonions", working_directory=str(tmp_path))
    configs = ExtractionConfig(imports=["Lemmanaid.RoughSpec", "Lemmanaid.ExtractLemmas"], working_directory=str(tmp_path))

    thy = lemma_object_to_body("Octonions.mult_hv_eq_cross_dot", src, configs)
    body = "\n".join(thy.queries)

    assert 'val imported_local_theories = ["Cross_Product_7"]' in body
    assert "Free (Long_Name.base_name c, T)" in body
    assert 'c = "Groups.zero_class.zero"' in body
    assert "Type.constraint T t" in body


def test_rediscover_conjecture_escapes_symbolic_fact_names(tmp_path):
    src = Theory(name="Decision_Procs/MIR", working_directory=str(tmp_path))
    configs = ExtractionConfig(imports=["Lemmanaid.RoughSpec", "Lemmanaid.ExtractLemmas"], working_directory=str(tmp_path))

    thy = rediscover_conjecture(r"MIR.\<beta>_int", src, configs)
    body = "\n".join(thy.queries)

    assert r"@{verbatim \<open>MIR.\<beta>_int\<close>}" in body
    assert r"\092<beta>_int" not in body
    assert '"malformed_template"' in body
    assert "Poly_Template.read_from_string" in body
    assert "templateCandidatesPolyWithCommands" in body


def test_roughspec_escapes_symbolic_templates_and_consts(tmp_path):
    src = Theory(name="Decision_Procs/MIR", working_directory=str(tmp_path))
    configs = ExtractionConfig(imports=["Lemmanaid.RoughSpec", "Lemmanaid.ExtractLemmas"], working_directory=str(tmp_path))

    thy = roughspec(
        template=r"\<lbrakk>?H1 x_1 x_2; x_3 \<in> ?H2 (?H3 x_1)\<rbrakk> \<Longrightarrow> ?H4 x_3 x_2",
        consts=[r"MIR.\<beta>", "MIR.isint"],
        thy=src,
        configs=configs,
    )
    body = "\n".join(thy.queries)

    assert "declare [[ML_catch_all]]" in body
    assert '"malformed_template"' in body
    assert "Poly_Template.read_from_string" in body
    assert r"\092<lbrakk>" in body
    assert r"\092<Longrightarrow>" in body
    assert r"\092<beta>" in body
    assert r"@{verbatim \<open>\<lbrakk>?H1 x_1 x_2; x_3 \<in> ?H2 (?H3 x_1)\<rbrakk> \<Longrightarrow> ?H4 x_3 x_2\<close>}" not in body


def test_roughspec_with_match_lemma_treats_malformed_prediction_as_plain_string(tmp_path):
    src = Theory(name="Decision_Procs/MIR", working_directory=str(tmp_path))
    configs = ExtractionConfig(imports=["Lemmanaid.RoughSpec", "Lemmanaid.ExtractLemmas"], working_directory=str(tmp_path))

    thy = roughspec_with_match_lemma(
        template=r"?H1 x_1 \<lambda",
        consts=[r"MIR.\<beta>"],
        gold_standard=r"MIR.\<beta>_int",
        thy=src,
        configs=configs,
    )
    body = "\n".join(thy.queries)

    assert "declare [[ML_catch_all]]" in body
    assert '"malformed_template"' in body
    assert "Poly_Template.read_from_string" in body
    assert r'val template = "?H1 x_1 \092<lambda"' in body
    assert r"@{verbatim \<open>MIR.\<beta>_int\<close>}" in body


def test_freshen_placeholder_vars_only_renames_generated_placeholders():
    text = r'Foo.x_1 = x_1 \<Longrightarrow> y_0 = x_1'
    renamed = freshen_placeholder_vars(text, "assm0")

    assert "Foo.x_1" in renamed
    assert "x_1_assm0" in renamed
    assert "y_0_assm0" in renamed
    assert "Foo.x_1_assm0" not in renamed


def test_equivalence_theory_from_assumptions_freshens_each_term_namespace(tmp_path):
    src = Theory(name="Decision_Procs/MIR", working_directory=str(tmp_path))
    configs = ExtractionConfig(imports=["Lemmanaid.RoughSpec", "Lemmanaid.ExtractLemmas"], working_directory=str(tmp_path))

    thy = equivalence_theory_from_assumptions(
        assm_conjs=[
            r'lemma "Foo.x_1 = x_1 \<Longrightarrow> y_0 = x_1"',
            r'lemma "x_1 = y_0"',
        ],
        conc_conj=r'lemma "x_1 = y_0"',
        src_thy=src,
        configs=configs,
    )
    body = "\n".join(thy.queries)

    assert 'Foo.x_1 = x_1_assm0' in body
    assert 'y_0_assm0 = x_1_assm0' in body
    assert 'x_1_assm1 = y_0_assm1' in body
    assert 'shows "x_1_conc = y_0_conc"' in body
    assert 'x_1 = y_0"' not in body
