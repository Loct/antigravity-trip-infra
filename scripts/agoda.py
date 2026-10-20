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
Agoda Hotel Search & Lodging Integration CLI

Supports hybrid hotel search via:
1. RapidAPI / Agoda API (AGODA_API_KEY or RAPIDAPI_KEY)
2. Apify Agoda Scraper (APIFY_TOKEN with tri_angle/agoda-scraper or configured actor)
3. Direct Web Search & Session Cookies (AGODA_SESSION_COOKIE fallback)

Integrates directly with Wanderlog trips via Wanderlog CLI and MCP tools.
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
    currency: str = "USD"
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    url: Optional[str] = None
    photo_url: Optional[str] = None
    badges: List[str] = dataclasses.field(default_factory=list)
    provider: str = "agoda"
    check_in: str = ""
    check_out: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class AgodaConfig:
    def __init__(
        self,
        api_key: Optional[str] = None,
        rapidapi_host: Optional[str] = None,
        apify_token: Optional[str] = None,
        apify_actor: Optional[str] = None,
        session_cookie: Optional[str] = None,
    ):
        self.api_key = api_key or self._resolve_api_key()
        self.rapidapi_host = rapidapi_host or self._resolve_rapidapi_host()
        self.apify_token = apify_token or self._resolve_apify_token()
        self.apify_actor = apify_actor or os.getenv(
            "APIFY_AGODA_ACTOR", "tri_angle/agoda-scraper"
        )
        self.session_cookie = session_cookie or self._resolve_session_cookie()

    def _resolve_rapidapi_host(self) -> str:
        for var in ["AGODA_RAPIDAPI_HOST", "RAPIDAPI_HOST"]:
            val = os.getenv(var)
            if val and val.strip():
                return val.strip()

        cfg_path = Path.home() / ".config" / "agoda" / "api_config.json"
        if cfg_path.is_file():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                val = data.get("rapidapi_host") or data.get("host")
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
                    if k in ["AGODA_RAPIDAPI_HOST", "RAPIDAPI_HOST"] and v:
                        return v
            except Exception:
                pass

        return "agoda-com.p.rapidapi.com"

    def _resolve_api_key(self) -> Optional[str]:
        # Check env vars
        for var in [
            "AGODA_API_KEY",
            "RAPIDAPI_KEY",
            "AGODA_COM_ACCESS_TOKEN",
            "RAPID_API_KEY",
        ]:
            val = os.getenv(var)
            if val and val.strip():
                return val.strip()

        # Check config file in ~/.config/agoda/api_config.json
        cfg_path = Path.home() / ".config" / "agoda" / "api_config.json"
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
                        "AGODA_API_KEY",
                        "RAPIDAPI_KEY",
                        "AGODA_COM_ACCESS_TOKEN",
                    ] and v:
                        return v
            except Exception:
                pass

        return None

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
        for var in ["AGODA_SESSION_COOKIE", "AGODA_COM_COOKIES", "AGODA_COOKIE"]:
            val = os.getenv(var)
            if val and val.strip():
                return val.strip()

        cfg_path = Path.home() / ".config" / "agoda" / "credentials.json"
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
                    if k in ["AGODA_SESSION_COOKIE", "AGODA_COM_COOKIES"] and v:
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
    config: AgodaConfig,
) -> List[Hotel]:
    """Search hotels using RapidAPI Agoda endpoints."""
    if not config.api_key:
        raise ValueError("RapidAPI key is not configured for Agoda.")

    headers = {
        "X-RapidAPI-Key": config.api_key,
        "X-RapidAPI-Host": config.rapidapi_host,
    }

    with httpx.Client(timeout=30.0) as client:
        host = config.rapidapi_host.lower()
        hotels: List[Hotel] = []

        # Step 1: Destination / location search
        dest_url = f"https://{config.rapidapi_host}/api/v1/hotels/auto-complete"
        dest_id = None
        try:
            r_dest = client.get(
                dest_url,
                params={"query": location, "locale": "en-us"},
                headers=headers,
            )
            if r_dest.status_code == 200:
                dest_json = r_dest.json()
                items = dest_json.get("data", dest_json) if isinstance(dest_json, dict) else dest_json
                if isinstance(items, list) and items:
                    first = items[0]
                    dest_id = first.get("id") or first.get("city_id") or first.get("dest_id")
        except Exception:
            pass

        # Step 2: Hotel search
        search_url = f"https://{config.rapidapi_host}/api/v1/hotels/search"
        params: Dict[str, Any] = {
            "checkIn": check_in,
            "checkOut": check_out,
            "adults": str(guests),
            "rooms": str(rooms),
            "currency": currency,
            "limit": str(limit),
        }
        if dest_id:
            params["city_id"] = str(dest_id)
        else:
            params["query"] = location

        r_search = client.get(search_url, params=params, headers=headers)
        r_search.raise_for_status()
        res_data = r_search.json()

        raw_hotels = []
        if isinstance(res_data, dict):
            raw_hotels = (
                res_data.get("data", {}).get("hotels", [])
                or res_data.get("data", [])
                or res_data.get("hotels", [])
                or res_data.get("results", [])
            )
        elif isinstance(res_data, list):
            raw_hotels = res_data

        if not raw_hotels and isinstance(res_data, dict) and "result" in res_data:
            raw_hotels = res_data["result"]

        for item in raw_hotels[:limit]:
            prop = item.get("property", item)
            name = (
                prop.get("name")
                or prop.get("hotel_name")
                or prop.get("hotelName")
                or prop.get("title")
                or "Unknown Hotel"
            )
            hotel_id = str(
                prop.get("hotel_id")
                or prop.get("hotelId")
                or prop.get("id")
                or item.get("hotel_id", "")
            )
            rating = (
                prop.get("rating")
                or prop.get("review_score")
                or prop.get("reviewScore")
                or prop.get("score")
            )
            review_count = (
                prop.get("review_count")
                or prop.get("review_nr")
                or prop.get("reviewsCount")
                or prop.get("reviewCount")
            )
            review_word = (
                prop.get("review_word")
                or prop.get("review_score_word")
                or prop.get("ratingText")
            )

            # Extract pricing
            price_val = None
            price_info = prop.get("price") or prop.get("pricing") or prop.get("dailyRate")
            if isinstance(price_info, dict):
                price_val = price_info.get("total") or price_info.get("value") or price_info.get("gross")
                price_curr = price_info.get("currency", currency)
            elif isinstance(price_info, (int, float)):
                price_val = float(price_info)
                price_curr = currency
            else:
                price_val = prop.get("min_total_price") or prop.get("totalPrice")
                price_curr = currency

            price_str = f"{price_curr} {float(price_val):.2f}" if price_val is not None else None

            lat = prop.get("latitude") or prop.get("lat")
            lng = prop.get("longitude") or prop.get("lng")
            url = (
                prop.get("url")
                or prop.get("hotelUrl")
                or (f"https://www.agoda.com/hotel/{hotel_id}.html" if hotel_id else "https://www.agoda.com")
            )
            photo = (
                prop.get("photo_url")
                or prop.get("image")
                or prop.get("photoUrl")
                or prop.get("main_photo_url")
            )
            address = (
                prop.get("address")
                or prop.get("neighborhood")
                or prop.get("city")
                or location
            )

            badges = []
            if prop.get("is_free_cancellable") or prop.get("freeCancellation"):
                badges.append("Free cancellation")
            if prop.get("stars") or prop.get("star_rating"):
                stars = prop.get("stars") or prop.get("star_rating")
                badges.append(f"{stars}★")

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
                    photo_url=photo,
                    badges=badges,
                    provider="RapidAPI (Agoda)",
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
    config: AgodaConfig,
) -> List[Hotel]:
    """Search hotels using Apify Agoda scraper actor."""
    if not config.apify_token:
        raise ValueError("Apify token is not configured.")

    actor_id = config.apify_actor.replace("/", "~")
    url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
    params = {"token": config.apify_token}
    payload = {
        "location": location,
        "search": location,
        "checkIn": check_in,
        "checkInDate": check_in,
        "checkOut": check_out,
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

    if not isinstance(items, list):
        items = []

    hotels: List[Hotel] = []
    for item in items[:limit]:
        name = (
            item.get("hotelName")
            or item.get("name")
            or item.get("title")
            or "Unknown Hotel"
        )
        hotel_id = str(item.get("hotelId") or item.get("id") or "")
        rating = item.get("rating") or item.get("score") or item.get("reviewScore")
        review_count = item.get("reviewsCount") or item.get("reviewCount")
        review_word = item.get("ratingText") or item.get("reviewScoreWord")

        price = (
            item.get("price")
            or item.get("dailyRate")
            or item.get("totalPrice")
            or item.get("rate")
        )
        price_val = None
        price_str = None
        if isinstance(price, (int, float)):
            price_val = float(price)
            price_str = f"{currency} {price_val:.2f}"
        elif isinstance(price, str):
            price_str = price
            match = re.search(r"([\d,]+(?:\.\d+)?)", price)
            if match:
                try:
                    price_val = float(match.group(1).replace(",", ""))
                except Exception:
                    pass

        address = (
            item.get("address")
            or item.get("neighborhood")
            or item.get("city")
            or location
        )
        lat = item.get("lat") or item.get("latitude")
        lng = item.get("lng") or item.get("longitude")
        url_link = (
            item.get("hotelUrl")
            or item.get("url")
            or item.get("link")
            or (f"https://www.agoda.com/hotel/{hotel_id}.html" if hotel_id else "https://www.agoda.com")
        )

        badges = []
        if item.get("freeCancellation"):
            badges.append("Free cancellation")
        if item.get("breakfastIncluded"):
            badges.append("Breakfast included")
        if item.get("starRating") or item.get("stars"):
            stars = item.get("starRating") or item.get("stars")
            badges.append(f"{stars}★")

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
    config: AgodaConfig,
) -> List[Hotel]:
    """Search hotels via direct Agoda public search API / web fallback."""
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.agoda.com/",
    }

    if config.session_cookie:
        headers["Cookie"] = config.session_cookie

    hotels: List[Hotel] = []

    with httpx.Client(timeout=25.0, headers=headers, follow_redirects=True) as client:
        # Step 1: Query Agoda suggestion / auto-complete endpoint
        suggest_url = "https://www.agoda.com/Search/Search/GetJsonDataSuggestions"
        city_id = None
        city_name = location

        try:
            r_sug = client.get(suggest_url, params={"searchText": location, "pageSize": 5})
            if r_sug.status_code == 200:
                sug_data = r_sug.json()
                items = sug_data.get("Data", []) if isinstance(sug_data, dict) else []
                if items:
                    first = items[0]
                    city_id = first.get("ObjectId") or first.get("CityId")
                    city_name = first.get("ObjectName") or location
        except Exception:
            pass

        # Step 2: Query Agoda SearchResultList API or fallback to landing page search
        search_api_url = "https://www.agoda.com/api/cronos/property/search/SearchResultList"
        payload = {
            "cityId": city_id,
            "searchText": location,
            "checkIn": check_in,
            "checkOut": check_out,
            "rooms": rooms,
            "adults": guests,
            "currency": currency,
            "pageNumber": 1,
            "pageSize": limit,
        }

        try:
            r_post = client.post(search_api_url, json=payload)
            if r_post.status_code == 200:
                res_json = r_post.json()
                props = res_json.get("properties", []) or res_json.get("results", [])
                for prop in props[:limit]:
                    name = prop.get("displayName") or prop.get("propertyName") or "Unknown Hotel"
                    hotel_id = str(prop.get("propertyId") or prop.get("hotelId") or "")
                    rating = prop.get("rating") or prop.get("reviewScore")
                    review_count = prop.get("reviewCount")
                    review_word = prop.get("reviewScoreWord") or prop.get("ratingText")

                    price_info = prop.get("pricing", {})
                    price_val = price_info.get("pricePerNight") or price_info.get("totalPrice")
                    price_str = f"{currency} {price_val:.2f}" if price_val else None

                    lat = prop.get("latitude")
                    lng = prop.get("longitude")
                    url = prop.get("propertyUrl") or f"https://www.agoda.com/hotel/{hotel_id}.html"

                    badges = []
                    if prop.get("isFreeCancellation"):
                        badges.append("Free cancellation")
                    if prop.get("starRating"):
                        badges.append(f"{prop.get('starRating')}★")

                    hotels.append(
                        Hotel(
                            name=name,
                            hotel_id=hotel_id,
                            rating=float(rating) if rating is not None else None,
                            review_count=int(review_count) if review_count is not None else None,
                            review_word=review_word,
                            price_text=price_str,
                            total_price=float(price_val) if price_val is not None else None,
                            currency=currency,
                            address=prop.get("address", location),
                            latitude=float(lat) if lat is not None else None,
                            longitude=float(lng) if lng is not None else None,
                            url=url,
                            photo_url=prop.get("photoUrl"),
                            badges=badges,
                            provider="Agoda Web",
                            check_in=check_in,
                            check_out=check_out,
                        )
                    )
                if hotels:
                    return hotels
        except Exception:
            pass

        # Fallback HTML scraping
        query_url = "https://www.agoda.com/en-gb/pages/agoda/default/DestinationSearchResult.aspx"
        params = {
            "city": str(city_id or location),
            "checkIn": check_in,
            "checkOut": check_out,
            "rooms": str(rooms),
            "adults": str(guests),
        }
        r_page = client.get(query_url, params=params)
        soup = BeautifulSoup(r_page.text, "html.parser")

        # Parse property cards
        cards = soup.select("[data-selenium='hotel-item']") or soup.select(".PropertyCard")
        for card in cards[:limit]:
            name_el = card.select_one("[data-selenium='hotel-name']") or card.select_one("h3")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)

            score_el = card.select_one("[data-selenium='review-score']") or card.select_one(".ReviewScore")
            rating = None
            if score_el:
                try:
                    rating = float(re.search(r"(\d+(?:\.\d+)?)", score_el.get_text()).group(1))
                except Exception:
                    pass

            price_el = card.select_one("[data-selenium='display-price']") or card.select_one(".PropertyCardPrice")
            price_str = price_el.get_text(strip=True) if price_el else None
            price_val = None
            if price_str:
                m = re.search(r"([\d,]+(?:\.\d+)?)", price_str)
                if m:
                    try:
                        price_val = float(m.group(1).replace(",", ""))
                    except Exception:
                        pass

            link_el = card.select_one("a[href]")
            link = f"https://www.agoda.com{link_el['href']}" if link_el else "https://www.agoda.com"

            hotels.append(
                Hotel(
                    name=name,
                    hotel_id="",
                    rating=rating,
                    price_text=price_str,
                    total_price=price_val,
                    currency=currency,
                    address=location,
                    url=link,
                    provider="Agoda Web",
                    check_in=check_in,
                    check_out=check_out,
                )
            )

    return hotels


