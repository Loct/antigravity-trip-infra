#!/usr/bin/env python3
"""
MCP Server exposing Antigravity workspace tools (Booking.com, Agoda, AI Travel Council).

Allows AI agents such as Antigravity (agy) and Claude to invoke workspace tools
natively over the Model Context Protocol (MCP) with strict JSON schemas,
persistent in-memory imports, and parallel dual-OTA execution.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from mcp.server.fastmcp import FastMCP

# Ensure scripts directory is importable regardless of working directory
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import agoda  # noqa: E402
import ai_council  # noqa: E402
import booking  # noqa: E402
import claude_validator  # noqa: E402
import cross_check_validator  # noqa: E402
import deepseek_validator  # noqa: E402

mcp = FastMCP("antigravity-tools")

AspectType = Literal["all", "transit", "dining", "hours", "hotels"]
AgodaProviderType = Literal["auto", "rapidapi", "apify", "scrape"]
AuthProviderType = Literal["all", "booking", "agoda"]


def _resolve_trip_context(
    trip: Optional[str],
    target_days: Optional[List[int]] = None,
    aspect: str = "all",
) -> Tuple[Dict[str, Any], str, str]:
    """Load trip JSON/markdown and filter context if a trip ID or file path is provided."""
    if not trip:
        return {}, "", ""
    trip_data, trip_md = claude_validator.fetch_trip_data(trip)
    trip_context = ai_council.filter_trip_context(
        trip_data,
        trip_md,
        target_days=target_days,
        aspect=aspect,
    )
    return trip_data, trip_md, trip_context


def _resolve_session(
    session_id: Optional[str],
    trip: Optional[str] = None,
    trip_context: str = "",
) -> Optional[ai_council.CouncilSession]:
    """Load an existing CouncilSession or create a new one when session_id is given."""
    if not session_id:
        return None
    session = ai_council.CouncilSession.load(session_id) or ai_council.CouncilSession(
        session_id=session_id,
        trip_target=trip,
    )
    if trip_context:
        session.trip_context = trip_context
    return session


async def _run_booking_search(
    location: str,
    check_in: str,
    check_out: str,
    guests: int,
    rooms: int,
    currency: str,
    limit: int,
    genius_level: int,
) -> Dict[str, Any]:
    hotels, provider_used = await asyncio.to_thread(
        booking.search_hotels,
        location=location,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        rooms=rooms,
        currency=currency,
        limit=limit,
        genius_level=genius_level,
    )
    return {
        "provider": provider_used,
        "location": location,
        "check_in": check_in,
        "check_out": check_out,
        "currency": currency,
        "count": len(hotels),
        "hotels": [h.to_dict() for h in hotels],
    }


async def _run_agoda_search(
    location: str,
    check_in: str,
    check_out: str,
    guests: int,
    rooms: int,
    currency: str,
    limit: int,
    provider: str,
    vip_level: int,
    personal_account: bool,
) -> Dict[str, Any]:
    hotels, provider_used = await asyncio.to_thread(
        agoda.search_hotels,
        location=location,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        rooms=rooms,
        currency=currency,
        limit=limit,
        provider=provider,
        vip_level=vip_level,
        personal_account=personal_account,
    )
    return {
        "provider": provider_used,
        "location": location,
        "check_in": check_in,
        "check_out": check_out,
        "currency": currency,
        "count": len(hotels),
        "hotels": [h.to_dict() for h in hotels],
    }


async def _safe_ota_call(coro_fn: Callable[[], Any]) -> Dict[str, Any]:
    """Execute an OTA search coroutine, returning a structured error dict on failure."""
    try:
        return await coro_fn()
    except Exception as exc:
        return {"error": str(exc), "count": 0, "hotels": []}


@mcp.tool()
async def booking_search_hotels(
    location: str,
    check_in: str,
    check_out: str,
    guests: int = 2,
    rooms: int = 1,
    currency: str = "EUR",
    limit: int = 10,
    genius_level: int = 3,
) -> Dict[str, Any]:
    """
    Search hotels on Booking.com using the workspace's authenticated session & Genius discounts.

    Args:
        location: Destination city or area (e.g. "Tokyo", "Paris").
        check_in: Check-in date in YYYY-MM-DD format.
        check_out: Check-out date in YYYY-MM-DD format.
        guests: Number of adult guests (default 2).
        rooms: Number of rooms (default 1).
        currency: 3-letter currency code (default "EUR").
        limit: Maximum number of properties to return (default 10).
        genius_level: Booking.com Genius loyalty level 0-3 (default 3).
    """
    return await _run_booking_search(
        location=location,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        rooms=rooms,
        currency=currency,
        limit=limit,
        genius_level=genius_level,
    )


@mcp.tool()
async def agoda_search_hotels(
    location: str,
    check_in: str,
    check_out: str,
    guests: int = 2,
    rooms: int = 1,
    currency: str = "EUR",
    limit: int = 10,
    provider: AgodaProviderType = "auto",
    vip_level: int = 4,
    personal_account: bool = False,
) -> Dict[str, Any]:
    """
    Search hotels on Agoda with hybrid provider fallback and AgodaVIP loyalty discounts.

    Args:
        location: Destination city or area (e.g. "Tokyo", "Bangkok").
        check_in: Check-in date in YYYY-MM-DD format.
        check_out: Check-out date in YYYY-MM-DD format.
        guests: Number of adult guests (default 2).
        rooms: Number of rooms (default 1).
        currency: 3-letter currency code (default "EUR").
        limit: Maximum number of properties to return (default 10).
        provider: Backend provider: "auto", "rapidapi", "apify", or "scrape".
        vip_level: AgodaVIP tier 0-4 (default 4).
        personal_account: Auto-detect VIP tier from personal Agoda session cookie.
    """
    return await _run_agoda_search(
        location=location,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        rooms=rooms,
        currency=currency,
        limit=limit,
        provider=provider,
        vip_level=vip_level,
        personal_account=personal_account,
    )


@mcp.tool()
async def search_hotels_dual_ota(
    location: str,
    check_in: str,
    check_out: str,
    guests: int = 2,
    rooms: int = 1,
    currency: str = "EUR",
    limit: int = 10,
    booking_genius_level: int = 3,
    agoda_vip_level: int = 4,
) -> Dict[str, Any]:
    """
    Search BOTH Booking.com and Agoda in parallel for side-by-side price & perk comparison.

    If one provider fails, the other provider's results are still returned alongside the error.

    Args:
        location: Destination city or area (e.g. "Tokyo", "Paris").
        check_in: Check-in date in YYYY-MM-DD format.
        check_out: Check-out date in YYYY-MM-DD format.
        guests: Number of adult guests (default 2).
        rooms: Number of rooms (default 1).
        currency: 3-letter currency code (default "EUR").
        limit: Maximum number of properties per provider (default 10).
        booking_genius_level: Booking.com Genius loyalty level 0-3 (default 3).
        agoda_vip_level: AgodaVIP tier 0-4 (default 4).
    """
    booking_res, agoda_res = await asyncio.gather(
        _safe_ota_call(
            lambda: _run_booking_search(
                location=location,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                rooms=rooms,
                currency=currency,
                limit=limit,
                genius_level=booking_genius_level,
            )
        ),
        _safe_ota_call(
            lambda: _run_agoda_search(
                location=location,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                rooms=rooms,
                currency=currency,
                limit=limit,
                provider="auto",
                vip_level=agoda_vip_level,
                personal_account=False,
            )
        ),
    )
    return {
        "location": location,
        "check_in": check_in,
        "check_out": check_out,
        "currency": currency,
        "booking": booking_res,
        "agoda": agoda_res,
    }


@mcp.tool()
async def check_ota_auth_status(
    provider: AuthProviderType = "all",
    live_verify: bool = True,
) -> Dict[str, Any]:
    """
    Check authentication and session cookie status for Booking.com and/or Agoda.

    Args:
        provider: Which provider to check: "all", "booking", or "agoda".
        live_verify: Perform a live HTTP check on configured session cookies (default True).
    """
    status: Dict[str, Any] = {}

    if provider in ("all", "booking"):
        b_cfg = booking.BookingConfig()
        b_entry: Dict[str, Any] = {
            "cookie_configured": bool(b_cfg.session_cookie),
            "genius_level": b_cfg.genius_level,
        }
        if live_verify:
            is_valid, status_type, details = await asyncio.to_thread(
                booking.verify_booking_session,
                b_cfg.session_cookie,
            )
            b_entry.update(
                {
                    "is_valid": is_valid,
                    "status_type": status_type,
                    "details": details,
                }
            )
        status["booking"] = b_entry

    if provider in ("all", "agoda"):
        a_cfg = agoda.AgodaConfig()
        a_entry: Dict[str, Any] = {
            "cookie_configured": bool(a_cfg.session_cookie),
            "rapidapi_configured": bool(a_cfg.api_key),
            "apify_configured": bool(a_cfg.apify_token),
            "vip_level": a_cfg.vip_level,
        }
        if live_verify:
            is_valid, status_type, details, member_info = await asyncio.to_thread(
                agoda.verify_agoda_session,
                a_cfg.session_cookie,
            )
            a_entry.update(
                {
                    "is_valid": is_valid,
                    "status_type": status_type,
                    "details": details,
                    "member_info": member_info,
                }
            )
        status["agoda"] = a_entry

    return status


@mcp.tool()
async def ai_council_ask(
    query: str,
    trip: Optional[str] = None,
    session_id: Optional[str] = None,
    target_days: Optional[List[int]] = None,
    aspect: AspectType = "all",
) -> Dict[str, Any]:
    """
    Ask the AI Travel Council (Anthropic Claude + DeepSeek) a question, optionally grounded in a trip.

    Args:
        query: Question or prompt for Claude and DeepSeek.
        trip: Optional Wanderlog trip ID or path to a local trip JSON/markdown file.
        session_id: Optional persistent council session ID to preserve multi-turn history.
        target_days: Optional list of 1-based day numbers to focus context on (e.g. [1, 2]).
        aspect: Context filter aspect: "all", "transit", "dining", "hours", or "hotels".
    """
    _, _, trip_context = await asyncio.to_thread(_resolve_trip_context, trip, target_days, aspect)
    session = await asyncio.to_thread(_resolve_session, session_id, trip, trip_context)
    return await asyncio.to_thread(
        ai_council.ask_council,
        query=query,
        trip_context=trip_context,
        session=session,
        stream_progress=False,
    )


@mcp.tool()
async def ai_council_crosscheck(
    trip: str,
    aspect: AspectType = "all",
    target_days: Optional[List[int]] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run a 2-round peer-review cross-check of a trip itinerary between Claude and DeepSeek.

    Round 1: Independent inspection. Round 2: Cross-examination of each other's findings.

    Args:
        trip: Wanderlog trip ID or path to a local trip JSON/markdown file.
        aspect: Focus area: "all", "transit", "dining", "hours", or "hotels".
        target_days: Optional list of 1-based day numbers to inspect (e.g. [3, 4]).
        session_id: Optional persistent council session ID.
    """
    trip_data, trip_md, trip_context = await asyncio.to_thread(_resolve_trip_context, trip, target_days, aspect)
    session = await asyncio.to_thread(_resolve_session, session_id, trip, trip_context)
    return await asyncio.to_thread(
        ai_council.cross_check_trip_data,
        trip_data=trip_data,
        trip_md=trip_md,
        aspect=aspect,
        target_days=target_days,
        session=session,
        stream_progress=False,
    )


