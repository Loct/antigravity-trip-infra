#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.27.0",
#     "rich>=13.0.0",
#     "openai>=1.0.0",
# ]
# ///
"""
DeepSeek Wanderlog Trip Validator (Free OpenRouter / Multi-Provider Support)

Validates travel itineraries created in Wanderlog using DeepSeek (DeepSeek-R1 or DeepSeek-Chat)
via free OpenRouter tier or custom OpenAI-compatible endpoints.

Checks for:
1. Schedule & Timing Feasibility (activity durations, opening hours, meal buffers)
2. Geographic Routing & Backtracking (neighborhood clusters, transit distance)
3. Lodging Continuity (uncovered nights, check-in/out logistics)
4. Transit & Flight Buffers (airport margins, connection realism)
5. Pacing & Workload Sanity (overloaded vs empty days)
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
from openai import OpenAI
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


class ProviderConfig:
    """Configures the LLM provider (OpenRouter Free, DeepSeek direct, Groq, Ollama)."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.provider = provider or os.getenv("DEEPSEEK_PROVIDER", "").lower()
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("GROQ_API_KEY")
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL")
        self.model = model or os.getenv("OPENROUTER_MODEL") or os.getenv("DEEPSEEK_MODEL")

        # Auto-detect provider if not explicitly passed
        if not self.provider:
            if os.getenv("OPENROUTER_API_KEY") or (self.api_key and self.api_key.startswith("sk-or-")):
                self.provider = "openrouter"
            elif os.getenv("GROQ_API_KEY") or (self.api_key and self.api_key.startswith("gsk_")):
                self.provider = "groq"
            elif os.getenv("OLLAMA_BASE_URL"):
                self.provider = "ollama"
            elif os.getenv("DEEPSEEK_API_KEY"):
                self.provider = "deepseek"
            else:
                self.provider = "openrouter"  # Default to OpenRouter free

        # Provider defaults
        if self.provider == "openrouter":
            self.base_url = self.base_url or "https://openrouter.ai/api/v1"
            self.model = self.model or "deepseek/deepseek-r1:free"
            self.default_headers = {
                "HTTP-Referer": "https://wanderlog.com",
                "X-Title": "Antigravity Wanderlog Trip Validator",
            }
        elif self.provider == "deepseek":
            self.base_url = self.base_url or "https://api.deepseek.com"
            self.model = self.model or "deepseek-reasoner"
            self.default_headers = {}
        elif self.provider == "groq":
            self.base_url = self.base_url or "https://api.groq.com/openai/v1"
            self.model = self.model or "deepseek-r1-distill-llama-70b"
            self.default_headers = {}
        elif self.provider == "ollama":
            self.base_url = self.base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            self.model = self.model or "deepseek-r1:latest"
            self.api_key = self.api_key or "ollama"
            self.default_headers = {}
        else:
            self.base_url = self.base_url or "https://openrouter.ai/api/v1"
            self.model = self.model or "deepseek/deepseek-r1:free"
            self.default_headers = {}

    def get_client(self) -> OpenAI:
        if not self.api_key and self.provider != "ollama":
            raise ValueError(
                f"Missing API key for provider '{self.provider}'. "
                f"Please set OPENROUTER_API_KEY or run './scripts/login_deepseek.sh'."
            )
        return OpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "no-key",
            default_headers=self.default_headers if hasattr(self, "default_headers") else None,
        )


def extract_trip_id(target: str) -> str:
    """Extract clean trip ID from URL or input string."""
    target = target.strip()
    # If URL: https://wanderlog.com/view/TRIP_ID/... or https://wanderlog.com/plan/TRIP_ID/...
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
            # Generate markdown via wanderlog trips show --file <path> -o markdown --details
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
    """
    tp = data.get("tripPlan", {}) if "tripPlan" in data else data.get("trip", {})
    if not tp and "title" in data:
        tp = data

    title = tp.get("title", "Untitled Trip")
    start_date = tp.get("startDate", "N/A")
    end_date = tp.get("endDate", "N/A")
    place_count = tp.get("placeCount", "N/A")

    summary_lines = [
        f"# Trip Validation Target: {title}",
        f"- Dates: {start_date} to {end_date}",
        f"- Total Places Listed: {place_count}",
        "",
        "## Itinerary & Booking Details:",
    ]

    if md.strip():
        summary_lines.append(md.strip())
    else:
        # Fallback to serializing tripPlan keys if markdown was unavailable
        summary_lines.append(json.dumps(tp, indent=2))

    return "\n".join(summary_lines)


VALIDATION_SYSTEM_PROMPT = """You are an elite Travel Itinerary Auditor and Logistical Analyst.
Your goal is to rigorously review and validate travel itineraries planned in Wanderlog to catch real-world mistakes, logistical friction, and schedule errors.

