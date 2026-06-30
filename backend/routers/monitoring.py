from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Candidate, District, LMS, LMSRemark, NSEITRequest, NSEITRemark, DCRemark

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

@router.get("/dc-stats")
def get_dc_stats(db: Session = Depends(get_db)):
    districts = db.query(District).all()
    
    # Exclude skipped LMS and NSEIT requests
    skipped_lms_ids = {r.lms_id for r in db.query(LMSRemark.lms_id).filter(LMSRemark.remark.like("%skipped%")).all()}
    skipped_nseit_ids = {r.nseit_id for r in db.query(NSEITRemark.nseit_id).filter(NSEITRemark.remark.like("%skipped%")).all()}
    
    result = []
    for dist in districts:
        # Candidate counts
        total_candidates = db.query(Candidate).filter(Candidate.district == dist.district_code).count()
        cand_pending = db.query(Candidate).filter(Candidate.district == dist.district_code, Candidate.status == "Pending").count()
        cand_approved = db.query(Candidate).filter(Candidate.district == dist.district_code, Candidate.status == "Approved").count()
        cand_rejected = db.query(Candidate).filter(Candidate.district == dist.district_code, Candidate.status == "Rejected").count()
        
        # LMS counts
        lms_requests = db.query(LMS).join(Candidate, LMS.r_id == Candidate.r_id).filter(
            Candidate.district == dist.district_code
        ).all()
        lms_pending = sum(1 for l in lms_requests if l.status in ["Pending", "Reapplied"] and l.id not in skipped_lms_ids)
        lms_forwarded = sum(1 for l in lms_requests if l.status in ["Forwarded", "Forwarded Again"] and l.id not in skipped_lms_ids)
        lms_approved = sum(1 for l in lms_requests if l.status == "Approved" and l.id not in skipped_lms_ids)
        lms_reverted = sum(1 for l in lms_requests if l.status in ["Reverted", "Reverted by CHiPS"] and l.id not in skipped_lms_ids)
        
        # NSEIT counts
        nseit_requests = db.query(NSEITRequest).join(Candidate, NSEITRequest.r_id == Candidate.r_id).filter(
            Candidate.district == dist.district_code
        ).all()
        nseit_pending = sum(1 for n in nseit_requests if n.status in ["Pending", "Reapplied"] and n.id not in skipped_nseit_ids)
        nseit_forwarded = sum(1 for n in nseit_requests if n.status in ["Forwarded", "Forwarded Again"] and n.id not in skipped_nseit_ids)
        nseit_approved = sum(1 for n in nseit_requests if n.status == "Approved" and n.id not in skipped_nseit_ids)
        nseit_reverted = sum(1 for n in nseit_requests if n.status in ["Reverted", "Reverted by CHiPS"] and n.id not in skipped_nseit_ids)
        
        result.append({
            "district_code": dist.district_code,
            "district_name": dist.district_name,
            "district_short_name": dist.district_short_name,
            "total_candidates": total_candidates,
            "candidate_stats": {
                "pending": cand_pending,
                "approved": cand_approved,
                "rejected": cand_rejected
            },
            "lms_stats": {
                "pending": lms_pending,
                "forwarded": lms_forwarded,
                "approved": lms_approved,
                "reverted": lms_reverted
            },
            "nseit_stats": {
                "pending": nseit_pending,
                "forwarded": nseit_forwarded,
                "approved": nseit_approved,
                "reverted": nseit_reverted
            }
        })
        
    return result