def search_hotels(
    location: str,
    check_in: str,
    check_out: str,
    guests: int = 2,
    rooms: int = 1,
    currency: str = "USD",
    limit: int = 10,
    provider: str = "auto",
    config: Optional[AgodaConfig] = None,
) -> Tuple[List[Hotel], str]:
    """Search hotels across Agoda providers with hybrid fallback."""
    if config is None:
        config = AgodaConfig()

    provider = provider.lower()
    errors: List[str] = []

    # Direct provider routing
    if provider == "rapidapi":
        return search_rapidapi(
            location, check_in, check_out, guests, rooms, currency, limit, config
        ), "RapidAPI (Agoda)"

    if provider == "apify":
        return search_apify(
            location, check_in, check_out, guests, rooms, currency, limit, config
        ), f"Apify ({config.apify_actor})"

    if provider == "scrape":
        return search_scrape(
            location, check_in, check_out, guests, rooms, currency, limit, config
        ), "Agoda Web"

    # Auto mode: RapidAPI -> Apify -> Scrape
    if config.api_key:
        try:
            results = search_rapidapi(
                location, check_in, check_out, guests, rooms, currency, limit, config
            )
            if results:
                return results, "RapidAPI (Agoda)"
        except Exception as e:
            errors.append(f"RapidAPI: {e}")

    if config.apify_token:
        try:
            results = search_apify(
                location, check_in, check_out, guests, rooms, currency, limit, config
            )
            if results:
                return results, f"Apify ({config.apify_actor})"
        except Exception as e:
            errors.append(f"Apify: {e}")

    # Fallback to direct web scrape
    try:
        results = search_scrape(
            location, check_in, check_out, guests, rooms, currency, limit, config
        )
        if results:
            return results, "Agoda Web Fallback"
    except Exception as e:
        errors.append(f"Direct Web: {e}")

    if errors:
        msg = "; ".join(errors)
        raise RuntimeError(
            f"All Agoda providers failed for location '{location}'. Details: {msg}\n"
            "Tip: Run './scripts/login_agoda.sh' to configure AGODA_API_KEY or APIFY_TOKEN."
        )

    return [], "None"


