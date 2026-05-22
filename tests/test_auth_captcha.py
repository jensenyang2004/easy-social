from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from easy_social import create_app
from easy_social.extensions import db

pytestmark = pytest.mark.integration


@pytest.fixture()
def captcha_app():
    with tempfile.TemporaryDirectory() as temp_dir:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "UPLOAD_FOLDER": str(Path(temp_dir) / "uploads"),
                "MEDIA_STORAGE_BACKEND": "local",
                "WTF_CSRF_ENABLED": False,
                "TURNSTILE_SECRET_KEY": "test-secret-key",
            }
        )
        with app.app_context():
            db.create_all()
        yield app


@pytest.fixture()
def captcha_client(captcha_app):
    return captcha_app.test_client()


def _register(client, username: str, token: str = ""):
    return client.post(
        "/auth/register",
        data={
            "username": username,
            "email": f"{username}@example.com",
            "password": "password",
            "cf-turnstile-response": token,
        },
        follow_redirects=True,
    )


# --- integration: signup route with CAPTCHA enabled ---

def test_register_missing_token_is_blocked(captcha_client):
    with patch("easy_social.auth.verify_turnstile_token", return_value=False):
        response = _register(captcha_client, "alice", token="")
    assert response.status_code == 200
    assert b"CAPTCHA" in response.data
    assert b"Feed" not in response.data


def test_register_invalid_token_is_blocked(captcha_client):
    with patch("easy_social.auth.verify_turnstile_token", return_value=False):
        response = _register(captcha_client, "alice", token="bad-token")
    assert response.status_code == 200
    assert b"CAPTCHA" in response.data
    assert b"Feed" not in response.data


def test_register_valid_token_creates_account(captcha_client):
    with patch("easy_social.auth.verify_turnstile_token", return_value=True):
        response = _register(captcha_client, "alice", token="good-token")
    assert response.status_code == 200
    assert b"Feed" in response.data


def test_register_valid_token_passes_correct_args(captcha_app, captcha_client):
    with patch("easy_social.auth.verify_turnstile_token", return_value=True) as mock_verify:
        _register(captcha_client, "alice", token="my-token")
    mock_verify.assert_called_once_with("my-token", "test-secret-key")


# --- integration: no CAPTCHA key → verification skipped ---

def test_register_without_captcha_key_succeeds(client):
    # The default `client` fixture has no TURNSTILE_SECRET_KEY configured.
    client.application.config["TURNSTILE_SECRET_KEY"] = ""
    client.application.config["TURNSTILE_SITE_KEY"] = ""
    response = client.post(
        "/auth/register",
        data={"username": "bob", "email": "bob@example.com", "password": "password"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Feed" in response.data

def test_register_with_incomplete_captcha_config_fails(client):
    # Only one key configured -> error
    client.application.config["TURNSTILE_SITE_KEY"] = "some-key"
    client.application.config["TURNSTILE_SECRET_KEY"] = ""
    response = client.post(
        "/auth/register",
        data={"username": "eve", "email": "eve@example.com", "password": "password"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"CAPTCHA configuration is incomplete" in response.data
    assert b"Feed" not in response.data