@router.get("/district-detail/{district_code}")
def get_district_detail(district_code: str, db: Session = Depends(get_db)):
    district = db.query(District).filter(District.district_code == district_code).first()
    if not district:
        raise HTTPException(status_code=404, detail="District not found")
        
    # Exclude skipped LMS and NSEIT requests
    skipped_lms_ids = {r.lms_id for r in db.query(LMSRemark.lms_id).filter(LMSRemark.remark.like("%skipped%")).all()}
    skipped_nseit_ids = {r.nseit_id for r in db.query(NSEITRemark.nseit_id).filter(NSEITRemark.remark.like("%skipped%")).all()}

    # Get all candidates in district
    candidates = db.query(Candidate).filter(Candidate.district == district_code).order_by(
        func.coalesce(Candidate.updated_at, Candidate.created_at).desc()
    ).all()
    
    cand_list = []
    for c in candidates:
        lms = db.query(LMS).filter(LMS.r_id == c.r_id).first()
        nseit = db.query(NSEITRequest).filter(NSEITRequest.r_id == c.r_id).first()
        
        lms_status = "Not Initiated"
        if lms:
            if lms.id in skipped_lms_ids:
                lms_status = "Not Initiated" if c.status == "Rejected" else "Skipped"
            else:
                lms_status = lms.status
            
        nseit_status = "Not Initiated"
        if nseit:
            if nseit.id in skipped_nseit_ids:
                nseit_status = "Not Initiated" if c.status == "Rejected" else "Skipped"
            else:
                nseit_status = nseit.status
        
        cand_list.append({
            "r_id": c.r_id,
            "request_code": c.request_code,
            "name": c.name,
            "mobile": c.mobile,
            "email": c.email,
            "status": c.status,
            "lms_status": lms_status,
            "nseit_status": nseit_status,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "",
            "updated_at": c.updated_at.strftime("%Y-%m-%d %H:%M:%S") if c.updated_at else (c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "")
        })
        
    # Get LMS requests in district
    lms_requests = db.query(LMS).join(Candidate, LMS.r_id == Candidate.r_id).filter(
        Candidate.district == district_code
    ).order_by(
        func.coalesce(LMS.updated_at, LMS.created_at).desc()
    ).all()
    
    lms_list = []
    for l in lms_requests:
        if l.id in skipped_lms_ids:
            continue
        lms_list.append({
            "r_id": l.candidate.r_id,
            "request_code": l.candidate.request_code,
            "name": l.candidate.name,
            "email": l.candidate.email,
            "status": l.status,
            "lms_credential_id": l.candidate.lms_id or "",
            "created_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else "",
            "updated_at": l.updated_at.strftime("%Y-%m-%d %H:%M:%S") if l.updated_at else (l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else "")
        })
        
    # Get NSEIT requests in district
    nseit_requests = db.query(NSEITRequest).join(Candidate, NSEITRequest.r_id == Candidate.r_id).filter(
        Candidate.district == district_code
    ).order_by(
        func.coalesce(NSEITRequest.updated_at, NSEITRequest.created_at).desc()
    ).all()
    
    nseit_list = []
    for n in nseit_requests:
        if n.id in skipped_nseit_ids:
            continue
        nseit_list.append({
            "r_id": n.candidate.r_id,
            "request_code": n.candidate.request_code,
            "name": n.candidate.name,
            "email": n.candidate.email,
            "status": n.status,
            "nseit_certificate_id": n.candidate.nseit_id or "",
            "created_at": n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else "",
            "updated_at": n.updated_at.strftime("%Y-%m-%d %H:%M:%S") if n.updated_at else (n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else "")
        })
        
    return {
        "district_code": district_code,
        "district_name": district.district_name,
        "candidates": cand_list,
        "lms_requests": lms_list,
        "nseit_requests": nseit_list
    }

