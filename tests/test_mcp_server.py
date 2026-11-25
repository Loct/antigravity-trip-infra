import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure scripts dir is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import agoda
import booking
import mcp_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_mcp_tools_registered():
    tools = await mcp_server.mcp.list_tools()
    tool_names = {t.name for t in tools}
    expected = {
        "booking_search_hotels",
        "agoda_search_hotels",
        "search_hotels_dual_ota",
        "check_ota_auth_status",
        "ai_council_ask",
        "ai_council_crosscheck",
        "ai_council_debate",
        "ai_council_list_sessions",
        "validate_trip_claude",
        "validate_trip_deepseek",
        "validate_trip_crosscheck",
        "check_ai_providers_status",
        "self_update_check",
    }
    assert expected.issubset(tool_names)


@pytest.mark.anyio
async def test_booking_search_hotels():
    hotel = booking.Hotel(name="Park Hyatt Tokyo", hotel_id="123", price_per_night=450.0)
    with patch("mcp_server.booking.search_hotels", return_value=([hotel], "Cookie Session (Booking.com)")) as mock_fn:
        res = await mcp_server.booking_search_hotels(
            location="Tokyo",
            check_in="2026-12-01",
            check_out="2026-12-05",
            guests=2,
            rooms=1,
            currency="EUR",
            limit=5,
            genius_level=3,
        )

    mock_fn.assert_called_once_with(
        location="Tokyo",
        check_in="2026-12-01",
        check_out="2026-12-05",
        guests=2,
        rooms=1,
        currency="EUR",
        limit=5,
        genius_level=3,
    )
    assert res["provider"] == "Cookie Session (Booking.com)"
    assert res["count"] == 1
    assert res["hotels"][0]["name"] == "Park Hyatt Tokyo"


@pytest.mark.anyio
async def test_agoda_search_hotels():
    hotel = agoda.Hotel(name="Shinjuku Granbell", hotel_id="456", price_per_night=180.0)
    with patch("mcp_server.agoda.search_hotels", return_value=([hotel], "Apify (clearpath)")) as mock_fn:
        res = await mcp_server.agoda_search_hotels(
            location="Tokyo",
            check_in="2026-12-01",
            check_out="2026-12-05",
        )

    mock_fn.assert_called_once()
    assert res["provider"] == "Apify (clearpath)"
    assert res["count"] == 1
    assert res["hotels"][0]["name"] == "Shinjuku Granbell"


@pytest.mark.anyio
async def test_search_hotels_dual_ota_partial_failure():
    b_hotel = booking.Hotel(name="Hotel A", hotel_id="1")
    with (
        patch("mcp_server.booking.search_hotels", return_value=([b_hotel], "Cookie Session (Booking.com)")),
        patch("mcp_server.agoda.search_hotels", side_effect=RuntimeError("Agoda timeout")),
    ):
        res = await mcp_server.search_hotels_dual_ota(
            location="Paris",
            check_in="2026-12-10",
            check_out="2026-12-12",
        )

    assert res["booking"]["count"] == 1
    assert res["booking"]["hotels"][0]["name"] == "Hotel A"
    assert res["agoda"]["count"] == 0
    assert "Agoda timeout" in res["agoda"]["error"]


@pytest.mark.anyio
async def test_check_ota_auth_status_live():
    b_cfg = SimpleNamespace(session_cookie="cookie_b", genius_level=3)
    a_cfg = SimpleNamespace(session_cookie="", api_key="key_a", apify_token="", vip_level=4)

    with (
        patch("mcp_server.booking.BookingConfig", return_value=b_cfg),
        patch("mcp_server.booking.verify_booking_session", return_value=(True, "valid", "OK")),
        patch("mcp_server.agoda.AgodaConfig", return_value=a_cfg),
        patch("mcp_server.agoda.verify_agoda_session", return_value=(False, "unavailable", "Missing", {})),
    ):
        res = await mcp_server.check_ota_auth_status(provider="all", live_verify=True)

    assert res["booking"]["is_valid"] is True
    assert res["booking"]["genius_level"] == 3
    assert res["agoda"]["rapidapi_configured"] is True
    assert res["agoda"]["is_valid"] is False


