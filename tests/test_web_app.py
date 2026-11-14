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

from web_app import (
    clean_ansi,
    handle_agoda_search,
    handle_booking_search,
    handle_compare_hotels,
    handle_status,
    init_sqlite_db,
    parse_thread_metadata,
    resume_chat_thread,
    run_agy_agent,
)


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
        assert "Agoda" in status
        assert "Antigravity CLI" in status
        assert "Chat Persistence" in status


def test_handle_status_configured():
    """Verify status report shows checkmarks when credentials are present."""
    mock_env = {
        "WANDERLOG_AUTH_SESSION_COOKIE": "test_cookie",
        "BOOKING_SESSION_COOKIE": "test_bkng",
        "AGODA_API_KEY": "test_agoda_key",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "OPENROUTER_API_KEY": "sk-or-test",
        "GH_TOKEN": "ghp_test",
    }
    with patch.dict(os.environ, mock_env):
        status = asyncio.run(handle_status())
        assert "✅ **Wanderlog**: Authenticated" in status
        assert "✅ **Booking.com**: Authenticated" in status
        assert "✅ **Agoda**: API key configured" in status
        assert "✅ **Anthropic Claude**: API key active" in status
        assert "✅ **DeepSeek**: API key active" in status
        assert "✅ **GitHub CLI (`gh`)**: Token configured" in status
        assert "Chat Persistence" in status


def test_handle_status_agoda_personal_account_detected():
    """Verify status report recognizes personal account with auto-detected VIP tier."""
    mock_env = {
        "AGODA_SESSION_COOKIE": "agoda.vip.tier=3; user_email=alex%40example.com",
    }
    with patch.dict(os.environ, mock_env):
        status = asyncio.run(handle_status())
        assert "Personal account connected" in status
        assert "VIP Gold auto-detected" in status


