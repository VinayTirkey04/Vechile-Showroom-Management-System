import os
import secrets
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse

from flask import abort, current_app, flash
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

ALLOWED_IMAGES = {"png", "jpg", "jpeg", "webp"}


def roles_required(*roles):
    """Role-based access control (SRS 5.3 / REQ-ADM-4)."""
    def deco(fn):
        @wraps(fn)
        @login_required
        def wrapper(*a, **kw):
            if current_user.role not in roles:
                abort(403, "You do not have permission to view this page.")
            return fn(*a, **kw)
        return wrapper
    return deco


def parse_int(value):
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def parse_datetime(value):
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except (ValueError, TypeError):
        return None


def safe_next(target):
    """Prevent open redirects after login."""
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.netloc or parsed.scheme or not target.startswith("/") or target.startswith("//"):
        return None
    return target


def save_image(file_storage):
    """DFD 2.0 Uploading Image: validate type, store under a random name."""
    if not file_storage or not file_storage.filename:
        return None
    name = secure_filename(file_storage.filename)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_IMAGES:
        flash("Image must be PNG, JPG or WEBP - the image was ignored.", "warning")
        return None
    filename = f"{secrets.token_hex(8)}.{ext}"
    file_storage.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
    return filename
