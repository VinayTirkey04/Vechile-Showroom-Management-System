import pytest

from vsms import create_app
from vsms.config import TestConfig
from vsms.extensions import db
from vsms.models import User, Vehicle


class Cfg(TestConfig):
    pass


@pytest.fixture()
def app(tmp_path):
    Cfg.UPLOAD_FOLDER = str(tmp_path)
    app = create_app(Cfg)
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(email="cust@test.com", role="customer", password="Passw0rd1", name="Test User", phone="9876543210"):
    u = User(name=name, email=email, phone=phone, role=role)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return u


def make_vehicle(number="MH01TEST01", brand="Hyundai", model="Creta", category="SUV", price=1000000,
                 status="available", year=2026, color="White"):
    v = Vehicle(vehicle_number=number, brand=brand, model=model, variant="SX", category=category,
                fuel_type="Petrol", color=color, year=year, price=price, status=status)
    db.session.add(v)
    db.session.commit()
    return v


@pytest.fixture()
def customer(app):
    return make_user()


@pytest.fixture()
def admin(app):
    return make_user("admin@test.com", "admin", "Admin@1234", "Admin")


@pytest.fixture()
def vehicle(app):
    return make_vehicle()


def login(client, email, password):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)
