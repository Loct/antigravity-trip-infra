#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pytest>=8.0.0",
#     "httpx>=0.27.0",
#     "rich>=13.0.0",
#     "beautifulsoup4>=4.12.0",
# ]
# ///
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts dir is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from agoda import (
    AgodaConfig,
    Hotel,
    add_lodging_to_wanderlog,
    apply_vip_discount,
    build_agoda_hotel_url,
    detect_personal_account_tier,
    print_personal_account_setup_prompt,
    run_status_check,
    search_apify,
    search_hotels,
    search_rapidapi,
)


def test_hotel_dataclass():
    h = Hotel(
        name="Agoda Test Resort",
        hotel_id="54321",
        rating=9.1,
        review_count=320,
        review_word="Exceptional",
        price_text="USD 180.00",
        price_per_night=180.0,
        total_price=720.0,
        currency="USD",
        address="Beach Road, Phuket",
        latitude=7.8804,
        longitude=98.3923,
        url="https://www.agoda.com/hotel/54321.html",
        photo_url="https://example.com/resort.jpg",
        badges=["Free cancellation", "Breakfast included", "5★"],
        provider="RapidAPI (Agoda)",
        check_in="2026-11-01",
        check_out="2026-11-05",
    )
    d = h.to_dict()
    assert d["name"] == "Agoda Test Resort"
    assert d["rating"] == 9.1
    assert d["currency"] == "USD"
    assert "Free cancellation" in d["badges"]
    assert "Breakfast included" in d["badges"]


def test_agoda_config_resolution(monkeypatch):
    monkeypatch.setenv("AGODA_API_KEY", "test-agoda-key")
    monkeypatch.setenv("APIFY_TOKEN", "test-apify-token")
    monkeypatch.setenv("AGODA_SESSION_COOKIE", "agoda_session=xyz")
    monkeypatch.setenv("AGODA_RAPIDAPI_HOST", "agoda-custom.p.rapidapi.com")

    cfg = AgodaConfig()
    assert cfg.api_key == "test-agoda-key"
    assert cfg.apify_token == "test-apify-token"
    assert cfg.session_cookie == "agoda_session=xyz"
    assert cfg.rapidapi_host == "agoda-custom.p.rapidapi.com"
    assert cfg.apify_actor == "tri_angle/agoda-scraper"


def test_search_rapidapi_mocked():
    mock_dest_resp = MagicMock()
    mock_dest_resp.status_code = 200
    mock_dest_resp.json.return_value = {"data": [{"id": "16056", "name": "Tokyo", "dest_id": "16056"}]}

    mock_hotels_resp = MagicMock()
    mock_hotels_resp.status_code = 200
    mock_hotels_resp.raise_for_status = MagicMock()
    mock_hotels_resp.json.return_value = {
        "data": {
            "hotels": [
                {
                    "hotel_id": 999,
                    "property": {
                        "name": "Agoda Tokyo Central Hotel",
                        "id": 999,
                        "rating": 8.9,
                        "review_count": 1500,
                        "review_word": "Excellent",
                        "price": {"value": 380.0, "currency": "USD"},
                        "latitude": 35.6812,
                        "longitude": 139.7671,
                        "address": "Chiyoda-ku, Tokyo",
                        "is_free_cancellable": True,
                        "stars": 4,
                    },
                }
            ]
        }
    }

    cfg = AgodaConfig(api_key="mock-key", rapidapi_host="agoda-com.p.rapidapi.com")

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.side_effect = [mock_dest_resp, mock_hotels_resp]
        mock_client_cls.return_value = mock_client

        results = search_rapidapi(
            location="Tokyo",
            check_in="2026-11-01",
            check_out="2026-11-05",
            guests=2,
            rooms=1,
            currency="USD",
            limit=5,
            config=cfg,
        )

        assert len(results) == 1
        h = results[0]
        assert h.name == "Agoda Tokyo Central Hotel"
        assert h.rating == 8.9
        assert h.total_price == 380.0
        assert "Free cancellation" in h.badges
        assert "4★" in h.badges


