#!/usr/bin/env bash
set -e

CONTAINER_NAME="antigravity-wanderlog"

echo "=========================================================="
echo "               Wanderlog Authentication Helper            "
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

# Check if already authenticated
if docker compose exec -T -e WANDERLOG_DISABLE_KEYCHAIN=1 "$CONTAINER_NAME" wanderlog status >/dev/null 2>&1; then
  echo ""
  echo "✅ Wanderlog is already authenticated!"
  docker compose exec -T -e WANDERLOG_DISABLE_KEYCHAIN=1 "$CONTAINER_NAME" wanderlog status
  echo ""
  read -r -p "Do you want to re-authenticate? [y/N]: " REAUTH || true
  if [[ ! "$REAUTH" =~ ^[Yy]$ ]]; then
    echo "[-] Keeping existing Wanderlog credentials."
    exit 0
  fi
fi

echo ""
echo "Choose an authentication method:"
echo "  1) Interactive login (Email & Password)"
echo "  2) Paste browser session cookie ('connect.sid')"
echo "  3) Check current login status"
echo ""
read -r -p "Enter choice [1-3]: " CHOICE || true

case "$CHOICE" in
  1)
    echo ""
    echo "[-] Starting interactive Wanderlog login..."
    docker compose exec -it -e WANDERLOG_DISABLE_KEYCHAIN=1 "$CONTAINER_NAME" wanderlog login
    echo ""
    echo "[-] Verifying authentication status:"
    docker compose exec -e WANDERLOG_DISABLE_KEYCHAIN=1 "$CONTAINER_NAME" wanderlog status
    ;;
  2)
    echo ""
    echo "How to get your session cookie:"
    echo "  1. Open https://wanderlog.com in your web browser and MAKE SURE you are signed in"
    echo "     (you should see your account name/avatar in the top right)."
    echo "  2. Open Developer Tools (F12 or Cmd+Option+I on Mac)."
    echo "  3. Go to Application (or Storage) -> Cookies -> https://wanderlog.com"
    echo "  4. Copy the value of 'connect.sid'."
    echo ""
    read -r -p "Paste connect.sid value: " COOKIE_VAL

    # Strip any leading/trailing quotes or whitespace
    COOKIE_VAL="$(echo "$COOKIE_VAL" | sed -e 's/^[[:space:]]*["'"'"']//' -e 's/["'"'"'][[:space:]]*$//')"

    if [ -z "$COOKIE_VAL" ]; then
      echo "[!] No cookie provided. Aborting."
      exit 1
    fi

    # Update or create .env
    if [ ! -f .env ]; then
      cp .env.example .env 2>/dev/null || touch .env
    fi

    # Replace or append WANDERLOG_AUTH_SESSION_COOKIE
    if grep -q "^WANDERLOG_AUTH_SESSION_COOKIE=" .env; then
      sed -i.bak "s|^WANDERLOG_AUTH_SESSION_COOKIE=.*|WANDERLOG_AUTH_SESSION_COOKIE=\"${COOKIE_VAL}\"|" .env
      rm -f .env.bak
    else
      echo "WANDERLOG_AUTH_SESSION_COOKIE=\"${COOKIE_VAL}\"" >> .env
    fi

    echo "[-] Updated .env with your session cookie."
    echo "[-] Applying credentials to container..."
    
    # Restart container with updated env
    docker compose up -d --force-recreate

    echo ""
    echo "[-] Verifying Wanderlog status:"
    docker compose exec -T -e WANDERLOG_DISABLE_KEYCHAIN=1 "$CONTAINER_NAME" wanderlog status
    ;;
  3)
    echo ""
    echo "[-] Current Wanderlog status:"
    docker compose exec -T -e WANDERLOG_DISABLE_KEYCHAIN=1 "$CONTAINER_NAME" wanderlog status
    echo ""
    echo "[-] Trips list:"
    docker compose exec -T -e WANDERLOG_DISABLE_KEYCHAIN=1 "$CONTAINER_NAME" wanderlog trips list || true
    ;;
  *)
    echo "[!] Invalid option selected."
    exit 1
    ;;
esac

echo "=========================================================="
echo "Wanderlog setup completed!"
echo "=========================================================="
