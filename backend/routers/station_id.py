# backend/routers/station_id.py
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.station_id import StationIDRequest, StationIDRemark
from backend.models.district import District
from backend.models import UserLogin

router = APIRouter()


def _fmt(dt):
    return str(dt)[:16] if dt else None


def _remarks_list(remarks):
    return [
        {
            "author_role": rm.author_role.upper(),
            "remark": rm.remark,
            "created_at": _fmt(rm.created_at),
        }
        for rm in remarks
    ]


# ─────────────────────────────────────────────
# DC ROUTES
# ─────────────────────────────────────────────


@router.post("/submit")
def submit_station_id_request(
    dc_id: int = Form(...),
    district_id: int = Form(...),
    model: str = Form(...),
    user_type: str = Form(...),
    user_type_custom_reason: str = Form(None),
    number_of_kits: int = Form(...),
    db: Session = Depends(get_db),
):
    """DC submits a new Station ID request."""
    # Find district short name
    dist = db.query(District).filter(District.district_code == str(district_id)).first()
    short = dist.district_short_name if dist else "RPR"

    new_req = StationIDRequest(
        dc_id=dc_id,
        district_id=str(district_id),
        model=model,
        user_type=user_type,
        user_type_custom_reason=user_type_custom_reason if user_type == "custom" else None,
        number_of_kits=number_of_kits,
        status="sent_to_chips",
    )
    db.add(new_req)
    db.flush()

    # Calculate next sequence number for this district
    last_req = db.query(StationIDRequest).filter(
        StationIDRequest.district_id == str(district_id),
        StationIDRequest.id != new_req.id
    ).order_by(StationIDRequest.id.desc()).first()

    next_num = 1
    if last_req and last_req.request_no:
        parts = last_req.request_no.split("-")
        if len(parts) >= 2 and parts[-1].startswith("K"):
            try:
                next_num = int(parts[-1][1:]) + 1
            except ValueError:
                next_num = db.query(StationIDRequest).filter(
                    StationIDRequest.district_id == str(district_id)
                ).count()
    else:
        next_num = db.query(StationIDRequest).filter(
            StationIDRequest.district_id == str(district_id)
        ).count()

    new_req.request_no = f"{short}-K{next_num:04d}"
    db.commit()
    db.refresh(new_req)

    return {
        "message": "Station ID request submitted successfully.",
        "request_id": new_req.id,
        "request_no": new_req.request_no,
        "status": new_req.status,
    }


# ───────────────────────────────────────────────────────────────────
# 🌟 UNIFORM RELATION-MAPPED DASHBOARD QUEUE ENDPOINTS
# ───────────────────────────────────────────────────────────────────

# ───────────────────────────────────────────────────────────────────
# 🌟 UNIFORM SCHEMA-MAPPED DASHBOARD QUEUE ENDPOINTS
# ───────────────────────────────────────────────────────────────────

@router.get("/dc/{dc_id}")
def get_dc_station_requests(dc_id: int, db: Session = Depends(get_db)):
    """All Station ID requests for the DC's district (see get_dc_requests note).

    Scope by district so every coordinator of a district sees all of its
    requests, including anything reverted/rejected by CHiPS; fall back to dc_id.
    """
    user = db.query(UserLogin).filter(UserLogin.id == dc_id).first()
    district_id = user.district_id if user and user.district_id else None

    query = db.query(StationIDRequest)
    if district_id:
        query = query.filter(StationIDRequest.district_id == str(district_id))
    else:
        query = query.filter(StationIDRequest.dc_id == dc_id)

    requests = query.order_by(StationIDRequest.submitted_at.desc()).all()
    
    compiled_list = []
    for r in requests:
        dist_name = r.district.district_name if r.district else f"District {r.district_id}"
        clean_status = str(r.status or "sent_to_chips").strip().lower()
        
        compiled_list.append({
            "id": r.id,
            "request_no": r.request_no if r.request_no else f"SID-REQ-{r.id}",
            "dc_id": r.dc_id,
            "district_name": dist_name,
            "model": str(r.model).strip().upper(),
            "user_type": str(r.user_type).strip().lower(),
            "user_type_custom_reason": r.user_type_custom_reason,
            "number_of_kits": r.number_of_kits,
            "status": clean_status,
            # 🌟 FIXED: Changed r.created_at to r.submitted_at to align with the database column model schema
            "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else "",
            "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else "",
            "assigned_station_id": r.station_id_inserted if r.station_id_inserted else "",
            "remarks_history": _remarks_list(r.remarks)
        })
    return compiled_list


