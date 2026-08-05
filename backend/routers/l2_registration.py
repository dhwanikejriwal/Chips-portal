# backend/routers/l2_registration.py
import re

import io
import openpyxl
from fastapi import APIRouter, Depends, Form, HTTPException
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from backend.utils.exporter import generate_excel_export
from sqlalchemy.orm import Session
from sqlalchemy import text, or_
from backend.database import SessionLocal
from backend.models import L2RegistrationRequest, L2RegistrationRemark, User, District, StationIDRequest
from backend.models.base import get_ist_time, StatusEnum

from backend.routers.auth import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


# Dependency to get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/submit")
def submit_l2_request(
    dc_id: int = Form(...),
    district_id: str = Form(...),
    client_version: str = Form(...),
    new_station_id: str = Form(...),
    ea_code: str = Form(...),
    reg_code: str = Form(...),
    new_machine_id: str = Form(...),
    client_type: str = Form(...),
    old_station_id: str = Form(None),
    reason_for_l2_registration: str = Form(None),
    old_machine_id: str = Form(None),
    tech_center_remarks: str = Form(None),
    operator_name: str = Form(None),
    operator_id: str = Form(None),
    unique_id: str = Form(None),
    block: str = Form(None),
    address_of_govt_premises: str = Form(None),
    db: Session = Depends(get_db)
):
    # Verify DC exists
    dc_user = db.query(User).filter(User.id == dc_id).first()
    if not dc_user:
        raise HTTPException(status_code=404, detail="DC User not found.")

    # Create Request
    new_req = L2RegistrationRequest(
        dc_id=dc_id,
        district_id=district_id,
        client_version=client_version,
        new_station_id=new_station_id,
        ea_code=ea_code,
        reg_code=reg_code,
        new_machine_id=new_machine_id,
        client_type=client_type,
        old_station_id=old_station_id,
        reason_for_l2_registration=reason_for_l2_registration,
        old_machine_id=old_machine_id,
        tech_center_remarks=tech_center_remarks,
        operator_name=operator_name.strip() if operator_name else "",
        operator_id=operator_id.strip() if operator_id else "",
        unique_id=unique_id.strip() if unique_id else "",
        block=block.strip() if block else "",
        address_of_govt_premises=address_of_govt_premises.strip() if address_of_govt_premises else "",
        status_id=StatusEnum.PENDING.value
    )
    db.add(new_req)
    db.commit()
    db.refresh(new_req)

    # Look up approved StationIDRequest matching new_station_id
    station_req = db.query(StationIDRequest).filter(
        StationIDRequest.station_id_inserted == new_station_id.strip(),
        StationIDRequest.status_id == StatusEnum.ALLOTTED.value
    ).first()

    if station_req:
        new_req.request_no = f"{station_req.request_no}{new_station_id.strip()}"
    else:
        last_req = db.query(L2RegistrationRequest).filter(
            L2RegistrationRequest.request_no.isnot(None),
            L2RegistrationRequest.id != new_req.id
        ).order_by(L2RegistrationRequest.id.desc()).first()

        if last_req and last_req.request_no:
            try:
                num_str = last_req.request_no.replace("L2-A", "")
                last_num = int(re.sub(r'[^\d]', '', num_str)) if num_str else 0
            except (ValueError, TypeError):
                last_num = 0
        else:
            last_num = 0
        new_req.request_no = f"L2-A{last_num + 1:04d}"

    initial_remark = L2RegistrationRemark(
        request_id=new_req.id,
        author_id=dc_id,
        author_role="dc",
        remark="Request submitted by DC.",
        status_after_id=StatusEnum.PENDING.value
    )
    db.add(initial_remark)

    db.commit()
    db.refresh(new_req)

    return {"message": "L2 Registration request submitted successfully.", "request_id": new_req.id, "request_no": new_req.request_no}

