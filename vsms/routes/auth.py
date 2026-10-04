from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .. import services
from ..services import BusinessError
from .helpers import safe_next

bp = Blueprint("auth", __name__)


def landing_for(user):
    return url_for("admin.dashboard") if user.role in ("admin", "sales") else (
        url_for("service.records") if user.role == "service" else url_for("customer.vehicles"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(landing_for(current_user))
    if request.method == "POST":
        f = request.form
        try:
            services.register_user(f.get("name"), f.get("email"), f.get("phone"), f.get("password"))
            flash("Account created - please log in.", "success")
            return redirect(url_for("auth.login"))
        except BusinessError as e:
            flash(str(e), "danger")
    return render_template("auth/register.html", form=request.form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(landing_for(current_user))
    if request.method == "POST":
        user = services.authenticate(request.form.get("email"), request.form.get("password"))
        if user:
            login_user(user)
            return redirect(safe_next(request.args.get("next")) or landing_for(user))
        flash("Invalid email or password.", "danger")  # REQ-REG-4
    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        try:
            if request.form.get("action") == "password":
                services.change_password(current_user, request.form.get("old"), request.form.get("new"))
                flash("Password changed.", "success")
            else:
                services.update_profile(current_user, request.form.get("name"), request.form.get("phone"))
                flash("Profile updated.", "success")
        except BusinessError as e:
            flash(str(e), "danger")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html")
