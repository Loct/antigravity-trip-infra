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
Claude Wanderlog Trip Validator (Anthropic Claude & Multi-Provider Support)

Validates travel itineraries created in Wanderlog using Claude (e.g. Claude 3.7 Sonnet,
Claude 3.5 Sonnet, Claude 3.5 Haiku) with optional extended thinking reasoning trace.
Provides standalone audits and cross-checking capabilities alongside DeepSeek.

Checks for:
1. Schedule & Timing Feasibility (activity durations, opening hours, meal buffers)
2. Geographic Routing & Backtracking (neighborhood clusters, transit distance)
3. Lodging Continuity (uncovered nights, check-in/out logistics)
4. Transit & Flight Buffers (airport margins, connection realism)
5. Pacing & Workload Sanity (overloaded vs empty days)
6. Dining Notes Audit (single unified lunch & dinner note per day)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def load_env_file() -> None:
    """Load key-value pairs from .env in repository root if present."""
    repo_root = Path(__file__).resolve().parent.parent
    env_file = repo_root / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("\"'")
                if k not in os.environ and v:
                    os.environ[k] = v


load_env_file()


class ClaudeProviderConfig:
    """Configures the Claude LLM provider (Direct Anthropic API or OpenRouter)."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        thinking_budget: Optional[int] = None,
    ) -> None:
        self.provider = provider or os.getenv("CLAUDE_PROVIDER", "").lower()
        self.api_key = (
            api_key
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("CLAUDE_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
        )
        self.base_url = (
            base_url
            or os.getenv("ANTHROPIC_BASE_URL")
            or os.getenv("OPENROUTER_BASE_URL")
        )
        self.model = (
            model
            or os.getenv("ANTHROPIC_MODEL")
            or os.getenv("CLAUDE_MODEL")
        )

        # Thinking budget: defaults to 2048 if using thinking-capable model
        env_budget = os.getenv("ANTHROPIC_THINKING_BUDGET")
        if thinking_budget is not None:
            self.thinking_budget = thinking_budget
        elif env_budget and env_budget.isdigit():
            self.thinking_budget = int(env_budget)
        else:
            self.thinking_budget = 2048

        # Auto-detect provider
        if not self.provider:
            if self.api_key and self.api_key.startswith("sk-ant-"):
                self.provider = "anthropic"
            elif self.api_key and self.api_key.startswith("sk-or-"):
                self.provider = "openrouter"
            elif os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY"):
                self.provider = "anthropic"
            elif os.getenv("OPENROUTER_API_KEY"):
                self.provider = "openrouter"
            else:
                self.provider = "anthropic"  # Default

        # Provider defaults
        if self.provider == "anthropic":
            self.base_url = self.base_url or "https://api.anthropic.com"
            self.model = self.model or "claude-opus-5"
        elif self.provider == "openrouter":
            self.base_url = self.base_url or "https://openrouter.ai/api/v1"
            # Default to active Claude model on OpenRouter (claude-sonnet-4.5)
            if not self.model or self.model in ("anthropic/claude-3.7-sonnet", "claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022"):
                self.model = "anthropic/claude-sonnet-4.5"
            self.default_headers = {
                "HTTP-Referer": "https://wanderlog.com",
                "X-Title": "Antigravity Wanderlog Claude Trip Validator",
            }
        else:
            self.base_url = self.base_url or "https://api.anthropic.com"
            self.model = self.model or "claude-3-7-sonnet-20250219"

    def is_thinking_supported(self) -> bool:
        """Extended thinking is supported on Claude 3.7+ sonnet models."""
        if self.provider != "anthropic":
            return False
        model_lower = self.model.lower()
        return ("3-7" in model_lower or "3.7" in model_lower or "claude-3-7" in model_lower) and self.thinking_budget > 0

    def get_anthropic_client(self):
        import anthropic

        if not self.api_key:
            raise ValueError(
                "Missing Anthropic API key. "
                "Please set ANTHROPIC_API_KEY in .env or run './scripts/login_claude.sh'."
            )
        kwargs: Dict[str, Any] = {"api_key": self.api_key}
        if self.base_url and self.base_url != "https://api.anthropic.com":
            kwargs["base_url"] = self.base_url
        return anthropic.Anthropic(**kwargs)

    def get_openrouter_client(self):
        from openai import OpenAI

        if not self.api_key:
            raise ValueError(
                "Missing OpenRouter API key for Claude. "
                "Please set OPENROUTER_API_KEY in .env or run './scripts/login_claude.sh'."
            )
        return OpenAI(
            base_url=self.base_url or "https://openrouter.ai/api/v1",
            api_key=self.api_key,
            default_headers=getattr(self, "default_headers", None),
        )


def extract_trip_id(target: str) -> str:
    """Extract clean trip ID from URL or input string."""
    target = target.strip()
    match = re.search(r"wanderlog\.com/(?:view|plan)/([a-zA-Z0-9_-]+)", target)
    if match:
        return match.group(1)
    return target


def fetch_trip_data(target: str) -> Tuple[Dict[str, Any], str]:
    """
    Fetch trip JSON and Markdown representation using Wanderlog CLI or local file.
    Returns (trip_json, trip_markdown).
    """
    path = Path(target)
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            proc = subprocess.run(
                ["wanderlog", "trips", "show", "--file", str(path), "-o", "markdown", "--details"],
                capture_output=True,
                text=True,
                check=False,
            )
            md = proc.stdout if proc.returncode == 0 else ""
            return data, md
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read local file as JSON: {e}[/yellow]")

    trip_id = extract_trip_id(target)

    # 1. Fetch JSON details
    proc_json = subprocess.run(
        ["wanderlog", "trips", "show", trip_id, "-o", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc_json.returncode != 0:
        raise RuntimeError(
            f"Failed to fetch trip from Wanderlog (ID: {trip_id}): {proc_json.stderr.strip()}"
        )
    data = json.loads(proc_json.stdout)

    # 2. Fetch Markdown representation for comprehensive itinerary view
    proc_md = subprocess.run(
        ["wanderlog", "trips", "show", trip_id, "-o", "markdown", "--details"],
        capture_output=True,
        text=True,
        check=False,
    )
    md = proc_md.stdout if proc_md.returncode == 0 else ""

    return data, md


def summarize_trip_context(data: Dict[str, Any], md: str) -> str:
    """
    Assemble a structured, dense text summary of the trip specifically for LLM validation.
    Extracts lodging, flights, and day-by-day activities & notes.
    """
    tp = data.get("tripPlan", {}) if "tripPlan" in data else data.get("trip", {})
    if not tp and "title" in data:
        tp = data

    title = tp.get("title", "Untitled Trip")
    start_date = tp.get("startDate", "N/A")
    end_date = tp.get("endDate", "N/A")
    place_count = tp.get("placeCount", "N/A")

    lines = [
        f"# Trip Validation Target: {title}",
        f"- Dates: {start_date} to {end_date}",
        f"- Total Days: {tp.get('days', 'N/A')}",
        f"- Total Places Listed: {place_count}",
        "",
    ]

    itin = tp.get("itinerary", {})
    sections = itin.get("sections", [])

    # Lodging section
    lodging_lines = []
    for s in sections:
        if s.get("type") == "hotels":
            for b in s.get("blocks", []):
                p = b.get("place", {})
                lodging_lines.append(f"- {p.get('name')}: {p.get('formatted_address', '')}")
    if lodging_lines:
        lines.append("## Lodging / Accommodations:")
        lines.extend(lodging_lines)
        lines.append("")

    # Flights section
    flight_lines = []
    for s in sections:
        if s.get("type") == "flights":
            for b in s.get("blocks", []):
                finfo = b.get("flightInfo", {})
                carrier = finfo.get("airline", {}).get("iata", "")
                num = finfo.get("number", "")
                dep = b.get("depart", {})
                arr = b.get("arrive", {})
                flight_lines.append(
                    f"- Flight {carrier} {num}: {dep.get('airport', {}).get('name')} "
                    f"({dep.get('date')} {dep.get('time')}) -> "
                    f"{arr.get('airport', {}).get('name')} ({arr.get('date')} {arr.get('time')})"
                )
    if flight_lines:
        lines.append("## Flights & Long-Distance Transit:")
        lines.extend(flight_lines)
        lines.append("")

    # Daily itinerary
    lines.append("## Day-by-Day Itinerary & Scheduled Places:")
    day_idx = 0
    has_daily_sections = False
    for s in sections:
        date = s.get("date")
        if date:
            has_daily_sections = True
            day_idx += 1
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
                    lines.append(f"  - Place: {name} (Address: {addr}){note_str}")
                elif btype == "text":
                    text_ops = b.get("text", {}).get("ops", [])
                    note = "".join([op.get("insert", "") for op in text_ops if isinstance(op, dict)]).strip()
                    lines.append(f"  - Note: {note}")
            lines.append("")

    if md.strip():
        if not has_daily_sections:
            lines.append(md.strip())
        else:
            lines.append("## Additional Itinerary Markdown:")
            lines.append(md.strip())

    return "\n".join(lines)


VALIDATION_SYSTEM_PROMPT = """You are an elite Travel Itinerary Auditor and Logistical Analyst powered by Claude.
Your goal is to rigorously review and validate travel itineraries planned in Wanderlog to catch real-world mistakes, logistical friction, and schedule errors.

