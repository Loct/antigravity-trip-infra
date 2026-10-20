#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CHECK_ONLY=false
FORCE_REBUILD=false
FORCE_RESTART=false
SKIP_CLI=false
SKIP_GIT=false

for arg in "$@"; do
  case "$arg" in
    --check)
      CHECK_ONLY=true
      ;;
    --rebuild)
      FORCE_REBUILD=true
      ;;
    --restart)
      FORCE_RESTART=true
      ;;
    --skip-cli)
      SKIP_CLI=true
      ;;
    --skip-git)
      SKIP_GIT=true
      ;;
  esac
done

echo "=========================================================="
echo "         Antigravity Remote Self-Update Manager           "
echo "=========================================================="

cd "$WORKSPACE_ROOT"

# Ensure git safe directory
git config --global --add safe.directory "$WORKSPACE_ROOT" 2>/dev/null || true

GIT_UPDATED=false
CHANGED_FILES=""
NEEDS_DOCKER_REBUILD=false
NEEDS_CONTAINER_RESTART=false

# ----------------------------------------------------
# 1. Git Repository Updates
# ----------------------------------------------------
if [ "$SKIP_GIT" = "false" ]; then
  CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'main')"
  echo "[-] Current Git Branch: $CURRENT_BRANCH"

  if git remote get-url origin >/dev/null 2>&1; then
    echo "[-] Fetching latest changes from origin/$CURRENT_BRANCH..."
    git fetch origin "$CURRENT_BRANCH" 2>/dev/null || echo "[!] Warning: git fetch origin failed."

    LOCAL_COMMIT="$(git rev-parse HEAD 2>/dev/null || true)"
    REMOTE_COMMIT="$(git rev-parse "origin/$CURRENT_BRANCH" 2>/dev/null || true)"

    if [ -n "$LOCAL_COMMIT" ] && [ -n "$REMOTE_COMMIT" ] && [ "$LOCAL_COMMIT" != "$REMOTE_COMMIT" ]; then
      echo "[-] New Git updates detected on remote:"
      git log --oneline "$LOCAL_COMMIT..$REMOTE_COMMIT"
      echo ""

      if [ "$CHECK_ONLY" = "false" ]; then
        # Auto-stash dirty state to prevent merge conflicts
        if ! git diff --quiet || ! git diff --staged --quiet; then
          echo "[-] Uncommitted changes detected. Auto-stashing before pull..."
          git stash push -m "auto-stash-self-update-$(date +%s)" 2>/dev/null || true
        fi

        echo "[-] Pulling latest changes..."
        OLD_HEAD="$LOCAL_COMMIT"
        git pull origin "$CURRENT_BRANCH"
        NEW_HEAD="$(git rev-parse HEAD)"

        CHANGED_FILES="$(git diff --name-only "$OLD_HEAD" "$NEW_HEAD")"
        echo "[-] Updated repository files:"
        echo "$CHANGED_FILES"
        echo ""
        GIT_UPDATED=true
      else
        echo "[*] Check-only mode: Not pulling Git changes."
      fi
    else
      echo "✅ Git repository is up-to-date (Commit: ${LOCAL_COMMIT:0:7})."
    fi
  else
    echo "[!] No git remote 'origin' configured. Skipping Git pull."
  fi
fi

# Determine if Docker rebuild is needed from git changes or force flag
if [ "$FORCE_REBUILD" = "true" ]; then
  NEEDS_DOCKER_REBUILD=true
  echo "[-] Force rebuild requested."
elif echo "$CHANGED_FILES" | grep -qE "(Dockerfile|docker-compose\.yml|entrypoint\.sh)"; then
  NEEDS_DOCKER_REBUILD=true
  echo "[-] Detected changes in Docker infrastructure (Dockerfile / compose / entrypoint)."
fi

# ----------------------------------------------------
# 2. Antigravity CLI Updates (`agy update`)
# ----------------------------------------------------
if [ "$SKIP_CLI" = "false" ] && command -v agy >/dev/null 2>&1; then
  echo ""
  echo "[-] Checking Antigravity CLI (agy) updates..."
  CURRENT_AGY_VERSION="$(agy --version 2>/dev/null || echo 'unknown')"
  echo "[-] Current agy version: $CURRENT_AGY_VERSION"

  if [ "$CHECK_ONLY" = "true" ]; then
    echo "[*] Check-only mode: Run 'agy update' to check or apply binary updates."
  else
    UPDATE_OUTPUT="$(agy update 2>&1 || true)"
    echo "$UPDATE_OUTPUT"

    if echo "$UPDATE_OUTPUT" | grep -qiE "(Update successful|Found new version)"; then
      NEW_AGY_VERSION="$(agy --version 2>/dev/null || echo 'updated')"
      echo "✅ Antigravity CLI successfully updated to $NEW_AGY_VERSION!"
      NEEDS_CONTAINER_RESTART=true
    fi
  fi
fi

if [ "$FORCE_RESTART" = "true" ]; then
  NEEDS_CONTAINER_RESTART=true
fi

