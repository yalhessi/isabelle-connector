
from isabelle_connector.config import HOL_DIR, INTERIM_DATA_DIR
from isabelle_connector.data_extraction import template_and_type_extraction_theory, transitions_theory
from isabelle_connector.isabelle_connector import IsabelleConnector
from isabelle_connector.isabelle_types import TheoryConfig
from isabelle_connector.utils import get_theory


def test_transitions():
    isabelle = IsabelleConnector(name="test", working_directory=".")
    test_config = TheoryConfig(
        working_directory=str(INTERIM_DATA_DIR),
        session="HOL",
        imports=[],
    )
    src_thy = get_theory("IMP/AExp.thy", HOL_DIR)
    transition_thy = transitions_theory(src_thy, theory_config=test_config)
    results = isabelle.use_theories(
        [transition_thy],
        rm_if_temp=True,
    )
    assert results[transition_thy].values, "No transitions extracted"


def test_info_extraction():
    isabelle = IsabelleConnector(name="test", working_directory=".")
    test_config = TheoryConfig(
        working_directory=str(INTERIM_DATA_DIR),
        session="HOL-IMP",
        imports=[],
    )
    src_thy = get_theory("IMP/AExp.thy", HOL_DIR)
    info_thy = template_and_type_extraction_theory(src_thy, theory_config=test_config)
    results = isabelle.use_theories(
        [info_thy],
        rm_if_temp=True,
    )
    assert results[info_thy].values, "No info extracted"
