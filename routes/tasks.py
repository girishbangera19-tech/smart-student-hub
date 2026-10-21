"""Personal tasks: CRUD, complete/undo, filters. The dashboard checkbox calls tasks.toggle."""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from helpers import clean, form_values, owned_or_404, parse_date, parse_time
from models import Task
from utils import now_local, today_local

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")

PRIORITIES = ["Low", "Medium", "High"]
CATEGORIES = ["General", "Study", "Exam Prep", "Lab", "Placement", "Project", "Personal"]
FIELDS = ("title", "description", "due_date", "due_time", "priority", "category", "is_completed")


def validate(form):
    errors = []
    if not form["title"]:
        errors.append("Task title is required.")
    due_date = parse_date(form["due_date"]) if form["due_date"] else None
    if form["due_date"] and due_date is None:
        errors.append("Due date is not valid.")
    due_time = parse_time(form["due_time"]) if form["due_time"] else None
    if form["due_time"] and due_time is None:
        errors.append("Due time is not valid.")
    if form["priority"] not in PRIORITIES:
        errors.append("Please choose a priority.")
    category = form["category"] if form["category"] in CATEGORIES else "General"
    data = {"title": form["title"][:150], "description": form["description"] or None,
            "due_date": due_date, "due_time": due_time, "priority": form["priority"], "category": category}
    return data, errors


def set_completed(task, done):
    task.is_completed = done
    task.completed_at = now_local() if done else None


@tasks_bp.route("/")
@login_required
def index():
    q = clean(request.args.get("q"))
    category = clean(request.args.get("category"))
    priority = clean(request.args.get("priority"))
    status = clean(request.args.get("status"))  # open / done / overdue / today
    today = today_local()

    base = Task.query.filter_by(user_id=current_user.id)
    query = base
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Task.title.ilike(like), Task.description.ilike(like)))
    if category in CATEGORIES:
        query = query.filter(Task.category == category)
    if priority in PRIORITIES:
        query = query.filter(Task.priority == priority)
    if status == "done":
        query = query.filter(Task.is_completed.is_(True))
    elif status == "open":
        query = query.filter(Task.is_completed.is_(False))
    elif status == "overdue":
        query = query.filter(Task.is_completed.is_(False), Task.due_date < today)
    elif status == "today":
        query = query.filter(Task.due_date == today)
    # Tasks without a due date go last.
    tasks = query.order_by(Task.is_completed, Task.due_date.is_(None), Task.due_date, Task.due_time).all()

    total = base.count()
    done = base.filter(Task.is_completed.is_(True)).count()
    overdue = base.filter(Task.is_completed.is_(False), Task.due_date < today).count()
    due_today = base.filter(Task.is_completed.is_(False), Task.due_date == today).count()
    return render_template("tasks/index.html", tasks=tasks, q=q, category=category, priority=priority,
                           status=status, categories=CATEGORIES, priorities=PRIORITIES, today=today,
                           total=total, done=done, overdue=overdue, due_today=due_today,
                           percent=round(done * 100 / total) if total else 0)


def _form_template(form, task, code=200):
    return render_template("tasks/form.html", form=form, task=task, categories=CATEGORIES,
                           priorities=PRIORITIES), code


@tasks_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = {"priority": "Medium", "category": "General", "due_date": today_local().isoformat()}
    if request.method == "POST":
        form = form_values(*FIELDS)
        data, errors = validate(form)
        if errors:
            for message in errors:
                flash(message, "danger")
            return _form_template(form, None, 400)
        task = Task(user_id=current_user.id, **data)
        set_completed(task, bool(form["is_completed"]))
        db.session.add(task)
        db.session.commit()
        flash("Task added.", "success")
        return redirect(url_for("tasks.index"))
    return _form_template(form, None)


@tasks_bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit(task_id):
    task = owned_or_404(Task, task_id)
    if request.method == "POST":
        form = form_values(*FIELDS)
        data, errors = validate(form)
        if errors:
            for message in errors:
                flash(message, "danger")
            return _form_template(form, task, 400)
        for key, value in data.items():
            setattr(task, key, value)
        set_completed(task, bool(form["is_completed"]))
        db.session.commit()
        flash("Task updated.", "success")
        return redirect(url_for("tasks.index"))
    form = {"title": task.title, "description": task.description or "",
            "due_date": task.due_date.isoformat() if task.due_date else "",
            "due_time": task.due_time.strftime("%H:%M") if task.due_time else "",
            "priority": task.priority, "category": task.category or "General",
            "is_completed": "1" if task.is_completed else ""}
    return _form_template(form, task)


@tasks_bp.route("/<int:task_id>/toggle", methods=["POST"])
@login_required
def toggle(task_id):
    """Flip complete/incomplete. Returns JSON for the dashboard checkbox, a redirect otherwise."""
    task = owned_or_404(Task, task_id)
    set_completed(task, not task.is_completed)
    db.session.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(ok=True, completed=task.is_completed)
    flash("Task completed." if task.is_completed else "Task marked as not done.", "success")
    return redirect(request.referrer or url_for("tasks.index"))


@tasks_bp.route("/<int:task_id>/delete", methods=["POST"])
@login_required
def delete(task_id):
    db.session.delete(owned_or_404(Task, task_id))
    db.session.commit()
    flash("Task deleted.", "success")
    return redirect(url_for("tasks.index"))
