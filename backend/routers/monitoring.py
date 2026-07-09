from backend.models.base import get_ist_now
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Candidate, District, LMS, LMSRemark, NSEITRequest, NSEITRemark, DCRemark
from backend.models.base import StatusEnum

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

from dateutil.relativedelta import relativedelta

@router.get("/dc-stats")
def get_dc_stats(timeframe: str = "all", db: Session = Depends(get_db)):
    try:
        from backend.models.operator_activation import OperatorActivationRequest
        from backend.models.station_id import StationIDRequest
        from backend.models.l1_registration import L1RegistrationRequest
        from backend.models.l2_registration import L2RegistrationRequest
        from backend.models.reactivation import OperatorReactivationRequest

        districts = db.query(District).order_by(District.district_name.asc()).all()
        
        # Exclude skipped LMS and NSEIT requests
        skipped_lms_ids = {r.lms_id for r in db.query(LMSRemark.lms_id).filter(LMSRemark.remark.like("%skipped%")).all()}
        skipped_nseit_ids = {r.nseit_id for r in db.query(NSEITRemark.nseit_id).filter(NSEITRemark.remark.like("%skipped%")).all()}
        
        now = get_ist_now()
        start_date = None
        end_date = None
        
        if timeframe == "7_days":
            start_date = now - timedelta(days=7)
        elif timeframe == "15_days":
            start_date = now - timedelta(days=15)
        elif timeframe == "this_month":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == "last_month":
            this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = this_month_start - timedelta(microseconds=1)
            start_date = (end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)).replace(day=1)
        elif timeframe == "this_year":
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

        def filter_by_date(q, model, date_field="created_at"):
            if start_date:
                q = q.filter(getattr(model, date_field) >= start_date)
            if end_date:
                q = q.filter(getattr(model, date_field) <= end_date)
            return q

        def calc_avg_holding(requests, time_field="updated_at", create_field="created_at"):
            if not requests: return 0
            total_seconds = 0
            for r in requests:
                t_end = getattr(r, time_field, None) or now
                t_start = getattr(r, create_field, None) or now
                total_seconds += (t_end - t_start).total_seconds()
            return total_seconds / (len(requests) * 3600)

        result = []
        for dist in districts:
            dist_code = dist.district_code
            
            cands_q = db.query(Candidate).filter(Candidate.district == dist_code)
            cands = filter_by_date(cands_q, Candidate).all()
            cand_holding_hours = calc_avg_holding(cands)
            
            lms_reqs_q = db.query(LMS).join(Candidate, LMS.r_id == Candidate.r_id).filter(Candidate.district == dist_code)
            lms_reqs = filter_by_date(lms_reqs_q, LMS).all()
            lms_holding_hours = calc_avg_holding(lms_reqs)
            
            nseit_reqs_q = db.query(NSEITRequest).join(Candidate, NSEITRequest.r_id == Candidate.r_id).filter(Candidate.district == dist_code)
            nseit_reqs = filter_by_date(nseit_reqs_q, NSEITRequest).all()
            nseit_holding_hours = calc_avg_holding(nseit_reqs)

            op_act_reqs_q = db.query(OperatorActivationRequest).filter(OperatorActivationRequest.district_id == dist_code)
            op_act_reqs = filter_by_date(op_act_reqs_q, OperatorActivationRequest, date_field="submitted_at").all()
            op_act_total = len(op_act_reqs)
            op_act_reverts = sum(1 for r in op_act_reqs if r.status in ["Reverted", "Reverted by CHiPS"])
            op_act_revert_pct = round((op_act_reverts / op_act_total * 100), 1) if op_act_total > 0 else 0.0

            st_id_reqs_q = db.query(StationIDRequest).filter(StationIDRequest.district_id == dist_code)
            st_id_reqs = filter_by_date(st_id_reqs_q, StationIDRequest, date_field="submitted_at").all()
            st_id_total = len(st_id_reqs)
            st_id_reverts = sum(1 for r in st_id_reqs if r.status in ["Reverted", "Reverted by CHiPS"])
            st_id_revert_pct = round((st_id_reverts / st_id_total * 100), 1) if st_id_total > 0 else 0.0

            l1_reqs_q = db.query(L1RegistrationRequest).filter(L1RegistrationRequest.district_id == dist_code)
            l1_reqs = filter_by_date(l1_reqs_q, L1RegistrationRequest, date_field="created_at").all()
            l1_total = len(l1_reqs)
            l1_reverts = sum(1 for r in l1_reqs if r.status in ["Reverted", "Reverted by CHiPS"])
            l1_revert_pct = round((l1_reverts / l1_total * 100), 1) if l1_total > 0 else 0.0

            l2_reqs_q = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.district_id == dist_code)
            l2_reqs = filter_by_date(l2_reqs_q, L2RegistrationRequest, date_field="submitted_at").all()
            l2_total = len(l2_reqs)
            l2_reverts = sum(1 for r in l2_reqs if r.status in ["Reverted", "Reverted by CHiPS"])
            l2_revert_pct = round((l2_reverts / l2_total * 100), 1) if l2_total > 0 else 0.0

            react_reqs_q = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.district_id == dist_code)
            react_reqs = filter_by_date(react_reqs_q, OperatorReactivationRequest, date_field="created_at").all()
            react_total = len(react_reqs)
            react_reverts = sum(1 for r in react_reqs if r.status in ["Reverted", "Reverted by CHiPS"])
            react_revert_pct = round((react_reverts / react_total * 100), 1) if react_total > 0 else 0.0

            avg_holding = (cand_holding_hours + lms_holding_hours + nseit_holding_hours) / 3
            if avg_holding < 24:
                health_status = "Excellent"
            elif avg_holding < 48:
                health_status = "Needs Attention"
            else:
                health_status = "Critical"
                
            pending_total = sum(1 for c in cands if c.status == "Pending")
            rejected_total = sum(1 for c in cands if c.status == "Rejected")
            reverted_total = op_act_reverts + st_id_reverts + l1_reverts + l2_reverts + react_reverts

            result.append({
                "district_code": dist_code,
                "district_name": dist.district_name,
                "dc_name": dist.dc_name if hasattr(dist, "dc_name") else "Unknown",
                "dc_email": dist.dc_email if hasattr(dist, "dc_email") else "",
                "dc_phone": dist.dc_phone if hasattr(dist, "dc_phone") else "",
                "cand_holding_hours": cand_holding_hours,
                "lms_holding_hours": lms_holding_hours,
                "nseit_holding_hours": nseit_holding_hours,
                "op_act_total": op_act_total,
                "op_act_revert_pct": op_act_revert_pct,
                "st_id_total": st_id_total,
                "st_id_revert_pct": st_id_revert_pct,
                "l1_total": l1_total,
                "l1_revert_pct": l1_revert_pct,
                "l2_total": l2_total,
                "l2_revert_pct": l2_revert_pct,
                "react_total": react_total,
                "react_revert_pct": react_revert_pct,
                "cand_total": len(cands),
                "lms_total": len(lms_reqs),
                "nseit_total": len(nseit_reqs),
                "pending_total": pending_total,
                "rejected_total": rejected_total,
                "reverted_total": reverted_total,
                "health_status": health_status
            })
            
        return result
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


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
            lms_status = "Not Initiated" if candidate.status_id == StatusEnum.REJECTED.value else "Skipped"
        else:
            lms_status = lms.status

    nseit_status = "Not Initiated"
    if nseit:
        if nseit.id in skipped_nseit_ids:
            nseit_status = "Not Initiated" if candidate.status_id == StatusEnum.REJECTED.value else "Skipped"
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
