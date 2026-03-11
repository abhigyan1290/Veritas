import sys
import os
import string
import random
import requests
from dotenv import load_dotenv

load_dotenv()  # Read VERITAS_ADMIN_SECRET and VERITAS_BASE_URL from .env

# Config - these can be overridden via environment variables
BASE_URL = os.environ.get("VERITAS_BASE_URL", "https://web-production-82424.up.railway.app")
ADMIN_SECRET = os.environ.get("VERITAS_ADMIN_SECRET", "local-admin-secret")

def generate_random_password(length=12):
    """Generate a secure alphanumeric password."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def create_invite(username: str):
    print(f"Generating invite for username: {username} ...")

    password = generate_random_password()

    try:
        res = requests.post(
            f"{BASE_URL}/admin/create-user",
            params={"username": username, "password": password},
            headers={"x-admin-secret": ADMIN_SECRET},
            timeout=15
        )

        if res.status_code == 200:
            print(f"Success! Created secure invite.")
            print(f"----------------------------------------")
            print(f"Username: {username}")
            print(f"Password: {password}")
            print(f"----------------------------------------")
            print("Share these credentials securely. They cannot be recovered if lost.")
        elif res.status_code == 409:
            print(f"Error: User '{username}' already exists on the server.")
        elif res.status_code == 403:
            print("Error: Admin secret is incorrect. Check VERITAS_ADMIN_SECRET.")
        else:
            print(f"Error: Server returned {res.status_code}: {res.text}")

    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to {BASE_URL}. Is the server running?")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_invite.py <desired_username>")
        sys.exit(1)

    target_username = sys.argv[1].strip()
    create_invite(target_username)
