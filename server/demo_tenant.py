import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
import hashlib

from server.models import Project, Event

def generate_demo_traffic(db: Session, project_id: str):
    """Seed the database with 50 realistic API calls over the last 7 days"""
    
    # Check if we already seeded to avoid duplicates
    existing = db.query(Event).filter(Event.project_id == project_id).count()
    if existing > 0:
        return

    features = ["chat_search", "doc_summary", "code_gen"]
    models = ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]
    
    now = datetime.now(timezone.utc)
    
    events = []
    # Seed older "stable" events
    for i in range(40):
        # Sprinkle them randomly over the last week
        days_ago = random.uniform(1, 7)
        timestamp = (now - timedelta(days=days_ago)).isoformat()
        
        feature = random.choice(features)
        model = random.choice(models)
        
        # Base latency around 2-4 seconds
        latency = random.uniform(2000, 4500)
        
        # Stable cost metrics
        tokens_in = random.randint(100, 800)
        tokens_out = random.randint(50, 400)
        cost_usd = (tokens_in * 3.0 / 1_000_000) + (tokens_out * 15.0 / 1_000_000)
        
        events.append(Event(
            project_id=project_id,
            feature=feature,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency,
            cost_usd=cost_usd,
            code_version="8f4b23c", # The "old" stable commit
            timestamp=timestamp,
            status="ok"
        ))
        
    # Seed 10 recent events representing the "New Spike"
    for i in range(10):
        hours_ago = random.uniform(0.1, 2)
        timestamp = (now - timedelta(hours=hours_ago)).isoformat()
        
        feature = random.choice(features)
        model = random.choice(models)
        
        latency = random.uniform(4000, 8000) # Slower
        
        # The spike: much higher output tokens
        tokens_in = random.randint(100, 800)
        tokens_out = random.randint(1500, 3000) 
        cost_usd = (tokens_in * 3.0 / 1_000_000) + (tokens_out * 15.0 / 1_000_000)
        
        events.append(Event(
            project_id=project_id,
            feature=feature,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency,
            cost_usd=cost_usd,
            code_version="a1b2c3d", # The "new" regression commit
            timestamp=timestamp,
            status="ok"
        ))
        
    db.bulk_save_objects(events)
    db.commit()

def ensure_demo_tenant(db: Session):
    """Ensure the static demo tenant 'beach_app' exists"""
    project = db.query(Project).filter(Project.id == "beach_app").first()
    if not project:
        demo_key_hash = hashlib.sha256("sk-vrt-demo-local".encode()).hexdigest()
        p = Project(
            id="beach_app",
            name="Beach Guesser UI",
            created_at=datetime.now(timezone.utc),
            api_key_hash=demo_key_hash
        )
        db.add(p)
        db.commit()
