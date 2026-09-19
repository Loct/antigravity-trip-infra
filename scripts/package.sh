#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_ARCHIVE="$ROOT_DIR/gemini-wanderlog-release.tar.gz"

INCLUDE_ENV=false

for arg in "$@"; do
  case "$arg" in
    --include-env)
      INCLUDE_ENV=true
      ;;
  esac
done

echo "=========================================================="
echo "        Packaging Gemini Wanderlog Release Archive        "
echo "=========================================================="

cd "$ROOT_DIR"

FILES=(
  "Dockerfile"
  "docker-compose.yml"
  "entrypoint.sh"
  "deploy.sh"
  "mcp_config.json"
  ".agents"
  "scripts"
  ".env.example"
  ".gitignore"
  "README.md"
)

if [ "$INCLUDE_ENV" = "true" ] && [ -f ".env" ]; then
  echo "[-] Including active .env file in release package..."
  FILES+=(".env")
fi

echo "[-] Creating archive: $OUTPUT_ARCHIVE"
tar -czf "$OUTPUT_ARCHIVE" "${FILES[@]}"

echo ""
echo "=========================================================="
echo "✅ Release package created successfully!"
echo "File: $OUTPUT_ARCHIVE"
echo "Size: $(du -h "$OUTPUT_ARCHIVE" | cut -f1)"
echo "=========================================================="
echo ""
echo "How to deploy on your server:"
echo "  1. Copy to your server:"
echo "     scp $OUTPUT_ARCHIVE user@your-server:/path/to/target/"
echo ""
echo "  2. Extract and run on server:"
echo "     tar -xzf gemini-wanderlog-release.tar.gz"
echo "     ./deploy.sh"
echo "=========================================================="
