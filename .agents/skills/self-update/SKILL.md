---
name: self-update
description: Check for updates from GitHub, pull latest changes, and trigger autonomous Docker rebuild and redeployment from inside the Antigravity Remote session.
---

# Antigravity Self-Update Skill

This skill enables Antigravity to autonomously check for updates, pull changes from GitHub, and safely rebuild/redeploy its own Docker environment from inside an Antigravity Remote session—even when users do not have direct SSH or server terminal access.

---

## 1. How It Works Under the Hood

1. **Live Code Updates (Skills, Rules, Scripts)**:
   Because `/workspace` is bind-mounted directly from the host filesystem, any `git pull` instantly updates skills, rules, and scripts in real time without needing to restart or rebuild the container.

2. **Docker Environment Updates (`Dockerfile`, `compose`, packages)**:
   When changes touch Docker infrastructure files, the container talks to the host Docker daemon via `/var/run/docker.sock` and spawns a lightweight, detached sibling updater container (`docker:cli`).
   - The sibling container runs independently on the host.
   - It rebuilds the new image and swaps the running container.
   - The new container boots up and re-establishes Antigravity Remote Control automatically within 15–30 seconds.

---

## 2. Update Workflow

When a user asks:
- *"Update yourself from GitHub"*
- *"Check for updates"*
- *"Pull latest changes and redeploy"*
- *"Redeploy the container"*

Follow this procedure:

### Step 1: Check for Updates
Run:
```bash
/workspace/scripts/self_update.sh --check
```
- If already up to date, inform the user with the current commit hash.
- If updates exist, summarize the incoming commit messages to the user.

### Step 2: Trigger Update & Redeploy
Ask the user for confirmation (or proceed if already confirmed):
```bash
/workspace/scripts/self_update.sh
```

Or force a full Docker image rebuild:
```bash
/workspace/scripts/self_update.sh --rebuild
```

### Step 3: Inform the User
If the script outputs that a background redeployment was initiated, inform the user:
> *"The self-update has been initiated! A background container is rebuilding the environment now. Your Antigravity Remote session will disconnect briefly for about 15–30 seconds while the new container starts, and then automatically reconnect."*
