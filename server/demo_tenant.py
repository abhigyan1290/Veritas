import os
import hashlib
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from server.models import Project, User
from server.auth_users import hash_password, verify_password

# Admin credentials — set in Railway environment variables
ADMIN_USERNAME = os.environ.get("VERITAS_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("VERITAS_ADMIN_PASS", "changeme")


def generate_demo_traffic(db, project_id: str):
    """Stub — demo traffic generation removed."""
    pass


def ensure_demo_tenant(db: Session):
    """
    Ensure the admin user and demo project exist. Safe to call on every boot.

    - Creates admin user if missing.
    - Only re-hashes password when VERITAS_ADMIN_PASS env var has changed
      (verified via bcrypt check), avoiding a full bcrypt hash on every restart.
    """
    user = db.query(User).filter(User.username == ADMIN_USERNAME).first()

    if not user:
        user = User(
            username=ADMIN_USERNAME,
            password_hash=hash_password(ADMIN_PASSWORD),
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not verify_password(ADMIN_PASSWORD, user.password_hash):
        # Password env var changed — update the stored hash
        user.password_hash = hash_password(ADMIN_PASSWORD)
        db.commit()

    # Ensure demo project is owned by admin
    project = db.query(Project).filter(Project.id == "demo").first()
    if not project:
        db.add(Project(
            id="demo",
            name="Demo Project",
            created_at=datetime.now(timezone.utc),
            api_key_hash=hashlib.sha256("sk-vrt-demo".encode()).hexdigest(),
            user_id=user.id,
        ))
        db.commit()
    elif project.user_id != user.id:
        project.user_id = user.id
        db.commit()
