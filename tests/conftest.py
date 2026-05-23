from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from easy_social import create_app
from easy_social.extensions import db


@pytest.fixture()
def app():
    with tempfile.TemporaryDirectory() as temp_dir:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "UPLOAD_FOLDER": str(Path(temp_dir) / "uploads"),
                "MEDIA_STORAGE_BACKEND": "local",
                "WTF_CSRF_ENABLED": False,
                "TURNSTILE_SITE_KEY": "",
                "TURNSTILE_SECRET_KEY": "",
            }
        )
        with app.app_context():
            db.create_all()
        yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, username: str, email: str | None = None, password: str = "password"):
    return client.post(
        "/auth/register",
        data={
            "username": username,
            "email": email or f"{username}@example.com",
            "password": password,
        },
        follow_redirects=True,
    )


def login(client, username_or_email: str, password: str = "password"):
    return client.post(
        "/auth/login",
        data={"username_or_email": username_or_email, "password": password},
        follow_redirects=True,
    )


def logout(client):
    return client.post("/auth/logout", follow_redirects=True)

import threading
from werkzeug.serving import make_server

# Cloudflare published test keys (always pass, safe to commit)
_SITE_KEY = "1x00000000000000000000AA"
_SECRET_KEY = "1x0000000000000000000000000000000AA"

@pytest.fixture(scope="module")
def captcha_live_server():
    with tempfile.TemporaryDirectory() as temp_dir:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{Path(temp_dir) / 'e2e.sqlite'}",
                "UPLOAD_FOLDER": str(Path(temp_dir) / "uploads"),
                "MEDIA_STORAGE_BACKEND": "local",
                "TURNSTILE_SITE_KEY": _SITE_KEY,
                "TURNSTILE_SECRET_KEY": _SECRET_KEY,
            }
        )
        with app.app_context():
            db.create_all()

        try:
            server = make_server("127.0.0.1", 0, app, threaded=True)
        except OSError:
            pytest.skip("Could not bind to a local port")

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"

        yield base_url

        server.shutdown()
        thread.join(timeout=5)
