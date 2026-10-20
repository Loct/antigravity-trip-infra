#!/usr/bin/env bash
set -e

LOCATION=""
CHECK_IN=""
CHECK_OUT=""
GUESTS=1
SOURCE="all"
LIMIT=10
OUTPUT="pretty"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Search for lodging across Wanderlog (Google rates), Apify Agoda, and Google Maps.

Options:
  -l, --location <string>    Destination / location (e.g. "Tokyo", "Paris") [required]
  -i, --check-in <YYYY-MM-DD>  Check-in date [optional, defaults to +14 days]
  -o, --check-out <YYYY-MM-DD> Check-out date [optional, defaults to +18 days]
  -g, --guests <number>      Number of guests (default: 1)
  -s, --source <name>        Search source: "wanderlog", "agoda", "gmaps", or "all" (default: "all")
      --limit <number>       Maximum results per provider (default: 10)
      --output <format>      Output format: "pretty" or "json" (default: "pretty")
  -h, --help                 Show this help message

Environment variables:
  APIFY_TOKEN                Apify API token for Agoda and Google Maps scraping
  APIFY_AGODA_ACTOR          Apify actor for Agoda (default: tri_angle/agoda-scraper)
  APIFY_GMAPS_ACTOR          Apify actor for Google Maps (default: compass/crawler-google-places)

Examples:
  $(basename "$0") -l "Kyoto" -i 2026-10-01 -o 2026-10-05 -s all
  $(basename "$0") -l "Rome" -s wanderlog
  $(basename "$0") -l "Bangkok" -s agoda --limit 5
EOF
  exit 1
}

# Parse command line options
while [[ $# -gt 0 ]]; do
  case "$1" in
    -l|--location)
      LOCATION="$2"
      shift 2
      ;;
    -i|--check-in)
      CHECK_IN="$2"
      shift 2
      ;;
    -o|--check-out)
      CHECK_OUT="$2"
      shift 2
      ;;
    -g|--guests)
      GUESTS="$2"
      shift 2
      ;;
    -s|--source)
      SOURCE="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      if [ -z "$LOCATION" ]; then
        LOCATION="$1"
        shift
      else
        echo "Unknown option: $1"
        usage
      fi
      ;;
  esac
done

if [ -z "$LOCATION" ]; then
  echo "[!] Error: Location is required."
  usage
fi

# Default dates if not specified
if [ -z "$CHECK_IN" ]; then
  CHECK_IN=$(date -u -d "+14 days" +%Y-%m-%d 2>/dev/null || date -u -v+14d +%Y-%m-%d 2>/dev/null || echo "2026-10-01")
fi
if [ -z "$CHECK_OUT" ]; then
  CHECK_OUT=$(date -u -d "+18 days" +%Y-%m-%d 2>/dev/null || date -u -v+18d +%Y-%m-%d 2>/dev/null || echo "2026-10-05")
fi

# Load credentials from .env or credentials.json if available
if [ -z "${APIFY_TOKEN:-}" ]; then
  if [ -f /root/.config/apify/credentials.json ]; then
    APIFY_TOKEN=$(jq -r '.token // empty' /root/.config/apify/credentials.json 2>/dev/null || true)
  fi
  if [ -z "$APIFY_TOKEN" ] && [ -f /workspace/.env ]; then
    APIFY_TOKEN=$(grep "^APIFY_TOKEN=" /workspace/.env | cut -d '=' -f2- | tr -d '"' | tr -d "'" | tr -d ' ' || true)
  fi
fi

APIFY_AGODA_ACTOR="${APIFY_AGODA_ACTOR:-tri_angle/agoda-scraper}"
APIFY_GMAPS_ACTOR="${APIFY_GMAPS_ACTOR:-compass/crawler-google-places}"

# Temporary scratch directory for results
TMP_DIR="$(mktemp -d /tmp/lodging-search.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

