from fastapi import APIRouter, Depends, Request, Form, Response, Header, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import os

from server.database import get_db
from server.models import User
from server.auth_users import hash_password, verify_password, create_session_token

router = APIRouter()
templates = Jinja2Templates(directory="server/templates")

# Secret used to authorize the invite creation script
ADMIN_SECRET = os.environ.get("VERITAS_ADMIN_SECRET", "local-admin-secret")

ALLOW_SIGNUPS = os.environ.get("ALLOW_SIGNUPS", "false").lower() == "true"

@router.get("/auth/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@router.post("/auth/login")
def login(response: Response, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
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
def signup(response: Response, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if not ALLOW_SIGNUPS:
        return RedirectResponse(url="/auth/signup?error=Signups+are+invite-only", status_code=303)
        
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return RedirectResponse(url="/auth/signup?error=Username+already+exists", status_code=303)
        
    new_user = User(
        username=username,
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

@router.post("/admin/create-user")
def admin_create_user(
    username: str,
    password: str,
    x_admin_secret: str = Header(...),
    db: Session = Depends(get_db)
):
    """Secure endpoint for the invite script to create users server-side."""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"User '{username}' already exists")
    
    new_user = User(
        username=username,
        password_hash=hash_password(password),
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_user)
    db.commit()
    return JSONResponse({"status": "created", "username": username})
