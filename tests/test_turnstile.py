from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from easy_social.turnstile import verify_turnstile_token

pytestmark = pytest.mark.unit


def _mock_urlopen(payload: dict):
    """Return a context-manager mock that yields a response reading `payload`."""
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    response.__enter__ = lambda s: s
    response.__exit__ = MagicMock(return_value=False)
    return response


def test_empty_token_returns_false():
    assert verify_turnstile_token("", "secret") is False


def test_empty_secret_returns_false():
    assert verify_turnstile_token("token", "") is False


def test_both_empty_returns_false():
    assert verify_turnstile_token("", "") is False


def test_api_success_true_returns_true():
    with patch("easy_social.turnstile.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_urlopen({"success": True})
        assert verify_turnstile_token("valid-token", "secret") is True


def test_api_success_false_returns_false():
    with patch("easy_social.turnstile.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_urlopen({"success": False, "error-codes": ["invalid-input-response"]})
        assert verify_turnstile_token("bad-token", "secret") is False


def test_network_error_returns_false():
    with patch("easy_social.turnstile.urllib.request.urlopen") as mock_open:
        mock_open.side_effect = urllib.error.URLError("connection refused")
        assert verify_turnstile_token("token", "secret") is False


def test_malformed_json_returns_false():
    response = MagicMock()
    response.read.return_value = b"not-json"
    response.__enter__ = lambda s: s
    response.__exit__ = MagicMock(return_value=False)
    with patch("easy_social.turnstile.urllib.request.urlopen") as mock_open:
        mock_open.return_value = response
        assert verify_turnstile_token("token", "secret") is False


def test_missing_success_key_returns_false():
    with patch("easy_social.turnstile.urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_urlopen({})
        assert verify_turnstile_token("token", "secret") is False
