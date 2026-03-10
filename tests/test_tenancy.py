import pytest
from fastapi.testclient import TestClient
from server.database import Base, engine, SessionLocal
from server.models import User, Project
from server.auth_users import hash_password, create_session_token
from server.main import app

# Ensure clean db for tests
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_user_a_cannot_see_user_b_events(client, db):
    # Setup User A
    user_a = User(email="a@test.com", password_hash=hash_password("test"))
    db.add(user_a)
    db.commit()
    token_a = create_session_token(user_a.id)
    
    # Create project for User A
    client.cookies.set("veritas_session", token_a)
    res = client.post("/settings/project/new", data={"project_name": "Project A"}, follow_redirects=True)
    assert res.status_code == 200
    
    project_a = db.query(Project).filter(Project.user_id == user_a.id).first()
    assert project_a is not None
    
    # Send event for User A via ingest API (bypassing dashboard cookie, using bearer)
    event_payload = {
        "feature": "search_a",
        "model": "claude-3-haiku-20240307",
        "tokens_in": 100,
        "tokens_out": 50,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "latency_ms": 150.0,
        "cost_usd": 0.001,
        "code_version": "rev1",
        "timestamp": "2024-03-01T12:00:00Z",
        "status": "ok",
        "estimated": False
    }
    # But wait, we need the raw api key to ingest. We know how it's stored and bypassed...
    # Actually, we can just insert the event directly for A to be fast:
    from server.models import Event
    db.add(Event(project_id=project_a.id, **event_payload))
    db.commit()
    
    # Verify User A can see their event
    dash_a = client.get(f"/?project_id={project_a.id}")
    assert "search_a" in dash_a.text
    
    # Setup User B
    user_b = User(email="b@test.com", password_hash=hash_password("test"))
    db.add(user_b)
    db.commit()
    token_b = create_session_token(user_b.id)
    
    # Log in as User B
    client.cookies.set("veritas_session", token_b)
    
    # Verify User B cannot see User A's project or event even if they try to pass the ID
    dash_b = client.get(f"/?project_id={project_a.id}")
    assert "search_a" not in dash_b.text
    assert "Project A" not in dash_b.text
    
    # Verify regressions isolating
    reg_b = client.get(f"/regressions?project_id={project_a.id}")
    assert "search_a" not in reg_b.text
