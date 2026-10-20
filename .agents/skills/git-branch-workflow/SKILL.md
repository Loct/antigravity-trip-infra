---
name: git-branch-workflow
description: Enforce strict Git branch protection, mandatory feature branching (feat/*, fix/*), pull request creation via GitHub CLI (gh pr create), and commit recovery procedures. Activate whenever creating, updating, or fixing code, skills, rules, or documentation.
---

# Git Branch Protection & Pull Request Workflow Skill

This skill enforces strict Git governance within the repository, ensuring changes are never committed or pushed directly to `main` (or `master`), and establishes a reliable, reviewable Pull Request workflow.

---

## 1. Core Rule & Invariant

> [!CAUTION]
> **NEVER commit or push directly to the `main` or `master` branch under ANY circumstances.**
> All changes—whether code, documentation, scripts, rules, or skills—MUST be authored on a feature branch and submitted as a GitHub Pull Request.

---

## 2. Standard Contribution Workflow

Follow this procedure for all repository changes:

### Step 1: Ensure Clean Working Tree
Before starting work, verify there are no unexpected uncommitted files or dirty states:
```bash
git status
```

### Step 2: Create a Dedicated Feature Branch
Ensure you are branching off the latest `origin/main`:
```bash
git checkout main
git pull origin main
git checkout -b feat/<descriptive-name>
# or for bug fixes:
git checkout -b fix/<descriptive-name>
```

### Step 3: Implement Changes & Stage Specific Files
- Only stage the specific files you modified.
- **Never** run `git add .` or `git add -A` blindly.
- Verify that secrets (`.env`, `credentials.json`, cookies, tokens) are NOT staged.
```bash
git add path/to/modified-file
git status
git diff --staged
```

### Step 4: Commit with Descriptive Conventional Message
Write clear semantic commit messages:
```bash
git commit -m "feat(scope): concise description of changes"
# or
git commit -m "fix(scope): concise description of fix"
```

### Step 5: Push Feature Branch to Remote Origin
Push the new branch to GitHub and set upstream tracking:
```bash
git push -u origin feat/<descriptive-name>
```

### Step 6: Create Pull Request via GitHub CLI
Open a Pull Request with a clear title and summary:
```bash
gh pr create \
  --base main \
  --head feat/<descriptive-name> \
  --title "feat(scope): descriptive title" \
  --body "### Summary
- Key change 1
- Key change 2

### Testing
- Verification details"
```

### Step 7: Provide PR Link to User
Present the resulting GitHub PR link to the user for review and merging.

---

## 3. Emergency Restoration Procedure (Accidental Commit to Main)

If an agent or user accidentally commits and pushes directly to `main`, execute this exact recovery runbook:

1. **Locate the last clean commit on `main`**:
   ```bash
   git log -n 5 --oneline
   ```
2. **Preserve the changes on a new feature branch**:
   ```bash
   git branch feat/<feature-name>
   git push origin feat/<feature-name>
   ```
3. **Reset local `main` to the clean commit**:
   ```bash
   git reset --hard <clean-commit-hash>
   ```
4. **Force-push local `main` to remote `origin/main`**:
   ```bash
   git push origin main --force
   ```
5. **Switch to the feature branch and submit PR**:
   ```bash
   git checkout feat/<feature-name>
   gh pr create --base main --head feat/<feature-name> --title "..." --body "..."
   ```

---

## 4. Protected Files & Content Rules

- **Trip Artifacts**: Store user-generated itineraries, markdown notes, and CSVs in `/workspace/trips/`.
- **Credentials & Secrets**: Never stage `.env`, session cookies, or API keys.
