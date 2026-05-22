"""pytest configuration for the isabelle-connector test suite.

Tests marked with ``@pytest.mark.integration`` require a live Isabelle server.
Run them explicitly with:

    pytest -m integration
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: requires a live Isabelle server process",
    )
