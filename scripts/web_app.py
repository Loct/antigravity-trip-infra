#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "chainlit>=1.3.0",
#     "httpx>=0.27.0",
#     "rich>=13.0.0",
#     "pydantic>=2.0.0",
#     "aiosqlite>=0.20.0",
#     "sqlalchemy>=2.0.0",
#     "greenlet>=3.0.0",
# ]
# ///
"""
Wanderlog & Antigravity Mobile Web Interface (Chainlit)

Provides a responsive, mobile-friendly chat and session interface for:
1. Conversing with Antigravity CLI (agy) remotely.
2. Managing Wanderlog trips, day plans, and places.
3. Searching hotels via Booking.com (Genius Level 3) & Agoda.
4. Consulting the multi-model AI Travel Council (Claude & DeepSeek).
5. Maintaining persistent multi-session history with shareable threads.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sqlite3
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import chainlit as cl
except ImportError:
    # Graceful fallback when imported in test or local environments without chainlit
    cl = None  # type: ignore

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Regex to strip ANSI escape codes from CLI output
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def clean_ansi(text: str) -> str:
    """Strip ANSI color and terminal escape sequences from text."""
    return ANSI_ESCAPE.sub("", text)


# ----------------------------------------------------------------------
# SQLite Data Persistence (Chainlit Data Layer)
# ----------------------------------------------------------------------
DB_DIR = WORKSPACE_DIR / "data"
DB_PATH = os.getenv("CHAINLIT_DB_PATH", str(DB_DIR / "chainlit.db"))

CHAINLIT_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    "id" TEXT PRIMARY KEY,
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata" TEXT NOT NULL DEFAULT '{}',
    "createdAt" TEXT
);

CREATE TABLE IF NOT EXISTS threads (
    "id" TEXT PRIMARY KEY,
    "createdAt" TEXT,
    "name" TEXT,
    "userId" TEXT,
    "userIdentifier" TEXT,
    "tags" TEXT,
    "metadata" TEXT DEFAULT '{}',
    FOREIGN KEY ("userId") REFERENCES users("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS steps (
    "id" TEXT PRIMARY KEY,
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "threadId" TEXT NOT NULL,
    "parentId" TEXT,
    "streaming" BOOLEAN NOT NULL DEFAULT 0,
    "waitForAnswer" BOOLEAN,
    "isError" BOOLEAN,
    "metadata" TEXT DEFAULT '{}',
    "tags" TEXT,
    "input" TEXT,
    "output" TEXT,
    "createdAt" TEXT,
    "command" TEXT,
    "start" TEXT,
    "end" TEXT,
    "generation" TEXT,
    "showInput" TEXT,
    "language" TEXT,
    "indent" INT,
    "defaultOpen" BOOLEAN,
    "autoCollapse" BOOLEAN,
    "icon" TEXT,
    "modes" TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS elements (
    "id" TEXT PRIMARY KEY,
    "threadId" TEXT,
    "type" TEXT,
    "url" TEXT,
    "chainlitKey" TEXT,
    "name" TEXT NOT NULL,
    "display" TEXT,
    "objectKey" TEXT,
    "size" TEXT,
    "page" INT,
    "language" TEXT,
    "forId" TEXT,
    "mime" TEXT,
    "props" TEXT DEFAULT '{}',
    "autoPlay" BOOLEAN,
    "playerConfig" TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS feedbacks (
    "id" TEXT PRIMARY KEY,
    "forId" TEXT NOT NULL,
    "threadId" TEXT NOT NULL,
    "value" INT NOT NULL,
    "comment" TEXT
);
"""


