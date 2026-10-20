#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================================="
echo "             Agoda Integration Diagnostics & Test         "
echo "=========================================================="

echo ""
echo "[-] 1. Checking Agoda Provider Configuration & Status..."
uv run "$SCRIPT_DIR/agoda.py" status

echo ""
echo "[-] 2. Running Automated Unit & CLI Test Suite..."
uv run pytest "$REPO_ROOT/tests/test_agoda.py" -v

echo ""
echo "[-] 3. Running Sample Hotel Search (Tokyo, 3 properties)..."
uv run "$SCRIPT_DIR/agoda.py" search -l "Tokyo" --limit 3 || echo "[!] Notice: Live hotel search requires valid AGODA_API_KEY, APIFY_TOKEN, or network access to Agoda."

echo ""
echo "=========================================================="
echo "Agoda Diagnostics & Tests completed!"
echo "=========================================================="
