"""System tests - complete user journeys through the HTTP interface (SRS sections 4 & 5)."""
import io
from datetime import datetime, timedelta

from vsms.extensions import db
from vsms.models import Notification, Sale, TestDrive, User, Vehicle
from tests.conftest import login, make_user, make_vehicle


def future_slot(days=2, hour=11):
    d = (datetime.now() + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return d.strftime("%Y-%m-%dT%H:%M")


def test_full_customer_journey(client, app):
    """register -> login -> search -> test drive -> reschedule -> cancel -> purchase -> invoice -> history."""
    admin = make_user("admin@test.com", "admin", "Admin@1234", "Admin")
    v = make_vehicle("JOURNEY1", "Tata", "Nexon", "SUV", 1250000)

    r = client.post("/register", data={"name": "Priya N", "email": "priya@test.com", "phone": "9123456780",
                                       "password": "Secret123"}, follow_redirects=True)
    assert b"Account created" in r.data
    r = login(client, "priya@test.com", "Secret123")
    assert b"Find your next vehicle" in r.data

    r = client.get("/vehicles?brand=tata&max_price=1300000&available=1")
    assert b"Nexon" in r.data and b"1 vehicle(s) found" in r.data

    r = client.get(f"/vehicles/{v.id}")
    assert b"Total payable" in r.data and "₹14,90,000".encode() in r.data   # 12,50,000 + 18% tax + 15,000 handling

    r = client.post(f"/vehicles/{v.id}/test-drive", data={"start_time": future_slot()}, follow_redirects=True)
    assert b"Test drive booked" in r.data
    td = TestDrive.query.one()

    r = client.post(f"/my/bookings/{td.id}/reschedule", data={"start_time": future_slot(3, 14)}, follow_redirects=True)
    assert b"rescheduled" in r.data
    r = client.post(f"/my/bookings/{td.id}/cancel", follow_redirects=True)
    assert b"cancelled" in r.data.lower()

    r = client.post(f"/vehicles/{v.id}/purchase", data={"card_number": "4242 4242 4242 4242", "expiry": "12/30", "cvv": "123"},
                    follow_redirects=True)
    assert b"Payment successful" in r.data and b"Sales Invoice" in r.data and b"INV-" in r.data
    assert db.session.get(Vehicle, v.id).status == "sold"

    r = client.get("/my/history")
    assert b"Nexon" in r.data
    r = client.get("/my/emails")
    assert b"Test drive confirmed" in r.data and b"Invoice INV-" in r.data


def test_declined_payment_shows_error_and_keeps_vehicle(client, app, customer, vehicle):
    login(client, "cust@test.com", "Passw0rd1")
    r = client.post(f"/vehicles/{vehicle.id}/purchase", data={"card_number": "4000000000000002", "expiry": "12/30", "cvv": "123"},
                    follow_redirects=True)
    assert b"declined" in r.data
    assert db.session.get(Vehicle, vehicle.id).status == "available"


def test_sold_vehicle_page_blocks_actions(client, app, customer):
    v = make_vehicle("SOLDX", status="sold")
    login(client, "cust@test.com", "Passw0rd1")
    assert b"has been sold" in client.get(f"/vehicles/{v.id}").data
    r = client.post(f"/vehicles/{v.id}/test-drive", data={"start_time": future_slot()}, follow_redirects=True)
    assert b"sold" in r.data and TestDrive.query.count() == 0
    r = client.get(f"/vehicles/{v.id}/purchase")
    assert b"no longer available" in r.data


def test_invalid_login_message(client, app, customer):
    r = login(client, "cust@test.com", "nope")
    assert b"Invalid email or password" in r.data


def test_admin_journey_inventory_pricing_reports(client, app, admin):
    login(client, "admin@test.com", "Admin@1234")
    data = {"vehicle_number": "mh12new001", "brand": "Kia", "model": "Seltos", "variant": "HTX", "category": "SUV",
            "fuel_type": "Diesel", "color": "Black", "year": "2026", "price": "1700000", "description": "New", "specs": ""}
    r = client.post("/admin/vehicles/new", data=data, follow_redirects=True)
    assert b"Vehicle added" in r.data
    v = Vehicle.query.filter_by(vehicle_number="MH12NEW001").one()

    data.update(price="1650000")                      # REQ-ADM-2 price update
    r = client.post(f"/admin/vehicles/{v.id}/edit", data=data, follow_redirects=True)
    assert b"Vehicle updated" in r.data and db.session.get(Vehicle, v.id).price == 1650000

    r = client.post("/admin/settings", data={"tax_rate": "28", "handling_charge": "10000"}, follow_redirects=True)
    assert b"updated" in r.data
    assert b"28%" in client.get(f"/vehicles/{v.id}").data

    r = client.get("/admin/customers?q=admin")
    assert b"admin@test.com" in r.data
    r = client.post("/admin/staff/new", data={"name": "Sam Sales", "email": "sam@test.com", "phone": "9000011111",
                                              "role": "sales", "password": "Sales1234"}, follow_redirects=True)
    assert b"Staff account created" in r.data and User.query.filter_by(email="sam@test.com").one().role == "sales"

    r = client.post(f"/admin/vehicles/{v.id}/delete", follow_redirects=True)
    assert b"Vehicle deleted" in r.data
    assert client.get("/admin/sales.csv").mimetype == "text/csv"
    assert client.get("/admin/outbox").status_code == 200


def test_admin_user_management_actions(client, app, admin, customer):
    login(client, "admin@test.com", "Admin@1234")
    r = client.post(f"/admin/users/{customer.id}/toggle", follow_redirects=True)
    assert b"deactivated" in r.data
    assert db.session.get(User, customer.id).is_active_account is False
    r = client.post(f"/admin/users/{customer.id}/reset-password", follow_redirects=True)
    assert b"Temporary password" in r.data


def test_service_staff_flow(client, app, customer, vehicle):
    from vsms import services
    sale = services.purchase_vehicle(customer, vehicle.id, "4242424242424242", "12/30", "123")
    make_user("svc@test.com", "service", "Service@123", "Svc")
    login(client, "svc@test.com", "Service@123")
    r = client.post("/service/", data={"sale_id": sale.id, "description": "Oil change", "service_date": "2026-11-01", "cost": "1800"},
                    follow_redirects=True)
    assert b"Service record created" in r.data and b"Oil change" in r.data
    client.post("/logout")
    login(client, "cust@test.com", "Passw0rd1")
    assert b"Oil change" in client.get("/my/history").data                 # REQ-HIST-2


def test_profile_update_and_password_change(client, app, customer):
    login(client, "cust@test.com", "Passw0rd1")
    r = client.post("/profile", data={"action": "profile", "name": "New Name", "phone": "9999999999"}, follow_redirects=True)
    assert b"Profile updated" in r.data and db.session.get(User, customer.id).name == "New Name"
    r = client.post("/profile", data={"action": "password", "old": "Passw0rd1", "new": "Better1234"}, follow_redirects=True)
    assert b"Password changed" in r.data


def test_search_page_handles_garbage_inputs(client, app, vehicle):
    for qs in ("min_price=abc", "max_price=-1", "brand=%27%3B--", "min_price=100&max_price=1", "category=Boat"):
        assert client.get("/vehicles?" + qs).status_code == 200