def test_sqlite_db_init(tmp_path):
    """Verify that init_sqlite_db initializes all required Chainlit tables and columns."""
    import sqlite3

    test_db = tmp_path / "test_chainlit.db"
    init_sqlite_db(test_db)
    assert test_db.exists()

    with sqlite3.connect(str(test_db)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        cursor.execute("PRAGMA table_info(steps);")
        step_cols = {row[1] for row in cursor.fetchall()}

    expected_tables = {"users", "threads", "steps", "elements", "feedbacks"}
    assert expected_tables.issubset(tables)
    assert "autoCollapse" in step_cols
    assert "icon" in step_cols
    assert "defaultOpen" in step_cols


def test_sqlite_db_migration(tmp_path):
    """Verify that init_sqlite_db migrates older steps table without autoCollapse or icon."""
    import sqlite3

    test_db = tmp_path / "legacy_chainlit.db"
    # Create older schema without autoCollapse or icon
    with sqlite3.connect(str(test_db)) as conn:
        conn.execute("""
            CREATE TABLE steps (
                "id" TEXT PRIMARY KEY,
                "name" TEXT NOT NULL,
                "type" TEXT NOT NULL,
                "threadId" TEXT NOT NULL
            );
        """)
        conn.commit()

    # Run init_sqlite_db migration
    init_sqlite_db(test_db)

    with sqlite3.connect(str(test_db)) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(steps);")
        cols = {row[1] for row in cursor.fetchall()}

    assert "autoCollapse" in cols
    assert "icon" in cols
    assert "defaultOpen" in cols


def test_parse_thread_metadata():
    """Verify safe parsing of thread metadata from various formats."""
    assert parse_thread_metadata('{"agy_conversation_id": "conv-1"}') == {"agy_conversation_id": "conv-1"}
    assert parse_thread_metadata({"agy_conversation_id": "conv-2"}) == {"agy_conversation_id": "conv-2"}
    assert parse_thread_metadata("") == {}
    assert parse_thread_metadata("invalid json") == {}
    assert parse_thread_metadata(None) == {}


def test_resume_chat_thread():
    """Verify resume_chat_thread restores user session without throwing AttributeError."""
    from unittest.mock import MagicMock

    import web_app

    session_store = {}
    mock_cl = MagicMock()
    mock_cl.user_session.set = MagicMock(side_effect=session_store.__setitem__)

    with patch.object(web_app, "cl", mock_cl):
        # Case 1: metadata is a raw string (as returned from SQLite)
        thread_raw_meta = {
            "id": "thread-1",
            "metadata": '{"agy_conversation_id": "conv-sqlite-123"}',
            "steps": [{"id": "s1", "output": "hi"}],
        }
        resume_chat_thread(thread_raw_meta)
        assert session_store.get("agy_conversation_id") == "conv-sqlite-123"
        assert len(session_store.get("history", [])) == 1

        # Case 2: metadata is a dict
        thread_dict_meta = {
            "id": "thread-2",
            "metadata": {"agy_conversation_id": "conv-dict-456"},
            "steps": [],
        }
        resume_chat_thread(thread_dict_meta)
        assert session_store.get("agy_conversation_id") == "conv-dict-456"


def test_run_agy_agent_command_construction():
    """Verify agy is invoked with -p and --output-format stream-json."""
    from unittest.mock import AsyncMock, MagicMock

    import web_app

    captured_cmds = []

    async def fake_create_subprocess_exec(*cmd, **kwargs):
        captured_cmds.append(list(cmd))
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.wait = AsyncMock(return_value=0)
        # Mock stdout lines (stream-json format)
        lines = [
            b'{"event":"init","conversation_id":"test-conv-123"}\n',
            b'{"event":"step_update","step_update":{"step_type":"agent_response","text_delta":"Hello world!"}}\n',
            b'{"event":"result","result":{"status":"SUCCESS","response":"Hello world!"}}\n',
            b"",
        ]
        mock_proc.stdout.readline = AsyncMock(side_effect=lines)
        mock_proc.stderr.readline = AsyncMock(side_effect=[b""])
        return mock_proc

    mock_msg = MagicMock()
    mock_msg.send = AsyncMock()
    mock_msg.stream_token = AsyncMock()
    mock_msg.update = AsyncMock()

    mock_step = MagicMock()
    mock_step.__aenter__ = AsyncMock(return_value=mock_step)
    mock_step.__aexit__ = AsyncMock(return_value=None)

    session_store = {}
    mock_cl = MagicMock()
    mock_cl.Message = MagicMock(return_value=mock_msg)
    mock_cl.Step = MagicMock(return_value=mock_step)
    mock_cl.user_session.get = MagicMock(side_effect=session_store.get)
    mock_cl.user_session.set = MagicMock(side_effect=session_store.__setitem__)

    with patch.object(web_app, "cl", mock_cl):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec):
            with patch("shutil.which", return_value="/usr/local/bin/agy"):
                asyncio.run(run_agy_agent("Hello"))

    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    assert cmd[0] == "agy"
    assert "--dangerously-skip-permissions" in cmd
    assert "-p" in cmd
    assert cmd[cmd.index("-p") + 1] == "Hello"
    assert "--output-format" in cmd
    assert cmd[cmd.index("--output-format") + 1] == "stream-json"
    assert session_store.get("agy_conversation_id") == "test-conv-123"
    assert mock_msg.stream_token.call_count > 0


def test_handle_agoda_search_command_construction():
    """Verify handle_agoda_search builds correct CLI arguments with search and date flags."""
    from unittest.mock import AsyncMock, MagicMock

    import web_app

    captured_cmds = []

    async def fake_subprocess_exec(*cmd, **kwargs):
        captured_cmds.append(list(cmd))
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"Mock Agoda output", b""))
        return mock_proc

    mock_step = MagicMock()
    mock_step.__aenter__ = AsyncMock(return_value=mock_step)
    mock_step.__aexit__ = AsyncMock(return_value=None)

    mock_cl = MagicMock()
    mock_cl.Step = MagicMock(return_value=mock_step)

    with patch.object(web_app, "cl", mock_cl):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess_exec):
            res = asyncio.run(handle_agoda_search("Tokyo 2026-12-01 2026-12-05"))

    assert "Mock Agoda output" in res
    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    assert "agoda.py" in cmd[2]
    assert "search" in cmd
    assert "-l" in cmd
    assert cmd[cmd.index("-l") + 1] == "Tokyo"
    assert "-i" in cmd
    assert cmd[cmd.index("-i") + 1] == "2026-12-01"
    assert "-o" in cmd
    assert cmd[cmd.index("-o") + 1] == "2026-12-05"


