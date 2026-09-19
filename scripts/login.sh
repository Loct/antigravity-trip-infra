#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================="
echo "    Setup & Login: Remote Antigravity & Wanderlog         "
echo "=========================================================="

echo ""
echo "This wizard helps you log in to both services:"
echo "  Step 1: Authenticate with Wanderlog (via cookie or email/pass)"
echo "  Step 2: Authenticate with Google Antigravity (via browser OAuth)"
echo ""
read -r -p "Press [Enter] to proceed..." || true

echo ""
echo "=== Step 1: Wanderlog Authentication ==="
"$SCRIPT_DIR/login_wanderlog.sh"

echo ""
echo "=== Step 2: Antigravity CLI Authentication ==="
"$SCRIPT_DIR/login_antigravity.sh"

echo ""
echo "=========================================================="
echo "All authentication steps completed!"
echo "Your credentials and sessions are saved and persisted."
echo "You can now manage Wanderlog trips remotely with Antigravity!"
echo "=========================================================="
