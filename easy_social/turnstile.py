from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import urlencode

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile_token(token: str, secret: str) -> bool:
    if not token or not secret:
        return False
    payload = urlencode({"secret": secret, "response": token}).encode()
    req = urllib.request.Request(VERIFY_URL, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return bool(data.get("success"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return False
