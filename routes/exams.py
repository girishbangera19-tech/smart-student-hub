"""VTU exam timetable. Students type dates in manually; nothing is fetched from VTU,
and entries are marked Unverified unless the student says otherwise."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from helpers import clean, form_values, owned_or_404, parse_date, parse_time
from models import Exam
from utils import today_local

exams_bp = Blueprint("exams", __name__, url_prefix="/exams")

FIELDS = ("subject_name", "subject_code", "exam_date", "start_time", "end_time", "session",
          "venue", "notes", "semester", "scheme", "source", "verification_status")
SESSIONS = ["Morning", "Afternoon"]
STATUSES = ["Unverified", "Verified"]


def validate(form):
    errors = []
    if not form["subject_name"]:
        errors.append("Subject name is required.")
    exam_date = parse_date(form["exam_date"])
    if exam_date is None:
        errors.append("Please enter a valid exam date.")
    start, end = parse_time(form["start_time"]), parse_time(form["end_time"])
    if form["start_time"] and start is None or form["end_time"] and end is None:
        errors.append("Please enter valid times.")
    elif start and end and end <= start:
        errors.append("End time must be later than start time.")
    semester = None
    if form["semester"]:
        if form["semester"].isdigit() and 1 <= int(form["semester"]) <= 8:
            semester = int(form["semester"])
        else:
            errors.append("Semester must be between 1 and 8.")
    if form["session"] and form["session"] not in SESSIONS:
        errors.append("Invalid session.")
    if form["verification_status"] not in STATUSES:
        form["verification_status"] = "Unverified"
    data = {
        "subject_name": form["subject_name"][:120], "subject_code": form["subject_code"][:20] or None,
        "exam_date": exam_date, "start_time": start, "end_time": end,
        "session": form["session"] or None, "venue": form["venue"][:120] or None,
        "notes": form["notes"] or None, "semester": semester, "scheme": form["scheme"][:20] or None,
        "source": form["source"][:200] or None, "verification_status": form["verification_status"],
    }
    return data, errors


@exams_bp.route("/")
@login_required
def index():
    view = request.args.get("view", "upcoming")
    q = clean(request.args.get("q"))
    semester = clean(request.args.get("semester"))
    today = today_local()

    query = Exam.query.filter_by(user_id=current_user.id)
    if view == "completed":
        query = query.filter(Exam.exam_date < today).order_by(Exam.exam_date.desc())
    elif view == "all":
        query = query.order_by(Exam.exam_date)
    else:
        view = "upcoming"
        query = query.filter(Exam.exam_date >= today).order_by(Exam.exam_date)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Exam.subject_name.ilike(like), Exam.subject_code.ilike(like)))
    if semester.isdigit():
        query = query.filter(Exam.semester == int(semester))
    exams = query.all()

    next_exam = (Exam.query.filter(Exam.user_id == current_user.id, Exam.exam_date >= today)
                 .order_by(Exam.exam_date).first())
    return render_template("exams/index.html", exams=exams, view=view, q=q, semester=semester,
                           next_exam=next_exam)


@exams_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = {"verification_status": "Unverified", "semester": str(current_user.semester),
            "scheme": current_user.scheme or ""}
    if request.method == "POST":
        form = form_values(*FIELDS)
        data, errors = validate(form)
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("exams/form.html", form=form, exam=None, sessions=SESSIONS, statuses=STATUSES), 400
        db.session.add(Exam(user_id=current_user.id, **data))
        db.session.commit()
        flash("Exam added.", "success")
        return redirect(url_for("exams.index"))
    return render_template("exams/form.html", form=form, exam=None, sessions=SESSIONS, statuses=STATUSES)


@exams_bp.route("/<int:exam_id>/edit", methods=["GET", "POST"])
@login_required
def edit(exam_id):
    exam = owned_or_404(Exam, exam_id)
    if request.method == "POST":
        form = form_values(*FIELDS)
        data, errors = validate(form)
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("exams/form.html", form=form, exam=exam, sessions=SESSIONS, statuses=STATUSES), 400
        for key, value in data.items():
            setattr(exam, key, value)
        db.session.commit()
        flash("Exam updated.", "success")
        return redirect(url_for("exams.index"))
    form = {
        "subject_name": exam.subject_name, "subject_code": exam.subject_code or "",
        "exam_date": exam.exam_date.isoformat(),
        "start_time": exam.start_time.strftime("%H:%M") if exam.start_time else "",
        "end_time": exam.end_time.strftime("%H:%M") if exam.end_time else "",
        "session": exam.session or "", "venue": exam.venue or "", "notes": exam.notes or "",
        "semester": str(exam.semester or ""), "scheme": exam.scheme or "", "source": exam.source or "",
        "verification_status": exam.verification_status,
    }
    return render_template("exams/form.html", form=form, exam=exam, sessions=SESSIONS, statuses=STATUSES)


@exams_bp.route("/<int:exam_id>/delete", methods=["POST"])
@login_required
def delete(exam_id):
    db.session.delete(owned_or_404(Exam, exam_id))
    db.session.commit()
    flash("Exam deleted.", "success")
    return redirect(url_for("exams.index"))
