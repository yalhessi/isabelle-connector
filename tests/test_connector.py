import pytest

from isabelle_connector.isabelle_connector import IsabelleConnector
from isabelle_connector.utils import temp_theory


@pytest.mark.integration
def test_echo():
    isabelle = IsabelleConnector(name="test", working_directory=".")
    responses = isabelle._client.echo("Hello World")
    response = responses[-1].response_body
    assert response == '"Hello World"'


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