You MUST analyze the trip across the following 6 critical dimensions:

1. ⏱️ Schedule Feasibility & Timing:
   - Are daily activities realistic in duration?
   - Are typical opening/closing hours respected (e.g. museums commonly closed Mondays, night spots visited in the daytime, holiday closures like Tết New Year in Vietnam)?
   - Are meal breaks (lunch, dinner) accounted for with reasonable buffer times?
   - Are there overlapping or physically conflicting time slots?

2. 🗺️ Geographic Routing & Backtracking:
   - Are places visited on each day clustered by neighborhood / district?
   - Is there obvious zigzagging or excessive travel back and forth across the city or province?
   - Are intra-city travel times feasible?

3. 🏨 Lodging Continuity & Logistics:
   - Is there a booked accommodation for EVERY single night of the trip?
   - Check-in / check-out alignment: Are there luggage storage or awkward gap issues before check-in or after check-out?
   - Are the hotel locations convenient relative to the daily sightseeing hubs?

4. ✈️ Flights & Transit Coordination:
   - Airport arrival margins: At least 2 hours domestic, 3 hours international before flight departures.
   - Post-arrival buffer: Realistic time allowed to clear customs, retrieve baggage, and travel to hotel before starting activities.
   - Train/transit connections: Buffer for departures and transfers.

