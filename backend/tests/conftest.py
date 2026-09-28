import os

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-key-for-pytest-at-least-32-bytes")

# Isolate tests from the developer's .env (load_dotenv never overrides
# variables that are already set): no real DB, no external API calls,
# plain-HTTP cookies, demo mode off unless a test turns it on.
for _key in ("DATABASE_URL", "ABUSEIPDB_API_KEY", "IPINFO_TOKEN", "GROQ_API_KEY"):
    os.environ[_key] = ""
os.environ["ENV"] = "development"
os.environ["DEMO_MODE"] = "false"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"

import users  # noqa: E402

# Cheap hashes keep the suite fast; set before main.py seeds anything.
users.BCRYPT_ROUNDS = 4

# With DEMO_MODE=false only `admin` is seeded; tests add their own analysts.
ANALYST_PASSWORD = "test-analyst-password"


@pytest.fixture(scope="session", autouse=True)
def _test_users():
    import main  # noqa: F401  (seeds admin)
    users.add_user("alice", "Alice Chen", "analyst", ANALYST_PASSWORD)
    users.add_user("bob", "Bob Martinez", "analyst", ANALYST_PASSWORD)
    users.add_user("mira", "Mira Cohen", "manager", ANALYST_PASSWORD)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from rate_limit import reset_limits
    reset_limits()


def session_client(username: str, role: str):
    """A TestClient carrying a valid session for `username` (no login round trip)."""
    from datetime import datetime, timedelta, timezone
    from fastapi.testclient import TestClient
    import jwt
    import main
    from store import SECRET_KEY
    import users
    record = users.get_user(username)
    token = jwt.encode(
        {"sub": username, "role": role, "typ": "session",
         "sk": record["session_key"] if record else None,
         "sid": __import__("sessions").new_session_id(),
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        SECRET_KEY, algorithm="HS256",
    )
    client = TestClient(main.app)
    client.cookies.set("sf_session", token)
    return client
