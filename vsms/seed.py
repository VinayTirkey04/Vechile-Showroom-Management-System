"""Demo data: `flask --app run seed`."""
import click

from .extensions import db
from .models import User, Vehicle

DEMO_USERS = [
    ("Admin User", "admin@showroom.test", "9000000001", "Admin@1234", "admin"),
    ("Sales Staff", "sales@showroom.test", "9000000002", "Sales@1234", "sales"),
    ("Service Staff", "service@showroom.test", "9000000003", "Service@1234", "service"),
    ("Demo Customer", "customer@showroom.test", "9000000004", "Customer@1234", "customer"),
]

DEMO_VEHICLES = [
    # number, brand, model, variant, category, fuel, color, year, price
    ("MH01AB1001", "Maruti Suzuki", "Swift", "VXi", "Hatchback", "Petrol", "Red", 2026, 650000),
    ("MH01AB1002", "Hyundai", "i20", "Sportz", "Hatchback", "Petrol", "White", 2026, 845000),
    ("MH01AB1003", "Honda", "City", "ZX", "Sedan", "Petrol", "Silver", 2026, 1450000),
    ("MH01AB1004", "Skoda", "Slavia", "Style", "Sedan", "Petrol", "Blue", 2025, 1400000),
    ("MH01AB1005", "Tata", "Nexon", "Creative", "SUV", "Diesel", "Grey", 2026, 1250000),
    ("MH01AB1006", "Mahindra", "XUV700", "AX7", "SUV", "Diesel", "Black", 2026, 2200000),
    ("MH01AB1007", "Hyundai", "Creta", "SX", "SUV", "Petrol", "White", 2026, 1650000),
    ("MH01AB1008", "Tata", "Nexon EV", "Empowered", "EV", "Electric", "Teal", 2026, 1700000),
    ("MH01AB1009", "MG", "ZS EV", "Exclusive", "EV", "Electric", "Green", 2025, 2100000),
    ("MH01AB1010", "Maruti Suzuki", "Baleno", "Delta", "Hatchback", "Petrol", "Orange", 2026, 780000),
]


def seed_demo():
    created = 0
    for name, email, phone, pw, role in DEMO_USERS:
        if not User.query.filter_by(email=email).first():
            u = User(name=name, email=email, phone=phone, role=role)
            u.set_password(pw)
            db.session.add(u)
            created += 1
    for num, brand, model, variant, cat, fuel, color, year, price in DEMO_VEHICLES:
        if not Vehicle.query.filter_by(vehicle_number=num).first():
            db.session.add(Vehicle(vehicle_number=num, brand=brand, model=model, variant=variant, category=cat,
                                   fuel_type=fuel, color=color, year=year, price=price,
                                   description=f"{brand} {model} {variant} - showroom fresh, single unit.",
                                   specs=f"Fuel: {fuel}\nBody: {cat}\nColour: {color}"))
            created += 1
    db.session.commit()
    return created


def register_cli(app):
    @app.cli.command("seed")
    def seed_command():
        """Load demo users and vehicles."""
        click.echo(f"Seeded {seed_demo()} records.")
