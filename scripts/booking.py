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

Operates via authenticated browser session cookies (BOOKING_SESSION_COOKIE).
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
import urllib.parse
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


def build_booking_hotel_url(
    name: str,
    canonical_url: Optional[str] = None,
    country_code: Optional[str] = None,
    hotel_id: Optional[str] = None,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    guests: int = 2,
    rooms: int = 1,
) -> str:
    """Build a valid Booking.com property URL or deep search link."""
    params: Dict[str, str] = {}
    if check_in and check_out:
        params["checkin"] = check_in
        params["checkout"] = check_out
        params["group_adults"] = str(guests)
        params["no_rooms"] = str(rooms)

    if canonical_url and "booking.com" in canonical_url:
        base = canonical_url.split("?")[0]
    else:
        base = "https://www.booking.com/searchresults.html"
        params["ss"] = name

    if params:
        return f"{base}?{urllib.parse.urlencode(params)}"
    return base


class BookingConfig:
    def __init__(
        self,
        session_cookie: Any = _UNSET,
        **kwargs: Any,
    ):
        if session_cookie == "":
            self.session_cookie = None
        elif session_cookie is not None and session_cookie is not _UNSET:
            self.session_cookie = session_cookie
        else:
            self.session_cookie = self._resolve_session_cookie()

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
    """Search hotels via authenticated Booking.com session cookie."""
    if not config.session_cookie:
        raise ValueError(
            "Booking.com session cookie is not configured.\n"
            "Please set BOOKING_SESSION_COOKIE in .env or run './scripts/login_booking.sh'."
        )

    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.booking.com/",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    cookie_header = config.session_cookie
    if "bkng_sso" not in cookie_header and "=" not in cookie_header:
        cookie_header = f"bkng_sso_session={cookie_header}"
    headers["Cookie"] = cookie_header

    params = {
        "ss": location,
        "checkin": check_in,
        "checkout": check_out,
        "group_adults": str(guests),
        "no_rooms": str(rooms),
        "selected_currency": currency,
    }

    url = "https://www.booking.com/searchresults.html"
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(url, params=params, headers=headers)
        if r.status_code in [202, 403]:
            raise PermissionError(
                f"Booking.com returned status {r.status_code} (session challenge or verification required).\n"
                "Please update your BOOKING_SESSION_COOKIE by copying the latest 'bkng_sso_session' cookie "
                "from your logged-in browser (F12 -> Application -> Cookies -> https://www.booking.com) "
                "and running './scripts/login_booking.sh'."
            )
        r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.select('[data-testid="property-card"]')
    if not cards:
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

        # Clean/build canonical url
        canonical_link = build_booking_hotel_url(
            name=name,
            canonical_url=link,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            rooms=rooms,
        )

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

        # Badges / Genius
        badges = []
        is_genius = False
        card_text = card.get_text()
        if "genius" in card_text.lower():
            badges.append("Genius Deal")
            is_genius = True

        hotels.append(
            Hotel(
                name=name,
                hotel_id="",
                rating=score_val,
                price_text=price_str,
                total_price=price_val,
                currency=currency,
                address=addr,
                url=canonical_link,
                badges=badges,
                is_genius_deal=is_genius,
                provider="Cookie Session (Booking.com)",
                check_in=check_in,
                check_out=check_out,
            )
        )

    if not hotels:
        raise ValueError(
            "No property cards could be parsed from Booking.com response. "
            "Please verify that your session cookie is active and valid."
        )

    return hotels


search_cookie = search_scrape


def apply_genius_discounts(hotels: List[Hotel], genius_level: int) -> None:
    """Apply Genius loyalty program discounts only to verified Genius properties."""
    if genius_level <= 0:
        return

    discount_rate = GENIUS_DISCOUNT_RATES.get(genius_level, 0.20 if genius_level >= 3 else 0.10)
    for h in hotels:
        # Strictly apply only if the property is verified as a Genius partner
        if h.is_genius_deal or "Genius Deal" in h.badges:
            if h.total_price:
                g_price = round(h.total_price * (1.0 - discount_rate), 2)
                h.genius_price = g_price
                h.genius_discount_rate = discount_rate
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
    genius_level: int = DEFAULT_GENIUS_LEVEL,
    config: Optional[BookingConfig] = None,
    **kwargs: Any,
) -> Tuple[List[Hotel], str]:
    """Execute hotel search using authenticated Booking.com session cookie."""
    cfg = config or BookingConfig()

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
    return results, "Cookie Session (Booking.com)"


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
    """Print configuration and connectivity status for Booking.com cookie session."""
    table = Table(
        title="🔍 Booking.com Integration Status",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Setting / Component", style="bold white", width=25)
    table.add_column("Status", width=15)
    table.add_column("Details", style="dim")

    # 1. Session Cookie
    if config.session_cookie:
        masked = (
            config.session_cookie[:15] + "..." + config.session_cookie[-6:]
            if len(config.session_cookie) > 25
            else "***"
        )
        table.add_row(
            "Session Cookie",
            "[green]Configured[/green]",
            f"Active ({len(config.session_cookie)} chars): {masked}",
        )
    else:
        table.add_row(
            "Session Cookie",
            "[yellow]Not Configured[/yellow]",
            "Set BOOKING_SESSION_COOKIE in .env or run ./scripts/login_booking.sh",
        )

    # 2. Genius Loyalty
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

    # 3. Wanderlog CLI
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
        description="Booking.com Hotel Search and Wanderlog Integration CLI (Cookie Session)",
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
        help=f"Genius loyalty discount level (0=none, 1=10%%, 2=15%%, 3=20%%, default: {DEFAULT_GENIUS_LEVEL})",
    )
    search_p.add_argument("--limit", type=int, default=10, help="Max results to display (default: 10)")
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
    search_p.add_argument("--session-cookie", help="Override Booking session cookie")

    # Subcommand: status
    subparsers.add_parser("status", help="Check configured credentials and connectivity status")

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    config = BookingConfig(
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
