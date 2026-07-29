import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import SessionLocal
from backend.models.operator_activation import (
    OperatorActivationRequest,
    ActivationDocument,
    OperatorActivationRemark
)

def clear_operator_activation_data():
    db = SessionLocal()
    try:
        print("Starting cleanup of Operator Activation requests data...")

        # 1. Delete Activation Documents
        docs_deleted = db.query(ActivationDocument).delete()
        print(f"Cleared ActivationDocument table ({docs_deleted} records).")

        # 2. Delete Operator Activation Remarks
        remarks_deleted = db.query(OperatorActivationRemark).delete()
        print(f"Cleared OperatorActivationRemark table ({remarks_deleted} records).")

        # 3. Delete Operator Activation Requests
        requests_deleted = db.query(OperatorActivationRequest).delete()
        print(f"Cleared OperatorActivationRequest table ({requests_deleted} records).")

        db.commit()
        print(f"\nSuccessfully committed transaction! Deleted {requests_deleted} activation request(s).")
    except Exception as e:
        db.rollback()
        print(f"Error during execution: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_operator_activation_data()