def print_pretty_table(
    hotels: List[Hotel],
    location: str,
    check_in: str,
    check_out: str,
    guests: int,
    provider_name: str,
) -> None:
    """Render a rich, formatted table of hotel search results."""
    title_text = (
        f"🏨 [bold cyan]Agoda Lodging Options for '{location}'[/bold cyan]\n"
        f"[dim]Dates: {check_in} → {check_out} | Guests: {guests} | Source: {provider_name}[/dim]"
    )
    table = Table(
        title=title_text,
        title_justify="left",
        header_style="bold magenta",
        show_lines=True,
    )

    table.add_column("#", justify="right", style="cyan", width=3)
    table.add_column("Property Name", style="bold white", min_width=25)
    table.add_column("Rating", justify="center", width=12)
    table.add_column("Total Price", justify="right", style="bold green", width=14)
    table.add_column("Location / Badges", style="dim", min_width=25)
    table.add_column("Booking Link", style="blue underline", min_width=20)

    for idx, h in enumerate(hotels, start=1):
        # Format rating
        if h.rating is not None:
            if h.rating >= 9.0:
                score_str = f"[bold green]{h.rating:.1f}[/bold green]"
            elif h.rating >= 8.0:
                score_str = f"[green]{h.rating:.1f}[/green]"
            elif h.rating >= 7.0:
                score_str = f"[yellow]{h.rating:.1f}[/yellow]"
            else:
                score_str = f"[red]{h.rating:.1f}[/red]"

            if h.review_word:
                score_str += f"\n[dim]{h.review_word}[/dim]"
            if h.review_count:
                score_str += f"\n[dim]({h.review_count} rev)[/dim]"
        else:
            score_str = "[dim]N/A[/dim]"

        # Price string
        price_display = h.price_text or (
            f"{h.currency} {h.total_price:.2f}" if h.total_price else "[dim]Check rate[/dim]"
        )

        # Address & Badges
        loc_badges = []
        if h.address:
            loc_badges.append(h.address)
        if h.badges:
            loc_badges.append(" • ".join(f"[cyan]{b}[/cyan]" for b in h.badges))
        loc_display = "\n".join(loc_badges) if loc_badges else "[dim]N/A[/dim]"

        # URL
        url_display = h.url or f"https://www.agoda.com/hotel/{h.hotel_id}.html"

        table.add_row(
            str(idx),
            h.name,
            score_str,
            price_display,
            loc_display,
            url_display,
        )

    console.print(table)


