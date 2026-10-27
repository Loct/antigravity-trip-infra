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
Wanderlog Multi-Model Itinerary Cross-Check Validator
Dual AI verification combining Anthropic Claude + DeepSeek

Cross-checks travel itineraries against both LLMs simultaneously to detect:
- Consensus issues: High-confidence schedule, lodging, transit, or dining errors flagged by BOTH models.
- Model-specific insights: Unique nuances caught by Claude or DeepSeek individually.
- Prioritized action plan for Wanderlog.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import claude_validator
import deepseek_validator

console = Console()


def extract_section_content(text: str, heading_pattern: str) -> str:
    """Extract content under a specific markdown heading until the next heading of same or higher level."""
    pattern = rf"(?:^|\n)##\s+.*?{heading_pattern}.*?\n(.*?)(?=\n##\s+|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def extract_verdict(text: str) -> str:
    """Extract the final verdict string."""
    # Look for known standard verdicts first across the document or under Final Verdict
    for v in [
        "CRITICAL ERRORS DETECTED",
        "NEEDS RESTRUCTURING",
        "GOOD WITH MINOR TWEAKS",
        "EXCELLENT",
    ]:
        if re.search(rf"(?:Final Verdict|Rating).*?{re.escape(v)}", text, re.IGNORECASE | re.DOTALL):
            return v

    # Fallback to checking full text
    for v in [
        "CRITICAL ERRORS DETECTED",
        "NEEDS RESTRUCTURING",
        "GOOD WITH MINOR TWEAKS",
        "EXCELLENT",
    ]:
        if v in text.upper():
            return v

    # Fallback to line after Final Verdict
    match = re.search(r"Final Verdict[:\s*]*\n*([^\n#]+)", text, re.IGNORECASE)
    if match:
        val = match.group(1).strip("[]* \r\n")
        if val:
            return val
    return "ANALYZED"


def synthesize_cross_check_report(
    trip_target: str,
    trip_title: str,
    ds_report: str,
    claude_report: str,
    ds_model: str,
    claude_model: str,
) -> str:
    """
    Synthesize dual reports into a unified cross-check document with consensus matrix.
    """
    ds_verdict = extract_verdict(ds_report)
    claude_verdict = extract_verdict(claude_report)

    ds_critical = extract_section_content(ds_report, "Critical Issues")
    claude_critical = extract_section_content(claude_report, "Critical Issues")

    ds_warnings = extract_section_content(ds_report, "Warnings")
    claude_warnings = extract_section_content(claude_report, "Warnings")

    ds_fixes = extract_section_content(ds_report, "Concrete Proposed Fixes")
    claude_fixes = extract_section_content(claude_report, "Concrete Proposed Fixes")

    lines = [
        f"# ⚖️ Dual AI Itinerary Cross-Check Report: {trip_title}",
        f"**Trip Target:** `{trip_target}`",
        f"**Evaluators:** DeepSeek (`{ds_model}`) + Anthropic Claude (`{claude_model}`)",
        "",
        "## 📊 Model Verdict Consensus",
        "| Evaluator | Model | Final Rating | Status |",
        "|---|---|---|---|",
        f"| **Anthropic Claude** | `{claude_model}` | **{claude_verdict}** | {'🚨 Needs Attention' if 'CRITICAL' in claude_verdict or 'NEEDS' in claude_verdict else '✅ Passed / Tweaks'} |",
        f"| **DeepSeek** | `{ds_model}` | **{ds_verdict}** | {'🚨 Needs Attention' if 'CRITICAL' in ds_verdict or 'NEEDS' in ds_verdict else '✅ Passed / Tweaks'} |",
        "",
        "## 🎯 Cross-Check Consensus Analysis",
    ]

    # Evaluate consensus
    if ds_verdict == claude_verdict:
        lines.append(f"> [!IMPORTANT]\n> **High Model Agreement:** Both Claude and DeepSeek independently reached the same overall verdict: **{claude_verdict}**.\n")
    else:
        lines.append(f"> [!NOTE]\n> **Model Nuance:** Claude rated the trip as **{claude_verdict}** while DeepSeek rated it **{ds_verdict}**. Review their specific findings below to resolve differences.\n")

    lines.extend([
        "## 🛑 Critical Issues Comparison",
        "### Claude Analysis (Critical)",
        claude_critical if claude_critical else "No critical issues detected by Claude.",
        "",
        "### DeepSeek Analysis (Critical)",
        ds_critical if ds_critical else "No critical issues detected by DeepSeek.",
        "",
        "## ⚠️ Warnings & Logistical Friction Comparison",
        "### Claude Warnings & Route Observations",
        claude_warnings if claude_warnings else "No major warnings flagged by Claude.",
        "",
        "### DeepSeek Warnings & Route Observations",
        ds_warnings if ds_warnings else "No major warnings flagged by DeepSeek.",
        "",
        "## 💡 Actionable Fixes & Wanderlog Adjustments",
        "### Recommended Edits from Claude",
        claude_fixes if claude_fixes else "None specified.",
        "",
        "### Recommended Edits from DeepSeek",
        ds_fixes if ds_fixes else "None specified.",
        "",
        "---",
        "",
        "<details>",
        "<summary><b>📖 Expand Full Claude Report</b></summary>",
        "",
        claude_report,
        "",
        "</details>",
        "",
        "<details>",
        "<summary><b>📖 Expand Full DeepSeek Report</b></summary>",
        "",
        ds_report,
        "",
        "</details>",
    ])

    return "\n".join(lines)


