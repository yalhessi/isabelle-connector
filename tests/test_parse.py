import json
from types import SimpleNamespace

from isabelle_connector.isabelle_types import Theory
from isabelle_connector.parse import extract_messages_from_responses


def test_extract_messages_attaches_top_level_errors(tmp_path):
    thy = Theory(name="Test", working_directory=str(tmp_path))
    response = SimpleNamespace(
        response_type="FINISHED",
        response_body=json.dumps(
            {
                "ok": False,
                "errors": [
                    {
                        "kind": "error",
                        "message": "Bad theory import",
                        "pos": {"file": str(tmp_path / "Test.thy")},
                    }
                ],
                "nodes": [
                    {
                        "theory_name": "Draft.Test",
                        "messages": [],
                        "status": {"ok": False},
                    }
                ],
            }
        ),
    )

    messages = extract_messages_from_responses([thy], [response])

    assert messages[thy] == [
        {
            "kind": "error",
            "message": "Bad theory import",
            "pos": {"file": str(tmp_path / "Test.thy")},
        }
    ]


def test_extract_messages_synthesizes_failed_node_errors(tmp_path):
    thy = Theory(name="Test", working_directory=str(tmp_path))
    response = SimpleNamespace(
        response_type="FINISHED",
        response_body=json.dumps(
            {
                "ok": False,
                "errors": [],
                "nodes": [
                    {
                        "theory_name": "Draft.Test",
                        "messages": [],
                        "status": {"ok": False},
                    }
                ],
            }
        ),
    )

    messages = extract_messages_from_responses([thy], [response])

    assert messages[thy] == [
        {
            "kind": "error",
            "message": "Theory processing failed without an explicit message: Test",
        }
    ]
