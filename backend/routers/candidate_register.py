from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator , field_validator
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import District, Candidate

router = APIRouter(prefix="/candidate_register", tags=["candidate_register"])

class CandidateRegisterRequest(BaseModel):
    name: str
    mobile: str
    email: str
    district: str
    qualification: str
    lms_id: str | None = None
    nseit_id: str | None = None
    dob: str
    aadhaar: str
    address: str | None = None
    pincode: str | None = None
    is_existing_operator: str = "false"
    photo_upload: str | None = None
    marksheet_upload: str | None = None  
    tenth_marksheet_upload: str | None = None

    @field_validator('pincode')
    @classmethod
    def validate_chhattisgarh_pincode(cls, value: str | None) -> str | None:
        if value:
            # Check length constraint and character prefix criteria
            if len(value) != 6 or not value.isdigit():
                raise ValueError("Pincode must be exactly 6 numeric digits.")
            if not value.startswith("49"):
                raise ValueError("Only applicants from Chhattisgarh state (Pincode series starting with 49) are eligible to register.")
        return value
    
    @model_validator(mode='before')
    def enforce_marksheet_routing(cls, values):
        qualification = values.get('qualification')
        marksheet = values.get('marksheet_upload')
        tenth = values.get('tenth_marksheet_upload')
        
        if qualification == 'High School (10th)':
            if marksheet and not tenth:
                values['tenth_marksheet_upload'] = marksheet
            values['marksheet_upload'] = None
        return values

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
def register_candidate(payload: CandidateRegisterRequest, db: Session = Depends(get_db)):
    district_obj = db.query(District).filter(District.district_code == payload.district).first()
    if not district_obj:
        raise HTTPException(status_code=400, detail="Invalid district code")

    count = db.query(Candidate).filter(Candidate.district == payload.district).count()
    short_name = district_obj.district_short_name or "CAN"
    request_code = f"{short_name}-A{count + 1:04d}"

    try:
        dob_parsed = datetime.strptime(payload.dob, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    new_candidate = Candidate(
        request_code=request_code,
        name=payload.name,
        mobile=payload.mobile,
        email=payload.email,
        district=payload.district,
        qualification=payload.qualification,
        lms_id=payload.lms_id,
        nseit_id=payload.nseit_id,
        dob=dob_parsed,
        aadhaar=payload.aadhaar,
        address=payload.address,
        pincode=payload.pincode,
        is_existing_operator=(payload.is_existing_operator.lower() == "true"),
        photo_upload=payload.photo_upload,
        marksheet_upload=payload.marksheet_upload,       
        tenth_marksheet_upload=payload.tenth_marksheet_upload, 
        status="Pending"
    )
    db.add(new_candidate)
    db.commit()
    
    return {
        "success": True,
        "request_code": request_code
    }
