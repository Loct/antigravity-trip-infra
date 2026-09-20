#!/usr/bin/env bash
set -e

SERVICE_NAME="antigravity-wanderlog"

echo "=========================================================="
echo "          GitHub CLI & Git Authentication Helper          "
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

# Check if already authenticated
if docker compose exec -T "$SERVICE_NAME" gh auth status >/dev/null 2>&1; then
  echo ""
  echo "✅ GitHub CLI is already authenticated!"
  docker compose exec -T "$SERVICE_NAME" gh auth status || true
  echo ""
  read -r -p "Do you want to re-authenticate or configure git? [y/N]: " REAUTH || true
  if [[ ! "$REAUTH" =~ ^[Yy]$ ]]; then
    echo "[-] Keeping existing GitHub credentials."
    exit 0
  fi
fi

echo ""
echo "Choose an authentication / setup method:"
echo "  1) Interactive login via Browser / One-Time Device Code (gh auth login)"
echo "  2) Paste Personal Access Token (PAT / fine-grained token)"
echo "  3) Configure Git User (user.name and user.email)"
echo "  4) Check current GitHub & Git status"
echo ""
read -r -p "Enter choice [1-4]: " CHOICE || true

case "$CHOICE" in
  1)
    echo ""
    echo "[-] Starting interactive GitHub CLI login..."
    echo "    When prompted, select:"
    echo "      - GitHub.com"
    echo "      - HTTPS (or SSH)"
    echo "      - Yes to authenticate Git with your GitHub credentials"
    echo "      - Login with a web browser (will display a one-time code)"
    echo ""
    docker compose exec -it "$SERVICE_NAME" gh auth login
    docker compose exec -T "$SERVICE_NAME" gh auth setup-git
    echo ""
    echo "[-] Verifying GitHub authentication status:"
    docker compose exec -T "$SERVICE_NAME" gh auth status
    ;;
  2)
    echo ""
    echo "How to create a Personal Access Token (PAT):"
    echo "  1. Open https://github.com/settings/tokens"
    echo "  2. Generate a new token (Classic or Fine-grained) with 'repo' scope."
    echo "  3. Copy and paste the token below."
    echo ""
    read -r -s -p "Paste GitHub Token (hidden): " GH_INPUT_TOKEN
    echo ""

    # Clean whitespace
    GH_INPUT_TOKEN="$(echo "$GH_INPUT_TOKEN" | tr -d '[:space:]')"

    if [ -z "$GH_INPUT_TOKEN" ]; then
      echo "[!] No token provided. Aborting."
      exit 1
    fi

    echo "[-] Authenticating GitHub CLI with token..."
    echo "$GH_INPUT_TOKEN" | docker compose exec -T "$SERVICE_NAME" gh auth login --with-token
    docker compose exec -T "$SERVICE_NAME" gh auth setup-git

    read -r -p "Do you want to save this token to your .env file? [y/N]: " SAVE_ENV || true
    if [[ "$SAVE_ENV" =~ ^[Yy]$ ]]; then
      if [ ! -f .env ]; then
        cp .env.example .env 2>/dev/null || touch .env
      fi
      if grep -q "^GH_TOKEN=" .env; then
        sed -i.bak "s|^GH_TOKEN=.*|GH_TOKEN=\"${GH_INPUT_TOKEN}\"|" .env
        rm -f .env.bak
      else
        echo "GH_TOKEN=\"${GH_INPUT_TOKEN}\"" >> .env
      fi
      echo "[-] Saved GH_TOKEN to .env."
    fi

    echo ""
    echo "[-] Verifying GitHub authentication status:"
    docker compose exec -T "$SERVICE_NAME" gh auth status
    ;;
  3)
    echo ""
    echo "Configure Git author details for commits inside container:"
    read -r -p "Enter Git user name (e.g. John Doe): " G_NAME
    read -r -p "Enter Git user email (e.g. user@example.com): " G_EMAIL

    if [ -n "$G_NAME" ]; then
      docker compose exec -T "$SERVICE_NAME" git config --global user.name "$G_NAME"
      echo "[-] Updated user.name: $G_NAME"
    fi
    if [ -n "$G_EMAIL" ]; then
      docker compose exec -T "$SERVICE_NAME" git config --global user.email "$G_EMAIL"
      echo "[-] Updated user.email: $G_EMAIL"
    fi

    echo ""
    echo "[-] Current Git Global Config:"
    docker compose exec -T "$SERVICE_NAME" git config --list --show-origin || true
    ;;
  4)
    echo ""
    echo "[-] GitHub CLI Status:"
    docker compose exec -T "$SERVICE_NAME" gh auth status || true
    echo ""
    echo "[-] Git Global Config:"
    docker compose exec -T "$SERVICE_NAME" git config --list --show-origin || true
    ;;
  *)
    echo "[!] Invalid choice."
    exit 1
    ;;
esac

echo ""
echo "=========================================================="
echo "GitHub CLI & Git setup completed!"
echo "Credentials are saved in the persistent 'github_data' & 'git_data' volumes."
echo "=========================================================="
