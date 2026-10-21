"""Placements. Listings are shared; application tracking is private to each student.
Listings entered by students are NEVER marked verified automatically."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from helpers import clean, form_values, is_http_url, parse_date
from models import PlacementOpportunity, StudentApplication
from utils import today_local

placements_bp = Blueprint("placements", __name__, url_prefix="/placements")

APP_STATUSES = ["Interested", "Applied", "Assessment", "Interview", "Selected", "Rejected"]
EMPLOYMENT = ["Full-time", "Internship", "Contract"]
FIELDS = ("company_name", "job_title", "description", "eligibility", "min_cgpa", "eligible_branches",
          "required_skills", "salary_package", "deadline", "application_url", "location", "employment_type")


def validate(form):
    errors = []
    if not form["company_name"]:
        errors.append("Company name is required.")
    if not form["job_title"]:
        errors.append("Job role is required.")
    cgpa = None
    if form["min_cgpa"]:
        try:
            cgpa = float(form["min_cgpa"])
            if not 0 <= cgpa <= 10:
                raise ValueError
        except ValueError:
            errors.append("Minimum CGPA must be a number between 0 and 10.")
    deadline = parse_date(form["deadline"]) if form["deadline"] else None
    if form["deadline"] and deadline is None:
        errors.append("Application deadline is not valid.")
    if form["application_url"] and not is_http_url(form["application_url"]):
        errors.append("Application URL must start with http:// or https://")
    data = {
        "company_name": form["company_name"][:150], "job_title": form["job_title"][:150],
        "description": form["description"] or None, "eligibility": form["eligibility"] or None,
        "min_cgpa": cgpa, "eligible_branches": form["eligible_branches"][:200] or None,
        "required_skills": form["required_skills"][:300] or None,
        "salary_package": form["salary_package"][:60] or None, "deadline": deadline,
        "application_url": form["application_url"] or None, "location": form["location"][:100] or None,
        "employment_type": form["employment_type"] if form["employment_type"] in EMPLOYMENT else None,
    }
    return data, errors


def my_application(opportunity_id):
    return StudentApplication.query.filter_by(user_id=current_user.id, opportunity_id=opportunity_id).first()


@placements_bp.route("/")
@login_required
def index():
    q = clean(request.args.get("q"))
    show = request.args.get("show", "open")          # open / expired / all / tracked
    status = clean(request.args.get("status"))
    today = today_local()

    query = PlacementOpportunity.query
    if show == "tracked":
        query = query.join(StudentApplication, StudentApplication.opportunity_id == PlacementOpportunity.id) \
                     .filter(StudentApplication.user_id == current_user.id)
        if status in APP_STATUSES:
            query = query.filter(StudentApplication.status == status)
    elif show == "expired":
        query = query.filter(PlacementOpportunity.deadline < today)
    elif show == "all":
        pass
    else:
        show = "open"
        query = query.filter(db.or_(PlacementOpportunity.deadline.is_(None), PlacementOpportunity.deadline >= today))
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(PlacementOpportunity.company_name.ilike(like),
                                    PlacementOpportunity.job_title.ilike(like),
                                    PlacementOpportunity.required_skills.ilike(like)))
    items = query.order_by(PlacementOpportunity.deadline.is_(None), PlacementOpportunity.deadline).all()

    mine = {a.opportunity_id: a for a in StudentApplication.query.filter_by(user_id=current_user.id).all()}
    return render_template("placements/index.html", items=items, mine=mine, q=q, show=show, status=status,
                           statuses=APP_STATUSES)


def _form_template(form, item, code=200):
    return render_template("placements/form.html", form=form, item=item, employment=EMPLOYMENT), code


@placements_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = {"employment_type": "Full-time"}
    if request.method == "POST":
        form = form_values(*FIELDS)
        data, errors = validate(form)
        if errors:
            for message in errors:
                flash(message, "danger")
            return _form_template(form, None, 400)
        db.session.add(PlacementOpportunity(created_by=current_user.id, is_verified=False, **data))
        db.session.commit()
        flash("Opportunity added (marked unverified).", "success")
        return redirect(url_for("placements.index"))
    return _form_template(form, None)


@placements_bp.route("/<int:item_id>")
@login_required
def detail(item_id):
    item = db.session.get(PlacementOpportunity, item_id) or abort(404)
    return render_template("placements/detail.html", item=item, app=my_application(item.id),
                           statuses=APP_STATUSES, can_edit=item.created_by == current_user.id)


def _own_listing(item_id):
    """Only the student who created a listing may edit or delete it."""
    item = db.session.get(PlacementOpportunity, item_id)
    if item is None or item.created_by != current_user.id:
        abort(404)
    return item


@placements_bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit(item_id):
    item = _own_listing(item_id)
    if request.method == "POST":
        form = form_values(*FIELDS)
        data, errors = validate(form)
        if errors:
            for message in errors:
                flash(message, "danger")
            return _form_template(form, item, 400)
        for key, value in data.items():
            setattr(item, key, value)
        db.session.commit()
        flash("Opportunity updated.", "success")
        return redirect(url_for("placements.detail", item_id=item.id))
    form = {k: ("" if getattr(item, k) is None else str(getattr(item, k))) for k in FIELDS}
    return _form_template(form, item)


@placements_bp.route("/<int:item_id>/delete", methods=["POST"])
@login_required
def delete(item_id):
    item = _own_listing(item_id)
    StudentApplication.query.filter_by(opportunity_id=item.id).delete()
    db.session.delete(item)
    db.session.commit()
    flash("Opportunity deleted.", "success")
    return redirect(url_for("placements.index"))


@placements_bp.route("/<int:item_id>/track", methods=["POST"])
@login_required
def track(item_id):
    """Save or update the logged-in student's own application status for a listing."""
    item = db.session.get(PlacementOpportunity, item_id) or abort(404)
    status = clean(request.form.get("status"))
    if status not in APP_STATUSES:
        flash("Please choose a valid status.", "danger")
        return redirect(url_for("placements.detail", item_id=item.id))
    app_row = my_application(item.id)
    if app_row is None:
        app_row = StudentApplication(user_id=current_user.id, opportunity_id=item.id)
        db.session.add(app_row)
    app_row.status = status
    app_row.notes = clean(request.form.get("notes")) or None
    db.session.commit()
    flash(f"Application status saved: {status}.", "success")
    return redirect(url_for("placements.detail", item_id=item.id))


@placements_bp.route("/<int:item_id>/untrack", methods=["POST"])
@login_required
def untrack(item_id):
    app_row = my_application(item_id)
    if app_row:
        db.session.delete(app_row)
        db.session.commit()
        flash("Stopped tracking this opportunity.", "success")
    return redirect(url_for("placements.detail", item_id=item_id))
