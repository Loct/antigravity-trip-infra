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
import datetime
import io
import json
import os
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
    main,
    print_pretty_table,
    run_status_check,
    search_apify,
    search_hotels,
    search_rapidapi,
    search_scrape,
)


# =====================================================================
# 1. Dataclass & Serialization Tests
# =====================================================================

def test_hotel_dataclass_and_serialization():
    """Verify Hotel dataclass initialization, attributes, and dict conversion."""
    h = Hotel(
        name="Agoda Grand Tokyo",
        hotel_id="12345",
        rating=9.2,
        review_count=1250,
        review_word="Exceptional",
        price_text="USD 210.00",
        price_per_night=210.0,
        total_price=840.0,
        currency="USD",
        address="1-1 Marunouchi, Chiyoda-ku, Tokyo",
        latitude=35.6812,
        longitude=139.7671,
        url="https://www.agoda.com/hotel/12345.html",
        photo_url="https://example.com/photo.jpg",
        badges=["Free cancellation", "Breakfast included", "5★"],
        provider="RapidAPI (Agoda)",
        check_in="2026-11-01",
        check_out="2026-11-05",
    )
    d = h.to_dict()
    assert d["name"] == "Agoda Grand Tokyo"
    assert d["hotel_id"] == "12345"
    assert d["rating"] == 9.2
    assert d["review_count"] == 1250
    assert d["review_word"] == "Exceptional"
    assert d["price_per_night"] == 210.0
    assert d["total_price"] == 840.0
    assert d["currency"] == "USD"
    assert d["address"] == "1-1 Marunouchi, Chiyoda-ku, Tokyo"
    assert d["latitude"] == 35.6812
    assert d["longitude"] == 139.7671
    assert "Free cancellation" in d["badges"]
    assert "Breakfast included" in d["badges"]
    assert "5★" in d["badges"]


# =====================================================================
# 2. Configuration Resolution Tests
# =====================================================================

def test_agoda_config_resolution_from_env(monkeypatch):
    """Verify AgodaConfig correctly resolves from environment variables."""
    monkeypatch.setenv("AGODA_API_KEY", "env-api-key-123")
    monkeypatch.setenv("APIFY_TOKEN", "env-apify-token-456")
    monkeypatch.setenv("AGODA_SESSION_COOKIE", "session_token=xyz789")
    monkeypatch.setenv("AGODA_RAPIDAPI_HOST", "custom-agoda.p.rapidapi.com")
    monkeypatch.setenv("APIFY_AGODA_ACTOR", "custom/agoda-actor")

    cfg = AgodaConfig()
    assert cfg.api_key == "env-api-key-123"
    assert cfg.apify_token == "env-apify-token-456"
    assert cfg.session_cookie == "session_token=xyz789"
    assert cfg.rapidapi_host == "custom-agoda.p.rapidapi.com"
    assert cfg.apify_actor == "custom/agoda-actor"


def test_agoda_config_resolution_fallback_to_rapidapi_key(monkeypatch):
    """Verify fallback to RAPIDAPI_KEY if AGODA_API_KEY is not set."""
    monkeypatch.delenv("AGODA_API_KEY", raising=False)
    monkeypatch.setenv("RAPIDAPI_KEY", "fallback-rapidapi-key")

    cfg = AgodaConfig()
    assert cfg.api_key == "fallback-rapidapi-key"
    assert cfg.rapidapi_host == "agoda-com.p.rapidapi.com"
    assert cfg.apify_actor == "tri_angle/agoda-scraper"


def test_agoda_config_resolution_from_config_files(monkeypatch, tmp_path):
    """Verify AgodaConfig reads JSON config files from ~/.config/agoda."""
    monkeypatch.delenv("AGODA_API_KEY", raising=False)
    monkeypatch.delenv("RAPIDAPI_KEY", raising=False)
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    monkeypatch.delenv("AGODA_SESSION_COOKIE", raising=False)

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    agoda_cfg_dir = fake_home / ".config" / "agoda"
    agoda_cfg_dir.mkdir(parents=True)
    (agoda_cfg_dir / "api_config.json").write_text(
        json.dumps({"api_key": "file-api-key", "rapidapi_host": "file-host.rapidapi.com"})
    )
    (agoda_cfg_dir / "credentials.json").write_text(
        json.dumps({"session_cookie": "file-cookie-val"})
    )

    apify_cfg_dir = fake_home / ".config" / "apify"
    apify_cfg_dir.mkdir(parents=True)
    (apify_cfg_dir / "credentials.json").write_text(
        json.dumps({"token": "file-apify-token"})
    )

    cfg = AgodaConfig()
    assert cfg.api_key == "file-api-key"
    assert cfg.rapidapi_host == "file-host.rapidapi.com"
    assert cfg.session_cookie == "file-cookie-val"
    assert cfg.apify_token == "file-apify-token"