def init_sqlite_db(db_path: str | Path) -> None:
    """Initialize SQLite database with required Chainlit tables and run migrations."""
    path = Path(db_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.register_adapter(list, json.dumps)
    with sqlite3.connect(str(path)) as conn:
        conn.executescript(CHAINLIT_SQLITE_SCHEMA)
        # Migrate existing tables if columns are missing from earlier schema versions
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(steps);")
        existing_cols = {row[1] for row in cursor.fetchall()}
        missing_cols = {
            "defaultOpen": "BOOLEAN",
            "autoCollapse": "BOOLEAN",
            "icon": "TEXT",
            "modes": "TEXT",
            "indent": "INT",
        }
        for col, col_type in missing_cols.items():
            if col not in existing_cols:
                try:
                    cursor.execute(f'ALTER TABLE steps ADD COLUMN "{col}" {col_type};')
                except sqlite3.OperationalError:
                    pass
        conn.commit()


# ----------------------------------------------------------------------
# Authentication & User Management
# ----------------------------------------------------------------------
AUTH_PASSWORD = os.getenv("WEB_AUTH_PASSWORD", "").strip()

if cl is not None:
    if not os.getenv("CHAINLIT_AUTH_SECRET"):
        secret_file = Path("/root/.gemini/antigravity-cli/.chainlit_secret")
        if secret_file.exists():
            os.environ["CHAINLIT_AUTH_SECRET"] = secret_file.read_text().strip()
        else:
            import secrets

            os.environ["CHAINLIT_AUTH_SECRET"] = secrets.token_hex(32)

    @cl.password_auth_callback
    def authenticate(username: str, password: str) -> Optional[cl.User]:
        """Authenticate user against WEB_AUTH_PASSWORD (or any username if no password is configured)."""
        if AUTH_PASSWORD:
            if password == AUTH_PASSWORD:
                return cl.User(identifier=username or "collaborator", metadata={"role": "user"})
            return None
        # When no password is required, allow any username or default to traveler
        return cl.User(identifier=username or "traveler", metadata={"role": "user"})

    try:
        from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

        init_sqlite_db(DB_PATH)

        @cl.data_layer
        def get_data_layer():
            return SQLAlchemyDataLayer(conninfo=f"sqlite+aiosqlite:///{DB_PATH}")

    except Exception as e:
        import logging

        logging.getLogger("chainlit").warning(f"Could not initialize SQLite data layer: {e}")


# ----------------------------------------------------------------------
# Starters: Suggested quick actions shown on new conversation
# ----------------------------------------------------------------------
if cl is not None:

    @cl.set_starters
    async def set_starters() -> List[cl.Starter]:
        return [
            cl.Starter(
                label="List Wanderlog Trips",
                message="/trips",
                icon="/public/trip_icon.svg" if Path("/public/trip_icon.svg").exists() else None,
            ),
            cl.Starter(
                label="Search Tokyo Hotels (Genius Lv3)",
                message="/hotel Tokyo 2026-04-01 2026-04-05",
                icon=None,
            ),
            cl.Starter(
                label="Consult AI Council",
                message="/council --latest How should I pace a 7-day Japan itinerary?",
                icon=None,
            ),
            cl.Starter(
                label="System & Auth Status",
                message="/status",
                icon=None,
            ),
        ]

    # ----------------------------------------------------------------------
    # Session Lifecycle: Startup & Resume
    # ----------------------------------------------------------------------
    @cl.on_chat_start
    async def on_chat_start() -> None:
        """Initialize session state and display welcome overview."""
        cl.user_session.set("history", [])
        cl.user_session.set("agy_conversation_id", None)

        welcome_text = """### 🌍 Welcome to Wanderlog & Antigravity Web Gateway!

This interface lets you collaborate on travel planning with:
- **Wanderlog**: Live trip itineraries, reservations, places, and budgets.
- **Lodging CLIs**: Booking.com (with Genius Level discounts) & Agoda.
- **AI Travel Council**: Anthropic Claude & DeepSeek mutual peer review.
- **Antigravity Agent**: Full autonomous agent capabilities.

💡 *Type `/help` to see quick slash commands, or start asking questions below!*
"""
        await cl.Message(content=welcome_text).send()

    @cl.on_chat_resume
    async def on_chat_resume(thread: Dict[str, Any]) -> None:
        """Resume an existing chat thread from persistent history."""
        resume_chat_thread(thread)


def parse_thread_metadata(metadata: Any) -> Dict[str, Any]:
    """Parse thread metadata safely whether dict or serialized JSON string."""
    if isinstance(metadata, str):
        try:
            return json.loads(metadata) if metadata.strip() else {}
        except Exception:
            return {}
    elif isinstance(metadata, dict):
        return metadata
    return {}


def resume_chat_thread(thread: Dict[str, Any]) -> None:
    """Extract and restore session state when resuming a chat thread."""
    if cl is None:
        return
    cl.user_session.set("history", thread.get("steps") or thread.get("messages") or [])
    meta = parse_thread_metadata(thread.get("metadata"))
    cl.user_session.set("agy_conversation_id", meta.get("agy_conversation_id"))


# ----------------------------------------------------------------------
# Command Handlers (Wanderlog, Booking, Agoda, AI Council, Status)
# ----------------------------------------------------------------------
async def handle_status() -> str:
    """Check authentication and connectivity for all services."""
    lines = ["### 🔍 System & Authentication Status\n"]

    # 1. Wanderlog Status
    wanderlog_cookie = os.getenv("WANDERLOG_AUTH_SESSION_COOKIE", "")
    cred_file = Path.home() / ".config" / "wanderlog" / "credentials.json"
    if wanderlog_cookie or cred_file.exists():
        lines.append("- ✅ **Wanderlog**: Authenticated via session cookie")
    else:
        lines.append("- ⚠️ **Wanderlog**: Not configured (set `WANDERLOG_AUTH_SESSION_COOKIE`)")

    # 2. Antigravity CLI (agy)
    if shutil.which("agy"):
        lines.append("- ✅ **Antigravity CLI (`agy`)**: Installed & ready")
    else:
        lines.append("- ⚠️ **Antigravity CLI (`agy`)**: Binary not found in PATH")

    # 3. Booking.com
    bkng_cookie = os.getenv("BOOKING_SESSION_COOKIE", "")
    if bkng_cookie:
        lines.append("- ✅ **Booking.com**: Authenticated with Genius Level discounts")
    else:
        lines.append(
            "- ℹ️ **Booking.com**: No session cookie set (standard public pricing; run `./scripts/login_booking.sh` for Genius discounts)"
        )

    # 4. Agoda
    agoda_key = os.getenv("AGODA_API_KEY", "") or os.getenv("RAPIDAPI_KEY", "")
    agoda_cookie = os.getenv("AGODA_SESSION_COOKIE", "")
    apify_tok = os.getenv("APIFY_TOKEN", "")
    agoda_vip = os.getenv("AGODA_VIP_LEVEL", "4")
    auto_vip = (
        os.getenv("AGODA_AUTO_DETECT_VIP", "").lower() in ("1", "true", "yes") or str(agoda_vip).lower() == "auto"
    )

    if agoda_cookie:
        from agoda import detect_personal_account_tier

        tier_lvl, tier_nm, acct_id = detect_personal_account_tier(agoda_cookie)
        if tier_lvl and tier_nm:
            lines.append(f"- ✅ **Agoda**: Personal account connected ({acct_id or 'Member'}, {tier_nm} auto-detected)")
        else:
            lines.append(f"- ✅ **Agoda**: Authenticated via session cookie (AgodaVIP Level {agoda_vip})")
    elif agoda_key:
        lines.append(f"- ✅ **Agoda**: API key configured (AgodaVIP Level {agoda_vip})")
    elif auto_vip:
        lines.append(
            "- ℹ️ **Agoda**: Personal account VIP auto-detection enabled (cookie not yet linked; run `./scripts/login_agoda.sh` Option 3)"
        )
    elif apify_tok:
        lines.append(f"- ✅ **Agoda**: Apify scraper configured (AgodaVIP Level {agoda_vip})")
    else:
        lines.append(f"- ℹ️ **Agoda**: Direct web mode active (AgodaVIP Level {agoda_vip})")

    # 5. AI Council (Claude & DeepSeek)
    claude_key = os.getenv("ANTHROPIC_API_KEY", "")
    deepseek_key = os.getenv("OPENROUTER_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")
    if claude_key:
        lines.append("- ✅ **Anthropic Claude**: API key active")
    else:
        lines.append("- ℹ️ **Anthropic Claude**: Not configured")
    if deepseek_key:
        lines.append("- ✅ **DeepSeek**: API key active")
    else:
        lines.append("- ℹ️ **DeepSeek**: Not configured")

    # 5. GitHub CLI
    if os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN"):
        lines.append("- ✅ **GitHub CLI (`gh`)**: Token configured")
    else:
        lines.append("- ℹ️ **GitHub CLI (`gh`)**: Optional token not set")

    # 6. SQLite Database & Persistence
    if Path(DB_PATH).exists():
        lines.append(f"- ✅ **Chat Persistence**: SQLite active (`{Path(DB_PATH).name}`)")
    else:
        lines.append("- ℹ️ **Chat Persistence**: In-memory / not initialized")

    return "\n".join(lines)


async def handle_trips_list() -> str:
    """Fetch and format current Wanderlog trips."""
    async with cl.Step(name="Fetching Wanderlog Trips", type="tool") as step:
        step.output = "Running `wanderlog trips list`..."
        try:
            proc = await asyncio.create_subprocess_exec(
                "wanderlog",
                "trips",
                "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0 and stdout:
                output = stdout.decode().strip()
                step.output = f"Retrieved trips successfully ({len(output.splitlines())} lines)"
                return f"### 🧳 Wanderlog Trips\n\n```text\n{output}\n```"
            else:
                err = stderr.decode().strip() if stderr else "Unknown error"
                step.output = f"Error: {err}"
                return f"⚠️ **Could not list trips**: {err}"
        except FileNotFoundError:
            step.output = "wanderlog CLI binary not found"
            return "⚠️ `wanderlog` binary is not installed in the container PATH."


def format_cookie_error_banner(provider: str, error_text: str) -> Optional[str]:
    """Inspect error output and return a high-clarity markdown recovery banner if cookie is expired/missing."""
    err_lower = error_text.lower()
    if provider == "Booking.com":
        if any(
            term in err_lower for term in ["session cookie is not configured", "unavailable", "unset", "not configured"]
        ):
            return (
                "> ⚠️ **Booking.com Cookie Missing / Unset — Please Log In & Configure**\n"
                "> `BOOKING_SESSION_COOKIE` is unset. **You need to log into Booking.com in your browser** to get your session cookie "
                "and unlock Genius Level 3 (-20%) discounts.\n"
                ">\n"
                "> **Action Required (Log in & 30s Setup)**:\n"
                "> 1. Open [booking.com](https://www.booking.com) in your browser and **log into your account**.\n"
                "> 2. Run `./scripts/login_booking.sh` to save your session cookie (or set `BOOKING_SESSION_COOKIE` in `.env`)."
            )
        if any(term in err_lower for term in ["expired", "401", "challenge", "202", "403", "signin", "sign-in"]):
            return (
                "> ⚠️ **Booking.com Session Cookie Expired — Please Log In Again**\n"
                "> Your Booking.com session has expired. **You must log in again to Booking.com in your browser** to refresh your session.\n"
                ">\n"
                "> **Action Required (Re-login & 30s Fix)**:\n"
                "> 1. Open [booking.com](https://www.booking.com) in your browser and **log into your account again**.\n"
                "> 2. Run `./scripts/login_booking.sh` to update your session cookie (or update `BOOKING_SESSION_COOKIE` in `.env`)."
            )
    elif provider == "Agoda":
        if any(
            term in err_lower for term in ["session cookie is not configured", "unavailable", "unset", "not configured"]
        ):
            return (
                "> ⚠️ **Agoda Session Cookie Unset — Please Log In & Configure**\n"
                "> `AGODA_SESSION_COOKIE` is unset. **You need to log into Agoda in your browser** to get your session cookie "
                "and auto-detect your AgodaVIP tier (up to -25%).\n"
                ">\n"
                "> **Action Required (Log in & 30s Setup)**:\n"
                "> 1. Open [agoda.com](https://www.agoda.com) in your browser and **log into your account**.\n"
                "> 2. Run `./scripts/login_agoda.sh` (Option 3: Personal Account & Session Cookie) to save `AGODA_SESSION_COOKIE` in `.env`."
            )
        if any(term in err_lower for term in ["expired", "401", "unauthenticated", "signin", "login"]):
            return (
                "> ⚠️ **Agoda Session Cookie Expired — Please Log In Again**\n"
                "> Your Agoda personal session has expired. **You must log in again to Agoda in your browser** to refresh your session.\n"
                ">\n"
                "> **Action Required (Re-login & 30s Fix)**:\n"
                "> 1. Open [agoda.com](https://www.agoda.com) in your browser and **log into your account again**.\n"
                "> 2. Run `./scripts/login_agoda.sh` (Option 3: Personal Account & Session Cookie) to update `AGODA_SESSION_COOKIE`."
            )
        if "challenge" in err_lower or "403" in err_lower:
            return (
                "> ⚠️ **Agoda Security Challenge Triggered**\n"
                "> Agoda bot protection blocked direct requests. Update `AGODA_SESSION_COOKIE` via `./scripts/login_agoda.sh` (Option 3)."
            )
    return None


async def handle_booking_search(args: str) -> str:
    """Execute Booking.com search via scripts/booking.py."""
    parts = args.strip().split()
    if not parts:
        return "⚠️ **Usage**: `/hotel <city> [checkin] [checkout]` (e.g. `/hotel Tokyo 2026-04-01 2026-04-05`)"

    city = parts[0]
    checkin = parts[1] if len(parts) > 1 else None
    checkout = parts[2] if len(parts) > 2 else None

    cmd = ["uv", "run", str(SCRIPT_DIR / "booking.py"), "search", "-l", city]
    if checkin:
        cmd.extend(["-i", checkin])
    if checkout:
        cmd.extend(["-o", checkout])

    async with cl.Step(name=f"Searching Hotels in {city}", type="tool") as step:
        step.output = f"Executing: {' '.join(cmd)}"
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(WORKSPACE_DIR),
            )
            stdout, stderr = await proc.communicate()
            output = clean_ansi(stdout.decode().strip() if stdout else "")
            if proc.returncode == 0:
                step.output = "Search completed successfully"
                return f"### 🏨 Hotel Results for {city}\n\n{output}"
            else:
                err = clean_ansi(stderr.decode().strip() if stderr else "Search failed")
                step.output = f"Failed with code {proc.returncode}"
                banner = format_cookie_error_banner("Booking.com", err or output)
                banner_md = f"{banner}\n\n" if banner else ""
                return f"{banner_md}⚠️ **Hotel search error**:\n```text\n{err or output}\n```"
        except Exception as e:
            step.output = str(e)
            return f"⚠️ Error executing hotel search: {e}"


async def handle_agoda_search(args: str) -> str:
    """Execute Agoda lodging search via scripts/agoda.py."""
    parts = args.strip().split()
    if not parts:
        return "⚠️ **Usage**: `/agoda <city> [checkin] [checkout]` (e.g. `/agoda Tokyo 2026-04-01 2026-04-05`)"

    city = parts[0]
    checkin = parts[1] if len(parts) > 1 else None
    checkout = parts[2] if len(parts) > 2 else None

    cmd = ["uv", "run", str(SCRIPT_DIR / "agoda.py"), "search", "-l", city]
    if checkin:
        cmd.extend(["-i", checkin])
    if checkout:
        cmd.extend(["-o", checkout])

    async with cl.Step(name=f"Searching Agoda Lodging in {city}", type="tool") as step:
        step.output = f"Executing: {' '.join(cmd)}"
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(WORKSPACE_DIR),
            )
            stdout, stderr = await proc.communicate()
            output = clean_ansi(stdout.decode().strip() if stdout else "")
            if proc.returncode == 0:
                step.output = "Search completed successfully"
                return f"### 🏨 Agoda Lodging Results for {city}\n\n{output}"
            else:
                err = clean_ansi(stderr.decode().strip() if stderr else "Search failed")
                step.output = f"Failed with code {proc.returncode}"
                banner = format_cookie_error_banner("Agoda", err or output)
                banner_md = f"{banner}\n\n" if banner else ""
                return f"{banner_md}⚠️ **Agoda search error**:\n```text\n{err or output}\n```"
        except Exception as e:
            step.output = str(e)
            return f"⚠️ Error executing Agoda search: {e}"