# 1. Search Wanderlog
search_wanderlog() {
  echo "[-] Searching Wanderlog (Google lodging engine)..." >&2
  if command -v wanderlog >/dev/null 2>&1; then
    WANDERLOG_RAW=$(wanderlog travel hotels "$LOCATION" --check-in "$CHECK_IN" --check-out "$CHECK_OUT" --guests "$GUESTS" -o json 2>/dev/null || echo '{"data":[]}')
    echo "$WANDERLOG_RAW" | jq --arg limit "$LIMIT" '
      (.data // [])[0:($limit | tonumber)] | map({
        provider: "wanderlog_google",
        name: .name,
        rating: .rating,
        price: .price,
        address: .address,
        property_id: .propertyId,
        url: (if .propertyId then "https://wanderlog.com/hotel/" + (.propertyId | tostring) else null end)
      })
    ' > "$TMP_DIR/wanderlog.json" 2>/dev/null || echo '[]' > "$TMP_DIR/wanderlog.json"
  else
    echo "[]" > "$TMP_DIR/wanderlog.json"
  fi
}

# 2. Search Agoda via Apify
search_agoda() {
  if [ -z "$APIFY_TOKEN" ]; then
    echo "[!] Notice: APIFY_TOKEN is not configured. Run './scripts/login_apify.sh' to enable Agoda search." >&2
    echo "[]" > "$TMP_DIR/agoda.json"
    return
  fi

  echo "[-] Querying Agoda scraper via Apify ($APIFY_AGODA_ACTOR)..." >&2
  ENCODED_ACTOR=$(echo "$APIFY_AGODA_ACTOR" | sed 's/\//~/g')
  
  AGODA_INPUT=$(cat <<EOF
{
  "location": "$LOCATION",
  "checkIn": "$CHECK_IN",
  "checkOut": "$CHECK_OUT",
  "rooms": 1,
  "adults": $GUESTS,
  "maxItems": $LIMIT
}
EOF
)

  AGODA_RESP=$(curl -sSL -X POST \
    -H "Content-Type: application/json" \
    "https://api.apify.com/v2/acts/${ENCODED_ACTOR}/run-sync-get-dataset-items?token=${APIFY_TOKEN}&timeout=60" \
    -d "$AGODA_INPUT" 2>/dev/null || echo '[]')

  echo "$AGODA_RESP" | jq --arg limit "$LIMIT" '
    if type == "array" then
      .[0:($limit | tonumber)] | map({
        provider: "agoda_apify",
        name: (.hotelName // .name // .title),
        rating: (.rating // .score),
        price: (.price // .dailyRate // .totalPrice),
        address: (.address // .neighborhood // .city),
        property_id: (.hotelId // .id),
        url: (.hotelUrl // .url)
      })
    else
      []
    end
  ' > "$TMP_DIR/agoda.json" 2>/dev/null || echo '[]' > "$TMP_DIR/agoda.json"
}

# 3. Search Google Maps via Apify
search_gmaps() {
  if [ -z "$APIFY_TOKEN" ]; then
    echo "[!] Notice: APIFY_TOKEN is not configured. Run './scripts/login_apify.sh' to enable Google Maps Apify search." >&2
    echo "[]" > "$TMP_DIR/gmaps.json"
    return
  fi

  echo "[-] Querying Google Maps scraper via Apify ($APIFY_GMAPS_ACTOR)..." >&2
  ENCODED_ACTOR=$(echo "$APIFY_GMAPS_ACTOR" | sed 's/\//~/g')

  GMAPS_INPUT=$(cat <<EOF
{
  "searchStringsArray": ["hotels in $LOCATION"],
  "maxCrawledPlacesPerSearch": $LIMIT
}
EOF
)

  GMAPS_RESP=$(curl -sSL -X POST \
    -H "Content-Type: application/json" \
    "https://api.apify.com/v2/acts/${ENCODED_ACTOR}/run-sync-get-dataset-items?token=${APIFY_TOKEN}&timeout=60" \
    -d "$GMAPS_INPUT" 2>/dev/null || echo '[]')

  echo "$GMAPS_RESP" | jq --arg limit "$LIMIT" '
    if type == "array" then
      .[0:($limit | tonumber)] | map({
        provider: "google_maps_apify",
        name: (.title // .name),
        rating: .totalScore,
        reviews_count: .reviewsCount,
        price: .price,
        address: (.address // .neighborhood),
        place_id: .placeId,
        url: .url
      })
    else
      []
    end
  ' > "$TMP_DIR/gmaps.json" 2>/dev/null || echo '[]' > "$TMP_DIR/gmaps.json"
}

# Run selected sources
case "$SOURCE" in
  wanderlog)
    search_wanderlog
    echo "[]" > "$TMP_DIR/agoda.json"
    echo "[]" > "$TMP_DIR/gmaps.json"
    ;;
  agoda)
    echo "[]" > "$TMP_DIR/wanderlog.json"
    search_agoda
    echo "[]" > "$TMP_DIR/gmaps.json"
    ;;
  gmaps)
    echo "[]" > "$TMP_DIR/wanderlog.json"
    echo "[]" > "$TMP_DIR/agoda.json"
    search_gmaps
    ;;
  all)
    search_wanderlog
    search_agoda
    # Wanderlog already covers Google lodging data natively; if Apify is configured we also include Google Maps Places
    if [ -n "$APIFY_TOKEN" ]; then
      search_gmaps
    else
      echo "[]" > "$TMP_DIR/gmaps.json"
    fi
    ;;
  *)
    echo "[!] Unknown source: $SOURCE"
    exit 1
    ;;
esac

# Combine results
jq -s '
  {
    location: "'"$LOCATION"'",
    check_in: "'"$CHECK_IN"'",
    check_out: "'"$CHECK_OUT"'",
    guests: ('"$GUESTS"'),
    wanderlog: .[0],
    agoda: .[1],
    google_maps: .[2]
  }
' "$TMP_DIR/wanderlog.json" "$TMP_DIR/agoda.json" "$TMP_DIR/gmaps.json" > "$TMP_DIR/combined.json"

if [ "$OUTPUT" = "json" ]; then
  cat "$TMP_DIR/combined.json"
  exit 0
fi

# Pretty Print Output
echo ""
echo "=========================================================="
echo "  Lodging Search Results for: $LOCATION"
echo "  Dates: $CHECK_IN -> $CHECK_OUT | Guests: $GUESTS"
echo "=========================================================="

echo ""
echo "--- Wanderlog (Google Lodging) ---"
W_COUNT=$(jq '.wanderlog | length' "$TMP_DIR/combined.json")
if [ "$W_COUNT" -eq 0 ]; then
  echo "  (No results or source disabled)"
else
  jq -r '.wanderlog[] | "• \(.name) [★ \(.rating // "N/A")] - Price: \(.price // "Check rates") | Property ID: \(.property_id // "N/A")"' "$TMP_DIR/combined.json"
fi

echo ""
echo "--- Agoda (via Apify) ---"
A_COUNT=$(jq '.agoda | length' "$TMP_DIR/combined.json")
if [ "$A_COUNT" -eq 0 ]; then
  if [ -z "$APIFY_TOKEN" ]; then
    echo "  (Requires APIFY_TOKEN. Run ./scripts/login_apify.sh to set up)"
  else
    echo "  (No results returned)"
  fi
else
  jq -r '.agoda[] | "• \(.name) [★ \(.rating // "N/A")] - Price: \(.price // "N/A") | \(.url // "agoda.com")"' "$TMP_DIR/combined.json"
fi

echo ""
echo "--- Google Maps Places (via Apify) ---"
G_COUNT=$(jq '.google_maps | length' "$TMP_DIR/combined.json")
if [ "$G_COUNT" -eq 0 ]; then
  if [ -z "$APIFY_TOKEN" ]; then
    echo "  (Requires APIFY_TOKEN. Run ./scripts/login_apify.sh to set up)"
  else
    echo "  (No results returned)"
  fi
else
  jq -r '.google_maps[] | "• \(.name) [★ \(.rating // "N/A")] - Address: \(.address // "N/A")"' "$TMP_DIR/combined.json"
fi

echo ""
echo "=========================================================="
echo "Tip: To add any selected hotel to your Wanderlog itinerary:"
echo "  wanderlog trips lodging add <trip-id> --name \"<Hotel Name>\" --check-in $CHECK_IN --check-out $CHECK_OUT"
echo "=========================================================="
