# backend/routers/station_id.py
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.station_id import StationIDRequest, StationIDRemark
from backend.utils.exporter import generate_csv_export

router = APIRouter()


def _fmt(dt):
    return str(dt)[:16] if dt else None


def _remarks_list(remarks):
    return [
        {
            "author_role": rm.author_role.upper(),
            "remark": rm.remark,
            "created_at": _fmt(rm.created_at),
            "status_after": rm.status_after,
            "sender_username": rm.author.username if rm.author else "",
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
    new_req = StationIDRequest(
        dc_id=dc_id,
        district_id=district_id,
        model=model,
        user_type=user_type,
        user_type_custom_reason=user_type_custom_reason if user_type == "custom" else None,
        number_of_kits=number_of_kits,
        status="sent_to_chips",
    )
    db.add(new_req)
    db.flush()
    new_req.request_no = f"SID-A{new_req.id:04d}"
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
    """DC fetches historical submissions mapped to their profile configuration."""
    requests = db.query(StationIDRequest).filter(StationIDRequest.dc_id == dc_id).order_by(StationIDRequest.submitted_at.desc()).all()
    
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
            status_after="approved",
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
        status_after="reverted",
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
        status_after="reapplied",
    )
    db.add(remark)
    db.commit()

    return {"message": "Request reapplied successfully.", "request_id": r.id}


@router.get("/export-excel")
def export_station_id_excel(ids: str = None, db: Session = Depends(get_db)):
    query = db.query(StationIDRequest)
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.isdigit()]
        query = query.filter(StationIDRequest.id.in_(id_list))
    records = query.all()

    export_data = []
    for idx, r in enumerate(records):
        dist_name = r.district.district_name if r.district else f"District {r.district_id}"
        user_type_display = r.user_type_custom_reason if r.user_type == "custom" and r.user_type_custom_reason else str(r.user_type).replace("_", " ").title()
        export_data.append({
            "s_no": idx + 1,
            "request_no": r.request_no or f"SID-REQ-{r.id}",
            "district_name": dist_name,
            "model": str(r.model).strip().upper(),
            "user_type": user_type_display,
            "number_of_kits": r.number_of_kits,
            "status": str(r.status or "sent_to_chips").replace("_", " ").title(),
            "assigned_station_id": r.station_id_inserted or "",
            "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else "",
            "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else "",
        })

    column_mappings = {
        "s_no": "S.No",
        "request_no": "Request No",
        "district_name": "District",
        "model": "Device Model",
        "user_type": "User Type",
        "number_of_kits": "Number of Kits",
        "status": "Status",
        "assigned_station_id": "Assigned Station ID",
        "submitted_at": "Submitted At",
        "reviewed_at": "Reviewed At",
    }

    return generate_csv_export(export_data, column_mappings, "station_id_requests")