@router.get("/all")
def get_all_station_requests_for_chips(db: Session = Depends(get_db)):
    """CHiPS Admin fetches all active requests committed to the infrastructure."""
    requests = db.query(StationIDRequest).order_by(StationIDRequest.submitted_at.desc()).all()
    
    compiled_list = []
    for r in requests:
        dist_name = r.district.district_name if r.district else f"District {r.district_id}"
        clean_status = str(r.status or "sent_to_chips").strip().lower()
        
        compiled_list.append({
            "id": r.id,
            "request_no": r.request_no if r.request_no else f"SID-REQ-{r.id}",
            "dc_id": r.dc_id,
            "district_name": dist_name,
            "model": str(r.model).strip().upper(),
            "user_type": str(r.user_type).strip().lower(),
            "user_type_custom_reason": r.user_type_custom_reason,
            "number_of_kits": r.number_of_kits,
            "status": clean_status,
            # 🌟 FIXED: Changed r.created_at to r.submitted_at to align with the database column model schema
            "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else "",
            "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else "",
            "station_id_inserted": r.station_id_inserted if r.station_id_inserted else "",
            "remarks_history": _remarks_list(r.remarks)
        })
    return compiled_list


@router.get("/{request_id}/detail")
def get_station_request_individual_detail(request_id: int, db: Session = Depends(get_db)):
    """Resolves frontend detail blocks by mapping properties onto modal containers."""
    r = db.query(StationIDRequest).filter(StationIDRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Requested Station ID record not found.")
        
    dist_name = r.district.district_name if r.district else f"District {r.district_id}"
    clean_status = str(r.status or "sent_to_chips").strip().lower()
    
    return {
        "id": r.id,
        "request_no": r.request_no if r.request_no else f"SID-REQ-{r.id}",
        "dc_id": r.dc_id,
        "district_name": dist_name,
        "model": str(r.model).strip().upper(),
        "user_type": str(r.user_type).strip().lower(),
        "user_type_custom_reason": r.user_type_custom_reason,
        "number_of_kits": r.number_of_kits,
        "status": clean_status,
        # 🌟 FIXED: Changed r.created_at to r.submitted_at to align with the database column model schema
        "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else "",
        "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else "",
        "station_id_inserted": r.station_id_inserted if r.station_id_inserted else "",
        "assigned_station_id": r.station_id_inserted if r.station_id_inserted else "",
        "remarks_history": _remarks_list(r.remarks)
    }


@router.patch("/{request_id}/approve")
def approve_station_request(
    request_id: int,
    reviewed_by: int = Form(...),
    station_id_value: str = Form(...),
    chips_remarks: str = Form(None),
    db: Session = Depends(get_db),
):
    """CHIPS Admin inserts the actual Station ID and approves the request."""
    r = db.query(StationIDRequest).filter(StationIDRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")
    if r.status not in ["sent_to_chips", "reapplied"]:
        raise HTTPException(status_code=400, detail=f"Cannot approve a request with status: {r.status}")

    r.status = "approved"
    r.station_id_inserted = station_id_value.strip()
    r.reviewed_by = reviewed_by
    r.reviewed_at = datetime.utcnow() + timedelta(hours=5, minutes=30)

    if chips_remarks and chips_remarks.strip():
        remark = StationIDRemark(
            request_id=r.id,
            author_id=reviewed_by,
            author_role="chips_admin",
            remark=chips_remarks.strip(),
        )
        db.add(remark)

    db.commit()
    return {"message": "Station ID request approved.", "request_id": r.id, "station_id": r.station_id_inserted}


@router.patch("/{request_id}/revert")
def revert_station_request(
    request_id: int,
    reviewed_by: int = Form(...),
    revert_reason: str = Form(...),
    db: Session = Depends(get_db),
):
    """CHIPS Admin reverts the request with a mandatory remark."""
    r = db.query(StationIDRequest).filter(StationIDRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")
    if r.status not in ["sent_to_chips", "reapplied"]:
        raise HTTPException(status_code=400, detail=f"Cannot revert a request with status: {r.status}")

    r.status = "reverted"
    r.reviewed_by = reviewed_by
    r.reviewed_at = datetime.utcnow() + timedelta(hours=5, minutes=30)

    remark = StationIDRemark(
        request_id=r.id,
        author_id=reviewed_by,
        author_role="chips_admin",
        remark=revert_reason.strip(),
    )
    db.add(remark)
    db.commit()

    return {"message": "Request reverted.", "request_id": r.id}


@router.post("/dc/{request_id}/reapply")
def reapply_station_request(
    request_id: int,
    dc_id: int = Form(...),
    model: str = Form(...),
    user_type: str = Form(...),
    user_type_custom_reason: str = Form(None),
    number_of_kits: int = Form(...),
    reapply_remark: str = Form(...),
    db: Session = Depends(get_db),
):
    """DC corrects and reapplies a reverted Station ID request."""
    r = db.query(StationIDRequest).filter(StationIDRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")
    if r.status != "reverted":
        raise HTTPException(status_code=400, detail=f"Cannot reapply a request with status: {r.status}")

    # Update the corrected fields
    r.model = model
    r.user_type = user_type
    r.user_type_custom_reason = user_type_custom_reason if user_type == "custom" else None
    r.number_of_kits = number_of_kits
    r.status = "reapplied"
    r.reviewed_at = None

    # Save DC reapply remark to conversation history
    remark = StationIDRemark(
        request_id=r.id,
        author_id=dc_id,
        author_role="dc",
        remark=reapply_remark.strip(),
    )
    db.add(remark)
    db.commit()

    return {"message": "Request reapplied successfully.", "request_id": r.id}
