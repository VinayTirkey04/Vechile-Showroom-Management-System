"""Vehicle Showroom Management System (VSMS) - application factory."""
import logging
import os
import secrets

from flask import Flask, abort, render_template, request, session

from .config import Config
from .extensions import db, login_manager

__version__ = "1.0.0"


def indian_grouping(n: int) -> str:
    """1490000 -> '14,90,000' (lakh/crore digit grouping)."""
    sign, digits = ("-" if n < 0 else ""), str(abs(n))
    if len(digits) <= 3:
        return sign + digits
    head, tail = digits[:-3], digits[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return sign + ",".join(parts + [tail])


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    logging.basicConfig(level=logging.INFO)

    db.init_app(app)
    login_manager.init_app(app)

    from .routes import admin, auth, customer, service
    for bp in (auth.bp, customer.bp, admin.bp, service.bp):
        app.register_blueprint(bp)

    # ---- CSRF protection for every state-changing request (security requirement 5.3)
    def csrf_token():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_hex(16)
        return session["_csrf"]

    @app.before_request
    def check_csrf():
        if app.config["CSRF_ENABLED"] and request.method in ("POST", "PUT", "DELETE", "PATCH"):
            sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
            if not sent or not secrets.compare_digest(sent, session.get("_csrf", "")):
                abort(400, "Invalid or missing CSRF token.")

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'"
        return resp

    @app.template_filter("inr")
    def inr(value):
        return "₹" + indian_grouping(int(value))

    app.jinja_env.globals["csrf_token"] = csrf_token  # global so imported macros can use it

    for code, title in ((400, "Bad request"), (403, "Access denied"), (404, "Page not found"), (413, "File too large")):
        app.register_error_handler(code, lambda e, code=code, title=title: (
            render_template("error.html", code=code, title=title, message=getattr(e, "description", "")), code))

    from .seed import register_cli
    register_cli(app)

    with app.app_context():
        db.create_all()
    return app
