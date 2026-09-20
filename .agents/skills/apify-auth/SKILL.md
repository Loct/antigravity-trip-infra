---
name: apify-auth
description: Configure Apify API tokens, test connection to mcp.apify.com, and manage credentials for Agoda and multi-OTA hotel comparison scrapers.
---

# Apify Authentication & Setup Skill

This skill guides Antigravity on authenticating with [Apify](https://apify.com) to enable cloud-based hotel and OTA price comparisons.

---

## 1. Checking Authentication Status

Run these commands to inspect Apify credentials:

```bash
# Check if APIFY_TOKEN is present in environment
echo "APIFY_TOKEN is ${APIFY_TOKEN:+'set'}"

# Verify credentials file inside container
cat /root/.config/apify/credentials.json 2>/dev/null

# Test API connectivity and get active user info
curl -s -f -H "Authorization: Bearer $APIFY_TOKEN" https://api.apify.com/v2/users/me | jq '{username: .data.username, email: .data.email}'
```

---

## 2. Authentication Methods

### Method A: Automated Setup Script (Recommended)
Run the built-in wizard:
```bash
./scripts/login_apify.sh
```
The script validates the token against Apify's `/v2/users/me` endpoint, writes it to `.env`, and saves it to `/root/.config/apify/credentials.json`.

### Method B: Manual Token Setup
1. Log in to [Apify Console](https://console.apify.com/).
2. Navigate to **Settings > Integrations** (`https://console.apify.com/account#/integrations`).
3. Under **Personal API tokens**, copy your token (`apify_api_...`).
4. Add to `.env`:
   ```env
   APIFY_TOKEN="apify_api_your_token_here"
   ```
5. Save to the persistent volume:
   ```bash
   mkdir -p /root/.config/apify
   cat <<EOF > /root/.config/apify/credentials.json
   {
     "token": "apify_api_your_token_here",
     "updated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
   }
   EOF
   chmod 600 /root/.config/apify/credentials.json
   ```

---

## 3. Connecting with Antigravity via MCP

The Apify MCP server is registered in `mcp_config.json`:

```json
{
  "mcpServers": {
    "apify": {
      "serverUrl": "https://mcp.apify.com",
      "headers": {
        "Authorization": "Bearer ${APIFY_TOKEN}"
      }
    }
  }
}
```

Discovered actors and tools (like `compass/google-hotels-scraper` and `johnvc/agoda-hotel-api`) will be exposed directly as callable tools for real-time price comparisons.