@router.get("/dc/{dc_id}")
def get_dc_requests(dc_id: int, db: Session = Depends(get_db)):
    # Scope by the coordinator's district (a district can have several DC/EDM
    # logins); every coordinator must see all district requests, including
    # anything reverted/rejected by CHiPS. Fall back to dc_id if unresolved.
    user = db.query(User).filter(User.id == dc_id).first()
    district_id = user.district_id if user and user.district_id else None

    query = db.query(L2RegistrationRequest)
    if district_id:
        query = query.filter(L2RegistrationRequest.district_id == str(district_id))
    else:
        query = query.filter(L2RegistrationRequest.dc_id == dc_id)

    reqs = query.order_by(L2RegistrationRequest.submitted_at.desc()).all()

    
    result = []
    for r in reqs:
        remarks_history = [
            {
                "author_role": rm.author_role.upper(),
                "remark": rm.remark,
                "created_at": str(rm.created_at)[:16],
                "status_after": rm.status_after,
                "sender_username": rm.author.username if rm.author else "",

            } for rm in r.remarks
        ]
        
        # 🌟 UNIFORM SCHEMA FIX: Map strictly to district_name & clean lowercase status keys
        dist_name = r.district.district_name if r.district else "—"
        clean_status = str(r.status or "PENDING").strip().upper()

        
        revert_reason = ""
        for rm in reversed(r.remarks):
            if rm.status_after_id in [StatusEnum.REVERTED.value, StatusEnum.REJECTED.value]:
                revert_reason = rm.remark
                break

        result.append({
            "id": r.id,
            "request_no": r.request_no,
            "operator_name": r.operator_name,
            "operator_id": r.operator_id,
            "client_version": r.client_version,
            "new_station_id": r.new_station_id,
            "new_machine_id": r.new_machine_id,
            "client_type": r.client_type,
            "old_station_id": r.old_station_id,
            "reason_for_l2_registration": r.reason_for_l2_registration,
            "old_machine_id": r.old_machine_id,
            "tech_center_remarks": r.tech_center_remarks,
            "ea_code": r.ea_code,
            "reg_code": r.reg_code,
            "unique_id": r.unique_id,
            "district_name": dist_name,
            "block": r.block,
            "address_of_govt_premises": r.address_of_govt_premises,
            "status": clean_status,
            "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else "",
            "updated_at": remarks_history[-1]["created_at"] if remarks_history else (str(r.submitted_at)[:16] if r.submitted_at else ""),
            "is_mailed": getattr(r, 'is_mailed', 0) or 0,
            "remarks_history": remarks_history,
            "revert_reason": revert_reason
        })

    # Sort descending by latest action
    result.sort(key=lambda x: x["updated_at"] or x["submitted_at"], reverse=True)

    return result


@router.get("/awaiting-l2/{dc_id}")
def get_awaiting_l2(dc_id: int, db: Session = Depends(get_db)):
    """Stations whose L1 registration is Done but that have no L2 request yet.

    These are the requests the DC still needs to fill L2 for. Scoped to the
    coordinator's district; once an L2 request exists for a station it drops
    off this list. Mirrors the L1 "Awaiting L1 (Station ID Allotted)" section.
    """
    from backend.models.l1_registration import L1RegistrationRequest

    # L1 states that count as "done" — kept in sync with the kit tracker.
    L1_DONE_STATES = [
        StatusEnum.L1_DONE.value,
        StatusEnum.APPROVED.value,
        StatusEnum.APPROVED.value,
    ]

    user = db.query(User).filter(User.id == dc_id).first()
    district_id = user.district_id if user and user.district_id else None

    q = db.query(L1RegistrationRequest).filter(
        L1RegistrationRequest.status_id.in_(L1_DONE_STATES)
    )
    if district_id:
        q = q.filter(L1RegistrationRequest.district_id == str(district_id))
    else:
        q = q.filter(L1RegistrationRequest.dc_id == dc_id)
    done_l1 = q.order_by(L1RegistrationRequest.updated_at.desc()).all()

    # Station IDs that already have an L2 request (any status) → exclude
    existing_l2 = {
        (s.new_station_id or "").strip()
        for s in db.query(L2RegistrationRequest.new_station_id).all()
    }

    out = []
    seen = set()
    for r in done_l1:
        sid = (r.station_id or "").strip()
        if not sid or sid in existing_l2 or sid in seen:
            continue
        seen.add(sid)
        dist_name = r.district.district_name if r.district else ""
        out.append({
            "station_id": sid,
            "request_no": r.request_code or "—",
            "model": r.model_type or "—",
            "district_name": dist_name,
            "l1_done_at": str(r.updated_at)[:19] if r.updated_at else "—",
        })
    return out


