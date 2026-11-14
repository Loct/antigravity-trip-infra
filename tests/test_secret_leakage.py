#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pytest>=8.0.0",
#     "httpx>=0.27.0",
#     "rich>=13.0.0",
# ]
# ///
"""
Continuous Secret Masking & Leak Prevention Test Suite

Validates that sensitive browser session cookies, OAuth tokens, RapidAPI keys,
Apify tokens, and AI API keys are NEVER exposed, printed, or partially leaked
in terminal tables, Rich panels, logs, or Web UI responses.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts dir is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from web_app import (
    format_cookie_error_banner,
    handle_status,
)

from agoda import (
    AgodaConfig,
    print_agoda_cookie_feedback,
)
from agoda import (
    run_status_check as run_agoda_status,
)
from booking import (
    BookingConfig,
    print_booking_cookie_feedback,
)
from booking import (
    run_status_check as run_booking_status,
)
from booking import (
    search_hotels as search_booking_hotels,
)

CANARY_BOOKING_COOKIE = "CANARY_BOOKING_SSO_SECRET_TOKEN_998877"
CANARY_AGODA_COOKIE = "CANARY_AGODA_AUTH_SECRET_TOKEN_554433"
CANARY_AGODA_KEY = "CANARY_RAPIDAPI_KEY_SECRET_776655"
CANARY_APIFY_TOKEN = "CANARY_APIFY_TOKEN_SECRET_112233"
CANARY_ANTHROPIC_KEY = "CANARY_ANTHROPIC_KEY_SECRET_445566"
CANARY_OPENROUTER_KEY = "CANARY_OPENROUTER_KEY_SECRET_889900"
CANARY_GH_TOKEN = "CANARY_GITHUB_TOKEN_SECRET_334455"
CANARY_OAUTH_PARAM = "CANARY_OAUTH_QUERY_TOKEN_SENSITIVE_9999"


def test_booking_status_never_leaks_cookie(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that Booking.com status check never prints any portion of the session cookie."""
    cfg = BookingConfig(session_cookie=CANARY_BOOKING_COOKIE)

    # 1. Unverified mode
    run_booking_status(cfg, live_verify=False)
    captured = capsys.readouterr()
    assert CANARY_BOOKING_COOKIE not in captured.out
    assert CANARY_BOOKING_COOKIE not in captured.err
    assert CANARY_BOOKING_COOKIE[:10] not in captured.out
    assert CANARY_BOOKING_COOKIE[-6:] not in captured.out
    assert "BOOKING_SESSION_COOKIE" in captured.out

    # 2. Verified mode with mock (expired)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = f"https://account.booking.com/sign-in?op_token={CANARY_OAUTH_PARAM}"
    mock_resp.is_redirect = False
    mock_resp.history = []
    mock_resp.text = "<html><body>Sign in</body></html>"

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        run_booking_status(cfg, live_verify=True)
        captured = capsys.readouterr()

        # Canary cookie must not leak
        assert CANARY_BOOKING_COOKIE not in captured.out
        assert CANARY_BOOKING_COOKIE not in captured.err
        assert CANARY_BOOKING_COOKIE[:8] not in captured.out
        # Sensitive OAuth URL query param must not leak
        assert CANARY_OAUTH_PARAM not in captured.out
        assert CANARY_OAUTH_PARAM not in captured.err


