#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CHECK_ONLY=false
FORCE_REBUILD=false

for arg in "$@"; do
  case "$arg" in
    --check)
      CHECK_ONLY=true
      ;;
    --rebuild)
      FORCE_REBUILD=true
      ;;
  esac
done

echo "=========================================================="
echo "         Antigravity Remote Self-Update Manager           "
echo "=========================================================="

cd "$WORKSPACE_ROOT"

# Ensure git safe directory
git config --global --add safe.directory "$WORKSPACE_ROOT" 2>/dev/null || true

# 1. Determine git branch and remote
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'main')"
echo "[-] Current Branch: $CURRENT_BRANCH"

# Check if remote exists
if ! git remote get-url origin >/dev/null 2>&1; then
  echo "[!] No git remote 'origin' configured. Cannot pull updates."
  exit 1
fi

echo "[-] Fetching latest changes from origin/$CURRENT_BRANCH..."
git fetch origin "$CURRENT_BRANCH"

LOCAL_COMMIT="$(git rev-parse HEAD)"
REMOTE_COMMIT="$(git rev-parse "origin/$CURRENT_BRANCH")"

if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ] && [ "$FORCE_REBUILD" = "false" ]; then
  echo "✅ Already up-to-date with origin/$CURRENT_BRANCH (Commit: ${LOCAL_COMMIT:0:7})."
  echo "   No environment or code changes detected."
  exit 0
fi

if [ "$LOCAL_COMMIT" != "$REMOTE_COMMIT" ]; then
  echo "[-] New updates detected on remote:"
  git log --oneline "$LOCAL_COMMIT..$REMOTE_COMMIT"
  echo ""

  if [ "$CHECK_ONLY" = "true" ]; then
    echo "[*] Check-only mode: Not applying changes."
    exit 0
  fi

  # Auto-stash dirty state to prevent merge conflicts
  if ! git diff --quiet || ! git diff --staged --quiet; then
    echo "[-] Uncommitted changes detected. Auto-stashing before pull..."
    git stash push -m "auto-stash-self-update-$(date +%s)" 2>/dev/null || true
  fi

  echo "[-] Pulling latest changes..."
  OLD_HEAD="$LOCAL_COMMIT"
  git pull origin "$CURRENT_BRANCH"
  NEW_HEAD="$(git rev-parse HEAD)"

  # Check what changed
  CHANGED_FILES="$(git diff --name-only "$OLD_HEAD" "$NEW_HEAD")"
  echo "[-] Updated files:"
  echo "$CHANGED_FILES"
  echo ""
fi

# 2. Determine if Docker environment rebuild is needed
NEEDS_DOCKER_REBUILD=false

if [ "$FORCE_REBUILD" = "true" ]; then
  NEEDS_DOCKER_REBUILD=true
  echo "[-] Force rebuild requested."
elif echo "$CHANGED_FILES" | grep -qE "(Dockerfile|docker-compose\.yml|entrypoint\.sh)"; then
  NEEDS_DOCKER_REBUILD=true
  echo "[-] Detected changes in Docker infrastructure (Dockerfile / compose / entrypoint)."
fi

# 3. Apply Rebuild or Restart
if [ "$NEEDS_DOCKER_REBUILD" = "true" ]; then
  echo "=========================================================="
  echo "[-] Rebuilding Docker environment (Atomic Safety Mode)..."
  echo "=========================================================="

  # Check if running inside container or on host
  if [ -f "/.dockerenv" ] || [ -n "${ENABLE_REMOTE_CONTROL:-}" ]; then
    # Running INSIDE Docker container
    echo "[-] Running inside Antigravity container."
    
    # Read host directory from environment or .env
    HOST_DIR="${HOST_PROJECT_DIR:-}"
    if [ -z "$HOST_DIR" ] && [ -f "$WORKSPACE_ROOT/.env" ]; then
      HOST_DIR="$(grep "^HOST_PROJECT_DIR=" "$WORKSPACE_ROOT/.env" | cut -d '=' -f2- | tr -d '"' | tr -d "'")"
    fi

    if [ -z "$HOST_DIR" ]; then
      echo "[!] Warning: HOST_PROJECT_DIR is not set. Defaulting to host path discovery."
      HOST_DIR="$(docker inspect "$(hostname)" --format '{{ range .Mounts }}{{ if eq .Destination "/workspace" }}{{ .Source }}{{ end }}{{ end }}' 2>/dev/null || true)"
    fi

    if [ -z "$HOST_DIR" ]; then
      HOST_DIR="$WORKSPACE_ROOT"
    fi

    echo "[-] Host workspace directory: $HOST_DIR"

    if [ ! -S "/var/run/docker.sock" ]; then
      echo "[!] Error: /var/run/docker.sock is not mounted in this container."
      echo "    Cannot trigger Docker rebuild from inside container."
      echo "    Please ask administrator to redeploy with docker.sock mounted."
      exit 1
    fi

    UPDATER_NAME="antigravity-updater-$(date +%s)"
    echo "[-] Spawning background sibling container ($UPDATER_NAME) to rebuild..."

    # The sibling container builds first BEFORE touching the running container.
    # If build fails, the running container is never stopped!
    docker run --rm -d \
      --name "$UPDATER_NAME" \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -v "${HOST_DIR}:${HOST_DIR}" \
      -w "${HOST_DIR}" \
      docker:cli \
      sh -c "echo '[-] Step 1: Testing Docker build...' && docker compose build || { echo '[!] Build failed! Aborting to keep current container running.' && exit 1; } && echo '[-] Step 2: Build succeeded. Recreating container...' && docker compose up -d && echo '[-] Redeploy completed successfully!'"

    echo ""
    echo "=========================================================="
    echo "🚀 Background redeployment initiated!"
    echo "=========================================================="
    echo "What will happen next:"
    echo "  1. The background updater container is rebuilding the Docker image."
    echo "  2. Current container stays running until the new build is confirmed healthy."
    echo "  3. Your Antigravity Remote session will reconnect in ~15-30 seconds."
    echo "=========================================================="
    exit 0
  else
    # Running ON HOST directly
    echo "[-] Running on host machine. Testing build first..."
    docker compose build || {
      echo "[!] Error: Build failed! Current container left untouched."
      exit 1
    }
    docker compose up -d
    echo "=========================================================="
    echo "✅ Rebuild and redeployment successful!"
    echo "=========================================================="
  fi
else
  echo "=========================================================="
  echo "✅ Changes applied successfully!"
  echo "   Workspace files (skills, rules, scripts) are live immediately."
  echo "   No Docker environment rebuild was required."
  echo "=========================================================="
fi
