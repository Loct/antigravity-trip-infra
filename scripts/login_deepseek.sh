#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

echo "=========================================================="
echo "    DeepSeek & OpenRouter Trip Validator Setup Wizard     "
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
echo "Select your preferred DeepSeek provider:"
echo "  1) OpenRouter (Recommended: 100% Free DeepSeek-R1 & Chat, No credit card required)"
echo "  2) Groq (Free fast inference: deepseek-r1-distill-llama-70b)"
echo "  3) Official DeepSeek API Key (platform.deepseek.com trial/paid credits)"
echo "  4) Local Ollama (Free & offline, no API key needed)"
echo "  5) Check current DeepSeek configuration & test connection"
echo "  6) Run test audit on sample trip (trips/southern_italy.json)"
echo ""
read -r -p "Enter choice [1-6]: " CHOICE || true

case "$CHOICE" in
  1)
    echo ""
    echo "--- OpenRouter Free Tier Setup ---"
    echo "OpenRouter offers free access to DeepSeek-R1 (671B) and DeepSeek-Chat."
    echo "1. Sign up for free (or log in) at https://openrouter.ai"
    echo "2. Create a free API key at: https://openrouter.ai/settings/keys"
    echo ""
    read -r -s -p "Paste OpenRouter API Key (sk-or-v1-...): " API_KEY_VAL
    echo ""

    API_KEY_VAL="$(echo "$API_KEY_VAL" | tr -d '[:space:]')"

    if [ -z "$API_KEY_VAL" ]; then
      echo "[!] No API key provided. Aborting."
      exit 1
    fi

    echo ""
    echo "Select default model for OpenRouter:"
    echo "  1) deepseek/deepseek-chat (DeepSeek V3 Chat - Recommended, lowest cost)"
    echo "  2) deepseek/deepseek-v4.1-flash (High speed DeepSeek Flash)"
    echo "  3) openrouter/free (Universal free reasoning router)"
    read -r -p "Choice [1-3, default: 1]: " MODEL_CHOICE || true

    if [ "$MODEL_CHOICE" = "2" ]; then
      MODEL_VAL="deepseek/deepseek-v4.1-flash"
    elif [ "$MODEL_CHOICE" = "3" ]; then
      MODEL_VAL="openrouter/free"
    else
      MODEL_VAL="deepseek/deepseek-chat"
    fi

    update_env_var "OPENROUTER_API_KEY" "$API_KEY_VAL"
    update_env_var "OPENROUTER_MODEL" "$MODEL_VAL"
    update_env_var "DEEPSEEK_PROVIDER" "openrouter"

    echo "[+] Configuration saved to .env"
    echo "[-] Verifying connection with OpenRouter..."

    OPENROUTER_API_KEY="$API_KEY_VAL" uv run "$SCRIPT_DIR/deepseek_validator.py" --test || {
      echo "[!] Connection test failed. Please verify your OpenRouter key."
      exit 1
    }
    echo "[✓] OpenRouter Free DeepSeek configured successfully!"
    ;;

  2)
    echo ""
    echo "--- Groq Free Tier Setup ---"
    echo "Groq offers ultra-fast free tier access to DeepSeek R1 Distill 70B."
    echo "Get your free API key at: https://console.groq.com/keys"
    echo ""
    read -r -s -p "Paste Groq API Key (gsk_...): " API_KEY_VAL
    echo ""

    API_KEY_VAL="$(echo "$API_KEY_VAL" | tr -d '[:space:]')"

    if [ -z "$API_KEY_VAL" ]; then
      echo "[!] No API key provided. Aborting."
      exit 1
    fi

    update_env_var "GROQ_API_KEY" "$API_KEY_VAL"
    update_env_var "DEEPSEEK_PROVIDER" "groq"
    update_env_var "DEEPSEEK_MODEL" "deepseek-r1-distill-llama-70b"

    echo "[+] Configuration saved to .env"
    echo "[-] Verifying connection with Groq..."

    GROQ_API_KEY="$API_KEY_VAL" uv run "$SCRIPT_DIR/deepseek_validator.py" --test || {
      echo "[!] Connection test failed. Please verify your Groq key."
      exit 1
    }
    echo "[✓] Groq DeepSeek configured successfully!"
    ;;

  3)
    echo ""
    echo "--- Official DeepSeek API Setup ---"
    echo "Get your API key at: https://platform.deepseek.com/api_keys"
    echo ""
    read -r -s -p "Paste DeepSeek API Key (sk-...): " API_KEY_VAL
    echo ""

    API_KEY_VAL="$(echo "$API_KEY_VAL" | tr -d '[:space:]')"

    if [ -z "$API_KEY_VAL" ]; then
      echo "[!] No API key provided. Aborting."
      exit 1
    fi

    update_env_var "DEEPSEEK_API_KEY" "$API_KEY_VAL"
    update_env_var "DEEPSEEK_PROVIDER" "deepseek"
    update_env_var "DEEPSEEK_MODEL" "deepseek-reasoner"

    echo "[+] Configuration saved to .env"
    echo "[-] Verifying connection with DeepSeek..."

    DEEPSEEK_API_KEY="$API_KEY_VAL" uv run "$SCRIPT_DIR/deepseek_validator.py" --test || {
      echo "[!] Connection test failed. Please verify your DeepSeek key."
      exit 1
    }
    echo "[✓] Official DeepSeek configured successfully!"
    ;;

  4)
    echo ""
    echo "--- Local Ollama Setup ---"
    read -r -p "Ollama Base URL [default: http://localhost:11434/v1]: " OLLAMA_URL || true
    OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434/v1}"

    read -r -p "Ollama Model [default: deepseek-r1:latest]: " OLLAMA_MDL || true
    OLLAMA_MDL="${OLLAMA_MDL:-deepseek-r1:latest}"

    update_env_var "OLLAMA_BASE_URL" "$OLLAMA_URL"
    update_env_var "DEEPSEEK_PROVIDER" "ollama"
    update_env_var "DEEPSEEK_MODEL" "$OLLAMA_MDL"

    echo "[+] Configuration saved to .env"
    echo "[-] Verifying connection with Ollama..."

    OLLAMA_BASE_URL="$OLLAMA_URL" uv run "$SCRIPT_DIR/deepseek_validator.py" --test || {
      echo "[!] Connection test failed. Ensure Ollama is running and model is pulled: 'ollama pull $OLLAMA_MDL'."
      exit 1
    }
    echo "[✓] Ollama DeepSeek configured successfully!"
    ;;

  5)
    echo ""
    echo "=== Current Configuration Status ==="
    echo "Provider: $(grep '^DEEPSEEK_PROVIDER=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo 'Not configured (defaults to openrouter)')"
    echo "OpenRouter Key: $(grep '^OPENROUTER_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | sed 's/.\{10\}$/**********/' || echo 'Not set')"
    echo "OpenRouter Model: $(grep '^OPENROUTER_MODEL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo 'deepseek/deepseek-r1:free (default)')"
    echo "DeepSeek API Key: $(grep '^DEEPSEEK_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | sed 's/.\{10\}$/**********/' || echo 'Not set')"
    echo "Groq API Key: $(grep '^GROQ_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | sed 's/.\{10\}$/**********/' || echo 'Not set')"
    echo "Ollama URL: $(grep '^OLLAMA_BASE_URL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo 'Not set')"
    echo ""
    echo "Testing connection..."
    uv run "$SCRIPT_DIR/deepseek_validator.py" --test || true
    ;;

  6)
    echo ""
    echo "Running test audit on trips/southern_italy.json..."
    uv run "$SCRIPT_DIR/deepseek_validator.py" "$REPO_ROOT/trips/southern_italy.json"
    ;;

  *)
    echo "Invalid option. Exiting."
    exit 1
    ;;
esac
