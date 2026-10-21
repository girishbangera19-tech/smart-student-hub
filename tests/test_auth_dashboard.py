"""Stage 1 tests: registration, login/logout, protected pages and the dashboard."""
from datetime import timedelta

from extensions import db
from models import Assignment, ClassSchedule, Task, User
from utils import now_local, today_local


def test_landing_page_loads(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Your Entire Academic Life, One Smart Hub." in res.data


def test_register_creates_user_with_hashed_password(client, register):
    res = register()
    assert res.status_code == 302  # redirected to login
    user = User.query.filter_by(email="asha@example.com").first()
    assert user is not None
    assert user.password_hash != "password123"
    assert user.check_password("password123")


def test_register_rejects_duplicate_email(client, register):
    register()
    res = register()
    assert res.status_code == 400
    assert User.query.count() == 1


def test_register_validates_input(client, register):
    assert register(password="short", confirm_password="short").status_code == 400
    assert register(confirm_password="different123").status_code == 400
    assert register(email="not-an-email").status_code == 400
    assert register(semester="12").status_code == 400
    assert User.query.count() == 0


def test_login_and_logout(client, register, login):
    register()
    assert login().status_code == 302
    assert client.get("/dashboard").status_code == 200
    assert client.post("/logout").status_code == 302
    assert client.get("/dashboard").status_code == 302  # back to login


def test_login_wrong_password(client, register, login):
    register()
    res = login(password="wrong-password")
    assert res.status_code == 401
    assert b"Incorrect email or password" in res.data


def test_protected_page_redirects_to_login(client):
    res = client.get("/dashboard")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_login_next_redirect_is_safe(client, register):
    register()
    res = client.post("/login?next=https://evil.example.com",
                      data={"email": "asha@example.com", "password": "password123"})
    assert res.headers["Location"].endswith("/dashboard")


def test_dashboard_empty_state(client, register, login):
    register()
    login()
    res = client.get("/dashboard")
    assert b"No classes today" in res.data
    assert b"No upcoming exams" in res.data


def test_dashboard_numbers_come_from_database(app, client, register, login):
    register()
    login()
    user = User.query.first()
    today = today_local()

    # Only add a class if today is Mon-Sat; Sunday has no classes by design.
    from datetime import time
    db.session.add(ClassSchedule(user_id=user.id, subject_name="Data Structures", day_of_week=today.weekday(),
                                 start_time=time(9, 0), end_time=time(10, 0), room="LH-1"))
    db.session.add(Assignment(user_id=user.id, title="DS Lab Record", subject_name="Data Structures",
                              deadline=now_local() + timedelta(hours=5)))
    db.session.add(Task(user_id=user.id, title="Revise Module 3", due_date=today))
    db.session.commit()

    html = client.get("/dashboard").data.decode()
    assert "DS Lab Record" in html
    assert "Revise Module 3" in html
    assert "within 24 hours" in html


def test_dashboard_shows_only_own_data(app, client, register, login):
    register()
    other = User(full_name="Other", email="other@example.com", college_name="X", branch="CSE", semester=3)
    other.set_password("password123")
    db.session.add(other)
    db.session.commit()
    db.session.add(Assignment(user_id=other.id, title="SECRET OTHER ASSIGNMENT", subject_name="Math",
                              deadline=now_local() + timedelta(days=1)))
    db.session.commit()

    login()
    assert b"SECRET OTHER ASSIGNMENT" not in client.get("/dashboard").data


def test_overdue_assignment_logic(app, register):
    register()
    user = User.query.first()
    past = now_local() - timedelta(days=1)
    overdue = Assignment(user_id=user.id, title="A", subject_name="S", deadline=past)
    done = Assignment(user_id=user.id, title="B", subject_name="S", deadline=past, status="Completed")
    assert overdue.is_overdue is True
    assert done.is_overdue is False
