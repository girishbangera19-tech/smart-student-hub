"""Helpers shared by the route modules: ownership checks and form parsing."""
from datetime import datetime

from flask import abort, request
from flask_login import current_user

from extensions import db


def owned_or_404(model, record_id):
    """Fetch a record that belongs to the logged-in student, otherwise return 404.
    Using 404 (not 403) avoids revealing that someone else's record exists."""
    record = db.session.get(model, record_id)
    if record is None or record.user_id != current_user.id:
        abort(404)
    return record


def clean(value):
    """Strip whitespace from form input; None becomes an empty string."""
    return (value or "").strip()


def form_values(*names):
    """Read several text fields from request.form into a dict of cleaned strings."""
    return {name: clean(request.form.get(name)) for name in names}


def _parse(value, formats):
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_date(value):
    """'2026-10-20' -> date, or None if empty/invalid."""
    parsed = _parse(value, ["%Y-%m-%d"]) if value else None
    return parsed.date() if parsed else None


def parse_time(value):
    """'14:30' -> time, or None if empty/invalid."""
    parsed = _parse(value, ["%H:%M", "%H:%M:%S"]) if value else None
    return parsed.time() if parsed else None


def parse_datetime(value):
    """Value of an <input type="datetime-local"> -> naive datetime, or None."""
    return _parse(value, ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"]) if value else None


def is_http_url(value):
    """Only allow http(s) links (blocks javascript: and other unsafe schemes)."""
    return value.lower().startswith(("http://", "https://")) and len(value) <= 500
