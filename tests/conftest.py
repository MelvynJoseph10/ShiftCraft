import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import User, UserRole

TEST_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./test.db")

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _seed_user(name, email, password, role, employee_role=None):
    db = TestingSessionLocal()
    try:
        user = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role=role,
            employee_role=employee_role,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def manager_token(client):
    _seed_user("Manager User", "manager@test.com", "managerpass", UserRole.manager)
    resp = client.post("/auth/login", json={"email": "manager@test.com", "password": "managerpass"})
    return resp.json()["access_token"]


@pytest.fixture
def employee_token(client, manager_token):
    _seed_user("Employee User", "employee@test.com", "employeepass", UserRole.employee, "junior")
    resp = client.post("/auth/login", json={"email": "employee@test.com", "password": "employeepass"})
    return resp.json()["access_token"]
