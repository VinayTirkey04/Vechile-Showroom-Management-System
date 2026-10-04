"""Unit tests - vehicle search (REQ-SRCH) and price calculation (REQ-PUR-2)."""
import pytest

from vsms import services
from vsms.services import BusinessError, calculate_price
from tests.conftest import make_vehicle


@pytest.fixture()
def fleet(app):
    make_vehicle("A1", "Hyundai", "Creta", "SUV", 1600000)
    make_vehicle("A2", "Hyundai", "i20", "Hatchback", 800000)
    make_vehicle("A3", "Tata", "Nexon", "SUV", 1200000)
    make_vehicle("A4", "Tata", "Nexon EV", "EV", 1700000, status="sold")


def test_search_by_brand_case_insensitive(fleet):
    assert {v.model for v in services.search_vehicles(brand="hyundai")} == {"Creta", "i20"}


def test_search_by_partial_model(fleet):
    assert {v.model for v in services.search_vehicles(model="nex")} == {"Nexon", "Nexon EV"}


def test_search_price_range_inclusive(fleet):
    res = services.search_vehicles(min_price=800000, max_price=1200000)
    assert {v.vehicle_number for v in res} == {"A2", "A3"}


def test_search_invalid_range_rejected(fleet):
    with pytest.raises(BusinessError):
        services.search_vehicles(min_price=5, max_price=1)


def test_search_available_only_excludes_sold(fleet):
    assert "A4" not in {v.vehicle_number for v in services.search_vehicles(available_only=True)}
    assert "A4" in {v.vehicle_number for v in services.search_vehicles()}  # sold still visible, flagged


def test_search_no_match_returns_empty(fleet):
    assert services.search_vehicles(brand="Ferrari") == []


def test_search_combined_filters(fleet):
    res = services.search_vehicles(brand="tata", category="SUV")
    assert [v.vehicle_number for v in res] == ["A3"]


def test_search_is_not_vulnerable_to_sql_injection(fleet):
    assert services.search_vehicles(brand="' OR 1=1 --") == []


def test_calculate_price_basic():
    p = calculate_price(1000000, 18, 15000)
    assert p == {"base_price": 1000000, "tax_rate": 18, "tax_amount": 180000,
                 "handling_charge": 15000, "total": 1195000}


def test_calculate_price_rounds_half_up():
    assert calculate_price(1005, 10, 0)["tax_amount"] == 101   # 100.5 -> 101
    assert calculate_price(1004, 10, 0)["tax_amount"] == 100   # 100.4 -> 100


def test_calculate_price_zero_tax_and_negative_rejected():
    assert calculate_price(500, 0, 0)["total"] == 500
    with pytest.raises(BusinessError):
        calculate_price(-1, 18, 0)


def test_pricing_config_update_changes_totals(app, vehicle):
    assert services.price_for(vehicle)["tax_rate"] == 18
    services.update_pricing_config(28, 20000)
    p = services.price_for(vehicle)
    assert p["tax_amount"] == 280000 and p["total"] == 1300000
    with pytest.raises(BusinessError):
        services.update_pricing_config(101, 0)