def run_cross_check(
    trip_target: str,
    claude_cfg: claude_validator.ClaudeProviderConfig,
    ds_cfg: deepseek_validator.ProviderConfig,
    stream_progress: bool = True,
) -> Tuple[str, str, str]:
    """
    Run both Claude and DeepSeek validations and return (cross_check_md, claude_report, ds_report).
    """
    # 1. Fetch trip data once
    if stream_progress:
        console.print(f"[cyan]Fetching itinerary data for: [bold]{trip_target}[/bold]...[/cyan]")
    trip_json, trip_md = claude_validator.fetch_trip_data(trip_target)
    trip_summary = claude_validator.summarize_trip_context(trip_json, trip_md)

    tp = trip_json.get("tripPlan", {}) if "tripPlan" in trip_json else trip_json.get("trip", {})
    if not tp and "title" in trip_json:
        tp = trip_json
    trip_title = tp.get("title", "Wanderlog Trip")

    claude_report = ""
    ds_report = ""

    # 2. Run DeepSeek validator
    if stream_progress:
        with console.status(
            f"[bold blue]Step 1/2: Running DeepSeek audit ({ds_cfg.provider} / {ds_cfg.model})...[/bold blue]",
            spinner="dots",
        ):
            ds_report, _ = deepseek_validator.run_validation(trip_summary, ds_cfg, stream=False)
        console.print(f"[green]✓ DeepSeek audit complete[/green] ({len(ds_report)} chars)")
    else:
        ds_report, _ = deepseek_validator.run_validation(trip_summary, ds_cfg, stream=False)

    # 3. Run Claude validator
    if stream_progress:
        with console.status(
            f"[bold magenta]Step 2/2: Running Claude audit ({claude_cfg.provider} / {claude_cfg.model})...[/bold magenta]",
            spinner="dots",
        ):
            claude_report, _ = claude_validator.run_claude_validation(trip_summary, claude_cfg, stream=False)
        console.print(f"[green]✓ Claude audit complete[/green] ({len(claude_report)} chars)")
    else:
        claude_report, _ = claude_validator.run_claude_validation(trip_summary, claude_cfg, stream=False)

    # 4. Synthesize Cross-Check Report
    cross_report = synthesize_cross_check_report(
        trip_target=trip_target,
        trip_title=trip_title,
        ds_report=ds_report,
        claude_report=claude_report,
        ds_model=ds_cfg.model,
        claude_model=claude_cfg.model,
    )

    return cross_report, claude_report, ds_report