def add_lodging_to_wanderlog(
    hotel: Hotel,
    trip_key: str,
    interactive: bool = True,
) -> bool:
    """
    Add selected Agoda lodging to a Wanderlog trip itinerary.
    Strictly enforces trip mutation confirmation rules.
    """
    booking_notes = (
        f"Booked via Agoda.\n"
        f"Rating: {hotel.rating}/10 ({hotel.review_word or ''})\n"
        f"Price: {hotel.price_text or 'N/A'}\n"
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
                f"• Price:      {hotel.price_text or 'N/A'}\n"
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


def run_status_check(config: AgodaConfig) -> None:
    """Print configuration and connectivity status for all Agoda providers."""
    table = Table(
        title="🔍 Agoda Integration Status",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Provider / Setting", style="bold white", width=25)
    table.add_column("Status", width=15)
    table.add_column("Details", style="dim")

    # 1. RapidAPI
    if config.api_key:
        masked_key = (
            config.api_key[:4] + "..." + config.api_key[-4:]
            if len(config.api_key) > 8
            else "***"
        )
        table.add_row(
            "RapidAPI / Agoda Key",
            "[green]Configured[/green]",
            f"Key: {masked_key} | Host: {config.rapidapi_host}",
        )
    else:
        table.add_row(
            "RapidAPI / Agoda Key",
            "[yellow]Not Configured[/yellow]",
            "Set AGODA_API_KEY in .env or run ./scripts/login_agoda.sh",
        )

    # 2. Apify
    if config.apify_token:
        masked_tok = (
            config.apify_token[:6] + "..." + config.apify_token[-4:]
            if len(config.apify_token) > 10
            else "***"
        )
        table.add_row(
            "Apify Token",
            "[green]Configured[/green]",
            f"Token: {masked_tok} | Actor: {config.apify_actor}",
        )
    else:
        table.add_row(
            "Apify Token",
            "[yellow]Not Configured[/yellow]",
            "Set APIFY_TOKEN in .env or run ./scripts/login_agoda.sh",
        )

    # 3. Session Cookie
    if config.session_cookie:
        table.add_row(
            "Session Cookie",
            "[green]Configured[/green]",
            f"Length: {len(config.session_cookie)} chars (AGODA_SESSION_COOKIE)",
        )
    else:
        table.add_row(
            "Session Cookie",
            "[yellow]Not Configured[/yellow]",
            "Optional: Set AGODA_SESSION_COOKIE for web access",
        )

    # 4. Wanderlog CLI
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
        description="Agoda Hotel Search and Wanderlog Integration CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute")

    # Subcommand: search
    search_p = subparsers.add_parser("search", help="Search hotels and lodging options on Agoda")
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
    search_p.add_argument("-c", "--currency", default="USD", help="Currency code (default: USD)")
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
        "--max-price",
        type=float,
        help="Filter hotels by maximum total price",
    )
    search_p.add_argument(
        "--add-to-trip",
        metavar="TRIP_KEY",
        help="Interactively select a hotel from search results to add to a Wanderlog trip",
    )
    search_p.add_argument("--api-key", help="Override Agoda / RapidAPI key")
    search_p.add_argument("--apify-token", help="Override Apify API token")
    search_p.add_argument("--session-cookie", help="Override Agoda session cookie")

    # Subcommand: status
    subparsers.add_parser("status", help="Check configured credentials and connectivity status")

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    config = AgodaConfig(
        api_key=getattr(args, "api_key", None),
        apify_token=getattr(args, "apify_token", None),
        session_cookie=getattr(args, "session_cookie", None),
    )

    if args.subcommand == "status":
        run_status_check(config)
        sys.exit(0)

    if args.subcommand == "search":
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
                config=config,
            )
        except Exception as e:
            err_console.print(f"[bold red]Search failed:[/bold red] {e}")
            sys.exit(1)

        # Filters
        if args.min_rating is not None:
            hotels = [h for h in hotels if h.rating is not None and h.rating >= args.min_rating]
        if args.max_price is not None:
            hotels = [h for h in hotels if h.total_price is None or h.total_price <= args.max_price]

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
