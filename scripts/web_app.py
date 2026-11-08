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
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    """Initialize SQLite database with required Chainlit tables and adapters."""
    path = Path(db_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.register_adapter(list, json.dumps)
    with sqlite3.connect(str(path)) as conn:
        conn.executescript(CHAINLIT_SQLITE_SCHEMA)


# ----------------------------------------------------------------------
# Authentication & User Management
# ----------------------------------------------------------------------
AUTH_PASSWORD = os.getenv("WEB_AUTH_PASSWORD", "").strip()

if cl is not None:
    if not os.getenv("CHAINLIT_AUTH_SECRET"):
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
        cl.user_session.set("history", thread.get("messages", []))
        cl.user_session.set("agy_conversation_id", thread.get("metadata", {}).get("agy_conversation_id"))


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
        lines.append("- ℹ️ **Booking.com**: No session cookie set (standard public pricing)")

    # 4. AI Council (Claude & DeepSeek)
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


async def handle_booking_search(args: str) -> str:
    """Execute Booking.com search via scripts/booking.py."""
    parts = args.strip().split()
    if not parts:
        return "⚠️ **Usage**: `/hotel <city> [checkin] [checkout]` (e.g. `/hotel Tokyo 2026-04-01 2026-04-05`)"

    city = parts[0]
    checkin = parts[1] if len(parts) > 1 else None
    checkout = parts[2] if len(parts) > 2 else None

    cmd = ["uv", "run", str(SCRIPT_DIR / "booking.py"), city]
    if checkin:
        cmd.extend(["--checkin", checkin])
    if checkout:
        cmd.extend(["--checkout", checkout])

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
                return f"⚠️ **Hotel search error**:\n```text\n{err or output}\n```"
        except Exception as e:
            step.output = str(e)
            return f"⚠️ Error executing hotel search: {e}"


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
- `/hotel <city> [checkin] [checkout]` - Search Booking.com (with Genius Lv3 discounts)
- `/agoda <city> [checkin] [checkout]` - Search Agoda lodging
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

            elif cmd in ("/hotel", "/booking"):
                res = await handle_booking_search(args)
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
