import os
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from server.database import get_db
from server.models import Feedback, Project

_ADMIN_USERNAME = os.environ.get("VERITAS_ADMIN_USERNAME", "admin")

router = APIRouter()
templates = Jinja2Templates(directory="server/templates")


def get_projects_for_user(db: Session, user_id: str):
    return db.query(Project).filter(Project.user_id == user_id).all()


@router.get("/feedback", response_class=HTMLResponse)
def feedback_form(request: Request, db: Session = Depends(get_db)):
    current_user = request.state.current_user
    projects = get_projects_for_user(db, current_user.id)
    project_id = request.query_params.get("project_id", projects[0].id if projects else None)

    existing = db.query(Feedback).filter(Feedback.username == current_user.username).first()
    if existing:
        return RedirectResponse(url="/feedback/thanks", status_code=303)

    return templates.TemplateResponse(
        "feedback.html",
        {
            "request": request,
            "project_id": project_id,
            "projects": projects,
            "current_user": current_user,
            "user": current_user,
        },
    )


@router.post("/feedback", response_class=HTMLResponse)
def feedback_submit(
    request: Request,
    nps_score: int = Form(...),
    willing_to_pay: str = Form(...),
    features: List[str] = Form(default=[]),
    feedback_text: Optional[str] = Form(default=None),
    name: Optional[str] = Form(default=None),
    email: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    current_user = request.state.current_user

    # Clamp NPS to valid range — never let out-of-range values corrupt aggregate metrics
    nps_score = max(1, min(10, nps_score))

    existing = db.query(Feedback).filter(Feedback.username == current_user.username).first()
    if not existing:
        entry = Feedback(
            username=current_user.username,
            nps_score=nps_score,
            willing_to_pay=willing_to_pay,
            valuable_features=json.dumps(features) if features else None,
            feedback_text=feedback_text or None,
            name=name or None,
            email=email or None,
        )
        db.add(entry)
        db.commit()

    return RedirectResponse(url="/feedback/thanks", status_code=303)


@router.get("/feedback/thanks", response_class=HTMLResponse)
def feedback_thanks(request: Request, db: Session = Depends(get_db)):
    current_user = request.state.current_user
    projects = get_projects_for_user(db, current_user.id)
    project_id = request.query_params.get("project_id", projects[0].id if projects else None)

    return templates.TemplateResponse(
        "feedback_thanks.html",
        {
            "request": request,
            "project_id": project_id,
            "projects": projects,
            "current_user": current_user,
            "user": current_user,
        },
    )


@router.get("/feedback/results", response_class=HTMLResponse)
def feedback_results(request: Request, db: Session = Depends(get_db)):
    current_user = request.state.current_user

    if current_user.username != _ADMIN_USERNAME:
        return RedirectResponse(url="/", status_code=303)

    projects = get_projects_for_user(db, current_user.id)
    project_id = request.query_params.get("project_id", projects[0].id if projects else None)

    all_feedback = db.query(Feedback).order_by(Feedback.submitted_at.desc()).all()
    total_responses = len(all_feedback)

    avg_nps = 0.0
    nps_distribution = {i: 0 for i in range(1, 11)}
    nps_promoters = 0
    nps_passives = 0
    nps_detractors = 0
    pay_distribution = {}
    feature_counts = {}

    if total_responses > 0:
        total_nps = sum(f.nps_score for f in all_feedback)
        avg_nps = round(total_nps / total_responses, 1)

        for f in all_feedback:
            score = f.nps_score
            if 1 <= score <= 10:
                nps_distribution[score] = nps_distribution.get(score, 0) + 1
            if score >= 9:
                nps_promoters += 1
            elif score in (7, 8):
                nps_passives += 1
            else:
                nps_detractors += 1

            val = f.willing_to_pay
            pay_distribution[val] = pay_distribution.get(val, 0) + 1

            if f.valuable_features:
                try:
                    feats = json.loads(f.valuable_features)
                    for feat in feats:
                        feature_counts[feat] = feature_counts.get(feat, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    pass

    nps_calculated = round(
        ((nps_promoters - nps_detractors) / total_responses * 100) if total_responses > 0 else 0,
        1,
    )

    feature_counts = dict(sorted(feature_counts.items(), key=lambda x: x[1], reverse=True))

    return templates.TemplateResponse(
        "feedback_results.html",
        {
            "request": request,
            "project_id": project_id,
            "projects": projects,
            "current_user": current_user,
            "user": current_user,
            "total_responses": total_responses,
            "avg_nps": avg_nps,
            "nps_distribution": nps_distribution,
            "nps_promoters": nps_promoters,
            "nps_passives": nps_passives,
            "nps_detractors": nps_detractors,
            "nps_calculated": nps_calculated,
            "pay_distribution": pay_distribution,
            "feature_counts": feature_counts,
            "all_feedback": all_feedback,
        },
    )
