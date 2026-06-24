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
    "activated": "AC"
}

INV_STATUS_MAP_LOWER = {
    "PE": "pending",
    "AP": "approved",
    "RV": "reverted",
    "RA": "reapplied",
    "SC": "sent_to_chips",
    "SU": "sent_to_uidai",
    "UA": "uidai_approved",
    "UR": "uidai_rejected",
    "RW": "reviewed",
    "AS": "assigned",
    "FW": "forwarded",
    "FA": "forwarded again",
    "SK": "skipped",
    "RJ": "rejected",
    "RC": "reverted by chips",
    "AC": "activated"
}

INV_STATUS_MAP_UPPER = {k: v.upper() for k, v in INV_STATUS_MAP_LOWER.items()}

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
    "AC": "Activated"
}

def to_code(status_str: str) -> str:
    if not status_str:
        return "PE"
    clean = str(status_str).strip().lower()
    if clean in STATUS_MAP:
        return STATUS_MAP[clean]
    if clean.replace(" ", "_") in STATUS_MAP:
        return STATUS_MAP[clean.replace(" ", "_")]
    if clean.replace("_", " ") in STATUS_MAP:
        return STATUS_MAP[clean.replace("_", " ")]
    return "PE"

def to_name(status_code: str, casing="lower") -> str:
    if not status_code:
        return "pending" if casing == "lower" else ("PENDING" if casing == "upper" else "Pending")
    if len(status_code) > 2:
        return status_code # if it is already a long string, return it
    code = status_code.strip().upper()
    if casing == "lower":
        return INV_STATUS_MAP_LOWER.get(code, "pending")
    elif casing == "upper":
        return INV_STATUS_MAP_UPPER.get(code, "PENDING")
    else:
        return INV_STATUS_MAP_TITLE.get(code, "Pending")

def get_status_expression(status_code_col, casing="lower"):
    if casing == "lower":
        return case(
            (status_code_col == 'PE', 'pending'),
            (status_code_col == 'AP', 'approved'),
            (status_code_col == 'RV', 'reverted'),
            (status_code_col == 'RA', 'reapplied'),
            (status_code_col == 'SC', 'sent_to_chips'),
            (status_code_col == 'SU', 'sent_to_uidai'),
            (status_code_col == 'UA', 'uidai_approved'),
            (status_code_col == 'UR', 'uidai_rejected'),
            (status_code_col == 'RW', 'reviewed'),
            (status_code_col == 'AS', 'assigned'),
            (status_code_col == 'FW', 'forwarded'),
            (status_code_col == 'FA', 'forwarded again'),
            (status_code_col == 'SK', 'skipped'),
            (status_code_col == 'RJ', 'rejected'),
            (status_code_col == 'RC', 'reverted by chips'),
            (status_code_col == 'AC', 'activated'),
            else_=status_code_col
        )
    elif casing == "upper":
        return case(
            (status_code_col == 'PE', 'PENDING'),
            (status_code_col == 'AP', 'APPROVED'),
            (status_code_col == 'RV', 'REVERTED'),
            (status_code_col == 'RA', 'REAPPLIED'),
            (status_code_col == 'SC', 'SENT_TO_CHIPS'),
            (status_code_col == 'SU', 'SENT_TO_UIDAI'),
            (status_code_col == 'UA', 'UIDAI_APPROVED'),
            (status_code_col == 'UR', 'UIDAI_REJECTED'),
            (status_code_col == 'RW', 'REVIEWED'),
            (status_code_col == 'AS', 'ASSIGNED'),
            (status_code_col == 'FW', 'FORWARDED'),
            (status_code_col == 'FA', 'FORWARDED AGAIN'),
            (status_code_col == 'SK', 'SKIPPED'),
            (status_code_col == 'RJ', 'REJECTED'),
            (status_code_col == 'RC', 'REVERTED BY CHIPS'),
            (status_code_col == 'AC', 'ACTIVATED'),
            else_=status_code_col
        )
    else: # title casing
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
            (status_code_col == 'AC', 'Activated'),
            else_=status_code_col
        )

