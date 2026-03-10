from fastapi import APIRouter, Depends, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import os

from server.database import get_db
from server.models import User
from server.auth_users import hash_password, verify_password, create_session_token

router = APIRouter()
templates = Jinja2Templates(directory="server/templates")

ALLOW_SIGNUPS = os.environ.get("ALLOW_SIGNUPS", "false").lower() == "true"

@router.get("/auth/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@router.post("/auth/login")
def login(response: Response, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return RedirectResponse(url="/auth/login?error=Invalid+credentials", status_code=303)
        
    token = create_session_token(user.id)
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(key="veritas_session", value=token, httponly=True, max_age=7*24*3600, samesite="lax")
    return resp

@router.get("/auth/signup", response_class=HTMLResponse)
def signup_page(request: Request, error: str = None):
    return templates.TemplateResponse(
        "signup.html", 
        {"request": request, "error": error, "allow_signups": ALLOW_SIGNUPS}
    )

@router.post("/auth/signup")
def signup(response: Response, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if not ALLOW_SIGNUPS:
        return RedirectResponse(url="/auth/signup?error=Signups+are+invite-only", status_code=303)
        
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return RedirectResponse(url="/auth/signup?error=Email+already+exists", status_code=303)
        
    new_user = User(
        email=email,
        password_hash=hash_password(password),
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    token = create_session_token(new_user.id)
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(key="veritas_session", value=token, httponly=True, max_age=7*24*3600, samesite="lax")
    return resp

@router.post("/auth/logout")
@router.get("/auth/logout")
def logout(response: Response):
    resp = RedirectResponse(url="/auth/login", status_code=303)
    resp.delete_cookie("veritas_session")
    return resp
