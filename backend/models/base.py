from datetime import datetime, timedelta
from sqlalchemy.orm import DeclarativeBase

def get_ist_now() -> datetime:
    # Indian Standard Time (UTC +05:30)
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# Alias for backward compatibility with friend's models
get_ist_time = get_ist_now

class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 Declarative Base class
    """
    pass
