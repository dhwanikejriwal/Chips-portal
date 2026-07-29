# backend/routers/station_id.py
import re
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Form
from backend.routers.auth import get_current_user
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.station_id import StationIDRequest, StationIDRemark
from backend.models.base import StatusEnum

from backend.models.district import District
from backend.models.user_login import UserLogin
from backend.models.station_id_master import StationIDMaster
from backend.services.station_id_allocation import (
    allocate_station_ids,
    advance_counter_past,
    MissingStationMasterError,
)
import json
from backend.utils.exporter import generate_csv_export
from typing import Optional


router = APIRouter(dependencies=[Depends(get_current_user)])



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
    district_id: str = Form(...),

    model: str = Form(...),
    user_type: str = Form(...),
    user_type_custom_reason: str = Form(None),
    slot: str = Form(None),
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
        slot=slot,
        number_of_kits=number_of_kits,
        status="pending",
    )
    db.add(new_req)
    db.flush()
    
    district_obj = db.query(District).filter(District.district_code == district_id).first()
    short_name = district_obj.district_short_name if district_obj and district_obj.district_short_name else "SID"

    # Generate request_no sequentially based on the highest existing number (not count)
    # Using count() is dangerous: deletions reduce the count and cause duplicate request_nos.
    last_req = db.query(StationIDRequest).filter(
        StationIDRequest.district_id == district_id,
        StationIDRequest.request_no.isnot(None),
        StationIDRequest.id != new_req.id
    ).order_by(StationIDRequest.id.desc()).first()

    if last_req and last_req.request_no:
        try:
            last_num = int(re.sub(r'[^\d]', '', last_req.request_no.split('-K')[-1]))
        except (ValueError, TypeError, IndexError):
            last_num = 0
    else:
        last_num = 0
    new_req.request_no = f"{short_name}-K{last_num + 1:04d}"
    db.flush()
   

    initial_remark = StationIDRemark(
        request_id=new_req.id,
        author_id=dc_id,
        author_role="dc",
        remark="New Station ID request submitted by DC.",
        status_after="pending"
    )
    db.add(initial_remark)

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

        
        revert_reason = ""
        for rm in reversed(r.remarks):
            if rm.status_after_id in [StatusEnum.REVERTED.value, StatusEnum.REJECTED.value]:
                revert_reason = rm.remark
                break

        compiled_list.append({
            "id": r.id,
            "request_no": r.request_no if r.request_no else f"SID-REQ-{r.id}",
            "dc_id": r.dc_id,
            "district_name": dist_name,
            "model": str(r.model).strip().upper(),
            "user_type": str(r.user_type).strip().lower(),
            "user_type_custom_reason": r.user_type_custom_reason,
            "slot": r.slot,
            "number_of_kits": r.number_of_kits,
            "status": clean_status,
            # 🌟 FIXED: Changed r.created_at to r.submitted_at to align with the database column model schema
            "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else "",
            "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else "",
            "updated_at": str(r.remarks[-1].created_at)[:16] if r.remarks else (str(r.reviewed_at)[:16] if r.reviewed_at else (str(r.submitted_at)[:16] if r.submitted_at else "")),

            "assigned_station_id": r.station_id_inserted if r.station_id_inserted else "",
            "remarks_history": _remarks_list(r.remarks),
            "revert_reason": revert_reason
        })
    return compiled_list


