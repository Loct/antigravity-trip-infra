#!/usr/bin/env bash
set -e

SERVICE_NAME="antigravity-wanderlog"

echo "=========================================================="
echo "          Apify (Agoda & Google Maps) Setup Helper        "
echo "=========================================================="

# Helper function to detect if running inside container
is_inside_container() {
  [ -f /.dockerenv ] || [ -f /run/.containerenv ]
}

echo ""
echo "Choose a setup method for Apify:"
echo "  1) Configure Apify API Token (for Agoda & Google Maps scrapers)"
echo "  2) Test current Apify connection"
echo "  3) Check Apify configuration status"
echo ""
read -r -p "Enter choice [1-3]: " CHOICE || true

case "$CHOICE" in
  1)
    echo ""
    echo "How to get your Apify API Token:"
    echo "  1. Log in to https://console.apify.com/"
    echo "  2. Go to Settings -> Integrations -> API Tokens"
    echo "  3. Copy your Personal API token"
    echo ""
    read -r -s -p "Paste your Apify API Token (hidden): " APIFY_TOKEN_VAL
    echo ""

    APIFY_TOKEN_VAL="$(echo "$APIFY_TOKEN_VAL" | tr -d '[:space:]')"

    if [ -z "$APIFY_TOKEN_VAL" ]; then
      echo "[!] No token provided. Aborting."
      exit 1
    fi

    echo "[-] Verifying token with Apify API..."
    USER_RESP=$(curl -sSL -w "\n%{http_code}" -H "Authorization: Bearer $APIFY_TOKEN_VAL" "https://api.apify.com/v2/users/me" 2>/dev/null || true)
    HTTP_CODE=$(echo "$USER_RESP" | tail -n 1)
    BODY=$(echo "$USER_RESP" | sed '$d')

    if [ "$HTTP_CODE" != "200" ]; then
      echo "[!] Error: Apify API token verification failed (HTTP $HTTP_CODE)."
      echo "    Response: $BODY"
      echo "    Please verify your token and try again."
      exit 1
    fi

    USERNAME=$(echo "$BODY" | jq -r '.data.username // .data.email // "user"')
    echo "[-] Verified successfully! Authenticated as Apify user: $USERNAME"

    # Update or create .env
    if [ ! -f .env ]; then
      cp .env.example .env 2>/dev/null || touch .env
    fi

    if grep -q "^APIFY_TOKEN=" .env; then
      sed -i.bak "s|^APIFY_TOKEN=.*|APIFY_TOKEN=\"${APIFY_TOKEN_VAL}\"|" .env
      rm -f .env.bak
    else
      echo "APIFY_TOKEN=\"${APIFY_TOKEN_VAL}\"" >> .env
    fi

    # Save credentials into persistent directory
    if is_inside_container; then
      mkdir -p /root/.config/apify
      cat <<EOF > /root/.config/apify/credentials.json
{
  "token": "${APIFY_TOKEN_VAL}",
  "username": "${USERNAME}",
  "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
      chmod 600 /root/.config/apify/credentials.json
      echo "export APIFY_TOKEN=\"${APIFY_TOKEN_VAL}\"" > /etc/profile.d/apify.sh
      chmod +x /etc/profile.d/apify.sh
    else
      if docker compose ps -q "$SERVICE_NAME" 2>/dev/null | grep -q .; then
        docker compose exec -T "$SERVICE_NAME" bash -c "mkdir -p /root/.config/apify && cat <<EOF > /root/.config/apify/credentials.json
{
  \"token\": \"${APIFY_TOKEN_VAL}\",
  \"username\": \"${USERNAME}\",
  \"updated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
}
EOF
chmod 600 /root/.config/apify/credentials.json
echo 'export APIFY_TOKEN=\"${APIFY_TOKEN_VAL}\"' > /etc/profile.d/apify.sh
chmod +x /etc/profile.d/apify.sh"
      fi
    fi

    echo "[-] Saved Apify API token to .env and /root/.config/apify/credentials.json."
    ;;
  2)
    echo ""
    echo "[-] Testing Apify connection..."
    TOKEN="${APIFY_TOKEN:-}"
    if [ -z "$TOKEN" ] && [ -f /root/.config/apify/credentials.json ]; then
      TOKEN=$(jq -r '.token // empty' /root/.config/apify/credentials.json 2>/dev/null || true)
    fi
    if [ -z "$TOKEN" ] && [ -f .env ]; then
      TOKEN=$(grep "^APIFY_TOKEN=" .env | cut -d '=' -f2- | tr -d '"' | tr -d "'" | tr -d ' ' || true)
    fi

    if [ -z "$TOKEN" ]; then
      echo "[!] No Apify token found in environment, .env, or credentials.json."
      exit 1
    fi

    RESP=$(curl -sSL -w "\n%{http_code}" -H "Authorization: Bearer $TOKEN" "https://api.apify.com/v2/users/me" 2>/dev/null || true)
    CODE=$(echo "$RESP" | tail -n 1)
    BODY=$(echo "$RESP" | sed '$d')

    if [ "$CODE" = "200" ]; then
      USER=$(echo "$BODY" | jq -r '.data.username // .data.email // "user"')
      PLAN=$(echo "$BODY" | jq -r '.data.plan.id // "free"')
      echo "✅ Successfully connected to Apify!"
      echo "   User: $USER"
      echo "   Plan: $PLAN"
    else
      echo "[!] Connection failed with HTTP status $CODE."
      echo "    Response: $BODY"
    fi
    ;;
  3)
    echo ""
    echo "[-] Checking Apify Configuration Status:"
    if [ -f /root/.config/apify/credentials.json ]; then
      echo "✅ Credentials file exists in /root/.config/apify/credentials.json"
      USER=$(jq -r '.username // "configured"' /root/.config/apify/credentials.json 2>/dev/null || echo "configured")
      echo "   Configured User: $USER"
    else
      echo "[-] No credentials file found in /root/.config/apify/"
    fi
    if grep -q "^APIFY_TOKEN=[^#[:space:]]" .env 2>/dev/null; then
      echo "✅ APIFY_TOKEN is set in .env"
    else
      echo "[-] APIFY_TOKEN is not set in .env"
    fi
    ;;
  *)
    echo "[!] Invalid choice."
    exit 1
    ;;
esac

echo ""
echo "=========================================================="
echo "Apify setup process completed!"
echo "=========================================================="
