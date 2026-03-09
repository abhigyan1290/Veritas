from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials
import os
import hashlib
import secrets
from sqlalchemy.orm import Session
from server.database import get_db
from server.models import Project

security = HTTPBearer()
admin_security = HTTPBasic()

def get_current_project(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> str:
    """Validate Bearer token using constant-time hash comparison and return project_id."""
    token = credentials.credentials
    
    # 1. Hash the incoming API Key immediately
    incoming_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    
    # 2. Fetch the Project by Hash
    project = db.query(Project).filter(Project.api_key_hash == incoming_hash).first()
    
    # 3. Use compare_digest to prevent timing attacks, even if DB misses
    if not project or not secrets.compare_digest(project.api_key_hash, incoming_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or unauthorized API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return project.project_id


def verify_admin(credentials: HTTPBasicCredentials = Depends(admin_security)):
    """Dashboard UI Protection: Basic Auth guard for Admin routes."""
    expected_username = os.environ.get("VERITAS_ADMIN_USER", "admin")
    expected_password = os.environ.get("VERITAS_ADMIN_PASS", "admin")
    
    # Constant-time string comparison for admin credentials
    is_correct_username = secrets.compare_digest(credentials.username.encode("utf8"), expected_username.encode("utf8"))
    is_correct_password = secrets.compare_digest(credentials.password.encode("utf8"), expected_password.encode("utf8"))
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True
