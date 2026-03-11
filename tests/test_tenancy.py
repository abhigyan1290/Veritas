"""
Multi-tenant isolation tests.

CRITICAL: These tests use an isolated in-memory SQLite database so they
NEVER touch the production Postgres database. The module-level drop_all
that existed previously has been removed — it was a data-loss hazard.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.database import Base, get_db
from server.models import User, Project, Event
from server.auth_users import hash_password, create_session_token
from server.main import app

# Isolated in-memory SQLite — never touches production
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create fresh tables before each test, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_user_a_cannot_see_user_b_events(client, db):
    """User B must not see User A's projects or events, even with explicit project_id."""
    # --- Setup User A ---
    user_a = User(username="a_test", password_hash=hash_password("test"))
    db.add(user_a)
    db.commit()
    token_a = create_session_token(user_a.id)

    # Create project for User A directly in the test DB (avoids startup DB complexity)
    import hashlib, uuid as _uuid
    from datetime import datetime, timezone
    project_a = Project(
        id="project_a_test",
        name="Project A",
        user_id=user_a.id,
        api_key_hash=hashlib.sha256(_uuid.uuid4().hex.encode()).hexdigest(),
        created_at=datetime.now(timezone.utc),
    )
    db.add(project_a)
    db.commit()

    assert project_a is not None
    client.cookies.set("veritas_session", token_a)

    # Insert an event for User A directly
    db.add(Event(
        project_id=project_a.id,
        feature="search_a",
        model="claude-3-haiku-20240307",
        tokens_in=100,
        tokens_out=50,
        cache_creation_tokens=0,
        cache_read_tokens=0,
        latency_ms=150.0,
        cost_usd=0.001,
        code_version="rev1",
        timestamp="2024-03-01T12:00:00Z",
        status="ok",
        estimated=False
    ))
    db.commit()

    # Verify User A's dashboard loads successfully (200)
    client.cookies.set("veritas_session", token_a)
    dash_a = client.get(f"/?project_id={project_a.id}")
    assert dash_a.status_code == 200

    # --- Setup User B ---
    user_b = User(username="b_test", password_hash=hash_password("test"))
    db.add(user_b)
    db.commit()
    token_b = create_session_token(user_b.id)

    # Log in as User B and try to view User A's project
    client.cookies.set("veritas_session", token_b)
    dash_b = client.get(f"/?project_id={project_a.id}")
    assert "search_a" not in dash_b.text
    assert "Project A" not in dash_b.text

    # User B's regressions should also be empty
    reg_b = client.get(f"/regressions?project_id={project_a.id}")
    assert "search_a" not in reg_b.text
