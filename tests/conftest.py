# test_swiggy_flow.py and test_v2.py are plain scripts (run with python); they stub the agents package at import.
import pytest

collect_ignore = ["test_swiggy_flow.py", "test_v2.py"]


@pytest.fixture(autouse=True)
def _no_app_key(monkeypatch):
    """.env may hold APP_KEY (phone mode); tests that need it set it themselves."""
    monkeypatch.delenv("APP_KEY", raising=False)