def normalize_hotel_name(name: str, city: str = "") -> str:
    """Normalize hotel name for fuzzy cross-platform deduplication and matching."""
    cleaned = re.sub(r"[^\w\s]", "", name.lower())
    stop_words = {"hotel", "resort", "the", "and", "suites", "apart", "tokyo", "japan", city.lower()}
    tokens = [w for w in cleaned.split() if w not in stop_words]
    return " ".join(tokens) if tokens else cleaned


async def handle_compare_hotels(args: str) -> str:
    """Execute parallel Booking.com, Agoda, and Hotel Direct search and synthesize a comparative overview."""
    parts = args.strip().split()
    if not parts:
        return "⚠️ **Usage**: `/hotels <city> [checkin] [checkout]` (e.g. `/hotels Tokyo 2026-04-01 2026-04-05`)"

    city = parts[0]
    checkin = parts[1] if len(parts) > 1 else None
    checkout = parts[2] if len(parts) > 2 else None

    # Base commands requesting JSON output for structured comparison
    bkng_cmd = ["uv", "run", str(SCRIPT_DIR / "booking.py"), "search", "-l", city, "-f", "json", "--limit", "5"]
    agoda_cmd = ["uv", "run", str(SCRIPT_DIR / "agoda.py"), "search", "-l", city, "-f", "json", "--limit", "5"]

    if checkin:
        bkng_cmd.extend(["-i", checkin])
        agoda_cmd.extend(["-i", checkin])
    if checkout:
        bkng_cmd.extend(["-o", checkout])
        agoda_cmd.extend(["-o", checkout])

    # Google Hotels / Wanderlog lodging command for direct rate lookup if available
    google_cmd = None
    if shutil.which("wanderlog"):
        google_cmd = ["wanderlog", "travel", "hotels", city, "-o", "json"]
        if checkin:
            google_cmd.extend(["--check-in", checkin])
        if checkout:
            google_cmd.extend(["--check-out", checkout])

    async with cl.Step(name=f"Comparing Booking.com, Agoda & Hotel Direct for {city}", type="tool") as step:
        step.output = "Searching Booking.com, Agoda & Hotel Direct simultaneously..."

        async def run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(WORKSPACE_DIR),
                )
                stdout, stderr = await proc.communicate()
                return (
                    proc.returncode,
                    clean_ansi(stdout.decode().strip() if stdout else ""),
                    clean_ansi(stderr.decode().strip() if stderr else ""),
                )
            except Exception as e:
                return -1, "", str(e)

        tasks = [run_cmd(bkng_cmd), run_cmd(agoda_cmd)]
        if google_cmd:
            tasks.append(run_cmd(google_cmd))

        results = await asyncio.gather(*tasks)
        code_b, out_b, err_b = results[0]
        code_a, out_a, err_a = results[1]
        code_g, out_g, err_g = results[2] if len(results) > 2 else (-1, "", "Not available")

        step.output = "Search complete, synthesizing property-matched comparison table..."

        # Parse JSON
        hotels_b = []
        if code_b == 0 and out_b:
            try:
                data_b = json.loads(out_b)
                hotels_b = data_b.get("hotels", [])
            except Exception:
                pass

        hotels_a = []
        if code_a == 0 and out_a:
            try:
                data_a = json.loads(out_a)
                hotels_a = data_a.get("hotels", [])
            except Exception:
                pass

        hotels_g = []
        if code_g == 0 and out_g:
            try:
                data_g = json.loads(out_g)
                if isinstance(data_g, dict):
                    hotels_g = data_g.get("data", []) or data_g.get("hotels", [])
                elif isinstance(data_g, list):
                    hotels_g = data_g
            except Exception:
                pass

        # Build Google / Direct rate lookup by normalized name
        google_lookup: Dict[str, Dict[str, Any]] = {}
        for h in hotels_g:
            g_name = h.get("name", "")
            if g_name:
                google_lookup[normalize_hotel_name(g_name, city)] = h

        # Check for cookie warnings/errors on either provider
        banner_b = format_cookie_error_banner("Booking.com", err_b or out_b)
        banner_a = format_cookie_error_banner("Agoda", err_a or out_a)

        if not hotels_b and not hotels_a:
            combined_banners = "\n\n".join(b for b in [banner_b, banner_a] if b)
            banner_prefix = f"{combined_banners}\n\n" if combined_banners else ""
            return (
                f"{banner_prefix}⚠️ **Could not retrieve hotels for {city}**:\n\n"
                f"**Booking.com**:\n```text\n{err_b or out_b or 'No results'}\n```\n\n"
                f"**Agoda**:\n```text\n{err_a or out_a or 'No results'}\n```"
            )

        # Build comparative Markdown table
        lines = []
        if not hotels_b:
            lines.append(banner_b or f"> ⚠️ **Booking.com**: No properties retrieved (`{err_b or 'No availability'}`)")
            lines.append("")
        if not hotels_a:
            lines.append(banner_a or f"> ⚠️ **Agoda**: No properties retrieved (`{err_a or 'No availability'}`)")
            lines.append("")

        lines.extend(
            [
                f"### 🏨 Hotel Comparison: Booking.com vs. Agoda vs. Hotel Direct for '{city}'",
                "",
                "| # | Property Name | Rating | Booking.com | Agoda | Hotel Direct | Perks / Badges |",
                "|---|---|:---:|---|---|---|---|",
            ]
        )

        # Property-matched deduplication across Booking and Agoda
        matched_properties: List[Dict[str, Any]] = []
        used_agoda_idx = set()

        for h_b in hotels_b[:5]:
            name_b = h_b.get("name", "Unknown")
            norm_b = normalize_hotel_name(name_b, city)
            matched_a = None
            for idx, h_a in enumerate(hotels_a[:5]):
                if idx in used_agoda_idx:
                    continue
                norm_a = normalize_hotel_name(h_a.get("name", ""), city)
                if norm_b and norm_a and (norm_b == norm_a or norm_b in norm_a or norm_a in norm_b):
                    matched_a = h_a
                    used_agoda_idx.add(idx)
                    break

            badges = list(dict.fromkeys(h_b.get("badges", []) + (matched_a.get("badges", []) if matched_a else [])))
            matched_properties.append(
                {
                    "name": name_b,
                    "booking": h_b,
                    "agoda": matched_a,
                    "rating": h_b.get("rating") or (matched_a.get("rating") if matched_a else None),
                    "badges": badges,
                }
            )

        for idx, h_a in enumerate(hotels_a[:5]):
            if idx not in used_agoda_idx:
                matched_properties.append(
                    {
                        "name": h_a.get("name", "Unknown"),
                        "booking": None,
                        "agoda": h_a,
                        "rating": h_a.get("rating"),
                        "badges": h_a.get("badges", []),
                    }
                )

        row_idx = 1
        for prop in matched_properties:
            name = prop["name"]
            score = f"{prop['rating']:.1f}/10" if prop.get("rating") else "N/A"
            badges = ", ".join(prop["badges"][:2]) or "—"

            # 1. Booking.com cell
            hb = prop["booking"]
            if hb:
                rate_b = (
                    hb.get("genius_price_text")
                    or hb.get("price_text")
                    or (f"{hb.get('currency')} {hb.get('total_price'):.2f}" if hb.get("total_price") else "Check rate")
                )
                if hb.get("is_genius_deal"):
                    rate_b += f" *(Genius -{int(hb.get('genius_discount_rate', 0.2) * 100)}%)*"
                url_b = hb.get("url") or "#"
                link_b = f"[Book Booking.com]({url_b})" if url_b != "#" else "—"
                cell_b = f"{rate_b}<br>{link_b}"
            else:
                bk_params = f"ss={urllib.parse.quote_plus(name)}"
                if checkin:
                    bk_params += f"&checkin={checkin}"
                if checkout:
                    bk_params += f"&checkout={checkout}"
                bk_params += "&group_adults=1&no_rooms=1"
                cell_b = (
                    f"*(Check rate)*<br>[Search Booking.com](https://www.booking.com/searchresults.html?{bk_params})"
                )

            # 2. Agoda cell
            ha = prop["agoda"]
            if ha:
                rate_a = (
                    ha.get("vip_price_text")
                    or ha.get("price_text")
                    or (f"{ha.get('currency')} {ha.get('total_price'):.2f}" if ha.get("total_price") else "Check rate")
                )
                if ha.get("is_vip_deal"):
                    rate_a += f" *(VIP -{int(ha.get('vip_discount_rate', 0.25) * 100)}%)*"
                url_a = ha.get("url") or "#"
                link_a = f"[Book Agoda]({url_a})" if url_a != "#" else "—"
                cell_a = f"{rate_a}<br>{link_a}"
            else:
                ag_params = f"text={urllib.parse.quote_plus(name)}"
                if checkin:
                    ag_params += f"&checkIn={checkin}"
                if checkout:
                    ag_params += f"&checkOut={checkout}"
                ag_params += "&adults=1&rooms=1"
                cell_a = f"*(Check rate)*<br>[Search Agoda](https://www.agoda.com/search?{ag_params})"

            # 3. Hotel Direct cell
            norm = normalize_hotel_name(name, city)
            direct_hotel = None
            for k, v in google_lookup.items():
                if norm and k and (norm == k or norm in k or k in norm):
                    direct_hotel = v
                    break

            q_direct = urllib.parse.quote_plus(f"{name} {city}")
            direct_params = f"q={q_direct}"
            if checkin:
                direct_params += f"&checkin={checkin}"
            if checkout:
                direct_params += f"&checkout={checkout}"
            direct_params += "&adults=1"
            direct_url = f"https://www.google.com/travel/hotels?{direct_params}"

            if direct_hotel and direct_hotel.get("pricePerNight"):
                curr = direct_hotel.get("currency", "EUR")
                ppn = direct_hotel.get("pricePerNight")
                cell_d = f"**{curr} {ppn}/night** *(Official)*<br>[Book Direct]({direct_url})"
            else:
                cell_d = f"Check Official Site<br>[Book Direct]({direct_url})"

            lines.append(f"| {row_idx} | **{name}** | {score} | {cell_b} | {cell_a} | {cell_d} | {badges} |")
            row_idx += 1

        lines.extend(
            [
                "",
                "💡 *Tip: Loyalty discounts (Genius on Booking.com & AgodaVIP on Agoda) are pre-calculated. Hotel Direct options link directly to Google Hotels / Official Hotel reservation engines with pre-populated travel dates.*",
            ]
        )

        return "\n".join(lines)


