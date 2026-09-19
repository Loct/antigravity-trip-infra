#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "           Wanderlog CLI Diagnostics & Test               "
echo "=========================================================="

if ! command -v wanderlog >/dev/null 2>&1; then
  echo "[!] 'wanderlog' binary not found in PATH."
  echo "    Ensure wanderlog-cli is installed or run this inside the Docker container."
  exit 1
fi

echo "[-] Checking Wanderlog CLI version..."
wanderlog --version 2>/dev/null || echo "wanderlog-cli installed"

echo ""
echo "[-] Checking Authentication Status..."
wanderlog status

echo ""
echo "[-] Fetching user trips..."
wanderlog trips list

echo ""
echo "[-] Done."
