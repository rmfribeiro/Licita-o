import os
import pytest


@pytest.fixture(autouse=True)
def set_cgu_api_key(monkeypatch):
    """Provide a dummy CGU_API_KEY so functions that require it can proceed in tests.
    Individual tests that need to test the 'no key' scenario mock _get_cgu_key directly."""
    monkeypatch.setenv("CGU_API_KEY", "test-dummy-key")
