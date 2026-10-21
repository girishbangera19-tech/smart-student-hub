"""Shared pytest fixtures: a fresh in-memory database for every test."""
import sys
from pathlib import Path

import pytest

# Let tests import app.py, models.py, etc. from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from config import TestingConfig  # noqa: E402
from extensions import db  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    class Cfg(TestingConfig):
        UPLOAD_FOLDER = str(tmp_path / "uploads")

    app = create_app(Cfg)
    with app.app_context():
        db.create_all()  # tests only; the real app uses migrations
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


REGISTER_DATA = {
    "full_name": "Asha Rao",
    "email": "asha@example.com",
    "password": "password123",
    "confirm_password": "password123",
    "college_name": "Test Institute of Technology",
    "branch": "Computer Science & Engineering",
    "semester": "5",
    "scheme": "2022",
}


@pytest.fixture()
def register(client):
    def _register(**overrides):
        data = {**REGISTER_DATA, **overrides}
        return client.post("/register", data=data)
    return _register


@pytest.fixture()
def login(client):
    def _login(email="asha@example.com", password="password123"):
        return client.post("/login", data={"email": email, "password": password})
    return _login