@mcp.tool()
async def ai_council_debate(
    topic: str,
    trip: Optional[str] = None,
    session_id: Optional[str] = None,
    target_days: Optional[List[int]] = None,
    aspect: AspectType = "all",
) -> Dict[str, Any]:
    """
    Run a 2-round structured debate between Claude (culture/experience) and DeepSeek (transit/logistics).

    Args:
        topic: Travel dilemma or decision to debate.
        trip: Optional Wanderlog trip ID or path to a local trip JSON/markdown file.
        session_id: Optional persistent council session ID.
        target_days: Optional list of 1-based day numbers to focus context on.
        aspect: Context filter aspect: "all", "transit", "dining", "hours", or "hotels".
    """
    _, _, trip_context = await asyncio.to_thread(_resolve_trip_context, trip, target_days, aspect)
    session = await asyncio.to_thread(_resolve_session, session_id, trip, trip_context)
    return await asyncio.to_thread(
        ai_council.debate_council,
        topic=topic,
        trip_context=trip_context,
        session=session,
        stream_progress=False,
    )


@mcp.tool()
async def ai_council_list_sessions() -> List[Dict[str, Any]]:
    """List saved multi-turn AI Travel Council sessions."""
    return await asyncio.to_thread(ai_council.CouncilSession.list_saved_sessions)