@router.get("/all")
def get_all_station_requests_for_chips(db: Session = Depends(get_db)):
    """CHiPS Admin fetches all active requests committed to the infrastructure."""
    requests = db.query(StationIDRequest).order_by(
        StationIDRequest.reviewed_at.desc(),
        StationIDRequest.submitted_at.desc()
    ).all()

    
    compiled_list = []
    for r in requests:
        dist_name = r.district.district_name if r.district else f"District {r.district_id}"
        clean_status = str(r.status or "PENDING").strip().upper()

        
        compiled_list.append({
            "id": r.id,
            "request_no": r.request_no if r.request_no else f"SID-REQ-{r.id}",
            "dc_id": r.dc_id,
            "district_name": dist_name,
            "model": str(r.model).strip().upper(),
            "user_type": str(r.user_type).strip().lower(),
            "user_type_custom_reason": r.user_type_custom_reason,
            "slot": r.slot,
            "number_of_kits": r.number_of_kits,
            "status": clean_status,
            # 🌟 FIXED: Changed r.created_at to r.submitted_at to align with the database column model schema
            "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else "",
            "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else "",
            "updated_at": str(r.remarks[-1].created_at)[:16] if r.remarks else (str(r.reviewed_at)[:16] if r.reviewed_at else (str(r.submitted_at)[:16] if r.submitted_at else "")),

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
    clean_status = str(r.status or "PENDING").strip().upper()

    
    return {
        "id": r.id,
        "request_no": r.request_no if r.request_no else f"SID-REQ-{r.id}",
        "dc_id": r.dc_id,
        "district_name": dist_name,
        "model": str(r.model).strip().upper(),
        "user_type": str(r.user_type).strip().lower(),
        "user_type_custom_reason": r.user_type_custom_reason,
        "slot": r.slot,
        "number_of_kits": r.number_of_kits,
        "status": clean_status,
        # 🌟 FIXED: Changed r.created_at to r.submitted_at to align with the database column model schema
        "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else "",
        "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else "",
        "updated_at": str(r.remarks[-1].created_at)[:16] if r.remarks else (str(r.reviewed_at)[:16] if r.reviewed_at else (str(r.submitted_at)[:16] if r.submitted_at else "")),

        "station_id_inserted": r.station_id_inserted if r.station_id_inserted else "",
        "assigned_station_id": r.station_id_inserted if r.station_id_inserted else "",
        "remarks_history": _remarks_list(r.remarks)
    }


@router.get("/{request_id}/recommend-station-ids")
def recommend_station_ids(request_id: int, db: Session = Depends(get_db)):
    """Suggest the next available Station IDs for a request's district.

    Reads the district's ``station_id_master.start_station_id`` counter WITHOUT
    consuming it, so the CHIPS Admin can see (and one-click auto-fill) the IDs
    that would be allotted. The IDs are only reserved when the request is
    actually approved.
    """
    r = db.query(StationIDRequest).filter(StationIDRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Requested Station ID record not found.")

    count = r.number_of_kits if r.number_of_kits and r.number_of_kits > 0 else 1

    master = None
    if r.district_id:
        master = (
            db.query(StationIDMaster)
            .filter(StationIDMaster.district_code == str(r.district_id))
            .first()
        )
    if not master:
        return {
            "available": False,
            "district_code": r.district_id,
            "count": count,
        }

    start = int(master.start_station_id)
    recommended = [start + i for i in range(count)]
    return {
        "available": True,
        "district_code": master.district_code,
        "district_name": master.district_name,
        "count": count,
        "start_station_id": start,
        "last_allotted": start - 1,
        "recommended_ids": recommended,
        "recommended_strings": [str(x) for x in recommended],
    }


@router.patch("/{request_id}/approve")
def approve_station_request(
    request_id: int,
    reviewed_by: int = Form(...),
    station_id_value: Optional[str] = Form(None),
    slot: Optional[str] = Form(None),
    chips_remarks: Optional[str] = Form(None), # Keeps parameters null-safe
    db: Session = Depends(get_db)
):
    r = db.query(StationIDRequest).filter(StationIDRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Requested Station ID record data entry not found.")

    manual_value = (station_id_value or "").strip()
    if manual_value:
        # Manual override: CHIPS Admin supplied the exact Station ID(s).
        sids = [sid.strip() for sid in manual_value.split(",") if sid.strip()]
        if not sids:
            raise HTTPException(status_code=400, detail="Station ID assignment string cannot be evaluated empty.")

        for sid in sids:
            if not sid.isdigit() or len(sid) != 5:
                raise HTTPException(status_code=400, detail=f"Invalid Station ID format: '{sid}'. Entry must be exactly 5 numeric digits long.")
    else:
        # Auto-allocate sequential IDs from the district's master counter using
        # the same atomic read-assign-increment rule as the backfill.
        if not r.district_id:
            raise HTTPException(status_code=400, detail="Request has no district; cannot auto-allocate a Station ID.")
        count = r.number_of_kits if r.number_of_kits and r.number_of_kits > 0 else 1
        try:
            allocated = allocate_station_ids(db, r.district_id, count=count)
        except MissingStationMasterError as e:
            raise HTTPException(status_code=409, detail=str(e))
        sids = [str(sid) for sid in allocated]

    # 🌟 FIXED: Dynamically matches and saves your backup note message if left completely blank
    final_remark_string = "Station ID credentials successfully assigned."
    if chips_remarks and str(chips_remarks).strip():
        final_remark_string = str(chips_remarks).strip()

    reviewed_at = datetime.utcnow() + timedelta(hours=5, minutes=30)

    # One record per Station ID: the first stays on the original request row, and each
    # additional Station ID becomes a sibling row sharing the same request_no.
    r.status_id = StatusEnum.ALLOTTED.value
    r.station_id_inserted = sids[0]
    if slot and slot.strip():
        r.slot = slot.strip()
    r.number_of_kits = 1
    r.reviewed_by = reviewed_by
    r.reviewed_at = reviewed_at
    db.add(StationIDRemark(
        request_id=r.id,
        author_id=reviewed_by,
        author_role="chips_admin",
        remark=final_remark_string,
        status_after_id=StatusEnum.ALLOTTED.value,
    ))

    for extra_sid in sids[1:]:
        sibling = StationIDRequest(
            request_no=r.request_no,
            dc_id=r.dc_id,
            district_id=r.district_id,
            model=r.model,
            user_type=r.user_type,
            user_type_custom_reason=r.user_type_custom_reason,
            slot=r.slot,
            number_of_kits=1,
            status_id=StatusEnum.ALLOTTED.value,
            station_id_inserted=extra_sid,
            submitted_at=r.submitted_at,
            reviewed_at=reviewed_at,
            reviewed_by=reviewed_by,
        )
        db.add(sibling)
        db.flush()  # obtain sibling.id for its remark
        db.add(StationIDRemark(
            request_id=sibling.id,
            author_id=reviewed_by,
            author_role="chips_admin",
            remark=final_remark_string,
            status_after_id=StatusEnum.ALLOTTED.value,
        ))

    # Auto-create Kit Registration tracker rows for each allotted Station ID
    # (application-layer replacement for the "after allotment" DB trigger).
    from backend.routers.kit_registration import create_kit_rows_for_station_ids
    create_kit_rows_for_station_ids(
        db,
        station_ids=sids,
        district=(r.district.district_name if r.district else None),
        request_no=r.request_no,
    )

    # Keep the district counter a truthful high-water mark: advance it past the
    # IDs just allotted (whether auto-allocated or manually entered) so future
    # allocations and recommendations never collide with a used ID.
    if r.district_id:
        advance_counter_past(db, r.district_id, sids)

    db.commit()

    # 🌟 CRITICAL: Returns an explicit operational map so the async network stream closes cleanly
    return {
        "success": True,
        "message": "Transaction verified and saved.",
        "assigned_station_id": ", ".join(sids)
    }



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
    if r.status_id not in [StatusEnum.PENDING.value, StatusEnum.REAPPLIED.value]:
        raise HTTPException(status_code=400, detail=f"Cannot revert a request with status: {r.status}")

    r.status_id = StatusEnum.REVERTED.value

    r.reviewed_by = reviewed_by
    r.reviewed_at = datetime.utcnow() + timedelta(hours=5, minutes=30)

    remark = StationIDRemark(
        request_id=r.id,
        author_id=reviewed_by,
        author_role="chips_admin",
        remark=revert_reason.strip(),
        status_after_id=StatusEnum.REVERTED.value,

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
    if r.status_id != StatusEnum.REVERTED.value:

        raise HTTPException(status_code=400, detail=f"Cannot reapply a request with status: {r.status}")

    # Update the corrected fields
    r.model = model
    r.user_type = user_type
    r.user_type_custom_reason = user_type_custom_reason if user_type == "custom" else None
    r.number_of_kits = number_of_kits
    r.status_id = StatusEnum.REAPPLIED.value

    r.reviewed_at = None

    # Save DC reapply remark to conversation history
    remark = StationIDRemark(
        request_id=r.id,
        author_id=dc_id,
        author_role="dc",
        remark=reapply_remark.strip(),
        status_after_id=StatusEnum.REAPPLIED.value,

    )
    db.add(remark)
    db.commit()

    return {"message": "Request reapplied successfully.", "request_id": r.id}

@router.get("/export-excel")
def export_station_id_excel(ids: str = None, exclude_kits: bool = False, exclude_slot: bool = False, exclude_assigned_id: bool = False, db: Session = Depends(get_db)):
    query = db.query(StationIDRequest).join(District, StationIDRequest.district_id == District.district_code)
    
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.isdigit()]
        query = query.filter(StationIDRequest.id.in_(id_list))
        
    station_records = query.order_by(StationIDRequest.submitted_at.desc()).all()

    export_data = []
    for idx, r in enumerate(station_records):
        dist_name = r.district.district_name if r.district else "Unknown"
        clean_status = str(r.status or "PENDING").strip().upper()
        
        updated_time = None
        if clean_status != "PENDING":
            updated_time = r.remarks[-1].created_at if r.remarks else r.reviewed_at

        export_data.append({
            "s_no": idx + 1,
   
            "request_no": r.request_no if r.request_no else f"",
    
            "district_name": dist_name,

            "model": str(r.model).strip().upper() if r.model else "",
            "user_type": str(r.user_type).strip().lower() if r.user_type else "",
            "user_type_custom_reason": r.user_type_custom_reason or "None",
            "slot": r.slot or "",
            "number_of_kits": r.number_of_kits,
            "station_id_inserted": r.station_id_inserted or "Not Assigned Yet",
            "status": clean_status,
            "submitted_at": r.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if r.submitted_at else "",
            "reviewed_at": updated_time.strftime("%Y-%m-%d %H:%M:%S") if updated_time else ""
        })

    column_mappings = {
        "s_no": "S.No",
    
        "request_no": "Request Number",
  
        "district_name": "District Name",

        "model": "Model",
        "user_type": "Operator User Type",
        "user_type_custom_reason": "Custom Specification Remarks",
        "slot": "Type of Slot",
        "number_of_kits": "Requested Kits Quantity",
        "station_id_inserted": "Assigned Station ID",
        "status": "Status",
        "submitted_at": "Submission Timestamp",
        "reviewed_at": "Review  Timestamp"
    }

    if exclude_kits:
        column_mappings.pop("number_of_kits", None)
    if exclude_slot:
        column_mappings.pop("slot", None)
    if exclude_assigned_id:
        column_mappings.pop("station_id_inserted", None)

    return generate_csv_export(export_data, column_mappings, "station_id_complete_report")

