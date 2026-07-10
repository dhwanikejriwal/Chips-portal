from backend.models.base import StatusEnum
from datetime import datetime, timedelta
import secrets
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator , field_validator, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.database import get_db
from backend.models import District, Candidate
from backend.models.otp_verification import OtpVerification
from backend.utils.email_utils import send_otp_email


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
def get_districts(all_districts: bool = False, db: Session = Depends(get_db)):
    districts = db.query(District).order_by(District.district_name).all()
    if all_districts:
        res = []
        for d in districts:
            res_info = None
            if d.aadhaar_resources:
                res_info = {
                    "edm_name": d.aadhaar_resources.edm_name,
                    "edm_contact": d.aadhaar_resources.edm_contact,
                    "edm_email": d.aadhaar_resources.edm_email,
                    "dc_name": d.aadhaar_resources.dc_name,
                    "dc_contact": d.aadhaar_resources.dc_contact,
                    "dc_email": d.aadhaar_resources.dc_email,
                    "mto_name": d.aadhaar_resources.mto_name,
                    "mto_contact": d.aadhaar_resources.mto_contact,
                    "mto_email": d.aadhaar_resources.mto_email,
                    "adc_name": d.aadhaar_resources.adc_name,
                    "adc_contact": d.aadhaar_resources.adc_contact,
                    "adc_email": d.aadhaar_resources.adc_email,
                }
            res.append({
                "district_code": d.district_code,
                "district_name": d.district_name,
                "district_short_name": d.district_short_name,
                "aadhaar_resources": res_info
            })
        return res
    else:
        now = datetime.now()
        open_districts = []
        for d in districts:
            if not d.registration_open:
                continue
            if d.registration_start_date:
                try:
                    start_date = datetime.strptime(d.registration_start_date, "%Y-%m-%dT%H:%M")
                    if now < start_date:
                        continue
                except ValueError:
                    pass
            if d.registration_end_date:
                try:
                    end_date = datetime.strptime(d.registration_end_date, "%Y-%m-%dT%H:%M")
                    if now > end_date:
                        continue
                except ValueError:
                    pass
            is_recently_opened = False
            if d.registration_opened_at:
                try:
                    opened_dt = datetime.fromisoformat(d.registration_opened_at)
                    if now - opened_dt <= timedelta(days=7):
                        is_recently_opened = True
                except ValueError:
                    pass
            open_districts.append({
                "district_code": d.district_code,
                "district_name": d.district_name,
                "district_short_name": d.district_short_name,
                "registration_start_date": d.registration_start_date,
                "registration_end_date": d.registration_end_date,
                "is_recently_opened": is_recently_opened
            })
        return open_districts

class SendOtpRequest(BaseModel):
    email: EmailStr
    mobile: str = None

class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp_code: str

@router.post("/send-otp")
async def send_otp(payload: SendOtpRequest, db: Session = Depends(get_db)):
    email_exists = db.query(Candidate).filter(Candidate.email == payload.email).first()
    
    mobile_exists = None
    if payload.mobile:
        mobile_exists = db.query(Candidate).filter(Candidate.mobile == payload.mobile).first()
        
    if email_exists or mobile_exists:
        field_errors = {}
        if email_exists:
            field_errors["email"] = "Email is already registered"
        if mobile_exists:
            field_errors["mobile"] = "Mobile number is already registered"
        raise HTTPException(status_code=400, detail={"field_errors": field_errors})

    otp = "".join(secrets.choice("0123456789") for _ in range(6))
    expires = datetime.now() + timedelta(minutes=1)

    existing_record = db.query(OtpVerification).filter(OtpVerification.email == payload.email).first()
    if existing_record:
        existing_record.otp_code = otp
        existing_record.expires_at = expires
        existing_record.is_verified = False
    else:
        new_record = OtpVerification(
            email=payload.email,
            otp_code=otp,
            expires_at=expires,
            is_verified=False
        )
        db.add(new_record)
    
    db.commit()
    
    # Send email asynchronously
    await send_otp_email(payload.email, otp)
    
    return {"success": True, "message": "OTP sent successfully"}

