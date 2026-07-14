from __future__ import annotations
import json
from unittest.mock import MagicMock


def mock_urlopen(payload: dict):
    """Return a context-manager mock that yields *payload* as the Anthropic API response."""
    data = json.dumps({"content": [{"text": json.dumps(payload)}]}).encode("utf-8")
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
    cm.__exit__ = MagicMock(return_value=False)
    return cm
