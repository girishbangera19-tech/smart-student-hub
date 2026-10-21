"""Registration, login and logout."""
import re
from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__)

BRANCHES = [
    "Computer Science & Engineering",
    "Information Science & Engineering",
    "Electronics & Communication",
    "Electrical & Electronics",
    "Mechanical Engineering",
    "Civil Engineering",
    "AI & Machine Learning",
    "Other",
]
SCHEMES = ["2022", "2021", "2018", "Other"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_safe_next(target):
    """Only allow redirects to paths on our own site (prevents open redirects)."""
    if not target:
        return False
    parts = urlparse(target)
    return not parts.netloc and not parts.scheme and target.startswith("/")


def validate_registration(form):
    """Return a list of error messages (empty list = valid)."""
    errors = []
    if len(form["full_name"]) < 2:
        errors.append("Please enter your full name.")
    if not EMAIL_RE.match(form["email"]):
        errors.append("Please enter a valid email address.")
    if len(form["password"]) < 8:
        errors.append("Password must be at least 8 characters long.")
    if form["password"] != form["confirm_password"]:
        errors.append("Passwords do not match.")
    if not form["college_name"]:
        errors.append("College name is required.")
    if not form["branch"]:
        errors.append("Please choose your branch.")
    try:
        sem = int(form["semester"])
        if not 1 <= sem <= 8:
            raise ValueError
    except ValueError:
        errors.append("Semester must be a number from 1 to 8.")
    return errors


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        form = {
            "full_name": request.form.get("full_name", "").strip(),
            "email": request.form.get("email", "").strip().lower(),
            "password": request.form.get("password", ""),
            "confirm_password": request.form.get("confirm_password", ""),
            "college_name": request.form.get("college_name", "").strip(),
            "branch": request.form.get("branch", "").strip(),
            "semester": request.form.get("semester", "").strip(),
            "scheme": request.form.get("scheme", "").strip(),
        }
        errors = validate_registration(form)

        # Duplicate email check
        if not errors and User.query.filter_by(email=form["email"]).first():
            errors.append("An account with this email already exists. Try logging in.")

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("auth/register.html", form=form, branches=BRANCHES, schemes=SCHEMES), 400

        user = User(
            full_name=form["full_name"],
            email=form["email"],
            college_name=form["college_name"],
            branch=form["branch"],
            semester=int(form["semester"]),
            scheme=form["scheme"] or None,
        )
        user.set_password(form["password"])  # stored as a hash, never plain text
        db.session.add(user)
        db.session.commit()

        flash("Account created! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form={}, branches=BRANCHES, schemes=SCHEMES)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        # Same message for unknown email and wrong password (don't reveal which).
        if user is None or not user.check_password(password):
            flash("Incorrect email or password.", "danger")
            return render_template("auth/login.html", email=email), 401

        login_user(user)
        next_url = request.args.get("next")
        return redirect(next_url if is_safe_next(next_url) else url_for("dashboard.index"))

    return render_template("auth/login.html", email="")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("dashboard.landing"))
