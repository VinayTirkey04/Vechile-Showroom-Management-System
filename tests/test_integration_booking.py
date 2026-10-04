"""Integration tests - test drive booking (REQ-TD-1..4) and its notification side effects."""
from datetime import datetime, timedelta

import pytest

from vsms import services
from vsms.extensions import db
from vsms.models import Notification, TestDrive
from vsms.services import BusinessError
from tests.conftest import make_user, make_vehicle

NOW = datetime(2026, 10, 4, 8, 0)
SLOT = datetime(2026, 10, 6, 11, 0)   # a Tuesday, inside 9-18


def test_book_success_creates_booking_and_email(app, customer, vehicle):
    td = services.book_test_drive(customer, vehicle.id, SLOT, now=NOW)
    assert td.status == "booked" and td.end_time == SLOT + timedelta(hours=1)
    mail = Notification.query.filter_by(subject="Test drive confirmed").one()   # REQ-TD-3
    assert mail.to_email == customer.email


def test_double_booking_same_vehicle_overlap_blocked(app, customer, vehicle):
    other = make_user("other@test.com")
    services.book_test_drive(customer, vehicle.id, SLOT, now=NOW)
    with pytest.raises(BusinessError, match="already booked"):          # REQ-TD-4
        services.book_test_drive(other, vehicle.id, SLOT + timedelta(minutes=30), now=NOW)


def test_adjacent_slots_are_allowed(app, customer, vehicle):
    other = make_user("other@test.com")
    services.book_test_drive(customer, vehicle.id, SLOT, now=NOW)
    services.book_test_drive(other, vehicle.id, SLOT + timedelta(hours=1), now=NOW)  # back-to-back is fine
    assert TestDrive.query.count() == 2


def test_customer_cannot_be_in_two_places_at_once(app, customer, vehicle):
    v2 = make_vehicle("V2", model="i20")
    services.book_test_drive(customer, vehicle.id, SLOT, now=NOW)
    with pytest.raises(BusinessError, match="already have"):
        services.book_test_drive(customer, v2.id, SLOT, now=NOW)


@pytest.mark.parametrize("when,msg", [
    (datetime(2026, 10, 3, 11, 0), "future"),
    (datetime(2026, 10, 6, 8, 30), "between"),     # before opening
    (datetime(2026, 10, 6, 17, 30), "between"),    # would end after closing
])
def test_invalid_slots_rejected(app, customer, vehicle, when, msg):
    with pytest.raises(BusinessError, match=msg):
        services.book_test_drive(customer, vehicle.id, when, now=NOW)


def test_last_valid_slot_ends_exactly_at_closing(app, customer, vehicle):
    services.book_test_drive(customer, vehicle.id, datetime(2026, 10, 6, 17, 0), now=NOW)


def test_sold_vehicle_cannot_be_booked(app, customer):
    v = make_vehicle("SOLD1", status="sold")
    with pytest.raises(BusinessError, match="sold"):
        services.book_test_drive(customer, v.id, SLOT, now=NOW)


def test_only_customers_can_book(app, admin, vehicle):
    with pytest.raises(BusinessError, match="customers"):
        services.book_test_drive(admin, vehicle.id, SLOT, now=NOW)


def test_unknown_vehicle(app, customer):
    with pytest.raises(BusinessError, match="not found"):
        services.book_test_drive(customer, 9999, SLOT, now=NOW)


def test_cancel_frees_the_slot(app, customer, vehicle):
    other = make_user("other@test.com")
    td = services.book_test_drive(customer, vehicle.id, SLOT, now=NOW)
    services.cancel_test_drive(customer, td.id)
    assert db.session.get(TestDrive, td.id).status == "cancelled"
    services.book_test_drive(other, vehicle.id, SLOT, now=NOW)         # slot reusable
    assert Notification.query.filter_by(subject="Test drive cancelled").count() == 1


def test_cannot_cancel_twice_or_someone_elses(app, customer, vehicle):
    other = make_user("other@test.com")
    td = services.book_test_drive(customer, vehicle.id, SLOT, now=NOW)
    with pytest.raises(BusinessError, match="not found"):
        services.cancel_test_drive(other, td.id)
    services.cancel_test_drive(customer, td.id)
    with pytest.raises(BusinessError, match="already cancelled"):
        services.cancel_test_drive(customer, td.id)


def test_reschedule_moves_booking_and_ignores_self_overlap(app, customer, vehicle):
    td = services.book_test_drive(customer, vehicle.id, SLOT, now=NOW)
    services.reschedule_test_drive(customer, td.id, SLOT + timedelta(minutes=30), now=NOW)  # overlaps only itself
    assert db.session.get(TestDrive, td.id).start_time == SLOT + timedelta(minutes=30)


def test_reschedule_into_taken_slot_rejected(app, customer, vehicle):
    other = make_user("other@test.com")
    services.book_test_drive(other, vehicle.id, SLOT, now=NOW)
    mine = services.book_test_drive(customer, vehicle.id, SLOT + timedelta(hours=2), now=NOW)
    with pytest.raises(BusinessError, match="already booked"):
        services.reschedule_test_drive(customer, mine.id, SLOT, now=NOW)


def test_sales_staff_can_complete_but_customer_cannot(app, customer, vehicle):
    staff = make_user("sales@test.com", "sales")
    td = services.book_test_drive(customer, vehicle.id, SLOT, now=NOW)
    with pytest.raises(BusinessError):
        services.complete_test_drive(customer, td.id)
    services.complete_test_drive(staff, td.id)
    assert db.session.get(TestDrive, td.id).status == "completed"
