# backend/routers/operator_activation.py
import re

import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, Form, HTTPException, File, UploadFile
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.operator_activation import (
    OperatorActivationRequest,
    ActivationDocument,
    OperatorActivationRemark,
)
from backend.models.district import District
from backend.models.base import StatusEnum
from backend.models import Candidate, NSEITRequest, User

from backend.utils.ocr_utils import (
    extract_text_from_file, 
    validate_aadhaar, 
    validate_pan,
    validate_consent_form,
    validate_passbook,
    validate_nseit_certificate,
    validate_excel_sheet
)

from backend.routers.auth import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


UPLOAD_BASE = "uploads/operator_activation"

VALID_DOC_TYPES = [
    "hard_copy_form",
    "aadhaar_photo",
    "pan_card",
    "passbook",
    "nseit_certificate",
    "excel_sheet",
]


def parse_optional_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {value}. Use YYYY-MM-DD.")


# ─────────────────────────────────────────────
# DC ROUTES
# ─────────────────────────────────────────────


@router.post("/submit")
def submit_operator_activation(
    dc_id: int = Form(...),
    district_id: str = Form(...),
    role: str = Form(None),
    name_as_per_aadhaar: str = Form(...),
    registrar_code: str = Form(None),
    ea_code: str = Form(None),
    user_code: str = Form(None),
    nseit_certificate_number: str = Form(None),
    operator_mobile: str = Form(...),
    primary_email: str = Form(None),
    operator_aadhaar: str = Form(None),
    operator_pan: str = Form(None),  # 🌟 Captures the key sent from submit_form.html
    nseit_certification_date: str = Form(None),
    nseit_certificate_expiry_date: str = Form(None),
    pincode: str = Form(None),
    hard_copy_form: UploadFile = File(...),
    aadhaar_photo: UploadFile = File(...),
    pan_card: UploadFile = File(...),
    passbook: UploadFile = File(...),
    nseit_certificate: UploadFile = File(...),
    excel_sheet: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # 🌟 FIXED: Parse HTML calendar text strings into explicit datetime primitives
    cert_date = parse_optional_date(nseit_certification_date)
    expiry_date = parse_optional_date(nseit_certificate_expiry_date)

    # 1. Enforce workflow validation rule: Candidate must be registered
    candidate = None
    if operator_mobile:
        candidate = db.query(Candidate).filter(Candidate.mobile == operator_mobile.strip()).first()
    
    if not candidate and operator_aadhaar:
        clean_aadhaar = operator_aadhaar.strip()
        if len(clean_aadhaar) == 4:
            candidate = db.query(Candidate).filter(Candidate.aadhaar.like(f"%{clean_aadhaar}")).first()
        else:
            candidate = db.query(Candidate).filter(Candidate.aadhaar == clean_aadhaar).first()

    if not candidate:
        raise HTTPException(
            status_code=400,
            detail="Candidate is not registered on the portal. The process must start with candidate registration."
        )

    # Check if candidate has completed NSEIT
    nseit_done = False
    nseit_req = db.query(NSEITRequest).filter(NSEITRequest.request_id == candidate.id).first()
    if nseit_req and nseit_req.status_id in [StatusEnum.APPROVED.value, StatusEnum.SKIPPED.value]:
        nseit_done = True
    elif candidate.nseit_id:
        nseit_done = True

    if not nseit_done:
        raise HTTPException(
            status_code=400,
            detail="Candidate has not completed the NSEIT exam. Operator activation can only be requested after NSEIT is completed."
        )


    # 2. Create the operator activation request
    new_request = OperatorActivationRequest(
        dc_id=dc_id,
        district_id=district_id,
        role=role,
        name_as_per_aadhaar=name_as_per_aadhaar,
        registrar_code=registrar_code,
        ea_code=ea_code,
        user_code=user_code,
        nseit_certificate_number=nseit_certificate_number,
        operator_mobile=operator_mobile.strip() if operator_mobile else None,
        primary_email=primary_email.strip() if primary_email else None,
        operator_aadhaar=operator_aadhaar.strip() if operator_aadhaar else None,
        pan_number=operator_pan.strip().upper() if operator_pan else None,
        nseit_certification_date=cert_date,
        nseit_certificate_expiry_date=expiry_date,
        pincode=pincode,
        status_id=StatusEnum.PENDING.value,
        request_no=candidate.request_code,
    )
    db.add(new_request)
    db.flush()

    # 3. Save each file to disk and create a document row
    uploaded_files = {
        "hard_copy_form": hard_copy_form,
        "aadhaar_photo": aadhaar_photo,
        "pan_card": pan_card,
        "passbook": passbook,
        "nseit_certificate": nseit_certificate,
        "excel_sheet": excel_sheet,
    }

    dist = db.query(District).filter(District.district_code == new_request.district_id).first()
    dist_name = dist.district_name if dist else f"DISTRICT_{new_request.district_id}"
    folder = f"{UPLOAD_BASE}/{dist_name}/{new_request.request_no}"

    os.makedirs(folder, exist_ok=True)

    for doc_type, upload in uploaded_files.items():
        ext = os.path.splitext(upload.filename)[-1]
        file_path = f"{folder}/{doc_type}{ext}"

        with open(file_path, "wb") as f:
            shutil.copyfileobj(upload.file, f)

        file_size = os.path.getsize(file_path)

        doc = ActivationDocument(
            request_id=new_request.id,
            doc_type=doc_type,
            file_path=file_path,
            original_filename=upload.filename,
            file_size_bytes=file_size,
            mime_type=upload.content_type,
        )
        db.add(doc)

    db.flush()
    initial_remark = OperatorActivationRemark(
        request_id=new_request.id,
        author_id=dc_id,
        author_role="dc",
        remark="Activation request submitted by District Coordinator.",
        status_after="pending"
    )
    db.add(initial_remark)

    db.commit()
    db.refresh(new_request)

    return {
        "status": "success",
        "message": "Operator activation request submitted successfully.",
        "request_id": new_request.id,
        "status": new_request.status,
    }


# backend/routers/operator_activation.py


@router.get("/dc/{dc_id}")
def get_dc_requests(dc_id: int, db: Session = Depends(get_db)):
    """All requests submitted by a specific DC — shown on DC portal list page."""
    requests = (
        db.query(OperatorActivationRequest)
        .filter(OperatorActivationRequest.dc_id == dc_id)
        .all()
    )


    result = []
    for r in requests:
        remarks_history = [
            {
                "author_role": rm.author_role.upper(),
                "remark": rm.remark,
                "created_at": str(rm.created_at)[:16],


            }
            for rm in r.remarks
        ]

        # 🌟 UNIFORM SCHEMA FIX: Query district name dynamically using relationship attributes
        dist_name = r.district.district_name if r.district else "—"
        # 🌟 UNIFORM SCHEMA FIX: Normalize status to lowercase for accurate template matching
        clean_status = str(r.status or "PENDING").strip().upper()


        result.append(
            {
                "id": r.id,
                "request_no": r.request_no if r.request_no else f"ACT-REQ-{r.id}",
                "operator_name": r.name_as_per_aadhaar,
                "operator_mobile": r.operator_mobile,
                "operator_aadhaar": r.operator_aadhaar,
                "operator_pan": r.pan_number,
                "primary_email": r.primary_email,
                "ea_code": r.ea_code,
                "user_code": r.user_code,

                "district_name": dist_name,
                "status": clean_status,
                "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else "",
                "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else None,
                "remarks_history": remarks_history,
            }
        )

    # Sort descending by latest action (reviewed_at if it exists, else submitted_at)
    result.sort(key=lambda x: x["reviewed_at"] or x["submitted_at"], reverse=True)

    return result

# ─────────────────────────────────────────────
# CHIPS ADMIN ROUTES
# ─────────────────────────────────────────────

@router.get("/all")
def get_all_requests(db: Session = Depends(get_db)):
    """All requests across all DCs — shown on CHIPS admin dashboard."""
    requests = (
        db.query(OperatorActivationRequest)
        .order_by(OperatorActivationRequest.submitted_at.desc())
        .all()
    )

    result = []
    for r in requests:
        dist_name = r.district.district_name if r.district else "—"
        clean_status = str(r.status or "PENDING").strip().upper()


        result.append(
            {
                "id": r.id,
                "request_no": r.request_no if r.request_no else f"ACT-REQ-{r.id}",
                "dc_id": r.dc_id,
                "district_id": r.district_id,
                "district_name": dist_name,
                "name_as_per_aadhaar": r.name_as_per_aadhaar,
                "operator_name": r.name_as_per_aadhaar,
                "operator_mobile": r.operator_mobile,
                "operator_aadhaar": r.operator_aadhaar,
                "operator_pan": r.pan_number,
                "primary_email": r.primary_email,
                "ea_code": r.ea_code,
                "user_code": r.user_code,
                "status": clean_status,
                "remark_to_uidai": r.remarks[-1].remark if r.remarks else "—",

                "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else "",
                "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else None,
                "reviewed_by": r.reviewed_by,
            }
        )

    # Sort descending by latest action (reviewed_at if it exists, else submitted_at)
    result.sort(key=lambda x: x["reviewed_at"] or x["submitted_at"], reverse=True)

    return result



@router.get("/export-excel")
def export_to_excel(ids: str = None, db: Session = Depends(get_db)):
    """🌟 FIXED: Export Sent to UIDAI pipeline records including all profile fields."""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    query = db.query(OperatorActivationRequest).filter(OperatorActivationRequest.status_id == StatusEnum.SENT_TO_UIDAI.value)
    if ids:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        query = query.filter(OperatorActivationRequest.id.in_(id_list))
    requests_list = query.order_by(OperatorActivationRequest.submitted_at.desc()).all()

    stream = io.StringIO()
    writer = csv.writer(stream)

    # 🌟 EXPANDED MASTER HEADERS MATRIX
    headers = [
        "S.No", "Request ID", "District Name", "Role", 
        "Name as per Aadhaar", "Registrar Code", "EA Code", "User Code", 
        "NSEIT Certificate Number", "Mobile Number", "Primary Email ID", 
        "Aadhaar Number", "PAN Number", "Pincode", "Status", 
        "Submitted At Timestamp", "Reviewed At Timestamp"
    ]
    writer.writerow(headers)

    for idx, r in enumerate(requests_list, start=1):
        dist_name = r.district.district_name if r.district else "—"
        writer.writerow([
            idx,
            r.request_no or "—",
            dist_name,
            r.role if r.role else "—",
            r.name_as_per_aadhaar,
            r.registrar_code if r.registrar_code else "—",
            r.ea_code if r.ea_code else "—",
            r.user_code if r.user_code else "—",
            r.nseit_certificate_number if r.nseit_certificate_number else "—",
            r.operator_mobile,
            r.primary_email if r.primary_email else "—",
            f"{r.operator_aadhaar}" if r.operator_aadhaar else "—",
            f"{r.pan_number}" if r.pan_number else "—",
            r.pincode if r.pincode else "—",
            r.status,
            str(r.submitted_at)[:19] if r.submitted_at else "—",
            str(r.reviewed_at)[:16] if r.reviewed_at else "—"
        ])

    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=uidai_pipeline_complete_report.csv"
    return response



@router.get("/export-excel/pending")
def export_pending_to_excel(ids: str = None, db: Session = Depends(get_db)):
    """🌟 FIXED: Export Pending activation queue records including all profile fields."""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    query = db.query(OperatorActivationRequest).filter(
        OperatorActivationRequest.status_id.in_([
            StatusEnum.PENDING.value,
            StatusEnum.REAPPLIED.value,
            StatusEnum.SENT_TO_UIDAI.value
        ])
    )
    if ids:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        query = query.filter(OperatorActivationRequest.id.in_(id_list))
    requests_list = query.order_by(OperatorActivationRequest.submitted_at.desc()).all()

    stream = io.StringIO()
    writer = csv.writer(stream)

    headers = [
        "S.No", "Request ID", "District Name", "Role", 
        "Name as per Aadhaar", "Registrar Code", "EA Code", "User Code", 
        "NSEIT Certificate Number", "Mobile Number", "Primary Email ID", 
        "Aadhaar Number", "PAN Number", "Pincode", "Status", 
        "Submitted At Timestamp", "Reviewed At Timestamp"
    ]
    writer.writerow(headers)

    for idx, r in enumerate(requests_list, start=1):
        dist_name = r.district.district_name if r.district else "—"
        reviewed_at_val = str(r.reviewed_at)[:19] if (r.status_id in [StatusEnum.REAPPLIED.value, StatusEnum.SENT_TO_UIDAI.value] and r.reviewed_at) else ""
        writer.writerow([
            idx,
            r.request_no or "—",
            dist_name,

            r.role if r.role else "—",
            r.name_as_per_aadhaar,
            r.registrar_code if r.registrar_code else "—",
            r.ea_code if r.ea_code else "—",
            r.user_code if r.user_code else "—",
            r.nseit_certificate_number if r.nseit_certificate_number else "—",
            r.operator_mobile,
            r.primary_email if r.primary_email else "—",
            f"{r.operator_aadhaar}" if r.operator_aadhaar else "—",
            f"{r.pan_number}" if r.pan_number else "—",
            r.pincode if r.pincode else "—",
            r.status,
            str(r.submitted_at)[:19] if r.submitted_at else "—",
            reviewed_at_val
        ])

    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=pending_activation_complete_report.csv"
    return response



@router.get("/export-excel/credentials")
def export_credentials_to_excel(ids: str = None, db: Session = Depends(get_db)):
    """🌟 FIXED: Export historical logs repository including all profile fields."""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    query = db.query(OperatorActivationRequest).filter(
        OperatorActivationRequest.status_id.in_([
            StatusEnum.APPROVED.value,
            StatusEnum.REJECTED.value,
            StatusEnum.REVERTED.value,
            StatusEnum.REVERTED_BY_CHIPS.value
        ])
    )
    if ids:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        query = query.filter(OperatorActivationRequest.id.in_(id_list))
    requests_list = query.order_by(OperatorActivationRequest.submitted_at.desc()).all()

    stream = io.StringIO()
    writer = csv.writer(stream)

    headers = [
        "S.No", "Request ID","District Name", "Role", 
        "Name as per Aadhaar", "Registrar Code", "EA Code", "User Code", 
        "NSEIT Certificate Number", "Mobile Number", "Primary Email ID", 
        "Aadhaar Number", "PAN Number", "Pincode", "Status", 
        "Submitted At Timestamp", "Reviewed At Timestamp", "Remarks"
    ]
    writer.writerow(headers)

    for idx, r in enumerate(requests_list, start=1):
        dist_name = r.district.district_name if r.district else "—"
        writer.writerow([
            idx,
            r.request_no or "—",
            dist_name,

            r.role if r.role else "—",
            r.name_as_per_aadhaar,
            r.registrar_code if r.registrar_code else "—",
            r.ea_code if r.ea_code else "—",
            r.user_code if r.user_code else "—",
            r.nseit_certificate_number if r.nseit_certificate_number else "—",
            r.operator_mobile,
            r.primary_email if r.primary_email else "—",
            f"{r.operator_aadhaar}" if r.operator_aadhaar else "—",
            f"{r.pan_number}" if r.pan_number else "—",
            r.pincode if r.pincode else "—",
            r.status,
            str(r.submitted_at)[:19] if r.submitted_at else "—",
            str(r.reviewed_at)[:19] if r.reviewed_at else "—",
            "" if r.status_id == StatusEnum.APPROVED.value else (r.remarks[-1].remark if r.remarks else "—")
        ])

    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=credentials_history_complete_report.csv"
    return response



@router.get("/{request_id}")
@router.get("/{request_id}/detail-json")
def get_request_detail(request_id: int, db: Session = Depends(get_db)):
    """Single request with all its documents — used on CHIPS detail/review page."""
    r = (
        db.query(OperatorActivationRequest)
        .filter(OperatorActivationRequest.id == request_id)
        .first()
    )

    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")

    docs = [
        {
            "doc_type": d.doc_type,
            "original_filename": d.original_filename,
            "file_path": d.file_path,
            "mime_type": d.mime_type,
            "uploaded_at": d.uploaded_at,
        }
        for d in r.documents
    ]

    remarks_history = [
        {
            "author_role": rm.author_role.upper(),
            "remark": rm.remark,
            "created_at": str(rm.created_at)[:16],
            "status_after": rm.status_after,
            "sender_username": rm.author.username if rm.author else "",

        }
        for rm in r.remarks
    ]

    dist_name = r.district.district_name if r.district else "—"
    clean_status = str(r.status or "PENDING").strip().upper()

    latest_remark = r.remarks[-1].remark if r.remarks else None

    return {
        "id": r.id,
        "request_no": r.request_no,
        "dc_id": r.dc_id,
        "district_id": r.district_id,
        "district_name": dist_name,
        "operator_name": r.name_as_per_aadhaar,
        "operator_mobile": r.operator_mobile,
        "operator_aadhaar": r.operator_aadhaar,
        "operator_pan": r.pan_number,
        "primary_email": r.primary_email,
        "role": r.role,
        "registrar_code": r.registrar_code,
        "ea_code": r.ea_code,
        "user_code": r.user_code,
        "nseit_certificate_number": r.nseit_certificate_number,
        "nseit_certification_date": str(r.nseit_certification_date)[:10] if r.nseit_certification_date else None,
        "nseit_certificate_expiry_date": str(r.nseit_certificate_expiry_date)[:10] if r.nseit_certificate_expiry_date else None,
        "pincode": r.pincode,
        "status": clean_status,
        "rejection_reason": latest_remark,
        "chips_remarks": r.remarks[-1].remark if r.remarks else "—",

        "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else None,
        "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else None,
        "reviewed_by": r.reviewed_by,
        "documents": docs,
        "remarks_history": remarks_history,
    }


@router.patch("/{request_id}/approve")
def approve_request(
    request_id: int,
    reviewed_by: int = Form(...),
    chips_remarks: str = Form(None),
    db: Session = Depends(get_db),
):
    r = (
        db.query(OperatorActivationRequest)
        .filter(OperatorActivationRequest.id == request_id)
        .first()
    )

    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")
    if r.status_id not in [StatusEnum.PENDING.value, StatusEnum.REAPPLIED.value, StatusEnum.SENT_TO_UIDAI.value]:
        raise HTTPException(status_code=400, detail=f"Cannot approve a request with status: {r.status}.")

    r.status_id = StatusEnum.APPROVED.value

    r.reviewed_by = reviewed_by
    r.chips_remarks = chips_remarks
    r.reviewed_at = datetime.utcnow() + timedelta(hours=5, minutes=30)  # IST

    remark_text = chips_remarks.strip() if chips_remarks else "Request successfully approved."
    remark = OperatorActivationRemark(
        request_id=r.id,
        author_id=reviewed_by,
        author_role="chips_admin",
        remark=remark_text,
        status_after_id=StatusEnum.APPROVED.value,
    )
    db.add(remark)

    db.commit()
    return {"message": "Operator activated successfully.", "request_id": r.id}


@router.patch("/{request_id}/reject")
def reject_request(
    request_id: int,
    reviewed_by: int = Form(...),
    rejection_reason: str = Form(None),

    chips_remarks: str = Form(None),
    db: Session = Depends(get_db),
):
    r = (
        db.query(OperatorActivationRequest)
        .filter(OperatorActivationRequest.id == request_id)
        .first()
    )

    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")
    if r.status_id not in [StatusEnum.PENDING.value, StatusEnum.SENT_TO_UIDAI.value, StatusEnum.REAPPLIED.value]:

        raise HTTPException(
            status_code=400, detail=f"Cannot revert a request with status: {r.status}"
        )

    r.status_id = StatusEnum.REVERTED.value

    r.reviewed_by = reviewed_by
    r.chips_remarks = chips_remarks
    r.reviewed_at = datetime.utcnow() + timedelta(hours=5, minutes=30)  # IST

    # Create a remark record so DC can see the rejection reason
    remark_text = rejection_reason.strip() if rejection_reason else "Request reverted to District Coordinator."

    remark = OperatorActivationRemark(
        request_id=r.id,
        author_id=reviewed_by,
        author_role="chips_admin",
        remark=remark_text,
        status_after_id=StatusEnum.REVERTED.value,

    )
    db.add(remark)
    db.commit()
    return {
        "message": "Request reverted.",
        "request_id": r.id,
        "reason": rejection_reason,
    }


@router.patch("/{request_id}/send-to-uidai")
def send_to_uidai(
    request_id: int,
    reviewed_by: int = Form(...),
    uidai_remarks: str = Form(None),
    db: Session = Depends(get_db),
):
    r = (
        db.query(OperatorActivationRequest)
        .filter(OperatorActivationRequest.id == request_id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")
    r.status_id = StatusEnum.SENT_TO_UIDAI.value
    r.reviewed_by = reviewed_by
    r.reviewed_at = datetime.utcnow() + timedelta(hours=5, minutes=30)

    remark_text = uidai_remarks.strip() if uidai_remarks else "Request forwarded to UIDAI."
    remark = OperatorActivationRemark(
        request_id=r.id,
        author_id=reviewed_by,
        author_role="chips_admin",
        remark=remark_text,  # 🌟 Requirement 4: Strip out prefix text safely
        status_after_id=StatusEnum.SENT_TO_UIDAI.value,
    )
    db.add(remark)


    db.commit()
    return {"message": "Sent to UIDAI.", "request_id": r.id}


@router.patch("/{request_id}/uidai-approve")  # 🌟 Kept as PATCH to maintain codebase uniformity

def uidai_approve(
    request_id: int,
    reviewed_by: int = Form(...),
    uidai_remarks: str = Form(None),
    db: Session = Depends(get_db),
):
    r = (
        db.query(OperatorActivationRequest)
        .filter(OperatorActivationRequest.id == request_id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")
    
    r.status_id = StatusEnum.APPROVED.value
    r.reviewed_by = reviewed_by
    r.reviewed_at = datetime.utcnow() + timedelta(hours=5, minutes=30)

    # 🌟 Insert the clean remark log into the remarks history table
    remark_text = uidai_remarks.strip() if uidai_remarks else "Request successfully approved by UIDAI."
    
    approved_remark = OperatorActivationRemark(
        request_id=r.id,
        author_id=reviewed_by,
        author_role="chips_admin",
        remark=remark_text,
        status_after_id=StatusEnum.APPROVED.value
    )
    db.add(approved_remark)
    
    db.commit()
    return {"message": "Approved by UIDAI.", "request_id": r.id}

@router.patch("/{request_id}/uidai-reject")
def uidai_reject(
    request_id: int,
    reviewed_by: int = Form(...),
    uidai_remarks: str = Form(None),

    db: Session = Depends(get_db),
):
    r = (
        db.query(OperatorActivationRequest)
        .filter(OperatorActivationRequest.id == request_id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")
    r.status_id = StatusEnum.REJECTED.value
    r.reviewed_by = reviewed_by
    r.reviewed_at = datetime.utcnow() + timedelta(hours=5, minutes=30)

    remark_text = uidai_remarks.strip() if uidai_remarks else "Request rejected by UIDAI."

    remark = OperatorActivationRemark(
        request_id=r.id,
        author_id=reviewed_by,
        author_role="chips_admin",
        remark=remark_text,  # 🌟 Requirement 4: Strip out prefix text safely
        status_after_id=StatusEnum.REJECTED.value,

    )
    db.add(remark)
    db.commit()
    return {"message": "Rejected by UIDAI.", "request_id": r.id}


@router.get("/{request_id}/detail")
def get_request_detail_full(request_id: int, db: Session = Depends(get_db)):
    # Simply points directly back to our synchronized payload schema to cut out duplicates
    return get_request_detail(request_id=request_id, db=db)

# Updated route to match the /dc/{id}/reapply URL design pattern
@router.post("/dc/{request_id}/reapply")
def reapply_request(
    request_id: int,
    dc_id: int = Form(...),
    district_id: str = Form(None),
    role: str = Form(None),
    name_as_per_aadhaar: str = Form(None),
    registrar_code: str = Form(None),
    ea_code: str = Form(None),
    user_code: str = Form(None),
    nseit_certificate_number: str = Form(None),
    operator_mobile: str = Form(None),
    primary_email: str = Form(None),
    operator_aadhaar: str = Form(None),
    operator_pan: str = Form(None),

    pincode: str = Form(None),
    nseit_certification_date: str = Form(None),
    nseit_certificate_expiry_date: str = Form(None),
    reapply_remark: str = Form(...),
    hard_copy_form: UploadFile = File(None),
    aadhaar_photo: UploadFile = File(None),
    pan_card: UploadFile = File(None),
    passbook: UploadFile = File(None),
    nseit_certificate: UploadFile = File(None),
    excel_sheet: UploadFile = File(None),

    db: Session = Depends(get_db),
):
    r = (
        db.query(OperatorActivationRequest)
        .filter(OperatorActivationRequest.id == request_id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Request not found.")

    if r.status_id not in [StatusEnum.REVERTED.value, StatusEnum.REJECTED.value, StatusEnum.REVERTED_BY_CHIPS.value]:

        raise HTTPException(
            status_code=400, detail=f"Cannot reapply a request with status: {r.status}"
        )


    if name_as_per_aadhaar:
        r.name_as_per_aadhaar = name_as_per_aadhaar

    if operator_mobile:
        r.operator_mobile = operator_mobile
    if operator_aadhaar:
        r.operator_aadhaar = operator_aadhaar
    if operator_pan:

        r.pan_number = operator_pan.upper()
    if primary_email:
        r.primary_email = primary_email
    if pincode:
        r.pincode = pincode
    if role:
        r.role = role
    if registrar_code:
        r.registrar_code = registrar_code

    if ea_code:
        r.ea_code = ea_code
    if user_code:
        r.user_code = user_code
    if nseit_certificate_number:
        r.nseit_certificate_number = nseit_certificate_number

    if nseit_certification_date:
        r.nseit_certification_date = nseit_certification_date
    if nseit_certificate_expiry_date:
        r.nseit_certificate_expiry_date = nseit_certificate_expiry_date


    cert_date = parse_optional_date(nseit_certification_date)
    expiry_date = parse_optional_date(nseit_certificate_expiry_date)
    if cert_date:
        r.nseit_certification_date = cert_date
    if expiry_date:
        r.nseit_certificate_expiry_date = expiry_date

    # Reset status
    r.status_id = StatusEnum.REAPPLIED.value
    r.reviewed_at = datetime.utcnow() + timedelta(hours=5, minutes=30)

    # Handle files
    uploaded_files = {
        "hard_copy_form": hard_copy_form,
        "aadhaar_photo": aadhaar_photo,
        "pan_card": pan_card,
        "passbook": passbook,
        "nseit_certificate": nseit_certificate,
        "excel_sheet": excel_sheet,
    }
    
    dist = db.query(District).filter(District.district_code == r.district_id).first()
    dist_name = dist.district_name if dist else f"DISTRICT_{r.district_id}"
    folder = f"{UPLOAD_BASE}/{dist_name}/{r.request_no}"
    os.makedirs(folder, exist_ok=True)

    for doc_type, upload in uploaded_files.items():
        if upload and upload.filename:
            ext = os.path.splitext(upload.filename)[-1]
            file_path = f"{folder}/{doc_type}{ext}"
            
            with open(file_path, "wb") as f:
                import shutil
                shutil.copyfileobj(upload.file, f)
            
            file_size = os.path.getsize(file_path)
            
            # Update existing or create new document record
            doc = db.query(ActivationDocument).filter_by(request_id=r.id, doc_type=doc_type).first()
            if not doc:
                doc = ActivationDocument(
                    request_id=r.id,
                    doc_type=doc_type,
                )
                db.add(doc)
            
            doc.file_path = file_path
            doc.original_filename = upload.filename
            doc.file_size_bytes = file_size
            doc.mime_type = upload.content_type

    # Save DC remark
    remark_text = reapply_remark.strip() if reapply_remark else "Request modified and reapplied."

    remark = OperatorActivationRemark(
        request_id=r.id,
        author_id=dc_id,
        author_role="dc",
        remark=remark_text,
        status_after="reapplied",

    )
    db.add(remark)
    db.commit()

    return {
        "status": "success",
        "redirect_url": "/auth/dc/operator-activation?reapplied=true"
    }



# ─────────────────────────────────────────────
# FILE SERVE ENDPOINT
# ─────────────────────────────────────────────

@router.get("/{request_id}/file/{doc_type}")
def serve_document(request_id: int, doc_type: str, db: Session = Depends(get_db)):
    """Stream a stored document file to the browser (inline view)."""
    from fastapi.responses import FileResponse

    if doc_type not in VALID_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Invalid document type.")

    doc = (
        db.query(ActivationDocument)
        .filter(
            ActivationDocument.request_id == request_id,
            ActivationDocument.doc_type == doc_type,
        )
        .first()
    )

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File missing on disk.")

    return FileResponse(
        path=doc.file_path,
        media_type=doc.mime_type or "application/octet-stream",
        filename=doc.original_filename,
        headers={"Content-Disposition": f"inline; filename=\"{doc.original_filename}\""},
    )
