#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================="
echo "    Setup & Login: Remote Antigravity & Wanderlog         "
echo "=========================================================="

echo ""
echo "This wizard helps you log in to your services:"
echo "  Step 1: Authenticate with Wanderlog (via cookie or email/pass)"
echo "  Step 2: Authenticate with Google Antigravity (via browser OAuth)"
echo "  Step 3: (Optional) Authenticate with GitHub CLI & Git"
echo "  Step 4: (Optional) Authenticate with Booking.com"
echo "  Step 5: (Optional) Authenticate with Apify (Agoda & Google Maps lodging)"
echo ""
read -r -p "Press [Enter] to proceed..." || true

echo ""
echo "=== Step 1: Wanderlog Authentication ==="
"$SCRIPT_DIR/login_wanderlog.sh"

echo ""
echo "=== Step 2: Antigravity CLI Authentication ==="
"$SCRIPT_DIR/login_antigravity.sh"

echo ""
echo "=== Step 3: GitHub & Git Authentication (Optional) ==="
read -r -p "Do you want to authenticate with GitHub CLI & Git now? [y/N]: " SETUP_GH || true
if [[ "$SETUP_GH" =~ ^[Yy]$ ]]; then
  "$SCRIPT_DIR/login_github.sh"
else
  echo "[-] Skipping GitHub setup. You can run './scripts/login_github.sh' anytime."
fi

echo ""
echo "=== Step 4: Booking.com Authentication (Optional) ==="
read -r -p "Do you want to configure Booking.com credentials now? [y/N]: " SETUP_BOOKING || true
if [[ "$SETUP_BOOKING" =~ ^[Yy]$ ]]; then
  "$SCRIPT_DIR/login_booking.sh"
else
  echo "[-] Skipping Booking.com setup. You can run './scripts/login_booking.sh' anytime."
fi

echo ""
echo "=== Step 5: Apify (Agoda & Google Maps) Authentication (Optional) ==="
read -r -p "Do you want to configure Apify credentials now? [y/N]: " SETUP_APIFY || true
if [[ "$SETUP_APIFY" =~ ^[Yy]$ ]]; then
  "$SCRIPT_DIR/login_apify.sh"
else
  echo "[-] Skipping Apify setup. You can run './scripts/login_apify.sh' anytime."
fi

echo ""
echo "=========================================================="
echo "All authentication steps completed!"
echo "Your credentials and sessions are saved and persisted."
echo "You can now manage Wanderlog trips remotely with Antigravity!"
echo "=========================================================="
