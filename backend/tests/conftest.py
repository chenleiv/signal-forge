import os

os.environ.setdefault("JWT_SECRET", "test-secret-key-for-pytest")

# Isolate tests from the developer's .env (load_dotenv never overrides
# variables that are already set): no real DB, no external API calls,
# plain-HTTP cookies, demo mode off unless a test turns it on.
for _key in ("DATABASE_URL", "ABUSEIPDB_API_KEY", "IPINFO_TOKEN", "GROQ_API_KEY"):
    os.environ[_key] = ""
os.environ["ENV"] = "development"
os.environ["DEMO_MODE"] = "false"
