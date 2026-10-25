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

from booking import (
    BookingConfig,
    Hotel,
    add_lodging_to_wanderlog,
    apply_genius_discounts,
    print_pretty_table,
    run_status_check,
    search_apify,
    search_hotels,
    search_rapidapi,
)


def test_hotel_dataclass():
    h = Hotel(
        name="Test Hotel",
        hotel_id="12345",
        rating=9.2,
        review_count=500,
        review_word="Superb",
        price_text="USD 200.00",
        price_per_night=200.0,
        total_price=800.0,
        currency="USD",
        address="123 Test St",
        latitude=35.6895,
        longitude=139.6917,
        url="https://booking.com/hotel/12345.html",
        photo_url="https://example.com/photo.jpg",
        badges=["Free cancellation"],
        provider="RapidAPI",
        check_in="2026-11-01",
        check_out="2026-11-05",
    )
    d = h.to_dict()
    assert d["name"] == "Test Hotel"
    assert d["rating"] == 9.2
    assert d["currency"] == "USD"
    assert "Free cancellation" in d["badges"]


def test_booking_config_resolution(monkeypatch, tmp_path):
    monkeypatch.setenv("BOOKING_API_KEY", "test-api-key")
    monkeypatch.setenv("APIFY_TOKEN", "test-apify-token")
    monkeypatch.setenv("BOOKING_SESSION_COOKIE", "bkng_sso_session=abc")
    monkeypatch.setenv("RAPIDAPI_HOST", "booking-com15.p.rapidapi.com")

    cfg = BookingConfig()
    assert cfg.api_key == "test-api-key"
    assert cfg.apify_token == "test-apify-token"
    assert cfg.session_cookie == "bkng_sso_session=abc"
    assert cfg.rapidapi_host == "booking-com15.p.rapidapi.com"


def test_search_rapidapi_mocked():
    mock_dest_resp = MagicMock()
    mock_dest_resp.json.return_value = {
        "data": [{"dest_id": "-246227", "search_type": "city", "name": "Tokyo"}]
    }
    mock_dest_resp.raise_for_status = MagicMock()

    mock_hotels_resp = MagicMock()
    mock_hotels_resp.json.return_value = {
        "data": {
            "hotels": [
                {
                    "hotel_id": 101,
                    "property": {
                        "name": "Tokyo Grand Hotel",
                        "id": 101,
                        "reviewScore": 8.8,
                        "reviewCount": 1200,
                        "reviewScoreWord": "Fabulous",
                        "priceBreakdown": {
                            "grossPrice": {"value": 450.0, "currency": "USD"}
                        },
                        "latitude": 35.68,
                        "longitude": 139.75,
                        "wishlistName": "Minato, Tokyo",
                        "isFreeCancellation": True,
                    },
                }
            ]
        }
    }
    mock_hotels_resp.raise_for_status = MagicMock()

    cfg = BookingConfig(api_key="mock-key", rapidapi_host="booking-com15.p.rapidapi.com")

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
        assert h.name == "Tokyo Grand Hotel"
        assert h.rating == 8.8
        assert h.total_price == 450.0
        assert "Free cancellation" in h.badges


def test_search_rapidapi_booking_com18_mocked():
    mock_dest_resp = MagicMock()
    mock_dest_resp.json.return_value = {
        "status": True,
        "data": [{"id": "base64-location-id", "name": "Rome"}],
    }
    mock_dest_resp.raise_for_status = MagicMock()

    mock_hotels_resp = MagicMock()
    mock_hotels_resp.json.return_value = {
        "status": True,
        "data": [
            {
                "id": 99999,
                "name": "Rome Boutique Stay",
                "reviewScore": 9.1,
                "reviewCount": 1200,
                "reviewScoreWord": "Superb",
                "priceBreakdown": {
                    "grossPrice": {
                        "value": 520.0,
                        "currency": "EUR",
                        "amountRounded": "€ 520",
                    },
                    "benefitBadges": [{"text": "Genius Deal"}, {"text": "Free cancellation"}],
                },
                "latitude": 41.9,
                "longitude": 12.5,
                "photoUrls": ["https://example.com/rome.jpg"],
                "wishlistName": "Rome",
            }
        ],
    }
    mock_hotels_resp.raise_for_status = MagicMock()

    cfg = BookingConfig(
        api_key="mock-key",
        rapidapi_host="booking-com18.p.rapidapi.com",
    )

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.side_effect = [mock_dest_resp, mock_hotels_resp]
        mock_client_cls.return_value = mock_client

        results = search_rapidapi(
            location="Rome",
            check_in="2026-11-01",
            check_out="2026-11-05",
            guests=2,
            rooms=1,
            currency="EUR",
            limit=5,
            config=cfg,
        )

        assert len(results) == 1
        h = results[0]
        assert h.name == "Rome Boutique Stay"
        assert h.rating == 9.1
        assert h.total_price == 520.0
        assert h.currency == "EUR"
        assert "Genius Deal" in h.badges
        assert "Free cancellation" in h.badges
        assert h.provider == "RapidAPI (booking-com18)"


