# Remote Antigravity CLI with Wanderlog Integration

A containerized deployment running the **Google Antigravity CLI (`agy`)** with **Remote Control** enabled and direct integration with the **Wanderlog CLI** and native **Model Context Protocol (MCP)** server.

Allows you to manage, create, and organize [Wanderlog](https://wanderlog.com) trips and day-by-day travel itineraries remotely using conversational AI.

---

## Architecture Overview

```
+-----------------------------------------------------------------------------------+
| Docker Container: antigravity-wanderlog                                           |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Antigravity CLI (`agy`)                                                     |  |
|  | - Persistent Remote Control Daemon (`agy remote-control start`)              |  |
|  | - Native MCP Client connecting to Wanderlog                                |  |
|  +-------------------------------------+---------------------------------------+  |
|                                        | (stdio MCP / CLI invocation)             |
|                                        v                                          |
|  +-----------------------------------------------------------------------------+  |
|  | Wanderlog CLI & MCP Server (`wanderlog`)                                    |  |
|  | - Built from denysvitali/wanderlog-cli with MCP support                     |  |
|  | - Session auth via WANDERLOG_AUTH_SESSION_COOKIE                             |  |
|  | - Full CRUD: trips, places, flights, lodgings, transit, notes, budgets      |  |
|  +-------------------------------------+---------------------------------------+  |
|                                        |                                          |
|                                        v                                          |
|                               Wanderlog Cloud API                                 |
+-----------------------------------------------------------------------------------+
                                         ^
                                         | Secure Remote Control Tunnel
                                         v
                      Antigravity Desktop App / IDE / Web Portal
```

---

## Features

- 🌍 **Full Trip Management**: Create, list, copy, and delete trips.
- 📍 **Place & Itinerary Building**: Add attractions, restaurants, and sights with coordinates, addresses, and scheduled visit times.
- ✈️ **Travel Reservations**: Add and manage flights, hotels, and train journeys.
- 🏨 **Booking.com Lodging Search & Integration**: Search, filter, and compare hotel and lodging accommodations via Booking.com (RapidAPI, Apify residential proxy scraper, or web fallback) and link selected stays directly to Wanderlog trips using `uv run scripts/booking.py`.
- 🏮 **Agoda Lodging Search & Integration**: Search, filter, and compare hotel room rates and properties via Agoda (RapidAPI, Apify scraper actor, or direct web search) and link selected stays directly to Wanderlog trips using `uv run scripts/agoda.py`.
- 🧠 **DeepSeek Itinerary Validator (Free OpenRouter Tier)**: Validate and double-check itineraries for scheduling feasibility, geographic backtracking, lodging gaps, and flight buffers using DeepSeek (DeepSeek-R1 / DeepSeek-Chat) via free OpenRouter or custom providers (`uv run scripts/deepseek_validator.py`).
- 🎭 **Claude Itinerary Validator & Multi-Model Cross-Checking**: Audit itineraries using Anthropic Claude (Claude 3.7 Sonnet with extended thinking, Claude 3.5 Sonnet, Claude 3.5 Haiku) via `uv run scripts/claude_validator.py` and run simultaneous **Dual AI Cross-Checks** comparing Claude and DeepSeek consensus via `uv run scripts/cross_check_validator.py`.
- 🤖 **Native Antigravity MCP Server**: The `wanderlog` CLI acts as an MCP server (`wanderlog mcp --enable-write`), giving Antigravity first-class tools for trip operations.
- 🐙 **Git & GitHub CLI Integration**: Full `git` and `gh` CLI capabilities preinstalled with persistent credentials (`github_data`, `git_data`, `ssh_data`) and Git credential helper setup.
- 🐍 **Python & uv Environment**: Modern, high-performance Python runtime managed by `uv` with Python 3.12 preinstalled for fast dependency management and script execution.
- 🔗 **Remote Control**: Connects seamlessly with the Antigravity Desktop app or web portal without needing manual SSH or open inbound ports.
- 💾 **State Persistence**: Docker volumes persist Antigravity session history (`gemini_data`), Wanderlog credentials (`wanderlog_data`), and GitHub/Git configuration (`github_data`, `git_data`, `ssh_data`).

---

## Getting Started

### 1. Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/) installed on your host machine or remote server.

### 2. Login & Authentication (Automated Scripts)

We provide interactive scripts to log in to Wanderlog, Antigravity, and GitHub:

#### All-in-One Setup Wizard
Run the unified login wizard to authenticate all services in sequence:
```bash
./scripts/login.sh
```

#### Individual Service Logins
- **Wanderlog Login**:
  ```bash
  ./scripts/login_wanderlog.sh
  ```
  Offers two options:
  1. *Interactive*: Enter your Wanderlog email and password directly.
  2. *Browser Cookie*: Paste your `connect.sid` cookie (automatically saves to `.env` and restarts container).

- **Antigravity CLI Login**:
  ```bash
  ./scripts/login_antigravity.sh
  ```
  Launches `agy` in interactive mode. If you are not yet authenticated, it displays a Google OAuth URL. Open the link in your browser to sign in with your Google account. Your session is saved permanently to the `gemini_data` volume.

- **GitHub CLI & Git Login**:
  ```bash
  ./scripts/login_github.sh
  ```
  Provides easy options to:
  1. Authenticate via web browser / device code (`gh auth login`).
  2. Paste a GitHub Personal Access Token (PAT).
  3. Configure Git author identity (`user.name` & `user.email`).
  4. Check current authentication and git config status.

- **Booking.com Setup**:
  ```bash
  ./scripts/login_booking.sh
  ```
  Provides options to configure:
  1. RapidAPI / Booking.com API Key for fast structured hotel search and rates.
  2. Apify Personal API Token for reliable residential-proxy scraper fallback (`voyager/booking-scraper`).
  3. Browser session cookie (`bkng_sso_session` / `bkng`) for account access.
  4. Integration and credentials status verification.
  5. Test hotel search.

- **Agoda Setup**:
  ```bash
  ./scripts/login_agoda.sh
  ```
  Provides options to configure:
  1. RapidAPI / Agoda API Key for structured hotel search and rates.
  2. Apify Personal API Token for Agoda scraper actor fallback (`tri_angle/agoda-scraper`).
  3. Browser session cookie (`AGODA_SESSION_COOKIE`) for web access.
  4. Integration and credentials status verification.
  5. Test hotel search.

- **DeepSeek & OpenRouter Validator Setup**:
  ```bash
  ./scripts/login_deepseek.sh
  ```
  Provides options to configure:
  1. OpenRouter (Recommended: 100% Free DeepSeek-R1 & Chat, no credit card required).
  2. Groq (Free fast inference: `deepseek-r1-distill-llama-70b`).
  3. Official DeepSeek API Key (`deepseek-reasoner`).
  4. Local Ollama (offline).
  5. Connection check and test audit on sample trip (`trips/southern_italy.json`).

- **Anthropic Claude & Cross-Checker Setup**:
  ```bash
  ./scripts/login_claude.sh
  ```
  Provides options to configure:
  1. Official Anthropic API Key (`sk-ant-...`) with Claude 3.7 Sonnet (Extended Thinking), Claude 3.5 Sonnet, or Claude 3.5 Haiku.
  2. OpenRouter Claude configuration.
  3. Check current configuration & test connection.
  4. Run test audit on sample trip (`trips/southern_italy.json`).
  5. Run dual cross-check test (Claude + DeepSeek) on sample trip.

---

### 3. Build & Start the Container (Manual)

If you prefer to start the container manually without the wizard:
```bash
cp .env.example .env
# Edit .env and set WANDERLOG_AUTH_SESSION_COOKIE
docker compose up -d --build
```

View the container logs to verify startup:

```bash
docker compose logs -f
```

---

## Connecting with Antigravity

### Option A: Antigravity Remote Control (Recommended)

When the container starts with `ENABLE_REMOTE_CONTROL=true`, the Antigravity Remote Control daemon is automatically registered and started.

1. Check your remote control status and machine identifier:
   ```bash
   docker compose exec antigravity-wanderlog agy remote-control status
   ```
2. In your local **Antigravity Desktop App** or **IDE**, open **Settings > Remote Control** or use the remote machine switcher to connect to the container instance.
3. You now have full untethered control of the remote agent with direct access to all Wanderlog tools!

### Option B: Interactive Terminal User Interface (TUI)

You can also launch and interact directly with the Antigravity TUI inside the container:

```bash
docker compose exec antigravity-wanderlog agy
```

Press `Ctrl+D` twice or type `/exit` to exit the session.

---

## Deploying Multiple Instances on the Same Server

You can run multiple independent instances on the same server (e.g., for different trips, workspaces, or user accounts) without port conflicts because the container connects outward via Remote Control websockets.

To deploy a second instance:
1. Extract or clone the deployment into a separate folder (e.g. `/opt/wanderlog-trip2`):
   ```bash
   mkdir -p /opt/wanderlog-trip2 && cd /opt/wanderlog-trip2
   tar -xzf /path/to/gemini-wanderlog-release.tar.gz
   ```
2. Copy and configure its `.env`:
   ```bash
   cp .env.example .env
   ```
3. Customize the instance variables in `.env`:
   ```env
   # Unique Compose project name (isolates volumes and network)
   COMPOSE_PROJECT_NAME=wanderlog-trip2

   # Unique container name (Docker requires globally unique container names)
   CONTAINER_NAME=antigravity-wanderlog-trip2

   # Hostname shown in https://antigravity.google.com/
   REMOTE_CONTROL_HOSTNAME=wanderlog-trip2

   # Wanderlog session cookie for this instance
   WANDERLOG_AUTH_SESSION_COOKIE="your-second-session-cookie"
   ```
4. Start the instance:
   ```bash
   ./deploy.sh
   ```
Each instance will maintain its own isolated Wanderlog session, Google authentication state, and workspace files.

---

## Autonomous Self-Updating (Without Server SSH Access)

Because the container has Git access and the Docker daemon socket mounted, users connected exclusively through **Antigravity Remote** (`https://antigravity.google.com`) can instruct the agent to update and redeploy itself without needing SSH or server terminal access.

### How It Works:
1. **Workspace / Skills / Rules Updates**:
   Prompting Antigravity with *"Update yourself from GitHub"* causes it to run `git pull origin main`. Because `/workspace` is bind-mounted, changes to skills, rules, and scripts apply **immediately in real time**.
2. **Antigravity CLI Updates (`agy`)**:
   `self_update.sh` automatically checks and updates the Antigravity CLI (`agy update`). If a new CLI version is downloaded and installed, it automatically restarts the container via a background sibling container so the updated binary is loaded without manual intervention.
3. **Docker Environment Updates (`Dockerfile`, `compose`, new packages)**:
   When infrastructure files change, Antigravity executes `./scripts/self_update.sh`.
   The script spawns a lightweight, detached background updater container (`docker:cli`) on the host Docker daemon.
   - The background container pulls, rebuilds, and restarts the environment.
   - The old container cleanly stops, and the new container starts with updated dependencies.
   - Antigravity Remote Control automatically reconnects in **15–30 seconds**.

### Commands to Give Antigravity in Chat:
- *"Check if there are any updates on GitHub."*
- *"Update yourself from GitHub and redeploy if needed."*
- *"Run self update."*
- *"Force a rebuild and redeploy of the Docker container."*

You can also run the script manually from inside the container:
```bash
# Check for updates without applying
./scripts/self_update.sh --check

# Check/pull Git updates, update agy CLI, and auto-restart if needed
./scripts/self_update.sh

# Force restart to reload binary
./scripts/self_update.sh --restart

# Force a full Docker rebuild and redeploy
./scripts/self_update.sh --rebuild
```

---

## Testing & CLI Diagnostics

A built-in diagnostic script is provided to verify Wanderlog connectivity and list your trips:

```bash
docker compose exec antigravity-wanderlog scripts/test_wanderlog.sh
```

Or run `wanderlog` commands directly:

```bash
# Check status
docker compose exec antigravity-wanderlog wanderlog status

# List your trips
docker compose exec antigravity-wanderlog wanderlog trips list

# View trip details in Markdown format
docker compose exec antigravity-wanderlog wanderlog trips show <trip-id> --details --output markdown
```

---

## Booking.com Lodging Search & Wanderlog Integration

The workspace includes a high-performance, uv-powered Booking.com integration CLI (`scripts/booking.py`) and agent skill (`.agents/skills/booking/SKILL.md`). It supports hybrid querying via RapidAPI (structured REST API), Apify cloud scraper actor (`voyager/booking-scraper`), or direct session cookies.

### Commands:

```bash
# Check status of configured Booking.com providers and Wanderlog CLI
uv run scripts/booking.py status

# Basic hotel search (defaults to +14 to +18 days)
uv run scripts/booking.py search -l "Tokyo"

# Search with custom dates, guests, currency, and rating filter
uv run scripts/booking.py search -l "Kyoto" -i 2026-11-01 -o 2026-11-05 -g 2 -c USD --min-rating 8.5

# Search and interactively select a property to add to a Wanderlog trip
uv run scripts/booking.py search -l "Paris" -i 2026-12-01 -o 2026-12-05 --add-to-trip <trip-key>

# Output as JSON for programmatic parsing
uv run scripts/booking.py search -l "Rome" -f json
```

> [!IMPORTANT]
> **Trip Mutation Policy**: Whenever adding lodging to a Wanderlog trip, confirmation is always required before mutating the itinerary. The exact property details, dates, and trip key are displayed for user approval.

---

## Agoda Lodging Search & Wanderlog Integration

The workspace includes a high-performance, uv-powered Agoda integration CLI (`scripts/agoda.py`) and agent skill (`.agents/skills/agoda/SKILL.md`). It supports hybrid querying via RapidAPI (structured REST API), Apify cloud scraper actor (`tri_angle/agoda-scraper`), or direct Agoda web search.

### Commands:

```bash
# Check status of configured Agoda providers and Wanderlog CLI
uv run scripts/agoda.py status

# Basic hotel search (defaults to +14 to +18 days)
uv run scripts/agoda.py search -l "Tokyo"

# Search with custom dates, guests, currency, and rating filter
uv run scripts/agoda.py search -l "Bangkok" -i 2026-11-01 -o 2026-11-05 -g 2 -c USD --min-rating 8.5 --max-price 250

# Search and interactively select a property to add to a Wanderlog trip
uv run scripts/agoda.py search -l "Phuket" -i 2026-12-01 -o 2026-12-05 --add-to-trip <trip-key>

# Output as JSON for programmatic parsing
uv run scripts/agoda.py search -l "Singapore" -f json
```

> [!IMPORTANT]
> **Trip Mutation Policy**: Whenever adding lodging to a Wanderlog trip, confirmation is always required before mutating the itinerary. The exact property details, dates, and trip key are displayed for user approval.

## DeepSeek Wanderlog Itinerary Validator (Free OpenRouter Integration)

The workspace includes an itinerary validation CLI (`scripts/deepseek_validator.py`) and agent skill (`.agents/skills/deepseek-validator/SKILL.md`) powered by DeepSeek via free OpenRouter tier (or Groq, Ollama, official DeepSeek API).

It provides automated second-opinion audits on Wanderlog trips to catch:
- ⏱️ **Schedule Feasibility & Timing**: Activity duration realism, opening hours (museum closures), meal buffers.
- 🗺️ **Geographic Routing & Backtracking**: Pinpoints zig-zagging across cities and groups sights by neighborhood.
- 🏨 **Lodging Continuity**: Catches uncovered nights (no hotel booked) and check-in/out awkward gaps.
- ✈️ **Transit & Flight Buffers**: 2–3 hour airport arrival margins and transit realism.
- 🏃 **Pacing**: Balances overloaded vs empty days.

### Usage Examples:

```bash
# Set up free OpenRouter API key (sk-or-v1-...)
./scripts/login_deepseek.sh

# Audit a trip by Wanderlog trip ID or URL (uses deepseek-r1 chain-of-thought)
uv run scripts/deepseek_validator.py <trip_id>

# Fast check mode (uses deepseek-chat)
uv run scripts/deepseek_validator.py <trip_id> --quick

# Audit local trip JSON file
uv run scripts/deepseek_validator.py trips/southern_italy.json

# Save audit report to markdown
uv run scripts/deepseek_validator.py <trip_id> --save-report trips/audit_report.md

# Cross-check with Claude
uv run scripts/deepseek_validator.py <trip_id> --cross-check

# Test connection to configured provider
uv run scripts/deepseek_validator.py --test
```

---

## Claude Wanderlog Itinerary Validator & Dual AI Cross-Checking

The workspace also integrates **Anthropic Claude** (`scripts/claude_validator.py`) and a unified multi-model cross-checker (`scripts/cross_check_validator.py`) with skill support (`.agents/skills/claude-validator/SKILL.md`).

Key capabilities:
- 🎭 **Claude 3.7 Sonnet Extended Thinking**: Leverages Anthropic's hybrid reasoning engine to analyze complex schedules, opening hours, and pacing.
- ⚖️ **Dual AI Cross-Checking**: Compares independent analyses from both Claude and DeepSeek to isolate unanimous consensus issues (high priority) and model-specific nuances.
- ⚡ **Haiku Quick Mode**: Low-latency, budget-friendly validation using `claude-3-5-haiku-20241022`.

### Usage Examples:

```bash
# Configure Anthropic API key (sk-ant-...) and preferred model
./scripts/login_claude.sh

# Audit a trip using Claude
uv run scripts/claude_validator.py <trip_id>

# Fast check mode with Claude Haiku
uv run scripts/claude_validator.py <trip_id> --quick

# Cross-check itinerary with BOTH Claude and DeepSeek
uv run scripts/cross_check_validator.py <trip_id>
# Or via flag on either validator:
uv run scripts/claude_validator.py <trip_id> --cross-check
uv run scripts/deepseek_validator.py <trip_id> --cross-check

# Save cross-check consensus report
uv run scripts/cross_check_validator.py <trip_id> --save-report trips/cross_check.md

# Test connectivity for Claude (or both models)
uv run scripts/claude_validator.py --test
uv run scripts/cross_check_validator.py --test
```

---

## 🏛️ Conversational AI Travel Council (Multi-AI Co-Planning)

Rather than only generating static markdown reports, Antigravity and the user can query multiple external AIs (Claude and DeepSeek) **conversationally** to debate route options, double-check specific days, and cross-examine dining and transit logistics.

Supported modes via `scripts/ai_council.py` & `.agents/skills/ai-travel-council/SKILL.md`:
- 💬 **Targeted Questions**: Ask specific questions focused on one day or the whole trip.
- 🏛️ **Dual Council Consultation**: Queries both Claude and DeepSeek to present two independent perspectives.
- 🗣️ **Interactive Chat Session**: Engage in live multi-turn discussion in the terminal.

### Usage Examples:

```bash
# Ask both Claude and DeepSeek a focused question about Day 4
uv run scripts/ai_council.py "Is our Day 4 schedule too packed with morning travel?" --trip trips/vietnam.json --day 4

# Ask Claude specifically about restaurant recommendations for Day 2
uv run scripts/ai_council.py "Suggest authentic local dinner near Hoan Kiem" --trip <trip_id> --day 2 --ai claude

# Ask DeepSeek specifically to calculate transit and route feasibility
uv run scripts/ai_council.py "Check driving time and route between Naples and Amalfi" --trip trips/southern_italy.json --ai deepseek

# Launch interactive terminal chat with the Council
uv run scripts/ai_council.py --trip <trip_id> --interactive
```

---

## How Antigravity Interacts with Wanderlog

The workspace includes:
- **`mcp_config.json`**: Registers `wanderlog mcp --enable-write` as an MCP server. Antigravity automatically detects this and exposes tools:
  - `create_trip`
  - `list_trips`
  - `get_trip`
  - `add_place`
  - `update_place_visit_time`
  - `delete_itinerary_block`
  - `add_flight`
  - `add_lodging`
- **`.agents/skills/wanderlog/SKILL.md`**: Teaches Antigravity how to construct itineraries, structure day-by-day schedules, and format trip outputs.
- **`.agents/rules/wanderlog.md`**: Sets safety and operational rules (e.g. validating trip IDs, confirmation for destructive changes).

### Example Prompts to Give Antigravity:

- *"List all my current trips on Wanderlog."*
- *"Create a 4-day itinerary for Tokyo from October 12 to October 16, 2026."*
- *"Add Senso-ji Temple and Meiji Shrine to Day 1 of my Tokyo trip with visit times."*
- *"Add our return flight JL005 on October 16 departing at 11:30 AM."*
- *"Show me a full markdown summary of my upcoming trip."*

---

## Common Commands Cheat Sheet

| Task | Command |
|---|---|
| Start Remote Control | `./scripts/start_remote_control.sh` |
| Check Auth Status | `docker compose exec antigravity-wanderlog wanderlog status` |
| List Trips | `docker compose exec antigravity-wanderlog wanderlog trips list` |
| View Trip (JSON) | `docker compose exec antigravity-wanderlog wanderlog trips show <id> --output json` |
| View Trip (Markdown) | `docker compose exec antigravity-wanderlog wanderlog trips show <id> --details --output markdown` |
| Create Trip | `docker compose exec antigravity-wanderlog wanderlog trips create --title "Trip" --geo-id 1 --start 2026-06-01 --end 2026-06-05` |
| Add Place | `docker compose exec antigravity-wanderlog wanderlog trips edit add-place <id> --name "Place Name"` |
| Add Flight | `docker compose exec antigravity-wanderlog wanderlog trips flight add <id> --flight-number AA100 --departure-date 2026-06-01 --departure-time 08:00` |
| Add Lodging | `docker compose exec antigravity-wanderlog wanderlog trips lodging add <id> --name "Hotel" --check-in 2026-06-01 --check-out 2026-06-05` |
| Set Budget | `docker compose exec antigravity-wanderlog wanderlog trips budget set <id> --amount 2000 --currency USD` |
| GitHub Status | `docker compose exec antigravity-wanderlog gh auth status` |
| Git Status | `docker compose exec antigravity-wanderlog git status` |
| GitHub CLI Login | `./scripts/login_github.sh` |
| Start Interactive TUI | `docker compose exec antigravity-wanderlog agy` |
| Stop Container | `docker compose down` |
