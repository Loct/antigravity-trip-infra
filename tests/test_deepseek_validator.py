#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pytest>=8.0.0",
#     "httpx>=0.27.0",
#     "rich>=13.0.0",
#     "openai>=1.0.0",
# ]
# ///
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts dir is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from deepseek_validator import (
    ProviderConfig,
    extract_trip_id,
    summarize_trip_context,
    run_validation,
    verify_connection,
)


def test_extract_trip_id():
    assert extract_trip_id("abc123xyz") == "abc123xyz"
    assert extract_trip_id("https://wanderlog.com/view/abc123xyz/trip-to-rome") == "abc123xyz"
    assert extract_trip_id("https://wanderlog.com/plan/def456ghi/tokyo-vacation") == "def456ghi"
    assert extract_trip_id("  test-id-999  ") == "test-id-999"


def test_provider_config_openrouter_defaults():
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test", "DEEPSEEK_PROVIDER": ""}, clear=True):
        cfg = ProviderConfig()
        assert cfg.provider == "openrouter"
        assert cfg.base_url == "https://openrouter.ai/api/v1"
        assert cfg.model == "deepseek/deepseek-chat"
        assert cfg.api_key == "sk-or-test"
        assert "HTTP-Referer" in cfg.default_headers


def test_provider_config_groq():
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test", "DEEPSEEK_PROVIDER": ""}, clear=True):
        cfg = ProviderConfig()
        assert cfg.provider == "groq"
        assert cfg.base_url == "https://api.groq.com/openai/v1"
        assert cfg.model == "deepseek-r1-distill-llama-70b"


def test_provider_config_deepseek_direct():
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk_test", "DEEPSEEK_PROVIDER": ""}, clear=True):
        cfg = ProviderConfig()
        assert cfg.provider == "deepseek"
        assert cfg.base_url == "https://api.deepseek.com"
        assert cfg.model == "deepseek-reasoner"


def test_provider_config_missing_key():
    with patch.dict(os.environ, {}, clear=True):
        cfg = ProviderConfig(provider="openrouter", api_key="")
        with pytest.raises(ValueError, match="Missing API key"):
            cfg.get_client()


def test_summarize_trip_context():
    sample_data = {
        "tripPlan": {
            "title": "Tokyo Cherry Blossom",
            "startDate": "2026-03-25",
            "endDate": "2026-04-02",
            "placeCount": 15,
        }
    }
    sample_md = "## Day 1\n- Senso-ji Temple at 10:00"
    summary = summarize_trip_context(sample_data, sample_md)

    assert "Tokyo Cherry Blossom" in summary
    assert "2026-03-25" in summary
    assert "Senso-ji Temple" in summary


@patch("deepseek_validator.OpenAI")
def test_run_validation_mocked(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    # Mock non-streaming completion
    mock_choice = MagicMock()
    mock_choice.message.content = "# 📋 Trip Audit Report: Tokyo\n## ✅ Final Verdict\nEXCELLENT"
    mock_choice.message.reasoning = "Looking at the itinerary, Senso-ji is close to Asakusa."
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_resp

    cfg = ProviderConfig(provider="openrouter", api_key="sk-or-test")
    report, reasoning = run_validation("Test Trip Summary", cfg, stream=False)

    assert "Trip Audit Report" in report
    assert "EXCELLENT" in report
    assert reasoning == "Looking at the itinerary, Senso-ji is close to Asakusa."


@patch("deepseek_validator.OpenAI")
def test_verify_connection_mocked(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    mock_choice = MagicMock()
    mock_choice.message.content = "VALIDATOR_READY"
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_resp

    cfg = ProviderConfig(provider="openrouter", api_key="sk-or-test")
    assert verify_connection(cfg) is True
