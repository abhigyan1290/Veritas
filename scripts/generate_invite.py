import sys
import os

# Add the root directory to path so we can import server.database
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server.database import SessionLocal
from server.models import User
from server.auth_users import hash_password
from datetime import datetime, timezone
import string
import random

def generate_random_password(length=12):
    """Generate a secure alphanumeric password."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def create_invite(username: str):
    print(f"Generating invite for username: {username} ...")
    
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"❌ User '{username}' already exists in the database.")
            return
        
        password = generate_random_password()
        hashed_pw = hash_password(password)
        
        new_user = User(
            username=username,
            password_hash=hashed_pw,
            created_at=datetime.now(timezone.utc)
        )
        db.add(new_user)
        db.commit()
        
        print(f"✅ Successfully created secure invite!")
        print(f"----------------------------------------")
        print(f"Username: {username}")
        print(f"Password: {password}")
        print(f"----------------------------------------")
        print("Share these credentials securely. They cannot be recovered if lost.")
        
    except Exception as e:
        print(f"❌ Failed to create user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_invite.py <desired_username>")
        sys.exit(1)
        
    target_username = sys.argv[1].strip()
    create_invite(target_username)