@router.get("/candidate-history/{request_code}")
def get_candidate_history(request_code: str, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.request_code == request_code).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found with the provided request code")
        
    district_name = candidate.district_rel.district_name if candidate.district_rel else "Unknown"
    
    lms = db.query(LMS).filter(LMS.r_id == candidate.r_id).first()
    nseit = db.query(NSEITRequest).filter(NSEITRequest.r_id == candidate.r_id).first()
    
    skipped_lms_ids = {r.lms_id for r in db.query(LMSRemark.lms_id).filter(LMSRemark.remark.like("%skipped%")).all()}
    skipped_nseit_ids = {r.nseit_id for r in db.query(NSEITRemark.nseit_id).filter(NSEITRemark.remark.like("%skipped%")).all()}
    
    lms_status = "Not Initiated"
    if lms:
        if lms.id in skipped_lms_ids:
            lms_status = "Not Initiated" if candidate.status == "Rejected" else "Skipped"
        else:
            lms_status = lms.status

    nseit_status = "Not Initiated"
    if nseit:
        if nseit.id in skipped_nseit_ids:
            nseit_status = "Not Initiated" if candidate.status == "Rejected" else "Skipped"
        else:
            nseit_status = nseit.status
    
    timeline = []
    
    # 1. Candidate Registration
    timeline.append({
        "step": "Candidate Request",
        "action": "Registration",
        "remark": "Candidate registration completed successfully.",
        "time": candidate.created_at.strftime("%Y-%m-%d %H:%M:%S") if candidate.created_at else "",
        "timestamp": candidate.created_at,
        "sender_role": "Candidate",
        "sender_username": candidate.name
    })
    
    # 2. DC Remarks/Actions for Candidate Onboarding
    remarks = db.query(DCRemark).filter(DCRemark.r_id == candidate.r_id).all()
    for r in remarks:
        role_name = r.author.role.role if r.author and r.author.role else "Admin"
        timeline.append({
            "step": "Candidate Request",
            "action": "Verification Decision",
            "remark": r.remark,
            "time": r.time.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": r.time,
            "sender_role": role_name if role_name in ["DC", "EDM"] else "CHIPS",
            "sender_username": r.author.username if r.author else "System",
            "status_after": r.status_after
        })
        
    # 3. LMS Remarks/Actions
    if lms and lms.id not in skipped_lms_ids:
        lms_remarks = db.query(LMSRemark).filter(LMSRemark.lms_id == lms.id).all()
        for r in lms_remarks:
            sender_role = "Candidate"
            sender_username = "Candidate"
            if r.admin_by_id:
                if r.admin_author and r.admin_author.role:
                    role_name = r.admin_author.role.role
                    sender_role = "CHIPS" if role_name == "Admin" else role_name
                else:
                    sender_role = "CHIPS"
                sender_username = r.admin_author.username if r.admin_author else "System"
            elif r.candidate_by_id:
                sender_role = "Candidate"
                sender_username = r.candidate_author.user_id if r.candidate_author else "Candidate"
                
            timeline.append({
                "step": "LMS Credential",
                "action": "Review Action",
                "remark": r.remark,
                "time": r.time.strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": r.time,
                "sender_role": sender_role,
                "sender_username": sender_username,
                "status_after": r.status_after
            })
            
    # 4. NSEIT Remarks/Actions
    if nseit and nseit.id not in skipped_nseit_ids:
        nseit_remarks = db.query(NSEITRemark).filter(NSEITRemark.nseit_id == nseit.id).all()
        for r in nseit_remarks:
            sender_role = "Candidate"
            sender_username = "Candidate"
            if r.admin_by_id:
                if r.admin_author and r.admin_author.role:
                    role_name = r.admin_author.role.role
                    sender_role = "CHIPS" if role_name == "Admin" else role_name
                else:
                    sender_role = "CHIPS"
                sender_username = r.admin_author.username if r.admin_author else "System"
            elif r.candidate_by_id:
                sender_role = "Candidate"
                sender_username = r.candidate_author.user_id if r.candidate_author else "Candidate"
                
            timeline.append({
                "step": "NSEIT Certificate",
                "action": "Review Action",
                "remark": r.remark,
                "time": r.time.strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": r.time,
                "sender_role": sender_role,
                "sender_username": sender_username,
                "status_after": r.status_after
            })
            
    # Sort timeline by timestamp ascending
    # Ensure any None timestamps don't crash the sort
    timeline.sort(key=lambda x: x["timestamp"] or datetime.min)
    
    # Strip the raw timestamp objects for JSON serialization safety
    for t in timeline:
        del t["timestamp"]
        
    return {
        "r_id": candidate.r_id,
        "request_code": candidate.request_code,
        "name": candidate.name,
        "mobile": candidate.mobile,
        "email": candidate.email,
        "district_code": candidate.district,
        "district_name": district_name,
        "qualification": candidate.qualification,
        "dob": candidate.dob.strftime("%Y-%m-%d") if candidate.dob else "",
        "aadhaar": candidate.aadhaar,
        "marksheet_upload": candidate.marksheet_upload,
        "tenth_marksheet_upload": candidate.tenth_marksheet_upload,
        "status": candidate.status,
        "lms_id": candidate.lms_id or "",
        "nseit_id": candidate.nseit_id or "",
        "lms_status": lms_status,
        "nseit_status": nseit_status,
        "timeline": timeline
    }
