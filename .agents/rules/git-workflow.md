# Git & Infrastructure Governance Rules

These rules govern how Antigravity manages files in the workspace, maintains Git cleanliness, and contributes infrastructure changes back to GitHub.

---

## 1. Trip Artifacts & User Content Isolation

> [!IMPORTANT]
> **All user-generated travel documents MUST be stored in `/workspace/trips/`.**

- Trip itineraries, markdown exports, packing lists, notes, and CSV budget sheets must **always** be created inside the `/workspace/trips/` directory (e.g., `/workspace/trips/tokyo-2026.md`).
- Never save user trip files into the root project directory, as this clutters the repository and can interfere with Git status.
- The `trips/` directory is ignored by Git, ensuring local user files are never wiped or conflicted during repository updates.

---

## 2. Infrastructure Immutability on `main`

> [!CAUTION]
> **NEVER commit infrastructure or skill changes directly to the `main` branch.**

- The `main` branch on the server tracks the upstream production deployment.
- Directly editing or committing to `main` risks merge conflicts during automated self-updates and can brick remote server access.
- Infrastructure files include:
  - `Dockerfile`
  - `docker-compose.yml`
  - `entrypoint.sh`
  - `deploy.sh`
  - `scripts/*`
  - `.agents/*` (skills and rules)
  - `mcp_config.json`

---

## 3. Pull Request (PR) Workflow for Infra & Skills

Whenever the user asks Antigravity to add a new skill, update an existing rule, modify Docker configurations, or add a script:

### Step 1: Create a Feature Branch
```bash
git checkout main
git pull origin main
git checkout -b feat/<feature-description>
```

### Step 2: Make Changes & Test
Edit the appropriate files. Ensure scripts are made executable (`chmod +x`).

### Step 3: Review & Stage Specific Files
- **Never** use `git add .` or `git add -A`.
- Explicitly stage only the files you modified:
  ```bash
  git add .agents/skills/new-skill/SKILL.md
  git diff --cached
  ```

### Step 4: Commit with Descriptive Message
```bash
git commit -m "feat(skills): add new-skill for platform integration"
```

### Step 5: Push Branch & Open Pull Request via GitHub CLI
```bash
git push -u origin feat/<feature-description>
gh pr create --title "feat: <feature-description>" --body "Automated PR from Antigravity Remote"
```

### Step 6: Return to `main` & Notify User
```bash
git checkout main
```
Present the Pull Request URL to the user. Inform them that once the PR is reviewed and merged on GitHub, running `self_update.sh` (or asking Antigravity to self-update) will pull the verified changes cleanly.

---

## 4. Strict Secret & Credential Protection

- **NEVER** stage or commit:
  - `.env`
  - `credentials.json`
  - `data/` or `.data/`
  - Session cookies (`connect.sid`, `bkng_sso_session`, etc.)
  - Personal Access Tokens (PATs) or API keys
- If a secret is accidentally staged, immediately run `git reset HEAD <file>` and verify before committing.