You MUST analyze the trip across the following 5 critical dimensions:

1. ⏱️ Schedule Feasibility & Timing:
   - Are daily activities realistic in duration?
   - Are typical opening/closing hours respected (e.g. museums commonly closed Mondays, night spots visited in the daytime)?
   - Are meal breaks (lunch, dinner) accounted for with reasonable buffer times?
   - Are there overlapping or physically conflicting time slots?

2. 🗺️ Geographic Routing & Backtracking:
   - Are places visited on each day clustered by neighborhood / district?
   - Is there obvious zigzagging or excessive travel back and forth across the city?
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
   - Is any day overloaded (e.g. 8+ major sights creating exhaustion)?
   - Is pacing balanced throughout the duration?

OUTPUT FORMAT:
Your response MUST be organized cleanly in GitHub Markdown using this exact structure:

# 📋 Trip Audit Report: [Trip Name]

## 🌟 Executive Summary
A concise paragraph summarizing the overall viability, strengths, and primary areas of concern.

## 🛑 Critical Issues (Must Fix)
Items that are physically, chronologically, or logistically impossible (e.g. missing hotel night, missed flight buffer, museum visit when closed). If none, state "None detected."

## ⚠️ Warnings & Logistical Friction (Recommended Fixes)
Items that will cause severe stress, excessive transit time, or poor experience (e.g. geographic backtracking, rushed meals, tight connection buffers).

## 💡 Suggestions & Route Optimizations
Concrete ideas to improve the flow, group places by district, or add smart local alternatives.

## 📅 Day-by-Day Audit Highlights
Brief breakdown of any specific day that needs attention, highlighting:
- **Day X (Date)**: [Issue & Recommended Adjustment]

