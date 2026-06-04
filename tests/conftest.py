import os
import pytest


@pytest.fixture(autouse=True)
def set_cgu_api_key(monkeypatch):
    """Provide dummy API keys so functions that require them can proceed in tests.
    Individual tests that need to test the 'no key' scenario mock the respective getter directly."""
    monkeypatch.setenv("CGU_API_KEY", "test-dummy-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-dummy-anthropic-key")
