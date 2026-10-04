"""Application configuration.

The SRS (section 2.4) names MySQL as the production database. SQLAlchemy keeps
the code database-agnostic, so switch by setting DATABASE_URL, e.g.
    mysql+pymysql://user:pass@localhost/vsms
SQLite is the zero-setup default so the project runs with one command.
"""
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "vsms.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "instance", "uploads")
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB image uploads
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"  # set COOKIE_SECURE=1 behind HTTPS
    CSRF_ENABLED = True
    # Showroom rules
    SHOWROOM_OPEN_HOUR = 9
    SHOWROOM_CLOSE_HOUR = 18
    TEST_DRIVE_MINUTES = 60
    DEFAULT_TAX_RATE = 18  # percent, editable by admin (DFD 1.4 Update Tax Details)
    DEFAULT_HANDLING_CHARGE = 15000


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    CSRF_ENABLED = False
    SECRET_KEY = "test"
    SERVER_NAME = None
