"""In-app notifications. Reminders are generated in reminders.py; nothing is sent by email."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from helpers import owned_or_404
from models import Notification
from reminders import generate_reminders

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/")
@login_required
def index():
    generate_reminders(current_user)
    show = request.args.get("show", "all")
    query = Notification.query.filter_by(user_id=current_user.id)
    if show == "unread":
        query = query.filter_by(is_read=False)
    items = query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(100).all()
    unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return render_template("notifications/index.html", items=items, show=show, unread=unread)


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    n = owned_or_404(Notification, notification_id)
    n.is_read = True
    db.session.commit()
    return redirect(request.referrer or url_for("notifications.index"))


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("notifications.index"))