def test_search_apify_mocked():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = [
        {
            "id": "777",
            "hotelName": "Bangkok Riverside Sanctuary",
            "rating": 9.3,
            "reviewsCount": 640,
            "ratingText": "Exceptional",
            "price": 250.0,
            "address": "Charoen Nakhon Rd, Bangkok",
            "lat": 13.72,
            "lng": 100.51,
            "hotelUrl": "https://www.agoda.com/hotel/777.html",
            "freeCancellation": True,
            "breakfastIncluded": True,
            "starRating": 5,
        }
    ]

    cfg = AgodaConfig(apify_token="mock-token", apify_actor="tri_angle/agoda-scraper")

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        results = search_apify(
            location="Bangkok",
            check_in="2026-11-01",
            check_out="2026-11-05",
            guests=2,
            rooms=1,
            currency="USD",
            limit=5,
            config=cfg,
        )

        assert len(results) == 1
        h = results[0]
        assert h.name == "Bangkok Riverside Sanctuary"
        assert h.rating == 9.3
        assert h.total_price == 250.0
        assert "Free cancellation" in h.badges
        assert "Breakfast included" in h.badges
        assert "5★" in h.badges


def test_search_hotels_hybrid_fallback():
    cfg = AgodaConfig(api_key="", apify_token="mock-token")
    with patch("agoda.search_apify") as mock_apify:
        mock_apify.return_value = [Hotel(name="Fallback Agoda Hotel", hotel_id="888", rating=8.6)]
        results, provider = search_hotels(
            location="Seoul",
            check_in="2026-11-01",
            check_out="2026-11-05",
            config=cfg,
        )
        assert len(results) == 1
        assert "Apify" in provider