@mcp.tool()
async def validate_trip_claude(trip: str) -> Dict[str, Any]:
    """
    Run a full itinerary validation report using Anthropic Claude.

    Args:
        trip: Wanderlog trip ID or path to a local trip JSON/markdown file.
    """
    trip_data, trip_md = await asyncio.to_thread(claude_validator.fetch_trip_data, trip)
    trip_summary = claude_validator.summarize_trip_context(trip_data, trip_md)
    cfg = claude_validator.ClaudeProviderConfig()
    report, reasoning = await asyncio.to_thread(
        claude_validator.run_claude_validation,
        trip_summary,
        cfg,
        False,
    )
    return {
        "provider": cfg.provider,
        "model": cfg.model,
        "trip": trip,
        "report": report,
        "reasoning": reasoning,
    }


@mcp.tool()
async def validate_trip_deepseek(trip: str) -> Dict[str, Any]:
    """
    Run a full itinerary validation report using DeepSeek.

    Args:
        trip: Wanderlog trip ID or path to a local trip JSON/markdown file.
    """
    trip_data, trip_md = await asyncio.to_thread(deepseek_validator.fetch_trip_data, trip)
    trip_summary = deepseek_validator.summarize_trip_context(trip_data, trip_md)
    cfg = deepseek_validator.ProviderConfig()
    report, reasoning = await asyncio.to_thread(
        deepseek_validator.run_validation,
        trip_summary,
        cfg,
        False,
    )
    return {
        "provider": cfg.provider,
        "model": cfg.model,
        "trip": trip,
        "report": report,
        "reasoning": reasoning,
    }


