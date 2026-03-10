from fastapi import FastAPI, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
# Database setup
from server.database import engine, Base, get_db
from server.models import Project

# Routes
from server.routes import api, ui

# Auth
from server.auth import verify_admin

# Build all tables on boot
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Veritas Cloud Backend")

# We mount our UI routes securely
app.include_router(ui.router, tags=["ui"])

# We mount the high-performance SDK ingestion endpoint separately
app.include_router(api.router, prefix="/api", tags=["api"])

# Internal form action to generate new projects
@app.post("/settings/project/new", include_in_schema=False)
def form_create_project(
    project_name: str = Form(...),
    username: str = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    from server.schemas import ProjectCreateSchema
    result = api.create_project(ProjectCreateSchema(name=project_name), db=db)
    
    # Redirect back to settings page, injecting the new Raw Key just this once
    return RedirectResponse(
        url=f"/settings?project_id={result['id']}&raw_key={result['raw_key']}", 
        status_code=303
    )