@router.get("/prefill/{station_id}")
def get_l2_prefill(station_id: str, db: Session = Depends(get_db)):
    """Everything already known about a Station ID from the earlier stages
    (Station ID request + L1 registration), used to pre-fill the L2 form.

    Every value is read from the database for this specific station — nothing
    is hardcoded. Only fields we actually captured before are returned; L2-only
    fields (old station/machine, reason, block, address, etc.) are left blank
    for the DC to fill.
    """
    from backend.models.l1_registration import L1RegistrationRequest

    sid = (station_id or "").strip()

    # Latest L1 registration for this station (source of most operator/hardware data)
    l1 = (
        db.query(L1RegistrationRequest)
        .filter(L1RegistrationRequest.station_id == sid)
        .order_by(L1RegistrationRequest.id.desc())
        .first()
    )

    # Matching Station ID allotment row (exact match within the comma-separated list)
    station_req = None
    for s in (
        db.query(StationIDRequest)
        .filter(StationIDRequest.station_id_inserted.isnot(None))
        .order_by(StationIDRequest.id.desc())
        .all()
    ):
        ids = [x.strip() for x in str(s.station_id_inserted).split(",")]
        if sid in ids:
            station_req = s
            break

    data = {"new_station_id": sid}

    if l1 is not None:
        data.update({
            "new_machine_id": l1.machine_id or "",
            "operator_name": l1.operator_name or "",
            "operator_id": l1.operator_id or "",
            # L1 software version → L2 client version; L1 model type → L2 client type.
            "client_version": l1.software_version or "",
            "client_type": l1.model_type or "",
            "request_no": l1.request_code or "",
            "district_id": str(l1.district_id) if l1.district_id else "",
            "district_name": l1.district.district_name if l1.district else "",
        })

    if station_req is not None:
        # Fall back to allotment data where L1 didn't provide it.
        if not data.get("client_type"):
            data["client_type"] = station_req.model or ""
        if not data.get("district_id") and station_req.district_id:
            data["district_id"] = str(station_req.district_id)
        if not data.get("district_name") and station_req.district:
            data["district_name"] = station_req.district.district_name

    return data


@router.get("/all")
def get_all_requests(db: Session = Depends(get_db)):
    reqs = db.query(L2RegistrationRequest).order_by(L2RegistrationRequest.submitted_at.desc()).all()
    
    result = []
    for r in reqs:
        remarks_history = [
            {
                "author_role": rm.author_role.upper(),
                "remark": rm.remark,
                "created_at": str(rm.created_at)[:16],
                "status_after": rm.status_after,
                "sender_username": rm.author.username if rm.author else "",

            } for rm in r.remarks
        ]
        
        # 🌟 UNIFORM SCHEMA FIX: Map strictly to district_name & clean lowercase status keys
        dist_name = r.district.district_name if r.district else "—"
        clean_status = "L2_DONE" if r.status_id in [StatusEnum.L2_DONE.value, StatusEnum.APPROVED.value, 20] else str(r.status or "PENDING").strip().upper()

        
        result.append({
            "id": r.id,
            "request_no": r.request_no,
            "operator_name": r.operator_name,
            "operator_id": r.operator_id,
            "client_version": r.client_version,
            "new_station_id": r.new_station_id,
            "new_machine_id": r.new_machine_id,
            "client_type": r.client_type,
            "old_station_id": r.old_station_id,
            "reason_for_l2_registration": r.reason_for_l2_registration,
            "old_machine_id": r.old_machine_id,
            "tech_center_remarks": r.tech_center_remarks,
            "ea_code": r.ea_code,
            "reg_code": r.reg_code,
            "unique_id": r.unique_id,
            "district_name": dist_name,
            "block": r.block,
            "address_of_govt_premises": r.address_of_govt_premises,
            "status": clean_status,
            "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else "",
            "updated_at": remarks_history[-1]["created_at"] if remarks_history else (str(r.submitted_at)[:16] if r.submitted_at else ""),
            "is_mailed": int(r.is_mailed or 0),
            "remarks_history": remarks_history
        })

    # Sort descending by latest action
    result.sort(key=lambda x: x["updated_at"] or x["submitted_at"], reverse=True)

    return result