# ----------------------------------------------------
# 3. Apply Rebuild or Restart Actions
# ----------------------------------------------------
if [ "$CHECK_ONLY" = "true" ]; then
  echo ""
  echo "=========================================================="
  echo "ℹ️  Check complete. Run without --check to apply updates."
  echo "=========================================================="
  exit 0
fi

# Path A: Full Docker Rebuild Needed
if [ "$NEEDS_DOCKER_REBUILD" = "true" ]; then
  echo ""
  echo "=========================================================="
  echo "[-] Rebuilding Docker environment (Atomic Safety Mode)..."
  echo "=========================================================="

  if [ -f "/.dockerenv" ] || [ -n "${ENABLE_REMOTE_CONTROL:-}" ]; then
    HOST_DIR="${HOST_PROJECT_DIR:-}"
    if [ -z "$HOST_DIR" ] && [ -f "$WORKSPACE_ROOT/.env" ]; then
      HOST_DIR="$(grep "^HOST_PROJECT_DIR=" "$WORKSPACE_ROOT/.env" | cut -d '=' -f2- | tr -d '"' | tr -d "'")"
    fi
    if [ -z "$HOST_DIR" ]; then
      HOST_DIR="$(docker inspect "$(hostname)" --format '{{ range .Mounts }}{{ if eq .Destination "/workspace" }}{{ .Source }}{{ end }}{{ end }}' 2>/dev/null || true)"
    fi
    if [ -z "$HOST_DIR" ]; then
      HOST_DIR="$WORKSPACE_ROOT"
    fi

    if [ ! -S "/var/run/docker.sock" ]; then
      echo "[!] Error: /var/run/docker.sock is not mounted. Cannot trigger Docker rebuild."
      exit 1
    fi

    UPDATER_NAME="antigravity-updater-$(date +%s)"
    echo "[-] Spawning background sibling container ($UPDATER_NAME) to rebuild..."

    docker run --rm -d \
      --name "$UPDATER_NAME" \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -v "${HOST_DIR}:${HOST_DIR}" \
      -w "${HOST_DIR}" \
      docker:cli \
      sh -c "echo '[-] Step 1: Testing Docker build...' && docker compose build || { echo '[!] Build failed! Aborting.' && exit 1; } && echo '[-] Step 2: Recreating container...' && docker compose up -d && echo '[-] Redeploy completed successfully!'"

    echo ""
    echo "=========================================================="
    echo "🚀 Background redeployment initiated!"
    echo "=========================================================="
    echo "What will happen next:"
    echo "  1. Sibling updater container is rebuilding the Docker image."
    echo "  2. Current container stays running until new build is confirmed healthy."
    echo "  3. Your Antigravity Remote session will reconnect in ~15-30 seconds."
    echo "=========================================================="
    exit 0
  else
    echo "[-] Running on host machine. Testing build first..."
    docker compose build || {
      echo "[!] Error: Build failed! Current container left untouched."
      exit 1
    }
    docker compose up -d
    echo "=========================================================="
    echo "✅ Rebuild and redeployment successful!"
    echo "=========================================================="
    exit 0
  fi
fi

# Path B: Container Restart Needed (e.g., CLI binary updated)
if [ "$NEEDS_CONTAINER_RESTART" = "true" ]; then
  echo ""
  echo "=========================================================="
  echo "[-] Restarting container to load updated Antigravity binary..."
  echo "=========================================================="

  if [ -S "/var/run/docker.sock" ]; then
    CONTAINER_NAME="$(docker inspect "$(hostname)" --format '{{.Name}}' 2>/dev/null | tr -d '/' || true)"
    if [ -z "$CONTAINER_NAME" ]; then
      CONTAINER_NAME="antigravity-wanderlog-domi"
    fi

    RESTARTER_NAME="antigravity-restarter-$(date +%s)"
    echo "[-] Spawning background restarter container for $CONTAINER_NAME..."

    docker run --rm -d \
      --name "$RESTARTER_NAME" \
      -v /var/run/docker.sock:/var/run/docker.sock \
      docker:cli \
      sh -c "sleep 4 && echo '[-] Restarting container $CONTAINER_NAME...' && docker restart $CONTAINER_NAME"

    echo ""
    echo "=========================================================="
    echo "🔄 Background restart scheduled!"
    echo "=========================================================="
    echo "What will happen next:"
    echo "  1. The restart will initiate in a few seconds."
    echo "  2. The updated Antigravity CLI binary ($NEW_AGY_VERSION) will be loaded."
    echo "  3. Your Antigravity Remote session will automatically reconnect in ~5-10 seconds."
    echo "=========================================================="
    exit 0
  elif [ -f "/.dockerenv" ]; then
    echo "[!] Docker socket not mounted. Please restart the container manually:"
    echo "    docker compose restart"
    exit 0
  else
    echo "[-] Running on host. Restarting container via docker compose..."
    docker compose restart
    echo "✅ Container restarted successfully!"
    exit 0
  fi
fi

# Path C: No Rebuild or Restart Needed
echo ""
echo "=========================================================="
echo "✅ All updates applied successfully!"
if [ "$GIT_UPDATED" = "true" ]; then
  echo "   Workspace files (skills, rules, scripts) are live immediately."
fi
echo "   No container restart or rebuild was required."
echo "=========================================================="
