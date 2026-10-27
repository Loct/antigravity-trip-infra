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
    CouncilSession,
    cross_check_trip_data,
    debate_council,
    format_cross_check_markdown,
    format_debate_markdown,
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
                            {"type": "place", "place": {"name": "Temple of Literature", "formatted_address": "Dong Da"}},
                            {"type": "place", "place": {"name": "Bun Cha Huong Lien Restaurant", "formatted_address": "Hai Ba Trung"}}
                        ]
                    },
                    {
                        "date": "2026-02-02",
                        "blocks": [
                            {"type": "place", "place": {"name": "Ho Chi Minh Mausoleum", "formatted_address": "Ba Dinh"}},
                            {"type": "text", "text": {"ops": [{"insert": "Dinner at Cha Ca Thang Long restaurant"}]}}
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


def test_filter_trip_context_dining_aspect(sample_trip_payload):
    ctx = filter_trip_context(sample_trip_payload, "", aspect="dining")
    assert "Bun Cha Huong Lien Restaurant" in ctx
    assert "Dinner at Cha Ca Thang Long restaurant" in ctx
    assert "Temple of Literature" not in ctx


def test_council_session_memory(tmp_path):
    session = CouncilSession(session_id="test_session", trip_target="sample_trip")
    session.add_turn(
        query="Is Day 1 feasible?",
        claude_response="Claude: Temple of Literature is wonderful in morning.",
        deepseek_response="DeepSeek: 15 min drive from hotel, good buffer.",
    )

    claude_msgs = session.get_messages_for_claude("Follow up on lunch")
    assert len(claude_msgs) == 3
    assert claude_msgs[0]["role"] == "user"
    assert claude_msgs[1]["role"] == "assistant"
    assert "Co-Council Logistics Advisor DeepSeek noted" in claude_msgs[1]["content"]
    assert claude_msgs[2]["content"] == "Follow up on lunch"

    saved_file = session.save(storage_dir=tmp_path)
    assert saved_file.exists()

    loaded = CouncilSession.load("test_session", storage_dir=tmp_path)
    assert loaded is not None
    assert loaded.session_id == "test_session"
    assert len(loaded.turns) == 1


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

    ans, reasoning = ask_claude("Is Day 3 paced well?", "Context here", claude_cfg=mock_cfg)
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

    ans, reasoning = ask_deepseek("Check traffic", "Context here", ds_cfg=mock_cfg)
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


@patch("ai_council.ask_claude")
@patch("ai_council.ask_deepseek")
def test_cross_check_trip_data_mocked(mock_ds, mock_claude, sample_trip_payload):
    # Round 1
    mock_claude.side_effect = [
        ("Claude Round 1: Cultural pacing is solid.", None),
        ("Claude Round 2: DeepSeek transit numbers look accurate.", None),
    ]
    mock_ds.side_effect = [
        ("DeepSeek Round 1: Transit times between places are 20m.", None),
        ("DeepSeek Round 2: Claude proposal does not cause backtracking.", None),
    ]

    res = cross_check_trip_data(
        trip_data=sample_trip_payload,
        trip_md="",
        aspect="transit",
        target_days=[1],
        stream_progress=False,
    )

    assert res["mode"] == "cross_check"
    assert "Cultural pacing is solid" in res["round_1"]["claude"]
    assert "Transit times between places" in res["round_1"]["deepseek"]
    assert "Claude proposal does not cause backtracking" in res["round_2_cross_examination"]["deepseek_critique_of_claude"]

    md = format_cross_check_markdown(res)
    assert "Dual AI Travel Data Cross-Check" in md
    assert "Round 2: Conversational Peer Review" in md


@patch("ai_council.ask_claude")
@patch("ai_council.ask_deepseek")
def test_debate_council_mocked(mock_ds, mock_claude):
    mock_claude.side_effect = [
        ("Claude: The overnight sleeper train offers iconic scenery.", None),
        ("Claude: DeepSeek makes a fair flight buffer point, but train is more memorable.", None),
    ]
    mock_ds.side_effect = [
        ("DeepSeek: The 1h20m flight saves 12 hours of travel fatigue.", None),
        ("DeepSeek: While sleeper is romantic, flight guarantees better sleep.", None),
    ]

    res = debate_council(
        topic="Sleeper train vs Flight to Da Nang",
        trip_context="Sample Context",
        stream_progress=False,
    )

    assert res["mode"] == "debate"
    assert "overnight sleeper train" in res["round_1"]["claude"]
    assert "1h20m flight saves" in res["round_1"]["deepseek"]
    assert "flight guarantees better sleep" in res["round_2"]["deepseek_rebuttal"]

    md = format_debate_markdown(res)
    assert "AI Travel Council Debate" in md
    assert "Cross-Talk & Rebuttals" in md