def test_search_apify_mocked():
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        {
            "id": "202",
            "name": "Kyoto Traditional Ryokan",
            "rating": 9.4,
            "reviewsCount": 850,
            "ratingText": "Exceptional",
            "price": 600.0,
            "address": "Gion, Kyoto",
            "lat": 35.0,
            "lng": 135.77,
            "url": "https://www.booking.com/hotel/jp/ryokan.html",
            "freeCancellation": True,
            "stars": 5,
        }
    ]
    mock_resp.raise_for_status = MagicMock()

    cfg = BookingConfig(apify_token="mock-token", apify_actor="voyager/booking-scraper")

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        results = search_apify(
            location="Kyoto",
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
        assert h.name == "Kyoto Traditional Ryokan"
        assert h.rating == 9.4
        assert h.total_price == 600.0
        assert "Free cancellation" in h.badges
        assert "5★" in h.badges


def test_search_hotels_hybrid_fallback():
    # Test fallback to Apify when RapidAPI key is absent
    cfg = BookingConfig(api_key="", apify_token="mock-token")
    with patch("booking.search_apify") as mock_apify:
        mock_apify.return_value = [
            Hotel(name="Fallback Hotel", hotel_id="303", rating=8.5)
        ]
        results, provider = search_hotels(
            location="Paris",
            check_in="2026-11-01",
            check_out="2026-11-05",
            config=cfg,
        )
        assert len(results) == 1
        assert "Apify" in provider


def test_add_lodging_to_wanderlog_cmd():
    hotel = Hotel(
        name="Hotel Granvia Kyoto",
        hotel_id="404",
        rating=9.0,
        price_text="USD 300.00",
        check_in="2026-11-01",
        check_out="2026-11-05",
        latitude=34.985,
        longitude=135.758,
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
        assert "Hotel Granvia Kyoto" in args


def test_default_currency_eur():
    hotel = Hotel(name="Euro Hotel", hotel_id="555")
    assert hotel.currency == "EUR"


def test_status_check():
    cfg = BookingConfig(api_key="test-key", apify_token=None, session_cookie=None)
    # Ensure run_status_check executes without errors
    run_status_check(cfg)


def test_genius_discount_application():
    hotels = [
        Hotel(name="Genius Hotel", hotel_id="101", total_price=500.0, price_text="€ 500.00", currency="EUR", is_genius_deal=True),
        Hotel(name="Regular Hotel", hotel_id="102", total_price=500.0, price_text="€ 500.00", currency="EUR", is_genius_deal=False),
    ]
    # Level 3: 20% off only for verified Genius properties
    apply_genius_discounts(hotels, genius_level=3)
    assert hotels[0].genius_price == 400.0
    assert "€ 400.00" in hotels[0].genius_price_text
    assert hotels[0].genius_discount_rate == 0.20
    assert "Genius L3 (-20%)" in hotels[0].badges

    # Non-genius property must NOT be discounted
    assert hotels[1].genius_price is None
    assert hotels[1].genius_price_text is None
    assert "Genius L3 (-20%)" not in hotels[1].badges

    # Level 2: 15% off
    hotels2 = [
        Hotel(name="Genius Hotel 2", hotel_id="103", total_price=500.0, price_text="€ 500.00", currency="EUR", is_genius_deal=True)
    ]
    apply_genius_discounts(hotels2, genius_level=2)
    assert hotels2[0].genius_price == 425.0

    # Level 1: 10% off
    hotels1 = [
        Hotel(name="Genius Hotel 1", hotel_id="104", total_price=500.0, price_text="€ 500.00", currency="EUR", is_genius_deal=True)
    ]
    apply_genius_discounts(hotels1, genius_level=1)
    assert hotels1[0].genius_price == 450.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
