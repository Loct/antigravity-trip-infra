#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "    Starting Remote Antigravity & Wanderlog Environment   "
echo "=========================================================="

# 1. Setup Wanderlog Credentials
mkdir -p /root/.config/wanderlog

export WANDERLOG_DISABLE_KEYCHAIN=1
echo "export WANDERLOG_DISABLE_KEYCHAIN=1" > /etc/profile.d/wanderlog.sh

if [ -n "${WANDERLOG_AUTH_SESSION_COOKIE:-}" ]; then
  echo "[-] Initializing Wanderlog credentials from environment..."
  cat <<EOF > /root/.config/wanderlog/credentials.json
{
  "SessionCookie": "${WANDERLOG_AUTH_SESSION_COOKIE}",
  "session_cookie": "${WANDERLOG_AUTH_SESSION_COOKIE}",
  "session": "${WANDERLOG_AUTH_SESSION_COOKIE}",
  "XSRFToken": "${WANDERLOG_AUTH_SESSION_XSRF_TOKEN:-}",
  "UserID": ""
}
EOF
  chmod 600 /root/.config/wanderlog/credentials.json

  cat <<EOF > /root/.config/wanderlog/config.yaml
auth:
  session:
    cookie: "${WANDERLOG_AUTH_SESSION_COOKIE}"
    xsrf_token: "${WANDERLOG_AUTH_SESSION_XSRF_TOKEN:-cookie_auth}"
EOF
  chmod 600 /root/.config/wanderlog/config.yaml
  
  # Ensure env is available in future interactive shells
  echo "export WANDERLOG_AUTH_SESSION_COOKIE=\"${WANDERLOG_AUTH_SESSION_COOKIE}\"" >> /etc/profile.d/wanderlog.sh
  echo "export WANDERLOG_SESSION=\"${WANDERLOG_AUTH_SESSION_COOKIE}\"" >> /etc/profile.d/wanderlog.sh
  echo "export WANDERLOG_AUTH_SESSION_XSRF_TOKEN=\"${WANDERLOG_AUTH_SESSION_XSRF_TOKEN:-}\"" >> /etc/profile.d/wanderlog.sh
  chmod +x /etc/profile.d/wanderlog.sh
  
  echo "[-] Wanderlog credentials configured successfully."
else
  if [ -f /root/.config/wanderlog/config.yaml ] || [ -f /root/.config/wanderlog/credentials.json ]; then
    echo "[-] Found existing credentials in /root/.config/wanderlog"
  else
    echo "[!] WARNING: WANDERLOG_AUTH_SESSION_COOKIE is not set."
    echo "    To authenticate, run './scripts/login_wanderlog.sh'"
    echo "    or set WANDERLOG_AUTH_SESSION_COOKIE in your .env"
  fi
fi

# 2. Setup Git & GitHub Credentials
mkdir -p /root/.config/gh /root/.config/git /root/.ssh
chmod 700 /root/.ssh 2>/dev/null || true

# Symlink ~/.gitconfig to persistent volume directory
if [ ! -L /root/.gitconfig ]; then
  touch /root/.config/git/config
  ln -sf /root/.config/git/config /root/.gitconfig
fi

# Configure safe directories to prevent dubious ownership issues with mounted repo
git config --global --add safe.directory /workspace 2>/dev/null || true
git config --global --add safe.directory '*' 2>/dev/null || true

# Ensure Git Identity (with fallback to prevent commit failures)
GIT_NAME="${GIT_USER_NAME:-$(git config --global user.name 2>/dev/null || true)}"
GIT_EMAIL="${GIT_USER_EMAIL:-$(git config --global user.email 2>/dev/null || true)}"

if [ -z "$GIT_NAME" ]; then
  GIT_NAME="Antigravity Agent"
  git config --global user.name "$GIT_NAME"
fi
if [ -z "$GIT_EMAIL" ]; then
  GIT_EMAIL="agent@antigravity.local"
  git config --global user.email "$GIT_EMAIL"
fi

