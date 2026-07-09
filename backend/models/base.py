
from datetime import datetime, timedelta
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import case

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

from enum import Enum

class StatusEnum(int, Enum):
    PENDING = 1
    APPROVED = 2
    REVERTED = 3
    REAPPLIED = 4
    SENT_TO_CHIPS = 5
    SENT_TO_UIDAI = 6
    UIDAI_APPROVED = 7
    UIDAI_REJECTED = 8
    REVIEWED = 9
    ASSIGNED = 10
    FORWARDED = 11
    FORWARDED_AGAIN = 12
    SKIPPED = 13
    REJECTED = 14
    REVERTED_BY_CHIPS = 15
    APPROVED_LEGACY = 16

def to_code(status_str: str) -> int:
    if not status_str:
        return StatusEnum.PENDING.value
    s = status_str.strip().upper().replace(' ', '_')
    try:
        return StatusEnum[s].value
    except KeyError:
        return StatusEnum.PENDING.value

def to_name(status_id: int) -> str:
    if not status_id:
        return ""
    try:
        return StatusEnum(status_id).name
    except ValueError:
        return ""
