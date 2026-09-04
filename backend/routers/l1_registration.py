# backend/routers/l1_registration.py
import re
from fastapi import APIRouter, Depends, HTTPException, Form, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import pandas as pd
import io
from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.models import User, District, StationIDRequest, L2RegistrationRequest
from backend.models.l1_registration import L1RegistrationRequest, L1RegistrationRemarkHistory
from backend.models.base import to_name, StatusEnum
from backend.utils.exporter import generate_csv_export


router = APIRouter()

def generate_l1_request_code(db: Session, district_id: int | str, station_id: str = "") -> str:
    district_obj = db.query(District).filter(District.district_code == str(district_id)).first()
    short_name = district_obj.district_short_name if district_obj and district_obj.district_short_name else "SID"

    # Find highest sequence number in this district across L1, L2, and StationID
    highest_num = 0
    for q_model, q_col in [
        (L1RegistrationRequest, L1RegistrationRequest.request_code),
        (L2RegistrationRequest, L2RegistrationRequest.request_no),
        (StationIDRequest, StationIDRequest.request_no)
    ]:
        rows = db.query(q_col).filter(q_model.district_id == str(district_id)).all()
        for r_tup in rows:
            val = r_tup[0]
            if val and '-K' in val:
                try:
                    part = val.split('-K')[1]
                    digits = re.match(r'^\d+', part)
                    if digits:
                        num = int(digits.group(0)[:4])
                        if num > highest_num:
                            highest_num = num
                except Exception:
                    pass

    clean_sid = station_id.strip() if station_id else ""
    return f"{short_name}-K{highest_num + 1:04d}{clean_sid}"

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
    laptop_serial_no: Optional[str] = Form(""),
    laptop_brand: Optional[str] = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        user_role_str = get_user_role_str(current_user)
        if user_role_str not in ["dc", "edm"]: 
            raise HTTPException(status_code=403, detail="Access Denied. Only DC/EDM can submit requests.")
        if not current_user.district_id: 
            raise HTTPException(status_code=400, detail="Missing user district layout configuration mapping.")

        # 1. Check if there is an approved StationIDRequest matching the station_id
        station_req = db.query(StationIDRequest).filter(
            StationIDRequest.station_id_inserted == station_id.strip(),
            StationIDRequest.status_id == StatusEnum.ALLOTTED.value
        ).first()

        if station_req and station_req.request_no:
            req_code = f"{station_req.request_no}{station_id.strip()}"
        else:
            # 2. Check if a prior L1 or L2 request already exists for this station_id / machine_id (repeated kit!)
            existing_l1 = db.query(L1RegistrationRequest).filter(
                L1RegistrationRequest.station_id == station_id.strip(),
                L1RegistrationRequest.request_code.isnot(None)
            ).order_by(L1RegistrationRequest.id.desc()).first()

            if not existing_l1 and machine_id:
                existing_l1 = db.query(L1RegistrationRequest).filter(
                    L1RegistrationRequest.machine_id == machine_id.strip(),
                    L1RegistrationRequest.request_code.isnot(None)
                ).order_by(L1RegistrationRequest.id.desc()).first()

            if existing_l1 and existing_l1.request_code:
                req_code = existing_l1.request_code
            else:
                existing_l2 = db.query(L2RegistrationRequest).filter(
                    (L2RegistrationRequest.new_station_id == station_id.strip()) |
                    (L2RegistrationRequest.old_station_id == station_id.strip()),
                    L2RegistrationRequest.request_no.isnot(None)
                ).order_by(L2RegistrationRequest.id.desc()).first()

                if existing_l2 and existing_l2.request_no:
                    req_code = existing_l2.request_no
                else:
                    # 3. New VLE request: Generate uniform {short_name}-K0001{station_id}
                    req_code = generate_l1_request_code(db, current_user.district_id, station_id)


        new_request = L1RegistrationRequest(
            request_code=req_code,
            district_id=current_user.district_id,
            dc_id=current_user.id,

            station_id=station_id,
            machine_id=machine_id,
            operator_name=operator_name,
            operator_id=operator_id,
            model_type=model_type,
            software_version=software_version,
            laptop_serial_no=laptop_serial_no,
            laptop_brand=laptop_brand,
            uv_id=uv_id,
            uv_password=uv_password,
            status="PENDING"
        )
        db.add(new_request)

        db.flush() # flush to get new_request.id
        
        # Record Initial Remark
        db.add(L1RegistrationRemarkHistory(
            request_id=new_request.id,
            remark="L1 Registration request initialized by District Coordinator.",
            action="SUBMITTED",
            user_role=user_role_str,
            author_id=current_user.id

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
    
    query = db.query(L1RegistrationRequest)
    if user_role_str == "dc":
        query = query.filter(L1RegistrationRequest.district_id == current_user.district_id)
    
    requests = query.order_by(L1RegistrationRequest.updated_at.desc()).all()
        
    compiled_list = []
    for req in requests:
        dist_name = req.district.district_name if req.district else "Raipur"
        revert_reason = ""
        for rm in reversed(req.remarks):
            if rm.action == "REVERTED":
                revert_reason = rm.remark
                break

        compiled_list.append({
            "id": req.id,
            "request_code": req.request_code,
            "station_id": req.station_id,
            "model_type": req.model_type,
            "status": "L1_DONE" if getattr(req, 'status_id', None) in [StatusEnum.L1_DONE.value, StatusEnum.APPROVED.value] else (to_name(req.status_id).upper().replace(" ", "_").strip() if hasattr(req, 'status_id') else "PENDING"),
            "created_at": str(req.created_at)[:19] if req.created_at else "",
            "reviewed_at": str(req.reviewed_at)[:19] if hasattr(req, 'reviewed_at') and req.reviewed_at else None,
            "submitted_at": str(req.created_at)[:19] if req.created_at else "",
            "updated_at": str(req.updated_at)[:19] if hasattr(req, 'updated_at') and req.updated_at else (str(req.created_at)[:19] if req.created_at else ""),
            "district_name": dist_name,
            "revert_reason": revert_reason
        })
    return compiled_list

@router.get("/allotted-pending")
async def get_allotted_pending_l1(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Station IDs that are ALLOTTED but have no L1 request filled yet.

    These are the requests the DC still needs to fill L1 for. Scoped to the
    DC's district; once an L1 request exists for a station it drops off this list.
    """
    user_role_str = get_user_role_str(current_user)

    q = db.query(StationIDRequest).filter(
        StationIDRequest.status_id == StatusEnum.ALLOTTED.value,
        StationIDRequest.station_id_inserted.isnot(None),
    )
    if user_role_str == "dc":
        q = q.filter(StationIDRequest.district_id == current_user.district_id)
    allotted = q.order_by(StationIDRequest.reviewed_at.desc().nullslast()).all()

    # Station IDs that already have an L1 request (any status) → exclude from this list
    existing = {
        (s.station_id or "").strip()
        for s in db.query(L1RegistrationRequest.station_id).all()
    }

    out = []
    for r in allotted:
        dist_name = r.district.district_name if r.district else ""
        for sid in str(r.station_id_inserted or "").split(","):
            sid = sid.strip()
            if not sid or sid in existing:
                continue
            out.append({
                "station_id": sid,
                # Show the station-suffixed request number (the code the L1 request
                # will actually be created with), not the bare batch code.
                "request_no": f"{r.request_no}-{sid}" if r.request_no else "—",
                "model": r.model or "—",
                "slot": r.slot or "—",
                "district_name": dist_name,
                "allotted_at": str(r.reviewed_at)[:19] if r.reviewed_at else "—",
            })
    return out


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
            "author_username": rm.author.username if rm.author else "system",

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
        "laptop_serial_no": req.laptop_serial_no,
        "laptop_brand": req.laptop_brand,
        "uv_id": req.uv_id,
        "uv_password": req.uv_password,
        "status": "L1_DONE" if getattr(req, 'status_id', None) in [StatusEnum.L1_DONE.value, StatusEnum.APPROVED.value] else (to_name(req.status_id).upper().replace(" ", "_").strip() if hasattr(req, 'status_id') else "PENDING"),
        "revert_reason": latest_revert,
        "remarks": remarks_data,
        "created_at": str(req.created_at)[:19] if req.created_at else "",
        "reviewed_at": str(req.reviewed_at)[:19] if hasattr(req, 'reviewed_at') and req.reviewed_at else None

    }

@router.post("/requests/{request_code}/perform")
async def perform_l1(
    request_code: str, 
    chips_remarks: Optional[str] = Form(None),

    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    req = db.query(L1RegistrationRequest).filter(L1RegistrationRequest.request_code == request_code).first()
    if not req:
        raise HTTPException(status_code=404, detail="L1 registration request not found")

    req.status_id = StatusEnum.L1_DONE.value
    req.reviewed_by = current_user.id

# --- FRIEND'S UPDATED CODE ---
    from backend.models.base import get_ist_now
    req.reviewed_at = get_ist_now()
# --- YOUR LOCAL CODE ---
    final_remark = chips_remarks.strip() if chips_remarks and chips_remarks.strip() else "L1 registration marked as Done by CHiPS Admin."

# ---------------------------

    db.add(L1RegistrationRemarkHistory(
        request_id=req.id,
        remark=final_remark,
        action="DONE",
        user_role=get_user_role_str(current_user),
        author_id=current_user.id

    ))
    db.commit()

    from backend.routers.kit_registration import _reconcile_kit_table
    _reconcile_kit_table(db)

    return {"success": True}

@router.post("/requests/approve-all")
async def approve_all_l1(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    pending_requests = db.query(L1RegistrationRequest).filter(
        L1RegistrationRequest.status_id.in_([StatusEnum.PENDING.value, StatusEnum.REAPPLIED.value])

    ).all()
    
    if not pending_requests:
        return {"success": True, "message": "No pending requests to approve."}
        
    for req in pending_requests:
        req.status_id = StatusEnum.L1_DONE.value
        req.reviewed_by = current_user.id
        from backend.models.base import get_ist_now
        req.reviewed_at = get_ist_now()
        db.add(L1RegistrationRemarkHistory(
            request_id=req.id,
            remark="L1 registration marked as Done (bulk) by CHIPS Admin.",
            action="DONE",
            user_role=get_user_role_str(current_user),
            author_id=current_user.id

        ))
    db.commit()

    from backend.routers.kit_registration import _reconcile_kit_table
    _reconcile_kit_table(db)

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
        req.status_id = StatusEnum.REVERTED.value
        req.reviewed_by = current_user.id
        from backend.models.base import get_ist_now
        req.reviewed_at = get_ist_now()
        db.add(L1RegistrationRemarkHistory(
            request_id=req.id,
            remark=revert_reason,
            action="REVERTED",
            user_role=get_user_role_str(current_user),
            author_id=current_user.id

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
    reapply_remark: str = Form(...),

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
        req.status_id = StatusEnum.REAPPLIED.value

        db.add(L1RegistrationRemarkHistory(
            request_id=req.id,
            remark=reapply_remark.strip(),  # 🌟 FIXED: Strictly binds the DC custom notes
            action="REAPPLIED",
            user_role=get_user_role_str(current_user),
            author_id=current_user.id

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




@router.get("/export-excel-v2")
def export_l1_excel_v2(ids: str = None, db: Session = Depends(get_db)):
    """
    🌟 FIXED: Expanded to extract comprehensive profile parameters from the database context
    and stream them as an un-truncated clean CSV report via the central exporter utility.
    """
    query = db.query(L1RegistrationRequest)
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.isdigit()]
        query = query.filter(L1RegistrationRequest.id.in_(id_list))
        
    records = query.order_by(L1RegistrationRequest.created_at.desc()).all()

    export_data = []
    for idx, req in enumerate(records):
        dist_name = req.district.district_name if req.district else "Unknown"
        export_data.append({
            "s_no": idx + 1,

            "request_code": req.request_code,
            "district_name": dist_name,
   
            "station_id": req.station_id or "N/A",
            "machine_id": req.machine_id or "N/A",
            "operator_name": req.operator_name or "N/A",
            "operator_id": req.operator_id or "N/A",
            "model_type": str(req.model_type).upper() if req.model_type else "N/A",
            "software_version": req.software_version or "N/A",
            "uv_id": req.uv_id or "None Allocated",
            "uv_password": req.uv_password or "None Allocated",
            "status": str(req.status).upper(),
            "submitted_at": req.created_at.strftime("%Y-%m-%d %H:%M:%S") if getattr(req, 'created_at', None) else "",
            "reviewed_at": req.updated_at.strftime("%Y-%m-%d %H:%M:%S") if (str(req.status).upper() not in ["PENDING"] and getattr(req, 'updated_at', None)) else ""
        })

    column_mappings = {
        "s_no": "S.No",
      
        "request_code": "Request Reference Number",
        "district_name": "District Name",

        "station_id": "Station ID",
        "machine_id": "Registered Machine ID",
        "operator_name": "Operator Name",
        "operator_id": "Operator Unique ID Code",
        "model_type": " Model Category",
        "software_version": " Software Version",
        "uv_id": "UV ID Credentials",
        "uv_password": "UV Security Password",
        "status": "Status",
        "submitted_at": "Submission Timestamp",
        "reviewed_at": "Review Timestamp"
    }

    return generate_csv_export(export_data, column_mappings, "l1_registration_complete_report")

