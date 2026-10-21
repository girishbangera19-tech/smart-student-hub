"""Class timetable: add / view / edit / delete, filter by day, block overlapping classes."""
import zlib

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from helpers import form_values, owned_or_404, parse_time
from models import ClassSchedule
from utils import today_local

timetable_bp = Blueprint("timetable", __name__, url_prefix="/timetable")

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
FIELDS = ("subject_name", "subject_code", "day_of_week", "start_time", "end_time",
          "faculty_name", "room", "notes")


def validate(form, entry_id=None):
    """Return (clean_data, errors). `entry_id` is the class being edited (ignored in the overlap check)."""
    errors = []
    if not form["subject_name"]:
        errors.append("Subject name is required.")
    if len(form["subject_name"]) > 120:
        errors.append("Subject name is too long (max 120 characters).")

    day = None
    if form["day_of_week"].isdigit() and 0 <= int(form["day_of_week"]) < len(DAYS):
        day = int(form["day_of_week"])
    else:
        errors.append("Please choose a day from Monday to Saturday.")

    start, end = parse_time(form["start_time"]), parse_time(form["end_time"])
    if start is None or end is None:
        errors.append("Please enter valid start and end times.")
    elif end <= start:
        errors.append("End time must be later than start time.")

    # Overlap check: two classes overlap when each one starts before the other ends.
    if not errors:
        query = ClassSchedule.query.filter(
            ClassSchedule.user_id == current_user.id,
            ClassSchedule.day_of_week == day,
            ClassSchedule.start_time < end,
            ClassSchedule.end_time > start,
        )
        if entry_id:
            query = query.filter(ClassSchedule.id != entry_id)
        clash = query.first()
        if clash:
            errors.append(
                f"This clashes with {clash.subject_name} on {DAYS[day]} "
                f"({clash.start_time.strftime('%I:%M %p')} - {clash.end_time.strftime('%I:%M %p')}). "
                "Please pick a different time."
            )

    data = {
        "subject_name": form["subject_name"], "subject_code": form["subject_code"][:20] or None,
        "day_of_week": day, "start_time": start, "end_time": end,
        "faculty_name": form["faculty_name"][:120] or None, "room": form["room"][:60] or None,
        "notes": form["notes"] or None,
    }
    return data, errors


@timetable_bp.route("/")
@login_required
def index():
    day_arg = request.args.get("day", "all")
    selected = int(day_arg) if day_arg.isdigit() and int(day_arg) < len(DAYS) else "all"

    query = ClassSchedule.query.filter_by(user_id=current_user.id)
    if selected != "all":
        query = query.filter_by(day_of_week=selected)
    classes = query.order_by(ClassSchedule.day_of_week, ClassSchedule.start_time).all()

    grouped = {i: [] for i in range(len(DAYS))}
    for c in classes:
        grouped[c.day_of_week].append(c)
    # A stable colour per subject name (same subject = same colour).
    colors = {c.id: zlib.crc32(c.subject_name.lower().encode()) % 6 for c in classes}

    visible_days = list(range(len(DAYS))) if selected == "all" else [selected]
    total = ClassSchedule.query.filter_by(user_id=current_user.id).count()
    return render_template("timetable/index.html", days=DAYS, grouped=grouped, colors=colors,
                           selected=selected, visible_days=visible_days, total=total,
                           today_idx=today_local().weekday())


@timetable_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = {"day_of_week": request.args.get("day", "")}
    if request.method == "POST":
        form = form_values(*FIELDS)
        data, errors = validate(form)
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("timetable/form.html", form=form, days=DAYS, entry=None), 400
        db.session.add(ClassSchedule(user_id=current_user.id, **data))
        db.session.commit()
        flash("Class added to your timetable.", "success")
        return redirect(url_for("timetable.index"))
    return render_template("timetable/form.html", form=form, days=DAYS, entry=None)


@timetable_bp.route("/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def edit(entry_id):
    entry = owned_or_404(ClassSchedule, entry_id)
    if request.method == "POST":
        form = form_values(*FIELDS)
        data, errors = validate(form, entry_id=entry.id)
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("timetable/form.html", form=form, days=DAYS, entry=entry), 400
        for key, value in data.items():
            setattr(entry, key, value)
        db.session.commit()
        flash("Class updated.", "success")
        return redirect(url_for("timetable.index"))

    form = {
        "subject_name": entry.subject_name, "subject_code": entry.subject_code or "",
        "day_of_week": str(entry.day_of_week), "start_time": entry.start_time.strftime("%H:%M"),
        "end_time": entry.end_time.strftime("%H:%M"), "faculty_name": entry.faculty_name or "",
        "room": entry.room or "", "notes": entry.notes or "",
    }
    return render_template("timetable/form.html", form=form, days=DAYS, entry=entry)


@timetable_bp.route("/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete(entry_id):
    entry = owned_or_404(ClassSchedule, entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash("Class deleted.", "success")
    return redirect(url_for("timetable.index"))
