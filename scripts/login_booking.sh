#!/usr/bin/env bash
set -e

SERVICE_NAME="antigravity-wanderlog"

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
echo "  1) Configure Browser Session Cookie (for account bookings & reservations)"
echo "  2) Configure API Key (for automated hotel search & rates)"
echo "  3) Check current Booking.com configuration status"
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

    # Clean whitespace and quotes
    COOKIE_VAL="$(echo "$COOKIE_VAL" | sed -e 's/^[[:space:]]*["'"'"']//' -e 's/["'"'"'][[:space:]]*$//')"

    if [ -z "$COOKIE_VAL" ]; then
      echo "[!] No cookie provided. Aborting."
      exit 1
    fi

    # Update or create .env
    if [ ! -f .env ]; then
      cp .env.example .env 2>/dev/null || touch .env
    fi

    if grep -q "^BOOKING_SESSION_COOKIE=" .env; then
      sed -i.bak "s|^BOOKING_SESSION_COOKIE=.*|BOOKING_SESSION_COOKIE=\"${COOKIE_VAL}\"|" .env
      rm -f .env.bak
    else
      echo "BOOKING_SESSION_COOKIE=\"${COOKIE_VAL}\"" >> .env
    fi

    # Save to container's persistent config directory
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
    echo "Enter your Booking.com API Key (or RapidAPI Booking.com key):"
    read -r -s -p "Paste API Key (hidden): " API_KEY_VAL
    echo ""

    API_KEY_VAL="$(echo "$API_KEY_VAL" | tr -d '[:space:]')"

    if [ -z "$API_KEY_VAL" ]; then
      echo "[!] No API key provided. Aborting."
      exit 1
    fi

    if [ ! -f .env ]; then
      cp .env.example .env 2>/dev/null || touch .env
    fi

    if grep -q "^BOOKING_API_KEY=" .env; then
      sed -i.bak "s|^BOOKING_API_KEY=.*|BOOKING_API_KEY=\"${API_KEY_VAL}\"|" .env
      rm -f .env.bak
    else
      echo "BOOKING_API_KEY=\"${API_KEY_VAL}\"" >> .env
    fi

    docker compose exec -T "$SERVICE_NAME" bash -c "mkdir -p /root/.config/booking && cat <<EOF > /root/.config/booking/api_config.json
{
  \"api_key\": \"${API_KEY_VAL}\",
  \"updated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
}
EOF
chmod 600 /root/.config/booking/api_config.json"

    echo "[-] Saved Booking.com API key to .env and /root/.config/booking/api_config.json."
    ;;
  3)
    echo ""
    echo "[-] Checking Booking.com Configuration Status:"
    docker compose exec -T "$SERVICE_NAME" bash -c '
      if [ -f /root/.config/booking/credentials.json ]; then
        echo "✅ Session Cookie credentials file exists."
      else
        echo "[-] No session credentials file found in /root/.config/booking/"
      fi
      if [ -f /root/.config/booking/api_config.json ]; then
        echo "✅ API Key credentials file exists."
      else
        echo "[-] No API key configuration found in /root/.config/booking/"
      fi
    '
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
