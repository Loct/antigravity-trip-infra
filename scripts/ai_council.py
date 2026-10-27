#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.27.0",
#     "rich>=13.0.0",
#     "anthropic>=0.40.0",
#     "openai>=1.0.0",
# ]
# ///
"""
Conversational AI Travel Council (Multi-AI Co-Planning, Cross-Checking & Debate)

Enables Antigravity and the user to actively converse with Anthropic Claude and DeepSeek:
1. Multi-turn dialogue: Maintain conversational context across questions and follow-ups.
2. Cross-examination & Peer Review: Have Claude and DeepSeek cross-check itinerary data,
   detect discrepancies, and verify transit, opening hours, lodging, and dining.
3. Debate mode: Let Claude and DeepSeek debate itinerary alternatives and synthesize consensus.
4. Interactive chat: Live terminal discussion with rich markdown visual panels.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import claude_validator
import deepseek_validator

console = Console()

# Default directory for persisted council conversational sessions
DEFAULT_SESSION_DIR = SCRIPT_DIR.parent / "trips" / ".council_sessions"
FALLBACK_SESSION_DIR = Path("/tmp/council_sessions")


CLAUDE_COUNCIL_PROMPT = """You are Anthropic Claude, the Culture, Dining & Experiential Specialist on an AI Travel Council, collaborating conversationally with lead planner Antigravity, logistics expert DeepSeek, and the traveler.
You have access to the user's Wanderlog travel itinerary.

Your focus:
1. Pacing, atmosphere, ambiance, and avoiding traveler burnout.
2. Cultural nuances, seasonal context, and opening hours/days (e.g. museum closures on Mondays, holidays like Tết or Ferragosto).
3. Authentic dining recommendations, neighborhood food culture, and single balanced lunch/dinner flow.
4. Active conversational collaboration:
   - When reviewing ideas from Antigravity or DeepSeek, state clearly what you love, what feels rushed or uninspired, and suggest experiential enhancements.
   - Keep answers conversational, direct, and actionable—avoid generic travel brochure fluff.
   - Reference specific place names, districts, and time windows.
"""

DEEPSEEK_COUNCIL_PROMPT = """You are DeepSeek, the Logistics, Transit & Route Geometry Specialist on an AI Travel Council, collaborating conversationally with lead planner Antigravity, cultural advisor Claude, and the traveler.
You have access to the user's Wanderlog travel itinerary.

Your focus:
1. Routing logistics: geographic clustering vs erratic zigzagging / backtracking across cities or provinces.
2. Realistic transit buffers: driving/taxi times with realistic rush-hour traffic, walking fatigue, and boat/ferry schedules.
3. Airport and rail continuity: 2–3 hour airport arrival buffers, train station arrival margins, and luggage transfer windows.
4. Lodging continuity: ensuring hotel nights match itinerary days with smooth check-in/out bags management.
5. Active conversational collaboration:
   - When reviewing ideas from Antigravity or Claude, run the logistical math. Challenge unrealistic transit or timing politely and propose concrete timetable fixes.
   - Keep answers conversational, direct, and actionable—avoid fluff.
   - Reference specific place names, distances, and suggested departure/arrival timestamps.
"""

COUNCIL_SYSTEM_PROMPT = """You are an expert travel co-planner and logistical advisor on an AI Travel Council, collaborating with the user and lead planner Antigravity.
You have access to the user's Wanderlog travel itinerary.

