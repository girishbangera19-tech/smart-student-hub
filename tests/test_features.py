"""Stage 2 tests: timetable, exams, assignments, tasks, materials, placements,
aptitude, notifications, profile and cross-user access protection."""
import io
from datetime import timedelta

import pytest

from extensions import db
from models import (Assignment, AptitudeAttempt, ClassSchedule, Exam, Notification,
                    PlacementOpportunity, StudentApplication, StudyMaterial, Task, User)
from tests.conftest import REGISTER_DATA
from utils import now_local, today_local


@pytest.fixture()
def user(client, register, login):
    """A registered, logged-in student."""
    register()
    login()
    return User.query.filter_by(email="asha@example.com").first()


@pytest.fixture()
def other_client(app):
    """A second, separately logged-in student."""
    c = app.test_client()
    data = {**REGISTER_DATA, "email": "ravi@example.com", "full_name": "Ravi K"}
    c.post("/register", data=data)
    c.post("/login", data={"email": "ravi@example.com", "password": "password123"})
    return c


PDF = (b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF", "notes.pdf")


# ---------------- timetable ----------------
CLASS = {"subject_name": "Data Structures", "subject_code": "BCS304", "day_of_week": "0",
         "start_time": "09:00", "end_time": "10:00", "faculty_name": "Dr. Rao", "room": "LH-1"}


def test_timetable_create_edit_delete(client, user):
    assert client.post("/timetable/new", data=CLASS).status_code == 302
    entry = ClassSchedule.query.one()
    assert entry.user_id == user.id and entry.faculty_name == "Dr. Rao"

    client.post(f"/timetable/{entry.id}/edit", data={**CLASS, "room": "LH-2"})
    assert db.session.get(ClassSchedule, entry.id).room == "LH-2"

    client.post(f"/timetable/{entry.id}/delete")
    assert ClassSchedule.query.count() == 0


def test_timetable_blocks_overlap_but_allows_back_to_back(client, user):
    client.post("/timetable/new", data=CLASS)
    clash = client.post("/timetable/new", data={**CLASS, "subject_name": "DBMS", "start_time": "09:30", "end_time": "10:30"})
    assert clash.status_code == 400 and b"clashes with" in clash.data
    ok = client.post("/timetable/new", data={**CLASS, "subject_name": "DBMS", "start_time": "10:00", "end_time": "11:00"})
    assert ok.status_code == 302
    assert ClassSchedule.query.count() == 2


def test_timetable_rejects_bad_times(client, user):
    res = client.post("/timetable/new", data={**CLASS, "start_time": "11:00", "end_time": "10:00"})
    assert res.status_code == 400 and ClassSchedule.query.count() == 0


def test_timetable_day_filter(client, user):
    client.post("/timetable/new", data=CLASS)
    client.post("/timetable/new", data={**CLASS, "subject_name": "Networks", "day_of_week": "2"})
    page = client.get("/timetable/?day=2").data
    assert b"Networks" in page and b"Data Structures" not in page


# ---------------- exams ----------------
def exam_data(days=10, **kw):
    return {"subject_name": "Computer Networks", "subject_code": "BCS502",
            "exam_date": (today_local() + timedelta(days=days)).isoformat(), "venue": "Hall A", **kw}


def test_exam_crud_and_countdown(client, user):
    assert client.post("/exams/new", data=exam_data(10)).status_code == 302
    exam = Exam.query.one()
    assert exam.days_remaining == 10
    assert exam.verification_status == "Unverified"
    assert b"until your next exam" in client.get("/exams/").data

    client.post(f"/exams/{exam.id}/edit", data=exam_data(5, venue="Hall B"))
    assert db.session.get(Exam, exam.id).venue == "Hall B"
    client.post(f"/exams/{exam.id}/delete")
    assert Exam.query.count() == 0


def test_exam_requires_valid_date(client, user):
    assert client.post("/exams/new", data={**exam_data(), "exam_date": "not-a-date"}).status_code == 400


def test_exam_upcoming_vs_completed(client, user):
    client.post("/exams/new", data=exam_data(-3, subject_name="Old Exam"))
    client.post("/exams/new", data=exam_data(3, subject_name="New Exam"))
    assert b"New Exam" in client.get("/exams/").data
    assert b"Old Exam" not in client.get("/exams/").data
    assert b"Old Exam" in client.get("/exams/?view=completed").data


# ---------------- assignments ----------------
def assignment_data(hours=48, **kw):
    due = (now_local() + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M")
    return {"title": "Lab record", "subject_name": "DBMS", "deadline": due,
            "priority": "High", "status": "Pending", **kw}


def test_assignment_crud_and_complete(client, user):
    assert client.post("/assignments/new", data=assignment_data()).status_code == 302
    a = Assignment.query.one()
    assert client.get(f"/assignments/{a.id}").status_code == 200

    client.post(f"/assignments/{a.id}/edit", data=assignment_data(title="Lab record v2"))
    assert db.session.get(Assignment, a.id).title == "Lab record v2"

    client.post(f"/assignments/{a.id}/complete")
    assert db.session.get(Assignment, a.id).status == "Completed"
    client.post(f"/assignments/{a.id}/delete")
    assert Assignment.query.count() == 0


def test_assignment_overdue_detection_and_filter(client, user):
    client.post("/assignments/new", data=assignment_data(-5, title="Late one"))
    client.post("/assignments/new", data=assignment_data(-5, title="Finished", status="Completed"))
    late = Assignment.query.filter_by(title="Late one").one()
    done = Assignment.query.filter_by(title="Finished").one()
    assert late.is_overdue and not done.is_overdue
    page = client.get("/assignments/?status=Overdue").data
    assert b"Late one" in page and b"Finished" not in page


def test_assignment_search_and_priority_filter(client, user):
    client.post("/assignments/new", data=assignment_data(title="Alpha", priority="High"))
    client.post("/assignments/new", data=assignment_data(title="Beta", priority="Low"))
    assert b"Beta" not in client.get("/assignments/?priority=High").data
    assert b"Alpha" not in client.get("/assignments/?q=Beta").data


def test_assignment_validation(client, user):
    assert client.post("/assignments/new", data={**assignment_data(), "title": ""}).status_code == 400
    assert client.post("/assignments/new", data={**assignment_data(), "priority": "Urgent"}).status_code == 400


# ---------------- tasks ----------------
def test_task_create_complete_and_dashboard_update(client, user):
    client.post("/tasks/new", data={"title": "Revise Module 3", "priority": "Medium",
                                    "category": "Study", "due_date": today_local().isoformat()})
    task = Task.query.one()
    assert b"Revise Module 3" in client.get("/dashboard").data

    res = client.post(f"/tasks/{task.id}/toggle", headers={"X-Requested-With": "fetch"})
    assert res.get_json()["completed"] is True
    assert db.session.get(Task, task.id).completed_at is not None
    # toggling again undoes it
    client.post(f"/tasks/{task.id}/toggle")
    assert db.session.get(Task, task.id).is_completed is False


def test_task_overdue_and_progress(client, user):
    yesterday = (today_local() - timedelta(days=1)).isoformat()
    client.post("/tasks/new", data={"title": "Old task", "priority": "Low", "due_date": yesterday})
    client.post("/tasks/new", data={"title": "Done task", "priority": "Low", "is_completed": "1"})
    assert b"Old task" in client.get("/tasks/?status=overdue").data
    assert b"Done task" not in client.get("/tasks/?status=overdue").data
    assert b"1 of 2 completed" in client.get("/tasks/").data


def test_task_edit_delete_and_validation(client, user):
    assert client.post("/tasks/new", data={"title": "", "priority": "Low"}).status_code == 400
    client.post("/tasks/new", data={"title": "T1", "priority": "Low"})
    t = Task.query.one()
    client.post(f"/tasks/{t.id}/edit", data={"title": "T1 edited", "priority": "High"})
    assert db.session.get(Task, t.id).title == "T1 edited"
    client.post(f"/tasks/{t.id}/delete")
    assert Task.query.count() == 0


# ---------------- study materials ----------------
def upload(client, content=PDF[0], name=PDF[1], **extra):
    data = {"title": "DS Module 1", "subject_name": "Data Structures", "resource_type": "Notes",
            "semester": "3", "module_number": "1", "file": (io.BytesIO(content), name), **extra}
    return client.post("/materials/upload", data=data, content_type="multipart/form-data")


def test_upload_download_delete_pdf(client, user, app):
    assert upload(client).status_code == 302
    m = StudyMaterial.query.one()
    assert m.stored_filename != "notes.pdf" and m.stored_filename.endswith(".pdf")
    res = client.get(f"/materials/{m.id}/download")
    assert res.status_code == 200 and res.data.startswith(b"%PDF")
    assert "attachment" in res.headers["Content-Disposition"]

    client.post(f"/materials/{m.id}/delete")
    assert StudyMaterial.query.count() == 0


def test_upload_rejects_bad_files(client, user):
    assert upload(client, b"MZ\x90 not allowed", "virus.exe").status_code == 400
    assert upload(client, b"just text pretending", "fake.pdf").status_code == 400
    assert upload(client, b"<?php ?>", "shell.php").status_code == 400
    assert StudyMaterial.query.count() == 0


def test_upload_filename_is_sanitised(client, user):
    upload(client, name="../../evil.pdf")
    m = StudyMaterial.query.one()
    assert ".." not in m.stored_filename and "/" not in m.stored_filename


def test_materials_search_and_filter(client, user):
    upload(client, title="Alpha Notes")
    upload(client, title="Beta Paper", resource_type="Question Paper", subject_name="Maths")
    assert b"Beta Paper" not in client.get("/materials/?type=Notes").data
    assert b"Alpha Notes" not in client.get("/materials/?q=Beta").data
    assert b"Alpha Notes" not in client.get("/materials/?subject=Maths").data


# ---------------- placements ----------------
def test_placement_create_and_private_tracking(client, user, other_client):
    deadline = (today_local() + timedelta(days=7)).isoformat()
    client.post("/placements/new", data={"company_name": "Acme", "job_title": "Developer",
                                          "min_cgpa": "7.5", "deadline": deadline,
                                          "application_url": "https://acme.example/jobs"})
    item = PlacementOpportunity.query.one()
    assert item.is_verified is False

    client.post(f"/placements/{item.id}/track", data={"status": "Applied", "notes": "sent CV"})
    row = StudentApplication.query.one()
    assert row.status == "Applied" and row.user_id == user.id
    # update, not duplicate
    client.post(f"/placements/{item.id}/track", data={"status": "Interview"})
    assert StudentApplication.query.one().status == "Interview"

    # the other student sees the listing but NOT my tracking
    page = other_client.get(f"/placements/{item.id}").data
    assert b"Acme" in page and b"sent CV" not in page


def test_placement_rejects_unsafe_url_and_other_users_edits(client, user, other_client):
    bad = client.post("/placements/new", data={"company_name": "X", "job_title": "Y",
                                                "application_url": "javascript:alert(1)"})
    assert bad.status_code == 400
    client.post("/placements/new", data={"company_name": "Acme", "job_title": "Dev"})
    item = PlacementOpportunity.query.one()
    assert other_client.post(f"/placements/{item.id}/delete").status_code == 404
    assert other_client.get(f"/placements/{item.id}/edit").status_code == 404
    assert PlacementOpportunity.query.count() == 1


def test_placement_invalid_status_rejected(client, user):
    client.post("/placements/new", data={"company_name": "Acme", "job_title": "Dev"})
    item = PlacementOpportunity.query.one()
    client.post(f"/placements/{item.id}/track", data={"status": "Hired!!"})
    assert StudentApplication.query.count() == 0


# ---------------- aptitude ----------------
def test_aptitude_quiz_scores_and_saves_attempt(client, user):
    page = client.get("/aptitude/Quantitative")
    assert page.status_code == 200 and b"15% of 200" in page.data

    from models import AptitudeQuestion
    questions = AptitudeQuestion.query.filter_by(category="Quantitative").all()
    answers = {f"q_{q.id}": q.correct_option for q in questions}
    res = client.post("/aptitude/Quantitative", data=answers)
    assert res.status_code == 200 and b"5 / 5" in res.data
    attempt = AptitudeAttempt.query.one()
    assert attempt.user_id == user.id and attempt.score == 5


def test_aptitude_wrong_answers_and_empty_submit(client, user):
    client.get("/aptitude/Verbal")
    from models import AptitudeQuestion
    qs = AptitudeQuestion.query.filter_by(category="Verbal").all()
    wrong = {f"q_{q.id}": ("a" if q.correct_option != "a" else "b") for q in qs}
    res = client.post("/aptitude/Verbal", data=wrong)
    assert AptitudeAttempt.query.one().score == 0 and b"Incorrect" in res.data
    assert client.post("/aptitude/Verbal", data={}).status_code == 400
    assert client.get("/aptitude/Nonsense").status_code == 404


# ---------------- notifications ----------------
def test_notifications_generated_without_duplicates(client, user):
    client.post("/assignments/new", data=assignment_data(5, title="Soon due"))
    client.post("/assignments/new", data=assignment_data(-5, title="Past due"))
    client.get("/notifications/")
    first = Notification.query.count()
    assert first == 2
    client.get("/notifications/")
    client.get("/dashboard")
    assert Notification.query.count() == first   # refreshing never duplicates


def test_notifications_mark_read(client, user):
    client.post("/assignments/new", data=assignment_data(5))
    client.get("/notifications/")
    assert Notification.query.filter_by(is_read=False).count() == 1
    n = Notification.query.first()
    client.post(f"/notifications/{n.id}/read")
    assert Notification.query.filter_by(is_read=False).count() == 0

    client.post("/assignments/new", data=assignment_data(6, title="Second"))
    client.get("/notifications/")
    client.post("/notifications/read-all")
    assert Notification.query.filter_by(is_read=False).count() == 0


def test_notification_unread_count_in_layout(client, user):
    client.post("/assignments/new", data=assignment_data(5))
    client.get("/notifications/")
    assert b'class="badge-count">1<' in client.get("/dashboard").data


# ---------------- profile ----------------
def test_profile_update_does_not_change_email_or_password(client, user):
    res = client.post("/profile/", data={"full_name": "Asha R", "college_name": "New College",
                                          "branch": "Information Science & Engineering", "semester": "6",
                                          "scheme": "2022", "email": "hacker@example.com"})
    assert res.status_code == 302
    u = db.session.get(User, user.id)
    assert u.full_name == "Asha R" and u.semester == 6
    assert u.email == "asha@example.com" and u.check_password("password123")


def test_profile_validation(client, user):
    bad = client.post("/profile/", data={"full_name": "A", "college_name": "", "branch": "", "semester": "99"})
    assert bad.status_code == 400


def test_change_password_and_theme(client, user):
    client.post("/profile/password", data={"current_password": "wrong-one", "new_password": "newpassword1",
                                            "confirm_password": "newpassword1"})
    assert db.session.get(User, user.id).check_password("password123")
    client.post("/profile/password", data={"current_password": "password123", "new_password": "newpassword1",
                                            "confirm_password": "newpassword1"})
    assert db.session.get(User, user.id).check_password("newpassword1")

    client.post("/profile/settings", data={"theme": "dark"})
    assert db.session.get(User, user.id).theme == "dark"
    client.post("/profile/settings", data={"theme": "<script>"})
    assert db.session.get(User, user.id).theme == "dark"


# ---------------- authorization ----------------
def test_pages_require_login(client):
    for url in ["/timetable/", "/exams/", "/assignments/", "/tasks/", "/materials/",
                "/placements/", "/aptitude/", "/notifications/", "/profile/", "/profile/settings"]:
        res = client.get(url)
        assert res.status_code == 302 and "/login" in res.headers["Location"], url


def test_user_cannot_touch_another_users_records(client, user, other_client):
    client.post("/timetable/new", data=CLASS)
    client.post("/exams/new", data=exam_data())
    client.post("/assignments/new", data=assignment_data())
    client.post("/tasks/new", data={"title": "Private", "priority": "Low"})
    upload(client)
    client.get("/aptitude/")  # nothing to protect here, just seeds questions
    client.get("/notifications/")

    ids = {"cls": ClassSchedule.query.one().id, "exam": Exam.query.one().id,
           "asg": Assignment.query.one().id, "task": Task.query.one().id,
           "mat": StudyMaterial.query.one().id}
    attempts = [
        ("get", f"/timetable/{ids['cls']}/edit"), ("post", f"/timetable/{ids['cls']}/delete"),
        ("get", f"/exams/{ids['exam']}/edit"), ("post", f"/exams/{ids['exam']}/delete"),
        ("get", f"/assignments/{ids['asg']}"), ("get", f"/assignments/{ids['asg']}/edit"),
        ("post", f"/assignments/{ids['asg']}/complete"), ("post", f"/assignments/{ids['asg']}/delete"),
        ("get", f"/tasks/{ids['task']}/edit"), ("post", f"/tasks/{ids['task']}/toggle"),
        ("post", f"/tasks/{ids['task']}/delete"),
        ("get", f"/materials/{ids['mat']}/download"), ("post", f"/materials/{ids['mat']}/delete"),
    ]
    for method, url in attempts:
        assert getattr(other_client, method)(url).status_code == 404, url

    # everything is still intact and unchanged
    assert ClassSchedule.query.count() == Exam.query.count() == Assignment.query.count() == 1
    assert Task.query.one().is_completed is False
    assert StudyMaterial.query.count() == 1
    # and the other student's lists are empty
    assert b"Private" not in other_client.get("/tasks/").data


def test_csrf_is_enforced_when_enabled(app):
    app.config["WTF_CSRF_ENABLED"] = True
    c = app.test_client()
    assert c.post("/login", data={"email": "a@b.co", "password": "x"}).status_code == 400
