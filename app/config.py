import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "flask_secret_key_change_me_in_production")
    DEBUG = True
    
    # URL of the FastAPI backend API
    BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000/api")
