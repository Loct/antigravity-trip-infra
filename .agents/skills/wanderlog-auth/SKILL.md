---
name: wanderlog-auth
description: Authenticate and verify Wanderlog credentials, extract session cookies (connect.sid), manage API tokens, and diagnose Wanderlog connection status.
---

# Wanderlog Authentication Skill

This skill provides step-by-step instructions for Antigravity to authenticate, verify, and maintain access to [Wanderlog](https://wanderlog.com).

---

## 1. Verifying Current Authentication Status

Always check the current login status first:

```bash
wanderlog status
```

- **If authenticated**: The command outputs the logged-in user's email, name, and user ID.
- **If unauthenticated**: The command exits with an error indicating missing or expired credentials.

To check via Docker container:
```bash
docker compose exec antigravity-wanderlog wanderlog status
```

---

## 2. Authentication Methods

### Method A: Browser Session Cookie (connect.sid) — Recommended

Wanderlog web uses standard session cookies. This method does not require storing passwords and bypasses Google/Apple Single Sign-On barriers.

#### Extraction Instructions for User:
1. Open [https://wanderlog.com](https://wanderlog.com) in your browser and confirm you are signed in (avatar/name visible in top-right).
2. Open Developer Tools (`F12` or `Cmd + Option + I` on Mac).
3. Navigate to **Application** (Chrome/Edge) or **Storage** (Firefox/Safari) -> **Cookies** -> `https://wanderlog.com`.
4. Locate the cookie named **`connect.sid`**.
5. Copy its complete value (usually begins with `s%3A...`).

#### Applying the Cookie:
Add or update the value in `.env`:
```env
WANDERLOG_AUTH_SESSION_COOKIE="s%3Ayoursessioncookiestring..."
```

Or write directly to `/root/.config/wanderlog/credentials.json`:
```json
{
  "SessionCookie": "<session-cookie-value>",
  "session_cookie": "<session-cookie-value>",
  "session": "<session-cookie-value>",
  "XSRFToken": "",
  "UserID": ""
}
```

Or execute the automated helper script:
```bash
./scripts/login_wanderlog.sh
```

---

### Method B: Interactive Login (Email & Password)

If the user signed up using email and password (not Google/Apple SSO):
```bash
docker compose exec -it antigravity-wanderlog wanderlog login
```
The CLI will prompt for email and password interactively and store the session in `~/.config/wanderlog/`.

---

## 3. Session Expiration & Refreshing

Wanderlog session cookies typically remain valid for several weeks. If commands begin failing with HTTP 401 / Unauthorized:
1. Re-run `wanderlog status` to confirm status.
2. Instruct user to grab a refreshed `connect.sid` from their browser.
3. Update `.env` and recreate the container:
   ```bash
   docker compose up -d --force-recreate
   ```
4. Verify again with `wanderlog trips list`.
