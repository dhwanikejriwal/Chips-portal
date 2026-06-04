import os
from dotenv import load_dotenv

# Ensure environment variables are loaded from the root .env file
load_dotenv()

class Config:
    """Core application configuration class."""
    # Flask Security Settings
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-fallback-key-change-in-production")
    
    # =====================================================================
    # FUTURE SCALABILITY SCRIPTS (For Member 2 & Member 3)
    # Your teammates can drop their Redis/Celery/Email settings right here:
    # =====================================================================
    # CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    # MAIL_SERVER = 'smtp.gmail.com'
    # MAIL_PORT = 587