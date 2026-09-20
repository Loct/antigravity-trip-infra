---
name: booking-auth
description: Authenticate and configure Booking.com integration, extract session cookies or API keys, manage credentials in .env and ~/.config/booking/, and verify hotel/lodging operations.
---

# Booking.com Authentication Skill

This skill guides Antigravity on authenticating with [Booking.com](https://www.booking.com) for hotel, lodging, and accommodation queries and reservation management.

---

## 1. Authentication Overview

Booking.com integrations generally operate via two modes:

1. **Browser Session Authentication**: For accessing personal reservations, saved lists, and account bookings.
2. **API Key Authentication**: For real-time hotel search, price comparisons, and availability queries (e.g., Booking.com API or RapidAPI Booking.com gateway).

All credentials are persisted in:
- `.env` (`BOOKING_SESSION_COOKIE`, `BOOKING_API_KEY`)
- `/root/.config/booking/credentials.json` (backed by persistent Docker volume `booking_data`)

---

## 2. Authentication Methods

### Method A: Browser Session Cookie — Recommended for Account & Bookings

#### Extraction Instructions:
1. Open [https://www.booking.com](https://www.booking.com) in your browser and sign in.
2. Open Developer Tools (`F12` or `Cmd + Option + I` on Mac).
3. Navigate to **Application** / **Storage** -> **Cookies** -> `https://www.booking.com`.
4. Locate the key session cookies:
   - **`bkng_sso_session`** (primary SSO token)
   - Or **`bkng`** / **`last_selected_currency`**
5. Copy the cookie string.

#### Storing in `.env`:
```env
BOOKING_SESSION_COOKIE="bkng_sso_session=eyJhbGciOi...; bkng=..."
```

---

### Method B: API Key (Developer / RapidAPI) — Recommended for Hotel Search

If using Booking.com search APIs:
1. Obtain an API key from Booking.com Developer Portal or RapidAPI Booking.com service.
2. Set the key in `.env`:
   ```env
   BOOKING_API_KEY="your-api-key-here"
   ```

---

### Method C: Automated Setup Helper

Run the interactive setup helper:
```bash
./scripts/login_booking.sh
```

---

## 3. Integration with Wanderlog

Once Booking.com credentials are configured, Antigravity can:
1. Search and inspect hotel accommodations matching trip destinations.
2. Format reservation details (hotel name, address, check-in, check-out, confirmation number).
3. Automatically link and add lodging blocks to Wanderlog trips using:
   ```bash
   wanderlog trips lodging add <trip-id> \
     --name "Hotel Name" \
     --check-in YYYY-MM-DD \
     --check-out YYYY-MM-DD
   ```