@router.post("/verify-otp")
def verify_otp(payload: VerifyOtpRequest, db: Session = Depends(get_db)):
    record = db.query(OtpVerification).filter(OtpVerification.email == payload.email).first()
    
    if not record:
        raise HTTPException(status_code=400, detail="OTP request not found for this email")
    
    if record.is_verified:
        return {"success": True, "message": "Email is already verified"}
        
    if record.otp_code != payload.otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP code")
        
    if datetime.now() > record.expires_at:
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
        
    record.is_verified = True
    db.commit()
    
    return {"success": True, "message": "Email verified successfully"}

@router.post("/register-candidate")
def register_candidate(payload: CandidateRegisterRequest, db: Session = Depends(get_db)):
    # 1. Verify that the email was validated via OTP
    otp_record = db.query(OtpVerification).filter(OtpVerification.email == payload.email).first()
    if not otp_record or not otp_record.is_verified:
        raise HTTPException(status_code=400, detail="Email address has not been verified with OTP.")

    # [DUPLICATE CHECK] You can comment out this block below to allow duplicate registrations during testing
    existing_candidate = db.query(Candidate).filter(
        (Candidate.email == payload.email) | (Candidate.mobile == payload.mobile)
    ).first()
    if existing_candidate:
        if existing_candidate.email == payload.email:
            raise HTTPException(status_code=400, detail="This email address is already registered.")
        else:
            raise HTTPException(status_code=400, detail="This mobile number is already registered.")
    # [/DUPLICATE CHECK]

    district_obj = db.query(District).filter(District.district_code == payload.district).first()
    if not district_obj:
        raise HTTPException(status_code=400, detail="Invalid district code")

    # Validate that district is actively accepting registrations
    if not district_obj.registration_open:
        raise HTTPException(status_code=400, detail="Registration is currently closed for this district.")
        
    now = datetime.now()
    if district_obj.registration_start_date:
        try:
            start_date = datetime.strptime(district_obj.registration_start_date, "%Y-%m-%dT%H:%M")
            if now < start_date:
                raise HTTPException(status_code=400, detail="Registration has not started yet for this district.")
        except ValueError:
            pass
            
    if district_obj.registration_end_date:
        try:
            end_date = datetime.strptime(district_obj.registration_end_date, "%Y-%m-%dT%H:%M")
            if now > end_date:
                raise HTTPException(status_code=400, detail="Registration has ended for this district.")
        except ValueError:
            pass

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
    
    # Clean up OTP record now that registration is successful
    db.delete(otp_record)
    db.commit()
    

    return {
        "success": True,
        "request_code": request_code
    }

class TrackRequest(BaseModel):
    identifier: str

@router.post("/track")
def track_application(payload: TrackRequest, db: Session = Depends(get_db)):
    identifier = payload.identifier.strip()
    
    # Search by email or mobile
    candidate = db.query(Candidate).filter(
        (Candidate.email == identifier) | (Candidate.mobile == identifier)
    ).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="No application found with this email or mobile number.")
        
    from backend.models.dc_remark import DCRemark
    reject_reason = None
    if candidate.status_id == StatusEnum.REJECTED.value:
        latest_remark = db.query(DCRemark).filter(
            DCRemark.r_id == candidate.r_id, 
            DCRemark.status_after_id == StatusEnum.REJECTED.value
        ).order_by(desc(DCRemark.time)).first()
        if latest_remark:
            reject_reason = latest_remark.remark

    return {
        "success": True,
        "request_code": candidate.request_code,
        "email": candidate.email,
        "name": candidate.name,
        "district": candidate.district_rel.district_name if candidate.district_rel else candidate.district,
        "status": candidate.status,
        "reject_reason": reject_reason
    }

