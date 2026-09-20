---
name: github-auth
description: Authenticate GitHub CLI (gh), configure Git user identity, manage Personal Access Tokens (PAT), configure credential helpers, and verify GitHub repository access.
---

# GitHub & Git Authentication Skill

This skill guides Antigravity on authenticating with [GitHub](https://github.com) and configuring Git within the containerized environment.

---

## 1. Checking Authentication & Git Configuration Status

Run these commands to inspect the active state:

```bash
# Check GitHub CLI authentication status and account
gh auth status

# Check Git global user identity
git config --global user.name
git config --global user.email

# View full git configuration origins
git config --list --show-origin
```

Inside Docker:
```bash
docker compose exec antigravity-wanderlog gh auth status
```

---

## 2. Authentication Methods

### Method A: One-Time Device Code (Interactive / Web Browser) — Recommended

This method uses GitHub's OAuth Device Flow and does not require generating or handling Personal Access Tokens manually.

1. Run the interactive login command:
   ```bash
   docker compose exec -it antigravity-wanderlog gh auth login
   ```
2. When prompted:
   - What account do you want to log into? -> **GitHub.com**
   - What is your preferred protocol for Git operations? -> **HTTPS**
   - Authenticate Git with your GitHub credentials? -> **Yes**
   - How would you like to authenticate GitHub CLI? -> **Login with a web browser**
3. The terminal displays a one-time code (e.g., `1234-ABCD`) and a link:
   `https://github.com/login/device`
4. Open the link in a browser, enter the 8-character code, and click **Authorize GitHub**.
5. Once authorized, the terminal automatically completes the login and writes persistent credentials to the `github_data` volume.

---

### Method B: Personal Access Token (PAT)

Best for automated deployments, headless servers, or fine-grained repository permissions:

1. Generate a token at [https://github.com/settings/tokens](https://github.com/settings/tokens) (Classic token with `repo` scope or Fine-Grained token with Repository Read/Write access).
2. Either set `GH_TOKEN` in `.env`:
   ```env
   GH_TOKEN="ghp_yourpersonalaccesstoken..."
   ```
   Or authenticate directly via CLI inside the container:
   ```bash
   echo "<TOKEN>" | docker compose exec -T antigravity-wanderlog gh auth login --with-token
   docker compose exec -T antigravity-wanderlog gh auth setup-git
   ```

---

### Method C: Automated Helper Script

Users can run the interactive setup wizard at any time:
```bash
./scripts/login_github.sh
```

---

## 3. Configuring Git Author Identity

To ensure commits made by Antigravity have the proper author name and email:

```bash
# Set author name
docker compose exec antigravity-wanderlog git config --global user.name "Your Name"

# Set author email
docker compose exec antigravity-wanderlog git config --global user.email "your.email@example.com"
```
Or define `GIT_USER_NAME` and `GIT_USER_EMAIL` in `.env`.

---

## 4. Setting Up Git Credential Helper

To ensure `git clone`, `git push`, and `git pull` use GitHub CLI credentials without prompting for username/password:

```bash
docker compose exec antigravity-wanderlog gh auth setup-git
```
This registers `gh auth git-credential` in the global Git configuration.
