"""In-app reminder generation.

generate_reminders() looks at a student's deadlines and creates Notification rows.
Each reminder has a `dedupe_key`; if that key already exists for the student we
skip it, so refreshing a page never creates duplicates. Nothing is sent by email
or push: reminders only appear inside the app.
"""
from datetime import timedelta

from flask import current_app, url_for
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models import Assignment, Exam, Notification, Task
from utils import now_local


def generate_reminders(user):
    """Create reminders; a database problem here is logged but never breaks the page."""
    try:
        _generate(user)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Reminder generation failed (run: flask check-db)")


def _generate(user):
    now = now_local()
    today = now.date()

    existing = {key for (key,) in db.session.query(Notification.dedupe_key).filter_by(user_id=user.id)}

    def add(key, kind, title, message, link):
        if key in existing:
            return
        existing.add(key)
        db.session.add(Notification(user_id=user.id, kind=kind, title=title,
                                    message=message[:300], link=link, dedupe_key=key))

    # Assignments: overdue, or due within 48 hours. The deadline is part of the key,
    # so moving a deadline later produces a fresh reminder.
    open_assignments = Assignment.query.filter(Assignment.user_id == user.id,
                                               Assignment.status != "Completed").all()
    for a in open_assignments:
        stamp = a.deadline.strftime("%Y%m%d%H%M")
        link = url_for("assignments.detail", assignment_id=a.id)
        if a.deadline < now:
            add(f"assignment-overdue-{a.id}-{stamp}", "assignment",
                "Assignment overdue", f"'{a.title}' was due {a.deadline.strftime('%d %b, %I:%M %p')}.", link)
        elif a.deadline <= now + timedelta(hours=48):
            add(f"assignment-due-{a.id}-{stamp}", "assignment",
                "Assignment due soon", f"'{a.title}' is due {a.deadline.strftime('%d %b, %I:%M %p')}.", link)

    # Exams in the next 7 days.
    for e in Exam.query.filter(Exam.user_id == user.id, Exam.exam_date >= today,
                               Exam.exam_date <= today + timedelta(days=7)).all():
        when = "today" if e.days_remaining == 0 else f"in {e.days_remaining} day(s)"
        add(f"exam-{e.id}-{e.exam_date.isoformat()}", "exam", "Upcoming exam",
            f"{e.subject_name} exam is {when} ({e.exam_date.strftime('%d %b')}).",
            url_for("exams.index"))

    # Tasks that are overdue, due today or due tomorrow.
    for t in Task.query.filter(Task.user_id == user.id, Task.is_completed.is_(False),
                               Task.due_date.isnot(None), Task.due_date <= today + timedelta(days=1)).all():
        label = "overdue" if t.due_date < today else ("due today" if t.due_date == today else "due tomorrow")
        add(f"task-{t.id}-{t.due_date.isoformat()}", "task", "Task reminder",
            f"'{t.title}' is {label}.", url_for("tasks.index"))

    try:
        db.session.commit()
    except IntegrityError:  # two requests raced; the other one created the rows
        db.session.rollback()
