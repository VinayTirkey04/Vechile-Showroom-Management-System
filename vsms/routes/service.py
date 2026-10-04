from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .. import services
from ..models import Sale, ServiceRecord
from ..services import BusinessError
from .helpers import parse_int, roles_required

bp = Blueprint("service", __name__, url_prefix="/service")


@bp.route("/", methods=["GET", "POST"])
@roles_required("service", "admin")
def records():
    """REQ-SVC-2: service staff create and update service records."""
    if request.method == "POST":
        try:
            sale_id = parse_int(request.form.get("sale_id"))
            when = datetime.strptime(request.form.get("service_date", ""), "%Y-%m-%d").date()
            services.create_service_record(current_user, sale_id, request.form.get("description"), when,
                                           parse_int(request.form.get("cost")) or 0)
            flash("Service record created.", "success")
        except ValueError:
            flash("Pick a valid service date.", "danger")
        except BusinessError as e:
            flash(str(e), "danger")
        return redirect(url_for("service.records"))
    recs = ServiceRecord.query.order_by(ServiceRecord.service_date.desc()).all()
    return render_template("staff/service.html", records=recs, sales=Sale.query.all(), today=date.today())


@bp.route("/<int:record_id>/update", methods=["POST"])
@roles_required("service", "admin")
def update(record_id):
    try:
        services.update_service_record(current_user, record_id, request.form.get("status"),
                                       parse_int(request.form.get("cost")) or 0)
        flash("Service record updated.", "success")
    except BusinessError as e:
        flash(str(e), "danger")
    return redirect(url_for("service.records"))
