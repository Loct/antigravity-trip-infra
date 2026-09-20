#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "      Deploying Remote Antigravity & Wanderlog            "
echo "=========================================================="

# 1. Check Docker
if ! command -v docker >/dev/null 2>&1; then
  echo "[!] Error: Docker is not installed or not in PATH."
  echo "    Please install Docker first: https://docs.docker.com/engine/install/"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "[!] Error: Docker daemon is not running. Please start Docker first."
  exit 1
fi

# 2. Check Environment
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo "[-] Creating .env from .env.example..."
    cp .env.example .env
    echo "[!] Please edit .env to set your WANDERLOG_AUTH_SESSION_COOKIE if not already set."
  else
    touch .env
  fi
fi

# Automatically register host directory in .env for self-updates
CURRENT_HOST_DIR="$(pwd)"
if grep -q "^HOST_PROJECT_DIR=" .env; then
  sed -i.bak "s|^HOST_PROJECT_DIR=.*|HOST_PROJECT_DIR=\"${CURRENT_HOST_DIR}\"|" .env 2>/dev/null || true
  rm -f .env.bak 2>/dev/null || true
else
  echo "HOST_PROJECT_DIR=\"${CURRENT_HOST_DIR}\"" >> .env
fi

# Pre-cache updater image for self-update capability
echo "[-] Ensuring self-update runner image is cached..."
docker pull docker:cli >/dev/null 2>&1 || true

# 3. Build and launch container
echo "[-] Building and starting Docker container..."
docker compose up -d --build

# 4. Make scripts executable
chmod +x scripts/*.sh 2>/dev/null || true

# 5. Check status
echo ""
echo "=========================================================="
echo "Deployment successful!"
echo "=========================================================="
echo ""
echo "Next steps:"
echo "  - To authenticate or check Wanderlog:  ./scripts/login_wanderlog.sh"
echo "  - To authenticate Antigravity CLI:     ./scripts/login_antigravity.sh"
echo "  - To authenticate GitHub CLI & Git:    ./scripts/login_github.sh"
echo "  - To authenticate Booking.com:         ./scripts/login_booking.sh"
echo "  - To check or trigger self-update:     ./scripts/self_update.sh"
echo "  - To check Remote Control status:      ./scripts/start_remote_control.sh"
echo "  - Or run the full login wizard:        ./scripts/login.sh"
echo "=========================================================="
