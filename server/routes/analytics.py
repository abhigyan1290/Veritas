import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func

from server.database import SessionLocal
from server.models import Project, Event, User

router = APIRouter()
templates = Jinja2Templates(directory="server/templates")


@router.get("/analytics/features", response_class=HTMLResponse)
def analytics_features(request: Request):
    current_user: User = request.state.current_user
    db = SessionLocal()
    try:
        projects = db.query(Project).filter(Project.user_id == current_user.id).all()

        raw_pid = request.query_params.get("project_id")
        if raw_pid and projects:
            owned = next((p for p in projects if p.id == raw_pid), None)
            project_id = owned.id if owned else projects[0].id
        elif projects:
            project_id = projects[0].id
        else:
            project_id = None

        feature_rows = []
        total_project_cost = 0.0

        if project_id:
            # All event queries join through Project to enforce ownership
            owned_events = (
                db.query(Event)
                .join(Project, Event.project_id == Project.id)
                .filter(Project.user_id == current_user.id, Event.project_id == project_id)
            )

            total_project_cost = owned_events.with_entities(
                func.coalesce(func.sum(Event.cost_usd), 0.0)
            ).scalar() or 0.0

            rows = (
                owned_events.with_entities(
                    Event.feature,
                    func.coalesce(func.sum(Event.cost_usd), 0.0).label("total_cost"),
                    func.count(Event.id).label("call_count"),
                    func.coalesce(func.avg(Event.latency_ms), 0.0).label("avg_latency_ms"),
                    func.coalesce(func.sum(Event.tokens_in + Event.tokens_out), 0).label("total_tokens"),
                )
                .group_by(Event.feature)
                .order_by(func.sum(Event.cost_usd).desc())
                .all()
            )

            error_counts_raw = (
                owned_events.with_entities(Event.feature, func.count(Event.id).label("error_count"))
                .filter(Event.status != "ok")
                .group_by(Event.feature)
                .all()
            )
            error_map = {r.feature: r.error_count for r in error_counts_raw}

            for r in rows:
                call_count = r.call_count or 1
                avg_cost = r.total_cost / call_count if r.call_count else 0.0
                share_pct = (r.total_cost / total_project_cost * 100) if total_project_cost > 0 else 0.0
                feature_rows.append({
                    "feature": r.feature or "unknown",
                    "total_cost": r.total_cost,
                    "call_count": r.call_count,
                    "avg_cost_per_call": avg_cost,
                    "avg_latency_ms": r.avg_latency_ms,
                    "total_tokens": r.total_tokens,
                    "error_count": error_map.get(r.feature, 0),
                    "share_pct": share_pct,
                })

        return templates.TemplateResponse("analytics_features.html", {
            "request": request,
            "project_id": project_id,
            "projects": projects,
            "current_user": current_user,
            "user": current_user,
            "feature_rows": feature_rows,
            "total_project_cost": total_project_cost,
        })
    finally:
        db.close()


@router.get("/analytics/models", response_class=HTMLResponse)
def analytics_models(request: Request):
    current_user: User = request.state.current_user
    db = SessionLocal()
    try:
        projects = db.query(Project).filter(Project.user_id == current_user.id).all()

        raw_pid = request.query_params.get("project_id")
        if raw_pid and projects:
            owned = next((p for p in projects if p.id == raw_pid), None)
            project_id = owned.id if owned else projects[0].id
        elif projects:
            project_id = projects[0].id
        else:
            project_id = None

        model_rows = []
        chart_labels = []
        chart_values = []

        if project_id:
            # JOIN through Project to enforce ownership
            owned_events = (
                db.query(Event)
                .join(Project, Event.project_id == Project.id)
                .filter(Project.user_id == current_user.id, Event.project_id == project_id)
            )
            rows = (
                owned_events.with_entities(
                    Event.model,
                    func.coalesce(func.sum(Event.cost_usd), 0.0).label("total_cost"),
                    func.count(Event.id).label("call_count"),
                    func.coalesce(func.sum(Event.tokens_in), 0).label("total_tokens_in"),
                    func.coalesce(func.sum(Event.tokens_out), 0).label("total_tokens_out"),
                )
                .group_by(Event.model)
                .order_by(func.sum(Event.cost_usd).desc())
                .all()
            )

            for r in rows:
                call_count = r.call_count or 1
                avg_cost = r.total_cost / call_count if r.call_count else 0.0
                total_tokens = (r.total_tokens_in or 0) + (r.total_tokens_out or 0)
                model_rows.append({
                    "model": r.model or "unknown",
                    "total_cost": r.total_cost,
                    "call_count": r.call_count,
                    "avg_cost_per_call": avg_cost,
                    "total_tokens_in": r.total_tokens_in or 0,
                    "total_tokens_out": r.total_tokens_out or 0,
                    "total_tokens": total_tokens,
                })

            chart_labels = [m["model"] for m in model_rows]
            chart_values = [round(m["total_cost"], 6) for m in model_rows]

        return templates.TemplateResponse("analytics_models.html", {
            "request": request,
            "project_id": project_id,
            "projects": projects,
            "current_user": current_user,
            "user": current_user,
            "model_rows": model_rows,
            "chart_labels_json": json.dumps(chart_labels),
            "chart_values_json": json.dumps(chart_values),
        })
    finally:
        db.close()
