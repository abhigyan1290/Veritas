import os
import random
import hashlib
from datetime import datetime, timedelta, timezone
from server.database import engine, Base, SessionLocal
from server.models import CloudCostEvent, Project

def seed_demo_tenant():
    print("Initializing Database...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Check if already seeded to prevent duplicates locally
    existing = db.query(CloudCostEvent).filter_by(project_id="demo").count()
    if existing > 0:
        print(f"Skipping seed: Demo tenant already has {existing} events.")
        return

    print("Seeding Demo Tenant: 'demo' project_id...")
    
    # Seed the Project
    project_exists = db.query(Project).filter_by(project_id="demo").first()
    if not project_exists:
        print("Creating 'demo' Project...")
        hashed_key = hashlib.sha256(b"sk-test-demo-123").hexdigest()
        demo_proj = Project(
            project_id="demo",
            name="Demo Tenant",
            api_key_hash=hashed_key,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        db.add(demo_proj)
        db.commit()

    events = []
    
    now = datetime.now(timezone.utc)
    
    # Commit A (Base): Spread across 7 to 4 days ago
    print("Generating events for Commit A (abc123) - claude-3-haiku-20240307 ($0.02/req)")
    for i in range(10):
        days_ago = random.uniform(4, 7)
        timestamp = (now - timedelta(days=days_ago)).isoformat()
        
        events.append(CloudCostEvent(
            project_id="demo",
            feature="chat_search",
            model="claude-3-haiku-20240307",
            tokens_in=500,
            tokens_out=250,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            latency_ms=random.uniform(300, 600),
            cost_usd=0.02,  # Exactly $0.02 narrative
            code_version="abc123",
            timestamp=timestamp,
            status="ok",
            estimated=False
        ))
        
    # Commit B (Target): Spread across 3 to 0 days ago (Model Swap Regression)
    print("Generating events for Commit B (def456) - claude-3-5-sonnet-20241022 ($0.08/req)")
    for i in range(10):
        days_ago = random.uniform(0, 3)
        timestamp = (now - timedelta(days=days_ago)).isoformat()
        
        events.append(CloudCostEvent(
            project_id="demo",
            feature="chat_search",
            model="claude-3-5-sonnet-20241022",
            tokens_in=500,  
            tokens_out=250,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            latency_ms=random.uniform(800, 1500),
            cost_usd=0.08,  # Exactly $0.08 narrative (4x spike)
            code_version="def456",
            timestamp=timestamp,
            status="ok",
            estimated=False
        ))
        
    db.bulk_save_objects(events)
    db.commit()
    db.close()
    
    print("✅ Demo tenant successfully seeded with 20 events!")
    print("Narrative: Model swapped from Claude Sonnet to Claude 3.5 Sonnet, increasing costs 4x.")

if __name__ == "__main__":
    seed_demo_tenant()
