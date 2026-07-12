import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import SessionLocal
from backend.models import (
    Candidate, CandidateLogin, LMS, LMSRemark,
    NSEITRequest, NSEITRemark, HoldCandidate, OtpVerification, DCRemark
)

def clear_data():
    db = SessionLocal()
    try:
        print("Starting cleanup of candidate, lms, and nseit data...")
        
        # 1. Delete LMSRemarks and LMS
        db.query(LMSRemark).delete()
        db.query(LMS).delete()
        print("Cleared LMS tables.")
        
        # 2. Delete NSEITRemarks and NSEITRequests
        db.query(NSEITRemark).delete()
        db.query(NSEITRequest).delete()
        print("Cleared NSEIT tables.")
        
        # 3. Delete HoldCandidate
        db.query(HoldCandidate).delete()
        print("Cleared HoldCandidate tables.")

        # 4. Delete DCRemark
        db.query(DCRemark).delete()
        print("Cleared DCRemark tables.")
        
        # 4. Delete OtpVerification
        db.query(OtpVerification).delete()
        print("Cleared OtpVerification tables.")
        
        # 5. Delete CandidateLogin and Candidate
        db.query(CandidateLogin).delete()
        db.query(Candidate).delete()
        print("Cleared Candidate tables.")
        
        db.commit()
        print("Successfully committed transaction. All candidate, lms, and nseit operational data has been deleted.")
    except Exception as e:
        db.rollback()
        print(f"Error during execution: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_data()
