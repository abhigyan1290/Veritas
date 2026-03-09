from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from server.database import get_db
from server.models import CloudCostEvent
from server.schemas import CostEventCreate
from server.auth import get_current_project

router = APIRouter()

@router.post("/events", status_code=201)
def ingest_events(
    events: List[CostEventCreate],
    project_id: str = Depends(get_current_project),
    db: Session = Depends(get_db)
):
    """Ingest a batch of cost events via the REST API."""
    db_events = []
    for event in events:
        db_events.append(CloudCostEvent(
            project_id=project_id,
            feature=event.feature,
            model=event.model,
            tokens_in=event.tokens_in,
            tokens_out=event.tokens_out,
            cache_creation_tokens=event.cache_creation_tokens,
            cache_read_tokens=event.cache_read_tokens,
            latency_ms=event.latency_ms,
            cost_usd=event.cost_usd,
            code_version=event.code_version,
            timestamp=event.timestamp,
            status=event.status,
            estimated=event.estimated
        ))
    
    # Fast bulk insertion for CI runner latency optimization
    db.bulk_save_objects(db_events)
    db.commit()
    
    return {"status": "ok", "inserted": len(db_events)}
