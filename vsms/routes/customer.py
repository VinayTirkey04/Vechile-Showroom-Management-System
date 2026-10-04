from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, send_from_directory, url_for)
from flask_login import current_user, login_required

from .. import services
from ..extensions import db
from ..models import CATEGORIES, Notification, Sale, TestDrive, Vehicle
from ..services import BusinessError
from .helpers import parse_datetime, parse_int, roles_required

bp = Blueprint("customer", __name__)


@bp.route("/")
def home():
    return redirect(url_for("customer.vehicles"))


@bp.route("/vehicles")
def vehicles():
    """REQ-SRCH-1/2: search by brand, model, price range; availability shown per result."""
    a = request.args
    min_p, max_p = parse_int(a.get("min_price")), parse_int(a.get("max_price"))
    results, error = [], None
    try:
        results = services.search_vehicles(a.get("brand", ""), a.get("model", ""), min_p, max_p,
                                           a.get("category", ""), a.get("available") == "1")
    except BusinessError as e:
        error = str(e)
        flash(error, "danger")
    return render_template("customer/vehicles.html", vehicles=results, categories=CATEGORIES, args=a)


@bp.route("/vehicles/<int:vehicle_id>")
def vehicle_detail(vehicle_id):
    """REQ-SRCH-3: detailed vehicle information."""
    v = db.session.get(Vehicle, vehicle_id) or abort(404)
    return render_template("customer/vehicle_detail.html", v=v, price=services.price_for(v),
                           open_hour=current_app.config["SHOWROOM_OPEN_HOUR"],
                           close_hour=current_app.config["SHOWROOM_CLOSE_HOUR"])


@bp.route("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@bp.route("/vehicles/<int:vehicle_id>/test-drive", methods=["POST"])
@roles_required("customer")
def book_test_drive(vehicle_id):
    start = parse_datetime(request.form.get("start_time"))
    if not start:
        flash("Pick a valid date and time.", "danger")
    else:
        try:
            td = services.book_test_drive(current_user, vehicle_id, start)
            flash(f"Test drive booked for {td.start_time:%d %b %Y, %H:%M}. A confirmation email was sent.", "success")
            return redirect(url_for("customer.bookings"))
        except BusinessError as e:
            flash(str(e), "danger")
    return redirect(url_for("customer.vehicle_detail", vehicle_id=vehicle_id))


@bp.route("/vehicles/<int:vehicle_id>/purchase", methods=["GET", "POST"])
@roles_required("customer")
def purchase(vehicle_id):
    v = db.session.get(Vehicle, vehicle_id) or abort(404)
    if request.method == "POST":
        f = request.form
        try:
            sale = services.purchase_vehicle(current_user, vehicle_id, f.get("card_number"), f.get("expiry"), f.get("cvv"))
            flash("Payment successful! Your invoice has been generated and emailed.", "success")
            return redirect(url_for("customer.invoice", sale_id=sale.id))
        except BusinessError as e:
            flash(str(e), "danger")
            db.session.refresh(v)
    return render_template("customer/purchase.html", v=v, price=services.price_for(v))


@bp.route("/my/bookings")
@roles_required("customer")
def bookings():
    """REQ-HIST-1."""
    drives = TestDrive.query.filter_by(user_id=current_user.id).order_by(TestDrive.start_time.desc()).all()
    return render_template("customer/bookings.html", drives=drives)


@bp.route("/my/bookings/<int:td_id>/reschedule", methods=["POST"])
@roles_required("customer")
def reschedule(td_id):
    start = parse_datetime(request.form.get("start_time"))
    try:
        if not start:
            raise BusinessError("Pick a valid date and time.")
        services.reschedule_test_drive(current_user, td_id, start)
        flash("Test drive rescheduled.", "success")
    except BusinessError as e:
        flash(str(e), "danger")
    return redirect(url_for("customer.bookings"))


@bp.route("/my/bookings/<int:td_id>/cancel", methods=["POST"])
@roles_required("customer")
def cancel(td_id):
    try:
        services.cancel_test_drive(current_user, td_id)
        flash("Test drive cancelled.", "info")
    except BusinessError as e:
        flash(str(e), "danger")
    return redirect(url_for("customer.bookings"))


@bp.route("/my/history")
@roles_required("customer")
def history():
    """REQ-HIST-2: purchases and service history."""
    sales = Sale.query.filter_by(user_id=current_user.id).order_by(Sale.created_at.desc()).all()
    return render_template("customer/history.html", sales=sales)


@bp.route("/invoice/<int:sale_id>")
@login_required
def invoice(sale_id):
    sale = db.session.get(Sale, sale_id) or abort(404)
    if sale.user_id != current_user.id and not current_user.is_staff:
        abort(403, "This invoice belongs to another customer.")
    return render_template("customer/invoice.html", sale=sale)


@bp.route("/my/emails")
@roles_required("customer")
def emails():
    mails = Notification.query.filter_by(to_email=current_user.email).order_by(Notification.id.desc()).all()
    return render_template("customer/emails.html", mails=mails)
