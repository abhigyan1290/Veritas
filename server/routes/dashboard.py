from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid
import hashlib
from datetime import datetime, timezone

from server.database import get_db
from server.models import Project, Event
from server.demo_tenant import ensure_demo_tenant
import json
from typing import Optional

router = APIRouter()
templates = Jinja2Templates(directory="server/templates")

def get_projects(db: Session, user_id: str):
    return db.query(Project).filter(Project.user_id == user_id).all()

@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    project_id: str = "demo",
    db: Session = Depends(get_db)
):
    ensure_demo_tenant(db)
    current_user = request.state.current_user
        
    projects = get_projects(db, current_user.id)
        
    events_query = (
        db.query(Event)
        .join(Project, Event.project_id == Project.id)
        .filter(Project.user_id == current_user.id, Event.project_id == project_id)
    )
    total_events = events_query.count()
    total_cost = events_query.with_entities(func.sum(Event.cost_usd)).scalar() or 0.0
    total_tokens = events_query.with_entities(func.sum(Event.tokens_in + Event.tokens_out)).scalar() or 0
    avg_latency = events_query.with_entities(func.avg(Event.latency_ms)).scalar() or 0.0

    recent_events = events_query.order_by(Event.timestamp.desc()).limit(15).all()

    commit_rows = (
        db.query(Event.code_version, func.avg(Event.cost_usd).label("avg_cost"))
        .join(Project, Event.project_id == Project.id)
        .filter(Project.user_id == current_user.id, Event.project_id == project_id, Event.code_version != None, Event.code_version != "")
        .group_by(Event.code_version)
        .order_by(func.max(Event.timestamp).asc())
        .all()
    )
    chart_labels = [r[0][:7] if r[0] else "unknown" for r in commit_rows]
    chart_values = [round(r[1], 6) for r in commit_rows]
    chart_data = json.dumps({"labels": chart_labels, "values": chart_values})

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "project_id": project_id,
            "projects": projects,
            "total_cost": total_cost,
            "total_events": total_events,
            "total_tokens": total_tokens,
            "avg_latency": avg_latency,
            "events": recent_events,
            "chart_data": chart_data,
            "user": current_user,
        }
    )

@router.get("/features/{name}", response_class=HTMLResponse)
def feature_breakdown(
    request: Request,
    name: str,
    project_id: str = "demo",
    db: Session = Depends(get_db)
):
    current_user = request.state.current_user
    projects = get_projects(db, current_user.id)
    
    events_query = (
        db.query(Event)
        .join(Project, Event.project_id == Project.id)
        .filter(Project.user_id == current_user.id, Event.project_id == project_id, Event.feature == name)
    )
    avg_cost = events_query.with_entities(func.avg(Event.cost_usd)).scalar() or 0.0
    total_cost = events_query.with_entities(func.sum(Event.cost_usd)).scalar() or 0.0
    events = events_query.order_by(Event.timestamp.desc()).limit(50).all()
    
    return templates.TemplateResponse(
        "feature.html",
        {
            "request": request,
            "project_id": project_id,
            "projects": projects,
            "feature_name": name,
            "avg_cost": avg_cost,
            "total_cost": total_cost,
            "events": events,
            "user": current_user,
        }
    )

@router.get("/regressions", response_class=HTMLResponse)
def regressions(
    request: Request,
    project_id: str = "demo",
    db: Session = Depends(get_db)
):
    current_user = request.state.current_user
    projects = get_projects(db, current_user.id)
    
    # Get distinct commits ordered by the MOST RECENT event timestamp for that commit.
    # This ensures latest = the newest commit, previous = the one before it.
    commit_rows = (
        db.query(Event.code_version, func.max(Event.timestamp).label("last_seen"))
        .join(Project, Event.project_id == Project.id)
        .filter(Project.user_id == current_user.id, Event.project_id == project_id, Event.code_version != None, Event.code_version != "")
        .group_by(Event.code_version)
        .order_by(func.max(Event.timestamp).asc())
        .all()
    )
    commits = [r[0] for r in commit_rows]
    insights = []
    
    if len(commits) >= 2:
        previous = commits[-2]   # second-most-recent commit
        latest = commits[-1]     # most recent commit
        
        features = [r[0] for r in (
            db.query(Event.feature)
            .join(Project, Event.project_id == Project.id)
            .filter(Project.user_id == current_user.id, Event.project_id == project_id)
            .distinct()
            .all()
        )]
        
        for feature in features:
            latest_avg = (
                db.query(func.avg(Event.cost_usd))
                .join(Project, Event.project_id == Project.id)
                .filter(Project.user_id == current_user.id, Event.project_id == project_id, Event.code_version == latest, Event.feature == feature)
                .scalar() or 0.0
            )
            prev_avg = (
                db.query(func.avg(Event.cost_usd))
                .join(Project, Event.project_id == Project.id)
                .filter(Project.user_id == current_user.id, Event.project_id == project_id, Event.code_version == previous, Event.feature == feature)
                .scalar() or 0.0
            )
            
            diff = latest_avg - prev_avg
            diff_pct = ((diff / prev_avg) * 100) if prev_avg > 0 else 0
            
            # Show all features, not just expensive regressions
            if latest_avg > 0 or prev_avg > 0:
                insights.append({
                    "feature": feature,
                    "prev_commit": previous,
                    "latest_commit": latest,
                    "prev_val": prev_avg,
                    "latest_val": latest_avg,
                    "diff": diff,
                    "diff_pct": diff_pct,
                    "is_regression": diff > 0
                })

    return templates.TemplateResponse(
        "regressions.html",
        {
            "request": request,
            "project_id": project_id,
            "projects": projects,
            "commits": commits,
            "insights": insights,
            "user": current_user,
        }
    )

@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    project_id: str = "demo",
    raw_key: Optional[str] = None,
    db: Session = Depends(get_db)
):
    current_user = request.state.current_user
    projects = get_projects(db, current_user.id)
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "project_id": project_id,
            "projects": projects,
            "raw_key": raw_key,
            "user": current_user,
        }
    )

@router.post("/settings/project/new")
def form_create_project(
    request: Request,
    project_name: str = Form(...),
    db: Session = Depends(get_db)
):
    from server.routes.ingest import create_project
    from server.schemas import ProjectCreateSchema
    from fastapi import HTTPException
    
    current_user = request.state.current_user
    try:
        result = create_project(ProjectCreateSchema(name=project_name), db=db, user_id=current_user.id)
    except HTTPException as e:
        # Redirect back with a user-friendly error (e.g. duplicate project name)
        from urllib.parse import quote
        return RedirectResponse(
            url=f"/settings?error={quote(e.detail)}",
            status_code=303
        )
    
    return RedirectResponse(
        url=f"/settings?project_id={result['id']}&raw_key={result['raw_key']}", 
        status_code=303
    )
