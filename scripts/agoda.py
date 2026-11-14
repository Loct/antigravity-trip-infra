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
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", os.getenv("AGODA_CURRENCY", "EUR"))
_raw_vip = os.getenv("AGODA_VIP_LEVEL", "auto").strip().lower()
if _raw_vip in ("auto", "personal"):
    DEFAULT_VIP_LEVEL: Any = "auto"
else:
    try:
        DEFAULT_VIP_LEVEL = int(_raw_vip)
    except ValueError:
        DEFAULT_VIP_LEVEL = "auto"

VIP_DISCOUNT_RATES = {
    1: 0.05,  # VIP Bronze: ~5%
    2: 0.12,  # VIP Silver: ~12%
    3: 0.18,  # VIP Gold: ~18%
    4: 0.25,  # VIP Platinum: ~25%
}
VIP_TIER_NAMES = {
    1: "VIP Bronze",
    2: "VIP Silver",
    3: "VIP Gold",
    4: "VIP Platinum",
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
    vip_price: Optional[float] = None
    vip_price_text: Optional[str] = None
    is_vip_deal: bool = False
    vip_discount_rate: float = 0.0
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


def build_agoda_hotel_url(
    name: str,
    canonical_url: Optional[str] = None,
    hotel_id: Optional[str] = None,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    guests: int = 2,
    rooms: int = 1,
) -> str:
    """Build a valid Agoda property URL or deep search link with populated travel dates and guests."""
    params: Dict[str, str] = {}
    if check_in and check_out:
        params["checkIn"] = check_in
        params["checkOut"] = check_out
        params["adults"] = str(guests)
        params["rooms"] = str(rooms)

    # Avoid generating broken placeholder URLs like 'agoda.com/hotel/<id>.html'
    if canonical_url and "agoda.com" in canonical_url and not re.search(r"agoda\.com/hotel/\d+\.html$", canonical_url):
        base = canonical_url.split("?")[0]
    elif hotel_id and str(hotel_id).isdigit():
        base = "https://www.agoda.com/search"
        params["hotel"] = str(hotel_id)
        params["text"] = name
    else:
        base = "https://www.agoda.com/search"
        params["text"] = name

    if params:
        return f"{base}?{urllib.parse.urlencode(params)}"
    return base


def apply_vip_discount(hotel: Hotel, vip_level: int = DEFAULT_VIP_LEVEL) -> Hotel:
    """Apply AgodaVIP loyalty discount to a hotel result if applicable."""
    if vip_level <= 0 or vip_level not in VIP_DISCOUNT_RATES:
        return hotel

    rate = VIP_DISCOUNT_RATES[vip_level]
    vip_tier = VIP_TIER_NAMES.get(vip_level, f"VIP Level {vip_level}")

    if hotel.total_price is not None and not hotel.is_vip_deal:
        discounted = round(hotel.total_price * (1.0 - rate), 2)
        hotel.vip_price = discounted
        hotel.vip_price_text = f"{hotel.currency} {discounted:.2f}"
        hotel.is_vip_deal = True
        hotel.vip_discount_rate = rate
        badge_text = f"{vip_tier} Deal (-{int(rate * 100)}%)"
        if badge_text not in hotel.badges:
            hotel.badges.insert(0, badge_text)
    return hotel


def print_agoda_cookie_feedback(status_type: str, details: Optional[str] = None) -> None:
    """
    Render a high-clarity Rich feedback panel when Agoda session cookie
    is expired, challenged, or unavailable.
    """
    if status_type == "expired":
        title = "⚠️ Agoda Session Cookie Expired — Please Log In Again"
        border_style = "bold red"
        symptom = (
            "🔴 [bold red]SESSION EXPIRED: YOU MUST LOG IN AGAIN TO AGODA[/bold red]\n"
            "Your Agoda personal session cookie has expired or was invalidated by Agoda.\n"
            "You need to log into your account again in your browser to generate a fresh authenticated session."
        )
        action_header = "[bold cyan]⚡ Action Required: Re-authenticate / Log In Again[/bold cyan]"
        step1_title = "Log into your account again in your browser"
        impact = (
            "AgodaVIP member tier (Bronze, Silver, Gold, Platinum - up to 25% off) cannot be auto-detected, "
            "and personal member rates cannot be verified. Searches will fall back to default VIP tiers or public pricing."
        )
    elif status_type == "challenge":
        title = "🛡️ Agoda Security Challenge Triggered — Please Log In Again"
        border_style = "bold yellow"
        symptom = (
            "🛡️ [bold yellow]SECURITY CHALLENGE: PLEASE LOG IN AGAIN IN BROWSER[/bold yellow]\n"
            "Agoda bot protection triggered (HTTP 403 or security verification required)."
        )
        action_header = "[bold cyan]⚡ Action Required: Pass Challenge & Re-authenticate[/bold cyan]"
        step1_title = "Log in again in your browser to complete verification"
        impact = (
            "Direct member queries and searches are blocked until a fresh authenticated browser session is supplied."
        )
    elif status_type == "unavailable":
        title = "❌ Agoda Session Cookie Unset — Please Log In & Configure"
        border_style = "bold yellow"
        symptom = (
            "🟡 [bold yellow]SESSION COOKIE UNSET: PLEASE LOG IN TO AGODA[/bold yellow]\n"
            "No Agoda session cookie ('AGODA_SESSION_COOKIE') is set in your environment or credentials.\n"
            "You must log into Agoda in your browser to retrieve your session cookie and link your personal VIP account."
        )
        action_header = "[bold cyan]⚡ Action Required: Log In to Agoda & Configure Personal Account[/bold cyan]"
        step1_title = "Log into Agoda in your browser"
        impact = "AgodaVIP personal loyalty discounts cannot be verified; searches fall back to default tiers or public rates."
    else:
        title = "⚠️ Agoda Session Verification Alert"
        border_style = "yellow"
        symptom = f"Agoda session status: {status_type}."
        action_header = "[bold cyan]⚡ Action Required:[/bold cyan]"
        step1_title = "Sign into your account in your browser"
        impact = "May affect personal loyalty pricing and auto-detection."

    details_line = f"\n[dim]Details: {details}[/dim]\n" if details else ""

    panel_content = (
        f"[bold]{symptom}[/bold]\n"
        f"{details_line}\n"
        f"[bold]Impact:[/bold] {impact}\n\n"
        f"{action_header}\n"
        f"  1. [bold yellow]{step1_title}:[/bold yellow]\n"
        "     • Open [link=https://www.agoda.com]https://www.agoda.com[/link] in Chrome or Firefox and [bold underline]sign into your account[/bold underline].\n\n"
        "  2. [bold yellow]Save your session cookie (choose one):[/bold yellow]\n"
        "     • Run setup wizard: [bold green]./scripts/login_agoda.sh[/bold green] (Choose [bold]Option 3[/bold]: Personal Account & Session Cookie)\n"
        "     • Or press [bold]F12[/bold] (DevTools) → [bold]Application[/bold] → [bold]Cookies[/bold] → [bold]https://www.agoda.com[/bold],\n"
        "       copy [bold]agoda.web.auth[/bold] (or full Cookie header), and set in [bold].env[/bold]:\n"
        '       [bold cyan]AGODA_SESSION_COOKIE="..."[/bold cyan]\n\n'
        "  3. [bold yellow]Verify your session:[/bold yellow]\n"
        "     [bold green]uv run scripts/agoda.py status[/bold green]"
    )

    err_console.print(
        Panel(
            panel_content,
            title=f"[bold]{title}[/bold]",
            border_style=border_style,
            expand=False,
        )
    )


def parse_agoda_jwt(token_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """Attempt to decode JWT token payload from Agoda cookie string."""
    if not token_str or not str(token_str).strip():
        return None
    m = re.search(
        r"(?:agoda\.web\.auth=)?(eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)", str(token_str).strip()
    )
    if not m:
        return None
    jwt_token = m.group(1)
    parts = jwt_token.split(".")
    if len(parts) != 3:
        return None
    try:
        import base64

        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")))
    except Exception:
        return None


def verify_agoda_session(
    session_cookie: Optional[str],
    timeout: float = 5.0,
    client: Optional[httpx.Client] = None,
) -> Tuple[bool, str, str, Dict[str, Any]]:
    """
    Live verification of Agoda session cookie validity.
    Returns: (is_valid: bool, status_type: str, details: str, member_info: Dict[str, Any])
    status_type in {"valid", "expired", "challenge", "unavailable", "network_error"}
    """
    if not session_cookie or not session_cookie.strip():
        return False, "unavailable", "Agoda session cookie is not configured", {}

    # Check embedded JWT validity if present
    jwt_data = parse_agoda_jwt(session_cookie)
    if jwt_data and "exp" in jwt_data:
        exp_ts = jwt_data.get("exp")
        if isinstance(exp_ts, (int, float)):
            now_ts = time.time()
            from datetime import datetime, timezone

            if exp_ts < now_ts:
                dt_str = datetime.fromtimestamp(exp_ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                return False, "expired", f"Agoda session token expired on {dt_str} (please log in again)", jwt_data
            else:
                dt_str = datetime.fromtimestamp(exp_ts, timezone.utc).strftime("%Y-%m-%d")
                member_id = jwt_data.get("m") or jwt_data.get("sub")
                acct_label = f"Member #{member_id}" if member_id else "Personal Account"
                return (
                    True,
                    "valid",
                    f"Agoda session token is active and authenticated ({acct_label}, valid until {dt_str})",
                    jwt_data,
                )

    cookie_val = session_cookie.strip()
    if "=" not in cookie_val:
        cookie_header = f"agoda.web.auth={cookie_val}"
    else:
        cookie_header = cookie_val

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
        "Cookie": cookie_header,
        "Referer": "https://www.agoda.com/",
    }

    def _eval(c: httpx.Client) -> Tuple[bool, str, str, Dict[str, Any]]:
        # 1. Profile API endpoint (used in mocks & modern Agoda API)
        api_url = "https://www.agoda.com/api/cronos/members/profile"
        try:
            r_api = c.get(api_url, headers=headers)
            if r_api.status_code == 200:
                try:
                    data = r_api.json()
                    if isinstance(data, dict):
                        if data.get("code") == 401 or data.get("isLoggedIn") is False:
                            return False, "expired", "Agoda profile API reported unauthenticated session", data
                        raw_tier = (
                            data.get("vipStatus") or data.get("vipTier") or data.get("loyaltyTier") or data.get("tier")
                        )
                        raw_user = (
                            data.get("email") or data.get("userName") or data.get("memberName") or data.get("firstName")
                        )
                        if raw_tier or raw_user or data.get("memberId") or data.get("userId"):
                            return True, "valid", "Agoda session is active and authenticated", data
                except Exception:
                    pass
            elif r_api.status_code == 401:
                return False, "expired", "Agoda profile API returned HTTP 401 Unauthorized", {}
            elif r_api.status_code == 403:
                return False, "challenge", "Agoda bot protection triggered (HTTP 403)", {}
        except Exception:
            pass

        # 2. Check web profile redirect
        web_url = "https://www.agoda.com/account/profile.html"
        r_web = c.get(web_url, headers=headers, follow_redirects=True)
        if r_web.status_code in (202, 403):
            return False, "challenge", "Agoda bot protection or challenge required (HTTP 403)", {}
        if r_web.status_code == 401:
            return False, "expired", "Agoda account returned HTTP 401 Unauthorized", {}
        final_url = str(r_web.url).lower()
        if "signin" in final_url or "login" in final_url:
            return (
                False,
                "expired",
                "Agoda session cookie expired (redirected to signin.html; please log in again at https://www.agoda.com)",
                {},
            )
        if r_web.status_code == 200:
            if "signin" in r_web.text[:2000].lower() and "password" in r_web.text[:2000].lower():
                return (
                    False,
                    "expired",
                    "Agoda login prompt detected on profile page (please log in again at https://www.agoda.com)",
                    {},
                )
            return True, "valid", "Agoda session cookie is active and authenticated", {}

        return False, "network_error", f"Agoda returned unexpected HTTP {r_web.status_code}", {}

    try:
        if client is not None:
            return _eval(client)
        with httpx.Client(timeout=timeout, follow_redirects=True) as local_client:
            return _eval(local_client)
    except httpx.RequestError as e:
        return False, "network_error", f"Network error during Agoda session check: {e}", {}
    except Exception as e:
        return False, "network_error", f"Agoda session check failed: {e}", {}


def detect_personal_account_tier(
    session_cookie: Optional[str],
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Detect AgodaVIP tier and account details from personal session cookie.
    Returns: (vip_level [1..4], tier_name, account_identifier)
    """
    if not session_cookie or not session_cookie.strip():
        return None, None, None

    cookie_str = session_cookie.strip()
    tier_level = None
    account_id = None

    # 1. JWT inspection
    jwt_data = parse_agoda_jwt(cookie_str)
    if jwt_data:
        member_id = jwt_data.get("m") or jwt_data.get("sub")
        if member_id:
            account_id = f"Member #{member_id}"
        for k in ["vipStatus", "vipTier", "vip_level", "loyaltyTier", "tier", "vip"]:
            if k in jwt_data:
                val = jwt_data[k]
                if str(val).isdigit() and int(val) in VIP_DISCOUNT_RATES:
                    tier_level = int(val)
                elif str(val).lower() in ("platinum", "gold", "silver", "bronze"):
                    name_map = {"bronze": 1, "silver": 2, "gold": 3, "platinum": 4}
                    tier_level = name_map.get(str(val).lower())

    # 2. Regex inspection of cookie string
    if tier_level is None:
        m_level = re.search(r"(?:agoda\.vip\.tier|agoda_vip_level|vip_level|user_tier)=(\d)", cookie_str, re.IGNORECASE)
        if m_level:
            try:
                val = int(m_level.group(1))
                if val in VIP_DISCOUNT_RATES:
                    tier_level = val
            except ValueError:
                pass

    if tier_level is None:
        m_named = re.search(
            r"(?:vip_tier|vip_status|agoda_vip|tier)=(platinum|gold|silver|bronze)", cookie_str, re.IGNORECASE
        )
        if m_named:
            name_map = {"bronze": 1, "silver": 2, "gold": 3, "platinum": 4}
            tier_level = name_map.get(m_named.group(1).lower())

    m_user = re.search(r"(?:user_email|email|user_name|member_name)=([^;]+)", cookie_str, re.IGNORECASE)
    if m_user:
        account_id = urllib.parse.unquote(m_user.group(1).strip())

    # 2. Query Agoda member profile endpoint if auth token is present
    auth_indicators = ["agoda.web.auth", "agoda_session", "agoda_token", "auth_token", "session_id"]
    if (any(ind in cookie_str.lower() for ind in auth_indicators) or tier_level is None) and tier_level is None:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Cookie": cookie_str,
            "Referer": "https://www.agoda.com/",
        }
        for endpoint in [
            "https://www.agoda.com/api/cronos/members/profile",
            "https://www.agoda.com/api/v4/user/profile",
        ]:
            try:
                with httpx.Client(timeout=4.0, headers=headers, follow_redirects=True) as client:
                    r = client.get(endpoint)
                    if r.status_code == 200:
                        data = r.json()
                        if isinstance(data, dict):
                            raw_tier = (
                                data.get("vipStatus")
                                or data.get("vipTier")
                                or data.get("loyaltyTier")
                                or data.get("tier")
                            )
                            if raw_tier:
                                if str(raw_tier).isdigit() and int(raw_tier) in VIP_DISCOUNT_RATES:
                                    tier_level = int(raw_tier)
                                else:
                                    name_map = {"bronze": 1, "silver": 2, "gold": 3, "platinum": 4}
                                    tier_level = name_map.get(str(raw_tier).strip().lower())

                            raw_user = (
                                data.get("email")
                                or data.get("userName")
                                or data.get("memberName")
                                or data.get("firstName")
                            )
                            if raw_user:
                                account_id = str(raw_user).strip()
                            if tier_level:
                                break
            except Exception:
                pass

    tier_name = VIP_TIER_NAMES.get(tier_level) if tier_level else None
    return tier_level, tier_name, account_id


def print_personal_account_setup_prompt() -> None:
    """Display instructions when a personal Agoda account needs to be set up."""
    console.print(
        Panel(
            "[bold yellow]Personal Agoda Account Setup Needed[/bold yellow]\n\n"
            "To auto-detect your AgodaVIP tier (Bronze, Silver, Gold, or Platinum) and access personal loyalty rates:\n\n"
            "  1. Run the interactive Agoda setup wizard:\n"
            "     [bold cyan]./scripts/login_agoda.sh[/bold cyan] (Choose [bold]Option 3[/bold]: Personal Account & Session Cookie)\n\n"
            "  2. Follow the extraction steps:\n"
            "     • Open [link=https://www.agoda.com]https://www.agoda.com[/link] in your browser and sign in.\n"
            "     • Press [bold]F12[/bold] (DevTools) → [bold]Application / Storage[/bold] → [bold]Cookies[/bold] → [bold]https://www.agoda.com[/bold].\n"
            "     • Copy the cookie string and paste it into the wizard (or save to [bold].env[/bold] as [bold]AGODA_SESSION_COOKIE[/bold]).\n\n"
            "  3. Alternatively, you can set your VIP tier manually in [bold].env[/bold]:\n"
            "     [bold cyan]AGODA_VIP_LEVEL=4[/bold cyan] (1=Bronze 5%, 2=Silver 12%, 3=Gold 18%, 4=Platinum 25%)\n\n"
            "[dim]Note: Continuing search with default VIP tier / public pricing.[/dim]",
            title="💡 Link Personal Agoda Account for Auto-VIP Tier",
            border_style="yellow",
        )
    )


class AgodaConfig:
    def __init__(
        self,
        api_key: Any = _UNSET,
        rapidapi_host: Optional[str] = None,
        apify_token: Any = _UNSET,
        apify_actor: Optional[str] = None,
        session_cookie: Any = _UNSET,
        vip_level: Any = _UNSET,
        personal_account: bool = False,
    ):
        if api_key == "":
            self.api_key = None
        elif api_key is not None and api_key is not _UNSET:
            self.api_key = api_key
        else:
            self.api_key = self._resolve_api_key()

        self.rapidapi_host = (
            rapidapi_host
            or (os.getenv("AGODA_RAPIDAPI_HOST") or "").strip()
            or (os.getenv("RAPIDAPI_HOST") or "").strip()
            or "agoda-com.p.rapidapi.com"
        )

        if apify_token == "":
            self.apify_token = None
        elif apify_token is not None and apify_token is not _UNSET:
            self.apify_token = apify_token
        else:
            self.apify_token = self._resolve_apify_token()

        self.apify_actor = apify_actor or self._resolve_apify_actor()

        if session_cookie == "":
            self.session_cookie = None
        elif session_cookie is not None and session_cookie is not _UNSET:
            self.session_cookie = session_cookie
        else:
            self.session_cookie = self._resolve_session_cookie()

        # Resolve VIP level & Personal Account Auto-Detection
        resolved_vip = vip_level if vip_level is not _UNSET else DEFAULT_VIP_LEVEL
        auto_vip = (
            personal_account
            or str(resolved_vip).lower() in ("auto", "personal")
            or os.getenv("AGODA_AUTO_DETECT_VIP", "").lower() in ("1", "true", "yes")
        )

        self.personal_account_detected = False
        self.personal_account_id: Optional[str] = None
        self.detected_vip_tier: Optional[str] = None
        self.prompt_personal_account_setup = False

        if auto_vip:
            detected_tier, detected_name, account_id = detect_personal_account_tier(self.session_cookie)
            if detected_tier is not None:
                self.vip_level = detected_tier
                self.personal_account_detected = True
                self.personal_account_id = account_id
                self.detected_vip_tier = detected_name
            else:
                self.prompt_personal_account_setup = True
                if personal_account and not self.session_cookie:
                    self.vip_level = 4
                elif resolved_vip is not None and str(resolved_vip).isdigit():
                    self.vip_level = int(resolved_vip)
                else:
                    self.vip_level = 0
        else:
            try:
                self.vip_level = int(resolved_vip)
            except (ValueError, TypeError):
                self.vip_level = 4

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
                    if (
                        k
                        in [
                            "AGODA_API_KEY",
                            "RAPIDAPI_KEY",
                            "AGODA_COM_ACCESS_TOKEN",
                        ]
                        and v
                    ):
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

    def _resolve_apify_actor(self) -> str:
        # Check explicit env var (ignoring deprecated tri_angle/agoda-scraper)
        val = os.getenv("APIFY_AGODA_ACTOR")
        if val and val.strip() and val.strip() != "tri_angle/agoda-scraper":
            return val.strip()

        # Check .env in workspace
        env_path = Path("/workspace/.env")
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    if k.strip() == "APIFY_AGODA_ACTOR" and v.strip().strip("'\""):
                        val_env = v.strip().strip("'\"")
                        if val_env != "tri_angle/agoda-scraper":
                            return val_env
            except Exception:
                pass

        cfg_path = Path.home() / ".config" / "apify" / "credentials.json"
        if cfg_path.is_file():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                val = data.get("agoda_actor") or data.get("actor")
                if val and str(val).strip() and str(val).strip() != "tri_angle/agoda-scraper":
                    return str(val).strip()
            except Exception:
                pass

        return "clearpath/agoda-hotel-scraper"

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
            hotel_id = str(prop.get("hotel_id") or prop.get("hotelId") or prop.get("id") or item.get("hotel_id", ""))
            rating = prop.get("rating") or prop.get("review_score") or prop.get("reviewScore") or prop.get("score")
            review_count = (
                prop.get("review_count") or prop.get("review_nr") or prop.get("reviewsCount") or prop.get("reviewCount")
            )
            review_word = prop.get("review_word") or prop.get("review_score_word") or prop.get("ratingText")

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
            url = build_agoda_hotel_url(
                name=name,
                canonical_url=prop.get("url") or prop.get("hotelUrl"),
                hotel_id=hotel_id,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                rooms=rooms,
            )
            photo = prop.get("photo_url") or prop.get("image") or prop.get("photoUrl") or prop.get("main_photo_url")
            address = prop.get("address") or prop.get("neighborhood") or prop.get("city") or location

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
        "city": location,
        "checkIn": check_in,
        "checkInDate": check_in,
        "checkOut": check_out,
        "checkOutDate": check_out,
        "adults": guests,
        "rooms": rooms,
        "currency": currency,
        "maxItems": limit,
    }

    items: List[Dict[str, Any]] = []
    with httpx.Client(timeout=30.0) as client:
        # Start run and poll dataset to stream items rapidly without waiting for whole crawler run
        run_url = f"https://api.apify.com/v2/acts/{actor_id}/runs"
        try:
            r_run = client.post(run_url, params=params, json=payload, timeout=15.0)
            if r_run.status_code == 201:
                run_data = r_run.json().get("data", {})
                run_id = run_data.get("id")
                dataset_id = run_data.get("defaultDatasetId")
                if dataset_id and run_id:
                    for _ in range(12):
                        time.sleep(2)
                        items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
                        r_items = client.get(items_url, params={"token": config.apify_token, "limit": limit})
                        if r_items.status_code == 200:
                            data = r_items.json()
                            if isinstance(data, list) and len(data) >= limit:
                                items = data
                                break
                            elif isinstance(data, list) and data:
                                items = data
                    try:
                        abort_url = f"https://api.apify.com/v2/actor-runs/{run_id}/abort"
                        client.post(abort_url, params=params, json={}, timeout=5.0)
                    except Exception:
                        pass
        except Exception:
            pass

    # Fallback to run-sync if stream didn't yield items
    if not items:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(url, params=params, json=payload)
            r.raise_for_status()
            res = r.json()
            if isinstance(res, list):
                items = res

    if not isinstance(items, list):
        items = []

    hotels: List[Hotel] = []
    for item in items[:limit]:
        name = item.get("hotelName") or item.get("name") or item.get("title") or "Unknown Hotel"
        hotel_id = str(item.get("hotelId") or item.get("id") or "")
        rating = item.get("rating") or item.get("score") or item.get("reviewScore")
        review_count = item.get("reviewsCount") or item.get("reviewCount")
        review_word = item.get("ratingText") or item.get("reviewScoreWord") or item.get("reviewScoreText")

        price = (
            item.get("price")
            or item.get("dailyRate")
            or item.get("pricePerNight")
            or item.get("pricePerNightWithTaxes")
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

        address = item.get("address") or item.get("neighborhood") or item.get("city") or location
        lat = item.get("lat") or item.get("latitude")
        lng = item.get("lng") or item.get("longitude")
        url_link = build_agoda_hotel_url(
            name=name,
            canonical_url=item.get("hotelUrl") or item.get("url") or item.get("link"),
            hotel_id=hotel_id,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            rooms=rooms,
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
                    url = build_agoda_hotel_url(
                        name=name,
                        canonical_url=prop.get("propertyUrl"),
                        hotel_id=hotel_id,
                        check_in=check_in,
                        check_out=check_out,
                        guests=guests,
                        rooms=rooms,
                    )

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
            raw_href = f"https://www.agoda.com{link_el['href']}" if link_el else None
            link = build_agoda_hotel_url(
                name=name,
                canonical_url=raw_href,
                hotel_id="",
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                rooms=rooms,
            )

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
    currency: str = DEFAULT_CURRENCY,
    limit: int = 10,
    provider: str = "auto",
    vip_level: Any = None,
    personal_account: bool = False,
    config: Optional[AgodaConfig] = None,
) -> Tuple[List[Hotel], str]:
    """Search hotels across Agoda providers with hybrid fallback and AgodaVIP discounting."""
    if config is None:
        config = AgodaConfig(
            vip_level=vip_level if vip_level is not None else DEFAULT_VIP_LEVEL,
            personal_account=personal_account,
        )
    elif personal_account:
        config = AgodaConfig(
            api_key=config.api_key,
            rapidapi_host=config.rapidapi_host,
            apify_token=config.apify_token,
            apify_actor=config.apify_actor,
            session_cookie=config.session_cookie,
            vip_level=vip_level if vip_level is not None else "auto",
            personal_account=True,
        )
    elif vip_level is not None:
        try:
            config.vip_level = int(vip_level)
        except (ValueError, TypeError):
            config.vip_level = 4

    effective_vip = config.vip_level

    def _finalize(items: List[Hotel], p_name: str) -> Tuple[List[Hotel], str]:
        if effective_vip > 0:
            items = [apply_vip_discount(h, effective_vip) for h in items]
        return items, p_name

    provider = provider.lower()
    errors: List[str] = []

    # Direct provider routing
    if provider == "rapidapi":
        return _finalize(
            search_rapidapi(location, check_in, check_out, guests, rooms, currency, limit, config),
            "RapidAPI (Agoda)",
        )

    if provider == "apify":
        return _finalize(
            search_apify(location, check_in, check_out, guests, rooms, currency, limit, config),
            f"Apify ({config.apify_actor})",
        )

    if provider == "scrape":
        return _finalize(
            search_scrape(location, check_in, check_out, guests, rooms, currency, limit, config),
            "Agoda Web",
        )

    # Auto mode: RapidAPI -> Apify -> Scrape
    if config.api_key:
        try:
            results = search_rapidapi(location, check_in, check_out, guests, rooms, currency, limit, config)
            if results:
                return _finalize(results, "RapidAPI (Agoda)")
        except Exception as e:
            errors.append(f"RapidAPI: {e}")

    if config.apify_token:
        try:
            results = search_apify(location, check_in, check_out, guests, rooms, currency, limit, config)
            if results:
                return _finalize(results, f"Apify ({config.apify_actor})")
        except Exception as e:
            errors.append(f"Apify: {e}")

    # Fallback to direct web scrape
    try:
        results = search_scrape(location, check_in, check_out, guests, rooms, currency, limit, config)
        if results:
            return _finalize(results, "Agoda Web Fallback")
    except Exception as e:
        errors.append(f"Direct Web: {e}")

    if errors:
        msg = "; ".join(errors)
        raise RuntimeError(
            f"All Agoda providers failed for location '{location}'. Details: {msg}\n"
            "Tip: Run './scripts/login_agoda.sh' to configure AGODA_API_KEY, APIFY_TOKEN, or AGODA_SESSION_COOKIE."
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
    table.add_column("Total Price", justify="right", style="bold green", width=16)
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

        # Price string with VIP deal highlight
        if h.is_vip_deal and h.vip_price_text:
            orig = h.price_text or (f"{h.currency} {h.total_price:.2f}" if h.total_price else "")
            orig_str = f"\n[dim strike]{orig}[/dim strike]" if orig else ""
            price_display = f"[bold green]{h.vip_price_text}[/bold green]{orig_str}"
        else:
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
        url_display = h.url or build_agoda_hotel_url(
            name=h.name,
            hotel_id=h.hotel_id,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
        )

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
    price_note = hotel.vip_price_text or hotel.price_text or "N/A"
    if hotel.is_vip_deal and hotel.vip_price_text and hotel.price_text:
        price_note = f"{hotel.vip_price_text} (AgodaVIP deal, standard: {hotel.price_text})"

    booking_notes = (
        f"Booked via Agoda.\n"
        f"Rating: {hotel.rating}/10 ({hotel.review_word or ''})\n"
        f"Price: {price_note}\n"
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
                f"• Price:      {price_note}\n"
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
        console.print(f"[bold green]✅ Successfully added '{hotel.name}' to Wanderlog trip {trip_key}![/bold green]")
        if res.stdout.strip():
            console.print(f"[dim]{res.stdout.strip()}[/dim]")
        return True
    else:
        err_console.print(f"[bold red]❌ Failed to add lodging to Wanderlog:[/bold red]\n{res.stderr.strip()}")
        return False


def run_status_check(config: AgodaConfig, live_verify: bool = True) -> None:
    """Print configuration and connectivity status for all Agoda providers."""
    table = Table(
        title="🔍 Agoda Integration Status",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Provider / Setting", style="bold white", width=25)
    table.add_column("Status", width=22)
    table.add_column("Details", style="dim")

    cookie_feedback_type: Optional[str] = None
    cookie_feedback_details: Optional[str] = None

    # 1. RapidAPI
    if config.api_key:
        table.add_row(
            "RapidAPI / Agoda Key",
            "[green]Configured[/green]",
            f"Key: {'*' * 8} ({len(config.api_key)} chars) | Host: {config.rapidapi_host}",
        )
    else:
        table.add_row(
            "RapidAPI / Agoda Key",
            "[yellow]Not Configured[/yellow]",
            "Set AGODA_API_KEY in .env or run ./scripts/login_agoda.sh",
        )

    # 2. Apify
    if config.apify_token:
        table.add_row(
            "Apify Token",
            "[green]Configured[/green]",
            f"Token: {'*' * 8} ({len(config.apify_token)} chars) | Actor: {config.apify_actor}",
        )
    else:
        table.add_row(
            "Apify Token",
            "[yellow]Not Configured[/yellow]",
            "Set APIFY_TOKEN in .env or run ./scripts/login_agoda.sh",
        )

    # 3. Session Cookie
    if config.session_cookie:
        acct_label = f" | User: {config.personal_account_id}" if config.personal_account_id else ""
        if live_verify:
            is_valid, reason, msg, _ = verify_agoda_session(config.session_cookie)
            if is_valid:
                table.add_row(
                    "Session Cookie",
                    "[bold green]Active & Valid[/bold green]",
                    f"Verified ({len(config.session_cookie)} chars): AGODA_SESSION_COOKIE{acct_label}",
                )
            elif reason == "expired":
                table.add_row(
                    "Session Cookie",
                    "[bold red]Expired (Re-login Required)[/bold red]",
                    f"Session expired: {msg}",
                )
                cookie_feedback_type = "expired"
                cookie_feedback_details = msg
            elif reason == "challenge":
                table.add_row(
                    "Session Cookie",
                    "[bold yellow]Challenge Required[/bold yellow]",
                    f"Bot check: {msg}",
                )
                cookie_feedback_type = "challenge"
                cookie_feedback_details = msg
            else:
                table.add_row(
                    "Session Cookie",
                    "[green]Configured[/green]",
                    f"Active: {len(config.session_cookie)} chars (AGODA_SESSION_COOKIE){acct_label}",
                )
        else:
            table.add_row(
                "Session Cookie",
                "[green]Configured[/green]",
                f"Active: {len(config.session_cookie)} chars (AGODA_SESSION_COOKIE){acct_label}",
            )
    else:
        table.add_row(
            "Session Cookie",
            "[bold yellow]Unset / Not Configured[/bold yellow]",
            "Session cookie is unset: log into Agoda and run ./scripts/login_agoda.sh (Option 3) to auto-detect VIP tier",
        )
        if config.prompt_personal_account_setup:
            cookie_feedback_type = "unavailable"

    # 4. AgodaVIP Loyalty & Personal Account
    if config.personal_account_detected:
        pct = int(VIP_DISCOUNT_RATES.get(config.vip_level, 0.25) * 100)
        table.add_row(
            "AgodaVIP Loyalty",
            f"[green]{config.detected_vip_tier}[/green]",
            f"Auto-detected from personal account ({config.personal_account_id or 'Member'}): -{pct}% VIP discount",
        )
    elif config.prompt_personal_account_setup:
        table.add_row(
            "AgodaVIP Loyalty",
            "[yellow]Personal Account Needed[/yellow]",
            "Run './scripts/login_agoda.sh' (Option 3) to link account and auto-detect VIP tier (Fallback: Level 4 Platinum)",
        )
    elif config.vip_level > 0 and config.vip_level in VIP_DISCOUNT_RATES:
        tier_name = VIP_TIER_NAMES.get(config.vip_level, f"VIP Level {config.vip_level}")
        pct = int(VIP_DISCOUNT_RATES[config.vip_level] * 100)
        table.add_row(
            "AgodaVIP Loyalty",
            f"[green]{tier_name}[/green]",
            f"Active: -{pct}% discount applied to searches (AGODA_VIP_LEVEL={config.vip_level})",
        )
    else:
        table.add_row(
            "AgodaVIP Loyalty",
            "[yellow]Standard[/yellow]",
            "Level 0 (No VIP discount). Set AGODA_VIP_LEVEL=1..4 in .env or run with --personal-account",
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

    if cookie_feedback_type:
        print_agoda_cookie_feedback(cookie_feedback_type, cookie_feedback_details)
    elif config.prompt_personal_account_setup:
        print_personal_account_setup_prompt()


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
    search_p.add_argument(
        "-g",
        "--guests",
        type=int,
        default=2,
        help="Number of adults/guests (default: 2)",
    )
    search_p.add_argument("-r", "--rooms", type=int, default=1, help="Number of rooms (default: 1)")
    search_p.add_argument(
        "-c",
        "--currency",
        default=DEFAULT_CURRENCY,
        help=f"Currency code (default: {DEFAULT_CURRENCY})",
    )
    search_p.add_argument(
        "--vip",
        default=str(DEFAULT_VIP_LEVEL),
        help="AgodaVIP loyalty discount level: 0=none, 1=VIP Bronze 5%%, 2=VIP Silver 12%%, 3=VIP Gold 18%%, 4=VIP Platinum 25%%, auto=auto-detect from personal account (default: %(default)s)",
    )
    search_p.add_argument(
        "--personal-account",
        action="store_true",
        help="Use personal account session cookie to auto-detect AgodaVIP loyalty tier",
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
    status_p = subparsers.add_parser("status", help="Check configured credentials and connectivity status")
    status_p.add_argument("--no-verify", action="store_true", help="Skip live endpoint validation")
    status_p.add_argument(
        "--personal-account",
        action="store_true",
        help="Check personal account loyalty status & auto-detection",
    )
    status_p.add_argument("--session-cookie", help="Override Agoda session cookie")

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    config = AgodaConfig(
        api_key=getattr(args, "api_key", None),
        apify_token=getattr(args, "apify_token", None),
        session_cookie=getattr(args, "session_cookie", None),
        vip_level=getattr(args, "vip", DEFAULT_VIP_LEVEL),
        personal_account=getattr(args, "personal_account", False),
    )

    if args.subcommand == "status":
        run_status_check(config, live_verify=not getattr(args, "no_verify", False))
        sys.exit(0)

    if args.subcommand == "search":
        if config.prompt_personal_account_setup:
            print_personal_account_setup_prompt()
        elif config.personal_account_detected:
            pct = int(VIP_DISCOUNT_RATES.get(config.vip_level, 0.25) * 100)
            console.print(
                f"[bold green]👤 Personal Account Connected:[/bold green] {config.personal_account_id or 'Agoda Member'} "
                f"({config.detected_vip_tier} Deal -{pct}% auto-applied)\n"
            )

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
