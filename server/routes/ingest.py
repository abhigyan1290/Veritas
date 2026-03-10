from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
import hashlib

from server.database import get_db
from server.models import Project, Event
from server.schemas import CostEventSchema, ProjectCreateSchema, ProjectSettingResponse
from server.auth import verify_api_key

router = APIRouter()

@router.delete("/events")
def reset_events(
    project_id: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """
    Delete all events for the authenticated project.
    This is a destructive operation — intended only for demo resets.
    Protected by the same Bearer token as event ingestion.
    """
    deleted = db.query(Event).filter(Event.project_id == project_id).delete()
    db.commit()
    return {"status": "ok", "deleted": deleted}

@router.post("/events")
def ingest_event(
    event_in: CostEventSchema, 
    project_id: str = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """
    Ingest a new CostEvent from an SDK client. 
    Protected by Bearer token authentication.
    """
    try:
        db_event = Event(
            project_id=project_id,
            feature=event_in.feature,
            model=event_in.model,
            tokens_in=event_in.tokens_in,
            tokens_out=event_in.tokens_out,
            cache_creation_tokens=event_in.cache_creation_tokens,
            cache_read_tokens=event_in.cache_read_tokens,
            latency_ms=event_in.latency_ms,
            cost_usd=event_in.cost_usd,
            code_version=event_in.code_version,
            timestamp=event_in.timestamp,
            status=event_in.status,
            estimated=event_in.estimated
        )
        db.add(db_event)
        db.commit()
        return {"status": "ok"}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to ingest event.")


@router.post("/projects", response_model=ProjectSettingResponse)
def create_project(data: ProjectCreateSchema, db: Session = Depends(get_db), user_id: str = None):
    """
    Create a new project workspace and generate an API key.
    Returns the raw API key EXACTLY ONCE.
    """
    project_id = data.name.lower().replace(" ", "_")
    
    # Generate a secure API Key
    raw_api_key = f"sk-vrt-{uuid.uuid4().hex}"
    api_key_hash = hashlib.sha256(raw_api_key.encode()).hexdigest()
    
    # Store only the hash
    db_project = Project(
        id=project_id,
        name=data.name,
        created_at=datetime.now(timezone.utc),
        api_key_hash=api_key_hash,
        user_id=user_id
    )
    try:
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Project already exists")
        
    return {
        "id": db_project.id,
        "name": db_project.name,
        "created_at": db_project.created_at,
        "has_api_key": True,
        # WE ONLY RETURN THIS ONCE
        "raw_key": raw_api_key 
    }
