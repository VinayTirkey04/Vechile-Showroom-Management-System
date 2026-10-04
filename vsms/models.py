"""Database models (ER design from Week 2 of the development plan).

Entities: User(role), Vehicle, TestDrive, Sale, Invoice, ServiceRecord,
Setting (tax/handling configuration), Notification (e-mail outbox).
"""
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

ROLES = ("customer", "admin", "sales", "service")
CATEGORIES = ("Hatchback", "Sedan", "SUV", "EV")  # categories named in the RMMM risk sheet
VEHICLE_STATUSES = ("available", "sold")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    test_drives = db.relationship("TestDrive", backref="customer", lazy=True)
    sales = db.relationship("Sale", backref="customer", lazy=True)

    # REQ security 5.3: salted hash, never plain text
    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_active(self):  # Flask-Login hook: deactivated accounts cannot log in
        return self.is_active_account

    @property
    def is_staff(self):
        return self.role in ("admin", "sales", "service")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Vehicle(db.Model):
    """One physical vehicle unit (identified by vehicle_number / VIN)."""
    __tablename__ = "vehicles"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_number = db.Column(db.String(30), unique=True, nullable=False)
    brand = db.Column(db.String(50), nullable=False, index=True)
    model = db.Column(db.String(50), nullable=False, index=True)
    variant = db.Column(db.String(50), default="")
    category = db.Column(db.String(20), nullable=False)
    fuel_type = db.Column(db.String(20), default="Petrol")
    color = db.Column(db.String(30), default="")
    year = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Integer, nullable=False)  # whole rupees
    description = db.Column(db.Text, default="")
    specs = db.Column(db.Text, default="")
    image_filename = db.Column(db.String(120))
    status = db.Column(db.String(20), nullable=False, default="available", index=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    test_drives = db.relationship("TestDrive", backref="vehicle", lazy=True)
    sale = db.relationship("Sale", backref="vehicle", uselist=False)

    @property
    def is_available(self):
        return self.status == "available"

    @property
    def title(self):
        return f"{self.year} {self.brand} {self.model} {self.variant}".strip()


class TestDrive(db.Model):
    __tablename__ = "test_drives"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="booked")  # booked/cancelled/completed
    created_at = db.Column(db.DateTime, default=datetime.now)


class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), unique=True, nullable=False)
    base_price = db.Column(db.Integer, nullable=False)
    tax_rate = db.Column(db.Integer, nullable=False)
    tax_amount = db.Column(db.Integer, nullable=False)
    handling_charge = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    payment_ref = db.Column(db.String(40), nullable=False)
    card_last4 = db.Column(db.String(4), nullable=False)  # only last 4 digits are ever stored
    created_at = db.Column(db.DateTime, default=datetime.now)

    invoice = db.relationship("Invoice", backref="sale", uselist=False)
    service_records = db.relationship("ServiceRecord", backref="sale", lazy=True)


class Invoice(db.Model):
    __tablename__ = "invoices"
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), unique=True, nullable=False)
    invoice_number = db.Column(db.String(30), unique=True, nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.now)


class ServiceRecord(db.Model):
    __tablename__ = "service_records"
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    description = db.Column(db.String(300), nullable=False)
    service_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="scheduled")  # scheduled/in_progress/completed
    cost = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.now)


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(100), nullable=False)


class Notification(db.Model):
    """E-mail outbox. Every message the system sends is recorded here; plug an SMTP/API sender into services.notify() to deliver them."""
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    to_email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
