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
Conversational AI Travel Council (Multi-AI Co-Planning & Double Checking)

Allows Antigravity and the user to conversationally query multiple external AIs
(Anthropic Claude, DeepSeek, Groq, OpenRouter) to double-check travel itineraries,
debate route alternatives, verify daily pacing, and brainstorm local gems.

Modes:
1. Targeted query: Ask Claude, DeepSeek, or both a specific question about a trip or day.
2. Council mode: Queries both Claude and DeepSeek, presenting their viewpoints and consensus.
3. Interactive chat: Live terminal discussion with the AI travel advisors.
4. Full Audit: Conversational comprehensive audit across 6 logistical dimensions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
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

COUNCIL_SYSTEM_PROMPT = """You are an expert travel co-planner and logistical advisor on an AI Travel Council, collaborating with the user and lead planner Antigravity.
You have access to the user's Wanderlog travel itinerary.

Your role is to:
1. Provide sharp, realistic, and honest feedback on the user's question or travel plan.
2. Flag logistical traps: unreasonable transit times, geographic backtracking, opening hour traps (e.g., museums closed Mondays, holiday closures), airport check-in margins, and hotel continuity.
3. If asked about dining, evaluate recommendations for authentic local cuisine with balanced lunch/dinner flow.
4. Keep your answer conversational, direct, and actionable—avoid fluff.
5. If suggesting fixes, give specific place names, districts, or suggested time windows.
"""


def filter_trip_context(
    data: Dict[str, Any],
    md: str,
    target_days: Optional[List[int]] = None,
) -> str:
    """
    Extract structured context from trip data.
    If target_days is provided (e.g. [3, 4]), extracts only those specific days
    along with global flight and lodging context.
    """
    tp = data.get("tripPlan", {}) if "tripPlan" in data else data.get("trip", {})
    if not tp and "title" in data:
        tp = data

    title = tp.get("title", "Untitled Trip")
    start_date = tp.get("startDate", "N/A")
    end_date = tp.get("endDate", "N/A")
    place_count = tp.get("placeCount", "N/A")

    day_filter_str = f" (Focus: Day(s) {', '.join(map(str, target_days))})" if target_days else ""
    lines = [
        f"# Trip Context: {title}{day_filter_str}",
        f"- Dates: {start_date} to {end_date}",
        f"- Total Days: {tp.get('days', 'N/A')}",
        f"- Total Places Listed: {place_count}",
        "",
    ]

    itin = tp.get("itinerary", {})
    sections = itin.get("sections", [])

    # Lodging
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

    # Flights
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
                    lines.append(f"  - Place: {name} (Address: {addr}){note_str}")
                elif btype == "text":
                    text_ops = b.get("text", {}).get("ops", [])
                    note = "".join([op.get("insert", "") for op in text_ops if isinstance(op, dict)]).strip()
                    lines.append(f"  - Note: {note}")
            lines.append("")

    if md.strip() and not matched_any_day:
        lines.append("## Additional Itinerary Details:")
        lines.append(md.strip())

    return "\n".join(lines)


