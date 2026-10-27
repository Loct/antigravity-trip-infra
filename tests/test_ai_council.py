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

from ai_council import (
    filter_trip_context,
    ask_claude,
    ask_deepseek,
    ask_council,
    format_council_markdown,
)
import claude_validator
import deepseek_validator


@pytest.fixture
def sample_trip_payload():
    return {
        "tripPlan": {
            "title": "Vietnam Highlights",
            "startDate": "2026-02-01",
            "endDate": "2026-02-10",
            "days": 10,
            "placeCount": 20,
            "itinerary": {
                "sections": [
                    {
                        "type": "hotels",
                        "blocks": [
                            {"place": {"name": "Hanoi Central Hotel", "formatted_address": "Hoan Kiem, Hanoi"}}
                        ]
                    },
                    {
                        "type": "flights",
                        "blocks": [
                            {
                                "flightInfo": {"airline": {"iata": "VN"}, "number": "123"},
                                "depart": {"airport": {"name": "HAN"}, "date": "2026-02-05", "time": "10:00"},
                                "arrive": {"airport": {"name": "DAD"}, "date": "2026-02-05", "time": "11:20"},
                            }
                        ]
                    },
                    {
                        "date": "2026-02-01",
                        "blocks": [
                            {"type": "place", "place": {"name": "Temple of Literature", "formatted_address": "Dong Da"}}
                        ]
                    },
                    {
                        "date": "2026-02-02",
                        "blocks": [
                            {"type": "place", "place": {"name": "Ho Chi Minh Mausoleum", "formatted_address": "Ba Dinh"}}
                        ]
                    }
                ]
            }
        }
    }


def test_filter_trip_context_full(sample_trip_payload):
    ctx = filter_trip_context(sample_trip_payload, "")
    assert "Vietnam Highlights" in ctx
    assert "Hanoi Central Hotel" in ctx
    assert "Flight VN 123" in ctx
    assert "Temple of Literature" in ctx
    assert "Ho Chi Minh Mausoleum" in ctx


def test_filter_trip_context_day_focus(sample_trip_payload):
    # Only Day 2
    ctx = filter_trip_context(sample_trip_payload, "", target_days=[2])
    assert "Hanoi Central Hotel" in ctx  # lodging preserved
    assert "Flight VN 123" in ctx        # flights preserved
    assert "Day 2" in ctx
    assert "Ho Chi Minh Mausoleum" in ctx
    assert "Temple of Literature" not in ctx  # Day 1 excluded


@patch("ai_council.claude_validator.ClaudeProviderConfig")
def test_ask_claude_mocked(mock_cfg_cls):
    mock_cfg = MagicMock()
    mock_cfg.provider = "anthropic"
    mock_cfg.model = "claude-3-7-sonnet-20250219"
    mock_cfg.is_thinking_supported.return_value = False
    
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = [SimpleNamespace(type="text", text="Day 3 looks well-paced with good buffer.")]
    mock_client.messages.create.return_value = mock_resp
    mock_cfg.get_anthropic_client.return_value = mock_client

    ans, reasoning = ask_claude("Is Day 3 paced well?", "Context here", mock_cfg)
    assert "Day 3 looks well-paced" in ans


@patch("ai_council.deepseek_validator.ProviderConfig")
def test_ask_deepseek_mocked(mock_cfg_cls):
    mock_cfg = MagicMock()
    mock_cfg.provider = "deepseek"
    mock_cfg.model = "deepseek-chat"
    
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Watch out for heavy traffic on the bridge during rush hour."
    mock_choice.message.reasoning = None
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_resp
    mock_cfg.get_client.return_value = mock_client

    ans, reasoning = ask_deepseek("Check traffic", "Context here", mock_cfg)
    assert "traffic on the bridge" in ans


@patch("ai_council.ask_claude")
@patch("ai_council.ask_deepseek")
def test_ask_council_mocked(mock_ds, mock_claude):
    mock_claude.return_value = ("Claude recommends swapping stops.", "thinking")
    mock_ds.return_value = ("DeepSeek confirms 45 min saved.", "reasoning")

    results = ask_council(
        query="Should we swap stops?",
        trip_context="Context",
        stream_progress=False,
    )

    assert results["query"] == "Should we swap stops?"
    assert results["claude"]["response"] == "Claude recommends swapping stops."
    assert results["deepseek"]["response"] == "DeepSeek confirms 45 min saved."

    md = format_council_markdown(results)
    assert "Anthropic Claude" in md
    assert "DeepSeek" in md
    assert "Claude recommends swapping" in md
