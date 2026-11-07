#!/usr/bin/env bash
set -e

SERVICE_NAME="antigravity-wanderlog"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================================="
echo "          Booking.com Authentication & Setup Helper       "
echo "=========================================================="

# Check if docker is running
if ! docker info >/dev/null 2>&1; then
  echo "[!] Error: Docker daemon is not running. Please start Docker first."
  exit 1
fi

# Ensure container is up
if ! docker compose ps -q "$SERVICE_NAME" 2>/dev/null | grep -q .; then
  echo "[-] Starting container in background..."
  docker compose up -d
fi

echo ""
echo "Choose a setup method for Booking.com:"
echo "  1) Configure Browser Session Cookie (Recommended & Primary Authentication)"
echo "  2) Check current Booking.com configuration & connectivity status"
echo "  3) Test Hotel Search"
echo ""
read -r -p "Enter choice [1-3]: " CHOICE || true

case "$CHOICE" in
  1)
    echo ""
    echo "How to get your Booking.com session cookie:"
    echo "  1. Open https://www.booking.com in your browser and ensure you are logged in."
    echo "  2. Open Developer Tools (F12 or Cmd+Option+I)."
    echo "  3. Go to Application / Storage -> Cookies -> https://www.booking.com"
    echo "  4. Copy the value of 'bkng_sso_session' (or 'bkng')."
    echo ""
    read -r -p "Paste Booking.com session cookie: " COOKIE_VAL

    COOKIE_VAL="$(echo "$COOKIE_VAL" | sed -e 's/^[[:space:]]*["'"'"']//' -e 's/["'"'"'][[:space:]]*$//')"

    if [ -z "$COOKIE_VAL" ]; then
      echo "[!] No cookie provided. Aborting."
      exit 1
    fi

    if [ ! -f .env ]; then
      cp .env.example .env 2>/dev/null || touch .env
    fi

    if grep -q "^BOOKING_SESSION_COOKIE=" .env; then
      sed -i.bak "s|^BOOKING_SESSION_COOKIE=.*|BOOKING_SESSION_COOKIE=\"${COOKIE_VAL}\"|" .env
      rm -f .env.bak
    else
      echo "BOOKING_SESSION_COOKIE=\"${COOKIE_VAL}\"" >>.env
    fi

    docker compose exec -T "$SERVICE_NAME" bash -c "mkdir -p /root/.config/booking && cat <<EOF > /root/.config/booking/credentials.json
{
  \"session_cookie\": \"${COOKIE_VAL}\",
  \"updated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
}
EOF
chmod 600 /root/.config/booking/credentials.json"

    echo "[-] Saved Booking.com session cookie to .env and /root/.config/booking/credentials.json."
    ;;

  2)
    echo ""
    echo "[-] Checking Booking.com Configuration Status:"
    docker compose exec -T "$SERVICE_NAME" uv run scripts/booking.py status
    ;;

  3)
    echo ""
    read -r -p "Enter destination to test [default: Tokyo]: " TEST_DEST || true
    TEST_DEST="${TEST_DEST:-Tokyo}"
    echo "[-] Running test search for '$TEST_DEST'..."
    docker compose exec -T "$SERVICE_NAME" uv run scripts/booking.py search -l "$TEST_DEST" --limit 3
    ;;

  *)
    echo "[!] Invalid choice."
    exit 1
    ;;
esac

echo ""
echo "=========================================================="
echo "Booking.com setup completed!"
echo "Credentials are saved in persistent storage."
echo "=========================================================="
