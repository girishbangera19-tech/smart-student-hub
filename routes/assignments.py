"""Assignments: CRUD, mark complete, search / filter / sort."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from helpers import clean, form_values, owned_or_404, parse_date, parse_datetime
from models import Assignment
from utils import now_local

assignments_bp = Blueprint("assignments", __name__, url_prefix="/assignments")

PRIORITIES = ["Low", "Medium", "High"]
STATUSES = ["Pending", "In Progress", "Completed"]
FIELDS = ("title", "subject_name", "subject_code", "description", "assigned_date",
          "deadline", "priority", "status")


def validate(form):
    errors = []
    if not form["title"]:
        errors.append("Title is required.")
    if not form["subject_name"]:
        errors.append("Subject is required.")
    deadline = parse_datetime(form["deadline"])
    if deadline is None:
        errors.append("Please enter a valid due date and time.")
    assigned = parse_date(form["assigned_date"]) if form["assigned_date"] else None
    if form["assigned_date"] and assigned is None:
        errors.append("Assigned date is not valid.")
    if form["priority"] not in PRIORITIES:
        errors.append("Please choose a priority.")
    if form["status"] not in STATUSES:
        errors.append("Please choose a status.")
    data = {
        "title": form["title"][:150], "subject_name": form["subject_name"][:120],
        "subject_code": form["subject_code"][:20] or None, "description": form["description"] or None,
        "assigned_date": assigned, "deadline": deadline, "priority": form["priority"], "status": form["status"],
    }
    return data, errors


@assignments_bp.route("/")
@login_required
def index():
    q = clean(request.args.get("q"))
    subject = clean(request.args.get("subject"))
    priority = clean(request.args.get("priority"))
    status = clean(request.args.get("status"))
    sort = request.args.get("sort", "deadline")

    base = Assignment.query.filter_by(user_id=current_user.id)
    query = base
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Assignment.title.ilike(like), Assignment.subject_name.ilike(like),
                                    Assignment.description.ilike(like)))
    if subject:
        query = query.filter(Assignment.subject_name == subject)
    if priority in PRIORITIES:
        query = query.filter(Assignment.priority == priority)
    if status == "Overdue":  # a computed state: not completed and deadline has passed
        query = query.filter(Assignment.status != "Completed", Assignment.deadline < now_local())
    elif status in STATUSES:
        query = query.filter(Assignment.status == status)
    query = query.order_by(Assignment.deadline.desc() if sort == "deadline_desc" else Assignment.deadline)

    subjects = [s for (s,) in db.session.query(Assignment.subject_name)
                .filter_by(user_id=current_user.id).distinct().order_by(Assignment.subject_name)]
    return render_template("assignments/index.html", assignments=query.all(), subjects=subjects,
                           q=q, subject=subject, priority=priority, status=status, sort=sort,
                           priorities=PRIORITIES, statuses=STATUSES, total=base.count(), now=now_local())


def _form_template(form, assignment, status_code=200):
    return render_template("assignments/form.html", form=form, assignment=assignment,
                           priorities=PRIORITIES, statuses=STATUSES), status_code


@assignments_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = {"priority": "Medium", "status": "Pending", "assigned_date": now_local().date().isoformat()}
    if request.method == "POST":
        form = form_values(*FIELDS)
        data, errors = validate(form)
        if errors:
            for message in errors:
                flash(message, "danger")
            return _form_template(form, None, 400)
        db.session.add(Assignment(user_id=current_user.id, **data))
        db.session.commit()
        flash("Assignment added.", "success")
        return redirect(url_for("assignments.index"))
    return _form_template(form, None)


@assignments_bp.route("/<int:assignment_id>")
@login_required
def detail(assignment_id):
    return render_template("assignments/detail.html", a=owned_or_404(Assignment, assignment_id))


@assignments_bp.route("/<int:assignment_id>/edit", methods=["GET", "POST"])
@login_required
def edit(assignment_id):
    a = owned_or_404(Assignment, assignment_id)
    if request.method == "POST":
        form = form_values(*FIELDS)
        data, errors = validate(form)
        if errors:
            for message in errors:
                flash(message, "danger")
            return _form_template(form, a, 400)
        for key, value in data.items():
            setattr(a, key, value)
        db.session.commit()
        flash("Assignment updated.", "success")
        return redirect(url_for("assignments.detail", assignment_id=a.id))
    form = {
        "title": a.title, "subject_name": a.subject_name, "subject_code": a.subject_code or "",
        "description": a.description or "",
        "assigned_date": a.assigned_date.isoformat() if a.assigned_date else "",
        "deadline": a.deadline.strftime("%Y-%m-%dT%H:%M"), "priority": a.priority, "status": a.status,
    }
    return _form_template(form, a)


@assignments_bp.route("/<int:assignment_id>/complete", methods=["POST"])
@login_required
def complete(assignment_id):
    a = owned_or_404(Assignment, assignment_id)
    a.status = "Completed"
    db.session.commit()
    flash(f"'{a.title}' marked as completed.", "success")
    return redirect(request.referrer or url_for("assignments.index"))


@assignments_bp.route("/<int:assignment_id>/delete", methods=["POST"])
@login_required
def delete(assignment_id):
    db.session.delete(owned_or_404(Assignment, assignment_id))
    db.session.commit()
    flash("Assignment deleted.", "success")
    return redirect(url_for("assignments.index"))
