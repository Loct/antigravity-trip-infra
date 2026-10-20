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
echo "  1) Configure RapidAPI / Booking API Key (Recommended for Hotel Search & Rates)"
echo "  2) Configure Apify Personal API Token (Recommended fallback scraper)"
echo "  3) Configure Browser Session Cookie (for web session & personal account)"
echo "  4) Check current Booking.com configuration & connectivity status"
echo "  5) Test Hotel Search"
echo ""
read -r -p "Enter choice [1-5]: " CHOICE || true

case "$CHOICE" in
  1)
    echo ""
    echo "Enter your RapidAPI / Booking.com API Key:"
    echo "  (e.g., from RapidAPI booking-com15.p.rapidapi.com or booking-com.p.rapidapi.com)"
    read -r -s -p "Paste API Key (hidden): " API_KEY_VAL
    echo ""

    API_KEY_VAL="$(echo "$API_KEY_VAL" | tr -d '[:space:]')"

    if [ -z "$API_KEY_VAL" ]; then
      echo "[!] No API key provided. Aborting."
      exit 1
    fi

    read -r -p "RapidAPI Host [default: booking-com15.p.rapidapi.com]: " HOST_VAL
    HOST_VAL="${HOST_VAL:-booking-com15.p.rapidapi.com}"
    HOST_VAL="$(echo "$HOST_VAL" | tr -d '[:space:]')"

    if [ ! -f .env ]; then
      cp .env.example .env 2>/dev/null || touch .env
    fi

    # Set BOOKING_API_KEY
    if grep -q "^BOOKING_API_KEY=" .env; then
      sed -i.bak "s|^BOOKING_API_KEY=.*|BOOKING_API_KEY=\"${API_KEY_VAL}\"|" .env
      rm -f .env.bak
    else
      echo "BOOKING_API_KEY=\"${API_KEY_VAL}\"" >> .env
    fi

    # Set RAPIDAPI_HOST
    if grep -q "^RAPIDAPI_HOST=" .env; then
      sed -i.bak "s|^RAPIDAPI_HOST=.*|RAPIDAPI_HOST=\"${HOST_VAL}\"|" .env
      rm -f .env.bak
    else
      echo "RAPIDAPI_HOST=\"${HOST_VAL}\"" >> .env
    fi

    docker compose exec -T "$SERVICE_NAME" bash -c "mkdir -p /root/.config/booking && cat <<EOF > /root/.config/booking/api_config.json
{
  \"api_key\": \"${API_KEY_VAL}\",
  \"rapidapi_host\": \"${HOST_VAL}\",
  \"updated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
}
EOF
chmod 600 /root/.config/booking/api_config.json"

    echo "[-] Saved Booking.com API key and host to .env and /root/.config/booking/api_config.json."
    ;;

  2)
    echo ""
    echo "How to get your Apify API Token:"
    echo "  1. Sign in or sign up at https://console.apify.com"
    echo "  2. Go to Settings > Integrations (https://console.apify.com/account#/integrations)"
    echo "  3. Under 'Personal API tokens', copy your token"
    echo ""
    read -r -s -p "Paste Apify API Token (hidden): " APIFY_VAL
    echo ""

    APIFY_VAL="$(echo "$APIFY_VAL" | tr -d '[:space:]')"

    if [ -z "$APIFY_VAL" ]; then
      echo "[!] No token provided. Aborting."
      exit 1
    fi

    if [ ! -f .env ]; then
      cp .env.example .env 2>/dev/null || touch .env
    fi

    if grep -q "^APIFY_TOKEN=" .env; then
      sed -i.bak "s|^APIFY_TOKEN=.*|APIFY_TOKEN=\"${APIFY_VAL}\"|" .env
      rm -f .env.bak
    else
      echo "APIFY_TOKEN=\"${APIFY_VAL}\"" >> .env
    fi

    docker compose exec -T "$SERVICE_NAME" bash -c "mkdir -p /root/.config/apify && cat <<EOF > /root/.config/apify/credentials.json
{
  \"token\": \"${APIFY_VAL}\",
  \"updated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
}
EOF
chmod 600 /root/.config/apify/credentials.json"

    echo "[-] Saved Apify API token to .env and /root/.config/apify/credentials.json."
    ;;

  3)
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
      echo "BOOKING_SESSION_COOKIE=\"${COOKIE_VAL}\"" >> .env
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

  4)
    echo ""
    echo "[-] Checking Booking.com Configuration Status:"
    docker compose exec -T "$SERVICE_NAME" uv run scripts/booking.py status
    ;;

  5)
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
