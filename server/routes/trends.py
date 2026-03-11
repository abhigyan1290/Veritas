from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta, timezone
import json

from server.database import SessionLocal
from server.models import Project, Event, User

router = APIRouter()
templates = Jinja2Templates(directory="server/templates")


@router.get("/trends", response_class=HTMLResponse)
def trends(request: Request):
    current_user: User = request.state.current_user
    db = SessionLocal()
    try:
        projects = db.query(Project).filter(Project.user_id == current_user.id).all()

        # Resolve project_id — fall back to first owned project if requested one isn't theirs
        raw_pid = request.query_params.get("project_id")
        if raw_pid and projects:
            owned = next((p for p in projects if p.id == raw_pid), None)
            project_id = owned.id if owned else projects[0].id
        elif projects:
            project_id = projects[0].id
        else:
            project_id = None

        # Build 30-day date range
        today = datetime.now(timezone.utc).date()
        thirty_days_ago = today - timedelta(days=29)
        thirty_days_ago_str = thirty_days_ago.isoformat()

        # Generate ordered list of date strings for the last 30 days
        daily_labels = [
            (thirty_days_ago + timedelta(days=i)).isoformat()
            for i in range(30)
        ]

        # Fetch all events in the window for the selected project
        if project_id:
            all_events = (
                db.query(Event)
                .filter(Event.project_id == project_id)
                .all()
            )
            events_30d = [
                e for e in all_events
                if e.timestamp and e.timestamp[:10] >= thirty_days_ago_str
            ]
        else:
            events_30d = []

        # Group by date
        cost_by_day: dict[str, float] = {}
        calls_by_day: dict[str, int] = {}
        for e in events_30d:
            day = e.timestamp[:10]
            cost_by_day[day] = cost_by_day.get(day, 0.0) + (e.cost_usd or 0.0)
            calls_by_day[day] = calls_by_day.get(day, 0) + 1

        daily_costs = [round(cost_by_day.get(d, 0.0), 6) for d in daily_labels]
        daily_calls = [calls_by_day.get(d, 0) for d in daily_labels]

        # Week-over-week calculations
        this_week_start = (today - timedelta(days=6)).isoformat()
        last_week_start = (today - timedelta(days=13)).isoformat()
        last_week_end = (today - timedelta(days=7)).isoformat()

        this_week_total = sum(
            e.cost_usd or 0.0
            for e in events_30d
            if e.timestamp and e.timestamp[:10] >= this_week_start
        )
        last_week_total = sum(
            e.cost_usd or 0.0
            for e in events_30d
            if e.timestamp
            and last_week_start <= e.timestamp[:10] <= last_week_end
        )

        if last_week_total > 0:
            wow_change_pct = ((this_week_total - last_week_total) / last_week_total) * 100
        else:
            wow_change_pct = None

        projected_monthly = (this_week_total / 7) * 30

        total_events_30d = len(events_30d)

        return templates.TemplateResponse("trends.html", {
            "request": request,
            "project_id": project_id,
            "projects": projects,
            "current_user": current_user,
            "user": current_user,
            "daily_labels_json": json.dumps(daily_labels),
            "daily_costs_json": json.dumps(daily_costs),
            "daily_calls_json": json.dumps(daily_calls),
            "this_week_total": this_week_total,
            "last_week_total": last_week_total,
            "wow_change_pct": wow_change_pct,
            "projected_monthly": projected_monthly,
            "total_events_30d": total_events_30d,
        })
    finally:
        db.close()
