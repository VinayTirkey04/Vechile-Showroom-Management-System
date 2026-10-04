"""Security tests - non-functional requirement 5.3 (authentication, RBAC, data protection)."""
import io

import pytest

from vsms import create_app
from vsms.config import TestConfig
from vsms.extensions import db
from vsms.models import Sale, Vehicle
from tests.conftest import login, make_user, make_vehicle


def test_anonymous_redirected_to_login_for_protected_pages(client, app, vehicle):
    for url in ("/my/bookings", "/my/history", "/admin/", "/admin/vehicles", "/service/", "/profile"):
        r = client.get(url)
        assert r.status_code == 302 and "/login" in r.headers["Location"], url


def test_customer_cannot_reach_staff_pages(client, app, customer):
    login(client, "cust@test.com", "Passw0rd1")
    for url in ("/admin/", "/admin/vehicles", "/admin/customers", "/admin/settings", "/admin/sales.csv", "/service/", "/admin/outbox"):
        assert client.get(url).status_code == 403, url
    assert client.post("/admin/settings", data={"tax_rate": "0", "handling_charge": "0"}).status_code == 403


def test_sales_staff_limited_to_subset_of_admin_functions(client, app):
    make_user("sales@test.com", "sales", "Sales@1234")
    login(client, "sales@test.com", "Sales@1234")
    assert client.get("/admin/").status_code == 200 and client.get("/admin/test-drives").status_code == 200
    assert client.get("/admin/vehicles").status_code == 403            # REQ-ADM-4 only admins edit inventory
    assert client.get("/admin/settings").status_code == 403
    assert client.get("/service/").status_code == 403


def test_admin_cannot_be_impersonated_by_posting_role(client, app):
    r = client.post("/register", data={"name": "Eve", "email": "eve@test.com", "phone": "9876543210",
                                       "password": "Passw0rd1", "role": "admin"}, follow_redirects=True)
    from vsms.models import User
    assert User.query.filter_by(email="eve@test.com").one().role == "customer"


def test_cannot_view_another_customers_invoice(client, app, vehicle):
    from vsms import services
    owner = make_user("owner@test.com")
    sale = services.purchase_vehicle(owner, vehicle.id, "4242424242424242", "12/30", "123")
    make_user("snoop@test.com")
    login(client, "snoop@test.com", "Passw0rd1")
    assert client.get(f"/invoice/{sale.id}").status_code == 403
    client.post("/logout")
    login(client, "owner@test.com", "Passw0rd1")
    assert client.get(f"/invoice/{sale.id}").status_code == 200


def test_open_redirect_blocked_on_login(client, app, customer):
    r = client.post("/login?next=https://evil.example/", data={"email": "cust@test.com", "password": "Passw0rd1"})
    assert r.status_code == 302 and "evil.example" not in r.headers["Location"]
    client.post("/logout")
    r = client.post("/login?next=//evil.example", data={"email": "cust@test.com", "password": "Passw0rd1"})
    assert "evil.example" not in r.headers["Location"]


def test_xss_in_vehicle_fields_is_escaped(client, app):
    make_vehicle("XSS1", brand="<script>alert(1)</script>", model="X")
    body = client.get("/vehicles").data
    assert b"<script>alert(1)</script>" not in body and b"&lt;script&gt;" in body


def test_security_headers_present(client):
    r = client.get("/vehicles")
    assert r.headers["X-Frame-Options"] == "DENY" and r.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]


def test_passwords_and_card_numbers_never_stored_in_plain_text(app, customer, vehicle):
    from vsms import services
    sale = services.purchase_vehicle(customer, vehicle.id, "4242424242424242", "12/30", "123")
    assert customer.password_hash != "Passw0rd1"
    stored = " ".join(str(getattr(sale, c.name)) for c in Sale.__table__.columns)
    assert "4242424242424242" not in stored and sale.card_last4 == "4242"


def test_image_upload_validation(client, app, admin):
    login(client, "admin@test.com", "Admin@1234")
    data = {"vehicle_number": "IMG1", "brand": "A", "model": "B", "category": "SUV", "year": "2026", "price": "100"}
    ok = dict(data, image=(io.BytesIO(b"\x89PNG fake"), "car.png"))
    assert client.post("/admin/vehicles/new", data=ok, content_type="multipart/form-data", follow_redirects=True).status_code == 200
    assert Vehicle.query.filter_by(vehicle_number="IMG1").one().image_filename.endswith(".png")
    bad = dict(data, vehicle_number="IMG2", image=(io.BytesIO(b"MZ exe"), "evil.exe"))
    r = client.post("/admin/vehicles/new", data=bad, content_type="multipart/form-data", follow_redirects=True)
    assert b"ignored" in r.data and Vehicle.query.filter_by(vehicle_number="IMG2").one().image_filename is None


def test_csrf_enforced_when_enabled(tmp_path):
    class Secure(TestConfig):
        CSRF_ENABLED = True
        UPLOAD_FOLDER = str(tmp_path)
    app = create_app(Secure)
    with app.app_context():
        make_user("c@test.com")
        c = app.test_client()
        assert c.post("/login", data={"email": "c@test.com", "password": "Passw0rd1"}).status_code == 400
        page = c.get("/login").data.decode()
        token = page.split('name="_csrf" value="')[1].split('"')[0]
        r = c.post("/login", data={"email": "c@test.com", "password": "Passw0rd1", "_csrf": token})
        assert r.status_code == 302
        db.session.remove()
        db.drop_all()
