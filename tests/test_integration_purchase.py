"""Integration tests - purchase -> payment -> inventory -> invoice -> notifications (REQ-PUR-1..5, REQ-SVC-1)."""
from datetime import datetime

import pytest

from vsms import services
from vsms.extensions import db
from vsms.models import Invoice, Notification, Sale, TestDrive, Vehicle
from vsms.services import BusinessError
from tests.conftest import make_user, make_vehicle

GOOD = ("4242424242424242", "12/29", "123")
NOW = datetime(2026, 10, 4, 8, 0)


def test_purchase_marks_sold_creates_sale_invoice_and_email(app, customer, vehicle):
    sale = services.purchase_vehicle(customer, vehicle.id, *GOOD, now=NOW)
    assert db.session.get(Vehicle, vehicle.id).status == "sold"                    # REQ-PUR-4
    assert sale.total == 1000000 + 180000 + 15000                            # REQ-PUR-2
    assert sale.card_last4 == "4242" and "4242424242424242" not in repr(sale.__dict__)
    inv = Invoice.query.one()                                                # REQ-SVC-1 / REQ-PUR-5
    assert inv.invoice_number == f"INV-2026-{sale.id:05d}"
    assert Notification.query.filter(Notification.subject.like("Invoice INV-%")).count() == 1


def test_declined_card_leaves_vehicle_available_and_no_sale(app, customer, vehicle):
    with pytest.raises(BusinessError, match="declined"):
        services.purchase_vehicle(customer, vehicle.id, "4000000000000002", "12/29", "123", now=NOW)
    assert db.session.get(Vehicle, vehicle.id).status == "available"               # claim rolled back
    assert Sale.query.count() == 0 and Invoice.query.count() == 0


def test_invalid_card_leaves_vehicle_available(app, customer, vehicle):
    with pytest.raises(BusinessError):
        services.purchase_vehicle(customer, vehicle.id, "1111", "12/29", "123", now=NOW)
    assert db.session.get(Vehicle, vehicle.id).status == "available"


def test_cannot_buy_same_vehicle_twice(app, customer, vehicle):
    other = make_user("other@test.com")
    services.purchase_vehicle(customer, vehicle.id, *GOOD, now=NOW)
    with pytest.raises(BusinessError, match="no longer available"):
        services.purchase_vehicle(other, vehicle.id, *GOOD, now=NOW)
    assert Sale.query.count() == 1


def test_purchase_cancels_pending_test_drives_of_that_vehicle(app, customer, vehicle):
    other = make_user("other@test.com")
    services.book_test_drive(other, vehicle.id, datetime(2026, 10, 6, 11, 0), now=NOW)
    services.purchase_vehicle(customer, vehicle.id, *GOOD, now=NOW)
    assert TestDrive.query.one().status == "cancelled"                       # business rule 5.5
    assert Notification.query.filter_by(to_email="other@test.com", subject="Test drive cancelled").count() == 1


def test_purchase_uses_current_tax_configuration(app, customer, vehicle):
    services.update_pricing_config(28, 0)
    assert services.purchase_vehicle(customer, vehicle.id, *GOOD, now=NOW).total == 1280000


def test_only_customers_can_purchase(app, admin, vehicle):
    with pytest.raises(BusinessError):
        services.purchase_vehicle(admin, vehicle.id, *GOOD, now=NOW)


def test_service_records_lifecycle(app, customer, vehicle):
    svc = make_user("svc@test.com", "service")
    sale = services.purchase_vehicle(customer, vehicle.id, *GOOD, now=NOW)
    rec = services.create_service_record(svc, sale.id, "First free service", datetime(2026, 11, 1).date(), 0)
    assert rec.status == "scheduled"
    services.update_service_record(svc, rec.id, "completed", 2500)
    assert sale.service_records[0].status == "completed" and sale.service_records[0].cost == 2500
    with pytest.raises(BusinessError):
        services.create_service_record(customer, sale.id, "hack", datetime(2026, 11, 1).date())
    with pytest.raises(BusinessError):
        services.update_service_record(svc, rec.id, "bogus", 0)


def test_reports_reflect_sales(app, customer):
    v1 = make_vehicle("R1", brand="Tata", model="Nexon", price=1000000)
    v2 = make_vehicle("R2", brand="Tata", model="Harrier", price=2000000)
    services.purchase_vehicle(customer, v1.id, *GOOD, now=NOW)
    services.purchase_vehicle(customer, v2.id, *GOOD, now=NOW)
    r = services.sales_report()
    assert r["count"] == 2 and r["revenue"] == (1000000 + 2000000) * 118 // 100 + 30000
    assert r["by_brand"][0][0] == "Tata" and r["by_brand"][0][1][0] == 2
    assert services.inventory_summary()["SUV"]["sold"] == 2
