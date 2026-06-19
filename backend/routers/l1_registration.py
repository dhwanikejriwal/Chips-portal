# backend/routers/l1_registration.py
from fastapi import APIRouter, Depends, HTTPException, Form, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import pandas as pd
import io
from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.models import User, District
from backend.models.l1_registration import L1RegistrationRequest, L1RegistrationRemarkHistory

router = APIRouter()

def generate_l1_request_code(db: Session, district_id: int, district_name: str) -> str:
    name_clean = district_name.strip().lower()
    district_map = {"raipur": "RP", "bilaspur": "BP", "durg": "DG"}
    prefix = district_map.get(name_clean, "".join([c for c in name_clean if c.isalnum()])[:2].upper())
    if len(prefix) != 2: prefix = "XX"
    
    last_req = db.query(L1RegistrationRequest).filter(
        L1RegistrationRequest.district_id == district_id
    ).order_by(L1RegistrationRequest.id.desc()).first()
    
    next_num = 1
    if last_req and last_req.request_code and "-L1-" in last_req.request_code:
        try:
            next_num = int(last_req.request_code.split("-L1-")[1]) + 1
        except ValueError:
            next_num = db.query(L1RegistrationRequest).filter(
                L1RegistrationRequest.district_id == district_id
            ).count() + 1
    else:
        next_num = db.query(L1RegistrationRequest).filter(
            L1RegistrationRequest.district_id == district_id
        ).count() + 1

    return f"{prefix}-L1-{next_num:04d}"

def get_user_role_str(current_user: User) -> str:
    if hasattr(current_user.role, "role"):
        return str(current_user.role.role).lower()
    elif hasattr(current_user.role, "value"):
        return str(current_user.role.value).lower()
    elif hasattr(current_user.role, "name"):
        return str(current_user.role.name).lower()
    return str(current_user.role).split(".")[-1].lower()

@router.post("/submit", status_code=status.HTTP_201_CREATED)
async def submit_l1_registration(
    station_id: str = Form(...),
    machine_id: str = Form(...),
    model_type: str = Form(...),
    software_version: str = Form(...),
    uv_id: str = Form(...),
    uv_password: str = Form(...),
    operator_name: Optional[str] = Form(""),
    operator_id: Optional[str] = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        user_role_str = get_user_role_str(current_user)
        if user_role_str != "dc": 
            raise HTTPException(status_code=403, detail="Access Denied. Only DC can submit requests.")
        if not current_user.district_id: 
            raise HTTPException(status_code=400, detail="Missing user district layout configuration mapping.")

        district = db.query(District).filter(District.district_code == current_user.district_id).first()
        district_name = district.district_name if district else "Unknown"
        req_code = generate_l1_request_code(db, current_user.district_id, district_name)

        new_request = L1RegistrationRequest(
            request_code=req_code,
            district_id=current_user.district_id,
            station_id=station_id,
            machine_id=machine_id,
            operator_name=operator_name,
            operator_id=operator_id,
            model_type=model_type,
            software_version=software_version,
            uv_id=uv_id,
            uv_password=uv_password,
            status="PENDING"
        )
        db.add(new_request)

        # Record Initial Remark
        db.add(L1RegistrationRemarkHistory(
            request_code=req_code,
            remark="L1 Registration request initialized by District Coordinator.",
            action="SUBMITTED",
            user_role=user_role_str
        ))

        db.commit()
        return {"success": True, "request_code": req_code}
    except Exception as e:
        db.rollback()
        import traceback
        error_msg = f"FastAPI internal error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/requests")
