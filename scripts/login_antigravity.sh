#!/usr/bin/env bash
set -e

CONTAINER_NAME="antigravity-wanderlog"

echo "=========================================================="
echo "          Antigravity CLI Authentication Helper           "
echo "=========================================================="

# Check if docker is running
if ! docker info >/dev/null 2>&1; then
  echo "[!] Error: Docker daemon is not running. Please start Docker first."
  exit 1
fi

# Ensure container is up
if ! docker compose ps -q "$CONTAINER_NAME" 2>/dev/null | grep -q .; then
  echo "[-] Starting $CONTAINER_NAME container in background..."
  docker compose up -d
fi

echo ""
echo "How Antigravity CLI Authentication Works:"
echo "  1. We will launch 'agy' inside the container in interactive mode."
echo "  2. If not yet signed in, 'agy' will display a Google OAuth URL in the terminal."
echo "  3. Open that URL in your browser and log in with your Google account."
echo "  4. Once confirmed, your session token is permanently saved in the"
echo "     'gemini_data' persistent Docker volume."
echo "  5. Press Ctrl+D twice (or type /exit) when you are done to exit the TUI."
echo ""
read -r -p "Press [Enter] to launch Antigravity CLI..." || true

echo "[-] Launching agy inside container..."
docker compose exec -it "$CONTAINER_NAME" agy

echo ""
echo "=========================================================="
echo "Checking Antigravity Remote Control Status:"
echo "=========================================================="
docker compose exec "$CONTAINER_NAME" agy remote-control status || true

echo ""
echo "[-] You can connect to this instance from your Antigravity Desktop app or IDE"
echo "    via Remote Control using the instance name shown above."
echo "=========================================================="
