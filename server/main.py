from fastapi import FastAPI
from server.database import engine, Base
from server.routes import ingest, dashboard

# Ensure all database tables are created automatically on boot
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Veritas Cloud Platform")

app.include_router(ingest.router, prefix="/api/v1")
app.include_router(dashboard.router)

@app.get("/health")
def health_check():
    return {"status": "serving"}