async def get_l1_requests(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    user_role_str = get_user_role_str(current_user)
    
    base_query = """
        SELECT r.id, r.request_code, r.station_id, r.model_type, CAST(r.status AS TEXT) as raw_status, r.created_at, d.district_name as dist_name
        FROM l1_registration_requests r LEFT JOIN district_table d ON r.district_id = d.district_code
    """
    if user_role_str == "dc":
        query_exec = db.execute(text(base_query + " WHERE r.district_id = :d_id ORDER BY r.created_at DESC"), {"d_id": current_user.district_id})
    else:
        query_exec = db.execute(text(base_query + " ORDER BY r.created_at DESC"))
        
    compiled_list = []
    for row in query_exec.fetchall():
        compiled_list.append({
            "id": row.id,
            "request_code": row.request_code,
            "station_id": row.station_id,
            "model_type": row.model_type,
            "status": str(row.raw_status or "PENDING").upper().replace(" ", "_").strip(),
            "submitted_at": str(row.created_at)[:19],
            "district_name": row.dist_name or "Raipur"
        })
    return compiled_list

@router.get("/requests/{request_code}")
async def get_l1_request_details(request_code: str, db: Session = Depends(get_db)):
    req = db.query(L1RegistrationRequest).filter(L1RegistrationRequest.request_code == request_code).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Compile the remarks timeline
    remarks_data = []
    for rm in req.remarks:
        remarks_data.append({
            "action": rm.action,
            "remark": rm.remark,
            "user_role": rm.user_role,
            "timestamp": str(rm.timestamp)[:19]
        })

    # Retrieve latest revert reason if applicable for Reapply form mapping
    latest_revert = ""
    for rm in reversed(req.remarks):
        if rm.action == "REVERTED":
            latest_revert = rm.remark
            break

    return {
        "id": req.id,
        "request_code": req.request_code,
        "station_id": req.station_id,
        "machine_id": req.machine_id,
        "operator_name": req.operator_name,
        "operator_id": req.operator_id,
        "model_type": req.model_type,
        "software_version": req.software_version,
        "uv_id": req.uv_id,
        "uv_password": req.uv_password,
        "status": str(req.status).upper().replace(" ", "_").strip(),
        "revert_reason": latest_revert,
        "remarks": remarks_data,
        "created_at": str(req.created_at)[:19]
    }

@router.post("/requests/{request_code}/perform")
async def perform_l1(
    request_code: str, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    req = db.query(L1RegistrationRequest).filter(L1RegistrationRequest.request_code == request_code).first()
    if req: 
        req.status = "APPROVED"
        db.add(L1RegistrationRemarkHistory(
            request_code=request_code,
            remark="Request successfully performed and approved.",
            action="APPROVED",
            user_role=get_user_role_str(current_user)
        ))
        db.commit()
    return {"success": True}

@router.post("/requests/approve-all")
async def approve_all_l1(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    pending_requests = db.query(L1RegistrationRequest).filter(
        L1RegistrationRequest.status.in_(["PENDING", "REAPPLIED"])
    ).all()
    
    if not pending_requests:
        return {"success": True, "message": "No pending requests to approve."}
        
    for req in pending_requests:
        req.status = "REVIEWED"
        db.add(L1RegistrationRemarkHistory(
            request_code=req.request_code,
            remark="Mass approval performed by CHIPS Admin.",
            action="REVIEWED",
            user_role=get_user_role_str(current_user)
        ))
    db.commit()
    return {"success": True, "count": len(pending_requests)}

@router.post("/requests/{request_code}/revert")
async def revert_l1_request(
    request_code: str, 
    revert_reason: str = Form(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    req = db.query(L1RegistrationRequest).filter(L1RegistrationRequest.request_code == request_code).first()
    if req: 
        req.status = "REVERTED"
        db.add(L1RegistrationRemarkHistory(
            request_code=request_code,
            remark=revert_reason,
            action="REVERTED",
            user_role=get_user_role_str(current_user)
        ))
        db.commit()
    return {"success": True}

@router.put("/requests/{request_code}/reapply")
async def reapply_l1_request(
    request_code: str,
    station_id: str = Form(...),
    machine_id: str = Form(...),
    model_type: str = Form(...),
    software_version: str = Form(...),
    uv_id: str = Form(...),
    uv_password: str = Form(...),
    operator_name: Optional[str] = Form(""),
    operator_id: Optional[str] = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    req = db.query(L1RegistrationRequest).filter(L1RegistrationRequest.request_code == request_code).first()
    if req: 
        req.station_id = station_id
        req.machine_id = machine_id
        req.operator_name = operator_name
        req.operator_id = operator_id
        req.model_type = model_type
        req.software_version = software_version
        req.uv_id = uv_id
        req.uv_password = uv_password
        req.status = "REAPPLIED"

        db.add(L1RegistrationRemarkHistory(
            request_code=request_code,
            remark="Request reapplied with updated data.",
            action="REAPPLIED",
            user_role=get_user_role_str(current_user)
        ))

        db.commit()
    return {"success": True}

@router.get("/export-excel/{request_code}")
def export_l1_to_excel_stream(request_code: str, db: Session = Depends(get_db)):
    req = db.query(L1RegistrationRequest).filter(L1RegistrationRequest.request_code == request_code).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Primary Details DataFrame
    primary_data = [{
        "Request Code": req.request_code,
        "Station ID": req.station_id,
        "Machine ID": req.machine_id,
        "Operator Name": req.operator_name or "N/A",
        "Operator ID": req.operator_id or "N/A",
        "Model Type": req.model_type,
        "Software Version": req.software_version,
        "UV ID": req.uv_id,
        "Status": str(req.status).upper(),
        "Submitted At": str(req.created_at)[:19]
    }]
    df_primary = pd.DataFrame(primary_data)
    
    # Remarks History DataFrame
    remarks_data = []
    for rm in req.remarks:
        remarks_data.append({
            "Timestamp": str(rm.timestamp)[:19],
            "User Role": "DC" if rm.user_role == "dc" else "CHIPS Admin",
            "Action": rm.action,
            "Remark": rm.remark
        })
    df_remarks = pd.DataFrame(remarks_data)

    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df_primary.to_excel(writer, sheet_name='Request Details', index=False)
        df_remarks.to_excel(writer, sheet_name='Remarks History', index=False)
        
    excel_buffer.seek(0)
    return StreamingResponse(
        excel_buffer, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        headers={"Content-Disposition": f"attachment; filename=L1_Request_{request_code}.xlsx"}
    )

@router.get("/export-excel-all")
def export_all_l1_to_excel_stream(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_role_str = get_user_role_str(current_user)
    
    if user_role_str == "dc":
        requests = db.query(L1RegistrationRequest).filter(
            L1RegistrationRequest.district_id == current_user.district_id,
            L1RegistrationRequest.status.in_(["PENDING", "REAPPLIED"])
        ).order_by(L1RegistrationRequest.created_at.desc()).all()
    else:
        requests = db.query(L1RegistrationRequest).filter(
            L1RegistrationRequest.status.in_(["PENDING", "REAPPLIED"])
        ).order_by(L1RegistrationRequest.created_at.desc()).all()
        
    data = []
    for req in requests:
        data.append({
            "Request Code": req.request_code,
            "District ID": req.district_id,
            "Station ID": req.station_id,
            "Machine ID": req.machine_id,
            "Operator Name": req.operator_name or "N/A",
            "Operator ID": req.operator_id or "N/A",
            "Model Type": req.model_type,
            "Software Version": req.software_version,
            "UV ID": req.uv_id,
            "UV Password": req.uv_password,
            "Status": str(req.status).upper(),
            "Submitted At": str(req.created_at)[:19]
        })
        
    df = pd.DataFrame(data)
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Pending Requests', index=False)
        
    excel_buffer.seek(0)
    return StreamingResponse(
        excel_buffer, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        headers={"Content-Disposition": f"attachment; filename=Pending_L1_Requests.xlsx"}
    )
