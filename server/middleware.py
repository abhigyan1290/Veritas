from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from server.auth_users import decode_session_token
from server.database import SessionLocal
from server.models import User

class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow open access to these paths
        open_paths = ["/auth/login", "/auth/signup", "/auth/logout", "/health"]
        
        # Static files and API ingested routes bypass the dashboard session check
        if request.url.path.startswith("/api/") or request.url.path in open_paths:
            return await call_next(request)
            
        token = request.cookies.get("veritas_session")
        if not token:
            return RedirectResponse(url="/auth/login", status_code=303)
            
        user_id = decode_session_token(token)
        if not user_id:
            return RedirectResponse(url="/auth/login", status_code=303)
            
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return RedirectResponse(url="/auth/login", status_code=303)
            request.state.current_user = user
        finally:
            db.close()
            
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