def display_cross_check_summary(
    trip_title: str,
    ds_report: str,
    claude_report: str,
    ds_model: str,
    claude_model: str,
) -> None:
    """Display rich CLI comparison table and overview."""
    ds_verdict = extract_verdict(ds_report)
    claude_verdict = extract_verdict(claude_report)

    console.print("\n")
    console.print(Panel(
        f"[bold white]Dual AI Cross-Check Results for:[/bold white] [bold cyan]{trip_title}[/bold cyan]\n"
        f"Comparing independent audits from [bold magenta]Claude[/bold magenta] ({claude_model}) "
        f"and [bold blue]DeepSeek[/bold blue] ({ds_model})",
        title="[bold yellow]⚖️ Wanderlog Cross-Check Summary[/bold yellow]",
        border_style="yellow",
    ))

    table = Table(title="Model Verdict Comparison", show_header=True, header_style="bold cyan")
    table.add_column("AI Evaluator", style="bold")
    table.add_column("Configured Model")
    table.add_column("Verdict", style="bold")
    table.add_column("Alignment")

    agreement = "🤝 Match" if ds_verdict == claude_verdict else "⚠️ Divergent"
    table.add_row("Anthropic Claude", claude_model, claude_verdict, agreement)
    table.add_row("DeepSeek", ds_model, ds_verdict, agreement)
    console.print(table)
    console.print("\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wanderlog Multi-Model Itinerary Cross-Check (Claude + DeepSeek)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "trip",
        nargs="?",
        help="Trip ID, Wanderlog URL, or local JSON file (e.g. trips/southern_italy.json)",
    )
    parser.add_argument(
        "--claude-model",
        help="Claude model override (default: ANTHROPIC_MODEL or claude-3-7-sonnet-20250219)",
    )
    parser.add_argument(
        "--deepseek-model",
        help="DeepSeek model override (default: deepseek/deepseek-chat or DEEPSEEK_MODEL)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run fast mode on both models (Claude Haiku & DeepSeek Chat)",
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
        help="Save generated cross-check Markdown report to specified file path",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test connectivity for both Claude and DeepSeek providers",
    )

    args = parser.parse_args()

    claude_model = args.claude_model
    ds_model = args.deepseek_model

    if args.quick:
        claude_model = claude_model or "claude-3-5-haiku-20241022"
        ds_model = ds_model or "deepseek/deepseek-chat"

    claude_cfg = claude_validator.ClaudeProviderConfig(model=claude_model)
    ds_cfg = deepseek_validator.ProviderConfig(model=ds_model)

    if args.test:
        console.print("[bold cyan]Testing Claude and DeepSeek Connectivity...[/bold cyan]\n")
        console.print("[bold]1. DeepSeek Test:[/bold]")
        ds_ok = deepseek_validator.verify_connection(ds_cfg)
        console.print("\n[bold]2. Claude Test:[/bold]")
        claude_ok = claude_validator.verify_connection(claude_cfg)
        sys.exit(0 if (ds_ok and claude_ok) else 1)

    if not args.trip:
        console.print(
            Panel(
                "[bold cyan]Wanderlog Dual AI Cross-Check Validator[/bold cyan]\n\n"
                "Run independent validation checks with [bold magenta]Claude[/bold magenta] and [bold blue]DeepSeek[/bold blue] "
                "to compare findings and catch every logistical blindspot.\n\n"
                "[bold]Usage:[/bold]\n"
                "  uv run scripts/cross_check_validator.py <trip_id_or_file> [options]\n\n"
                "[bold]Examples:[/bold]\n"
                "  uv run scripts/cross_check_validator.py trips/southern_italy.json\n"
                "  uv run scripts/cross_check_validator.py abc123xyz --quick\n"
                "  uv run scripts/cross_check_validator.py abc123xyz --save-report trips/cross_check.md\n"
                "  uv run scripts/cross_check_validator.py --test\n\n"
                "To configure keys:\n"
                "  Claude:   [green]./scripts/login_claude.sh[/green]\n"
                "  DeepSeek: [green]./scripts/login_deepseek.sh[/green]",
                title="Claude + DeepSeek Cross-Check",
            )
        )
        sys.exit(0)

    cross_report, claude_report, ds_report = run_cross_check(
        trip_target=args.trip,
        claude_cfg=claude_cfg,
        ds_cfg=ds_cfg,
        stream_progress=(args.format == "rich"),
    )

    if args.format == "rich":
        display_cross_check_summary(
            trip_title=args.trip,
            ds_report=ds_report,
            claude_report=claude_report,
            ds_model=ds_cfg.model,
            claude_model=claude_cfg.model,
        )
        console.print(Markdown(cross_report))
    elif args.format == "markdown":
        print(cross_report)
    elif args.format == "json":
        output_payload = {
            "trip": args.trip,
            "models": {
                "claude": claude_cfg.model,
                "deepseek": ds_cfg.model,
            },
            "claude_report": claude_report,
            "deepseek_report": ds_report,
            "cross_check_report": cross_report,
        }
        print(json.dumps(output_payload, indent=2))

    if args.save_report:
        save_path = Path(args.save_report)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(cross_report)
        console.print(f"[green]✓ Cross-check report saved to {save_path}[/green]")


if __name__ == "__main__":
    main()