@pytest.mark.anyio
async def test_ai_council_tools():
    fake_session = MagicMock()
    expected_ask = {"query": "Best ramen?", "claude": {"response": "A"}, "deepseek": {"response": "B"}}
    expected_cc = {"mode": "cross_check", "aspect": "transit"}
    expected_deb = {"mode": "debate", "topic": "JR Pass"}

    with (
        patch("mcp_server.claude_validator.fetch_trip_data", return_value=({"title": "Japan"}, "# Japan")),
        patch("mcp_server.ai_council.filter_trip_context", return_value="filtered"),
        patch("mcp_server.ai_council.CouncilSession.load", return_value=fake_session),
        patch("mcp_server.ai_council.ask_council", return_value=expected_ask) as mock_ask,
        patch("mcp_server.ai_council.cross_check_trip_data", return_value=expected_cc) as mock_cc,
        patch("mcp_server.ai_council.debate_council", return_value=expected_deb) as mock_deb,
        patch("mcp_server.ai_council.CouncilSession.list_saved_sessions", return_value=[{"session_id": "s1"}]),
    ):
        ask_res = await mcp_server.ai_council_ask(query="Best ramen?", trip="trip123", session_id="s1")
        cc_res = await mcp_server.ai_council_crosscheck(trip="trip123", aspect="transit", target_days=[1, 2])
        deb_res = await mcp_server.ai_council_debate(topic="JR Pass", trip="trip123")
        sess_res = await mcp_server.ai_council_list_sessions()

    assert ask_res == expected_ask
    assert mock_ask.call_args.kwargs["stream_progress"] is False
    assert cc_res == expected_cc
    assert mock_cc.call_args.kwargs["stream_progress"] is False
    assert deb_res == expected_deb
    assert mock_deb.call_args.kwargs["stream_progress"] is False
    assert sess_res == [{"session_id": "s1"}]


@pytest.mark.anyio
async def test_validator_tools_and_provider_status():
    c_cfg = SimpleNamespace(provider="anthropic", model="claude-sonnet", api_key="sk-ant")
    d_cfg = SimpleNamespace(provider="openrouter", model="deepseek-r1", api_key="sk-or")

    with (
        patch("mcp_server.claude_validator.fetch_trip_data", return_value=({}, "# Trip")),
        patch("mcp_server.claude_validator.summarize_trip_context", return_value="summary"),
        patch("mcp_server.claude_validator.ClaudeProviderConfig", return_value=c_cfg),
        patch("mcp_server.claude_validator.run_claude_validation", return_value=("Claude report", None)),
        patch("mcp_server.deepseek_validator.fetch_trip_data", return_value=({}, "# Trip")),
        patch("mcp_server.deepseek_validator.summarize_trip_context", return_value="summary"),
        patch("mcp_server.deepseek_validator.ProviderConfig", return_value=d_cfg),
        patch("mcp_server.deepseek_validator.run_validation", return_value=("DS report", "think")),
        patch("mcp_server.cross_check_validator.run_cross_check", return_value=("CC md", "C rep", "D rep")),
        patch("mcp_server.claude_validator.verify_connection", return_value=True),
        patch("mcp_server.deepseek_validator.verify_connection", return_value=True),
    ):
        c_res = await mcp_server.validate_trip_claude("trip1")
        d_res = await mcp_server.validate_trip_deepseek("trip1")
        cc_res = await mcp_server.validate_trip_crosscheck("trip1")
        status_res = await mcp_server.check_ai_providers_status(live_verify=True)

    assert c_res["report"] == "Claude report"
    assert d_res["report"] == "DS report"
    assert cc_res["cross_check_report"] == "CC md"
    assert status_res["claude"]["connected"] is True
    assert status_res["deepseek"]["connected"] is True


@pytest.mark.anyio
async def test_self_update_check():
    fake_proc = AsyncMock()
    fake_proc.returncode = 0
    fake_proc.communicate = AsyncMock(return_value=(b"Up to date", b""))

    with patch("mcp_server.asyncio.create_subprocess_exec", return_value=fake_proc) as mock_exec:
        res = await mcp_server.self_update_check()

    mock_exec.assert_called_once()
    assert res["exit_code"] == 0
    assert res["output"] == "Up to date"
