from datetime import datetime
import re
import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from pydantic import BaseModel, model_validator , field_validator
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import District, Candidate

router = APIRouter(prefix="/candidate_register", tags=["candidate_register"])

UPLOAD_BASE = "app/static/uploads"

@router.get("/districts")
def get_districts(db: Session = Depends(get_db)):
    districts = db.query(District).order_by(District.district_name).all()
    return [
        {
            "district_code": d.district_code,
            "district_name": d.district_name,
            "district_short_name": d.district_short_name
        } for d in districts
    ]

@router.post("/register-candidate")
def register_candidate(
    name: str = Form(...),
    mobile: str = Form(...),
    email: str = Form(...),
    district: str = Form(...),
    qualification: str = Form(...),
    lms_id: str = Form(None),
    nseit_id: str = Form(None),
    dob: str = Form(...),
    aadhaar: str = Form(...),
    address: str = Form(None),
    pincode: str = Form(None),
    is_existing_operator: str = Form("false"),
    photo: UploadFile = File(None),
    marksheet: UploadFile = File(None),
    tenth_marksheet: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    district_obj = db.query(District).filter(District.district_code == district).first()
    if not district_obj:
        raise HTTPException(status_code=400, detail="Invalid district code")

    if pincode:
        if len(pincode) != 6 or not pincode.isdigit():
            raise HTTPException(status_code=400, detail="Pincode must be exactly 6 numeric digits.")
        if not pincode.startswith("49"):
            raise HTTPException(status_code=400, detail="Only applicants from Chhattisgarh state (Pincode series starting with 49) are eligible to register.")

    # Generate request_code sequentially based on the highest existing number (not count)
    # Using count() is dangerous: deletions reduce count and can cause duplicate request_codes.
    last_candidate = db.query(Candidate).filter(
        Candidate.district == district,
        Candidate.request_code.isnot(None)
    ).order_by(Candidate.id.desc()).first()

    if last_candidate and last_candidate.request_code:
        try:
            last_num = int(re.sub(r'[^\d]', '', last_candidate.request_code.split('-A')[-1]))
        except (ValueError, TypeError, IndexError):
            last_num = 0
    else:
        last_num = 0
    short_name = district_obj.district_short_name or "CAN"
    request_code = f"{short_name}-A{last_num + 1:04d}"

    try:
        dob_parsed = datetime.strptime(dob, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Helper function to save file
    def save_upload(file_obj: UploadFile):
        if not file_obj or not file_obj.filename:
            return None
        # Target directory: candidate_upload/<request_code>/
        target_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "candidate_upload", request_code)
        os.makedirs(target_dir, exist_ok=True)
        filename = file_obj.filename.replace(" ", "_")
        filepath = os.path.join(target_dir, filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file_obj.file, buffer)
        return f"/candidate_upload/{request_code}/{filename}"

    photo_path = save_upload(photo)
    marksheet_path = save_upload(marksheet)
    tenth_marksheet_path = save_upload(tenth_marksheet)
    
    if qualification == "High School (10th)":
        if marksheet_path and not tenth_marksheet_path:
            tenth_marksheet_path = marksheet_path
        marksheet_path = None

    new_candidate = Candidate(
        request_code=request_code,
        name=name,
        mobile=mobile,
        email=email,
        district=district,
        qualification=qualification,
        lms_id=lms_id,
        nseit_id=nseit_id,
        dob=dob_parsed,
        aadhaar=aadhaar,
        address=address,
        pincode=pincode,
        is_existing_operator=(is_existing_operator.lower() == "true"),
        photo_upload=photo_path,
        marksheet_upload=marksheet_path,       
        tenth_marksheet_upload=tenth_marksheet_path, 
        status="Pending"
    )
    db.add(new_candidate)
    db.commit()
    
    return {
        "success": True,
        "request_code": request_code
    }

@router.get("/status/{request_code}")
def get_candidate_status(request_code: str, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.request_code == request_code).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"status": candidate.status}