def ask_claude(
    query: str,
    trip_context: str,
    claude_cfg: Optional[claude_validator.ClaudeProviderConfig] = None,
    stream: bool = False,
) -> Tuple[str, Optional[str]]:
    """Query Claude with a conversational travel question."""
    cfg = claude_cfg or claude_validator.ClaudeProviderConfig()
    prompt = f"Itinerary Context:\n{trip_context}\n\nUser Question / Task:\n{query}"

    if cfg.provider == "openrouter":
        client = cfg.get_openrouter_client()
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=[
                {"role": "system", "content": COUNCIL_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=2500,
        )
        content = resp.choices[0].message.content or ""
        reasoning = getattr(resp.choices[0].message, "reasoning", None)
        return content, reasoning
    else:
        client = cfg.get_anthropic_client()
        use_thinking = cfg.is_thinking_supported()
        create_kwargs: Dict[str, Any] = {
            "model": cfg.model,
            "system": COUNCIL_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
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
    ds_cfg: Optional[deepseek_validator.ProviderConfig] = None,
    stream: bool = False,
) -> Tuple[str, Optional[str]]:
    """Query DeepSeek with a conversational travel question."""
    cfg = ds_cfg or deepseek_validator.ProviderConfig()
    prompt = f"Itinerary Context:\n{trip_context}\n\nUser Question / Task:\n{query}"

    client = cfg.get_client()
    resp = client.chat.completions.create(
        model=cfg.model,
        messages=[
            {"role": "system", "content": COUNCIL_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
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
    claude_cfg: Optional[claude_validator.ClaudeProviderConfig] = None,
    ds_cfg: Optional[deepseek_validator.ProviderConfig] = None,
    stream_progress: bool = True,
) -> Dict[str, Any]:
    """
    Query both Claude and DeepSeek and return a structured multi-AI synthesis.
    """
    c_cfg = claude_cfg or claude_validator.ClaudeProviderConfig()
    d_cfg = ds_cfg or deepseek_validator.ProviderConfig()

    results: Dict[str, Any] = {
        "query": query,
        "models": {
            "claude": c_cfg.model,
            "deepseek": d_cfg.model,
        },
        "claude": {"response": "", "reasoning": None, "available": True},
        "deepseek": {"response": "", "reasoning": None, "available": True},
    }

    # Query Claude
    try:
        if stream_progress:
            with console.status(f"[bold magenta]Consulting Claude ({c_cfg.model})...[/bold magenta]", spinner="dots"):
                c_resp, c_reason = ask_claude(query, trip_context, c_cfg)
        else:
            c_resp, c_reason = ask_claude(query, trip_context, c_cfg)
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
                d_resp, d_reason = ask_deepseek(query, trip_context, d_cfg)
        else:
            d_resp, d_reason = ask_deepseek(query, trip_context, d_cfg)
        results["deepseek"]["response"] = d_resp
        results["deepseek"]["reasoning"] = d_reason
    except Exception as e:
        results["deepseek"]["available"] = False
        results["deepseek"]["error"] = str(e)
        if stream_progress:
            console.print(f"[yellow]DeepSeek consultation skipped: {e}[/yellow]")

    return results


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


def run_interactive_council(
    trip_target: str,
    claude_cfg: claude_validator.ClaudeProviderConfig,
    ds_cfg: deepseek_validator.ProviderConfig,
) -> None:
    """Live interactive chat session with the AI Council."""
    console.print(f"[cyan]Loading itinerary data for [bold]{trip_target}[/bold]...[/cyan]")
    data, md = claude_validator.fetch_trip_data(trip_target)
    trip_context = filter_trip_context(data, md)

    console.print(
        Panel(
            "[bold cyan]Interactive AI Travel Council[/bold cyan]\n\n"
            "Ask questions, debate route choices, and get second opinions in real time.\n"
            "Commands:\n"
            "  • Type your question and press Enter\n"
            "  • Prefix with [magenta]'claude:'[/magenta] to ask only Claude\n"
            "  • Prefix with [blue]'deepseek:'[/blue] to ask only DeepSeek\n"
            "  • Type [green]'exit'[/green] or [green]'quit'[/green] to finish\n",
            title="🏛️ Travel Council Chat",
            border_style="cyan",
        )
    )

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]Ask Council[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input or user_input.lower() in ["exit", "quit", "q"]:
            console.print("[dim]Exiting Travel Council chat.[/dim]")
            break

        # Check for single-agent directive
        lower = user_input.lower()
        if lower.startswith("claude:"):
            q = user_input[7:].strip()
            with console.status("[bold magenta]Claude thinking...[/bold magenta]", spinner="dots"):
                ans, _ = ask_claude(q, trip_context, claude_cfg)
            console.print(Panel(Markdown(ans), title="🎭 Claude", border_style="magenta"))
        elif lower.startswith("deepseek:"):
            q = user_input[9:].strip()
            with console.status("[bold blue]DeepSeek thinking...[/bold blue]", spinner="dots"):
                ans, _ = ask_deepseek(q, trip_context, ds_cfg)
            console.print(Panel(Markdown(ans), title="🧠 DeepSeek", border_style="blue"))
        else:
            results = ask_council(user_input, trip_context, claude_cfg, ds_cfg)
            display_council_results(results)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Conversational AI Travel Council (Multi-AI Co-Planning & Double Checking)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Question or prompt to ask the travel council (e.g. 'Is Day 3 too rushed?')",
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
        "--ai",
        choices=["council", "claude", "deepseek"],
        default="council",
        help="Which AI advisor to query (default: council queries both Claude & DeepSeek)",
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
        help="Launch an interactive chat session with the AI council",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Perform a full conversational multi-AI itinerary audit",
    )

    args = parser.parse_args()

    claude_cfg = claude_validator.ClaudeProviderConfig(model=args.claude_model)
    ds_cfg = deepseek_validator.ProviderConfig(model=args.deepseek_model)

    if args.interactive:
        if not args.trip:
            console.print("[red]Error: --trip <id_or_file> is required for interactive mode.[/red]")
            sys.exit(1)
        run_interactive_council(args.trip, claude_cfg, ds_cfg)
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

    # Trip context resolution
    trip_target = args.trip
    trip_context = ""
    if trip_target:
        trip_data, trip_md = claude_validator.fetch_trip_data(trip_target)
        trip_context = filter_trip_context(trip_data, trip_md, target_days=target_days)

    query = args.query
    if args.audit and not query:
        query = (
            "Please perform a complete logistical double-check on this itinerary. "
            "Highlight any schedule conflicts, backtracking, missing hotel nights, or dining issues."
        )

    if not query:
        console.print(
            Panel(
                "[bold cyan]🏛️ Conversational AI Travel Council[/bold cyan]\n\n"
                "Double-check Wanderlog plans by conversationally consulting multiple AIs.\n\n"
                "[bold]Usage:[/bold]\n"
                "  uv run scripts/ai_council.py \"<question>\" --trip <id_or_file> [options]\n\n"
                "[bold]Examples:[/bold]\n"
                "  uv run scripts/ai_council.py \"Is Day 4 schedule too packed?\" --trip trips/vietnam.json\n"
                "  uv run scripts/ai_council.py \"Suggest authentic dinner near Senso-ji\" --trip abc123xyz --day 2\n"
                "  uv run scripts/ai_council.py \"Check transit between Rome and Florence\" --ai claude --trip trips/southern_italy.json\n"
                "  uv run scripts/ai_council.py --trip trips/vietnam.json --interactive\n"
                "  uv run scripts/ai_council.py --trip trips/vietnam.json --audit\n\n"
                "To configure keys:\n"
                "  Claude:   [green]./scripts/login_claude.sh[/green]\n"
                "  DeepSeek: [green]./scripts/login_deepseek.sh[/green]",
                title="AI Travel Council",
            )
        )
        sys.exit(0)

    # Execute consultation based on chosen AI
    if args.ai == "claude":
        content, reasoning = ask_claude(query, trip_context, claude_cfg)
        if args.format == "json":
            print(json.dumps({"model": claude_cfg.model, "response": content, "reasoning": reasoning}, indent=2))
        elif args.format == "markdown":
            print(content)
        else:
            console.print(Panel(Markdown(content), title=f"[bold magenta]🎭 Claude ({claude_cfg.model})[/bold magenta]"))
    elif args.ai == "deepseek":
        content, reasoning = ask_deepseek(query, trip_context, ds_cfg)
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
