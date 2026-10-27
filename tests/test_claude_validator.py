#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pytest>=8.0.0",
#     "httpx>=0.27.0",
#     "rich>=13.0.0",
#     "anthropic>=0.40.0",
#     "openai>=1.0.0",
# ]
# ///
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts dir is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from claude_validator import (
    ClaudeProviderConfig,
    extract_trip_id,
    summarize_trip_context,
    run_claude_validation,
    verify_connection,
)


def test_extract_trip_id():
    assert extract_trip_id("abc123xyz") == "abc123xyz"
    assert extract_trip_id("https://wanderlog.com/view/abc123xyz/trip-to-rome") == "abc123xyz"
    assert extract_trip_id("https://wanderlog.com/plan/def456ghi/tokyo-vacation") == "def456ghi"
    assert extract_trip_id("  test-id-999  ") == "test-id-999"


def test_claude_provider_config_defaults():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-testkey"}, clear=True):
        cfg = ClaudeProviderConfig()
        assert cfg.provider == "anthropic"
        assert cfg.base_url == "https://api.anthropic.com"
        assert cfg.model == "claude-3-7-sonnet-20250219"
        assert cfg.thinking_budget == 2048
        assert cfg.is_thinking_supported() is True


def test_claude_provider_config_haiku():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-testkey", "ANTHROPIC_MODEL": "claude-3-5-haiku-20241022"}, clear=True):
        cfg = ClaudeProviderConfig()
        assert cfg.model == "claude-3-5-haiku-20241022"
        assert cfg.is_thinking_supported() is False


def test_claude_provider_config_openrouter():
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-testkey", "CLAUDE_PROVIDER": "openrouter"}, clear=True):
        cfg = ClaudeProviderConfig()
        assert cfg.provider == "openrouter"
        assert cfg.base_url == "https://openrouter.ai/api/v1"
        assert "claude" in cfg.model.lower()


def test_claude_provider_config_missing_key():
    with patch.dict(os.environ, {}, clear=True):
        cfg = ClaudeProviderConfig(api_key="")
        with pytest.raises(ValueError, match="Missing Anthropic API key"):
            cfg.get_anthropic_client()


def test_summarize_trip_context():
    sample_data = {
        "tripPlan": {
            "title": "Kyoto Autumn Leaves",
            "startDate": "2026-11-10",
            "endDate": "2026-11-15",
            "placeCount": 12,
            "itinerary": {
                "sections": [
                    {
                        "type": "hotels",
                        "blocks": [
                            {"place": {"name": "Kyoto Ryokan", "formatted_address": "Gion, Kyoto"}}
                        ]
                    },
                    {
                        "date": "2026-11-10",
                        "blocks": [
                            {"type": "place", "place": {"name": "Kiyomizu-dera", "formatted_address": "Higashiyama"}}
                        ]
                    }
                ]
            }
        }
    }
    summary = summarize_trip_context(sample_data, "")
    assert "Kyoto Autumn Leaves" in summary
    assert "Kyoto Ryokan" in summary
    assert "Kiyomizu-dera" in summary


def test_run_claude_validation_mocked_non_streaming():
    cfg = ClaudeProviderConfig(api_key="sk-ant-test")
    
    mock_client = MagicMock()
    mock_resp = MagicMock()
    
    thinking_block = SimpleNamespace(type="thinking", thinking="Let's review the hotel continuity and timing.")
    text_block = SimpleNamespace(type="text", text="# 📋 Trip Audit Report: Kyoto\n## ✅ Final Verdict\nEXCELLENT")
    mock_resp.content = [thinking_block, text_block]
    
    mock_client.messages.create.return_value = mock_resp

    with patch.object(cfg, "get_anthropic_client", return_value=mock_client):
        content, reasoning = run_claude_validation("Trip summary context", cfg, stream=False)
        assert "Trip Audit Report" in content
        assert "EXCELLENT" in content
        assert reasoning is not None
        assert "hotel continuity" in reasoning


def test_verify_connection_mocked():
    cfg = ClaudeProviderConfig(api_key="sk-ant-test")
    mock_client = MagicMock()
    mock_resp = MagicMock()
    text_block = SimpleNamespace(type="text", text="VALIDATOR_READY")
    mock_resp.content = [text_block]
    mock_client.messages.create.return_value = mock_resp

    with patch.object(cfg, "get_anthropic_client", return_value=mock_client):
        assert verify_connection(cfg) is True
