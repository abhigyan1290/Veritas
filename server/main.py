from fastapi import FastAPI
from server.database import engine, Base
from server.routes import dashboard, ingest

# Build all tables on boot
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Veritas Cloud Backend")

# Mount routes exactly per Phase 3 spec
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(ingest.router, prefix="/api/v1", tags=["api"])