# 🌟 ROUTE ROUTING SIGNATURE FIXED: Keeps endpoint paths perfectly synchronized
# 🌟 FIXED: Stack both routes so the backend safely catches both endpoint paths perfectly
@router.get("/{request_id}")
@router.get("/{request_id}/detail")
def get_request_details(request_id: int, db: Session = Depends(get_db)):
    r = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")
    
    remarks_history = [
        {
            "author_role": rm.author_role.upper(),
            "remark": rm.remark,
            "created_at": str(rm.created_at)[:16],
            "status_after": rm.status_after,
            "sender_username": rm.author.username if rm.author else "",

        } for rm in r.remarks
    ]

    # 🌟 UNIFORM SCHEMA FIX: Map strictly to district_name & clean lowercase status keys
    dist_name = r.district.district_name if r.district else "—"
    clean_status = "L2_DONE" if r.status_id in [StatusEnum.L2_DONE.value, StatusEnum.APPROVED.value, 20] else str(r.status or "PENDING").strip().upper()


    return {
        "id": r.id,
        "request_no": r.request_no,
        "dc_id": r.dc_id,
        "district_id": r.district_id,
        "district_name": dist_name,
        "client_version": r.client_version,
        "new_station_id": r.new_station_id,
        "ea_code": r.ea_code,
        "reg_code": r.reg_code,
        "new_machine_id": r.new_machine_id,
        "client_type": r.client_type,
        "old_station_id": r.old_station_id,
        "reason_for_l2_registration": r.reason_for_l2_registration,
        "old_machine_id": r.old_machine_id,
        "tech_center_remarks": r.tech_center_remarks,
        "operator_name": r.operator_name,
        "operator_id": r.operator_id,
        "unique_id": r.unique_id,
        "block": r.block,
        "address_of_govt_premises": r.address_of_govt_premises,
        "status": clean_status,
        "uidai_remarks": r.uidai_remarks,
        "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else "",
        "updated_at": remarks_history[-1]["created_at"] if remarks_history else (str(r.submitted_at)[:16] if r.submitted_at else ""),
        "is_mailed": int(r.is_mailed or 0),
        "remarks_history": remarks_history
    }

@router.patch("/{request_id}/send-to-uidai")
def send_to_uidai(
    request_id: int,
    reviewed_by: int = Form(...),
    uidai_remarks: str = Form(None),
    db: Session = Depends(get_db)
):
    r = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")

    r.status_id = StatusEnum.SENT_TO_UIDAI.value

    r.reviewed_by = reviewed_by
    r.reviewed_at = get_ist_time()
    r.uidai_remarks = uidai_remarks

    remark_text = uidai_remarks.strip() if uidai_remarks and uidai_remarks.strip() else "Request forwarded to UIDAI for processing."
    remark = L2RegistrationRemark(
        request_id=r.id, author_id=reviewed_by, author_role="chips_admin",
        remark=remark_text,
        status_after_id=StatusEnum.SENT_TO_UIDAI.value
    )
    db.add(remark)

    db.commit()
    return {"message": "Status updated to sent_to_uidai."}

