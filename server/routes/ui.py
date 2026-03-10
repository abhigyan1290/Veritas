from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from server.database import get_db
from server.models import Project, Event
from server.auth import verify_admin
from server.demo_tenant import ensure_demo_tenant, generate_demo_traffic

router = APIRouter()
templates = Jinja2Templates(directory="server/templates")

@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """The main Veritas Cloud Dashboard"""
    ensure_demo_tenant(db)
    
    # Global metrics
    total_events = db.query(Event).count()
    if total_events == 0:
        # Generate some fake demo traffic if empty
        generate_demo_traffic(db, project_id="beach_app")
        
    total_cost = db.query(func.sum(Event.cost_usd)).scalar() or 0.0
    total_tokens = db.query(func.sum(Event.tokens_in + Event.tokens_out)).scalar() or 0
    total_latency = db.query(func.avg(Event.latency_ms)).scalar() or 0.0

    projects = db.query(Project).all()
    recent_events = db.query(Event).order_by(Event.id.desc()).limit(15).all()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "total_cost": total_cost,
            "total_events": total_events,
            "total_tokens": total_tokens,
            "avg_latency": total_latency,
            "projects": projects,
            "events": recent_events
        }
    )

@router.get("/regressions", response_class=HTMLResponse)
def regressions(
    request: Request,
    project_id: str = "beach_app",
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """A regression tracking route that compares commit A vs commit B."""
    
    # Here we simulate fetching the average cost per feature across the last two known commits
    # For a real implementation, we'd dynamically query the two most recent `code_version` values
    # Grouping logic simulation 
    
    # Find all unique commits for this project
    commits = [r[0] for r in db.query(Event.code_version).filter(Event.project_id == project_id).distinct().all() if r[0]]
    
    insights = []
    
    if len(commits) >= 2:
        latest = commits[-1]
        previous = commits[-2]
        
        # Calculate averge cost for the latest commit
        latest_avg = db.query(func.avg(Event.cost_usd)).filter(Event.project_id == project_id, Event.code_version == latest).scalar() or 0.0
        prev_avg = db.query(func.avg(Event.cost_usd)).filter(Event.project_id == project_id, Event.code_version == previous).scalar() or 0.0
        
        diff = latest_avg - prev_avg
        diff_pct = 0
        if prev_avg > 0:
            diff_pct = (diff / prev_avg) * 100
            
        is_regression = diff > 0.001 # 1/10th of a cent threshold
        
        insights.append({
            "feature": "Cost per Request",
            "prev_commit": previous,
            "latest_commit": latest,
            "prev_val": prev_avg,
            "latest_val": latest_avg,
            "diff": diff,
            "diff_pct": diff_pct,
            "is_regression": is_regression
        })

    return templates.TemplateResponse(
        "regressions.html",
        {
            "request": request,
            "project_id": project_id,
            "insights": insights
        }
    )

@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, project_id: str = None, raw_key: str = None):
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "project_id": project_id,
            "raw_key": raw_key
        }
    )