def test_add_lodging_to_wanderlog_cmd():
    hotel = Hotel(
        name="Hotel Gracery Shinjuku",
        hotel_id="555",
        rating=8.8,
        price_text="USD 190.00",
        check_in="2026-11-01",
        check_out="2026-11-05",
        latitude=35.695,
        longitude=139.702,
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")
        success = add_lodging_to_wanderlog(
            hotel=hotel,
            trip_key="test-trip-key",
            interactive=False,
        )
        assert success is True
        args = mock_run.call_args[0][0]
        assert args[0] == "wanderlog"
        assert args[1] == "trips"
        assert args[2] == "lodging"
        assert args[3] == "add"
        assert args[4] == "test-trip-key"
        assert "--name" in args
        assert "Hotel Gracery Shinjuku" in args


def test_status_check():
    cfg = AgodaConfig(api_key="test-key", apify_token=None, session_cookie=None, vip_level=4)
    # Ensure run_status_check executes cleanly
    run_status_check(cfg)


def test_build_agoda_hotel_url():
    # 1. Search link from name and dates
    url1 = build_agoda_hotel_url(
        name="Hotel Gracery Shinjuku",
        check_in="2026-12-01",
        check_out="2026-12-05",
        guests=2,
        rooms=1,
    )
    assert "https://www.agoda.com/search" in url1
    assert "checkIn=2026-12-01" in url1
    assert "checkOut=2026-12-05" in url1
    assert "adults=2" in url1
    assert "rooms=1" in url1
    assert "text=Hotel+Gracery+Shinjuku" in url1

    # 2. Replaces broken placeholder /hotel/<id>.html with valid deeplink
    url2 = build_agoda_hotel_url(
        name="Kyoto Machiya Stay",
        canonical_url="https://www.agoda.com/hotel/12345.html",
        hotel_id="12345",
        check_in="2026-12-01",
        check_out="2026-12-05",
    )
    assert "/hotel/12345.html" not in url2
    assert "https://www.agoda.com/search" in url2
    assert "hotel=12345" in url2

    # 3. Preserves legitimate canonical Agoda property URL
    valid_property_url = "https://www.agoda.com/en-gb/hotel-gracery-shinjuku/hotel/tokyo-jp.html"
    url3 = build_agoda_hotel_url(
        name="Hotel Gracery Shinjuku",
        canonical_url=valid_property_url,
        check_in="2026-12-01",
        check_out="2026-12-05",
    )
    assert "hotel-gracery-shinjuku/hotel/tokyo-jp.html" in url3
    assert "checkIn=2026-12-01" in url3


def test_apply_vip_discount():
    # Platinum: 25% off
    h1 = Hotel(name="Test Stay", hotel_id="1", total_price=400.0, currency="EUR")
    h1_disc = apply_vip_discount(h1, vip_level=4)
    assert h1_disc.is_vip_deal is True
    assert h1_disc.vip_discount_rate == 0.25
    assert h1_disc.vip_price == 300.0
    assert h1_disc.vip_price_text == "EUR 300.00"
    assert "VIP Platinum Deal (-25%)" in h1_disc.badges

    # Silver: 12% off
    h2 = Hotel(name="Test Stay 2", hotel_id="2", total_price=100.0, currency="USD")
    h2_disc = apply_vip_discount(h2, vip_level=2)
    assert h2_disc.is_vip_deal is True
    assert h2_disc.vip_discount_rate == 0.12
    assert h2_disc.vip_price == 88.0
    assert "VIP Silver Deal (-12%)" in h2_disc.badges

    # Level 0: No discount
    h3 = Hotel(name="Test Stay 3", hotel_id="3", total_price=200.0)
    h3_disc = apply_vip_discount(h3, vip_level=0)
    assert h3_disc.is_vip_deal is False
    assert h3_disc.vip_price is None


def test_search_hotels_vip_applied():
    cfg = AgodaConfig(api_key="", apify_token="mock-token", vip_level=4)
    with patch("agoda.search_apify") as mock_apify:
        mock_apify.return_value = [Hotel(name="Luxury Stay", hotel_id="555", total_price=200.0, currency="EUR")]
        results, provider = search_hotels(
            location="Osaka",
            check_in="2026-12-01",
            check_out="2026-12-05",
            config=cfg,
        )
        assert len(results) == 1
        h = results[0]
        assert h.is_vip_deal is True
        assert h.vip_price == 150.0  # 200 - 25%
        assert "VIP Platinum Deal (-25%)" in h.badges


def test_detect_personal_account_tier_from_cookie():
    # Direct numeric VIP tier in cookie
    c1 = "agoda.vip.tier=3; user_email=traveler%40example.com; agoda_session=abc"
    tier, name, user = detect_personal_account_tier(c1)
    assert tier == 3
    assert name == "VIP Gold"
    assert user == "traveler@example.com"

    # Named tier in cookie
    c2 = "vip_status=platinum; email=vip_traveler%40world.org"
    tier2, name2, user2 = detect_personal_account_tier(c2)
    assert tier2 == 4
    assert name2 == "VIP Platinum"
    assert user2 == "vip_traveler@world.org"


def test_detect_personal_account_tier_none():
    assert detect_personal_account_tier(None) == (None, None, None)
    assert detect_personal_account_tier("") == (None, None, None)
    assert detect_personal_account_tier("random_cookie=123") == (None, None, None)


def test_detect_personal_account_tier_api_mock():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "vipStatus": "Silver",
        "email": "silver_member@example.com",
    }

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        tier, name, user = detect_personal_account_tier("agoda.web.auth=token_xyz")
        assert tier == 2
        assert name == "VIP Silver"
        assert user == "silver_member@example.com"


def test_agoda_config_personal_account_auto_detection():
    # Session cookie with VIP Gold
    cfg = AgodaConfig(
        session_cookie="agoda.vip.tier=3; user_email=alex%40test.org",
        personal_account=True,
    )
    assert cfg.personal_account_detected is True
    assert cfg.personal_account_id == "alex@test.org"
    assert cfg.detected_vip_tier == "VIP Gold"
    assert cfg.vip_level == 3
    assert cfg.prompt_personal_account_setup is False


def test_agoda_config_personal_account_prompt_needed():
    # No session cookie when personal_account is requested
    cfg = AgodaConfig(session_cookie="", personal_account=True)
    assert cfg.personal_account_detected is False
    assert cfg.prompt_personal_account_setup is True
    assert cfg.vip_level == 4  # Graceful fallback


def test_print_personal_account_setup_prompt():
    # Ensure it prints cleanly without errors
    print_personal_account_setup_prompt()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