Your role is to:
1. Provide sharp, realistic, and honest feedback on the user's question or travel plan.
2. Flag logistical traps: unreasonable transit times, geographic backtracking, opening hour traps (e.g., museums closed Mondays, holiday closures), airport check-in margins, and hotel continuity.
3. If asked about dining, evaluate recommendations for authentic local cuisine with balanced lunch/dinner flow.
4. Keep your answer conversational, direct, and actionable—avoid fluff.
5. If suggesting fixes, give specific place names, districts, or suggested time windows.
"""


class CouncilSession:
    """Manages multi-turn conversational dialogue and cross-talk history between Antigravity, Claude, and DeepSeek."""

    def __init__(self, session_id: str, trip_target: Optional[str] = None):
        self.session_id = session_id
        self.trip_target = trip_target
        self.trip_context = ""
        self.turns: List[Dict[str, Any]] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    def add_turn(
        self,
        query: str,
        claude_response: Optional[str] = None,
        deepseek_response: Optional[str] = None,
        synthesis: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        turn_num = len(self.turns) + 1
        self.turns.append({
            "turn": turn_num,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "claude": claude_response,
            "deepseek": deepseek_response,
            "synthesis": synthesis,
            "metadata": metadata or {},
        })
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def get_messages_for_claude(self, new_query: str, include_co_counsel: bool = True) -> List[Dict[str, str]]:
        """Construct multi-turn message history for Claude."""
        messages: List[Dict[str, str]] = []
        for t in self.turns:
            q = t.get("query", "")
            c = t.get("claude") or ""
            d = t.get("deepseek") or ""
            if q:
                messages.append({"role": "user", "content": q})
            assistant_content = c
            if include_co_counsel and d and d.strip():
                assistant_content += f"\n\n[Co-Council Logistics Advisor DeepSeek noted]:\n{d.strip()}"
            if assistant_content.strip():
                messages.append({"role": "assistant", "content": assistant_content})

        messages.append({"role": "user", "content": new_query})
        return messages

    def get_messages_for_deepseek(self, new_query: str, include_co_counsel: bool = True) -> List[Dict[str, str]]:
        """Construct multi-turn message history for DeepSeek."""
        messages: List[Dict[str, str]] = []
        for t in self.turns:
            q = t.get("query", "")
            c = t.get("claude") or ""
            d = t.get("deepseek") or ""
            if q:
                messages.append({"role": "user", "content": q})
            assistant_content = d
            if include_co_counsel and c and c.strip():
                assistant_content += f"\n\n[Co-Council Cultural & Experience Advisor Claude noted]:\n{c.strip()}"
            if assistant_content.strip():
                messages.append({"role": "assistant", "content": assistant_content})

        messages.append({"role": "user", "content": new_query})
        return messages

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "trip_target": self.trip_target,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "turns_count": len(self.turns),
            "turns": self.turns,
        }

    def save(self, storage_dir: Optional[Path] = None) -> Path:
        target_dir = storage_dir or DEFAULT_SESSION_DIR
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            target_dir = FALLBACK_SESSION_DIR
            target_dir.mkdir(parents=True, exist_ok=True)

        safe_id = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in self.session_id)
        file_path = target_dir / f"{safe_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return file_path

    @classmethod
    def load(cls, session_id: str, storage_dir: Optional[Path] = None) -> Optional["CouncilSession"]:
        dirs_to_check = [storage_dir or DEFAULT_SESSION_DIR, FALLBACK_SESSION_DIR]
        safe_id = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in session_id)

        for d in dirs_to_check:
            file_path = d / f"{safe_id}.json"
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    session = cls(session_id=data.get("session_id", session_id), trip_target=data.get("trip_target"))
                    session.created_at = data.get("created_at", session.created_at)
                    session.updated_at = data.get("updated_at", session.updated_at)
                    session.turns = data.get("turns", [])
                    return session
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to load session {file_path}: {e}[/yellow]")
        return None

    @classmethod
    def list_saved_sessions(cls, storage_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
        dirs_to_check = [storage_dir or DEFAULT_SESSION_DIR, FALLBACK_SESSION_DIR]
        sessions = []
        seen = set()
        for d in dirs_to_check:
            if not d.exists():
                continue
            for f in d.glob("*.json"):
                if f.stem in seen:
                    continue
                seen.add(f.stem)
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        meta = json.load(fp)
                    sessions.append({
                        "session_id": meta.get("session_id", f.stem),
                        "trip_target": meta.get("trip_target", "N/A"),
                        "turns_count": meta.get("turns_count", len(meta.get("turns", []))),
                        "updated_at": meta.get("updated_at", ""),
                        "path": str(f),
                    })
                except Exception:
                    continue
        return sessions


def filter_trip_context(
    data: Dict[str, Any],
    md: str,
    target_days: Optional[List[int]] = None,
    aspect: str = "all",
) -> str:
    """
    Extract structured context from trip data.
    Allows targeting specific days and filtering by aspect (transit, dining, hours, hotels, all).
    """
    tp = data.get("tripPlan", {}) if "tripPlan" in data else data.get("trip", {})
    if not tp and "title" in data:
        tp = data

    title = tp.get("title", "Untitled Trip")
    start_date = tp.get("startDate", "N/A")
    end_date = tp.get("endDate", "N/A")
    place_count = tp.get("placeCount", "N/A")

    day_filter_str = f" (Focus: Day(s) {', '.join(map(str, target_days))})" if target_days else ""
    aspect_str = f" [Aspect Filter: {aspect.upper()}]" if aspect != "all" else ""
    lines = [
        f"# Trip Context: {title}{day_filter_str}{aspect_str}",
        f"- Dates: {start_date} to {end_date}",
        f"- Total Days: {tp.get('days', 'N/A')}",
        f"- Total Places Listed: {place_count}",
        "",
    ]

    itin = tp.get("itinerary", {})
    sections = itin.get("sections", [])

    # Lodging
    if aspect in ("all", "hotels", "transit"):
        lodgings = []
        for s in sections:
            if s.get("type") == "hotels":
                for b in s.get("blocks", []):
                    p = b.get("place", {})
                    lodgings.append(f"- {p.get('name')}: {p.get('formatted_address', '')}")
        if lodgings:
            lines.append("## Accommodations:")
            lines.extend(lodgings)
            lines.append("")

    # Flights & Long-Distance Transit
    if aspect in ("all", "transit"):
        flights = []
        for s in sections:
            if s.get("type") == "flights":
                for b in s.get("blocks", []):
                    finfo = b.get("flightInfo", {})
                    carrier = finfo.get("airline", {}).get("iata", "")
                    num = finfo.get("number", "")
                    dep = b.get("depart", {})
                    arr = b.get("arrive", {})
                    flights.append(
                        f"- Flight {carrier} {num}: {dep.get('airport', {}).get('name')} "
                        f"({dep.get('date')} {dep.get('time')}) -> "
                        f"{arr.get('airport', {}).get('name')} ({arr.get('date')} {arr.get('time')})"
                    )
        if flights:
            lines.append("## Flights & Long-Distance Transit:")
            lines.extend(flights)
            lines.append("")

    # Day-by-day
    lines.append("## Daily Activities & Notes:")
    day_idx = 0
    matched_any_day = False
    for s in sections:
        date = s.get("date")
        if date:
            day_idx += 1
            if target_days and day_idx not in target_days:
                continue
            matched_any_day = True
            lines.append(f"### Day {day_idx} ({date}):")
            blocks = s.get("blocks", [])
            if not blocks:
                lines.append("  (No scheduled activities / Transit day)")
            for b in blocks:
                btype = b.get("type")
                if btype == "place":
                    p = b.get("place", {})
                    name = p.get("name", "Unknown")
                    addr = p.get("formatted_address", "")
                    text_ops = b.get("text", {}).get("ops", [])
                    note = "".join([op.get("insert", "") for op in text_ops if isinstance(op, dict)]).strip()
                    note_str = f" | Note: {note}" if note else ""

                    # Filter based on aspect if requested
                    if aspect == "dining":
                        lower_name = (name + " " + note).lower()
                        if any(kw in lower_name for kw in ("restaurant", "food", "dinner", "lunch", "cafe", "bistro", "eatery", "cuisine", "pho", "bun cha", "coffee")):
                            lines.append(f"  - Place: {name} (Address: {addr}){note_str}")
                    else:
                        lines.append(f"  - Place: {name} (Address: {addr}){note_str}")
                elif btype == "text":
                    text_ops = b.get("text", {}).get("ops", [])
                    note = "".join([op.get("insert", "") for op in text_ops if isinstance(op, dict)]).strip()
                    if aspect == "dining":
                        lower_note = note.lower()
                        if any(kw in lower_note for kw in ("restaurant", "food", "dinner", "lunch", "cafe", "meal", "eat")):
                            lines.append(f"  - Dining Note: {note}")
                    else:
                        lines.append(f"  - Note: {note}")
            lines.append("")

    if md.strip() and not matched_any_day:
        lines.append("## Additional Itinerary Details:")
        lines.append(md.strip())

    return "\n".join(lines)


def ask_claude(
    query: str,
    trip_context: str,
    history_messages: Optional[List[Dict[str, str]]] = None,
    claude_cfg: Optional[claude_validator.ClaudeProviderConfig] = None,
    system_prompt: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """Query Claude with multi-turn conversational support."""
    cfg = claude_cfg or claude_validator.ClaudeProviderConfig()
    sys_prompt = system_prompt or CLAUDE_COUNCIL_PROMPT

    # Contextual system prompt with itinerary
    system_with_context = f"{sys_prompt}\n\n=== ITINERARY CONTEXT ===\n{trip_context}"

    if history_messages:
        messages = list(history_messages)
    else:
        messages = [{"role": "user", "content": query}]

    if cfg.provider == "openrouter":
        client = cfg.get_openrouter_client()
        call_messages = [{"role": "system", "content": system_with_context}] + messages
        tokens_to_request = 1500
        try:
            resp = client.chat.completions.create(
                model=cfg.model,
                messages=call_messages,
                temperature=0.4,
                max_tokens=tokens_to_request,
            )
        except Exception as e:
            err_msg = str(e)
            if "fewer max_tokens" in err_msg or "402" in err_msg or "credits" in err_msg:
                # Try lower token allocation or cost-effective haiku model
                try:
                    resp = client.chat.completions.create(
                        model="anthropic/claude-haiku-4.5",
                        messages=call_messages,
                        temperature=0.4,
                        max_tokens=1000,
                    )
                except Exception:
                    resp = client.chat.completions.create(
                        model=cfg.model,
                        messages=call_messages,
                        temperature=0.4,
                        max_tokens=800,
                    )
            elif "no longer available" in err_msg or "404" in err_msg:
                fallback_model = "anthropic/claude-sonnet-4.5"
                resp = client.chat.completions.create(
                    model=fallback_model,
                    messages=call_messages,
                    temperature=0.4,
                    max_tokens=tokens_to_request,
                )
            else:
                raise e

        content = resp.choices[0].message.content or ""
        reasoning = getattr(resp.choices[0].message, "reasoning", None)
        return content, reasoning
    else:
        client = cfg.get_anthropic_client()
        use_thinking = cfg.is_thinking_supported()
        create_kwargs: Dict[str, Any] = {
            "model": cfg.model,
            "system": system_with_context,
            "messages": messages,
            "max_tokens": max(cfg.thinking_budget + 2500, 3000) if use_thinking else 2500,
        }
        if use_thinking:
            create_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": cfg.thinking_budget,
            }
        else:
            create_kwargs["temperature"] = 0.4

        resp = client.messages.create(**create_kwargs)
        reasoning_list = []
        content_list = []
        for block in getattr(resp, "content", []):
            b_type = getattr(block, "type", "")
            if b_type == "thinking":
                reasoning_list.append(getattr(block, "thinking", ""))
            elif b_type == "text":
                content_list.append(getattr(block, "text", ""))

        content = "".join(content_list)
        reasoning = "".join(reasoning_list) if reasoning_list else None
        return content, reasoning


def ask_deepseek(
    query: str,
    trip_context: str,
    history_messages: Optional[List[Dict[str, str]]] = None,
    ds_cfg: Optional[deepseek_validator.ProviderConfig] = None,
    system_prompt: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """Query DeepSeek with multi-turn conversational support."""
    cfg = ds_cfg or deepseek_validator.ProviderConfig()
    sys_prompt = system_prompt or DEEPSEEK_COUNCIL_PROMPT
    system_with_context = f"{sys_prompt}\n\n=== ITINERARY CONTEXT ===\n{trip_context}"

    if history_messages:
        messages = list(history_messages)
    else:
        messages = [{"role": "user", "content": query}]

    client = cfg.get_client()
    call_messages = [{"role": "system", "content": system_with_context}] + messages

    resp = client.chat.completions.create(
        model=cfg.model,
        messages=call_messages,
        temperature=0.3,
        max_tokens=2500,
    )
    content = resp.choices[0].message.content or ""
    reasoning = getattr(resp.choices[0].message, "reasoning", None) or getattr(
        resp.choices[0].message, "reasoning_content", None
    )
    return content, reasoning


def ask_council(
    query: str,
    trip_context: str,
    session: Optional[CouncilSession] = None,
    claude_cfg: Optional[claude_validator.ClaudeProviderConfig] = None,
    ds_cfg: Optional[deepseek_validator.ProviderConfig] = None,
    stream_progress: bool = True,
) -> Dict[str, Any]:
    """
    Query both Claude and DeepSeek conversationally and return a structured multi-AI synthesis.
    If session is provided, context is updated and history is preserved.
    """
    c_cfg = claude_cfg or claude_validator.ClaudeProviderConfig()
    d_cfg = ds_cfg or deepseek_validator.ProviderConfig()

    results: Dict[str, Any] = {
        "query": query,
        "models": {
            "claude": c_cfg.model,
            "deepseek": d_cfg.model,
        },
        "session_id": session.session_id if session else None,
        "claude": {"response": "", "reasoning": None, "available": True},
        "deepseek": {"response": "", "reasoning": None, "available": True},
    }

    claude_history = session.get_messages_for_claude(query) if session else None
    deepseek_history = session.get_messages_for_deepseek(query) if session else None

    # Query Claude
    try:
        if stream_progress:
            with console.status(f"[bold magenta]Consulting Claude ({c_cfg.model})...[/bold magenta]", spinner="dots"):
                c_resp, c_reason = ask_claude(query, trip_context, history_messages=claude_history, claude_cfg=c_cfg)
        else:
            c_resp, c_reason = ask_claude(query, trip_context, history_messages=claude_history, claude_cfg=c_cfg)
        results["claude"]["response"] = c_resp
        results["claude"]["reasoning"] = c_reason
    except Exception as e:
        results["claude"]["available"] = False
        results["claude"]["error"] = str(e)
        if stream_progress:
            console.print(f"[yellow]Claude consultation skipped: {e}[/yellow]")

    # Query DeepSeek
    try:
        if stream_progress:
            with console.status(f"[bold blue]Consulting DeepSeek ({d_cfg.model})...[/bold blue]", spinner="dots"):
                d_resp, d_reason = ask_deepseek(query, trip_context, history_messages=deepseek_history, ds_cfg=d_cfg)
        else:
            d_resp, d_reason = ask_deepseek(query, trip_context, history_messages=deepseek_history, ds_cfg=d_cfg)
        results["deepseek"]["response"] = d_resp
        results["deepseek"]["reasoning"] = d_reason
    except Exception as e:
        results["deepseek"]["available"] = False
        results["deepseek"]["error"] = str(e)
        if stream_progress:
            console.print(f"[yellow]DeepSeek consultation skipped: {e}[/yellow]")

    # Record turn into session if active
    if session:
        session.add_turn(
            query=query,
            claude_response=results["claude"]["response"] if results["claude"]["available"] else None,
            deepseek_response=results["deepseek"]["response"] if results["deepseek"]["available"] else None,
        )
        session.save()

    return results


def cross_check_trip_data(
    trip_data: Dict[str, Any],
    trip_md: str,
    aspect: str = "all",
    target_days: Optional[List[int]] = None,
    claude_cfg: Optional[claude_validator.ClaudeProviderConfig] = None,
    ds_cfg: Optional[deepseek_validator.ProviderConfig] = None,
    session: Optional[CouncilSession] = None,
    stream_progress: bool = True,
) -> Dict[str, Any]:
    """
    Two-Round Conversational Cross-Check & Peer Review of Itinerary Data:
    - Round 1: Claude & DeepSeek independently inspect the trip data for the specified aspect.
    - Round 2 (Cross-Talk): DeepSeek cross-examines Claude's report for transit/logistical flaws;
                           Claude cross-examines DeepSeek's report for cultural/experiential flaws.
    - Synthesis: Cross-verified facts, discrepancies, and vetted action items.
    """
    c_cfg = claude_cfg or claude_validator.ClaudeProviderConfig()
    d_cfg = ds_cfg or deepseek_validator.ProviderConfig()
    trip_context = filter_trip_context(trip_data, trip_md, target_days=target_days, aspect=aspect)

    day_label = f"Day(s) {', '.join(map(str, target_days))}" if target_days else "Full Trip"
    initial_prompt = (
        f"Please perform a rigorous data inspection on {day_label} specifically focusing on: {aspect.upper()}.\n"
        "Identify:\n"
        "1. Verified accurate elements (places, sequences, timings).\n"
        "2. Potential errors, logistical traps, closed days/hours, or missing items.\n"
        "3. Concrete proposed fixes with exact place names."
    )

    results: Dict[str, Any] = {
        "mode": "cross_check",
        "aspect": aspect,
        "target_days": target_days,
        "round_1": {"claude": "", "deepseek": ""},
        "round_2_cross_examination": {"deepseek_critique_of_claude": "", "claude_critique_of_deepseek": ""},
        "session_id": session.session_id if session else None,
    }

    # Round 1: Independent Analysis
    if stream_progress:
        with console.status("[bold magenta]Round 1: Claude evaluating experiential & cultural data...[/bold magenta]", spinner="dots"):
            c_r1, _ = ask_claude(initial_prompt, trip_context, claude_cfg=c_cfg)
        with console.status("[bold blue]Round 1: DeepSeek evaluating transit & routing geometry...[/bold blue]", spinner="dots"):
            d_r1, _ = ask_deepseek(initial_prompt, trip_context, ds_cfg=d_cfg)
    else:
        c_r1, _ = ask_claude(initial_prompt, trip_context, claude_cfg=c_cfg)
        d_r1, _ = ask_deepseek(initial_prompt, trip_context, ds_cfg=d_cfg)

    results["round_1"]["claude"] = c_r1
    results["round_1"]["deepseek"] = d_r1

    # Round 2: Peer Review & Cross-Examination
    deepseek_cross_prompt = (
        f"Co-council advisor Claude completed Round 1 review of the {aspect.upper()} data:\n\n"
        f"--- CLAUDE REVIEW ---\n{c_r1}\n---------------------\n\n"
        "As DeepSeek (Logistics & Transit Specialist), cross-examine Claude's findings against the trip data:\n"
        "1. Do Claude's suggested fixes introduce transit backtracking, unrealistic driving times, or missed connections?\n"
        "2. Which points of Claude's analysis are logistically solid and verified by you?\n"
        "3. Where do you disagree or propose an alternative logistical solution?"
    )

    claude_cross_prompt = (
        f"Co-council advisor DeepSeek completed Round 1 review of the {aspect.upper()} data:\n\n"
        f"--- DEEPSEEK REVIEW ---\n{d_r1}\n-----------------------\n\n"
        "As Anthropic Claude (Culture & Experience Specialist), cross-examine DeepSeek's findings against the trip data:\n"
        "1. Does DeepSeek's logistical optimization preserve the cultural atmosphere and pacing, or does it feel rushed and sterile?\n"
        "2. Did DeepSeek overlook opening hours, authentic dining ambience, or seasonal nuances?\n"
        "3. Where do you agree with DeepSeek, and where do you challenge DeepSeek?"
    )

    if stream_progress:
        with console.status("[bold blue]Round 2: DeepSeek cross-examining Claude's suggestions...[/bold blue]", spinner="dots"):
            d_r2, _ = ask_deepseek(deepseek_cross_prompt, trip_context, ds_cfg=d_cfg)
        with console.status("[bold magenta]Round 2: Claude cross-examining DeepSeek's suggestions...[/bold magenta]", spinner="dots"):
            c_r2, _ = ask_claude(claude_cross_prompt, trip_context, claude_cfg=c_cfg)
    else:
        d_r2, _ = ask_deepseek(deepseek_cross_prompt, trip_context, ds_cfg=d_cfg)
        c_r2, _ = ask_claude(claude_cross_prompt, trip_context, claude_cfg=c_cfg)

    results["round_2_cross_examination"]["deepseek_critique_of_claude"] = d_r2
    results["round_2_cross_examination"]["claude_critique_of_deepseek"] = c_r2

    if session:
        session.add_turn(
            query=f"Cross-check itinerary data ({aspect}, {day_label})",
            claude_response=f"Round 1:\n{c_r1}\n\nRound 2 Critique of DeepSeek:\n{c_r2}",
            deepseek_response=f"Round 1:\n{d_r1}\n\nRound 2 Critique of Claude:\n{d_r2}",
            metadata={"mode": "cross_check", "aspect": aspect, "target_days": target_days},
        )
        session.save()

    return results


def debate_council(
    topic: str,
    trip_context: str,
    claude_cfg: Optional[claude_validator.ClaudeProviderConfig] = None,
    ds_cfg: Optional[deepseek_validator.ProviderConfig] = None,
    session: Optional[CouncilSession] = None,
    stream_progress: bool = True,
) -> Dict[str, Any]:
    """
    Two-round structured debate between Claude and DeepSeek on an itinerary decision.
    """
    c_cfg = claude_cfg or claude_validator.ClaudeProviderConfig()
    d_cfg = ds_cfg or deepseek_validator.ProviderConfig()

    debate_q = f"Travel Debate Dilemma: {topic}"

    # Round 1: Opening Arguments
    if stream_progress:
        with console.status("[bold magenta]Debate Round 1: Claude presenting experiential argument...[/bold magenta]", spinner="dots"):
            c_r1, _ = ask_claude(f"Present your recommendation on this travel debate: {topic}", trip_context, claude_cfg=c_cfg)
        with console.status("[bold blue]Debate Round 1: DeepSeek presenting logistical argument...[/bold blue]", spinner="dots"):
            d_r1, _ = ask_deepseek(f"Present your recommendation on this travel debate: {topic}", trip_context, ds_cfg=d_cfg)
    else:
        c_r1, _ = ask_claude(f"Present your recommendation on this travel debate: {topic}", trip_context, claude_cfg=c_cfg)
        d_r1, _ = ask_deepseek(f"Present your recommendation on this travel debate: {topic}", trip_context, ds_cfg=d_cfg)

    # Round 2: Direct Rebuttal / Cross-Talk
    d_rebuttal_prompt = (
        f"Debate Dilemma: {topic}\n\n"
        f"Claude argues:\n{c_r1}\n\n"
        "Respond directly to Claude. Defend or adjust your logistical stance and identify the best compromise."
    )
    c_rebuttal_prompt = (
        f"Debate Dilemma: {topic}\n\n"
        f"DeepSeek argues:\n{d_r1}\n\n"
        "Respond directly to DeepSeek. Defend or adjust your experiential stance and identify the best compromise."
    )

    if stream_progress:
        with console.status("[bold blue]Debate Round 2: DeepSeek responding to Claude...[/bold blue]", spinner="dots"):
            d_r2, _ = ask_deepseek(d_rebuttal_prompt, trip_context, ds_cfg=d_cfg)
        with console.status("[bold magenta]Debate Round 2: Claude responding to DeepSeek...[/bold magenta]", spinner="dots"):
            c_r2, _ = ask_claude(c_rebuttal_prompt, trip_context, claude_cfg=c_cfg)
    else:
        d_r2, _ = ask_deepseek(d_rebuttal_prompt, trip_context, ds_cfg=d_cfg)
        c_r2, _ = ask_claude(c_rebuttal_prompt, trip_context, claude_cfg=c_cfg)

    results = {
        "mode": "debate",
        "topic": topic,
        "round_1": {"claude": c_r1, "deepseek": d_r1},
        "round_2": {"claude_rebuttal": c_r2, "deepseek_rebuttal": d_r2},
        "session_id": session.session_id if session else None,
    }

    if session:
        session.add_turn(
            query=debate_q,
            claude_response=f"Stance:\n{c_r1}\n\nResponse to DeepSeek:\n{c_r2}",
            deepseek_response=f"Stance:\n{d_r1}\n\nResponse to Claude:\n{d_r2}",
            metadata={"mode": "debate", "topic": topic},
        )
        session.save()

    return results


def format_cross_check_markdown(results: Dict[str, Any]) -> str:
    """Format cross-check consultation into structured markdown."""
    aspect = results.get("aspect", "all").upper()
    r1 = results.get("round_1", {})
    r2 = results.get("round_2_cross_examination", {})

    lines = [
        f"### 🔍 Dual AI Travel Data Cross-Check ({aspect})",
        "",
        "#### 🎭 Round 1: Claude's Experiential & Opening Hours Audit",
        r1.get("claude", "").strip(),
        "",
        "#### 🧠 Round 1: DeepSeek's Transit & Backtracking Audit",
        r1.get("deepseek", "").strip(),
        "",
        "---",
        "### ⚔️ Round 2: Conversational Peer Review & Cross-Examination",
        "",
        "#### 🧠 DeepSeek Cross-Checking Claude's Findings",
        r2.get("deepseek_critique_of_claude", "").strip(),
        "",
        "#### 🎭 Claude Cross-Checking DeepSeek's Findings",
        r2.get("claude_critique_of_deepseek", "").strip(),
        "",
        "---",
        "💡 *Antigravity Synthesis: Review these verified points with the user before applying mutations.*",
    ]
    return "\n".join(lines)


def format_debate_markdown(results: Dict[str, Any]) -> str:
    """Format debate results into clean markdown."""
    topic = results.get("topic", "")
    r1 = results.get("round_1", {})
    r2 = results.get("round_2", {})

    lines = [
        f"### ⚔️ AI Travel Council Debate: *\"{topic}\"*",
        "",
        "#### 🎭 Claude's Opening Stance (Culture & Pacing)",
        r1.get("claude", "").strip(),
        "",
        "#### 🧠 DeepSeek's Opening Stance (Logistics & Efficiency)",
        r1.get("deepseek", "").strip(),
        "",
        "---",
        "#### 🔄 Cross-Talk & Rebuttals",
        "",
        "**DeepSeek responding to Claude:**",
        r2.get("deepseek_rebuttal", "").strip(),
        "",
        "**Claude responding to DeepSeek:**",
        r2.get("claude_rebuttal", "").strip(),
        "",
        "---",
        "💡 *Council Recommendation: Balance Claude's experience value with DeepSeek's transit buffer.*",
    ]
    return "\n".join(lines)


def format_council_markdown(results: Dict[str, Any]) -> str:
    """Format council consultation results into a clean markdown block."""
    lines = [
        f"### 🏛️ AI Travel Council Consultation",
        f"**Question:** *\"{results.get('query', '')}\"*",
        "",
    ]

    c_info = results.get("claude", {})
    if c_info.get("available"):
        lines.extend([
            f"#### 🎭 Anthropic Claude (`{results['models']['claude']}`)",
            c_info.get("response", "").strip(),
            "",
        ])
    elif "error" in c_info:
        lines.append(f"*Claude consultation unavailable: {c_info['error']}*\n")

    d_info = results.get("deepseek", {})
    if d_info.get("available"):
        lines.extend([
            f"#### 🧠 DeepSeek (`{results['models']['deepseek']}`)",
            d_info.get("response", "").strip(),
            "",
        ])
    elif "error" in d_info:
        lines.append(f"*DeepSeek consultation unavailable: {d_info['error']}*\n")

    lines.extend([
        "---",
        "💡 *Tip: Discuss these perspectives with Antigravity to adjust your Wanderlog plan.*",
    ])
    return "\n".join(lines)


def display_council_results(results: Dict[str, Any]) -> None:
    """Render rich terminal view of council perspectives."""
    console.print("\n")
    console.print(
        Panel(
            f"[bold white]Query:[/bold white] [italic]{results.get('query')}[/italic]",
            title="[bold yellow]🏛️ AI Travel Council Feedback[/bold yellow]",
            border_style="yellow",
        )
    )

    c_info = results.get("claude", {})
    if c_info.get("available"):
        console.print(
            Panel(
                Markdown(c_info.get("response", "")),
                title=f"[bold magenta]🎭 Claude ({results['models']['claude']})[/bold magenta]",
                border_style="magenta",
            )
        )

    d_info = results.get("deepseek", {})
    if d_info.get("available"):
        console.print(
            Panel(
                Markdown(d_info.get("response", "")),
                title=f"[bold blue]🧠 DeepSeek ({results['models']['deepseek']})[/bold blue]",
                border_style="blue",
            )
        )


def display_cross_check_results(results: Dict[str, Any]) -> None:
    """Render rich terminal view of cross-check findings."""
    aspect = results.get("aspect", "all").upper()
    console.print("\n")
    console.print(
        Panel(
            f"[bold cyan]Dual AI Data Cross-Check: {aspect}[/bold cyan]\n"
            f"Target Days: {results.get('target_days') or 'All'}",
            title="[bold yellow]🔍 Itinerary Data Cross-Check[/bold yellow]",
            border_style="yellow",
        )
    )

    r1 = results.get("round_1", {})
    console.print(
        Panel(
            Markdown(r1.get("claude", "")),
            title="[bold magenta]Round 1: Claude's Experiential & Opening Hours Audit[/bold magenta]",
            border_style="magenta",
        )
    )
    console.print(
        Panel(
            Markdown(r1.get("deepseek", "")),
            title="[bold blue]Round 1: DeepSeek's Transit & Backtracking Audit[/bold blue]",
            border_style="blue",
        )
    )

    r2 = results.get("round_2_cross_examination", {})
    console.print(
        Panel(
            Markdown(r2.get("deepseek_critique_of_claude", "")),
            title="[bold blue]Round 2: DeepSeek Cross-Checking Claude's Suggestions[/bold blue]",
            border_style="blue",
        )
    )
    console.print(
        Panel(
            Markdown(r2.get("claude_critique_of_deepseek", "")),
            title="[bold magenta]Round 2: Claude Cross-Checking DeepSeek's Suggestions[/bold magenta]",
            border_style="magenta",
        )
    )


def display_debate_results(results: Dict[str, Any]) -> None:
    """Render rich terminal view of debate results."""
    console.print("\n")
    console.print(
        Panel(
            f"[bold white]Debate Topic:[/bold white] [italic]{results.get('topic')}[/italic]",
            title="[bold yellow]⚔️ AI Travel Council Debate[/bold yellow]",
            border_style="yellow",
        )
    )

    r1 = results.get("round_1", {})
    console.print(
        Panel(
            Markdown(r1.get("claude", "")),
            title="[bold magenta]Claude Opening Stance[/bold magenta]",
            border_style="magenta",
        )
    )
    console.print(
        Panel(
            Markdown(r1.get("deepseek", "")),
            title="[bold blue]DeepSeek Opening Stance[/bold blue]",
            border_style="blue",
        )
    )

    r2 = results.get("round_2", {})
    console.print(
        Panel(
            Markdown(r2.get("deepseek_rebuttal", "")),
            title="[bold blue]DeepSeek Cross-Talk Rebuttal[/bold blue]",
            border_style="blue",
        )
    )
    console.print(
        Panel(
            Markdown(r2.get("claude_rebuttal", "")),
            title="[bold magenta]Claude Cross-Talk Rebuttal[/bold magenta]",
            border_style="magenta",
        )
    )


def run_interactive_council(
    trip_target: str,
    claude_cfg: claude_validator.ClaudeProviderConfig,
    ds_cfg: deepseek_validator.ProviderConfig,
    session_id: Optional[str] = None,
) -> None:
    """Live interactive chat session with the AI Council."""
    console.print(f"[cyan]Loading itinerary data for [bold]{trip_target}[/bold]...[/cyan]")
    data, md = claude_validator.fetch_trip_data(trip_target)
    trip_context = filter_trip_context(data, md)

    sid = session_id or f"interactive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    session = CouncilSession.load(sid) or CouncilSession(session_id=sid, trip_target=trip_target)
    session.trip_context = trip_context

    console.print(
        Panel(
            "[bold cyan]🏛️ Conversational AI Travel Council[/bold cyan]\n\n"
            "Collaborate live with Claude, DeepSeek, and Antigravity.\n"
            f"[bold]Session ID:[/bold] {sid}\n\n"
            "Commands:\n"
            "  • Type any question or proposal and press Enter\n"
            "  • Prefix with [magenta]'claude:'[/magenta] to ask only Claude\n"
            "  • Prefix with [blue]'deepseek:'[/blue] to ask only DeepSeek\n"
            "  • [green]/crosscheck [day][/green] - Cross-examine data between both AIs\n"
            "  • [green]/debate <topic>[/green] - Run a structured debate on two options\n"
            "  • [green]/history[/green] - View previous dialogue turns\n"
            "  • [green]/exit[/green] or [green]/quit[/green] to finish\n",
            title="🏛️ Travel Council Chat",
            border_style="cyan",
        )
    )

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]Ask Council[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input or user_input.lower() in ["exit", "quit", "q", "/exit", "/quit"]:
            console.print("[dim]Exiting Travel Council chat.[/dim]")
            break

        lower = user_input.lower()

        # Handle commands
        if lower == "/history":
            if not session.turns:
                console.print("[yellow]No conversational turns yet in this session.[/yellow]")
            else:
                table = Table(title=f"Session History ({len(session.turns)} turns)")
                table.add_column("Turn", style="cyan", width=6)
                table.add_column("Query", style="white")
                table.add_column("Claude Status", style="magenta")
                table.add_column("DeepSeek Status", style="blue")
                for t in session.turns:
                    table.add_row(
                        str(t["turn"]),
                        t["query"][:60] + "..." if len(t["query"]) > 60 else t["query"],
                        "Answered" if t.get("claude") else "Skipped",
                        "Answered" if t.get("deepseek") else "Skipped",
                    )
                console.print(table)
            continue

        if lower.startswith("/crosscheck"):
            parts = user_input.split()
            day_target = None
            if len(parts) > 1 and parts[1].isdigit():
                day_target = [int(parts[1])]
            cc_results = cross_check_trip_data(
                trip_data=data,
                trip_md=md,
                aspect="all",
                target_days=day_target,
                claude_cfg=claude_cfg,
                ds_cfg=ds_cfg,
                session=session,
                stream_progress=True,
            )
            display_cross_check_results(cc_results)
            continue

        if lower.startswith("/debate"):
            topic = user_input[7:].strip()
            if not topic:
                console.print("[yellow]Please provide a debate topic (e.g. '/debate Sleeper train vs morning flight')[/yellow]")
                continue
            deb_results = debate_council(
                topic=topic,
                trip_context=trip_context,
                claude_cfg=claude_cfg,
                ds_cfg=ds_cfg,
                session=session,
                stream_progress=True,
            )
            display_debate_results(deb_results)
            continue

        # Single-agent directives
        if lower.startswith("claude:"):
            q = user_input[7:].strip()
            with console.status("[bold magenta]Claude thinking...[/bold magenta]", spinner="dots"):
                history = session.get_messages_for_claude(q)
                ans, _ = ask_claude(q, trip_context, history_messages=history, claude_cfg=claude_cfg)
            console.print(Panel(Markdown(ans), title="🎭 Claude", border_style="magenta"))
            session.add_turn(query=q, claude_response=ans, deepseek_response=None)
            session.save()
        elif lower.startswith("deepseek:"):
            q = user_input[9:].strip()
            with console.status("[bold blue]DeepSeek thinking...[/bold blue]", spinner="dots"):
                history = session.get_messages_for_deepseek(q)
                ans, _ = ask_deepseek(q, trip_context, history_messages=history, ds_cfg=ds_cfg)
            console.print(Panel(Markdown(ans), title="🧠 DeepSeek", border_style="blue"))
            session.add_turn(query=q, claude_response=None, deepseek_response=ans)
            session.save()
        else:
            results = ask_council(
                query=user_input,
                trip_context=trip_context,
                session=session,
                claude_cfg=claude_cfg,
                ds_cfg=ds_cfg,
                stream_progress=True,
            )
            display_council_results(results)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Conversational AI Travel Council (Multi-AI Co-Planning, Cross-Checking & Debate)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Question or prompt to ask the travel council (e.g. 'Can we fit Cu Chi tunnels and War Remnants Museum in the same morning?')",
    )
    parser.add_argument(
        "--trip",
        required=False,
        help="Trip ID, Wanderlog URL, or local JSON file (e.g. trips/vietnam.json)",
    )
    parser.add_argument(
        "--day",
        type=int,
        help="Focus context specifically on a single day index (e.g. 3)",
    )
    parser.add_argument(
        "--days",
        help="Comma-separated day indices to focus on (e.g. '3,4,5')",
    )
    parser.add_argument(
        "--aspect",
        choices=["all", "transit", "dining", "hours", "hotels"],
        default="all",
        help="Specific aspect to filter or cross-check (default: all)",
    )
    parser.add_argument(
        "--ai",
        choices=["council", "claude", "deepseek"],
        default="council",
        help="Which AI advisor to query (default: council queries both Claude & DeepSeek)",
    )
    parser.add_argument(
        "--session",
        help="Session identifier to persist and continue multi-turn conversational dialogue",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List all active/saved conversational sessions",
    )
    parser.add_argument(
        "--crosscheck",
        action="store_true",
        help="Perform a two-round mutual cross-examination between Claude and DeepSeek on trip data",
    )
    parser.add_argument(
        "--debate",
        help="Debate a travel dilemma between Claude and DeepSeek (e.g. --debate 'Train vs Flight to Da Nang')",
    )
    parser.add_argument(
        "--format",
        choices=["rich", "markdown", "json"],
        default="rich",
        help="Output display format (default: rich)",
    )
    parser.add_argument(
        "--claude-model",
        help="Claude model override",
    )
    parser.add_argument(
        "--deepseek-model",
        help="DeepSeek model override",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Launch an interactive live chat session with the AI council",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Perform a full conversational multi-AI itinerary audit",
    )

    args = parser.parse_args()

    if args.list_sessions:
        sessions = CouncilSession.list_saved_sessions()
        if not sessions:
            console.print("[dim]No saved council sessions found.[/dim]")
            sys.exit(0)
        table = Table(title="Saved AI Council Sessions")
        table.add_column("Session ID", style="cyan")
        table.add_column("Trip Target", style="white")
        table.add_column("Turns", style="green")
        table.add_column("Last Updated", style="yellow")
        for s in sessions:
            table.add_row(s["session_id"], s["trip_target"], str(s["turns_count"]), s["updated_at"])
        console.print(table)
        sys.exit(0)

    claude_cfg = claude_validator.ClaudeProviderConfig(model=args.claude_model)
    ds_cfg = deepseek_validator.ProviderConfig(model=args.deepseek_model)

    if args.interactive:
        if not args.trip:
            console.print("[red]Error: --trip <id_or_file> is required for interactive mode.[/red]")
            sys.exit(1)
        run_interactive_council(args.trip, claude_cfg, ds_cfg, session_id=args.session)
        return

    # Parse target days if provided
    target_days = None
    if args.day:
        target_days = [args.day]
    elif args.days:
        try:
            target_days = [int(x.strip()) for x in args.days.split(",") if x.strip()]
        except ValueError:
            console.print("[red]Error: --days must be comma-separated integers (e.g. '1,2,3')[/red]")
            sys.exit(1)

    # Resolve Trip context
    trip_target = args.trip
    trip_data: Dict[str, Any] = {}
    trip_md: str = ""
    trip_context: str = ""
    if trip_target:
        trip_data, trip_md = claude_validator.fetch_trip_data(trip_target)
        trip_context = filter_trip_context(trip_data, trip_md, target_days=target_days, aspect=args.aspect)

    # Session resolution
    session = None
    if args.session:
        session = CouncilSession.load(args.session) or CouncilSession(session_id=args.session, trip_target=trip_target)
        if trip_context:
            session.trip_context = trip_context

    # Mode 1: Cross-Check
    if args.crosscheck:
        if not trip_target:
            console.print("[red]Error: --trip <id_or_file> is required for --crosscheck.[/red]")
            sys.exit(1)
        cc_results = cross_check_trip_data(
            trip_data=trip_data,
            trip_md=trip_md,
            aspect=args.aspect,
            target_days=target_days,
            claude_cfg=claude_cfg,
            ds_cfg=ds_cfg,
            session=session,
            stream_progress=(args.format == "rich"),
        )
        if args.format == "json":
            print(json.dumps(cc_results, indent=2))
        elif args.format == "markdown":
            print(format_cross_check_markdown(cc_results))
        else:
            display_cross_check_results(cc_results)
        return

    # Mode 2: Debate
    if args.debate:
        deb_results = debate_council(
            topic=args.debate,
            trip_context=trip_context,
            claude_cfg=claude_cfg,
            ds_cfg=ds_cfg,
            session=session,
            stream_progress=(args.format == "rich"),
        )
        if args.format == "json":
            print(json.dumps(deb_results, indent=2))
        elif args.format == "markdown":
            print(format_debate_markdown(deb_results))
        else:
            display_debate_results(deb_results)
        return

    # Mode 3: Query / Audit
    query = args.query
    if args.audit and not query:
        query = (
            "Please perform a complete conversational double-check on this itinerary. "
            "Flag schedule conflicts, backtracking, missing hotel nights, or dining issues."
        )

    if not query:
        console.print(
            Panel(
                "[bold cyan]🏛️ Conversational AI Travel Council[/bold cyan]\n\n"
                "Converse with Claude & DeepSeek to cross-check data, ask questions, and debate plans.\n\n"
                "[bold]Commands & Modes:[/bold]\n"
                "  • Ask a question:     [green]uv run scripts/ai_council.py \"<question>\" --trip <id_or_file>[/green]\n"
                "  • Cross-check data:   [green]uv run scripts/ai_council.py --trip <id_or_file> --crosscheck [--day <N>] [--aspect dining][/green]\n"
                "  • Debate dilemma:     [green]uv run scripts/ai_council.py --trip <id_or_file> --debate \"Train vs Flight\"[/green]\n"
                "  • Multi-turn session: [green]uv run scripts/ai_council.py \"Follow-up question\" --session <session_id>[/green]\n"
                "  • Interactive Chat:   [green]uv run scripts/ai_council.py --trip <id_or_file> --interactive[/green]\n"
                "  • List Sessions:      [green]uv run scripts/ai_council.py --list-sessions[/green]\n",
                title="AI Travel Council",
            )
        )
        sys.exit(0)

    # Execute consultation
    if args.ai == "claude":
        claude_history = session.get_messages_for_claude(query) if session else None
        content, reasoning = ask_claude(query, trip_context, history_messages=claude_history, claude_cfg=claude_cfg)
        if session:
            session.add_turn(query=query, claude_response=content)
            session.save()
        if args.format == "json":
            print(json.dumps({"model": claude_cfg.model, "response": content, "reasoning": reasoning}, indent=2))
        elif args.format == "markdown":
            print(content)
        else:
            console.print(Panel(Markdown(content), title=f"[bold magenta]🎭 Claude ({claude_cfg.model})[/bold magenta]"))
    elif args.ai == "deepseek":
        ds_history = session.get_messages_for_deepseek(query) if session else None
        content, reasoning = ask_deepseek(query, trip_context, history_messages=ds_history, ds_cfg=ds_cfg)
        if session:
            session.add_turn(query=query, deepseek_response=content)
            session.save()
        if args.format == "json":
            print(json.dumps({"model": ds_cfg.model, "response": content, "reasoning": reasoning}, indent=2))
        elif args.format == "markdown":
            print(content)
        else:
            console.print(Panel(Markdown(content), title=f"[bold blue]🧠 DeepSeek ({ds_cfg.model})[/bold blue]"))
    else:  # Council
        results = ask_council(
            query=query,
            trip_context=trip_context,
            session=session,
            claude_cfg=claude_cfg,
            ds_cfg=ds_cfg,
            stream_progress=(args.format == "rich"),
        )
        if args.format == "json":
            print(json.dumps(results, indent=2))
        elif args.format == "markdown":
            print(format_council_markdown(results))
        else:
            display_council_results(results)


if __name__ == "__main__":
    main()
