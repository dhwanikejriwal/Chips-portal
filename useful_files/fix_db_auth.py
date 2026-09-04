"""
Utility script to automatically sync Postgres user password with DATABASE_URL in .env.
"""
import os
import sys
import subprocess
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load .env from project root or current working dir
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(ROOT_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("❌ ERROR: DATABASE_URL is not set in .env file.")
    sys.exit(1)

parsed = urlparse(db_url)
db_password = parsed.password
db_user = parsed.username or "postgres"

if not db_password:
    print(f"⚠️ Warning: No password found in DATABASE_URL: {db_url}")
    db_password = os.getenv("DB_PASSWORD", "YOUR_STRONG_PASSWORD")

print(f"Syncing Postgres user '{db_user}' password with DATABASE_URL...")

# Execute ALTER USER in postgres container using Linux peer socket (-u postgres) which never prompts for password
cmd = ["docker", "exec", "-u", "postgres", "chips-postgres", "psql", "-U", "postgres", "-c", f"ALTER USER postgres WITH PASSWORD '{db_password}';"]
# Also set fallback default password just in case
cmd_fallback = ["docker", "exec", "-u", "postgres", "chips-postgres", "psql", "-U", "postgres", "-c", "ALTER USER postgres WITH PASSWORD 'YOUR_STRONG_PASSWORD';"]

try:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print("✅ Postgres user password successfully updated!")
    else:
        print(f"⚠️ SQL Execution output: {res.stdout} {res.stderr}")
        subprocess.run(cmd_fallback, capture_output=True, text=True)
except Exception as e:
    print(f"⚠️ Failed to run docker exec: {e}")

# Now test connection
print("\nTesting SQLAlchemy Database Connection...")
try:
    from sqlalchemy import create_engine
    test_url = f"postgresql://{db_user}:{db_password}@127.0.0.1:5432/chips_db_new"
    engine = create_engine(test_url, pool_pre_ping=True)
    with engine.connect() as conn:
        print("🎉 SUCCESS: DATABASE CONNECTED PERFECTLY!")
except Exception as ex:
    print(f"❌ Connection failed: {ex}")

