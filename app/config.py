import os
from dotenv import load_dotenv

# Ensure environment variables are loaded from the root .env file
load_dotenv()

class Config:
    """Core application configuration class."""
    # Flask Security Settings
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-fallback-key-change-in-production")
    DEBUG = True
    
    # URL of the FastAPI backend API
    BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000/api")
    
    # Flask Session Settings (6 Hours lifetime)
    from datetime import timedelta
    PERMANENT_SESSION_LIFETIME = timedelta(hours=6)
    # Multi-language configuration toggle (Default: True)
    ENABLE_LANGUAGE_TOGGLE = os.getenv("ENABLE_LANGUAGE_TOGGLE", "True").strip().lower() in ("true", "1", "yes")
