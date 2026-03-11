from fastapi import FastAPI
from server.database import engine, Base
from server.routes import dashboard, ingest, auth, trends, analytics, feedback
from server.middleware import SessionMiddleware
from server.demo_tenant import ensure_demo_tenant

import time
import os

# Build all tables on boot with a retry loop for Postgres readiness
for i in range(5):
    try:
        Base.metadata.create_all(bind=engine)
        
        from server.database import SessionLocal
        db = SessionLocal()
        try:
            ensure_demo_tenant(db)
        finally:
            db.close()
            
        break
    except Exception as e:
        if i == 4:
            raise e
        print(f"Database not ready, retrying in 3 seconds... ({i+1}/5)")
        time.sleep(3)

app = FastAPI(title="Veritas Cloud Backend")

app.add_middleware(SessionMiddleware)

# Mount routes exactly per Phase 3 spec
app.include_router(auth.router, tags=["auth"])
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(trends.router, tags=["dashboard"])
app.include_router(analytics.router, tags=["dashboard"])
app.include_router(feedback.router, tags=["dashboard"])
app.include_router(ingest.router, prefix="/api/v1", tags=["api"])

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server.main:app", host="0.0.0.0", port=port)
