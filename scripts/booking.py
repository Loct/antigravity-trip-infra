#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.27.0",
#     "rich>=13.0.0",
#     "beautifulsoup4>=4.12.0",
# ]
# ///
"""
Booking.com Hotel Search & Lodging Integration CLI

Supports hybrid search via:
1. RapidAPI / Booking.com API (BOOKING_API_KEY or RAPIDAPI_KEY)
2. Apify Booking Scraper (APIFY_TOKEN with voyager/booking-scraper)
3. Direct Web Search & Session Cookies (BOOKING_SESSION_COOKIE fallback)

Integrates directly with Wanderlog trips via Wanderlog CLI.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()
err_console = Console(stderr=True)


DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", os.getenv("BOOKING_CURRENCY", "EUR"))
DEFAULT_GENIUS_LEVEL = int(os.getenv("GENIUS_LEVEL", os.getenv("BOOKING_GENIUS_LEVEL", "3")))
GENIUS_DISCOUNT_RATES = {
    1: 0.10,  # Level 1: 10%
    2: 0.15,  # Level 2: 15%
    3: 0.20,  # Level 3: 20%
}
_UNSET = object()


@dataclasses.dataclass
class Hotel:
    name: str
    hotel_id: str
    rating: Optional[float] = None
    review_count: Optional[int] = None
    review_word: Optional[str] = None
    price_text: Optional[str] = None
    price_per_night: Optional[float] = None
    total_price: Optional[float] = None
    currency: str = DEFAULT_CURRENCY
    genius_price: Optional[float] = None
    genius_price_text: Optional[str] = None
    is_genius_deal: bool = False
    genius_discount_rate: float = 0.0
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    url: Optional[str] = None
    photo_url: Optional[str] = None
    badges: List[str] = dataclasses.field(default_factory=list)
    provider: str = "booking"
    check_in: str = ""
    check_out: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class BookingConfig:
    def __init__(
        self,
        api_key: Any = _UNSET,
        rapidapi_host: Optional[str] = None,
        apify_token: Any = _UNSET,
        apify_actor: Optional[str] = None,
        session_cookie: Any = _UNSET,
    ):
        if api_key == "":
            self.api_key = None
        elif api_key is not None and api_key is not _UNSET:
            self.api_key = api_key
        else:
            self.api_key = self._resolve_api_key()

        self.rapidapi_host = rapidapi_host or self._resolve_rapidapi_host()

        if apify_token == "":
            self.apify_token = None
        elif apify_token is not None and apify_token is not _UNSET:
            self.apify_token = apify_token
        else:
            self.apify_token = self._resolve_apify_token()

        self.apify_actor = apify_actor or os.getenv(
            "APIFY_BOOKING_ACTOR", "voyager/booking-scraper"
        )

        if session_cookie == "":
            self.session_cookie = None
        elif session_cookie is not None and session_cookie is not _UNSET:
            self.session_cookie = session_cookie
        else:
            self.session_cookie = self._resolve_session_cookie()

    def _resolve_api_key(self) -> Optional[str]:
        # Check env vars
        for var in [
            "BOOKING_API_KEY",
            "RAPIDAPI_KEY",
            "BOOKING_COM_ACCESS_TOKEN",
            "RAPID_API_KEY",
        ]:
            val = os.getenv(var)
            if val and val.strip():
                return val.strip()

        # Check config file in ~/.config/booking/api_config.json
        cfg_path = Path.home() / ".config" / "booking" / "api_config.json"
        if cfg_path.is_file():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                val = data.get("api_key") or data.get("rapidapi_key")
                if val and str(val).strip():
                    return str(val).strip()
            except Exception:
                pass

        # Check .env in workspace
        env_path = Path("/workspace/.env")
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k in [
                        "BOOKING_API_KEY",
                        "RAPIDAPI_KEY",
                        "BOOKING_COM_ACCESS_TOKEN",
                    ] and v:
                        return v
            except Exception:
                pass

        return None

    def _resolve_rapidapi_host(self) -> str:
        for var in ["RAPIDAPI_HOST", "BOOKING_RAPIDAPI_HOST"]:
            val = os.getenv(var)
            if val and val.strip():
                return val.strip()

        cfg_path = Path.home() / ".config" / "booking" / "api_config.json"
        if cfg_path.is_file():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                val = data.get("rapidapi_host")
                if val and str(val).strip():
                    return str(val).strip()
            except Exception:
                pass

        env_path = Path("/workspace/.env")
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k in ["RAPIDAPI_HOST", "BOOKING_RAPIDAPI_HOST"] and v:
                        return v
            except Exception:
                pass

        return "booking-com15.p.rapidapi.com"

    def _resolve_apify_token(self) -> Optional[str]:
        val = os.getenv("APIFY_TOKEN")
        if val and val.strip():
            return val.strip()

        cfg_path = Path.home() / ".config" / "apify" / "credentials.json"
        if cfg_path.is_file():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                val = data.get("token") or data.get("api_token")
                if val and str(val).strip():
                    return str(val).strip()
            except Exception:
                pass

        env_path = Path("/workspace/.env")
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k == "APIFY_TOKEN" and v:
                        return v
            except Exception:
                pass

        return None

    def _resolve_session_cookie(self) -> Optional[str]:
        for var in ["BOOKING_SESSION_COOKIE", "BOOKING_COM_COOKIES", "BOOKING_COOKIE"]:
            val = os.getenv(var)
            if val and val.strip():
                return val.strip()

        cfg_path = Path.home() / ".config" / "booking" / "credentials.json"
        if cfg_path.is_file():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                val = data.get("session_cookie") or data.get("cookie")
                if val and str(val).strip():
                    return str(val).strip()
            except Exception:
                pass

        env_path = Path("/workspace/.env")
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k in ["BOOKING_SESSION_COOKIE", "BOOKING_COM_COOKIES"] and v:
                        return v
            except Exception:
                pass

        return None


def search_rapidapi(
    location: str,
    check_in: str,
    check_out: str,
    guests: int,
    rooms: int,
    currency: str,
    limit: int,
    config: BookingConfig,
) -> List[Hotel]:
    """Search hotels using RapidAPI Booking.com endpoints."""
    if not config.api_key:
        raise ValueError("RapidAPI key is not configured.")

    headers = {
        "X-RapidAPI-Key": config.api_key,
        "X-RapidAPI-Host": config.rapidapi_host,
    }

    with httpx.Client(timeout=30.0) as client:
        # Check host type
        host = config.rapidapi_host.lower()
        hotels: List[Hotel] = []

        if "booking-com15" in host:
            # Step 1: Destination search
            dest_url = f"https://{config.rapidapi_host}/api/v1/hotels/searchDestination"
            r_dest = client.get(dest_url, params={"query": location}, headers=headers)
            r_dest.raise_for_status()
            dest_json = r_dest.json()

            dest_items = dest_json.get("data", [])
            if not dest_items:
                raise ValueError(f"No destination found for '{location}'.")

            dest_id = dest_items[0].get("dest_id")
            search_type = dest_items[0].get("search_type", "city")

            # Step 2: Hotel search
            search_url = f"https://{config.rapidapi_host}/api/v1/hotels/searchHotels"
            params = {
                "dest_id": dest_id,
                "search_type": search_type,
                "arrival_date": check_in,
                "departure_date": check_out,
                "adults": str(guests),
                "room_qty": str(rooms),
                "page_number": "1",
                "units": "metric",
                "temperature_unit": "c",
                "languagecode": "en-us",
                "currency_code": currency,
            }
            r_search = client.get(search_url, params=params, headers=headers)
            r_search.raise_for_status()
            res_data = r_search.json().get("data", {})
            raw_hotels = res_data.get("hotels", [])

            for item in raw_hotels[:limit]:
                prop = item.get("property", {})
                name = prop.get("name", "Unknown Hotel")
                hotel_id = str(item.get("hotel_id", prop.get("id", "")))
                rating = prop.get("reviewScore")
                review_count = prop.get("reviewCount")
                review_word = prop.get("reviewScoreWord")

                price_info = prop.get("priceBreakdown", {}).get("grossPrice", {})
                price_val = price_info.get("value")
                price_curr = price_info.get("currency", currency)
                price_str = f"{price_curr} {price_val:.2f}" if price_val else None

                lat = prop.get("latitude")
                lng = prop.get("longitude")
                photo_url = prop.get("photoUrls", [None])[0] if prop.get("photoUrls") else None
                url = f"https://www.booking.com/hotel/{hotel_id}.html"

                badges = []
                if prop.get("isBeachFront"):
                    badges.append("Beachfront")
                if prop.get("isFreeCancellation"):
                    badges.append("Free cancellation")

                hotels.append(
                    Hotel(
                        name=name,
                        hotel_id=hotel_id,
                        rating=float(rating) if rating is not None else None,
                        review_count=int(review_count) if review_count is not None else None,
                        review_word=review_word,
                        price_text=price_str,
                        total_price=float(price_val) if price_val is not None else None,
                        currency=price_curr,
                        address=prop.get("wishlistName") or location,
                        latitude=float(lat) if lat is not None else None,
                        longitude=float(lng) if lng is not None else None,
                        url=url,
                        photo_url=photo_url,
                        badges=badges,
                        provider="RapidAPI (Booking.com)",
                        check_in=check_in,
                        check_out=check_out,
                    )
                )

        elif "booking-com18" in host:
            # Step 1: Destination search via /stays/auto-complete
            dest_url = f"https://{config.rapidapi_host}/stays/auto-complete"
            r_dest = client.get(dest_url, params={"query": location}, headers=headers)
            r_dest.raise_for_status()
            dest_json = r_dest.json()

            dest_items = dest_json.get("data", [])
            if not dest_items:
                raise ValueError(f"No destination found for '{location}'.")

            loc_id = dest_items[0].get("id") or dest_items[0].get("dest_id")

            # Step 2: Hotel search via /stays/search
            search_url = f"https://{config.rapidapi_host}/stays/search"
            params = {
                "locationId": loc_id,
                "checkinDate": check_in,
                "checkoutDate": check_out,
                "adults": guests,
                "rooms": rooms,
                "currency": currency,
            }
            r_search = client.get(search_url, params=params, headers=headers)
            r_search.raise_for_status()
            raw_data = r_search.json().get("data", [])
            raw_hotels = (
                raw_data
                if isinstance(raw_data, list)
                else (raw_data.get("hotels", []) if isinstance(raw_data, dict) else [])
            )

            for item in raw_hotels[:limit]:
                name = item.get("name") or item.get("hotel_name", "Unknown Hotel")
                hotel_id = str(item.get("id") or item.get("hotel_id", ""))
                rating = item.get("reviewScore") or item.get("review_score")
                review_count = item.get("reviewCount") or item.get("review_nr")
                review_word = item.get("reviewScoreWord") or item.get("review_score_word")

                price_info = item.get("priceBreakdown", {}).get("grossPrice", {})
                price_val = price_info.get("value")
                price_curr = price_info.get("currency", currency)
                price_str = price_info.get("amountRounded") or (
                    f"{price_curr} {float(price_val):.2f}" if price_val is not None else None
                )

                lat = item.get("latitude")
                lng = item.get("longitude")
                photo_urls = item.get("photoUrls", [])
                photo_url = photo_urls[0] if photo_urls else None
                url = f"https://www.booking.com/hotel/{hotel_id}.html"

                badges = []
                for b in item.get("priceBreakdown", {}).get("benefitBadges", []):
                    if isinstance(b, dict) and b.get("text"):
                        badges.append(b["text"])
                    elif isinstance(b, str):
                        badges.append(b)

                hotels.append(
                    Hotel(
                        name=name,
                        hotel_id=hotel_id,
                        rating=float(rating) if rating is not None and rating > 0 else None,
                        review_count=int(review_count) if review_count is not None and review_count > 0 else None,
                        review_word=review_word if review_word else None,
                        price_text=price_str,
                        total_price=float(price_val) if price_val is not None else None,
                        currency=price_curr,
                        address=item.get("wishlistName") or location,
                        latitude=float(lat) if lat is not None else None,
                        longitude=float(lng) if lng is not None else None,
                        url=url,
                        photo_url=photo_url,
                        badges=badges,
                        provider="RapidAPI (booking-com18)",
                        check_in=check_in,
                        check_out=check_out,
                    )
                )

        else:
            # Standard booking-com.p.rapidapi.com or compatible
            dest_url = f"https://{config.rapidapi_host}/v1/hotels/locations"
            r_dest = client.get(
                dest_url, params={"name": location, "locale": "en-us"}, headers=headers
            )
            r_dest.raise_for_status()
            dest_items = r_dest.json()
            if not dest_items or not isinstance(dest_items, list):
                raise ValueError(f"No destination found for '{location}'.")

            dest_id = dest_items[0].get("dest_id")
            dest_type = dest_items[0].get("dest_type", "city")

            search_url = f"https://{config.rapidapi_host}/v1/hotels/search"
            params = {
                "dest_id": str(dest_id),
                "dest_type": str(dest_type),
                "checkin_date": check_in,
                "checkout_date": check_out,
                "adults_number": str(guests),
                "room_number": str(rooms),
                "units": "metric",
                "order_by": "popularity",
                "page_number": "0",
                "currency_code": currency,
            }
            r_search = client.get(search_url, params=params, headers=headers)
            r_search.raise_for_status()
            raw_hotels = r_search.json().get("result", [])

            for item in raw_hotels[:limit]:
                name = item.get("hotel_name", "Unknown Hotel")
                hotel_id = str(item.get("hotel_id", ""))
                rating = item.get("review_score")
                review_count = item.get("review_nr")
                review_word = item.get("review_score_word")

                price_val = item.get("min_total_price")
                price_curr = item.get("currency_code", currency)
                price_str = f"{price_curr} {price_val:.2f}" if price_val else None

                lat = item.get("latitude")
                lng = item.get("longitude")
                url = item.get("url") or f"https://www.booking.com/hotel/{hotel_id}.html"
                address = item.get("address") or item.get("city_trans") or location

                badges = []
                if item.get("is_free_cancellable"):
                    badges.append("Free cancellation")
                if item.get("has_free_parking"):
                    badges.append("Free parking")

                hotels.append(
                    Hotel(
                        name=name,
                        hotel_id=hotel_id,
                        rating=float(rating) if rating is not None else None,
                        review_count=int(review_count) if review_count is not None else None,
                        review_word=review_word,
                        price_text=price_str,
                        total_price=float(price_val) if price_val is not None else None,
                        currency=price_curr,
                        address=address,
                        latitude=float(lat) if lat is not None else None,
                        longitude=float(lng) if lng is not None else None,
                        url=url,
                        photo_url=item.get("main_photo_url"),
                        badges=badges,
                        provider="RapidAPI (Booking.com)",
                        check_in=check_in,
                        check_out=check_out,
                    )
                )

        return hotels


def search_apify(
    location: str,
    check_in: str,
    check_out: str,
    guests: int,
    rooms: int,
    currency: str,
    limit: int,
    config: BookingConfig,
) -> List[Hotel]:
    """Search hotels using Apify Booking.com scraper actor."""
    if not config.apify_token:
        raise ValueError("Apify token is not configured.")

    actor_id = config.apify_actor.replace("/", "~")
    url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
    params = {"token": config.apify_token}
    payload = {
        "search": location,
        "checkInDate": check_in,
        "checkOutDate": check_out,
        "adults": guests,
        "rooms": rooms,
        "currency": currency,
        "maxItems": limit,
    }

    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, params=params, json=payload)
        r.raise_for_status()
        items = r.json()

    hotels: List[Hotel] = []
    for item in items[:limit]:
        name = item.get("name") or item.get("title") or "Unknown Hotel"
        hotel_id = str(item.get("id") or item.get("hotel_id") or "")
        rating = item.get("rating") or item.get("reviewScore")
        review_count = item.get("reviewsCount") or item.get("reviewCount")
        review_word = item.get("reviewScoreWord") or item.get("ratingText")

        price = item.get("price") or item.get("totalPrice")
        price_val = None
        price_str = None
        if isinstance(price, (int, float)):
            price_val = float(price)
            price_str = f"{currency} {price_val:.2f}"
        elif isinstance(price, str):
            price_str = price
            # Extract numbers if possible
            match = re.search(r"([\d,]+(?:\.\d+)?)", price)
            if match:
                try:
                    price_val = float(match.group(1).replace(",", ""))
                except Exception:
                    pass

        address = item.get("address") or item.get("location") or location
        if isinstance(address, dict):
            address = address.get("full") or address.get("name") or ", ".join(f"{v}" for v in address.values() if isinstance(v, str))
        lat = item.get("lat") or item.get("latitude")
        lng = item.get("lng") or item.get("longitude")
        url_link = item.get("url") or item.get("link")

        badges = []
        if item.get("freeCancellation"):
            badges.append("Free cancellation")
        if item.get("stars"):
            badges.append(f"{item.get('stars')}★")

        hotels.append(
            Hotel(
                name=name,
                hotel_id=hotel_id,
                rating=float(rating) if rating is not None else None,
                review_count=int(review_count) if review_count is not None else None,
                review_word=review_word,
                price_text=price_str,
                total_price=price_val,
                currency=currency,
                address=address,
                latitude=float(lat) if lat is not None else None,
                longitude=float(lng) if lng is not None else None,
                url=url_link,
                photo_url=item.get("image") or item.get("photoUrl"),
                badges=badges,
                provider=f"Apify ({config.apify_actor})",
                check_in=check_in,
                check_out=check_out,
            )
        )

    return hotels


def search_scrape(
    location: str,
    check_in: str,
    check_out: str,
    guests: int,
    rooms: int,
    currency: str,
    limit: int,
    config: BookingConfig,
) -> List[Hotel]:
    """Search hotels via direct web search fallback."""
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.booking.com/",
    }

    if config.session_cookie:
        headers["Cookie"] = config.session_cookie

    params = {
        "ss": location,
        "checkin": check_in,
        "checkout": check_out,
        "group_adults": str(guests),
        "no_rooms": str(rooms),
        "selected_currency": currency,
    }

    url = "https://www.booking.com/searchresults.html"
    with httpx.Client(timeout=25.0, follow_redirects=True) as client:
        r = client.get(url, params=params, headers=headers)
        if r.status_code in [202, 403]:
            raise PermissionError(
                f"Booking.com returned status {r.status_code} (anti-bot protection challenge). "
                "Direct web scraping from datacenters requires a RapidAPI key (BOOKING_API_KEY) "
                "or Apify token (APIFY_TOKEN). Run './scripts/login_booking.sh' to configure."
            )
        r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.select('[data-testid="property-card"]')
    if not cards:
        # Fallback card selectors
        cards = soup.select(".sr_item, [data-hotel-id]")

    hotels: List[Hotel] = []
    for card in cards[:limit]:
        title_el = card.select_one('[data-testid="title"]') or card.select_one(".sr-hotel__name")
        name = title_el.get_text(strip=True) if title_el else "Unknown Hotel"

        # Hotel ID / Link
        link_el = card.select_one('a[data-testid="title-link"]') or card.select_one("a.hotel_name_link")
        link = link_el["href"] if link_el and "href" in link_el.attrs else None
        if link and link.startswith("/"):
            link = f"https://www.booking.com{link}"

        # Review score
        score_el = card.select_one('[data-testid="review-score"]') or card.select_one(".bui-review-score__badge")
        score_val = None
        if score_el:
            score_match = re.search(r"(\d+(?:\.\d+)?)", score_el.get_text())
            if score_match:
                try:
                    score_val = float(score_match.group(1))
                except Exception:
                    pass

        # Price
        price_el = card.select_one('[data-testid="price-and-discounted-price"]') or card.select_one(".prco-valign-middle-helper")
        price_str = price_el.get_text(strip=True) if price_el else None
        price_val = None
        if price_str:
            match = re.search(r"([\d,]+(?:\.\d+)?)", price_str)
            if match:
                try:
                    price_val = float(match.group(1).replace(",", ""))
                except Exception:
                    pass

        # Address
        addr_el = card.select_one('[data-testid="address"]') or card.select_one(".sr_card_address_line")
        addr = addr_el.get_text(strip=True) if addr_el else location

        hotels.append(
            Hotel(
                name=name,
                hotel_id="",
                rating=score_val,
                price_text=price_str,
                total_price=price_val,
                currency=currency,
                address=addr,
                url=link,
                provider="Direct Scrape (Booking.com)",
                check_in=check_in,
                check_out=check_out,
            )
        )

    if not hotels:
        raise ValueError(
            "No property cards could be parsed from Booking.com response. "
            "Please use RapidAPI or Apify."
        )

    return hotels


def apply_genius_discounts(hotels: List[Hotel], genius_level: int) -> None:
    """Apply Genius loyalty program discounts to hotel rates."""
    if genius_level <= 0:
        return

    discount_rate = GENIUS_DISCOUNT_RATES.get(genius_level, 0.20 if genius_level >= 3 else 0.10)
    for h in hotels:
        if h.total_price:
            g_price = round(h.total_price * (1.0 - discount_rate), 2)
            h.genius_price = g_price
            h.genius_discount_rate = discount_rate
            h.is_genius_deal = True
            curr_symbol = "€ " if h.currency == "EUR" else ("$ " if h.currency == "USD" else f"{h.currency} ")
            h.genius_price_text = f"{curr_symbol}{g_price:.2f}"
            badge_text = f"Genius L{genius_level} (-{int(discount_rate*100)}%)"
            if badge_text not in h.badges:
                h.badges.append(badge_text)


def search_hotels(
    location: str,
    check_in: str,
    check_out: str,
    guests: int = 2,
    rooms: int = 1,
    currency: str = DEFAULT_CURRENCY,
    limit: int = 10,
    provider: str = "auto",
    genius_level: int = DEFAULT_GENIUS_LEVEL,
    config: Optional[BookingConfig] = None,
) -> Tuple[List[Hotel], str]:
    """Execute hybrid search using the best available provider."""
    cfg = config or BookingConfig()
    errors = []

    # Priority order for auto: RapidAPI -> Apify -> Direct Scrape
    if provider in ["rapidapi", "auto"]:
        if cfg.api_key:
            try:
                results = search_rapidapi(
                    location=location,
                    check_in=check_in,
                    check_out=check_out,
                    guests=guests,
                    rooms=rooms,
                    currency=currency,
                    limit=limit,
                    config=cfg,
                )
                if results:
                    apply_genius_discounts(results, genius_level)
                    return results, f"RapidAPI ({cfg.rapidapi_host})"
            except Exception as e:
                errors.append(f"RapidAPI failed: {e}")
                if provider == "rapidapi":
                    raise

    if provider in ["apify", "auto"]:
        if cfg.apify_token:
            try:
                results = search_apify(
                    location=location,
                    check_in=check_in,
                    check_out=check_out,
                    guests=guests,
                    rooms=rooms,
                    currency=currency,
                    limit=limit,
                    config=cfg,
                )
                if results:
                    apply_genius_discounts(results, genius_level)
                    return results, f"Apify ({cfg.apify_actor})"
            except Exception as e:
                errors.append(f"Apify failed: {e}")
                if provider == "apify":
                    raise

    if provider in ["scrape", "auto"]:
        try:
            results = search_scrape(
                location=location,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                rooms=rooms,
                currency=currency,
                limit=limit,
                config=cfg,
            )
            if results:
                apply_genius_discounts(results, genius_level)
                return results, "Direct Web Scrape"
        except Exception as e:
            errors.append(f"Direct scrape failed: {e}")
            if provider == "scrape":
                raise

    # If we reached here, no provider succeeded
    err_summary = "\n  - ".join(errors) if errors else "No active provider credentials configured."
    raise RuntimeError(
        f"Unable to complete Booking.com hotel search.\n"
        f"Attempted providers reported:\n  - {err_summary}\n\n"
        f"To fix this, configure one of the following:\n"
        f"  1. Run './scripts/login_booking.sh' and configure a RapidAPI / Booking API key\n"
        f"  2. Set BOOKING_API_KEY or RAPIDAPI_KEY in .env\n"
        f"  3. Set APIFY_TOKEN in .env for voyager/booking-scraper\n"
    )


def print_pretty_table(
    hotels: List[Hotel],
    location: str,
    check_in: str,
    check_out: str,
    guests: int,
    provider_name: str,
    genius_level: int = DEFAULT_GENIUS_LEVEL,
) -> None:
    genius_tag = ""
    if genius_level > 0:
        disc_pct = int(GENIUS_DISCOUNT_RATES.get(genius_level, 0.20) * 100)
        genius_tag = f"\n[bold cyan]✨ Genius Level {genius_level} Active (-{disc_pct}% loyalty discount applied)[/bold cyan]"

    table = Table(
        title=f"🏨 Booking.com Hotels in {location} ({check_in} → {check_out}, {guests} guests){genius_tag}\n[dim]Source: {provider_name}[/dim]",
        header_style="bold magenta",
        show_lines=True,
    )

    table.add_column("#", justify="center", style="dim", width=4)
    table.add_column("Hotel Name", style="bold white", min_width=25)
    table.add_column("Rating", justify="center", width=12)
    table.add_column("Price", justify="right", width=16)
    table.add_column("Location / Address", style="dim", min_width=25)
    table.add_column("Amenities / Badges", style="cyan", min_width=18)

    for idx, h in enumerate(hotels, start=1):
        # Rating text with color
        if h.rating is not None:
            if h.rating >= 9.0:
                rating_str = f"[bold green]{h.rating:.1f}[/bold green]"
            elif h.rating >= 8.0:
                rating_str = f"[green]{h.rating:.1f}[/green]"
            elif h.rating >= 7.0:
                rating_str = f"[yellow]{h.rating:.1f}[/yellow]"
            else:
                rating_str = f"[red]{h.rating:.1f}[/red]"

            if h.review_word:
                rating_str += f"\n[dim]{h.review_word}[/dim]"
            if h.review_count:
                rating_str += f"\n[dim]({h.review_count} revs)[/dim]"
        else:
            rating_str = "[dim]N/A[/dim]"

        # Price formatting with Genius tier
        if h.genius_price_text and h.genius_price is not None:
            price_str = (
                f"[dim strikethrough]{h.price_text}[/dim strikethrough]\n"
                f"[bold green]{h.genius_price_text}[/bold green]\n"
                f"[dim cyan](Genius L{genius_level})[/dim cyan]"
            )
        else:
            price_str = h.price_text or (
                f"{h.currency} {h.total_price:.2f}" if h.total_price else "[dim]Check site[/dim]"
            )
            price_str = f"[bold yellow]{price_str}[/bold yellow]"

        badges_str = ", ".join(h.badges) if h.badges else "[dim]Standard[/dim]"
        address_str = (h.address.get("full") if isinstance(h.address, dict) else h.address) or "[dim]N/A[/dim]"

        name_text = h.name
        if h.url:
            name_text = f"[link={h.url}]{h.name}[/link]"

        table.add_row(
            str(idx),
            name_text,
            rating_str,
            price_str,
            address_str,
            badges_str,
        )

    console.print(table)


def add_lodging_to_wanderlog(
    hotel: Hotel,
    trip_key: str,
    notes: Optional[str] = None,
    interactive: bool = True,
) -> bool:
    """Add hotel lodging to a Wanderlog trip using the wanderlog CLI."""
    price_desc = hotel.price_text or "N/A"
    if hotel.genius_price_text:
        price_desc = f"{hotel.genius_price_text} (Genius discount applied, retail {hotel.price_text})"

    booking_notes = notes or (
        f"Booking.com lodging.\n"
        f"Rating: {hotel.rating or 'N/A'}/10 ({hotel.review_word or ''})\n"
        f"Price: {price_desc}\n"
        f"URL: {hotel.url or 'N/A'}"
    )

    cmd = [
        "wanderlog",
        "trips",
        "lodging",
        "add",
        trip_key,
        "--name",
        hotel.name,
        "--check-in",
        hotel.check_in,
        "--check-out",
        hotel.check_out,
        "--notes",
        booking_notes,
    ]

    if hotel.latitude is not None and hotel.longitude is not None:
        cmd.extend(["--lat", str(hotel.latitude), "--lng", str(hotel.longitude)])

    if interactive:
        console.print(
            Panel(
                f"[bold cyan]Action Required: Confirm Trip Mutation[/bold cyan]\n\n"
                f"• Trip Key:   [bold green]{trip_key}[/bold green]\n"
                f"• Property:   [bold]{hotel.name}[/bold]\n"
                f"• Dates:      {hotel.check_in} → {hotel.check_out}\n"
                f"• Price:      {price_desc}\n"
                f"• Address:    {hotel.address or 'N/A'}\n\n"
                f"Execute command: [dim]{' '.join(cmd)}[/dim]",
                title="Wanderlog Trip Mutation Confirmation",
                border_style="yellow",
            )
        )
        confirm = input("Confirm adding this lodging to Wanderlog? [y/N]: ").strip().lower()
        if confirm not in ["y", "yes"]:
            console.print("[yellow]Operation cancelled by user.[/yellow]")
            return False

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        console.print(
            f"[bold green]✅ Successfully added '{hotel.name}' to Wanderlog trip {trip_key}![/bold green]"
        )
        if res.stdout.strip():
            console.print(f"[dim]{res.stdout.strip()}[/dim]")
        return True
    else:
        err_console.print(
            f"[bold red]❌ Failed to add lodging to Wanderlog:[/bold red]\n{res.stderr.strip()}"
        )
        return False


def run_status_check(config: BookingConfig) -> None:
    """Print configuration and connectivity status for all providers."""
    table = Table(
        title="🔍 Booking.com Integration Status",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Provider / Setting", style="bold white", width=25)
    table.add_column("Status", width=15)
    table.add_column("Details", style="dim")

    # 1. RapidAPI
    if config.api_key:
        masked_key = config.api_key[:4] + "..." + config.api_key[-4:] if len(config.api_key) > 8 else "***"
        table.add_row(
            "RapidAPI Key",
            "[green]Configured[/green]",
            f"Key: {masked_key} | Host: {config.rapidapi_host}",
        )
    else:
        table.add_row(
            "RapidAPI Key",
            "[yellow]Not Configured[/yellow]",
            "Set BOOKING_API_KEY in .env or run ./scripts/login_booking.sh",
        )

    # 2. Apify
    if config.apify_token:
        masked_tok = config.apify_token[:6] + "..." + config.apify_token[-4:] if len(config.apify_token) > 10 else "***"
        table.add_row(
            "Apify Token",
            "[green]Configured[/green]",
            f"Token: {masked_tok} | Actor: {config.apify_actor}",
        )
    else:
        table.add_row(
            "Apify Token",
            "[yellow]Not Configured[/yellow]",
            "Set APIFY_TOKEN in .env or run ./scripts/login_booking.sh",
        )

    # 3. Session Cookie
    if config.session_cookie:
        table.add_row(
            "Session Cookie",
            "[green]Configured[/green]",
            f"Length: {len(config.session_cookie)} chars (bkng_sso_session)",
        )
    else:
        table.add_row(
            "Session Cookie",
            "[yellow]Not Configured[/yellow]",
            "Optional: Set BOOKING_SESSION_COOKIE for web access",
        )

    # 4. Genius Loyalty
    genius_lvl = int(os.getenv("GENIUS_LEVEL", os.getenv("BOOKING_GENIUS_LEVEL", str(DEFAULT_GENIUS_LEVEL))))
    if genius_lvl > 0:
        disc = int(GENIUS_DISCOUNT_RATES.get(genius_lvl, 0.20) * 100)
        table.add_row(
            "Genius Loyalty",
            f"[bold green]Level {genius_lvl}[/bold green]",
            f"Active: -{disc}% discount applied to searches (GENIUS_LEVEL={genius_lvl})",
        )
    else:
        table.add_row(
            "Genius Loyalty",
            "[dim]Disabled[/dim]",
            "Set GENIUS_LEVEL=3 in .env to apply 20% loyalty discounts",
        )

    # 5. Wanderlog CLI
    w_avail = subprocess.run(["which", "wanderlog"], capture_output=True).returncode == 0
    if w_avail:
        table.add_row(
            "Wanderlog CLI",
            "[green]Available[/green]",
            "Native trip lodging commands available",
        )
    else:
        table.add_row(
            "Wanderlog CLI",
            "[red]Missing[/red]",
            "wanderlog CLI not found in PATH",
        )

    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Booking.com Hotel Search and Wanderlog Integration CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute")

    # Subcommand: search
    search_p = subparsers.add_parser("search", help="Search hotels and lodging options")
    search_p.add_argument("-l", "--location", required=True, help="Destination city, region, or landmark")
    search_p.add_argument(
        "-i",
        "--check-in",
        help="Check-in date (YYYY-MM-DD, defaults to +14 days)",
    )
    search_p.add_argument(
        "-o",
        "--check-out",
        help="Check-out date (YYYY-MM-DD, defaults to +18 days)",
    )
    search_p.add_argument("-g", "--guests", type=int, default=2, help="Number of adults/guests (default: 2)")
    search_p.add_argument("-r", "--rooms", type=int, default=1, help="Number of rooms (default: 1)")
    search_p.add_argument(
        "-c",
        "--currency",
        default=DEFAULT_CURRENCY,
        help=f"Currency code (default: {DEFAULT_CURRENCY})",
    )
    search_p.add_argument(
        "--genius",
        type=int,
        choices=[0, 1, 2, 3],
        default=DEFAULT_GENIUS_LEVEL,
        help=f"Genius loyalty discount level (0=none, 1=10%, 2=15%, 3=20%, default: {DEFAULT_GENIUS_LEVEL})",
    )
    search_p.add_argument("--limit", type=int, default=10, help="Max results to display (default: 10)")
    search_p.add_argument(
        "-p",
        "--provider",
        choices=["auto", "rapidapi", "apify", "scrape"],
        default="auto",
        help="Search provider backend (default: auto)",
    )
    search_p.add_argument(
        "-f",
        "--format",
        choices=["pretty", "json"],
        default="pretty",
        help="Output format (default: pretty)",
    )
    search_p.add_argument(
        "--min-rating",
        type=float,
        help="Filter hotels by minimum review score (e.g. 8.0)",
    )
    search_p.add_argument(
        "--add-to-trip",
        metavar="TRIP_KEY",
        help="Interactively select a hotel from search results to add to a Wanderlog trip",
    )
    search_p.add_argument("--api-key", help="Override Booking / RapidAPI key")
    search_p.add_argument("--apify-token", help="Override Apify API token")
    search_p.add_argument("--session-cookie", help="Override Booking session cookie")

    # Subcommand: status
    subparsers.add_parser("status", help="Check configured credentials and connectivity status")

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    config = BookingConfig(
        api_key=getattr(args, "api_key", None),
        apify_token=getattr(args, "apify_token", None),
        session_cookie=getattr(args, "session_cookie", None),
    )

    if args.subcommand == "status":
        run_status_check(config)
        sys.exit(0)

    if args.subcommand == "search":
        # Calculate default dates if omitted
        today = datetime.date.today()
        check_in = args.check_in or (today + datetime.timedelta(days=14)).isoformat()
        check_out = args.check_out or (today + datetime.timedelta(days=18)).isoformat()

        try:
            hotels, provider_used = search_hotels(
                location=args.location,
                check_in=check_in,
                check_out=check_out,
                guests=args.guests,
                rooms=args.rooms,
                currency=args.currency,
                limit=args.limit,
                provider=args.provider,
                genius_level=args.genius,
                config=config,
            )
        except Exception as e:
            err_console.print(f"[bold red]Search failed:[/bold red] {e}")
            sys.exit(1)

        # Apply min-rating filter if specified
        if args.min_rating is not None:
            hotels = [h for h in hotels if h.rating is not None and h.rating >= args.min_rating]

        if not hotels:
            console.print(f"[yellow]No hotels found matching criteria in '{args.location}'.[/yellow]")
            sys.exit(0)

        if args.format == "json":
            out_data = {
                "location": args.location,
                "check_in": check_in,
                "check_out": check_out,
                "guests": args.guests,
                "rooms": args.rooms,
                "genius_level": args.genius,
                "provider": provider_used,
                "count": len(hotels),
                "hotels": [h.to_dict() for h in hotels],
            }
            print(json.dumps(out_data, indent=2))
        else:
            print_pretty_table(
                hotels=hotels,
                location=args.location,
                check_in=check_in,
                check_out=check_out,
                guests=args.guests,
                provider_name=provider_used,
                genius_level=args.genius,
            )

        # If user passed --add-to-trip, allow choosing a property
        if args.add_to_trip:
            console.print("")
            choice_str = input(
                f"Enter property # to add to Wanderlog trip '{args.add_to_trip}' (1-{len(hotels)}, or press Enter to skip): "
            ).strip()
            if choice_str.isdigit():
                idx = int(choice_str)
                if 1 <= idx <= len(hotels):
                    selected_hotel = hotels[idx - 1]
                    add_lodging_to_wanderlog(
                        hotel=selected_hotel,
                        trip_key=args.add_to_trip,
                        interactive=True,
                    )
                else:
                    err_console.print("[red]Invalid index selected.[/red]")


if __name__ == "__main__":
    main()