5. 🏃 Pacing & Sanity:
   - Is any day overloaded (e.g. 6+ major sights creating exhaustion)?
   - Is pacing balanced throughout the duration?

6. 🍽️ Dining Notes Audit (Single Unified Lunch & Dinner Note per day):
   - The user requires EXACTLY ONE unified note per day covering Lunch and Dinner recommendations.
   - Check every single day (Day 1 through the end of the trip).
   - Flag any days that are missing lunch and dinner notes.
   - Flag any days that have multiple conflicting or duplicate notes attached to different places.
   - Provide concrete, authentic restaurant recommendations for any day that is missing lunch or dinner.

OUTPUT FORMAT:
Your response MUST be organized cleanly in GitHub Markdown using this exact structure:

# 📋 Trip Audit Report: [Trip Name] (Claude Analysis)

## 🌟 Executive Summary
A concise paragraph summarizing the overall viability, strengths, and primary areas of concern.

## 🛑 Critical Issues (Must Fix)
Items that are physically, chronologically, or logistically impossible. If none, state "None detected."

## ⚠️ Warnings & Logistical Friction (Recommended Fixes)
Items that will cause severe stress, excessive transit time, or poor experience.

## 🍽️ Daily Dining Notes Audit (Lunch & Dinner per Day)
A complete Markdown table covering all days:
| Day | Date | Location / Theme | Dining Note Status | Lunch Recommendation | Dinner Recommendation |
Include notes on days that had duplicate dining notes or missing dining notes.

## 📅 Day-by-Day Route & Feasibility Audit
Thorough evaluation of every single day, checking geographic clustering, opening hours, holiday considerations, and flow.

