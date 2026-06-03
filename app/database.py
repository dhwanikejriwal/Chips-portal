from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

# Step 1: Load .env file
load_dotenv()

# Step 2: Read DB URL
DATABASE_URL = os.getenv("DATABASE_URL")

# Step 3: Create engine (the actual connection)
engine = create_engine(DATABASE_URL)

# Step 4: Create session factory
SessionLocal = sessionmaker(bind=engine)

# Step 5: Base class for all models
Base = declarative_base()

# Step 6: Function every route will use
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()