"""Profile, password change and theme settings. Users can only ever edit themselves."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from helpers import form_values
from routes.auth import BRANCHES, SCHEMES

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


@profile_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        form = form_values("full_name", "college_name", "branch", "semester", "scheme")
        errors = []
        if len(form["full_name"]) < 2:
            errors.append("Please enter your full name.")
        if not form["college_name"]:
            errors.append("College name is required.")
        if not form["branch"]:
            errors.append("Please choose your branch.")
        if not (form["semester"].isdigit() and 1 <= int(form["semester"]) <= 8):
            errors.append("Semester must be a number from 1 to 8.")
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("profile/index.html", form=form, branches=BRANCHES, schemes=SCHEMES), 400
        # Only these fields are updated. Email and password are NOT changed here.
        current_user.full_name = form["full_name"][:120]
        current_user.college_name = form["college_name"][:150]
        current_user.branch = form["branch"][:100]
        current_user.semester = int(form["semester"])
        current_user.scheme = form["scheme"][:20] or None
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile.index"))

    form = {"full_name": current_user.full_name, "college_name": current_user.college_name,
            "branch": current_user.branch, "semester": str(current_user.semester),
            "scheme": current_user.scheme or ""}
    return render_template("profile/index.html", form=form, branches=BRANCHES, schemes=SCHEMES)


@profile_bp.route("/password", methods=["POST"])
@login_required
def password():
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    if not current_user.check_password(current):
        flash("Your current password is incorrect.", "danger")
    elif len(new) < 8:
        flash("New password must be at least 8 characters long.", "danger")
    elif new != confirm:
        flash("New passwords do not match.", "danger")
    elif new == current:
        flash("Choose a password different from your current one.", "danger")
    else:
        current_user.set_password(new)
        db.session.commit()
        flash("Password changed successfully.", "success")
    return redirect(url_for("profile.settings"))


@profile_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        theme = request.form.get("theme")
        if theme in ("light", "dark"):
            current_user.theme = theme
            db.session.commit()
            flash(f"{theme.title()} mode enabled.", "success")
        else:
            flash("Invalid theme.", "danger")
        return redirect(url_for("profile.settings"))
    return render_template("profile/settings.html")
