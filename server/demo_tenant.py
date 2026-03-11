import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import hashlib

from server.models import Project, Event, User
from server.auth_users import hash_password

def generate_demo_traffic(db, project_id: str):
    """Stub — demo traffic generation removed per user request."""
    pass


DEMO_USERNAME = "admin"
DEMO_PASSWORD = os.environ.get("VERITAS_DEMO_PASS", "claudecode")

def ensure_demo_tenant(db: Session):
    """Ensure the admin user and demo project exist. Runs on every boot.

    This is the recovery mechanism: if the database gets wiped (e.g. Railway
    redeploy, free-tier reset), the next boot automatically re-creates admin.
    The password hash is refreshed from the VERITAS_DEMO_PASS env var each time.
    """
    current_hash = hash_password(DEMO_PASSWORD)

    user = db.query(User).filter(User.username == DEMO_USERNAME).first()
    if not user:
        user = User(
            username=DEMO_USERNAME,
            password_hash=current_hash,
            created_at=datetime.now(timezone.utc)
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Refresh hash in case VERITAS_DEMO_PASS env var changed
        user.password_hash = current_hash
        db.commit()

    # Ensure demo project exists and is owned by admin
    project = db.query(Project).filter(Project.id == "demo").first()
    if not project:
        p = Project(
            id="demo",
            name="Demo Project",
            created_at=datetime.now(timezone.utc),
            api_key_hash=hashlib.sha256("sk-vrt-demo".encode()).hexdigest(),
            user_id=user.id
        )
        db.add(p)
        db.commit()
    elif project.user_id != user.id:
        project.user_id = user.id
        db.commit()
