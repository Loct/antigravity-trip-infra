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
    build_booking_hotel_url,
    run_status_check,
    search_hotels,
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
        provider="Cookie Session",
        check_in="2026-11-01",
        check_out="2026-11-05",
    )
    d = h.to_dict()
    assert d["name"] == "Test Hotel"
    assert d["rating"] == 9.2
    assert d["currency"] == "USD"
    assert "Free cancellation" in d["badges"]


def test_booking_config_resolution(monkeypatch, tmp_path):
    monkeypatch.setenv("BOOKING_SESSION_COOKIE", "bkng_sso_session=abc123xyz")

    cfg = BookingConfig()
    assert cfg.session_cookie == "bkng_sso_session=abc123xyz"


def test_booking_config_from_credentials_file(monkeypatch, tmp_path):
    monkeypatch.delenv("BOOKING_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("BOOKING_COM_COOKIES", raising=False)
    monkeypatch.delenv("BOOKING_COOKIE", raising=False)

    fake_home = tmp_path / "home"
    booking_dir = fake_home / ".config" / "booking"
    booking_dir.mkdir(parents=True)
    creds_file = booking_dir / "credentials.json"
    creds_file.write_text(json.dumps({"session_cookie": "bkng_sso_session=file_cookie"}), encoding="utf-8")

    monkeypatch.setattr(Path, "home", lambda: fake_home)

    cfg = BookingConfig()
    assert cfg.session_cookie == "bkng_sso_session=file_cookie"


MOCK_BOOKING_HTML = """
<!DOCTYPE html>
<html>
<body>
  <div data-testid="property-card">
    <a data-testid="title-link" href="/hotel/jp/tokyo-grand-hotel.html">
      <div data-testid="title">Tokyo Grand Hotel</div>
    </a>
    <div data-testid="review-score">8.8 Fabulous</div>
    <div data-testid="price-and-discounted-price">€ 450.00</div>
    <div data-testid="address">Minato, Tokyo</div>
    <div>Genius Deal Available</div>
  </div>
  <div data-testid="property-card">
    <a data-testid="title-link" href="/hotel/jp/shinjuku-residence.html">
      <div data-testid="title">Shinjuku Residence</div>
    </a>
    <div data-testid="review-score">9.1 Superb</div>
    <div data-testid="price-and-discounted-price">€ 320.00</div>
    <div data-testid="address">Shinjuku, Tokyo</div>
  </div>
</body>
</html>
"""


def test_search_cookie_mocked():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = MOCK_BOOKING_HTML
    mock_resp.raise_for_status = MagicMock()

    cfg = BookingConfig(session_cookie="bkng_sso_session=test_cookie")

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        results, provider = search_hotels(
            location="Tokyo",
            check_in="2026-11-01",
            check_out="2026-11-05",
            guests=2,
            rooms=1,
            currency="EUR",
            limit=5,
            genius_level=3,
            config=cfg,
        )

        assert len(results) == 2
        assert provider == "Cookie Session (Booking.com)"

        h1 = results[0]
        assert h1.name == "Tokyo Grand Hotel"
        assert h1.rating == 8.8
        assert h1.total_price == 450.0
        assert h1.currency == "EUR"
        assert "Genius Deal" in h1.badges
        # Genius Level 3 (20% off) applied to verified Genius properties
        assert h1.genius_price == 360.0
        assert "Genius L3 (-20%)" in h1.badges
        assert "https://www.booking.com/hotel/jp/tokyo-grand-hotel.html" in h1.url
        assert "checkin=2026-11-01" in h1.url

        h2 = results[1]
        assert h2.name == "Shinjuku Residence"
        assert h2.rating == 9.1
        assert h2.total_price == 320.0
        assert h2.genius_price is None


def test_search_cookie_missing_cookie():
    cfg = BookingConfig(session_cookie="")
    with pytest.raises(ValueError, match="Booking.com session cookie is not configured"):
        search_hotels(
            location="Tokyo",
            check_in="2026-11-01",
            check_out="2026-11-05",
            config=cfg,
        )


def test_search_cookie_challenge_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 202
    mock_resp.text = "Challenge required"

    cfg = BookingConfig(session_cookie="bkng_sso_session=stale_cookie")

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with pytest.raises(PermissionError, match="session challenge or verification required"):
            search_hotels(
                location="Tokyo",
                check_in="2026-11-01",
                check_out="2026-11-05",
                config=cfg,
            )


def test_search_cookie_empty_results():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html><body><div>No hotels</div></body></html>"
    mock_resp.raise_for_status = MagicMock()

    cfg = BookingConfig(session_cookie="bkng_sso_session=test_cookie")

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with pytest.raises(ValueError, match="No property cards could be parsed"):
            search_hotels(
                location="Nowhere",
                check_in="2026-11-01",
                check_out="2026-11-05",
                config=cfg,
            )


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
    cfg = BookingConfig(session_cookie="test-cookie")
    # Ensure run_status_check executes without errors
    run_status_check(cfg)


def test_genius_discount_application():
    hotels = [
        Hotel(
            name="Genius Hotel",
            hotel_id="101",
            total_price=500.0,
            price_text="€ 500.00",
            currency="EUR",
            is_genius_deal=True,
        ),
        Hotel(
            name="Regular Hotel",
            hotel_id="102",
            total_price=500.0,
            price_text="€ 500.00",
            currency="EUR",
            is_genius_deal=False,
        ),
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
        Hotel(
            name="Genius Hotel 2",
            hotel_id="103",
            total_price=500.0,
            price_text="€ 500.00",
            currency="EUR",
            is_genius_deal=True,
        )
    ]
    apply_genius_discounts(hotels2, genius_level=2)
    assert hotels2[0].genius_price == 425.0

    # Level 1: 10% off
    hotels1 = [
        Hotel(
            name="Genius Hotel 1",
            hotel_id="104",
            total_price=500.0,
            price_text="€ 500.00",
            currency="EUR",
            is_genius_deal=True,
        )
    ]
    apply_genius_discounts(hotels1, genius_level=1)
    assert hotels1[0].genius_price == 450.0


def test_build_booking_hotel_url():
    # With canonical url from provider and dates
    url = build_booking_hotel_url(
        name="Tam Coc Victoria Hotel",
        canonical_url="https://www.booking.com/hotel/vn/tam-coc-victoria.html",
        check_in="2027-01-27",
        check_out="2027-01-29",
        guests=2,
        rooms=1,
    )
    assert "https://www.booking.com/hotel/vn/tam-coc-victoria.html" in url
    assert "checkin=2027-01-27" in url
    assert "checkout=2027-01-29" in url
    assert "group_adults=2" in url

    # Default to search link without canonical URL
    url_fallback = build_booking_hotel_url(
        name="Tam Coc Victoria Hotel",
        canonical_url=None,
        check_in="2027-01-27",
        check_out="2027-01-29",
        guests=2,
        rooms=1,
    )
    assert "https://www.booking.com/searchresults.html" in url_fallback
    assert "ss=Tam+Coc+Victoria+Hotel" in url_fallback
    assert "checkin=2027-01-27" in url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