async def handle_council_query(query: str) -> str:
    """Execute AI Council deliberation via scripts/ai_council.py."""
    if not query.strip():
        return "⚠️ **Usage**: `/council <question or topic>`"

    cmd = ["uv", "run", str(SCRIPT_DIR / "ai_council.py"), query]
    async with cl.Step(name="Consulting AI Travel Council (Claude & DeepSeek)", type="tool") as step:
        step.output = "Council deliberation in progress..."
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(WORKSPACE_DIR),
            )
            stdout, stderr = await proc.communicate()
            output = clean_ansi(stdout.decode().strip() if stdout else "")
            if proc.returncode == 0 and output:
                step.output = "Council synthesized recommendation"
                return output
            else:
                err = clean_ansi(stderr.decode().strip() if stderr else "Council failed")
                step.output = "Deliberation error"
                return f"⚠️ **AI Council Error**:\n```text\n{err or output}\n```"
        except Exception as e:
            step.output = str(e)
            return f"⚠️ Error running AI Council: {e}"


# ----------------------------------------------------------------------
# Antigravity Agent (agy) Runner
# ----------------------------------------------------------------------
async def run_agy_agent(user_prompt: str) -> None:
    """Execute user prompt against Antigravity CLI and stream response."""
    msg = cl.Message(content="")
    await msg.send()

    # Check if agy is available
    if not shutil.which("agy"):
        msg.content = (
            "⚠️ **Antigravity CLI (`agy`) is not installed in the PATH.**\n\n"
            "You can still use slash commands:\n"
            "- `/trips` - List Wanderlog trips\n"
            "- `/hotel <city>` - Search Booking.com\n"
            "- `/council <question>` - Consult Claude & DeepSeek\n"
            "- `/status` - Check integrations"
        )
        await msg.update()
        return

    conv_id = cl.user_session.get("agy_conversation_id") if cl else None

    async with cl.Step(name="Antigravity Agent Processing", type="run") as step:
        step.output = "Spawning agy agent session..."
        try:
            cmd = ["agy", "--dangerously-skip-permissions"]
            if conv_id:
                cmd.extend(["--conversation", conv_id])
            cmd.extend(["-p", user_prompt, "--output-format", "stream-json"])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(WORKSPACE_DIR),
            )

            has_tokens = False

            async def read_stdout():
                nonlocal has_tokens
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        continue
                    try:
                        payload = json.loads(line_str)
                        event = payload.get("event")
                        if event == "init":
                            new_conv_id = payload.get("conversation_id")
                            if new_conv_id and cl:
                                cl.user_session.set("agy_conversation_id", new_conv_id)
                                try:
                                    sess = getattr(getattr(cl, "context", None), "session", None)
                                    t_id = getattr(sess, "thread_id", None)
                                    dl = getattr(cl.data, "get_data_layer", lambda: None)()
                                    if dl and t_id:
                                        asyncio.create_task(
                                            dl.update_thread(
                                                thread_id=t_id,
                                                metadata={"agy_conversation_id": new_conv_id},
                                            )
                                        )
                                except Exception:
                                    pass
                        elif event == "step_update":
                            step_up = payload.get("step_update", {})
                            stype = step_up.get("step_type")
                            if stype == "tool":
                                tname = step_up.get("tool_name", "tool")
                                step.output = f"Executing tool: {tname}"
                            elif stype == "agent_response":
                                delta = step_up.get("text_delta")
                                if delta:
                                    has_tokens = True
                                    await msg.stream_token(delta)
                        elif event == "result":
                            res = payload.get("result", {})
                            if not has_tokens and res.get("response"):
                                has_tokens = True
                                await msg.stream_token(res.get("response"))
                    except json.JSONDecodeError:
                        clean_line = clean_ansi(line_str)
                        if clean_line and not clean_line.startswith("warning:"):
                            has_tokens = True
                            await msg.stream_token(clean_line + "\n")

            stderr_lines = []

            async def read_stderr():
                while True:
                    line = await proc.stderr.readline()
                    if not line:
                        break
                    stderr_lines.append(line.decode("utf-8", errors="replace"))

            await asyncio.gather(read_stdout(), read_stderr())
            await proc.wait()

            if proc.returncode != 0:
                err_text = clean_ansi("".join(stderr_lines).strip())
                step.output = f"Exited with code {proc.returncode}"
                if not has_tokens:
                    msg.content = f"⚠️ **Error running agent (status {proc.returncode})**:\n```text\n{err_text or 'Unknown CLI error'}\n```"
            else:
                step.output = "Completed successfully"

            await msg.update()

        except Exception as e:
            step.output = f"Execution error: {e}"
            msg.content = f"⚠️ **Error running agent**: {e}"
            await msg.update()


