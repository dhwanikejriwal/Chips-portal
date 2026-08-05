
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
    SENT_TO_UIDAI = 6
    FORWARDED = 11
    FORWARDED_AGAIN = 12
    SKIPPED = 13
    REJECTED = 14
    REVERTED_BY_CHIPS = 15
    APPROVED_LEGACY = 16
    ON_HOLD = 17
    ALLOTTED = 18
    L1_DONE = 19
    L2_DONE = 20

def to_code(status_str: str) -> int:
    if not status_str:
        return StatusEnum.PENDING.value
    s = status_str.strip().upper().replace(' ', '_')
    if s in ['L1_DONE', 'L1DONE', 'L1_APPROVED']:
        return StatusEnum.L1_DONE.value
    if s in ['L2_DONE', 'L2DONE', 'L2_APPROVED']:
        return StatusEnum.L2_DONE.value
    try:
        return StatusEnum[s].value
    except KeyError:
        return StatusEnum.PENDING.value

def to_name(status_id: int) -> str:
    if not status_id:
        return ""
    if status_id == StatusEnum.L1_DONE.value:
        return "L1 Done"
    if status_id == StatusEnum.L2_DONE.value:
        return "L2 Done"
    try:
        return StatusEnum(status_id).name
    except ValueError:
        return ""
