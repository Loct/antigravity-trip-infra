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
- 🤖 **Native Antigravity MCP Server**: The `wanderlog` CLI acts as an MCP server (`wanderlog mcp --enable-write`), giving Antigravity first-class tools for trip operations.
- 🐙 **Git & GitHub CLI Integration**: Full `git` and `gh` CLI capabilities preinstalled with persistent credentials (`github_data`, `git_data`, `ssh_data`) and Git credential helper setup.
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
  1. Browser session cookie (`bkng_sso_session` / `bkng`) for account reservations.
  2. API Key for programmatic hotel search and rates.

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
