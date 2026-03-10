import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import hashlib

from server.models import Project, Event

def generate_demo_traffic(db: Session, project_id: str):
    """Seed the database with realistically chronological API calls - REMOVED PER USER REQUEST"""
    pass

def ensure_demo_tenant(db: Session):
    """Ensure the static demo tenant exists"""
    project = db.query(Project).filter(Project.id == "demo").first()
    if not project:
        p = Project(
            id="demo",
            name="Demo Project",
            created_at=datetime.now(timezone.utc),
            api_key_hash=hashlib.sha256("sk-vrt-demo".encode()).hexdigest()
        )
        db.add(p)
        db.commit()
