"""Application factory. Run with:  flask run   (or: python app.py)"""
import os
from datetime import timedelta

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from sqlalchemy.exc import SQLAlchemyError

from config import Config
from extensions import csrf, db, login_manager, migrate


# Sidebar items: (label, endpoint, icon). If an endpoint is ever missing, the
# sidebar shows it as a disabled "Soon" item instead of a broken link.
NAV_ITEMS = [
    ("Dashboard", "dashboard.index", "bi-grid-1x2"),
    ("Class Timetable", "timetable.index", "bi-calendar3-week"),
    ("VTU Exam Timetable", "exams.index", "bi-journal-check"),
    ("Assignments", "assignments.index", "bi-clipboard-check"),
    ("Study Materials", "materials.index", "bi-folder2-open"),
    ("My Tasks", "tasks.index", "bi-check2-square"),
    ("Placements", "placements.index", "bi-briefcase"),
    ("Aptitude Practice", "aptitude.index", "bi-lightbulb"),
    ("Notifications", "notifications.index", "bi-bell"),
    ("My Profile", "profile.index", "bi-person-circle"),
    ("Settings", "profile.settings", "bi-gear"),
]


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Make sure the instance and upload folders exist.
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)

    # Import blueprints here (after extensions exist) to avoid circular imports.
    from routes.aptitude import aptitude_bp
    from routes.assignments import assignments_bp
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.exams import exams_bp
    from routes.materials import materials_bp
    from routes.notifications import notifications_bp
    from routes.placements import placements_bp
    from routes.profile import profile_bp
    from routes.tasks import tasks_bp
    from routes.timetable import timetable_bp

    for blueprint in (auth_bp, dashboard_bp, timetable_bp, exams_bp, assignments_bp, tasks_bp,
                      materials_bp, placements_bp, aptitude_bp, notifications_bp, profile_bp):
        app.register_blueprint(blueprint)

    from cli import auto_repair_on_startup, register_commands
    register_commands(app)
    if not app.config.get("TESTING"):
        auto_repair_on_startup(app)

    @app.before_request
    def refresh_reminders():
        """Create deadline reminders for the logged-in student, at most once per 5 minutes
        per browser session. (The dashboard and notifications pages always refresh them.)"""
        if request.method != "GET" or request.endpoint in (None, "static") or not current_user.is_authenticated:
            return
        from reminders import generate_reminders
        from utils import now_local

        last = session.get("reminders_at")
        now = now_local()
        if last:
            try:
                from datetime import datetime
                if now - datetime.fromisoformat(last) < timedelta(minutes=5):
                    return
            except ValueError:
                pass
        generate_reminders(current_user)
        session["reminders_at"] = now.isoformat()

    @app.context_processor
    def inject_globals():
        """Variables available in every template."""
        from models import Notification
        from utils import now_local

        unread = 0
        if current_user.is_authenticated:
            try:
                unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
            except SQLAlchemyError:
                db.session.rollback()  # a schema problem must not break every page
                app.logger.exception("Could not count notifications (run: flask check-db)")
        return {
            "nav_items": NAV_ITEMS,
            "endpoint_exists": lambda name: name in app.view_functions,
            "unread_count": unread,
            "today": now_local(),
        }

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")  # never "guess" file types
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        """Any failed save: undo the half-finished change, log the real error to the
        terminal, and show the student a short message instead of a traceback."""
        db.session.rollback()
        app.logger.exception("Database error on %s %s", request.method, request.path)
        if request.method == "POST":
            flash("Sorry, that could not be saved. Nothing was changed. Please try again.", "danger")
            return redirect(request.referrer or url_for("dashboard.index"))
        return render_template("errors/error.html", code=500,
                               message="A database problem occurred. If this keeps happening, "
                                       "run 'flask check-db' in the terminal."), 500

    @app.errorhandler(CSRFError)
    def csrf_failed(_):
        return render_template("errors/error.html", code=400,
                               message="Your form expired. Please go back, refresh the page and try again."), 400

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("errors/error.html", code=403, message="You don't have access to this page."), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template("errors/error.html", code=404, message="We couldn't find that page."), 404

    @app.errorhandler(413)
    def too_large(_):
        return render_template("errors/error.html", code=413, message="That file is too large (max 10 MB)."), 413

    @app.errorhandler(500)
    def server_error(_):
        db.session.rollback()
        return render_template("errors/error.html", code=500, message="Something went wrong on our side."), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