# Ensure user trip output directory exists
mkdir -p /workspace/trips 2>/dev/null || true

# Optional GitHub Token
GH_AUTH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
if [ -n "$GH_AUTH_TOKEN" ]; then
  echo "[-] Initializing GitHub credentials from environment..."
  echo "$GH_AUTH_TOKEN" | gh auth login --with-token 2>/dev/null || true
  gh auth setup-git 2>/dev/null || true
  export GH_TOKEN="$GH_AUTH_TOKEN"
  export GITHUB_TOKEN="$GH_AUTH_TOKEN"
  echo "export GH_TOKEN=\"$GH_AUTH_TOKEN\"" > /etc/profile.d/github.sh
  echo "export GITHUB_TOKEN=\"$GH_AUTH_TOKEN\"" >> /etc/profile.d/github.sh
  chmod +x /etc/profile.d/github.sh
fi

# 3. Setup Booking.com Credentials
mkdir -p /root/.config/booking
if [ -n "${BOOKING_SESSION_COOKIE:-}" ]; then
  echo "[-] Initializing Booking.com session credentials from environment..."
  cat <<EOF > /root/.config/booking/credentials.json
{
  "session_cookie": "${BOOKING_SESSION_COOKIE}",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
  chmod 600 /root/.config/booking/credentials.json
fi

if [ -n "${BOOKING_API_KEY:-}" ]; then
  echo "[-] Initializing Booking.com API credentials from environment..."
  cat <<EOF > /root/.config/booking/api_config.json
{
  "api_key": "${BOOKING_API_KEY}",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
  chmod 600 /root/.config/booking/api_config.json
fi

# 4. Setup Apify Credentials (for Agoda & Google Maps lodging search)
mkdir -p /root/.config/apify
if [ -n "${APIFY_TOKEN:-}" ]; then
  echo "[-] Initializing Apify credentials from environment..."
  cat <<EOF > /root/.config/apify/credentials.json
{
  "token": "${APIFY_TOKEN}",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
  chmod 600 /root/.config/apify/credentials.json
  echo "export APIFY_TOKEN=\"${APIFY_TOKEN}\"" > /etc/profile.d/apify.sh
  chmod +x /etc/profile.d/apify.sh
fi

# 5. Verify Installed CLIs
if command -v wanderlog >/dev/null 2>&1; then
  echo "[-] Wanderlog CLI available: $(wanderlog --version 2>/dev/null || echo 'Denys Vitali wanderlog-cli')"
fi

if command -v agy >/dev/null 2>&1; then
  echo "[-] Antigravity CLI available: $(agy --version 2>/dev/null || echo 'agy installed')"
fi

if command -v git >/dev/null 2>&1; then
  echo "[-] Git available: $(git --version 2>/dev/null || echo 'git installed')"
fi

if command -v gh >/dev/null 2>&1; then
  echo "[-] GitHub CLI available: $(gh --version 2>/dev/null | head -n 1 || echo 'gh installed')"
  if gh auth status >/dev/null 2>&1; then
    echo "[-] GitHub CLI authenticated as: $(gh api user --jq .login 2>/dev/null || echo 'authenticated user')"
  fi
fi

# 4. Copy or link workspace MCP & skills if mounted
mkdir -p /root/.gemini/antigravity-cli
if [ -d /workspace ]; then
  cd /workspace
  if [ -f /workspace/mcp_config.json ]; then
    cp /workspace/mcp_config.json /root/.gemini/antigravity-cli/mcp_config.json 2>/dev/null || true
  fi
fi

# 5. Permissive Settings (Auto-approve all tools and commands)
echo "[-] Configuring permissive mode across all Antigravity settings..."
mkdir -p /root/.gemini/config/projects /root/.gemini/antigravity-cli

# A. Global config.json
cat <<EOF > /root/.gemini/config/config.json
{
  "userSettings": {
    "cliRemoteControlHostname": "${REMOTE_CONTROL_HOSTNAME:-wanderlog-agent}",
    "enableTerminalSandbox": false,
    "allowAgentAccessNonWorkspaceFiles": true,
    "allowedCommands": [
      "*"
    ],
    "globalPermissionGrants": {
      "allow": [
        "*",
        "command(*)",
        "command(regex:.*)",
        "mcp(*)",
        "read_file(*)",
        "write_file(*)",
        "read_url(*)",
        "execute_url(*)"
      ]
    }
  }
}
EOF

# B. Standalone project config (handles outside-of-project workspace)
cat <<EOF > /root/.gemini/config/projects/outside-of-project.json
{
  "id": "outside-of-project",
  "name": "Outside of Project",
  "permissionPreset": "Turbo",
  "toolPermission": "always-proceed",
  "enableTerminalSandbox": false
}
EOF

# C. CLI settings.json
cat <<EOF > /root/.gemini/antigravity-cli/settings.json
{
  "trustedWorkspaces": [
    "/workspace"
  ],
  "toolPermission": "always-proceed",
  "enableTerminalSandbox": false,
  "permissionPreset": "Turbo",
  "permissions": {
    "allow": [
      "*",
      "command(*)",
      "command(regex:.*)",
      "mcp(*)",
      "read_file(*)",
      "write_file(*)",
      "read_url(*)",
      "execute_url(*)"
    ],
    "ask": [],
    "deny": []
  }
}
EOF
cp /root/.gemini/antigravity-cli/settings.json /root/.gemini/config/settings.json 2>/dev/null || true

# Ensure interactive shells also default to permissive mode
echo "alias agy='agy --dangerously-skip-permissions'" > /etc/profile.d/permissive.sh
echo "alias agy='agy --dangerously-skip-permissions'" >> /root/.bashrc
chmod +x /etc/profile.d/permissive.sh

# 6. Remote Control
ENABLE_REMOTE_CONTROL="${ENABLE_REMOTE_CONTROL:-true}"

if [ "$ENABLE_REMOTE_CONTROL" = "true" ]; then
  echo "[-] Starting Antigravity Remote Control daemon in permissive mode..."
  agy --dangerously-skip-permissions remote-control serve > /root/.gemini/antigravity-cli/remote-control.log 2>&1 &
  DAEMON_PID=$!
  sleep 3

  if kill -0 "$DAEMON_PID" 2>/dev/null; then
    echo "[-] Remote Control daemon is RUNNING in PERMISSIVE mode (PID: $DAEMON_PID)."
    echo "[-] Connection status:"
    grep -E "Connection status|authenticated as|Starting V2 remote" /root/.gemini/antigravity-cli/cli.log 2>/dev/null | tail -n 5 || true
    echo "=========================================================="
    echo "[-] Remote Control is active, connected, and PERMISSIVE!"
    echo "    Open https://antigravity.google.com/ or your Antigravity Desktop app."
    echo "    Tool prompts (like 'ls', bash commands) will be auto-approved."
    echo "=========================================================="
  else
    echo "[!] Remote Control daemon exited early. Check logs:"
    cat /root/.gemini/antigravity-cli/remote-control.log 2>/dev/null || true
  fi
fi

# 6. Execute Command
if [ "$1" = "daemon" ] || [ -z "$1" ]; then
  echo "[-] Container ready. Running in daemon mode."
  echo "    Useful commands:"
  echo "      - Interactive CLI:  docker compose exec antigravity-wanderlog agy"
  echo "      - Wanderlog status: docker compose exec antigravity-wanderlog wanderlog status"
  echo "      - Wanderlog trips:  docker compose exec antigravity-wanderlog wanderlog trips list"
  echo "      - GitHub CLI:       docker compose exec antigravity-wanderlog gh auth status"
  echo "      - Git status:       docker compose exec antigravity-wanderlog git status"
  echo "      - Remote status:    docker compose exec antigravity-wanderlog agy remote-control status"
  echo "=========================================================="
  # Keep container running and periodically display heartbeat
  exec tail -f /dev/null
else
  exec "$@"
fi