@router.patch("/{request_id}/uidai-approve")
def uidai_approve(
    request_id: int,
    reviewed_by: int = Form(...),
    uidai_remarks: str = Form(None),
    db: Session = Depends(get_db)
):
    r = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")

    r.status_id = StatusEnum.L2_DONE.value

    r.reviewed_by = reviewed_by
    r.reviewed_at = get_ist_time()
    r.uidai_remarks = uidai_remarks

    # Add approval remark to history
    remark_text = uidai_remarks.strip() if uidai_remarks and uidai_remarks.strip() else "Request successfully approved by UIDAI."
    remark = L2RegistrationRemark(
        request_id=r.id, author_id=reviewed_by, author_role="chips_admin",
        remark=remark_text, status_after_id=StatusEnum.L2_DONE.value

    )
    db.add(remark)
    db.commit()
    return {"message": "Request approved."}

@router.patch("/{request_id}/uidai-reject")
def uidai_reject(
    request_id: int,
    reviewed_by: int = Form(...),
    uidai_remarks: str = Form(...),
    db: Session = Depends(get_db)
):
    r = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")

    r.status_id = StatusEnum.REJECTED.value

    r.reviewed_by = reviewed_by
    r.reviewed_at = get_ist_time()
    r.uidai_remarks = uidai_remarks

    # Add rejection remark to history
    remark = L2RegistrationRemark(
        request_id=r.id, author_id=reviewed_by, author_role="chips_admin",
        remark=uidai_remarks.strip(),  # 🌟 FIXED: Dropped manual 'UIDAI Rejected. Remarks:' prefix string layout
        status_after_id=StatusEnum.REJECTED.value

    )
    db.add(remark)
    db.commit()
    return {"message": "Request rejected."}

@router.patch("/{request_id}/revert")
def revert_request(
    request_id: int,
    reviewed_by: int = Form(...),
    revert_reason: str = Form(...),
    db: Session = Depends(get_db)
):
    r = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")

    r.status_id = StatusEnum.REVERTED.value

    r.reviewed_by = reviewed_by
    r.reviewed_at = get_ist_time()

    # Log Revert Remark
    remark = L2RegistrationRemark(
        request_id=r.id, author_id=reviewed_by, author_role="chips_admin",
        remark=revert_reason.strip(),  # 🌟 FIXED: Dropped manual 'Reverted back to DC:' prefix string layout
        status_after_id=StatusEnum.REVERTED.value

    )
    db.add(remark)
    db.commit()
    return {"message": "Request reverted to DC."}

@router.post("/dc/{request_id}/reapply")
def reapply_l2_request(
    request_id: int,
    dc_id: int = Form(...),
    client_version: str = Form(...),
    new_station_id: str = Form(...),
    ea_code: str = Form(...),
    reg_code: str = Form(...),
    new_machine_id: str = Form(...),
    client_type: str = Form(...),
    old_station_id: str = Form(None),
    reason_for_l2_registration: str = Form(None),
    old_machine_id: str = Form(None),
    tech_center_remarks: str = Form(None),
    operator_name: str = Form(...),
    operator_id: str = Form(...),
    unique_id: str = Form(None),
    block: str = Form(...),
    address_of_govt_premises: str = Form(...),
    reapply_remark: str = Form(...),
    db: Session = Depends(get_db)
):
    r = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.id == request_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")

    if r.status_id not in [StatusEnum.REVERTED.value, StatusEnum.REJECTED.value]:

        raise HTTPException(status_code=400, detail="Can only reapply reverted or rejected requests.")

    # Update Fields
    r.client_version = client_version
    r.new_station_id = new_station_id
    r.ea_code = ea_code
    r.reg_code = reg_code
    r.new_machine_id = new_machine_id
    r.client_type = client_type
    r.old_station_id = old_station_id
    r.reason_for_l2_registration = reason_for_l2_registration
    r.old_machine_id = old_machine_id
    r.tech_center_remarks = tech_center_remarks
    r.operator_name = operator_name.strip() if operator_name else ""
    r.operator_id = operator_id.strip() if operator_id else ""
    r.unique_id = unique_id.strip() if unique_id else ""
    r.block = block.strip() if block else ""
    r.address_of_govt_premises = address_of_govt_premises.strip() if address_of_govt_premises else ""
    r.status_id = StatusEnum.REAPPLIED.value

    r.reviewed_at = None
    r.reviewed_by = None

    # Save DC Reapply remark
    remark = L2RegistrationRemark(
        request_id=r.id,
        author_id=dc_id,
        author_role="dc",
        remark=reapply_remark.strip(),
        status_after_id=StatusEnum.REAPPLIED.value

    )
    db.add(remark)
    db.commit()

    return {"message": "L2 Request reapplied successfully."}

