# backend/routers/l2_registration.py
import re
import io
import openpyxl
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import StreamingResponse
from backend.utils.exporter import generate_excel_export
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import L2RegistrationRequest, L2RegistrationRemark, User, District
from backend.models.base import get_ist_time

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
    operator_name: str = Form(...),
    operator_id: str = Form(...),
    unique_id: str = Form(None),
    block: str = Form(...),
    address_of_govt_premises: str = Form(...),
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
        operator_name=operator_name,
        operator_id=operator_id,
        unique_id=unique_id.strip() if unique_id else "",
        block=block,
        address_of_govt_premises=address_of_govt_premises,
        status="pending"
    )
    db.add(new_req)
    db.commit()
    db.refresh(new_req)

    # Generate request_no sequentially based on the highest existing number (not id)
    # This prevents gaps caused by rolled-back transactions or deleted dev data
    last_req = db.query(L2RegistrationRequest).filter(
        L2RegistrationRequest.request_no.isnot(None),
        L2RegistrationRequest.id != new_req.id
    ).order_by(L2RegistrationRequest.id.desc()).first()

    if last_req and last_req.request_no:
        try:
            # Remove the L2-A prefix so we don't accidentally capture the '2' in 'L2'
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
        status_after="pending"  # 🌟 Direct alignment with frontend layout mapping tags
    )
    db.add(initial_remark)
    
    db.commit()
    db.refresh(new_req)

    return {"message": "L2 Registration request submitted successfully.", "request_id": new_req.id, "request_no": new_req.request_no}

@router.get("/dc/{dc_id}")
def get_dc_requests(dc_id: int, db: Session = Depends(get_db)):
    reqs = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.dc_id == dc_id).order_by(L2RegistrationRequest.submitted_at.desc()).all()
    
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
        clean_status = str(r.status or "pending").strip().lower()
        
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
            "remarks_history": remarks_history
        })

    # Sort descending by latest action
    result.sort(key=lambda x: x["updated_at"] or x["submitted_at"], reverse=True)
    return result

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
        clean_status = str(r.status or "pending").strip().lower()
        
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
    clean_status = str(r.status or "pending").strip().lower()

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

    r.status = "sent_to_uidai"
    r.reviewed_by = reviewed_by
    r.reviewed_at = get_ist_time()
    r.uidai_remarks = uidai_remarks

    remark_text = uidai_remarks.strip() if uidai_remarks and uidai_remarks.strip() else "Request forwarded to UIDAI for processing."
    remark = L2RegistrationRemark(
        request_id=r.id, author_id=reviewed_by, author_role="chips_admin",
        remark=remark_text,
        status_after="sent_to_uidai"
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

    r.status = "approved"
    r.reviewed_by = reviewed_by
    r.reviewed_at = get_ist_time()
    r.uidai_remarks = uidai_remarks

    # Add approval remark to history
    remark_text = uidai_remarks.strip() if uidai_remarks and uidai_remarks.strip() else "Request successfully approved by UIDAI."
    remark = L2RegistrationRemark(
        request_id=r.id, author_id=reviewed_by, author_role="chips_admin",
        remark=remark_text, status_after="approved"
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

    r.status = "rejected"
    r.reviewed_by = reviewed_by
    r.reviewed_at = get_ist_time()
    r.uidai_remarks = uidai_remarks

    # Add rejection remark to history
    remark = L2RegistrationRemark(
        request_id=r.id, author_id=reviewed_by, author_role="chips_admin",
        remark=uidai_remarks.strip(),  # 🌟 FIXED: Dropped manual 'UIDAI Rejected. Remarks:' prefix string layout
        status_after="rejected"
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

    r.status = "reverted"
    r.reviewed_by = reviewed_by
    r.reviewed_at = get_ist_time()

    # Log Revert Remark
    remark = L2RegistrationRemark(
        request_id=r.id, author_id=reviewed_by, author_role="chips_admin",
        remark=revert_reason.strip(),  # 🌟 FIXED: Dropped manual 'Reverted back to DC:' prefix string layout
        status_after="reverted"
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

    if r.status not in ["reverted", "rejected"]:
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
    r.operator_name = operator_name
    r.operator_id = operator_id
    r.unique_id = unique_id.strip() if unique_id else ""
    r.block = block
    r.address_of_govt_premises = address_of_govt_premises
    r.status = "reapplied"
    r.reviewed_at = None
    r.reviewed_by = None

    # Save DC Reapply remark
    remark = L2RegistrationRemark(
        request_id=r.id,
        author_id=dc_id,
        author_role="dc",
        remark=reapply_remark.strip(),
        status_after="reapplied"
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
    
    # Conditionally include 'Review Timestamp' if exporting historical/processed records
    include_review_time = any(str(r.status).lower() not in ["pending", "reapplied", "sent_to_uidai"] for r in requests_list)
    if include_review_time:
        headers.append("Review Timestamp")
        
    writer.writerow(headers)

    for idx, r in enumerate(requests_list, start=1):
        dist_name = r.district.district_name if r.district else "—"
        
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
            str(r.status).upper().strip(),
            str(r.submitted_at)[:19] if r.submitted_at else "—"
        ]
        
        if include_review_time:
            row_data.append(str(r.updated_at)[:19] if getattr(r, 'updated_at', None) else "—")
            
        writer.writerow(row_data)

    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={report_filename}.csv"
    response.headers["Cache-Control"] = "no-cache"
    return response

@router.get("/export-excel/pending")
def export_pending_excel(ids: str = None, db: Session = Depends(get_db)):
    query = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.status.in_(["pending", "reapplied", "sent_to_uidai"]))
    if ids:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        if id_list:
            query = query.filter(L2RegistrationRequest.id.in_(id_list))
    reqs = query.order_by(L2RegistrationRequest.submitted_at.desc()).all()
    return make_csv_stream(reqs, "pending_l2_queue_report")

@router.get("/export-excel/uidai")
def export_uidai_excel(ids: str = None, db: Session = Depends(get_db)):
    query = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.status == "sent_to_uidai")
    if ids:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        if id_list:
            query = query.filter(L2RegistrationRequest.id.in_(id_list))
    reqs = query.order_by(L2RegistrationRequest.submitted_at.desc()).all()
    return make_csv_stream(reqs, "uidai_pipeline_l2_report")

@router.get("/export-excel/credentials")
def export_creds_excel(ids: str = None, db: Session = Depends(get_db)):
    query = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.status.in_(["approved", "rejected", "reverted"]))
    if ids:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        if id_list:
            query = query.filter(L2RegistrationRequest.id.in_(id_list))
    reqs = query.order_by(L2RegistrationRequest.submitted_at.desc()).all()
    return make_csv_stream(reqs, "credentials_history_l2_report")