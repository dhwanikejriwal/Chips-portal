"""
Backfill script to populate status_after field for existing remarks
"""
from backend.database import SessionLocal
from backend.models.lms import LMSRemark
from backend.models.nseit import NSEITRemark
from backend.models.dc_remark import DCRemark
from backend.models.lms import LMS
from backend.models.nseit import NSEITRequest
from backend.models.candidate import Candidate

def backfill_lms_remarks():
    """Backfill LMS remarks with status_after"""
    db = SessionLocal()
    try:
        remarks = db.query(LMSRemark).all()
        updated_count = 0
        
        for remark in remarks:
            if remark.status_after is not None:
                continue  # Skip already filled remarks
            
            # Get the LMS request to determine status
            lms = db.query(LMS).filter(LMS.id == remark.lms_id).first()
            if not lms:
                continue
            
            # Infer status based on who created the remark
            if remark.candidate_by_id:  # Candidate action
                inferred_status = "Pending"
            elif remark.admin_by_id:  # Admin action
                remark_text = (remark.remark or "").lower()
                if "approved" in remark_text:
                    inferred_status = "Approved"
                elif "forwarded again" in remark_text or ("forwarded" in remark_text and lms.status == "Forwarded Again"):
                    inferred_status = "Forwarded Again"
                elif "forwarded" in remark_text:
                    inferred_status = "Forwarded"
                elif "reverted" in remark_text:
                    inferred_status = lms.status if lms.status in ["Reverted", "Reverted by CHiPS"] else "Reverted"
                elif "reapplied" in remark_text:
                    inferred_status = "Reapplied"
                else:
                    inferred_status = lms.status or "Pending"
            else:
                inferred_status = lms.status or "Pending"
            
            remark.status_after = inferred_status
            updated_count += 1
        
        db.commit()
        print(f"✅ Backfilled {updated_count} LMS remarks")
    finally:
        db.close()

def backfill_nseit_remarks():
    """Backfill NSEIT remarks with status_after"""
    db = SessionLocal()
    try:
        remarks = db.query(NSEITRemark).all()
        updated_count = 0
        
        for remark in remarks:
            if remark.status_after is not None:
                continue  # Skip already filled remarks
            
            # Get the NSEIT request to determine status
            nseit = db.query(NSEITRequest).filter(NSEITRequest.id == remark.nseit_id).first()
            if not nseit:
                continue
            
            # Infer status based on who created the remark
            if remark.candidate_by_id:  # Candidate action
                inferred_status = "Pending"
            elif remark.admin_by_id:  # Admin action
                remark_text = (remark.remark or "").lower()
                if "approved" in remark_text:
                    inferred_status = "Approved"
                elif "forwarded again" in remark_text or ("forwarded" in remark_text and nseit.status == "Forwarded Again"):
                    inferred_status = "Forwarded Again"
                elif "forwarded" in remark_text:
                    inferred_status = "Forwarded"
                elif "reverted" in remark_text:
                    inferred_status = nseit.status if nseit.status in ["Reverted", "Reverted by CHiPS"] else "Reverted"
                elif "reapplied" in remark_text:
                    inferred_status = "Reapplied"
                else:
                    inferred_status = nseit.status or "Pending"
            else:
                inferred_status = nseit.status or "Pending"
            
            remark.status_after = inferred_status
            updated_count += 1
        
        db.commit()
        print(f"✅ Backfilled {updated_count} NSEIT remarks")
    finally:
        db.close()

def backfill_dc_remarks():
    """Backfill DC remarks with status_after"""
    db = SessionLocal()
    try:
        remarks = db.query(DCRemark).all()
        updated_count = 0
        
        for remark in remarks:
            if remark.status_after is not None:
                continue  # Skip already filled remarks
            
            # Get the candidate to determine status
            candidate = db.query(Candidate).filter(Candidate.r_id == remark.r_id).first()
            if not candidate:
                continue
            
            # Infer status based on remark text
            remark_text = (remark.remark or "").lower()
            if "approved" in remark_text:
                inferred_status = "Approved"
            elif "rejected" in remark_text:
                inferred_status = "Rejected"
            else:
                inferred_status = candidate.status or "Pending"
            
            remark.status_after = inferred_status
            updated_count += 1
        
        db.commit()
        print(f"✅ Backfilled {updated_count} DC remarks")
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting backfill of status_after field...")
    backfill_lms_remarks()
    backfill_nseit_remarks()
    backfill_dc_remarks()
    print("✅ Backfill completed!")
