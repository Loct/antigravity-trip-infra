#!/usr/bin/env bash
set -e

CONTAINER_NAME="antigravity-wanderlog"

echo "=========================================================="
echo "         Antigravity Remote Control Status & Start        "
echo "=========================================================="

if ! docker info >/dev/null 2>&1; then
  echo "[!] Error: Docker daemon is not running."
  exit 1
fi

if ! docker compose ps -q "$CONTAINER_NAME" 2>/dev/null | grep -q .; then
  echo "[-] Container is not running. Starting container..."
  docker compose up -d --build
fi

echo "[-] Checking Remote Control daemon inside container..."
if docker compose exec -T "$CONTAINER_NAME" pgrep -f "remote-control serve" >/dev/null 2>&1; then
  echo "[-] Remote Control daemon is already RUNNING."
else
  echo "[-] Launching Remote Control daemon in permissive mode..."
  docker compose exec -d "$CONTAINER_NAME" bash -c "agy --dangerously-skip-permissions remote-control serve > /root/.gemini/antigravity-cli/remote-control.log 2>&1"
  sleep 3
fi

echo ""
echo "[-] Latest Connection Status:"
docker compose exec -T "$CONTAINER_NAME" bash -c 'grep -E "Connection status|authenticated as|Starting V2 remote" /root/.gemini/antigravity-cli/cli.log 2>/dev/null | tail -n 5' || true

echo ""
echo "=========================================================="
echo "✅ Remote Control is ACTIVE!"
echo ""
echo "How to connect:"
echo "  1. Open https://antigravity.google.com/ in your browser"
echo "     (or the Antigravity Desktop App)."
echo "  2. Sign in with: loctran01@gmail.com"
echo "  3. You will see your remote container instance listed and ready!"
echo "=========================================================="