# Helper to generate Excel Workbook
# Helper to generate un-truncated CSV Streaming Responses
def make_csv_stream(requests_list, report_filename):
    import csv
    import io
    from fastapi.responses import StreamingResponse

    stream = io.StringIO()
    writer = csv.writer(stream)

    # 🌟 EXPANDED PROFILE COLUMNS MATRIX 
    headers = [
        "S.No", "Request ID","District Name", "Block", "Govt Premises Address",
        "Operator Name", "Operator ID", "Unique ID", "Client Version", "Client Type",
        "New Station ID", "New Machine ID", "EA Code", "Registrar Code",
        "Old Station ID", "Old Machine ID", "Reason for L2 Registration", 
        "Tech Center Remarks", "Status", "Submission Timestamp"
    ]
    
    # Always include 'Review Timestamp' as 'Updated At' equivalent
    headers.append("Review Timestamp")
        
    writer.writerow(headers)

    for idx, r in enumerate(requests_list, start=1):
        dist_name = r.district.district_name if r.district else "—"
        
        clean_status = str(r.status).upper().strip()
        updated_time = None
        if clean_status != "PENDING":
            updated_time = r.remarks[-1].created_at if r.remarks else r.submitted_at

        row_data = [
            idx,
            r.request_no or "",
            dist_name,
            r.block or "",
            r.address_of_govt_premises or "",
            r.operator_name,
            r.operator_id,
            r.unique_id or "",
            r.client_version,
            r.client_type,
            r.new_station_id,
            r.new_machine_id,
            r.ea_code,
            r.reg_code,
            r.old_station_id or "",
            r.old_machine_id or "",
            r.reason_for_l2_registration or "",
            r.tech_center_remarks or "",
            clean_status,
            str(r.submitted_at)[:19] if r.submitted_at else "—",
            str(updated_time)[:19] if updated_time else ""
        ]
            
        writer.writerow(row_data)

    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={report_filename}.csv"
    response.headers["Cache-Control"] = "no-cache"
    return response

@router.get("/export-excel/pending")
def export_pending_excel(ids: str = None, db: Session = Depends(get_db)):
    query = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.status_id.in_([StatusEnum.PENDING.value, StatusEnum.REAPPLIED.value, StatusEnum.SENT_TO_UIDAI.value]))

    if ids:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        if id_list:
            query = query.filter(L2RegistrationRequest.id.in_(id_list))
    reqs = query.order_by(L2RegistrationRequest.submitted_at.desc()).all()
    return make_csv_stream(reqs, "pending_l2_queue_report")

def generate_l2_uidai_csv_content(reqs: list) -> str:
    import csv
    import io

    stream = io.StringIO()
    writer = csv.writer(stream)

    headers = [
        "S.NO.",
        "Client Version",
        "New Station Id",
        "EA Code",
        "Reg Code",
        "New Machine Id",
        "Client Type",
        "Old Station ID(If Any)",
        "Reason For L2 Registration In Case of New Station Id is sent against the Old Station ID",
        "Old Machine ID",
        "Tech Center Remarks",
        "Operator name",
        "Operator Id",
        "Unique Id",
        "District",
        "Block",
        "Address of Govt premises"
    ]
    writer.writerow(headers)

    for idx, r in enumerate(reqs, start=1):
        dist_name = r.district.district_name if r.district else ""

        row_data = [
            idx,
            r.client_version or "",
            r.new_station_id or "",
            r.ea_code or "",
            r.reg_code or "",
            r.new_machine_id or "",
            r.client_type or "",
            r.old_station_id or "",
            r.reason_for_l2_registration or "",
            r.old_machine_id or "",
            r.tech_center_remarks or "",
            r.operator_name or "",
            r.operator_id or "",
            r.unique_id or "",
            dist_name,
            r.block or "",
            r.address_of_govt_premises or ""
        ]
        writer.writerow(row_data)

    return stream.getvalue()


