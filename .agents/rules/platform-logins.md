# Platform Authentication & Login Guidelines (Memo)

This memo authorizes and directs Antigravity on how to manage, verify, and guide user authentication across all external platforms—including travel services, code hosting, and third-party booking providers.

---

## 1. Supported Platforms & Scope

Antigravity is explicitly allowed and configured to facilitate user logins and credential management for:
1. **Wanderlog** (`https://wanderlog.com`): Travel itinerary and trip planning.
2. **GitHub** (`https://github.com`): Code repository management, version control, and GitHub CLI (`gh`).
3. **Booking.com** (`https://booking.com`): Hotel, lodging, and accommodation search and bookings.
4. **Apify** (`https://apify.com`): Cloud scraping and multi-OTA hotel comparison (Agoda, Google Hotels, Booking.com) via Model Context Protocol (MCP).
5. **New / Future Platforms** (e.g. Airbnb, Skyscanner, Google Flights, Expedia): Any new travel or utility platform added to the environment must follow the Standard Platform Onboarding Protocol below.

---

## 2. Authentication Policy & Principles

When a user requests to log in to, connect with, or authenticate any platform:

1. **Verify Existing Status First**:
   - Check if credentials already exist before prompting the user (e.g. check `.env`, `~/.config/<platform>/`, or run platform status commands like `wanderlog status`, `gh auth status`).
   - If already authenticated, confirm the current identity/status and ask if they wish to re-authenticate or keep existing credentials.

2. **Non-Blocking & Remote-Friendly Flows**:
   - Always favor non-blocking, headless-friendly authentication methods:
     - **Web Device Codes**: One-time codes with authorization URLs (e.g., `gh auth login --web`).
     - **Browser Session Cookies**: Guiding the user to extract session cookies (e.g., `connect.sid` for Wanderlog, `bkng_sso_session` for Booking.com) from browser DevTools (`F12 -> Application/Storage -> Cookies`).
     - **API Tokens / Keys**: Personal Access Tokens (PATs) or API keys pasted into `.env` or passed via dedicated CLI commands.

3. **Persistent Credential Storage**:
   - All credentials must be stored in persistent storage locations backed by Docker volumes or workspace configuration:
     - `.env` in the workspace root for environment variables.
     - `~/.config/<platform>/` for CLI configuration and tokens (mounted to persistent Docker volumes).
   - Never write credentials to temporary directories (like `/tmp`) or non-persistent container layers.

4. **Security & Privacy**:
   - **Never print secret keys, tokens, passwords, or full session cookies into conversation responses.**
   - Mask secret values when echoing status (e.g. `s%3AA8...[REDACTED]`).
   - Ensure credential files have appropriate permissions (`chmod 600`).
   - Ensure `.env` is listed in `.gitignore` to prevent committing secrets to version control.

---

## 3. Standard Platform Onboarding Protocol (New Platforms)

When adding support or authenticating a new platform (e.g., Booking.com, Airbnb, etc.):

1. **Identify Required Auth Type**:
   - **Cookie-based**: Requires browser session cookie. Document the cookie key (e.g., `bkng_sso_session` for Booking.com).
   - **API Key-based**: Requires developer/affiliate API key (e.g., `BOOKING_API_KEY` or `RAPIDAPI_KEY`).
   - **OAuth / Device Code**: Requires CLI tool with device authorization grant.

2. **Standard Configuration Locations**:
   - Environment Variable: Add `<PLATFORM>_AUTH_SESSION_COOKIE` or `<PLATFORM>_API_KEY` to `.env.example` and `.env`.
   - Config Directory: `/root/.config/<platform>/credentials.json`.
   - Docker Volume: `<platform>_data:/root/.config/<platform>` in `docker-compose.yml`.

3. **Provide Guided User Instructions**:
   - Clearly explain in numbered steps how the user can obtain their credentials from their browser or developer portal.
   - Offer to write the credentials directly to `.env` or provide an automated helper script (`./scripts/login_<platform>.sh`).

4. **Add Dedicated Skill**:
   - Create a skill in `.agents/skills/<platform>-auth/SKILL.md` documenting the authentication workflows, validation commands, and API usage patterns.