# =====================================================================
# 3. Provider Search & Response Parsing Tests (Mocked)
# =====================================================================

def test_search_rapidapi_mocked():
    """Verify RapidAPI response parsing with autocomplete destination resolution."""
    mock_dest_resp = MagicMock()
    mock_dest_resp.status_code = 200
    mock_dest_resp.json.return_value = {
        "data": [{"id": "16056", "name": "Tokyo", "dest_id": "16056"}]
    }

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
        assert h.hotel_id == "999"
        assert h.rating == 8.9
        assert h.review_count == 1500
        assert h.review_word == "Excellent"
        assert h.total_price == 380.0
        assert h.price_text == "USD 380.00"
        assert "Free cancellation" in h.badges
        assert "4★" in h.badges
        assert h.provider == "RapidAPI (Agoda)"


def test_search_rapidapi_missing_key_raises():
    """Verify search_rapidapi raises ValueError when API key is missing."""
    cfg = AgodaConfig(api_key=None)
    with pytest.raises(ValueError, match="RapidAPI key is not configured"):
        search_rapidapi(
            location="Tokyo",
            check_in="2026-11-01",
            check_out="2026-11-05",
            guests=2,
            rooms=1,
            currency="USD",
            limit=5,
            config=cfg,
        )


def test_search_apify_mocked():
    """Verify Apify actor sync dataset extraction and field mapping."""
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
        assert h.hotel_id == "777"
        assert h.rating == 9.3
        assert h.total_price == 250.0
        assert "Free cancellation" in h.badges
        assert "Breakfast included" in h.badges
        assert "5★" in h.badges
        assert h.provider == "Apify (tri_angle/agoda-scraper)"


def test_search_apify_missing_token_raises():
    """Verify search_apify raises ValueError when token is missing."""
    cfg = AgodaConfig(apify_token=None)
    with pytest.raises(ValueError, match="Apify token is not configured"):
        search_apify(
            location="Bangkok",
            check_in="2026-11-01",
            check_out="2026-11-05",
            guests=2,
            rooms=1,
            currency="USD",
            limit=5,
            config=cfg,
        )


