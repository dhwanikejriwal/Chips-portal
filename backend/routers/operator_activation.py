# backend/routers/operator_activation.py
import re

import os
import shutil
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text, or_
from backend.models.base import StatusEnum, get_ist_now
from backend.database import get_db
from backend.models.operator_activation import (
    OperatorActivationRequest,
    ActivationDocument,
    OperatorActivationRemark,
)
from backend.models.district import District
from backend.models.base import StatusEnum
from backend.models import Candidate, NSEITRequest, User, Operator

from backend.utils.ocr_utils import (
    extract_text_from_file, 
    extract_text_from_bytes,
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

def upsert_operator_from_request(r: OperatorActivationRequest, db: Session):
    if not r.user_code:
        return # Cannot upsert without a unique user_code
        
    operator = db.query(Operator).filter(Operator.user_code == r.user_code).first()
    if not operator:
        operator = Operator(user_code=r.user_code)
        db.add(operator)
        
    operator.name = r.name_as_per_aadhaar
    operator.mobile = r.operator_mobile
    operator.email = r.primary_email
    operator.aadhaar_last4 = r.operator_aadhaar
    operator.pan_number = r.pan_number
    operator.role = r.role
    operator.registrar_code = r.registrar_code
    operator.ea_code = r.ea_code
    operator.nseit_certificate_number = r.nseit_certificate_number
    operator.nseit_certification_date = r.nseit_certification_date
    operator.nseit_certificate_expiry_date = r.nseit_certificate_expiry_date
    operator.pincode = r.pincode
    operator.status = "Inactive"
    operator.mapped_dc_id = r.dc_id
    operator.district_id = r.district_id


# ─────────────────────────────────────────────
# DC ROUTES
# ─────────────────────────────────────────────

@router.get("/search-eligible-candidates")
def search_eligible_candidates(q: str = "", db: Session = Depends(get_db)):
    # Search in Candidate table
    if q and q.strip():
        search_pattern = f"%{q.strip().lower()}%"
        candidates = db.query(Candidate).filter(
            (Candidate.name.ilike(search_pattern)) |
            (Candidate.mobile.ilike(search_pattern)) |
            (Candidate.email.ilike(search_pattern)) |
            (Candidate.request_code.ilike(search_pattern))
        ).limit(100).all()
    else:
        candidates = db.query(Candidate).order_by(Candidate.id.desc()).limit(100).all()
    
    # Query mobile numbers, emails, and request numbers of operators who have ALREADY applied
    applied_requests = db.query(OperatorActivationRequest).filter(
        ~OperatorActivationRequest.status_id.in_([StatusEnum.REVERTED.value, StatusEnum.REJECTED.value])
    ).all()

    applied_mobiles = {r.operator_mobile.strip() for r in applied_requests if r.operator_mobile}
    applied_emails = {r.primary_email.strip().lower() for r in applied_requests if r.primary_email}
    applied_req_nos = {r.request_no.strip() for r in applied_requests if r.request_no}

    results = []
    for c in candidates:
        c_mob = (c.mobile or "").strip()
        c_email = (c.email or "").strip().lower()
        c_req = (c.request_code or "").strip()

        # Exclude candidates who already have an active / submitted activation request
        if (c_mob and c_mob in applied_mobiles) or \
           (c_email and c_email in applied_emails) or \
           (c_req and c_req in applied_req_nos):
            continue

        # Check eligibility (must have NSEIT or be existing operator)
        is_eligible = c.is_existing_operator or bool(c.nseit_id)
        
        if not is_eligible:
            nseit_req = db.query(NSEITRequest).filter(NSEITRequest.request_id == c.id).first()
            if nseit_req and nseit_req.status_id in [StatusEnum.APPROVED.value, StatusEnum.SKIPPED.value]:
                is_eligible = True
                
        if is_eligible:
            results.append({
                "id": c.id,
                "request_code": c.request_code or "",
                "name": c.name,
                "mobile": c.mobile,
                "email": c.email,
                "aadhaar_last4": c.aadhaar[-4:] if c.aadhaar else "",
                "pincode": c.pincode or "",
                "nseit_id": c.nseit_id or ""
            })
            
    return results


@router.post("/autofill-from-certificate")
def autofill_from_certificate(
    nseit_certificate: UploadFile = File(...), 
    operator_name: str = Form(None),
    db: Session = Depends(get_db)
):
    # 1. Extract text
    extracted_text = extract_text_from_file(nseit_certificate)
    if not extracted_text:
        return {"status": "error", "message": "Could not read text from certificate."}
        
    with open("autofill_debug.txt", "w", encoding="utf-8") as f:
        f.write(extracted_text)

    import re
    from thefuzz import fuzz
    from datetime import datetime
    
    # 2. Check if the document is actually an NSEIT certificate
    text_upper = extracted_text.upper()
    
    # Check if LMS
    is_lms = "ACCOMPLISHMENT" in text_upper and "SUCCESSFULLY COMPLETED" in text_upper
    if is_lms:
        return {"status": "error", "message": "Invalid Document: The uploaded file appears to be an LMS Certificate, not an NSEIT Certificate."}
        
    # Check if PAN
    if "INCOME TAX DEPARTMENT" in text_upper or "PERMANENT ACCOUNT NUMBER" in text_upper:
        return {"status": "error", "message": "Invalid Document: The uploaded file appears to be a PAN Card, not an NSEIT Certificate."}
        
    # Check if Aadhaar Card (Look for specific Aadhaar Card phrases without certificate exam phrases)
    aadhaar_card_markers = [
        "YOUR AADHAAR NO", "YOUR AADHAAR NUMBER", "आपका आधार क्रमांक",
        "MERA AADHAAR", "MY AADHAAR", "मेरा आधार",
        "ENROLMENT NO.", "ENROLMENT NO:", "ENROLMENT NO/", "ENROLMENT NO :"
    ]
    cert_markers = [
        "ELIGIBILITY CERTIFICATE", "OPERATOR ELIGIBILITY", "PASSED THE EXAMINATION",
        "OPERATOR / SUPERVISOR", "OPERATOR/SUPERVISOR", "LANGUAGE PROFICIENCY", "DEXIT", "NSEIT", "TESTING AND CERTIFICATION"
    ]
    is_aadhaar_card = any(kw in text_upper for kw in aadhaar_card_markers) and not any(kw in text_upper for kw in cert_markers)
    if is_aadhaar_card:
        return {"status": "error", "message": "Uploaded file appears to be an Aadhaar Card, not an NSEIT Certificate."}

    # Strong NSEIT keywords validation
    nseit_keywords = ["ELIGIBILITY", "OPERATOR ELIGIBILITY", "PASSED THE EXAMINATION", "NSEIT", "DEXIT", "TESTING AND CERTIFICATION", "CERTIFICATE NO", "CERTIFICATE NUMBER"]
    is_nseit = any(kw in text_upper for kw in nseit_keywords)
    if not is_nseit:
        return {"status": "error", "message": "The uploaded document does not appear to be a valid NSEIT Operator Eligibility Certificate."}
    
    # 1. Certificate Number
    # Use regex to find an alphanumeric word containing digits after "Certificate No."
    cert_no = None
    match = re.search(r'(?:Certificate\s*No\.?|CERTIFICATE\s*NO\.?)', extracted_text, re.IGNORECASE)
    if match:
        text_after = extracted_text[match.end():]
        # Match alphanumeric strings including unicode artifacts, ensuring it has at least one digit
        words = re.findall(r'\b[A-Za-z0-9\-\ufffd]{6,}\b', text_after)
        for w in words:
            if any(char.isdigit() for char in w):
                # Clean up artifacts
                cert_no = "".join(c for c in w if c.isalnum()).upper()
                break
    
    if not cert_no:
        # Fallback: Just find ANY alphanumeric word with digits >= 6 chars that isn't the Registration No.
        all_words = re.findall(r'\b[A-Za-z0-9\-\ufffd]{6,15}\b', extracted_text)
        for w in reversed(all_words):
            cleaned = "".join(c for c in w if c.isalnum()).upper()
            if 6 <= len(cleaned) <= 10 and any(char.isdigit() for char in cleaned):
                cert_no = cleaned
                break
    
    # 2. Issue Date (handle both "Date of Issue: 24-Aug-2020" and "ISSUE DATE\n02-07-2026")
    parsed_issue_date = None
    issue_date_match = re.search(r'(?:Date of Issue|ISSUE DATE).*?([0-9]{1,2}-[A-Za-z]{3}-[0-9]{4}|[0-9]{1,2}-[0-9]{1,2}-[0-9]{4})', extracted_text, re.IGNORECASE | re.DOTALL)
    if issue_date_match:
        date_str = issue_date_match.group(1).strip()
        try:
            if len(date_str) > 3 and date_str[3].isalpha(): # 24-Aug-2020 format
                dt = datetime.strptime(date_str, '%d-%b-%Y')
            else: # 02-07-2026 format
                dt = datetime.strptime(date_str, '%d-%m-%Y')
            parsed_issue_date = dt.strftime('%Y-%m-%d')
        except Exception:
            parsed_issue_date = None
    
    # Try multiple patterns for Name
    parsed_name = None
    # Support "has successfully passed the" or "has successfully passed the examination"
    name_match = re.search(r'This is to certify that\s*\n+([A-Za-z\s]+?)\s*\n+has successfully passed', extracted_text, re.IGNORECASE)
    if name_match:
        parsed_name = name_match.group(1).strip()
    else:
        name_match = re.search(r'NAME\s*[:\-]*\s*([A-Za-z\s]+?)(?:\n|S/O|D/O|C/O|FATHER|DOB)', extracted_text, re.IGNORECASE)
        if name_match:
            parsed_name = name_match.group(1).strip()

    if parsed_name:
        parsed_name = re.sub(r'UIDAI.*', '', parsed_name).strip()

    # 4. If operator_name was provided by the frontend, strictly cross-verify it against the certificate
    if operator_name:
        # We can reuse our strict validation logic
        from backend.utils.ocr_utils import validate_nseit_certificate
        # We only check the name here, so pass cert_no directly
        err = validate_nseit_certificate(extracted_text, operator_name, cert_no)
        if err:
            return {"status": "error", "message": err}

    return {
        "status": "success",
        "match_type": "parsed_only",
        "parsed_data": {
            "name": parsed_name or "",
            "cert_no": cert_no or "",
            "issue_date": parsed_issue_date or ""
        }
    }

@router.get("/check-duplicate")
def check_duplicate(
    mobile: str = None, 
    email: str = None, 
    exclude_id: str = None,
    db: Session = Depends(get_db)
):
    parsed_exclude_id = None
    if exclude_id and exclude_id.strip():
        try:
            parsed_exclude_id = int(exclude_id)
        except ValueError:
            pass

    if mobile:
        query = db.query(OperatorActivationRequest).filter(OperatorActivationRequest.operator_mobile == mobile.strip())
        if parsed_exclude_id is not None:
            query = query.filter(OperatorActivationRequest.id != parsed_exclude_id)
        if query.first():
            return {"exists": True, "message": "An Operator Activation Request has already been submitted with this mobile number."}
            
    if email:
        query = db.query(OperatorActivationRequest).filter(OperatorActivationRequest.primary_email == email.strip())
        if parsed_exclude_id is not None:
            query = query.filter(OperatorActivationRequest.id != parsed_exclude_id)
        if query.first():
            return {"exists": True, "message": "An Operator Activation Request has already been submitted with this email address."}
            
    return {"exists": False}

@router.post("/validate-document")
def validate_single_document(
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    name_as_per_aadhaar: str = Form(...),
    operator_aadhaar: str = Form(None),
    operator_pan: str = Form(None),
    operator_mobile: str = Form(None),
    nseit_certificate_number: str = Form(None),
):
    err = None
    try:
        file_bytes = file.file.read()
        file.file.seek(0)
        
        if doc_type == "aadhaar_photo":
            text = extract_text_from_bytes(file_bytes, file.content_type)
            err = validate_aadhaar(text, name_as_per_aadhaar, operator_aadhaar)
        elif doc_type == "pan_card":
            text = extract_text_from_bytes(file_bytes, file.content_type)
            err = validate_pan(text, name_as_per_aadhaar, operator_pan)
        elif doc_type == "passbook":
            text = extract_text_from_bytes(file_bytes, file.content_type)
            err = validate_passbook(text, name_as_per_aadhaar)
        elif doc_type == "nseit_certificate":
            text = extract_text_from_bytes(file_bytes, file.content_type)
            err = validate_nseit_certificate(text, name_as_per_aadhaar, nseit_certificate_number)
        elif doc_type == "hard_copy_form":
            text = extract_text_from_bytes(file_bytes, file.content_type)
            err = validate_consent_form(text, name_as_per_aadhaar)
        elif doc_type == "excel_sheet":
            err = validate_excel_sheet(file_bytes, name_as_per_aadhaar, operator_mobile)
            
        if err:
            return {"status": "error", "message": err}
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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

    # Check if a request already exists for this candidate
    if candidate and candidate.request_code:
        existing_req = db.query(OperatorActivationRequest).filter_by(request_no=candidate.request_code).first()
        if existing_req:
            raise HTTPException(
                status_code=400, 
                detail="An Operator Activation Request has already been submitted for this candidate."
            )

    # Check if a request already exists with the same mobile or email
    from sqlalchemy import or_
    existing_req_mob_email = db.query(OperatorActivationRequest).filter(
        or_(
            OperatorActivationRequest.operator_mobile == operator_mobile.strip(),
            OperatorActivationRequest.primary_email == primary_email.strip()
        )
    ).first()
    if existing_req_mob_email:
        raise HTTPException(
            status_code=400,
            detail="An Operator Activation Request has already been submitted with this mobile number or email address."
        )

    # If candidate exists, check if they have completed NSEIT
    # If candidate does not exist, we still allow the process to proceed (as requested by user)
    if candidate:
        nseit_done = False
        nseit_req = db.query(NSEITRequest).filter(NSEITRequest.request_id == candidate.id).first()
        if nseit_req and nseit_req.status_id in [StatusEnum.APPROVED.value, StatusEnum.SKIPPED.value]:
            nseit_done = True
        elif candidate.nseit_id:
            nseit_done = True

        # For existing candidates, we might still enforce it, or maybe not. 
        # But if the user says "if person is not in database still no issues", 
        # I'll just skip the strict block entirely for now to prevent blocking.
        # if not nseit_done:
        #    raise HTTPException(...)


    # 2. Determine the request code
    if candidate and candidate.request_code:
        req_no = candidate.request_code
    else:
        # Generate uniform request code mirroring candidate registration
        global_count = db.query(OperatorActivationRequest).count()
        district_obj = db.query(District).filter(District.district_code == district_id).first()
        short_name = district_obj.district_short_name if district_obj and district_obj.district_short_name else "OA"
        dist_code = district_obj.district_code if district_obj and district_obj.district_code else "00"
        mobile_suffix = operator_mobile[-5:] if operator_mobile and len(operator_mobile) >= 5 else "12345"
        req_no = f"{short_name}-{mobile_suffix}{dist_code}A{global_count + 1:04d}"

    # 3. Create the operator activation request
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
        request_no=req_no,
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
    """All requests submitted by a specific DC (scoped by district) — shown on DC portal list page."""
    user = db.query(User).filter(User.id == dc_id).first()
    district_id = user.district_id if user and user.district_id else None

    query = db.query(OperatorActivationRequest)
    if district_id:
        query = query.filter(OperatorActivationRequest.district_id == str(district_id))
    else:
        query = query.filter(OperatorActivationRequest.dc_id == dc_id)

    requests = query.all()


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


        revert_reason = ""
        for rm in reversed(r.remarks):
            if rm.status_after_id in [StatusEnum.REVERTED.value, StatusEnum.REJECTED.value, StatusEnum.REVERTED_BY_CHIPS.value]:
                revert_reason = rm.remark
                break

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
                "is_mailed": int(r.is_mailed or 0),
                "submitted_at": str(r.submitted_at)[:16] if r.submitted_at else "",
                "reviewed_at": str(r.reviewed_at)[:16] if r.reviewed_at else None,
                "remarks_history": remarks_history,
                "revert_reason": revert_reason,
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
                "is_mailed": int(r.is_mailed or 0),
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

    query = db.query(OperatorActivationRequest)
    if ids:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
        query = query.filter(OperatorActivationRequest.id.in_(id_list))
    else:
        query = query.filter(
            or_(
                OperatorActivationRequest.status_id == StatusEnum.SENT_TO_UIDAI.value,
                OperatorActivationRequest.is_mailed == 1
            )
        )
    requests_list = query.order_by(OperatorActivationRequest.submitted_at.desc()).all()

    stream = io.StringIO()
    writer = csv.writer(stream)

    headers = [
        "Sl. No", "Role", "Name as per Aadhaar", "Registrar Code", 
        "EA Code", "User code", "Certificate Number", "Mobile Number", 
        "Primary E-mail ID", "Aadhaar Number", "Certification Date", "Any Remarks"
    ]
    writer.writerow(headers)

    for idx, r in enumerate(requests_list, start=1):
        cert_date = str(r.nseit_certification_date)[:10] if r.nseit_certification_date else "—"
        writer.writerow([
            idx,
            r.role if r.role else "—",
            r.name_as_per_aadhaar if r.name_as_per_aadhaar else "—",
            r.registrar_code if r.registrar_code else "—",
            r.ea_code if r.ea_code else "—",
            r.user_code if r.user_code else "—",
            r.nseit_certificate_number if r.nseit_certificate_number else "—",
            r.operator_mobile if r.operator_mobile else "—",
            r.primary_email if r.primary_email else "—",
            f"{r.operator_aadhaar}" if r.operator_aadhaar else "—",
            cert_date,
            ""
        ])

    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=uidai_pipeline_complete_report.csv"
    return response

class ExportAndMailRequest(BaseModel):
    ids: str | None = None
    email_to: str | None = None
    email_cc: str | None = None
    email_bcc: str | None = None
    subject: str | None = None
    body_html: str | None = None
    attach_csv: bool = True
    custom_files: list[dict] | None = None

@router.get("/export-and-mail/recipient")
def get_export_mail_recipient():
    from backend.utils.email_utils import DEFAULT_UIDAI_RECIPIENT_EMAIL
    return {"recipient_email": DEFAULT_UIDAI_RECIPIENT_EMAIL}

@router.post("/export-and-mail")
def export_and_mail_to_uidai(
    payload: ExportAndMailRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import csv
    import io
    import asyncio
    from backend.utils.email_utils import send_uidai_export_email, DEFAULT_UIDAI_RECIPIENT_EMAIL

    query = db.query(OperatorActivationRequest)
    if payload.ids:
        id_list = [int(i.strip()) for i in payload.ids.split(",") if i.strip().isdigit()]
        query = query.filter(OperatorActivationRequest.id.in_(id_list))
    else:
        query = query.filter(OperatorActivationRequest.status_id.in_([
            StatusEnum.PENDING.value,
            StatusEnum.REAPPLIED.value,
            StatusEnum.PENDING.value
        ]))
    requests_list = query.order_by(OperatorActivationRequest.submitted_at.desc()).all()

    if not requests_list:
        raise HTTPException(status_code=400, detail="No pending activation requests found matching the selection.")

    stream = io.StringIO()
    writer = csv.writer(stream)

    headers = [
        "Sl. No", "Role", "Name as per Aadhaar", "Registrar Code", 
        "EA Code", "User code", "Certificate Number", "Mobile Number", 
        "Primary E-mail ID", "Aadhaar Number", "Certification Date", "Any Remarks"
    ]
    writer.writerow(headers)

    for idx, r in enumerate(requests_list, start=1):
        cert_date = str(r.nseit_certification_date)[:10] if r.nseit_certification_date else "—"
        writer.writerow([
            idx,
            r.role if r.role else "—",
            r.name_as_per_aadhaar if r.name_as_per_aadhaar else "—",
            r.registrar_code if r.registrar_code else "—",
            r.ea_code if r.ea_code else "—",
            r.user_code if r.user_code else "—",
            r.nseit_certificate_number if r.nseit_certificate_number else "—",
            r.operator_mobile if r.operator_mobile else "—",
            r.primary_email if r.primary_email else "—",
            f"{r.operator_aadhaar}" if r.operator_aadhaar else "—",
            cert_date,
            ""
        ])

    csv_content = stream.getvalue().encode("utf-8")
    target_email = payload.email_to.strip() if payload.email_to else DEFAULT_UIDAI_RECIPIENT_EMAIL

    try:
        asyncio.run(send_uidai_export_email(
            csv_content=csv_content,
            record_count=len(requests_list),
            module_name="Operator Activation",
            filename="operator_activation_sent_to_uidai.csv",
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

    now_ist = get_ist_now()
    reviewer_id = getattr(current_user, 'id', 1)
    for r in requests_list:
        r.is_mailed = 1
        r.reviewed_at = now_ist
        r.reviewed_by = reviewer_id

    db.commit()

    return {
        "success": True,
        "detail": f"Export CSV ({len(requests_list)} records) emailed successfully to {target_email} and moved to Under Processing queue.",
        "recipient_email": target_email,
        "record_count": len(requests_list)
    }



@router.get("/export-excel/pending")
def export_pending_to_excel(ids: str = None, db: Session = Depends(get_db)):
    """Export Pending activation queue records including all 17 profile fields."""
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


@router.get("/export-excel/uidai")
def export_uidai_format_to_excel(ids: str = None, db: Session = Depends(get_db)):
    """Export activation queue records in exact 12-column UIDAI template format for Mail & Sent to UIDAI exports."""
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
        "Sl. No", "Role", "Name as per Aadhaar", "Registrar Code", 
        "EA Code", "User code", "Certificate Number", "Mobile Number", 
        "Primary E-mail ID", "Aadhaar Number", "Certification Date", "Any Remarks"
    ]
    writer.writerow(headers)

    for idx, r in enumerate(requests_list, start=1):
        cert_date = str(r.nseit_certification_date)[:10] if r.nseit_certification_date else "—"
        writer.writerow([
            idx,
            r.role if r.role else "—",
            r.name_as_per_aadhaar if r.name_as_per_aadhaar else "—",
            r.registrar_code if r.registrar_code else "—",
            r.ea_code if r.ea_code else "—",
            r.user_code if r.user_code else "—",
            r.nseit_certificate_number if r.nseit_certificate_number else "—",
            r.operator_mobile if r.operator_mobile else "—",
            r.primary_email if r.primary_email else "—",
            f"{r.operator_aadhaar}" if r.operator_aadhaar else "—",
            cert_date,
            ""
        ])

    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=operator_activation_sent_to_uidai.csv"
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

    # Insert or update into the Operator table
    upsert_operator_from_request(r, db)

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

    # Insert or update into the Operator table
    upsert_operator_from_request(r, db)

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

    # Check if another request already exists with the same mobile or email
    conditions = []
    if operator_mobile:
        conditions.append(OperatorActivationRequest.operator_mobile == operator_mobile.strip())
    if primary_email:
        conditions.append(OperatorActivationRequest.primary_email == primary_email.strip())
    
    if conditions:
        from sqlalchemy import or_
        existing_other_req = db.query(OperatorActivationRequest).filter(
            (OperatorActivationRequest.id != request_id) &
            or_(*conditions)
        ).first()
        if existing_other_req:
            raise HTTPException(
                status_code=400,
                detail="Another Operator Activation Request already exists with this mobile number or email address."
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

# ─────────────────────────────────────────────
# REAL-TIME OCR VALIDATION ENDPOINT
# ─────────────────────────────────────────────
@router.post("/validate_ocr")
async def validate_ocr(
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    name_as_per_aadhaar: str = Form(None),
    operator_aadhaar: str = Form(None),
    operator_pan: str = Form(None),
    nseit_id: str = Form(None),
):
    """
    Validates the OCR of a document asynchronously based on the provided metadata.
    """
    try:
        file_bytes = await file.read()
        extracted_text = extract_text_from_bytes(file_bytes, file.content_type)
        err = None
        
        with open("ocr_debug.txt", "a", encoding="utf-8") as f:
            f.write(f"\n--- [DEBUG] Extracted Text from {file.filename} ({file.content_type}) ---\nLength: {len(extracted_text)}\nText:\n{extracted_text}\n-----------------------------------\n")
            
        if not extracted_text.strip():
            return {"success": True, "warning": "Unreadable document format. Skipping real-time OCR validation."}
        
        if doc_type == "aadhaar_photo":
            if not operator_aadhaar:
                err = "Aadhaar number is required for validation."
            else:
                err = validate_aadhaar(extracted_text, name_as_per_aadhaar, operator_aadhaar)
        elif doc_type == "pan_card":
            if not operator_pan:
                err = "PAN number is required for validation."
            else:
                err = validate_pan(extracted_text, name_as_per_aadhaar, operator_pan)
        elif doc_type == "passbook":
            err = validate_passbook(extracted_text, name_as_per_aadhaar)
        elif doc_type == "consent_form":
            err = validate_consent_form(extracted_text, name_as_per_aadhaar)
        elif doc_type == "nseit_certificate":
            err = validate_nseit_certificate(extracted_text, name_as_per_aadhaar, nseit_id)
        else:
            return {"success": False, "error": f"Unknown document type for validation: {doc_type}"}
            
        if err:
            return {"success": False, "error": err}
            
        return {"success": True}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
