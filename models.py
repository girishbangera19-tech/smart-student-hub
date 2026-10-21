"""Database models. Every student-owned table has a user_id foreign key,
so queries can always be filtered with `user_id=current_user.id`."""
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, login_manager
from utils import now_local


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    college_name = db.Column(db.String(150), nullable=False)
    branch = db.Column(db.String(100), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    scheme = db.Column(db.String(20))
    theme = db.Column(db.String(10), default="light", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class ClassSchedule(db.Model):
    __tablename__ = "class_schedules"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    subject_name = db.Column(db.String(120), nullable=False)
    subject_code = db.Column(db.String(20))
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday ... 5=Saturday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    faculty_name = db.Column(db.String(120))
    room = db.Column(db.String(60))
    notes = db.Column(db.Text)

    user = db.relationship("User", backref=db.backref("classes", cascade="all, delete-orphan"))


class Exam(db.Model):
    __tablename__ = "exams"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    subject_name = db.Column(db.String(120), nullable=False)
    subject_code = db.Column(db.String(20))
    semester = db.Column(db.Integer)
    scheme = db.Column(db.String(20))
    exam_date = db.Column(db.Date, nullable=False)
    session = db.Column(db.String(20))  # Morning / Afternoon
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    venue = db.Column(db.String(120))
    notes = db.Column(db.Text)  # added in Stage 2 (needs a migration)
    # Students enter dates manually, so entries are unverified by default.
    source = db.Column(db.String(200))
    verification_status = db.Column(db.String(20), default="Unverified", nullable=False)
    attachment_filename = db.Column(db.String(255))

    user = db.relationship("User", backref=db.backref("exams", cascade="all, delete-orphan"))

    @property
    def days_remaining(self):
        return (self.exam_date - now_local().date()).days


class Assignment(db.Model):
    __tablename__ = "assignments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    subject_name = db.Column(db.String(120), nullable=False)
    subject_code = db.Column(db.String(20))
    description = db.Column(db.Text)
    assigned_date = db.Column(db.Date)
    deadline = db.Column(db.DateTime, nullable=False)
    priority = db.Column(db.String(10), default="Medium", nullable=False)
    status = db.Column(db.String(20), default="Pending", nullable=False)
    attachment_filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("assignments", cascade="all, delete-orphan"))

    @property
    def is_overdue(self):
        """Overdue = deadline passed AND not completed."""
        return self.status != "Completed" and self.deadline < now_local()


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    due_time = db.Column(db.Time)
    priority = db.Column(db.String(10), default="Medium", nullable=False)
    category = db.Column(db.String(40), default="General")
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("tasks", cascade="all, delete-orphan"))


class StudyMaterial(db.Model):
    __tablename__ = "study_materials"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    subject_name = db.Column(db.String(120), nullable=False)
    subject_code = db.Column(db.String(20))
    scheme = db.Column(db.String(20))
    semester = db.Column(db.Integer)
    module_number = db.Column(db.Integer)
    resource_type = db.Column(db.String(40), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)  # safe random name
    file_size = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship("User", backref=db.backref("materials", cascade="all, delete-orphan"))


class PlacementOpportunity(db.Model):
    """Shared listing. Entries are NOT verified unless an admin marks them so."""
    __tablename__ = "placement_opportunities"

    id = db.Column(db.Integer, primary_key=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    company_name = db.Column(db.String(150), nullable=False)
    job_title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    eligibility = db.Column(db.Text)
    min_cgpa = db.Column(db.Float)
    eligible_branches = db.Column(db.String(200))
    required_skills = db.Column(db.String(300))
    salary_package = db.Column(db.String(60))
    deadline = db.Column(db.Date)
    application_url = db.Column(db.String(500))
    location = db.Column(db.String(100))
    employment_type = db.Column(db.String(40))
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    @property
    def is_expired(self):
        return self.deadline is not None and self.deadline < now_local().date()


class StudentApplication(db.Model):
    """Per-student tracking of a placement opportunity (private to each user)."""
    __tablename__ = "student_applications"
    __table_args__ = (db.UniqueConstraint("user_id", "opportunity_id", name="uq_user_opportunity"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("placement_opportunities.id"), nullable=False)
    status = db.Column(db.String(20), default="Interested", nullable=False)
    notes = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("applications", cascade="all, delete-orphan"))
    opportunity = db.relationship("PlacementOpportunity")


class AptitudeQuestion(db.Model):
    __tablename__ = "aptitude_questions"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(40), nullable=False, index=True)  # Quantitative / Logical / Verbal
    question = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)  # a, b, c or d
    explanation = db.Column(db.Text)


class AptitudeAttempt(db.Model):
    __tablename__ = "aptitude_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category = db.Column(db.String(40), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    taken_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("attempts", cascade="all, delete-orphan"))


class Notification(db.Model):
    __tablename__ = "notifications"
    # dedupe_key stops the same reminder being created again on every refresh.
    __table_args__ = (db.UniqueConstraint("user_id", "dedupe_key", name="uq_user_dedupe"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kind = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(300))
    link = db.Column(db.String(200))
    dedupe_key = db.Column(db.String(100), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship("User", backref=db.backref("notifications", cascade="all, delete-orphan"))
