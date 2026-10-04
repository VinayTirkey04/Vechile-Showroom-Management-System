"""Non-functional tests - performance (SRS 5.1) and concurrent purchase safety (SRS 5.2 / RMMM risk 204)."""
import threading
import time

from vsms import create_app, services
from vsms.config import TestConfig
from vsms.extensions import db
from vsms.models import Sale, User, Vehicle


def test_search_returns_within_three_seconds_on_large_inventory(app):
    """SRS 5.1: results within 3 s under normal load - checked with 3,000 vehicles."""
    db.session.bulk_save_objects([
        Vehicle(vehicle_number=f"PERF{i:05d}", brand=f"Brand{i % 25}", model=f"Model{i % 90}", category="SUV",
                fuel_type="Petrol", color="White", year=2026, price=500000 + i * 100)
        for i in range(3000)])
    db.session.commit()
    start = time.perf_counter()
    results = services.search_vehicles(brand="brand7", min_price=600000, max_price=700000)
    elapsed = time.perf_counter() - start
    assert results and elapsed < 3.0
    assert elapsed < 0.5, f"search took {elapsed:.3f}s"   # comfortable margin on any dev machine


def test_two_customers_racing_for_one_vehicle_only_one_wins(tmp_path):
    """The conditional UPDATE guarantees a single sale even when two requests collide."""
    class FileDb(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'race.db'}"
        UPLOAD_FOLDER = str(tmp_path)
    app = create_app(FileDb)
    with app.app_context():
        for i in (1, 2, 3, 4):
            u = User(name=f"U{i}", email=f"u{i}@t.com", phone="9876543210", role="customer")
            u.set_password("Passw0rd1")
            db.session.add(u)
        db.session.add(Vehicle(vehicle_number="RACE1", brand="A", model="B", category="SUV", year=2026, price=100000))
        db.session.commit()
        vehicle_id = Vehicle.query.one().id
        user_ids = [u.id for u in User.query.all()]

    outcomes, barrier = [], threading.Barrier(len(user_ids))

    def buy(uid):
        with app.app_context():
            user = db.session.get(User, uid)
            barrier.wait()
            try:
                services.purchase_vehicle(user, vehicle_id, "4242424242424242", "12/30", "123")
                outcomes.append("sold")
            except services.BusinessError:
                outcomes.append("rejected")
            finally:
                db.session.remove()

    threads = [threading.Thread(target=buy, args=(uid,)) for uid in user_ids]
    [t.start() for t in threads]
    [t.join() for t in threads]
    with app.app_context():
        assert outcomes.count("sold") == 1 and outcomes.count("rejected") == len(user_ids) - 1
        assert Sale.query.count() == 1
        db.session.remove()
        db.engine.dispose()
