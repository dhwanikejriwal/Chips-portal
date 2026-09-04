import os
from urllib.parse import urlparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

db_pass = os.getenv("DB_PASSWORD", "YOUR_STRONG_PASSWORD")
db_user = os.getenv("POSTGRES_USER", "postgres")
db_name = os.getenv("POSTGRES_DB", "chips_db_new")

raw_url = os.getenv("DATABASE_URL")
if raw_url:
    try:
        parsed = urlparse(raw_url)
        if parsed.password:
            db_pass = parsed.password
        if parsed.username:
            db_user = parsed.username
        if parsed.path and len(parsed.path) > 1:
            db_name = parsed.path.lstrip("/")
    except Exception:
        pass

is_docker = os.path.exists("/.dockerenv") or os.getenv("CONTAINER") is not None or os.getenv("HOSTNAME", "").startswith("chips-")

primary_url = f"postgresql://{db_user}:{db_pass}@postgres:5432/{db_name}" if is_docker else (raw_url or f"postgresql://{db_user}:{db_pass}@localhost:5432/{db_name}")

try:
    engine = create_engine(primary_url, pool_pre_ping=True)
    with engine.connect() as conn:
        pass
    DATABASE_URL = primary_url
except Exception as err:
    if "password" in str(err).lower() or "authentication" in str(err).lower():
        fallback_url = f"postgresql://postgres:YOUR_STRONG_PASSWORD@postgres:5432/{db_name}" if is_docker else f"postgresql://postgres:YOUR_STRONG_PASSWORD@localhost:5432/{db_name}"
        DATABASE_URL = fallback_url
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    else:
        DATABASE_URL = primary_url
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Session Local class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get db session in FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
