"""
E2E Playwright tests for the Turnstile CAPTCHA signup flow.

Uses Cloudflare's published test keys so the widget auto-passes without
any user interaction:
  Site key  1x00000000000000000000AA  → always passes
  Secret    1x0000000000000000000000000000000AA  → siteverify returns success

Requires:  pip install pytest-playwright && playwright install chromium
Run with:  pytest -m e2e tests/test_e2e_playwright.py
"""

from __future__ import annotations
import pytest

pytest.importorskip("playwright", reason="playwright not installed — skipping E2E tests")

@pytest.mark.e2e
def test_register_with_turnstile_auto_pass(page, captcha_live_server):
    """Full signup flow: Turnstile widget auto-passes with the test site key."""
    page.goto(f"{captcha_live_server}/auth/register")

    page.fill("[name=username]", "e2euser")
    page.fill("[name=email]", "e2euser@example.com")
    page.fill("[name=password]", "s3cret!")

    # Wait for the Turnstile widget to silently fill the hidden input.
    # With the "always passes" test key this happens within a few seconds.
    page.wait_for_function(
        "() => (document.querySelector('[name=\"cf-turnstile-response\"]') || {}).value !== ''",
        timeout=15_000,
    )

    page.click("button[type=submit]")
    page.wait_for_url(f"{captcha_live_server}/", timeout=10_000)

    assert "Feed" in page.content()


@pytest.mark.e2e
def test_register_blocked_when_token_cleared(page, captcha_live_server):
    """Server rejects the form when the Turnstile token is absent."""
    page.goto(f"{captcha_live_server}/auth/register")

    page.fill("[name=username]", "notcreated")
    page.fill("[name=email]", "notcreated@example.com")
    page.fill("[name=password]", "s3cret!")

    # Wait until Turnstile has populated the token, then blank it.
    page.wait_for_function(
        "() => (document.querySelector('[name=\"cf-turnstile-response\"]') || {}).value !== ''",
        timeout=15_000,
    )

    # Blank the hidden token to simulate a missing/tampered response.
    page.evaluate(
        """() => {
            const el = document.querySelector('[name="cf-turnstile-response"]');
            if (el) el.value = '';
        }"""
    )

    page.click("button[type=submit]")

    # Should stay on the register page with a CAPTCHA error message.
    page.wait_for_url(f"{captcha_live_server}/auth/register", timeout=5_000)
    assert "CAPTCHA" in page.content()
    assert "Feed" not in page.content()
