"""Small helpers shared across the app (time handling mostly)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app


def now_local():
    """Current local time as a *naive* datetime.
    We store naive local datetimes everywhere so comparisons stay simple."""
    tz = ZoneInfo(current_app.config["APP_TIMEZONE"])
    return datetime.now(tz).replace(tzinfo=None)


def today_local():
    return now_local().date()


def greeting():
    hour = now_local().hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"
