"""Business logic. Each function notes the SRS requirement it implements.

Routes stay thin: they call these functions, which raise BusinessError with a
user-friendly message when a rule is violated.
"""
import logging
import re
import secrets
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from flask import current_app
from sqlalchemy import func, update

from . import payment
from .extensions import db
from .models import (CATEGORIES, Invoice, Notification, Sale, ServiceRecord,
                     Setting, TestDrive, User, Vehicle)

log = logging.getLogger("vsms")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


class BusinessError(Exception):
    """A rule was violated; message is safe to show to the user."""


# ----------------------------------------------------------------- notifications
def notify(to_email, subject, body):
    """REQ-TD-3 / REQ-PUR-5: record an e-mail (caller commits)."""
    db.session.add(Notification(to_email=to_email, subject=subject, body=body))
    log.info("EMAIL to=%s subject=%s", to_email, subject)


# ----------------------------------------------------------------- settings / pricing
def get_setting(key, default):
    row = db.session.get(Setting, key)
    return int(row.value) if row else int(default)


def set_setting(key, value):
    row = db.session.get(Setting, key)
    if row:
        row.value = str(value)
    else:
        db.session.add(Setting(key=key, value=str(value)))


def get_pricing_config():
    cfg = current_app.config
    return (get_setting("tax_rate", cfg["DEFAULT_TAX_RATE"]),
            get_setting("handling_charge", cfg["DEFAULT_HANDLING_CHARGE"]))