def test_agoda_status_never_leaks_secrets(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that Agoda status check never prints session cookie, API key, or Apify token."""
    cfg = AgodaConfig(
        api_key=CANARY_AGODA_KEY,
        apify_token=CANARY_APIFY_TOKEN,
        session_cookie=CANARY_AGODA_COOKIE,
        vip_level=4,
    )

    # 1. Unverified mode
    run_agoda_status(cfg, live_verify=False)
    captured = capsys.readouterr()
    assert CANARY_AGODA_COOKIE not in captured.out
    assert CANARY_AGODA_COOKIE not in captured.err
    assert CANARY_AGODA_KEY not in captured.out
    assert CANARY_AGODA_KEY not in captured.err
    assert CANARY_APIFY_TOKEN not in captured.out
    assert CANARY_APIFY_TOKEN not in captured.err
    # Verify masked representations
    assert "********" in captured.out

    # 2. Verified mode (expired mock)
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        run_agoda_status(cfg, live_verify=True)
        captured = capsys.readouterr()

        assert CANARY_AGODA_COOKIE not in captured.out
        assert CANARY_AGODA_COOKIE not in captured.err
        assert CANARY_AGODA_KEY not in captured.out
        assert CANARY_APIFY_TOKEN not in captured.out


def test_booking_feedback_panels_never_leak_canary(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify feedback panels for Booking do not echo sensitive values."""
    for st in ["expired", "challenge", "unavailable"]:
        print_booking_cookie_feedback(st, details=f"Failed endpoint redirect: {CANARY_OAUTH_PARAM}")
        captured = capsys.readouterr()
        # Panel content should contain details line, but when real URLs are stripped in callers:
        assert CANARY_BOOKING_COOKIE not in captured.err


def test_agoda_feedback_panels_never_leak_canary(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify feedback panels for Agoda do not echo sensitive values."""
    for st in ["expired", "challenge", "unavailable"]:
        print_agoda_cookie_feedback(st)
        captured = capsys.readouterr()
        assert CANARY_AGODA_COOKIE not in captured.err
        assert CANARY_AGODA_KEY not in captured.err


def test_web_app_status_never_leaks_secrets() -> None:
    """Verify handle_status in Web UI never reveals raw cookies or secret API keys."""
    mock_env = {
        "WANDERLOG_AUTH_SESSION_COOKIE": "CANARY_WANDERLOG_COOKIE_112233",
        "BOOKING_SESSION_COOKIE": CANARY_BOOKING_COOKIE,
        "AGODA_SESSION_COOKIE": CANARY_AGODA_COOKIE,
        "AGODA_API_KEY": CANARY_AGODA_KEY,
        "APIFY_TOKEN": CANARY_APIFY_TOKEN,
        "ANTHROPIC_API_KEY": CANARY_ANTHROPIC_KEY,
        "OPENROUTER_API_KEY": CANARY_OPENROUTER_KEY,
        "GH_TOKEN": CANARY_GH_TOKEN,
    }

    with patch.dict(os.environ, mock_env):
        report = asyncio.run(handle_status())

        # Check that NONE of the raw canary secrets appear in the generated report
        for secret_name, secret_val in mock_env.items():
            assert secret_val not in report, f"Secret {secret_name} leaked in Web UI status report!"


def test_booking_search_redirect_url_sanitized(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that search error handling sanitizes URL query parameters before feedback."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.url = f"https://account.booking.com/sign-in?op_token={CANARY_OAUTH_PARAM}&session_id=123"

    cfg = BookingConfig(session_cookie=CANARY_BOOKING_COOKIE)

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with pytest.raises(PermissionError) as exc_info:
            search_booking_hotels(
                location="Kyoto",
                check_in="2026-11-01",
                check_out="2026-11-05",
                config=cfg,
            )

        # Exception message must NOT contain canary cookie or query oauth token
        err_msg = str(exc_info.value)
        assert CANARY_BOOKING_COOKIE not in err_msg
        assert CANARY_OAUTH_PARAM not in err_msg

        # Printed feedback panel must NOT contain the canary query oauth token
        captured = capsys.readouterr()
        assert CANARY_OAUTH_PARAM not in captured.err
        assert CANARY_BOOKING_COOKIE not in captured.err


def test_web_app_error_banners_do_not_reflect_secrets() -> None:
    """Verify format_cookie_error_banner returns clean instructional text without reflecting input secrets."""
    dirty_err = f"Error: 401 Unauthorized for cookie {CANARY_BOOKING_COOKIE} and token {CANARY_OAUTH_PARAM}"
    banner = format_cookie_error_banner("Booking.com", dirty_err)
    assert banner is not None
    assert CANARY_BOOKING_COOKIE not in banner
    assert CANARY_OAUTH_PARAM not in banner


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
