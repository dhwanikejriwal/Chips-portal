import os
import sys

# Add backend to python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
print("Starting query inspection...")

try:
    base_query = """
        SELECT r.id, r.request_code, r.station_id, r.model_type, r.status_code, r.created_at, d.district_name as dist_name
        FROM l1_registration_requests r LEFT JOIN district_table d ON r.district_id = d.district_code
    """
    print("Executing L1 Registration query...")
    q = db.execute(text(base_query))
    rows = q.fetchall()
    print("L1 Query Success! Count:", len(rows))
except Exception as e:
    import traceback
    print("L1 Query Failed!")
    traceback.print_exc()

try:
    base_query = """
        SELECT r.id, r.request_code, r.operator_count, r.training_date, r.status_code, r.created_at, r.updated_at, r.reject_reason, d.district_name as dist_name
        FROM operator_reactivation_requests r LEFT JOIN district_table d ON r.district_id = d.district_code
    """
    print("\nExecuting Reactivation query...")
    q = db.execute(text(base_query))
    rows = q.fetchall()
    print("Reactivation Query Success! Count:", len(rows))
except Exception as e:
    import traceback
    print("Reactivation Query Failed!")
    traceback.print_exc()

db.close()
