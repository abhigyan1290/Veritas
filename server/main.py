from fastapi import FastAPI
from server.database import engine, Base
from server.routes import dashboard, ingest, auth
from server.middleware import SessionMiddleware

import time
import os

# Build all tables on boot with a retry loop for Postgres readiness
for i in range(5):
    try:
        Base.metadata.create_all(bind=engine)
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
app.include_router(ingest.router, prefix="/api/v1", tags=["api"])

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server.main:app", host="0.0.0.0", port=port)
