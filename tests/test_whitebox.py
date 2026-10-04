"""White-box tests - every branch of the decision-heavy functions is exercised explicitly
(see docs/WHITE_BOX_TESTING.md for the control-flow graphs and cyclomatic-complexity notes)."""
from datetime import datetime

import pytest

from vsms import services
from vsms.payment import _expiry_ok, charge
from vsms.services import BusinessError, clean_vehicle_form, has_overlap
from tests.conftest import make_user, make_vehicle

NOW = datetime(2026, 10, 4, 8, 0)


# --- has_overlap: boundary conditions of  start < end2 AND end > start2 ------------------
@pytest.mark.parametrize("s,e,expected", [
    (9, 10, False),    # entirely before existing 10-11 (touching at boundary)
    (9, 11, True),     # overlaps front
    (10, 11, True),    # exact same
    (10, 12, True),    # overlaps back
    (10.5, 11, True),  # inside
    (11, 12, False),   # starts exactly when existing ends
    (8, 12, True),     # fully contains
])
def test_has_overlap_boundaries(app, customer, vehicle, s, e, expected):
    base = datetime(2026, 10, 6)
    td_start, td_end = base.replace(hour=10), base.replace(hour=11)
    from vsms.extensions import db
    from vsms.models import TestDrive
    db.session.add(TestDrive(user_id=customer.id, vehicle_id=vehicle.id, start_time=td_start, end_time=td_end))
    db.session.commit()

    def at(h):
        return base.replace(hour=int(h), minute=int((h % 1) * 60))
    assert has_overlap(vehicle.id, at(s), at(e)) is expected


def test_has_overlap_ignores_cancelled_and_other_vehicles(app, customer, vehicle):
    from vsms.extensions import db
    from vsms.models import TestDrive
    other_v = make_vehicle("OV2")
    base = datetime(2026, 10, 6)
    db.session.add(TestDrive(user_id=customer.id, vehicle_id=vehicle.id, start_time=base.replace(hour=10),
                             end_time=base.replace(hour=11), status="cancelled"))
    db.session.add(TestDrive(user_id=customer.id, vehicle_id=other_v.id, start_time=base.replace(hour=10),
                             end_time=base.replace(hour=11)))
    db.session.commit()
    assert not has_overlap(vehicle.id, base.replace(hour=10), base.replace(hour=11))


# --- clean_vehicle_form: each validation branch --------------------------------------------
def _form(**kw):
    f = {"vehicle_number": "mh01zz9999", "brand": "Kia", "model": "Seltos", "category": "SUV",
         "year": "2026", "price": "1500000"}
    f.update(kw)
    return f


def test_clean_form_happy_path_normalises_number(app):
    assert clean_vehicle_form(_form())["vehicle_number"] == "MH01ZZ9999"


@pytest.mark.parametrize("bad,msg", [
    ({"vehicle_number": ""}, "Vehicle number is required"),
    ({"brand": " "}, "Brand is required"),
    ({"model": ""}, "Model is required"),
    ({"category": "Truck"}, "valid category"),
    ({"year": "abc"}, "Year must be a number"),
    ({"year": "1800"}, "realistic"),
    ({"price": "x"}, "whole number"),
    ({"price": "0"}, "greater than zero"),
    ({"price": "-5"}, "greater than zero"),
])
def test_clean_form_each_error_branch(app, bad, msg):
    with pytest.raises(BusinessError, match=msg):
        clean_vehicle_form(_form(**bad))


def test_clean_form_duplicate_number_branch_and_edit_exclusion(app):
    v = make_vehicle("DUP1")
    with pytest.raises(BusinessError, match="already exists"):
        clean_vehicle_form(_form(vehicle_number="dup1"))
    assert clean_vehicle_form(_form(vehicle_number="dup1"), vehicle_id=v.id)  # editing itself is fine


# --- payment expiry branches -----------------------------------------------------------------
@pytest.mark.parametrize("exp,ok", [("10/26", True), ("09/26", False), ("12/25", False), ("12/27", True),
                                     ("00/30", False), ("1/2/3", False), (None, False), ("", False)])
def test_expiry_branches(exp, ok):
    assert _expiry_ok(exp, NOW) is ok


# --- delete_vehicle branches --------------------------------------------------------------------
def test_delete_vehicle_branches(app, customer):
    with pytest.raises(BusinessError, match="not found"):
        services.delete_vehicle(404)
    sold = make_vehicle("D-SOLD")
    services.purchase_vehicle(customer, sold.id, "4242424242424242", "12/29", "123", now=NOW)
    with pytest.raises(BusinessError, match="sold vehicle"):
        services.delete_vehicle(sold.id)
    booked = make_vehicle("D-BOOKED")
    services.book_test_drive(customer, booked.id, datetime(2026, 10, 6, 11, 0), now=NOW)
    with pytest.raises(BusinessError, match="Cancel the active"):
        services.delete_vehicle(booked.id)
    free = make_vehicle("D-FREE")
    services.delete_vehicle(free.id)
    from vsms.models import Vehicle
    assert Vehicle.query.filter_by(vehicle_number="D-FREE").first() is None
