from isabelle_connector.config import HOL_DIR, INTERIM_DATA_DIR
from isabelle_connector.data_extraction import (
    template_and_type_extraction_theory,
    transitions_theory,
)
from isabelle_connector.decorators import theory_builder
from isabelle_connector.isabelle_connector import (
    IsabelleConnector,
    temp_theory,
)
from isabelle_connector.isabelle_types import TheoryConfig
from isabelle_connector.utils import get_theory


def test_echo():
    isabelle = IsabelleConnector(name="test", working_directory=".")
    responses = isabelle._client.echo("Hello World")
    response = responses[-1].response_body
    assert response == "Hello World"


def test_use_thy():
    isabelle = IsabelleConnector(name="test", working_directory=".")
    query = 'ML\\<open> let val res = "Hello, World!" in res end \\<close>'
    test_thy = temp_theory(
        working_directory=".",
        queries=[query],
        imports=[],
        name="Test",
    )

    result = isabelle.use_theories(
        [test_thy],
        rm_if_temp=True,
    )
    assert test_thy in result and result[test_thy].values == ["Hello, World!"]


@theory_builder(prefix="Simpl")
def simpl_thy(theory_config: TheoryConfig) -> str:
    return """
        let
            val res = "Hello, World!"
         in
            res
         end"""


def test_thy_builder():
    isabelle = IsabelleConnector(name="test", working_directory=".")
    test_config = TheoryConfig(
        working_directory=str(INTERIM_DATA_DIR),
        session="HOL",
        imports=[],
    )
    test_thy = simpl_thy(theory_config=test_config)
    result = isabelle.use_theories(
        [test_thy],
        rm_if_temp=True,
    )
    assert test_thy in result and result[test_thy].values == ["Hello, World!"]

