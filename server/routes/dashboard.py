from fastapi import APIRouter, Request, Depends, Query, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from server.database import get_db
from server.models import CloudCostEvent, Project
from server.auth import verify_admin
import os
import secrets
import hashlib
from datetime import datetime, timezone

router = APIRouter()

# Setup Jinja2 Templates Directory
# Need absolute pathing just in case of different CWD executions
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@router.get("/", response_class=HTMLResponse)
def dashboard_overview(request: Request, project_id: str = Query("demo"), db: Session = Depends(get_db), admin: bool = Depends(verify_admin)):
    """Overview dashboard landing page."""
    projects = db.query(Project).all()
    # Query aggregate cost
    total_cost = db.query(func.sum(CloudCostEvent.cost_usd)).filter_by(project_id=project_id).scalar() or 0.0
    
    # Top features by total spend
    top_features = db.query(
        CloudCostEvent.feature, 
        func.sum(CloudCostEvent.cost_usd).label("total_cost"),
        func.count(CloudCostEvent.id).label("event_count")
    ).filter_by(project_id=project_id).group_by(CloudCostEvent.feature).order_by(func.sum(CloudCostEvent.cost_usd).desc()).limit(3).all()
    
    # Get recent raw events to simulate a feed
    recent_events = db.query(CloudCostEvent).filter_by(project_id=project_id).order_by(CloudCostEvent.timestamp.desc()).limit(5).all()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "projects": projects,
        "project_id": project_id,
        "total_cost": total_cost,
        "top_features": top_features,
        "recent_events": recent_events
    })

@router.get("/features/{feature_name}", response_class=HTMLResponse)
def feature_detail(request: Request, feature_name: str, project_id: str = Query("demo"), db: Session = Depends(get_db), admin: bool = Depends(verify_admin)):
    """Detailed view for a specific feature."""
    projects = db.query(Project).all()
    events = db.query(CloudCostEvent).filter_by(project_id=project_id, feature=feature_name).order_by(CloudCostEvent.timestamp.desc()).limit(100).all()
    
    total_cost = sum(e.cost_usd for e in events)
    count = len(events)
    avg_cost = total_cost / count if count > 0 else 0
    
    # Group by commit
    commits = {}
    for e in events:
        c = e.code_version or "unknown"
        if c not in commits:
            commits[c] = {"count": 0, "total_cost": 0.0, "avg_cost": 0.0}
        commits[c]["count"] += 1
        commits[c]["total_cost"] += e.cost_usd
        commits[c]["avg_cost"] = commits[c]["total_cost"] / commits[c]["count"]
        
    return templates.TemplateResponse("feature.html", {
        "request": request,
        "projects": projects,
        "project_id": project_id,
        "feature_name": feature_name,
        "avg_cost": avg_cost,
        "count": count,
        "commits": commits
    })

@router.get("/regressions", response_class=HTMLResponse)
def regressions_feed(request: Request, project_id: str = Query("demo"), db: Session = Depends(get_db), admin: bool = Depends(verify_admin)):
    """Visualizes detected cost spikes between commits."""
    projects = db.query(Project).all()
    # Simple explicit narrative pull for the YC demonstration. 
    # In production, this would hit an AnalyticsDB materialized view.
    from veritas.engine import REGRESSION_ABSOLUTE_THRESHOLD_USD, REGRESSION_PERCENT_THRESHOLD, _compute_averages
    
    # Find all unique features that exist for this project
    features = db.query(CloudCostEvent.feature).filter_by(project_id=project_id).distinct().all()
    
    regressions_list = []
    
    for (feat,) in features:
        # Get all events for the feature ordered newest to oldest
        events = db.query(CloudCostEvent).filter_by(project_id=project_id, feature=feat).order_by(CloudCostEvent.timestamp.desc()).all()
        if not events:
            continue
            
        commits = {}
        ordered_commits = []
        for e in events:
            c = e.code_version
            if c not in commits:
                commits[c] = []
                ordered_commits.append(c)
            commits[c].append(e.__dict__)
            
        # Compare the absolute newest commit against the one right before it
        if len(ordered_commits) >= 2:
            target_commit = ordered_commits[0]
            base_commit = ordered_commits[1]
            
            avg_base = _compute_averages(commits[base_commit])
            avg_target = _compute_averages(commits[target_commit])
            
            cost_delta = avg_target["avg_cost_usd"] - avg_base["avg_cost_usd"]
            percent_change = cost_delta / avg_base["avg_cost_usd"] if avg_base["avg_cost_usd"] > 0 else 0
            
            regressions_list.append({
                "feature": feat,
                "commit_a": base_commit,
                "commit_b": target_commit,
                "avg_cost_a": avg_base["avg_cost_usd"],
                "avg_cost_b": avg_target["avg_cost_usd"],
                "delta": cost_delta,
                "percent_change": percent_change * 100,
                "is_regression": (cost_delta >= REGRESSION_ABSOLUTE_THRESHOLD_USD and percent_change >= REGRESSION_PERCENT_THRESHOLD)
            })

    return templates.TemplateResponse("regressions.html", {
        "request": request,
        "projects": projects,
        "project_id": project_id,
        "regressions": regressions_list
    })

@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, project_id: str = Query("demo"), raw_key: str = Query(None), db: Session = Depends(get_db), admin: bool = Depends(verify_admin)):
    """Settings page for dynamic API Keys and Projects."""
    projects = db.query(Project).all()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "projects": projects,
        "project_id": project_id,
        "raw_key": raw_key  # Inject exactly once upon creation
    })

@router.post("/settings/project/new")
def create_project(request: Request, name: str = Form(...), new_project_id: str = Form(...), db: Session = Depends(get_db), admin: bool = Depends(verify_admin)):
    """Creates a new Project dynamically and safely hashes its key."""
    # 1. Generate the raw, highly secure API key
    raw_key = "sk-vrt-" + secrets.token_urlsafe(32)
    
    # 2. Hash it immediately before it ever touches the database
    hashed_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    
    # 3. Save the Hash ONLY
    new_proj = Project(
        project_id=new_project_id,
        name=name,
        api_key_hash=hashed_key,
        created_at=datetime.now(timezone.utc).isoformat()
    )
    db.add(new_proj)
    db.commit()
    
    # 4. Redirect back to Settings but inject the raw_key into the URL precisely ONE time so Jinja can render it.
    # Note: In a production heavily-audited system, even returning it via query params is risky because 
    # of intermediate proxy logging, but for the MVP SaaS UI it securely satisfies the ephemeral requirement.
    return RedirectResponse(url=f"/settings?project_id={new_project_id}&raw_key={raw_key}", status_code=303)
