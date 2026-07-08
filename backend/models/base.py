
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

# =====================================================================
# 📊 CHIP-PORTAL GLOBAL STATUS CODE DICTIONARY & MAPS
# =====================================================================
STATUS_MAP = {
    "pending": "PE",
    "approved": "AP",
    "reverted": "RV",
    "reapplied": "RA",
    "sent_to_chips": "SC",
    "sent_to_uidai": "SU",
    "uidai_approved": "UA",
    "uidai_rejected": "UR",
    "reviewed": "RW",
    "assigned": "AS",
    "forwarded": "FW",
    "forwarded again": "FA",
    "skipped": "SK",
    "rejected": "RJ",
    "reverted by chips": "RC",
    "approved (legacy)": "AC"
}


INV_STATUS_MAP_TITLE = {
    "PE": "Pending",
    "AP": "Approved",
    "RV": "Reverted",
    "RA": "Reapplied",
    "SC": "Sent to CHiPS",
    "SU": "Sent to UIDAI",
    "UA": "UIDAI Approved",
    "UR": "UIDAI Rejected",
    "RW": "Reviewed",
    "AS": "Assigned",
    "FW": "Forwarded",
    "FA": "Forwarded Again",
    "SK": "Skipped",
    "RJ": "Rejected",
    "RC": "Reverted by CHiPS",
    "AC": "Approved"
}

def to_code(status_str: str) -> str:
    if not status_str:
        return "PE"
    s = status_str.strip().lower()
    return STATUS_MAP.get(s, "PE")

def to_name(status_code: str, casing: str = None) -> str:
    if not status_code:
        return ""
    code = status_code.strip().upper()
    return INV_STATUS_MAP_TITLE.get(code, code)

def get_status_expression(status_code_col, casing: str = None):
    return case(
        (status_code_col == 'PE', 'Pending'),
        (status_code_col == 'AP', 'Approved'),
        (status_code_col == 'RV', 'Reverted'),
        (status_code_col == 'RA', 'Reapplied'),
        (status_code_col == 'SC', 'Sent to CHiPS'),
        (status_code_col == 'SU', 'Sent to UIDAI'),
        (status_code_col == 'UA', 'UIDAI Approved'),
        (status_code_col == 'UR', 'UIDAI Rejected'),
        (status_code_col == 'RW', 'Reviewed'),
        (status_code_col == 'AS', 'Assigned'),
        (status_code_col == 'FW', 'Forwarded'),
        (status_code_col == 'FA', 'Forwarded Again'),
        (status_code_col == 'SK', 'Skipped'),
        (status_code_col == 'RJ', 'Rejected'),
        (status_code_col == 'RC', 'Reverted by CHiPS'),
        (status_code_col == 'AC', 'Approved'),
        else_=status_code_col
    )
