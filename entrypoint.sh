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

# 2. Verify Wanderlog CLI
if command -v wanderlog >/dev/null 2>&1; then
  echo "[-] Wanderlog CLI available: $(wanderlog --version 2>/dev/null || echo 'Denys Vitali wanderlog-cli')"
fi

# 3. Verify Antigravity CLI
if command -v agy >/dev/null 2>&1; then
  echo "[-] Antigravity CLI available: $(agy --version 2>/dev/null || echo 'agy installed')"
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
  echo "      - Remote status:    docker compose exec antigravity-wanderlog agy remote-control status"
  echo "=========================================================="
  # Keep container running and periodically display heartbeat
  exec tail -f /dev/null
else
  exec "$@"
fi