@mcp.tool()
async def validate_trip_crosscheck(trip: str) -> Dict[str, Any]:
    """
    Run both Claude and DeepSeek validators and synthesize a cross-checked comparison report.

    Args:
        trip: Wanderlog trip ID or path to a local trip JSON/markdown file.
    """
    claude_cfg = claude_validator.ClaudeProviderConfig()
    ds_cfg = deepseek_validator.ProviderConfig()
    cross_check_md, claude_report, ds_report = await asyncio.to_thread(
        cross_check_validator.run_cross_check,
        trip,
        claude_cfg,
        ds_cfg,
        False,
    )
    return {
        "trip": trip,
        "claude_model": claude_cfg.model,
        "deepseek_model": ds_cfg.model,
        "cross_check_report": cross_check_md,
        "claude_report": claude_report,
        "deepseek_report": ds_report,
    }


@mcp.tool()
async def check_ai_providers_status(live_verify: bool = False) -> Dict[str, Any]:
    """
    Check configuration and optional live connectivity for Claude and DeepSeek providers.

    Args:
        live_verify: Send a lightweight probe request to verify API connectivity (default False).
    """
    claude_cfg = claude_validator.ClaudeProviderConfig()
    ds_cfg = deepseek_validator.ProviderConfig()

    def _probe(fn: Callable[[Any], bool], cfg: Any) -> bool:
        with contextlib.redirect_stdout(sys.stderr):
            return fn(cfg)

    claude_status: Dict[str, Any] = {
        "provider": claude_cfg.provider,
        "model": claude_cfg.model,
        "configured": bool(claude_cfg.api_key),
    }
    ds_status: Dict[str, Any] = {
        "provider": ds_cfg.provider,
        "model": ds_cfg.model,
        "configured": bool(ds_cfg.api_key),
    }

    if live_verify:
        claude_status["connected"] = await asyncio.to_thread(_probe, claude_validator.verify_connection, claude_cfg)
        ds_status["connected"] = await asyncio.to_thread(_probe, deepseek_validator.verify_connection, ds_cfg)

    return {"claude": claude_status, "deepseek": ds_status}


@mcp.tool()
async def self_update_check() -> Dict[str, Any]:
    """Check whether git or Antigravity CLI updates are available via scripts/self_update.sh --check."""
    script_path = str(Path(_SCRIPTS_DIR) / "self_update.sh")
    proc = await asyncio.create_subprocess_exec(
        script_path,
        "--check",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    return {
        "exit_code": proc.returncode,
        "output": stdout_bytes.decode("utf-8", errors="replace"),
        "stderr": stderr_bytes.decode("utf-8", errors="replace"),
    }


if __name__ == "__main__":
    mcp.run()
