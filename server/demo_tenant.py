import random
import os
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import hashlib

from server.models import Project, Event, User
from server.auth_users import hash_password

DEMO_USERNAME = "admin"
DEMO_PASSWORD = os.environ.get("VERITAS_DEMO_PASS", "claudecode")

def generate_demo_traffic(db: Session, project_id: str):
    """Seed the database with realistically chronological API calls - REMOVED PER USER REQUEST"""
    pass

def ensure_demo_tenant(db: Session):
    """Ensure the static demo tenant exists and has a real user"""
    user = db.query(User).filter(User.username == DEMO_USERNAME).first()
    if not user:
        user = User(
            username=DEMO_USERNAME,
            password_hash=hash_password(DEMO_PASSWORD),
            created_at=datetime.now(timezone.utc)
        )
        db.add(user)
        db.flush() # flush to get user.id

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
