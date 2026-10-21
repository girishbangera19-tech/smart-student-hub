"""Public landing page and the student dashboard (all numbers come from the DB)."""
from datetime import datetime, timedelta

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from extensions import db
from models import (Assignment, ClassSchedule, Exam, PlacementOpportunity,
                    StudyMaterial, Task)
from reminders import generate_reminders
from utils import greeting, now_local, today_local

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return render_template("index.html")


@dashboard_bp.route("/dashboard")
@login_required
def index():
    uid = current_user.id
    now = now_local()
    today = today_local()
    generate_reminders(current_user)  # idempotent: duplicates are prevented by dedupe_key

    # Monday = 0 ... Sunday = 6. Classes only exist for Mon-Sat.
    todays_classes = (ClassSchedule.query.filter_by(user_id=uid, day_of_week=today.weekday())
                      .order_by(ClassSchedule.start_time).all())

    upcoming_exams = (Exam.query.filter(Exam.user_id == uid, Exam.exam_date >= today)
                      .order_by(Exam.exam_date).limit(5).all())

    open_assignments = (Assignment.query.filter(Assignment.user_id == uid, Assignment.status != "Completed")
                        .order_by(Assignment.deadline).all())
    due_24h = [a for a in open_assignments if now <= a.deadline <= now + timedelta(hours=24)]

    todays_tasks = (Task.query.filter(Task.user_id == uid, Task.due_date == today)
                    .order_by(Task.is_completed, Task.due_time).all())
    soon = today + timedelta(days=2)
    tasks_due_soon = Task.query.filter(Task.user_id == uid, Task.is_completed.is_(False),
                                       Task.due_date.isnot(None), Task.due_date <= soon).count()

    recent_materials = (StudyMaterial.query.filter_by(user_id=uid)
                        .order_by(StudyMaterial.uploaded_at.desc()).limit(4).all())
    material_count = StudyMaterial.query.filter_by(user_id=uid).count()

    opportunities = (PlacementOpportunity.query
                     .filter(db.or_(PlacementOpportunity.deadline.is_(None),
                                    PlacementOpportunity.deadline >= today))
                     .order_by(PlacementOpportunity.created_at.desc()).limit(4).all())
    opportunity_count = PlacementOpportunity.query.filter(
        db.or_(PlacementOpportunity.deadline.is_(None), PlacementOpportunity.deadline >= today)).count()

    # Numbers for the progress chart.
    total_assignments = Assignment.query.filter_by(user_id=uid).count()
    done_assignments = Assignment.query.filter_by(user_id=uid, status="Completed").count()
    overdue_assignments = sum(1 for a in open_assignments if a.is_overdue)
    total_tasks = Task.query.filter_by(user_id=uid).count()
    done_tasks = Task.query.filter_by(user_id=uid, is_completed=True).count()

    stats = {
        "classes_today": len(todays_classes),
        "upcoming_exams": Exam.query.filter(Exam.user_id == uid, Exam.exam_date >= today).count(),
        "pending_assignments": len(open_assignments),
        "tasks_due_soon": tasks_due_soon,
        "materials": material_count,
        "opportunities": opportunity_count,
    }
    chart = {
        "assignments": [done_assignments,
                        total_assignments - done_assignments - overdue_assignments,
                        overdue_assignments],
        "tasks": [done_tasks, total_tasks - done_tasks],
    }

    return render_template(
        "dashboard/dashboard.html",
        greeting=greeting(), stats=stats, chart=chart,
        todays_classes=todays_classes, upcoming_exams=upcoming_exams,
        open_assignments=open_assignments[:5], due_24h=due_24h,
        todays_tasks=todays_tasks, recent_materials=recent_materials,
        opportunities=opportunities,
        next_exam=upcoming_exams[0] if upcoming_exams else None,
        has_chart_data=(total_assignments + total_tasks) > 0,
    )
