"""Check the state of the Railway Postgres database."""
from dotenv import load_dotenv
load_dotenv()

from server.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    tables = db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).fetchall()
    print("Tables:", [t[0] for t in tables])

    user_count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
    project_count = db.execute(text("SELECT COUNT(*) FROM projects")).scalar()
    event_count = db.execute(text("SELECT COUNT(*) FROM events")).scalar()
    print(f"Users: {user_count}, Projects: {project_count}, Events: {event_count}")

    if user_count > 0:
        users = db.execute(text("SELECT username, created_at FROM users ORDER BY created_at")).fetchall()
        for u in users:
            print(f"  User: {u[0]}  created: {u[1]}")
finally:
    db.close()