def calculate_price(base_price, tax_rate, handling_charge):
    """REQ-PUR-2: total = base + tax + handling (tax rounded half-up to whole rupees)."""
    if base_price < 0 or tax_rate < 0 or handling_charge < 0:
        raise BusinessError("Price components cannot be negative.")
    tax = int((Decimal(base_price) * Decimal(tax_rate) / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return {"base_price": base_price, "tax_rate": tax_rate, "tax_amount": tax,
            "handling_charge": handling_charge, "total": base_price + tax + handling_charge}


def price_for(vehicle):
    tax_rate, handling = get_pricing_config()
    return calculate_price(vehicle.price, tax_rate, handling)


def update_pricing_config(tax_rate, handling_charge):
    """DFD 1.4 Update Tax Details (admin only - enforced in routes)."""
    if not 0 <= tax_rate <= 100:
        raise BusinessError("Tax rate must be between 0 and 100.")
    if handling_charge < 0:
        raise BusinessError("Handling charge cannot be negative.")
    set_setting("tax_rate", tax_rate)
    set_setting("handling_charge", handling_charge)
    db.session.commit()


# ----------------------------------------------------------------- accounts
def validate_registration(name, email, phone, password):
    errors = []
    if not name or not name.strip():
        errors.append("Name is required.")
    if not EMAIL_RE.match(email or ""):
        errors.append("Enter a valid email address.")
    digits = re.sub(r"[\s\-+]", "", phone or "")
    if not digits.isdigit() or not 10 <= len(digits) <= 15:
        errors.append("Enter a valid phone number (10-15 digits).")
    errors.extend(validate_password(password))
    return errors


def validate_password(password):
    errors = []
    if not password or len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        errors.append("Password must be at least 8 characters and contain a letter and a digit.")
    return errors


def register_user(name, email, phone, password, role="customer"):
    """REQ-REG-1/2: register with unique, well-formed email."""
    errors = validate_registration(name, email, phone, password)
    if errors:
        raise BusinessError(" ".join(errors))
    email = email.strip().lower()
    if User.query.filter(func.lower(User.email) == email).first():
        raise BusinessError("An account with this email already exists.")
    user = User(name=name.strip(), email=email, phone=phone.strip(), role=role)
    user.set_password(password)
    db.session.add(user)
    notify(email, "Welcome to the Vehicle Showroom", f"Hi {user.name}, your account has been created.")
    db.session.commit()
    return user


def authenticate(email, password):
    """REQ-REG-3/4: returns the user or None. Failure reason is deliberately generic."""
    user = User.query.filter(func.lower(User.email) == (email or "").strip().lower()).first()
    if user and user.is_active_account and user.check_password(password or ""):
        return user
    return None


def update_profile(user, name, phone):
    errors = validate_registration(name, user.email, phone, "placeholder1")
    if errors:
        raise BusinessError(" ".join(errors))
    user.name, user.phone = name.strip(), phone.strip()
    db.session.commit()


def change_password(user, old, new):
    if not user.check_password(old or ""):
        raise BusinessError("Current password is incorrect.")
    errs = validate_password(new)
    if errs:
        raise BusinessError(errs[0])
    user.set_password(new)
    db.session.commit()


def admin_reset_password(user_id):
    """DFD 1.3 Create New Password: admin issues a temporary password."""
    user = db.session.get(User, user_id)
    if not user:
        raise BusinessError("User not found.")
    temp = "Tmp" + secrets.token_hex(4) + "9"
    user.set_password(temp)
    notify(user.email, "Your password was reset", "An administrator reset your password. Please change it after logging in.")
    db.session.commit()
    return temp


def set_account_active(admin, user_id, active):
    user = db.session.get(User, user_id)
    if not user:
        raise BusinessError("User not found.")
    if user.id == admin.id and not active:
        raise BusinessError("You cannot deactivate your own account.")
    user.is_active_account = active
    db.session.commit()
    return user


# ----------------------------------------------------------------- vehicles
def search_vehicles(brand="", model="", min_price=None, max_price=None, category="", available_only=False):
    """REQ-SRCH-1/2: search by brand, model and price range (+ category filter)."""
    if min_price is not None and max_price is not None and min_price > max_price:
        raise BusinessError("Minimum price cannot be greater than maximum price.")
    q = Vehicle.query
    if brand:
        q = q.filter(Vehicle.brand.ilike(f"%{brand.strip()}%"))
    if model:
        q = q.filter(Vehicle.model.ilike(f"%{model.strip()}%"))
    if min_price is not None:
        q = q.filter(Vehicle.price >= min_price)
    if max_price is not None:
        q = q.filter(Vehicle.price <= max_price)
    if category:
        q = q.filter(Vehicle.category == category)
    if available_only:
        q = q.filter(Vehicle.status == "available")
    return q.order_by(Vehicle.brand, Vehicle.model, Vehicle.price).all()


def clean_vehicle_form(form, vehicle_id=None):
    """REQ-ADM-1/2: validate admin vehicle input, return a dict of clean fields."""
    errors = {}
    def req(name, label):
        val = (form.get(name) or "").strip()
        if not val:
            errors[name] = f"{label} is required."
        return val
    data = {
        "vehicle_number": req("vehicle_number", "Vehicle number").upper(),
        "brand": req("brand", "Brand"), "model": req("model", "Model"),
        "variant": (form.get("variant") or "").strip(),
        "fuel_type": (form.get("fuel_type") or "Petrol").strip(),
        "color": (form.get("color") or "").strip(),
        "description": (form.get("description") or "").strip(),
        "specs": (form.get("specs") or "").strip(),
    }
    data["category"] = form.get("category") or ""
    if data["category"] not in CATEGORIES:
        errors["category"] = "Choose a valid category."
    try:
        data["year"] = int(form.get("year", ""))
        if not 1990 <= data["year"] <= date.today().year + 1:
            errors["year"] = "Enter a realistic model year."
    except ValueError:
        errors["year"] = "Year must be a number."
    try:
        data["price"] = int(form.get("price", ""))
        if data["price"] <= 0:
            errors["price"] = "Price must be greater than zero."
    except ValueError:
        errors["price"] = "Price must be a whole number (rupees)."
    if data["vehicle_number"]:
        dup = Vehicle.query.filter(Vehicle.vehicle_number == data["vehicle_number"])
        if vehicle_id:
            dup = dup.filter(Vehicle.id != vehicle_id)
        if dup.first():
            errors["vehicle_number"] = "This vehicle number already exists."
    if errors:
        raise BusinessError(" ".join(errors.values()))
    return data


def create_vehicle(data, image_filename=None):
    v = Vehicle(**data, image_filename=image_filename, status="available")
    db.session.add(v)
    db.session.commit()
    return v


def update_vehicle(vehicle_id, data, image_filename=None):
    v = db.session.get(Vehicle, vehicle_id)
    if not v:
        raise BusinessError("Vehicle not found.")
    for k, val in data.items():
        setattr(v, k, val)
    if image_filename:
        v.image_filename = image_filename
    db.session.commit()
    return v


def delete_vehicle(vehicle_id):
    v = db.session.get(Vehicle, vehicle_id)
    if not v:
        raise BusinessError("Vehicle not found.")
    if v.sale:
        raise BusinessError("A sold vehicle cannot be deleted (it has a sales record).")
    if any(t.status == "booked" for t in v.test_drives):
        raise BusinessError("Cancel the active test-drive bookings before deleting this vehicle.")
    for t in v.test_drives:
        db.session.delete(t)
    db.session.delete(v)
    db.session.commit()


# ----------------------------------------------------------------- test drives
def _require_customer(user):
    if not user or not user.is_authenticated or user.role != "customer":
        raise BusinessError("Only logged-in customers can do this.")  # business rule 5.5


def _slot_end(start):
    return start + timedelta(minutes=current_app.config["TEST_DRIVE_MINUTES"])


def _validate_slot(start, now):
    cfg = current_app.config
    end = _slot_end(start)
    if start <= now:
        raise BusinessError("Choose a time in the future.")
    close = start.replace(hour=cfg["SHOWROOM_CLOSE_HOUR"], minute=0, second=0, microsecond=0)
    if start.hour < cfg["SHOWROOM_OPEN_HOUR"] or end > close:
        raise BusinessError(f"Test drives run between {cfg['SHOWROOM_OPEN_HOUR']}:00 and {cfg['SHOWROOM_CLOSE_HOUR']}:00.")
    return end


def has_overlap(vehicle_id, start, end, exclude_id=None, user_id=None):
    """REQ-TD-4: overlapping active bookings clash (same vehicle, or same customer)."""
    q = TestDrive.query.filter(TestDrive.status == "booked", TestDrive.start_time < end, TestDrive.end_time > start)
    q = q.filter(TestDrive.user_id == user_id) if user_id else q.filter(TestDrive.vehicle_id == vehicle_id)
    if exclude_id:
        q = q.filter(TestDrive.id != exclude_id)
    return db.session.query(q.exists()).scalar()


def book_test_drive(user, vehicle_id, start, now=None):
    """REQ-TD-1/3/4."""
    now = now or datetime.now()
    _require_customer(user)
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise BusinessError("Vehicle not found.")
    if not vehicle.is_available:
        raise BusinessError("This vehicle has been sold and is no longer available.")  # rule 5.5
    end = _validate_slot(start, now)
    if has_overlap(vehicle_id, start, end):
        raise BusinessError("That time slot is already booked for this vehicle.")
    if has_overlap(vehicle_id, start, end, user_id=user.id):
        raise BusinessError("You already have a test drive at that time.")
    td = TestDrive(user_id=user.id, vehicle_id=vehicle_id, start_time=start, end_time=end)
    db.session.add(td)
    notify(user.email, "Test drive confirmed",
           f"Your test drive for {vehicle.title} is confirmed for {start:%d %b %Y, %H:%M}.")
    db.session.commit()
    return td


def _own_booking(user, td_id):
    td = db.session.get(TestDrive, td_id)
    if not td or (td.user_id != user.id and not user.is_staff):
        raise BusinessError("Booking not found.")
    if td.status != "booked":
        raise BusinessError(f"This booking is already {td.status}.")
    return td


def reschedule_test_drive(user, td_id, new_start, now=None):
    """REQ-TD-2."""
    now = now or datetime.now()
    td = _own_booking(user, td_id)
    end = _validate_slot(new_start, now)
    if has_overlap(td.vehicle_id, new_start, end, exclude_id=td.id):
        raise BusinessError("That time slot is already booked for this vehicle.")
    if has_overlap(td.vehicle_id, new_start, end, exclude_id=td.id, user_id=td.user_id):
        raise BusinessError("You already have a test drive at that time.")
    td.start_time, td.end_time = new_start, end
    notify(td.customer.email, "Test drive rescheduled", f"New time: {new_start:%d %b %Y, %H:%M}.")
    db.session.commit()
    return td


def cancel_test_drive(user, td_id):
    """REQ-TD-2/3."""
    td = _own_booking(user, td_id)
    td.status = "cancelled"
    notify(td.customer.email, "Test drive cancelled", f"Your test drive on {td.start_time:%d %b %Y, %H:%M} was cancelled.")
    db.session.commit()
    return td


def complete_test_drive(staff, td_id):
    if staff.role not in ("admin", "sales"):
        raise BusinessError("Only sales staff or admins can complete a test drive.")
    td = _own_booking(staff, td_id)
    td.status = "completed"
    db.session.commit()
    return td


# ----------------------------------------------------------------- purchase
def purchase_vehicle(user, vehicle_id, card_number, expiry, cvv, now=None):
    """REQ-PUR-1..5. The availability claim is a single conditional UPDATE so two
    customers can never both buy the same unit (RMMM risk: stock mismatch)."""
    _require_customer(user)
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise BusinessError("Vehicle not found.")
    pricing = price_for(vehicle)
    claimed = db.session.execute(
        update(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.status == "available").values(status="sold"))
    if claimed.rowcount != 1:
        db.session.rollback()
        raise BusinessError("Sorry, this vehicle is no longer available.")
    result = payment.charge(card_number, expiry, cvv, pricing["total"], now=now)
    if not result.success:
        db.session.rollback()  # releases the claim
        raise BusinessError(result.message)
    sale = Sale(user_id=user.id, vehicle_id=vehicle_id, payment_ref=result.reference,
                card_last4=result.last4, **pricing)
    db.session.add(sale)
    db.session.flush()
    year = (now or datetime.now()).year
    invoice = Invoice(sale_id=sale.id, invoice_number=f"INV-{year}-{sale.id:05d}")
    db.session.add(invoice)
    # a sold vehicle can no longer be test driven: cancel pending bookings (rule 5.5)
    for td in TestDrive.query.filter_by(vehicle_id=vehicle_id, status="booked").all():
        td.status = "cancelled"
        notify(td.customer.email, "Test drive cancelled", f"{vehicle.title} has been sold, so your test drive was cancelled.")
    notify(user.email, f"Invoice {invoice.invoice_number}",
           f"Thank you for purchasing {vehicle.title}. Total paid: Rs {sale.total:,} (ref {sale.payment_ref}).")
    db.session.commit()
    return sale


# ----------------------------------------------------------------- service records
def create_service_record(staff, sale_id, description, service_date, cost=0):
    """REQ-SVC-2."""
    if staff.role not in ("service", "admin"):
        raise BusinessError("Only service staff can manage service records.")
    if not db.session.get(Sale, sale_id):
        raise BusinessError("Sale/vehicle not found.")
    if not (description or "").strip():
        raise BusinessError("Description is required.")
    if cost < 0:
        raise BusinessError("Cost cannot be negative.")
    rec = ServiceRecord(sale_id=sale_id, description=description.strip(), service_date=service_date,
                        cost=cost, created_by=staff.id)
    db.session.add(rec)
    db.session.commit()
    return rec


def update_service_record(staff, record_id, status, cost):
    if staff.role not in ("service", "admin"):
        raise BusinessError("Only service staff can manage service records.")
    rec = db.session.get(ServiceRecord, record_id)
    if not rec:
        raise BusinessError("Service record not found.")
    if status not in ("scheduled", "in_progress", "completed"):
        raise BusinessError("Invalid status.")
    if cost < 0:
        raise BusinessError("Cost cannot be negative.")
    rec.status, rec.cost = status, cost
    db.session.commit()
    return rec


# ----------------------------------------------------------------- reports
def sales_report():
    """REQ-SVC-3."""
    sales = Sale.query.order_by(Sale.created_at.desc()).all()
    by_brand = {}
    by_month = {}
    for s in sales:
        by_brand.setdefault(s.vehicle.brand, [0, 0])
        by_brand[s.vehicle.brand][0] += 1
        by_brand[s.vehicle.brand][1] += s.total
        key = s.created_at.strftime("%Y-%m")
        by_month.setdefault(key, [0, 0])
        by_month[key][0] += 1
        by_month[key][1] += s.total
    return {"count": len(sales), "revenue": sum(s.total for s in sales), "tax": sum(s.tax_amount for s in sales),
            "by_brand": sorted(by_brand.items()), "by_month": sorted(by_month.items()), "sales": sales}


def service_report():
    recs = ServiceRecord.query.all()
    counts = {"scheduled": 0, "in_progress": 0, "completed": 0}
    for r in recs:
        counts[r.status] = counts.get(r.status, 0) + 1
    return {"count": len(recs), "counts": counts, "cost": sum(r.cost or 0 for r in recs)}


def inventory_summary():
    rows = db.session.query(Vehicle.category, Vehicle.status, func.count(Vehicle.id)).group_by(Vehicle.category, Vehicle.status).all()
    out = {c: {"available": 0, "sold": 0} for c in CATEGORIES}
    for cat, status, n in rows:
        out.setdefault(cat, {"available": 0, "sold": 0})[status] = n
    return out
