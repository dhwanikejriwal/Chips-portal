# backend/routers/l2_registration.py
import io
import openpyxl
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import L2RegistrationRequest, L2RegistrationRemark, User, District
from backend.models.base import get_ist_time

router = APIRouter()

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
        status="sent_to_chips"
    )
    db.add(new_req)
    db.commit()
    db.refresh(new_req)

    # Format Request Number L2-A0001
    new_req.request_no = f"L2-A{new_req.id:04d}"
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
        clean_status = str(r.status or "sent_to_chips").strip().lower()
        
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
            "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else None,
            "remarks_history": remarks_history
        })
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
        clean_status = str(r.status or "sent_to_chips").strip().lower()
        
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
            "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else None,
            "remarks_history": remarks_history
        })
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
    clean_status = str(r.status or "sent_to_chips").strip().lower()

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
        "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else None,
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

    if uidai_remarks and uidai_remarks.strip():
        remark = L2RegistrationRemark(
            request_id=r.id,
            author_id=reviewed_by,
            author_role="chips_admin",
            remark=f"Sent to UIDAI: {uidai_remarks.strip()}",
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
    remark_text = f"UIDAI Approved. Remarks: {uidai_remarks}" if uidai_remarks else "UIDAI Approved."
    remark = L2RegistrationRemark(
        request_id=r.id,
        author_id=reviewed_by,
        author_role="chips_admin",
        remark=remark_text,
        status_after="approved"
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
        request_id=r.id,
        author_id=reviewed_by,
        author_role="chips_admin",
        remark=f"UIDAI Rejected. Remarks: {uidai_remarks}",
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
        request_id=r.id,
        author_id=reviewed_by,
        author_role="chips_admin",
        remark=f"Reverted back to DC: {revert_reason.strip()}",
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
# Helper to generate Excel Workbook
def make_excel_sheet(requests_list, sheet_title):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title
    
    headers = [
        "S.NO.", "Client Version", "New Station Id", "EA Code", "Reg Code", "New Machine Id", "Client Type", 
        "Old Station ID(If Any)", "Reason For L2 Registration In Case of New Station Idis sent against the Old Station ID", 
        "Old Machine ID", "Tech Cenetr Remarks", "Operator name", "Operator Id", "Unique Id", "District", 
        "Block", "Address of Govt premises"
    ]
    ws.append(headers)
    for idx, r in enumerate(requests_list, start=1):
        # 🌟 UNIFORM SCHEMA FIX: Change r.district.name to r.district.district_name to prevent corruption errors
        dist_name = r.district.district_name if r.district else "—"
        
        ws.append([
            idx,
            r.client_version or "—",
            r.new_station_id or "—",
            r.ea_code or "—",
            r.reg_code or "—",
            r.new_machine_id or "—",
            r.client_type or "—",
            r.old_station_id or "—",
            r.reason_for_l2_registration or "—",
            r.old_machine_id or "—",
            r.tech_center_remarks or "—",
            r.operator_name or "—",
            r.operator_id or "—",
            r.unique_id or "—",
            dist_name,
            r.block or "—",
            r.address_of_govt_premises or "—"
        ])
    
    stream = io.BytesIO()
    wb.save(stream)
    file_bytes = stream.getvalue()
    stream.close()
    return file_bytes

@router.get("/export-excel/pending")
def export_pending_excel(ids: str = None, db: Session = Depends(get_db)):
    query = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.status.in_(["sent_to_chips", "reapplied"]))
    if ids:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        if id_list:
            query = query.filter(L2RegistrationRequest.id.in_(id_list))
    reqs = query.order_by(L2RegistrationRequest.submitted_at.desc()).all()
    file_data = make_excel_sheet(reqs, "Pending Queue")
    
    return StreamingResponse(
        io.BytesIO(file_data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=pending_l2_queue.xlsx"}
    )

@router.get("/export-excel/uidai")
def export_uidai_excel(ids: str = None, db: Session = Depends(get_db)):
    query = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.status == "sent_to_uidai")
    if ids:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        if id_list:
            query = query.filter(L2RegistrationRequest.id.in_(id_list))
    reqs = query.order_by(L2RegistrationRequest.submitted_at.desc()).all()
    file_data = make_excel_sheet(reqs, "Sent to UIDAI Queue")
    
    return StreamingResponse(
        io.BytesIO(file_data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=uidai_l2_queue.xlsx"}
    )

@router.get("/export-excel/credentials")
def export_creds_excel(ids: str = None, db: Session = Depends(get_db)):
    query = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.status.in_(["approved", "rejected", "reverted"]))
    if ids:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        if id_list:
            query = query.filter(L2RegistrationRequest.id.in_(id_list))
    reqs = query.order_by(L2RegistrationRequest.submitted_at.desc()).all()
    file_data = make_excel_sheet(reqs, "Processed Log History")
    
    return StreamingResponse(
        io.BytesIO(file_data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=processed_l2_history.xlsx"}
    )