## 💡 Concrete Proposed Fixes for Wanderlog
Specific adjustments to apply to Wanderlog (swapping places, updating notes, consolidating dining notes).

## ✅ Final Verdict
A concluding rating: [EXCELLENT | GOOD WITH MINOR TWEAKS | NEEDS RESTRUCTURING | CRITICAL ERRORS DETECTED]
"""


def run_claude_validation_anthropic(
    trip_summary: str,
    provider_cfg: ClaudeProviderConfig,
    stream: bool = True,
) -> Tuple[str, Optional[str]]:
    """Execute validation using official Anthropic API."""
    client = provider_cfg.get_anthropic_client()

    messages = [
        {
            "role": "user",
            "content": f"Please thoroughly audit and validate this Wanderlog itinerary:\n\n{trip_summary}",
        }
    ]

    use_thinking = provider_cfg.is_thinking_supported()
    max_tokens = max(provider_cfg.thinking_budget + 4000, 4096) if use_thinking else 4096

    create_kwargs: Dict[str, Any] = {
        "model": provider_cfg.model,
        "system": VALIDATION_SYSTEM_PROMPT,
        "messages": messages,
        "max_tokens": max_tokens,
    }

    if use_thinking:
        create_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": provider_cfg.thinking_budget,
        }
    else:
        model_lower = provider_cfg.model.lower()
        if "opus" in model_lower or "sonnet-5" in model_lower:
            create_kwargs["output_config"] = {"effort": "low"}

    console.print(
        f"[cyan]Connecting to [bold]Anthropic Claude[/bold] using model [bold green]{provider_cfg.model}[/bold green]"
        + (f" with [bold magenta]{provider_cfg.thinking_budget}[/bold magenta] thinking tokens" if use_thinking else "")
        + "...[/cyan]"
    )

    reasoning_accum: List[str] = []
    content_accum: List[str] = []

    try:
        if stream:
            with console.status("[bold green]Claude is analyzing the itinerary...[/bold green]", spinner="dots"):
                pass

            console.print("\n[bold cyan]─── Claude Validation Report ───[/bold cyan]\n")
            in_thinking = False

            with client.messages.stream(**create_kwargs) as message_stream:
                for event in message_stream:
                    event_type = getattr(event, "type", "")
                    if event_type == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if not delta:
                            continue
                        delta_type = getattr(delta, "type", "")

                        if delta_type == "thinking_delta":
                            thinking_chunk = getattr(delta, "thinking", "")
                            if thinking_chunk:
                                if not in_thinking:
                                    console.print("[dim italic]Reasoning Thought Process (Claude Extended Thinking):[/dim italic]")
                                    in_thinking = True
                                sys.stdout.write(thinking_chunk)
                                sys.stdout.flush()
                                reasoning_accum.append(thinking_chunk)

                        elif delta_type == "text_delta":
                            text_chunk = getattr(delta, "text", "")
                            if text_chunk:
                                if in_thinking:
                                    console.print("\n\n[bold cyan]─── Report ───[/bold cyan]\n")
                                    in_thinking = False
                                sys.stdout.write(text_chunk)
                                sys.stdout.flush()
                                content_accum.append(text_chunk)

            console.print("\n")
            full_content = "".join(content_accum)
            full_reasoning = "".join(reasoning_accum) if reasoning_accum else None
            return full_content, full_reasoning
        else:
            response = client.messages.create(**create_kwargs)
            for block in getattr(response, "content", []):
                b_type = getattr(block, "type", "")
                if b_type == "thinking":
                    reasoning_accum.append(getattr(block, "thinking", ""))
                elif b_type == "text":
                    content_accum.append(getattr(block, "text", ""))

            full_content = "".join(content_accum)
            full_reasoning = "".join(reasoning_accum) if reasoning_accum else None
            return full_content, full_reasoning

    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "authentication" in error_msg.lower():
            raise RuntimeError(
                "Anthropic Authentication failed (401). "
                "Please verify your key in .env (ANTHROPIC_API_KEY=sk-ant-...) or run './scripts/login_claude.sh'."
            ) from e
        raise e


def run_claude_validation_openrouter(
    trip_summary: str,
    provider_cfg: ClaudeProviderConfig,
    stream: bool = True,
) -> Tuple[str, Optional[str]]:
    """Execute validation using OpenRouter API with a Claude model."""
    client = provider_cfg.get_openrouter_client()

    messages = [
        {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Please thoroughly audit and validate this Wanderlog itinerary:\n\n{trip_summary}",
        },
    ]

    console.print(
        f"[cyan]Connecting to [bold]OpenRouter[/bold] using model [bold green]{provider_cfg.model}[/bold green]...[/cyan]"
    )

    reasoning_accum: List[str] = []
    content_accum: List[str] = []

    try:
        response = client.chat.completions.create(
            model=provider_cfg.model,
            messages=messages,
            stream=stream,
            temperature=0.3,
            max_tokens=4000,
        )

        if stream:
            with console.status("[bold green]Claude is analyzing the itinerary via OpenRouter...[/bold green]", spinner="dots"):
                pass

            console.print("\n[bold cyan]─── Claude Validation Report ───[/bold cyan]\n")
            for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                reasoning = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None)
                if reasoning:
                    reasoning_accum.append(reasoning)

                content = delta.content
                if content:
                    sys.stdout.write(content)
                    sys.stdout.flush()
                    content_accum.append(content)

            console.print("\n")
            full_content = "".join(content_accum)
            full_reasoning = "".join(reasoning_accum) if reasoning_accum else None
            return full_content, full_reasoning
        else:
            choice = response.choices[0]
            content = choice.message.content or ""
            reasoning = getattr(choice.message, "reasoning", None) or getattr(choice.message, "reasoning_content", None)
            return content, reasoning

    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg:
            raise RuntimeError(
                "OpenRouter Authentication failed (401). Please check OPENROUTER_API_KEY in .env."
            ) from e
        raise e


def run_claude_validation(
    trip_summary: str,
    provider_cfg: ClaudeProviderConfig,
    stream: bool = True,
) -> Tuple[str, Optional[str]]:
    """Route validation to configured provider (Anthropic direct or OpenRouter)."""
    if provider_cfg.provider == "openrouter":
        return run_claude_validation_openrouter(trip_summary, provider_cfg, stream=stream)
    return run_claude_validation_anthropic(trip_summary, provider_cfg, stream=stream)


def verify_connection(provider_cfg: ClaudeProviderConfig) -> bool:
    """Test connection with a quick probe."""
    try:
        console.print(
            f"Testing connection to [bold]{provider_cfg.provider}[/bold] ({provider_cfg.model})..."
        )
        if provider_cfg.provider == "openrouter":
            client = provider_cfg.get_openrouter_client()
            resp = client.chat.completions.create(
                model=provider_cfg.model,
                messages=[{"role": "user", "content": "Respond with 'VALIDATOR_READY' if you can read this."}],
                max_tokens=20,
            )
            content = resp.choices[0].message.content or ""
        else:
            client = provider_cfg.get_anthropic_client()
            resp = client.messages.create(
                model=provider_cfg.model,
                messages=[{"role": "user", "content": "Respond with 'VALIDATOR_READY' if you can read this."}],
                max_tokens=600,
            )
            content = "".join(b.text for b in getattr(resp, "content", []) if getattr(b, "type", "") == "text")

        console.print(f"[green]✓ Success! Response received:[/green] {content.strip()}")
        return True
    except Exception as e:
        console.print(f"[red]✗ Connection failed: {e}[/red]")
        return False


def list_wanderlog_trips() -> None:
    """List available trips via wanderlog CLI."""
    try:
        subprocess.run(["wanderlog", "trips", "list"], check=False)
    except Exception as e:
        console.print(f"[red]Error listing trips: {e}[/red]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Claude Wanderlog Trip Validator (Anthropic Claude & Multi-Provider)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "trip",
        nargs="?",
        help="Trip ID, Wanderlog URL, or local JSON file (e.g. trips/southern_italy.json)",
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openrouter"],
        help="LLM provider (default: anthropic)",
    )
    parser.add_argument(
        "--model",
        help="Model identifier (default: claude-3-7-sonnet-20250219 or ANTHROPIC_MODEL)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Fast check mode (uses claude-3-5-haiku-20241022 with thinking disabled)",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        metavar="TOKENS",
        help="Extended thinking token budget for Claude 3.7+ (default: 2048, 0 to disable)",
    )
    parser.add_argument(
        "--format",
        choices=["rich", "markdown", "json"],
        default="rich",
        help="Output display format (default: rich)",
    )
    parser.add_argument(
        "--save-report",
        metavar="PATH",
        help="Save generated Markdown report to specified file path",
    )
    parser.add_argument(
        "--cross-check",
        action="store_true",
        help="Cross-check this itinerary with DeepSeek as well to compare findings",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run a connectivity test to the configured Claude provider",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available Wanderlog trips",
    )

    args = parser.parse_args()

    if args.list:
        list_wanderlog_trips()
        return

    # Handle cross-check request
    if args.cross_check and args.trip:
        cross_check_script = Path(__file__).parent / "cross_check_validator.py"
        cmd = [
            "uv",
            "run",
            str(cross_check_script),
            args.trip,
            "--format",
            args.format,
        ]
        if args.save_report:
            cmd.extend(["--save-report", args.save_report])
        if args.quick:
            cmd.append("--quick")
        subprocess.run(cmd, check=False)
        return

    model_override = args.model
    thinking_budget_override = args.thinking_budget

    if args.quick and not model_override:
        if args.provider == "openrouter":
            model_override = "anthropic/claude-3.5-haiku"
        else:
            model_override = "claude-3-5-haiku-20241022"
        thinking_budget_override = 0

    provider_cfg = ClaudeProviderConfig(
        provider=args.provider,
        model=model_override,
        thinking_budget=thinking_budget_override,
    )

    if args.test:
        success = verify_connection(provider_cfg)
        sys.exit(0 if success else 1)

    if not args.trip:
        console.print(
            Panel(
                "[bold cyan]Claude Wanderlog Itinerary Validator[/bold cyan]\n\n"
                "Audit your Wanderlog trips for schedule conflicts, geographic backtracking,\n"
                "missing hotel nights, and flight buffers using Anthropic Claude.\n\n"
                "[bold]Usage:[/bold]\n"
                "  uv run scripts/claude_validator.py <trip_id_or_file> [options]\n\n"
                "[bold]Examples:[/bold]\n"
                "  uv run scripts/claude_validator.py trips/southern_italy.json\n"
                "  uv run scripts/claude_validator.py abc123xyz --quick\n"
                "  uv run scripts/claude_validator.py abc123xyz --cross-check\n"
                "  uv run scripts/claude_validator.py --test\n"
                "  uv run scripts/claude_validator.py --list\n\n"
                "To configure your Anthropic Claude API key, run:\n"
                "  [green]./scripts/login_claude.sh[/green]",
                title="Wanderlog + Claude",
            )
        )
        sys.exit(0)

    # 1. Fetch trip data
    console.print(f"[cyan]Fetching itinerary data for: [bold]{args.trip}[/bold]...[/cyan]")
    trip_json, trip_md = fetch_trip_data(args.trip)

    # 2. Prepare structured summary
    trip_summary = summarize_trip_context(trip_json, trip_md)

    # 3. Run validation
    report_text, reasoning = run_claude_validation(
        trip_summary, provider_cfg, stream=(args.format == "rich")
    )

    # 4. Output formatting
    if args.format == "markdown":
        print(report_text)
    elif args.format == "json":
        output_payload = {
            "trip": args.trip,
            "provider": provider_cfg.provider,
            "model": provider_cfg.model,
            "reasoning": reasoning,
            "report": report_text,
        }
        print(json.dumps(output_payload, indent=2))

    # 5. Save report if requested
    if args.save_report:
        save_path = Path(args.save_report)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            if reasoning:
                f.write(f"<!-- Claude Thinking Trace:\n{reasoning}\n-->\n\n")
            f.write(report_text)
        console.print(f"[green]✓ Audit report saved to {save_path}[/green]")


if __name__ == "__main__":
    main()