## ✅ Final Verdict
A concluding rating: [EXCELLENT | GOOD WITH MINOR TWEAKS | NEEDS RESTRUCTURING | CRITICAL ERRORS DETECTED]
"""


def run_validation(
    trip_summary: str,
    provider_cfg: ProviderConfig,
    stream: bool = True,
) -> Tuple[str, Optional[str]]:
    """
    Call DeepSeek model via OpenAI-compatible endpoint.
    Returns (report_text, reasoning_trace).
    """
    client = provider_cfg.get_client()

    messages = [
        {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Please thoroughly audit and validate this Wanderlog itinerary:\n\n{trip_summary}",
        },
    ]

    console.print(
        f"[cyan]Connecting to [bold]{provider_cfg.provider}[/bold] using model [bold green]{provider_cfg.model}[/bold green]...[/cyan]"
    )

    reasoning_accum = []
    content_accum = []

    try:
        response = client.chat.completions.create(
            model=provider_cfg.model,
            messages=messages,
            stream=stream,
            temperature=0.3,
        )

        if stream:
            with console.status("[bold green]DeepSeek is analyzing the itinerary...[/bold green]", spinner="dots"):
                pass

            console.print("\n[bold cyan]─── DeepSeek Validation Report ───[/bold cyan]\n")
            in_reasoning = False

            for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                # OpenRouter / DeepSeek reasoning chunks
                reasoning = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None)
                if reasoning:
                    if not in_reasoning:
                        console.print("[dim italic]Reasoning Thought Process:[/dim italic]")
                        in_reasoning = True
                    sys.stdout.write(reasoning)
                    sys.stdout.flush()
                    reasoning_accum.append(reasoning)

                content = delta.content
                if content:
                    if in_reasoning:
                        console.print("\n\n[bold cyan]─── Report ───[/bold cyan]\n")
                        in_reasoning = False
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
                f"Authentication failed (401). Please check your API key for {provider_cfg.provider} "
                f"or run './scripts/login_deepseek.sh'."
            ) from e
        elif "rate limit" in error_msg.lower() or "429" in error_msg:
            if provider_cfg.model == "deepseek/deepseek-r1:free":
                console.print(
                    "[yellow]Notice: 'deepseek/deepseek-r1:free' hit a rate limit. Falling back to 'deepseek/deepseek-chat:free'...[/yellow]"
                )
                provider_cfg.model = "deepseek/deepseek-chat:free"
                return run_validation(trip_summary, provider_cfg, stream=stream)
        raise e


def verify_connection(provider_cfg: ProviderConfig) -> bool:
    """Test connection with a quick query."""
    try:
        console.print(
            f"Testing connection to [bold]{provider_cfg.provider}[/bold] ({provider_cfg.model})..."
        )
        client = provider_cfg.get_client()
        resp = client.chat.completions.create(
            model=provider_cfg.model,
            messages=[{"role": "user", "content": "Respond with 'VALIDATOR_READY' if you can read this."}],
            max_tokens=20,
        )
        content = resp.choices[0].message.content or ""
        console.print(f"[green]✓ Success! Response received:[/green] {content.strip()}")
        return True
    except Exception as e:
        console.print(f"[red]✗ Connection failed: {e}[/red]")
        return False


def list_wanderlog_trips() -> None:
    """List available trips via wanderlog CLI."""
    try:
        proc = subprocess.run(["wanderlog", "trips", "list"], check=False)
    except Exception as e:
        console.print(f"[red]Error listing trips: {e}[/red]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DeepSeek Wanderlog Trip Validator (Free OpenRouter & Multi-Provider)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "trip",
        nargs="?",
        help="Trip ID, Wanderlog URL, or local JSON file (e.g. trips/southern_italy.json)",
    )
    parser.add_argument(
        "--provider",
        choices=["openrouter", "deepseek", "groq", "ollama"],
        help="LLM provider (default: openrouter for free DeepSeek-R1)",
    )
    parser.add_argument(
        "--model",
        help="Model identifier (default: deepseek/deepseek-r1:free on OpenRouter, or deepseek-reasoner)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use deepseek-chat instead of deepseek-r1 for faster turnaround",
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
        "--test",
        action="store_true",
        help="Run a connectivity test to the configured provider",
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

    model_override = args.model
    if args.quick and not model_override:
        if args.provider == "deepseek":
            model_override = "deepseek-chat"
        else:
            model_override = "deepseek/deepseek-chat:free"

    provider_cfg = ProviderConfig(provider=args.provider, model=model_override)

    if args.test:
        success = verify_connection(provider_cfg)
        sys.exit(0 if success else 1)

    if not args.trip:
        console.print(
            Panel(
                "[bold cyan]DeepSeek Wanderlog Itinerary Validator[/bold cyan]\n\n"
                "Double-check your Wanderlog trips for schedule conflicts, geographic backtracking,\n"
                "missing hotel nights, and flight buffers using free DeepSeek.\n\n"
                "[bold]Usage:[/bold]\n"
                "  uv run scripts/deepseek_validator.py <trip_id_or_file> [options]\n\n"
                "[bold]Examples:[/bold]\n"
                "  uv run scripts/deepseek_validator.py trips/southern_italy.json\n"
                "  uv run scripts/deepseek_validator.py abc123xyz --quick\n"
                "  uv run scripts/deepseek_validator.py --test\n"
                "  uv run scripts/deepseek_validator.py --list\n\n"
                "To configure your free OpenRouter API key, run:\n"
                "  [green]./scripts/login_deepseek.sh[/green]",
                title="Wanderlog + DeepSeek",
            )
        )
        sys.exit(0)

    # 1. Fetch trip data
    console.print(f"[cyan]Fetching itinerary data for: [bold]{args.trip}[/bold]...[/cyan]")
    trip_json, trip_md = fetch_trip_data(args.trip)

    # 2. Prepare structured summary
    trip_summary = summarize_trip_context(trip_json, trip_md)

    # 3. Run validation
    report_text, reasoning = run_validation(
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
                f.write(f"<!-- DeepSeek Reasoning Trace:\n{reasoning}\n-->\n\n")
            f.write(report_text)
        console.print(f"[green]✓ Audit report saved to {save_path}[/green]")


if __name__ == "__main__":
    main()
