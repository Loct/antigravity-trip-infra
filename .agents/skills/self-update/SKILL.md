---
name: self-update
description: Check for updates from GitHub, update Antigravity CLI (agy update), pull latest changes, and trigger autonomous Docker rebuild or container restart from inside the Antigravity Remote session.
---

# Antigravity Self-Update Skill

This skill enables Antigravity to autonomously check for updates, update the `agy` CLI binary, pull changes from GitHub, and safely rebuild/redeploy its own Docker environment from inside an Antigravity Remote session—even when users do not have direct SSH or server terminal access.

---

## 1. How It Works Under the Hood

1. **Live Code Updates (Skills, Rules, Scripts)**:
   Because `/workspace` is bind-mounted directly from the host filesystem, any `git pull` instantly updates skills, rules, and scripts in real time without needing to restart or rebuild the container.

2. **Antigravity CLI Binary Updates (`agy`)**:
   The script checks for and runs `agy update`. When a new binary is installed, the container automatically spawns a lightweight background restarter container (`docker:cli`) that restarts the container cleanly after a brief delay, reloading the updated binary with zero manual user intervention.

3. **Docker Environment Updates (`Dockerfile`, `compose`, packages)**:
   When changes touch Docker infrastructure files, the container talks to the host Docker daemon via `/var/run/docker.sock` and spawns a lightweight, detached sibling updater container (`docker:cli`).
   - The sibling container runs independently on the host.
   - It rebuilds the new image and swaps the running container.
   - The new container boots up and re-establishes Antigravity Remote Control automatically within 15–30 seconds.

---

## 2. Update Workflow

When a user asks:
- *"Run self update"*
- *"Update yourself from GitHub"*
- *"Check for updates"*
- *"Pull latest changes and redeploy"*
- *"Redeploy the container"*
- *"Restart the container"*

Follow this procedure:

### Step 0: Ensure Tracking Branch
If the working tree is clean and currently on a feature branch (e.g., after pull request merges):
```bash
git checkout main
```

### Step 1: Check for Updates
Run:
```bash
/workspace/scripts/self_update.sh --check
```
- If already up to date, inform the user with the current commit hash and CLI version.
- If updates exist, summarize the incoming changes.

### Step 2: Trigger Update & Redeploy / Restart
Execute:
```bash
/workspace/scripts/self_update.sh
```

Or on-demand controls:
- **Force container restart** (reload CLI binary):
  ```bash
  /workspace/scripts/self_update.sh --restart
  ```
- **Force full Docker image rebuild & redeploy**:
  ```bash
  /workspace/scripts/self_update.sh --rebuild
  ```

### Step 3: Inform the User
If the script outputs that a background redeployment or restart was scheduled:
> *"The self-update has been initiated! The container will restart in a few seconds to load the updates. Your Antigravity Remote session will disconnect briefly and automatically reconnect in ~5–15 seconds."*
