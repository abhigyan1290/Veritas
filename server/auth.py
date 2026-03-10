import secrets
import hashlib
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from server.database import SessionLocal
from server.models import Project
import os

security_basic = HTTPBasic()
security_bearer = HTTPBearer()

def verify_admin(credentials: HTTPBasicCredentials = Security(security_basic)):
    """Basic Auth for Dashboard UI Access"""
    correct_username = os.environ.get("VERITAS_ADMIN_USER", "admin")
    correct_password = os.environ.get("VERITAS_ADMIN_PASS", "password")
    
    is_user_ok = secrets.compare_digest(credentials.username, correct_username)
    is_pass_ok = secrets.compare_digest(credentials.password, correct_password)
    
    if not (is_user_ok and is_pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security_bearer)):
    """Bearer Auth for SDK API Event Ingestion"""
    token = credentials.credentials
    
    db = SessionLocal()
    try:
        # Re-hash the provided key and check if any project owns it securely
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        project = db.query(Project).filter(Project.api_key_hash == token_hash).first()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing API Key"
            )
        return project.id
    finally:
        db.close()
