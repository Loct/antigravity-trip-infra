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
    print_pretty_table,
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
        mock_apify.return_value = [
            Hotel(name="Fallback Agoda Hotel", hotel_id="888", rating=8.6)
        ]
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
    cfg = AgodaConfig(api_key="test-key", apify_token=None, session_cookie=None)
    # Ensure run_status_check executes cleanly
    run_status_check(cfg)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
