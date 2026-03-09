import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# Default to SQLite for MVP and local development out-of-the-box.
# For production, set VERITAS_DATABASE_URL="postgresql://user:pass@host/dbname"
SQLALCHEMY_DATABASE_URL = os.environ.get("VERITAS_DATABASE_URL", "sqlite:///./veritas_cloud.db")

connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    # Needed for SQLite to allow multiple threads handling requests
    connect_args = {"check_same_thread": False}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args=connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency resolver for FastAPI to get DB sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