def test_handle_booking_search_command_construction():
    """Verify handle_booking_search builds correct CLI arguments with search and date flags."""
    from unittest.mock import AsyncMock, MagicMock

    import web_app

    captured_cmds = []

    async def fake_subprocess_exec(*cmd, **kwargs):
        captured_cmds.append(list(cmd))
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"Mock Booking output", b""))
        return mock_proc

    mock_step = MagicMock()
    mock_step.__aenter__ = AsyncMock(return_value=mock_step)
    mock_step.__aexit__ = AsyncMock(return_value=None)

    mock_cl = MagicMock()
    mock_cl.Step = MagicMock(return_value=mock_step)

    with patch.object(web_app, "cl", mock_cl):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess_exec):
            res = asyncio.run(handle_booking_search("Kyoto 2026-12-01 2026-12-05"))

    assert "Mock Booking output" in res
    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    assert "booking.py" in cmd[2]
    assert "search" in cmd
    assert "-l" in cmd
    assert cmd[cmd.index("-l") + 1] == "Kyoto"
    assert "-i" in cmd
    assert cmd[cmd.index("-i") + 1] == "2026-12-01"
    assert "-o" in cmd
    assert cmd[cmd.index("-o") + 1] == "2026-12-05"


def test_handle_compare_hotels_command_construction():
    """Verify handle_compare_hotels executes both Booking.com and Agoda and builds a comparative table."""
    import json
    from unittest.mock import AsyncMock, MagicMock

    import web_app

    captured_cmds = []

    mock_booking_json = json.dumps(
        {
            "hotels": [
                {
                    "name": "Booking Grand Hotel",
                    "total_price": 250.0,
                    "currency": "EUR",
                    "rating": 9.2,
                    "badges": ["Free cancellation"],
                    "url": "https://www.booking.com/hotel/jp/grand.html",
                }
            ]
        }
    ).encode()

    mock_agoda_json = json.dumps(
        {
            "hotels": [
                {
                    "name": "Agoda River Resort",
                    "total_price": 220.0,
                    "vip_price_text": "EUR 165.00",
                    "is_vip_deal": True,
                    "vip_discount_rate": 0.25,
                    "currency": "EUR",
                    "rating": 9.0,
                    "badges": ["Breakfast included"],
                    "url": "https://www.agoda.com/search?hotel=123",
                }
            ]
        }
    ).encode()

    async def fake_subprocess_exec(*cmd, **kwargs):
        captured_cmds.append(list(cmd))
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        if "booking.py" in cmd[2]:
            mock_proc.communicate = AsyncMock(return_value=(mock_booking_json, b""))
        else:
            mock_proc.communicate = AsyncMock(return_value=(mock_agoda_json, b""))
        return mock_proc

    mock_step = MagicMock()
    mock_step.__aenter__ = AsyncMock(return_value=mock_step)
    mock_step.__aexit__ = AsyncMock(return_value=None)

    mock_cl = MagicMock()
    mock_cl.Step = MagicMock(return_value=mock_step)

    with patch.object(web_app, "cl", mock_cl):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess_exec):
            res = asyncio.run(handle_compare_hotels("Tokyo 2026-12-01 2026-12-05"))

    assert len(captured_cmds) == 2
    # Verify both commands were executed
    executed_scripts = [cmd[2] for cmd in captured_cmds]
    assert any("booking.py" in s for s in executed_scripts)
    assert any("agoda.py" in s for s in executed_scripts)

    # Verify comparative table output
    assert "Hotel Comparison: Booking.com vs. Agoda" in res
    assert "Booking Grand Hotel" in res
    assert "Agoda River Resort" in res
    assert "Booking.com" in res
    assert "Agoda" in res
    assert "EUR 165.00" in res


if __name__ == "__main__":
    test_clean_ansi()
    test_clean_ansi_plain_text()
    test_handle_status_unconfigured()
    test_handle_status_configured()
    test_run_agy_agent_command_construction()
    test_handle_agoda_search_command_construction()
    test_handle_booking_search_command_construction()
    test_handle_compare_hotels_command_construction()
    print("All web_app tests passed successfully!")
