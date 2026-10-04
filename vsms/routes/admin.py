import csv
import io

from flask import (Blueprint, Response, abort, flash, redirect, render_template, request, url_for)
from flask_login import current_user

from .. import services
from ..extensions import db
from ..models import CATEGORIES, Notification, Sale, TestDrive, User, Vehicle
from ..services import BusinessError
from .helpers import parse_int, roles_required, save_image

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@roles_required("admin", "sales")
def dashboard():
    report = services.sales_report()
    upcoming = (TestDrive.query.filter_by(status="booked").order_by(TestDrive.start_time).limit(8).all())
    return render_template("admin/dashboard.html", inv=services.inventory_summary(), report=report,
                           upcoming=upcoming, service=services.service_report())


# ------------------------------------------------------------------ inventory (REQ-ADM-1/2/4)
@bp.route("/vehicles")
@roles_required("admin")
def vehicles():
    items = Vehicle.query.order_by(Vehicle.id.desc()).all()
    return render_template("admin/vehicles.html", vehicles=items)


@bp.route("/vehicles/new", methods=["GET", "POST"])
@roles_required("admin")
def vehicle_new():
    if request.method == "POST":
        try:
            data = services.clean_vehicle_form(request.form)
            services.create_vehicle(data, save_image(request.files.get("image")))
            flash("Vehicle added to inventory.", "success")
            return redirect(url_for("admin.vehicles"))
        except BusinessError as e:
            flash(str(e), "danger")
    return render_template("admin/vehicle_form.html", v=None, form=request.form, categories=CATEGORIES)


@bp.route("/vehicles/<int:vehicle_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def vehicle_edit(vehicle_id):
    v = db.session.get(Vehicle, vehicle_id) or abort(404)
    if request.method == "POST":
        try:
            data = services.clean_vehicle_form(request.form, vehicle_id)
            services.update_vehicle(vehicle_id, data, save_image(request.files.get("image")))
            flash("Vehicle updated.", "success")
            return redirect(url_for("admin.vehicles"))
        except BusinessError as e:
            flash(str(e), "danger")
    return render_template("admin/vehicle_form.html", v=v, form=request.form or v.__dict__, categories=CATEGORIES)


@bp.route("/vehicles/<int:vehicle_id>/delete", methods=["POST"])
@roles_required("admin")
def vehicle_delete(vehicle_id):
    try:
        services.delete_vehicle(vehicle_id)
        flash("Vehicle deleted.", "info")
    except BusinessError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.vehicles"))


# ------------------------------------------------------------------ customers / users (REQ-ADM-3/4)
@bp.route("/customers")
@roles_required("admin")
def customers():
    q = (request.args.get("q") or "").strip()
    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(User.name.ilike(like) | User.email.ilike(like) | User.phone.ilike(like))
    return render_template("admin/customers.html", users=query.order_by(User.role, User.name).all(), q=q)


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@roles_required("admin")
def user_toggle(user_id):
    user = db.session.get(User, user_id) or abort(404)
    try:
        services.set_account_active(current_user, user_id, not user.is_active_account)
        flash(f"Account {'activated' if user.is_active_account else 'deactivated'}.", "info")
    except BusinessError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.customers"))


@bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@roles_required("admin")
def user_reset(user_id):
    try:
        temp = services.admin_reset_password(user_id)
        flash(f"Temporary password: {temp} (shown once - share it securely).", "warning")
    except BusinessError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.customers"))


@bp.route("/staff/new", methods=["GET", "POST"])
@roles_required("admin")
def staff_new():
    if request.method == "POST":
        f = request.form
        role = f.get("role")
        try:
            if role not in ("admin", "sales", "service"):
                raise BusinessError("Choose a staff role.")
            services.register_user(f.get("name"), f.get("email"), f.get("phone"), f.get("password"), role=role)
            flash("Staff account created.", "success")
            return redirect(url_for("admin.customers"))
        except BusinessError as e:
            flash(str(e), "danger")
    return render_template("admin/staff_form.html", form=request.form)


# ------------------------------------------------------------------ test drives & sales
@bp.route("/test-drives")
@roles_required("admin", "sales")
def test_drives():
    drives = TestDrive.query.order_by(TestDrive.start_time.desc()).all()
    return render_template("admin/test_drives.html", drives=drives)


@bp.route("/test-drives/<int:td_id>/<action>", methods=["POST"])
@roles_required("admin", "sales")
def test_drive_action(td_id, action):
    try:
        if action == "complete":
            services.complete_test_drive(current_user, td_id)
        elif action == "cancel":
            services.cancel_test_drive(current_user, td_id)
        else:
            abort(404)
        flash("Booking updated.", "success")
    except BusinessError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.test_drives"))


@bp.route("/sales")
@roles_required("admin", "sales")
def sales():
    return render_template("admin/sales.html", report=services.sales_report())


@bp.route("/sales.csv")
@roles_required("admin")
def sales_csv():
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["invoice", "date", "customer", "vehicle", "base_price", "tax", "handling", "total", "payment_ref"])
    for s in services.sales_report()["sales"]:
        w.writerow([s.invoice.invoice_number, s.created_at.date(), s.customer.name, s.vehicle.title,
                    s.base_price, s.tax_amount, s.handling_charge, s.total, s.payment_ref])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=sales.csv"})


@bp.route("/settings", methods=["GET", "POST"])
@roles_required("admin")
def settings():
    if request.method == "POST":
        rate, handling = parse_int(request.form.get("tax_rate")), parse_int(request.form.get("handling_charge"))
        try:
            if rate is None or handling is None:
                raise BusinessError("Enter whole numbers for both fields.")
            services.update_pricing_config(rate, handling)
            flash("Pricing configuration updated.", "success")
        except BusinessError as e:
            flash(str(e), "danger")
        return redirect(url_for("admin.settings"))
    rate, handling = services.get_pricing_config()
    return render_template("admin/settings.html", rate=rate, handling=handling)


@bp.route("/outbox")
@roles_required("admin")
def outbox():
    mails = Notification.query.order_by(Notification.id.desc()).limit(100).all()
    return render_template("admin/outbox.html", mails=mails)