@router.get("/export-excel/uidai")
def export_uidai_excel(ids: str = None, db: Session = Depends(get_db)):
    query = db.query(L2RegistrationRequest)

    if ids:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        if id_list:
            query = query.filter(L2RegistrationRequest.id.in_(id_list))
    else:
        query = query.filter(
            or_(
                L2RegistrationRequest.status_id == StatusEnum.SENT_TO_UIDAI.value,
                L2RegistrationRequest.is_mailed == 1
            )
        )
    reqs = query.order_by(L2RegistrationRequest.submitted_at.desc()).all()
    
    csv_content = generate_l2_uidai_csv_content(reqs)
    response = StreamingResponse(iter([csv_content]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=uidai_pipeline_l2_report.csv"
    response.headers["Cache-Control"] = "no-cache"
    return response

@router.get("/export-excel/credentials")
def export_creds_excel(ids: str = None, db: Session = Depends(get_db)):
    query = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.status_id.in_([StatusEnum.L2_DONE.value, StatusEnum.APPROVED.value, StatusEnum.REJECTED.value, StatusEnum.REVERTED.value]))

    if ids:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        if id_list:
            query = query.filter(L2RegistrationRequest.id.in_(id_list))
    reqs = query.order_by(L2RegistrationRequest.submitted_at.desc()).all()
    return make_csv_stream(reqs, "credentials_history_l2_report")


class ExportAndMailL2Request(BaseModel):
    ids: str | None = None
    email_to: str | None = None
    email_cc: str | None = None
    email_bcc: str | None = None
    subject: str | None = None
    body_html: str | None = None
    attach_csv: bool = True
    custom_files: list[dict] | None = None

@router.get("/export-and-mail/recipient")
def get_l2_export_mail_recipient():
    from backend.utils.email_utils import DEFAULT_UIDAI_RECIPIENT_EMAIL
    return {"recipient_email": DEFAULT_UIDAI_RECIPIENT_EMAIL}

@router.post("/export-and-mail")
def export_and_mail_l2_to_uidai(
    payload: ExportAndMailL2Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import asyncio
    from backend.utils.email_utils import send_uidai_export_email, DEFAULT_UIDAI_RECIPIENT_EMAIL

    target_email = (payload.email_to or DEFAULT_UIDAI_RECIPIENT_EMAIL).strip()

    query = db.query(L2RegistrationRequest)
    if payload.ids:
        id_list = [int(i.strip()) for i in payload.ids.split(",") if i.strip().isdigit()]
        if id_list:
            query = query.filter(L2RegistrationRequest.id.in_(id_list))
    else:
        query = query.filter(
            L2RegistrationRequest.status_id.in_([
                StatusEnum.PENDING.value,
                StatusEnum.REAPPLIED.value
            ]),
            or_(L2RegistrationRequest.is_mailed == 0, L2RegistrationRequest.is_mailed.is_(None))
        )
    reqs = query.order_by(L2RegistrationRequest.submitted_at.desc()).all()

    if not reqs:
        raise HTTPException(status_code=400, detail="No unmailed L2 registration requests found matching the selection.")

    csv_content = generate_l2_uidai_csv_content(reqs)

    try:
        asyncio.run(send_uidai_export_email(
            csv_content=csv_content,
            record_count=len(reqs),
            module_name="L2 Registration",
            filename="l2_registration_sent_to_uidai.csv",
            email_to=target_email,
            email_cc=payload.email_cc,
            email_bcc=payload.email_bcc,
            custom_subject=payload.subject,
            custom_body_html=payload.body_html,
            attach_csv=payload.attach_csv,
            custom_files=payload.custom_files
        ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to email CSV export: {str(e)}")

    for r in reqs:
        r.is_mailed = 1

    db.commit()

    return {
        "success": True,
        "detail": f"Export CSV ({len(reqs)} records) emailed successfully to {target_email} and moved to Under Processing queue.",
        "recipient_email": target_email,
        "count": len(reqs)
    }