# ----------------------------------------------------------------------
# Main Incoming Message Router
# ----------------------------------------------------------------------
if cl is not None:

    @cl.on_message
    async def on_message(message: cl.Message) -> None:
        """Handle incoming message from user."""
        text = message.content.strip()

        # 1. Slash Commands
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            if cmd == "/help":
                help_md = """### 📖 Available Slash Commands

- `/trips` - List current Wanderlog trips
- `/hotels <city> [checkin] [checkout]` - 3-way lodging comparison (Booking.com, Agoda & Hotel Direct)
- `/hotel <city> [checkin] [checkout]` - Search Booking.com (with Genius Lv3 discounts)
- `/agoda <city> [checkin] [checkout]` - Search Agoda lodging (with AgodaVIP discounts)
- `/council <question>` - Ask the Claude & DeepSeek AI Travel Council
- `/status` - Check authentication status for all services
- `/help` - Show this help menu

*Or simply type any message to chat directly with the Antigravity Agent!*
"""
                await cl.Message(content=help_md).send()
                return

            elif cmd == "/trips":
                res = await handle_trips_list()
                await cl.Message(content=res).send()
                return

            elif cmd in ("/hotels", "/compare"):
                res = await handle_compare_hotels(args)
                await cl.Message(content=res).send()
                return

            elif cmd in ("/hotel", "/booking"):
                res = await handle_booking_search(args)
                await cl.Message(content=res).send()
                return

            elif cmd == "/agoda":
                res = await handle_agoda_search(args)
                await cl.Message(content=res).send()
                return

            elif cmd == "/council":
                res = await handle_council_query(args)
                await cl.Message(content=res).send()
                return

            elif cmd == "/status":
                res = await handle_status()
                await cl.Message(content=res).send()
                return

        # 2. General Agent Execution
        await run_agy_agent(text)