def test_search_scrape_public_api_mocked():
    """Verify direct Agoda search via public SearchResultList API."""
    mock_sug_resp = MagicMock()
    mock_sug_resp.status_code = 200
    mock_sug_resp.json.return_value = {
        "Data": [{"ObjectId": "4064", "ObjectName": "Singapore", "CityId": "4064"}]
    }

    mock_search_resp = MagicMock()
    mock_search_resp.status_code = 200
    mock_search_resp.json.return_value = {
        "properties": [
            {
                "propertyId": 3344,
                "displayName": "Marina Bay Suites",
                "rating": 9.0,
                "reviewCount": 890,
                "reviewScoreWord": "Wonderful",
                "pricing": {"pricePerNight": 320.0, "totalPrice": 1280.0},
                "latitude": 1.2838,
                "longitude": 103.8591,
                "address": "Marina Bay, Singapore",
                "isFreeCancellation": True,
                "starRating": 5,
            }
        ]
    }

    cfg = AgodaConfig()
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_sug_resp
        mock_client.post.return_value = mock_search_resp
        mock_client_cls.return_value = mock_client

        results = search_scrape(
            location="Singapore",
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
        assert h.name == "Marina Bay Suites"
        assert h.hotel_id == "3344"
        assert h.rating == 9.0
        assert h.total_price == 320.0
        assert "Free cancellation" in h.badges
        assert "5★" in h.badges


# =====================================================================
# 4. Hybrid Fallback & Router Tests
# =====================================================================

def test_search_hotels_hybrid_order():
    """Verify auto provider attempts RapidAPI, then Apify, then scrape."""
    # Scenario A: RapidAPI key present and succeeds
    cfg_rapid = AgodaConfig(api_key="valid-key", apify_token="valid-token")
    with patch("agoda.search_rapidapi") as mock_rapid:
        mock_rapid.return_value = [Hotel(name="Rapid Hotel", hotel_id="1")]
        results, provider = search_hotels("Tokyo", "2026-11-01", "2026-11-05", config=cfg_rapid)
        assert len(results) == 1
        assert "RapidAPI" in provider

    # Scenario B: RapidAPI missing, Apify present and succeeds
    cfg_apify = AgodaConfig(api_key=None, apify_token="valid-token")
    with patch("agoda.search_apify") as mock_apify:
        mock_apify.return_value = [Hotel(name="Apify Hotel", hotel_id="2")]
        results, provider = search_hotels("Tokyo", "2026-11-01", "2026-11-05", config=cfg_apify)
        assert len(results) == 1
        assert "Apify" in provider

    # Scenario C: Both RapidAPI and Apify missing, falls back to direct scrape
    cfg_scrape = AgodaConfig(api_key=None, apify_token=None)
    with patch("agoda.search_scrape") as mock_scrape:
        mock_scrape.return_value = [Hotel(name="Scraped Hotel", hotel_id="3")]
        results, provider = search_hotels("Tokyo", "2026-11-01", "2026-11-05", config=cfg_scrape)
        assert len(results) == 1
        assert "Web Fallback" in provider


def test_search_hotels_all_fail_raises_runtime_error():
    """Verify RuntimeError when all providers raise exceptions."""
    cfg = AgodaConfig(api_key="bad-key", apify_token="bad-token")
    with patch("agoda.search_rapidapi", side_effect=Exception("RapidAPI 401 Unauthorized")), \
         patch("agoda.search_apify", side_effect=Exception("Apify Quota Exceeded")), \
         patch("agoda.search_scrape", side_effect=Exception("Network Timeout")):
        with pytest.raises(RuntimeError, match="All Agoda providers failed"):
            search_hotels("Nowhere", "2026-11-01", "2026-11-05", config=cfg)


# =====================================================================
# 5. Wanderlog Mutation & Confirmation Tests
# =====================================================================

def test_add_lodging_to_wanderlog_confirmed():
    """Verify lodging mutation builds correct command and executes successfully."""
    hotel = Hotel(
        name="Hotel Gracery Shinjuku",
        hotel_id="555",
        rating=8.8,
        price_text="USD 190.00",
        check_in="2026-11-01",
        check_out="2026-11-05",
        latitude=35.6953,
        longitude=139.7022,
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Added successfully", stderr="")
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
        assert "--check-in" in args
        assert "2026-11-01" in args
        assert "--lat" in args
        assert "35.6953" in args


def test_add_lodging_to_wanderlog_cancelled_by_user():
    """Verify mutation is aborted when user answers 'n' to confirmation prompt."""
    hotel = Hotel(
        name="Hotel Gracery Shinjuku",
        hotel_id="555",
        check_in="2026-11-01",
        check_out="2026-11-05",
    )

    with patch("builtins.input", return_value="n"), \
         patch("subprocess.run") as mock_run:
        success = add_lodging_to_wanderlog(
            hotel=hotel,
            trip_key="test-trip-key",
            interactive=True,
        )
        assert success is False
        mock_run.assert_not_called()


# =====================================================================
# 6. Status Check & Diagnostic Table Tests
# =====================================================================

def test_status_check_formatting():
    """Verify run_status_check builds and prints status table cleanly."""
    cfg = AgodaConfig(
        api_key="1234567890abcdef",
        apify_token="apify_api_token_12345",
        session_cookie="session_cookie_string",
    )

    with patch("agoda.console.print") as mock_print:
        run_status_check(cfg)
        assert mock_print.called
        # Check table structure
        printed_obj = mock_print.call_args[0][0]
        assert printed_obj.title == "🔍 Agoda Integration Status"


# =====================================================================
# 7. CLI End-to-End Invocations & Filters
# =====================================================================

def test_cli_search_json_output_and_filters(capsys):
    """Verify CLI search subcommand outputs valid JSON and respects filters."""
    fake_hotels = [
        Hotel(name="Budget Inn", hotel_id="1", rating=7.2, total_price=100.0),
        Hotel(name="Deluxe Resort", hotel_id="2", rating=9.0, total_price=220.0),
        Hotel(name="Luxury Palace", hotel_id="3", rating=9.5, total_price=500.0),
    ]

    test_args = [
        "agoda.py",
        "search",
        "-l", "Tokyo",
        "--min-rating", "8.5",
        "--max-price", "300",
        "-f", "json",
    ]

    with patch("sys.argv", test_args), \
         patch("agoda.search_hotels", return_value=(fake_hotels, "Mock Provider")):
        main()

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["location"] == "Tokyo"
    assert data["provider"] == "Mock Provider"
    assert data["count"] == 1
    assert data["hotels"][0]["name"] == "Deluxe Resort"
    assert data["hotels"][0]["rating"] == 9.0
    assert data["hotels"][0]["total_price"] == 220.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
