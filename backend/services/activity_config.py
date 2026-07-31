# backend/services/activity_config.py
"""Configuration for the Operator Activity ingestion pipeline.

Values are read from the environment (.env) with sane defaults, and the
registrar/EA codes can be overridden per-upload from the form.
"""
import os
from datetime import date, datetime

# Our registrar + enrolment agency. Defaults match the current deployment,
# overridable via .env and per-upload form fields.
DEFAULT_REGISTRAR_CODE = int(os.getenv("REGISTRAR_CODE", "986"))
DEFAULT_EA_CODE = int(os.getenv("EA_CODE", "2084"))

# Earliest date we expect daily activity data for. Used by the missing-date
# reminder to know where the calendar starts. If unset, we start from the
# earliest date already present in the data.
_START = os.getenv("ACTIVITY_TRACKING_START", "").strip()
ACTIVITY_TRACKING_START: date | None = (
    datetime.strptime(_START, "%Y-%m-%d").date() if _START else None
)

# Reject any query window wider than this many days (guards the DB).
MAX_QUERY_RANGE_DAYS = int(os.getenv("ACTIVITY_MAX_RANGE_DAYS", "366"))

# Where uploaded files are staged and rejected-row CSVs are written.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_TMP_DIR = os.getenv("ACTIVITY_UPLOAD_DIR", os.path.join(BASE_DIR, "data", "activity_uploads"))
REJECTED_DIR = os.getenv("ACTIVITY_REJECTED_DIR", os.path.join(BASE_DIR, "data", "activity_rejected"))

# Above this row count, spill CSV processing to DuckDB's on-disk temp rather
# than in-memory (DuckDB manages this itself once we set a temp_directory).
LARGE_FILE_ROW_THRESHOLD = int(os.getenv("ACTIVITY_LARGE_ROW_THRESHOLD", "2000000"))


def ensure_dirs() -> None:
    os.makedirs(UPLOAD_TMP_DIR, exist_ok=True)
    os.makedirs(REJECTED_DIR, exist_ok=True)
