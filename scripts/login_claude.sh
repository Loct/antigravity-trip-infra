#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

echo "=========================================================="
echo "         Claude Trip Validator Setup Wizard               "
echo "=========================================================="

# Ensure .env exists
if [ ! -f "$ENV_FILE" ]; then
  touch "$ENV_FILE"
fi

update_env_var() {
  local var_name="$1"
  local var_val="$2"

  if grep -q "^${var_name}=" "$ENV_FILE"; then
    # Replace existing
    sed -i "s|^${var_name}=.*|${var_name}=${var_val}|" "$ENV_FILE"
  else
    # Append
    echo "${var_name}=${var_val}" >> "$ENV_FILE"
  fi
}

echo ""
echo "Select your preferred setup option:"
echo "  1) Official Anthropic API Key (console.anthropic.com - Recommended)"
echo "  2) OpenRouter Claude (Route Claude requests through OpenRouter)"
echo "  3) Check current Claude configuration & test connection"
echo "  4) Run test audit on sample trip (trips/southern_italy.json)"
echo "  5) Run dual cross-check test (Claude + DeepSeek) on sample trip"
echo ""
read -r -p "Enter choice [1-5]: " CHOICE || true

case "$CHOICE" in
  1)
    echo ""
    echo "--- Official Anthropic API Setup ---"
    echo "Anthropic provides direct access to Claude 3.7 Sonnet (with Extended Thinking),"
    echo "Claude 3.5 Sonnet, and Claude 3.5 Haiku."
    echo "1. Sign up or log in at: https://console.anthropic.com"
    echo "2. Create an API key at: https://console.anthropic.com/settings/keys"
    echo ""
    read -r -s -p "Paste Anthropic API Key (sk-ant-...): " API_KEY_VAL
    echo ""

    API_KEY_VAL="$(echo "$API_KEY_VAL" | tr -d '[:space:]')"

    if [ -z "$API_KEY_VAL" ]; then
      echo "[!] No API key provided. Aborting."
      exit 1
    fi

    echo ""
    echo "Select default model for Claude:"
    echo "  1) claude-3-7-sonnet-20250219 (Claude 3.7 Sonnet with Extended Thinking - Recommended)"
    echo "  2) claude-3-5-sonnet-20241022 (Claude 3.5 Sonnet v2)"
    echo "  3) claude-3-5-haiku-20241022  (Claude 3.5 Haiku - Ultra fast)"
    echo "  4) Custom model string"
    read -r -p "Choice [1-4, default: 1]: " MODEL_CHOICE || true

    if [ "$MODEL_CHOICE" = "2" ]; then
      MODEL_VAL="claude-3-5-sonnet-20241022"
      THINKING_BUDGET=0
    elif [ "$MODEL_CHOICE" = "3" ]; then
      MODEL_VAL="claude-3-5-haiku-20241022"
      THINKING_BUDGET=0
    elif [ "$MODEL_CHOICE" = "4" ]; then
      read -r -p "Enter custom model identifier: " MODEL_VAL
      THINKING_BUDGET=0
    else
      MODEL_VAL="claude-3-7-sonnet-20250219"
      echo ""
      read -r -p "Extended thinking token budget for Claude 3.7 [default: 2048, 0 to disable]: " TB_INPUT || true
      THINKING_BUDGET="${TB_INPUT:-2048}"
    fi

    update_env_var "ANTHROPIC_API_KEY" "$API_KEY_VAL"
    update_env_var "ANTHROPIC_MODEL" "$MODEL_VAL"
    update_env_var "ANTHROPIC_THINKING_BUDGET" "$THINKING_BUDGET"
    update_env_var "CLAUDE_PROVIDER" "anthropic"

    echo "[+] Configuration saved to .env"
    echo "[-] Verifying connection with Anthropic..."

    ANTHROPIC_API_KEY="$API_KEY_VAL" ANTHROPIC_MODEL="$MODEL_VAL" uv run "$SCRIPT_DIR/claude_validator.py" --test || {
      echo "[!] Connection test failed. Please verify your Anthropic API key."
      exit 1
    }
    echo "[✓] Anthropic Claude configured successfully!"
    ;;

  2)
    echo ""
    echo "--- OpenRouter Claude Setup ---"
    echo "Route Claude requests through OpenRouter."
    echo "Get your key at: https://openrouter.ai/settings/keys"
    echo ""
    read -r -s -p "Paste OpenRouter API Key (sk-or-...): " API_KEY_VAL
    echo ""

    API_KEY_VAL="$(echo "$API_KEY_VAL" | tr -d '[:space:]')"

    if [ -z "$API_KEY_VAL" ]; then
      echo "[!] No API key provided. Aborting."
      exit 1
    fi

    echo ""
    echo "Select OpenRouter Claude model:"
    echo "  1) anthropic/claude-3.7-sonnet (Recommended)"
    echo "  2) anthropic/claude-3.5-sonnet"
    echo "  3) anthropic/claude-3.5-haiku"
    read -r -p "Choice [1-3, default: 1]: " MODEL_CHOICE || true

    if [ "$MODEL_CHOICE" = "2" ]; then
      MODEL_VAL="anthropic/claude-3.5-sonnet"
    elif [ "$MODEL_CHOICE" = "3" ]; then
      MODEL_VAL="anthropic/claude-3.5-haiku"
    else
      MODEL_VAL="anthropic/claude-3.7-sonnet"
    fi

    update_env_var "OPENROUTER_API_KEY" "$API_KEY_VAL"
    update_env_var "CLAUDE_PROVIDER" "openrouter"
    update_env_var "ANTHROPIC_MODEL" "$MODEL_VAL"

    echo "[+] Configuration saved to .env"
    echo "[-] Verifying connection with OpenRouter..."

    OPENROUTER_API_KEY="$API_KEY_VAL" uv run "$SCRIPT_DIR/claude_validator.py" --provider openrouter --model "$MODEL_VAL" --test || {
      echo "[!] Connection test failed. Please verify your OpenRouter key."
      exit 1
    }
    echo "[✓] OpenRouter Claude configured successfully!"
    ;;

  3)
    echo ""
    echo "=== Current Claude Configuration Status ==="
    echo "Provider: $(grep '^CLAUDE_PROVIDER=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo 'anthropic (default)')"
    echo "Anthropic Key: $(grep '^ANTHROPIC_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | sed 's/.\{10\}$/**********/' || echo 'Not set')"
    echo "Claude Model: $(grep '^ANTHROPIC_MODEL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo 'claude-3-7-sonnet-20250219 (default)')"
    echo "Thinking Budget: $(grep '^ANTHROPIC_THINKING_BUDGET=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo '2048 (default)')"
    echo "OpenRouter Key: $(grep '^OPENROUTER_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | sed 's/.\{10\}$/**********/' || echo 'Not set')"
    echo ""
    echo "Testing connection..."
    uv run "$SCRIPT_DIR/claude_validator.py" --test || true
    ;;

  4)
    echo ""
    echo "Running test audit on trips/southern_italy.json using Claude..."
    uv run "$SCRIPT_DIR/claude_validator.py" "$REPO_ROOT/trips/southern_italy.json"
    ;;

  5)
    echo ""
    echo "Running Dual AI Cross-Check (Claude + DeepSeek) on trips/southern_italy.json..."
    uv run "$SCRIPT_DIR/cross_check_validator.py" "$REPO_ROOT/trips/southern_italy.json"
    ;;

  *)
    echo "Invalid option. Exiting."
    exit 1
    ;;
esac
