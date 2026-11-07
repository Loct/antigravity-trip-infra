#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pytest>=8.0.0",
# ]
# ///
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

try:
    import pytest
except ImportError:
    pytest = None

# Ensure scripts dir is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from web_app import clean_ansi, handle_status


def test_clean_ansi():
    """Verify that ANSI escape codes are properly stripped."""
    raw_ansi = "\x1b[31mError:\x1b[0m \x1b[1mSomething went wrong\x1b[0m\n"
    cleaned = clean_ansi(raw_ansi)
    assert cleaned == "Error: Something went wrong\n"
    assert "\x1b" not in cleaned


def test_clean_ansi_plain_text():
    """Verify clean_ansi leaves plain text unchanged."""
    text = "Hello, Tokyo! Planning 3 days."
    assert clean_ansi(text) == text


def test_handle_status_unconfigured():
    """Verify status report when credentials are not configured."""
    with patch.dict(os.environ, {}, clear=True):
        status = asyncio.run(handle_status())
        assert "System & Authentication Status" in status
        assert "Wanderlog" in status
        assert "Booking.com" in status
        assert "Antigravity CLI" in status


def test_handle_status_configured():
    """Verify status report shows checkmarks when credentials are present."""
    mock_env = {
        "WANDERLOG_AUTH_SESSION_COOKIE": "test_cookie",
        "BOOKING_SESSION_COOKIE": "test_bkng",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "OPENROUTER_API_KEY": "sk-or-test",
        "GH_TOKEN": "ghp_test",
    }
    with patch.dict(os.environ, mock_env):
        status = asyncio.run(handle_status())
        assert "✅ **Wanderlog**: Authenticated" in status
        assert "✅ **Booking.com**: Authenticated" in status
        assert "✅ **Anthropic Claude**: API key active" in status
        assert "✅ **DeepSeek**: API key active" in status
        assert "✅ **GitHub CLI (`gh`)**: Token configured" in status


if __name__ == "__main__":
    test_clean_ansi()
    test_clean_ansi_plain_text()
    test_handle_status_unconfigured()
    test_handle_status_configured()
    print("All web_app tests passed successfully!")
