from isabelle_connector.isabelle_types import Theory


def test_theory_cache_round_trip(tmp_path):
    thy = Theory(name="Test", working_directory=str(tmp_path))
    response = [{"kind": "writeln", "message": 'val result = ("ok", []) : string'}]

    thy.write_cache(response)

    assert thy.cache_exists() is True
    assert thy.read_cache() == response


def test_theory_cache_ignores_truncated_files(tmp_path):
    thy = Theory(name="Test", working_directory=str(tmp_path))
    cache_path = tmp_path / "Test.thy.result"
    cache_path.write_bytes(b"")

    assert thy.cache_exists() is False
    assert thy.read_cache() is None
    assert cache_path.exists() is False
