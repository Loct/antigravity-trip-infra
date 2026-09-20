#!/usr/bin/env bash
set -e

SERVICE_NAME="antigravity-wanderlog"

echo "=========================================================="
echo "         Apify & Hotel Search Setup Helper                "
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
echo "Choose a setup method for Apify:"
echo "  1) Configure Apify Personal API Token (for Agoda & Multi-OTA searches)"
echo "  2) Test & Validate Apify connection"
echo "  3) Check current Apify configuration status"
echo ""
read -r -p "Enter choice [1-3]: " CHOICE || true

case "$CHOICE" in
  1)
    echo ""
    echo "How to get your Apify API Token:"
    echo "  1. Sign in or sign up at https://console.apify.com"
    echo "  2. Go to Settings > Integrations (https://console.apify.com/account#/integrations)"
    echo "  3. Under 'Personal API tokens', copy your token (e.g. apify_api_...)"
    echo ""
    read -r -s -p "Paste Apify API Token (hidden): " TOKEN_VAL
    echo ""

    TOKEN_VAL="$(echo "$TOKEN_VAL" | tr -d '[:space:]')"

    if [ -z "$TOKEN_VAL" ]; then
      echo "[!] No token provided. Aborting."
      exit 1
    fi

    echo "[-] Validating token with Apify API..."
    USER_RESP="$(curl -s -f -H "Authorization: Bearer $TOKEN_VAL" https://api.apify.com/v2/users/me 2>/dev/null || true)"

    if [ -n "$USER_RESP" ] && echo "$USER_RESP" | grep -q "username"; then
      USER_NAME="$(echo "$USER_RESP" | grep -o '"username":"[^"]*' | cut -d'"' -f4)"
      USER_EMAIL="$(echo "$USER_RESP" | grep -o '"email":"[^"]*' | cut -d'"' -f4)"
      echo "✅ Token validated successfully! Logged in as: $USER_NAME ($USER_EMAIL)"
    else
      echo "[!] Warning: Could not verify token with Apify API. Saving anyway."
    fi

    # Update or create .env
    if [ ! -f .env ]; then
      cp .env.example .env 2>/dev/null || touch .env
    fi

    if grep -q "^APIFY_TOKEN=" .env; then
      sed -i.bak "s|^APIFY_TOKEN=.*|APIFY_TOKEN=\"${TOKEN_VAL}\"|" .env
      rm -f .env.bak
    else
      echo "APIFY_TOKEN=\"${TOKEN_VAL}\"" >> .env
    fi

    # Save to container's persistent config directory
    docker compose exec -T "$SERVICE_NAME" bash -c "mkdir -p /root/.config/apify && cat <<EOF > /root/.config/apify/credentials.json
{
  \"token\": \"${TOKEN_VAL}\",
  \"updated_at\": \"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
}
EOF
chmod 600 /root/.config/apify/credentials.json"

    echo "[-] Saved APIFY_TOKEN to .env and /root/.config/apify/credentials.json."
    ;;
  2)
    echo ""
    echo "[-] Testing Apify API connectivity from container..."
    docker compose exec -T "$SERVICE_NAME" bash -c '
      APIFY_AUTH_TOKEN="${APIFY_TOKEN:-}"
      if [ -z "$APIFY_AUTH_TOKEN" ] && [ -f /root/.config/apify/credentials.json ]; then
        APIFY_AUTH_TOKEN="$(grep -o "\"token\":[ ]*\"[^\"]*" /root/.config/apify/credentials.json | cut -d"\"" -f4)"
      fi

      if [ -z "$APIFY_AUTH_TOKEN" ]; then
        echo "[!] No APIFY_TOKEN configured in environment or /root/.config/apify/credentials.json."
        exit 1
      fi

      USER_RESP="$(curl -s -f -H "Authorization: Bearer $APIFY_AUTH_TOKEN" https://api.apify.com/v2/users/me 2>/dev/null || true)"
      if [ -n "$USER_RESP" ] && echo "$USER_RESP" | grep -q "username"; then
        USER_NAME="$(echo "$USER_RESP" | grep -o "\"username\":\"[^\"]*" | cut -d"\"" -f4)"
        echo "✅ Apify connection active! User: $USER_NAME"
      else
        echo "[!] Failed to authenticate with Apify API. Please verify token."
        exit 1
      fi
    '
    ;;
  3)
    echo ""
    echo "[-] Checking Apify Configuration Status:"
    docker compose exec -T "$SERVICE_NAME" bash -c '
      if [ -f /root/.config/apify/credentials.json ]; then
        echo "✅ Apify credentials file exists (/root/.config/apify/credentials.json)."
      else
        echo "[-] No credentials file found in /root/.config/apify/"
      fi

      if [ -n "${APIFY_TOKEN:-}" ]; then
        echo "✅ APIFY_TOKEN environment variable is set in container."
      else
        echo "[-] APIFY_TOKEN environment variable is empty."
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
echo "Apify setup completed!"
echo "Credentials are saved in persistent storage."
echo "=========================================================="
