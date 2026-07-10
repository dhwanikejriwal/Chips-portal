import os
from datetime import datetime, timedelta
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status, Security, BackgroundTasks

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from backend.database import get_db
from backend.models import UserLogin, CandidateLogin
from backend.utils.email_utils import send_password_reset_email


router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "your_super_secret_key_change_me_in_production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "360"))


class LoginRequest(BaseModel):
    username: str
    password: str

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserLogin).filter(UserLogin.username == payload.username).first()
    is_candidate = False
    candidate_login = None
    if not user:
        candidate_login = db.query(CandidateLogin).filter(CandidateLogin.user_id == payload.username).first()
        if not candidate_login:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )
        is_candidate = True

    password_bytes = payload.password.encode('utf-8')
    if is_candidate:
        db_password_bytes = candidate_login.password.encode('utf-8')
        if not bcrypt.checkpw(password_bytes, db_password_bytes):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )
        candidate = candidate_login.candidate
        token_data = {
            "user_id": candidate_login.id,
            "username": candidate_login.user_id,
            "role": "Candidate",
            "district_id": candidate.district if candidate else None
        }
        access_token = create_access_token(data=token_data)
        district_name = candidate.district_rel.district_name if (candidate and candidate.district_rel) else ""
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": "Candidate",
            "district_id": candidate.district if candidate else None,
            "district_name": district_name,
            "user_id": candidate_login.id,
            "r_id": candidate_login.r_id,
            "has_changed_password": candidate_login.has_changed_password

        }
    else:
        db_password_bytes = user.password.encode('utf-8')
        if not bcrypt.checkpw(password_bytes, db_password_bytes):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )

        token_data = {
            "user_id": user.id,
            "username": user.username,
            "role": user.role.role,
            "district_id": user.district_id
        }

        district_name = user.district.district_name if user.district else ""

        # Track login if role is Admin (chips_admin) or DC/EDM (dc_admin)
        admin_type = None
        if user.role.role == "Admin":
            admin_type = "chips_admin"
        elif user.role.role in ["DC", "EDM"]:
            admin_type = "dc_admin"

        if admin_type:
            from backend.models import AdminLoginLog
            from backend.models.base import get_ist_now

            # Sessions are independent per device/browser — a new login must NOT
            # touch any other still-active session row for this admin.
            started_at = get_ist_now()

            # baseline_at = the previous session's login_time for THIS SAME USER
            # (across any device). No prior session -> baseline is this session's
            # own start, so a first-ever login shows zero new requests. This stays
            # fixed for the session's lifetime, but the notifications endpoint
            # queries against it live (see backend/routers/notifications.py) so
            # requests that arrive during the session still show up.
            prev_session = (
                db.query(AdminLoginLog)
                .filter(
                    AdminLoginLog.admin_id == user.id,
                    AdminLoginLog.admin_type == admin_type,
                )
                .order_by(AdminLoginLog.login_time.desc())
                .first()
            )
            baseline_at = prev_session.login_time if prev_session else started_at

            new_log = AdminLoginLog(
                admin_id=user.id,
                admin_type=admin_type,
                login_time=started_at,
                baseline_at=baseline_at,
                is_current=True,
            )
            db.add(new_log)
            db.commit()
            db.refresh(new_log)
            token_data["session_id"] = new_log.id

        access_token = create_access_token(data=token_data)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": user.role.role,
            "district_id": user.district_id,
            "district_name": district_name,
            "user_id": user.id
        }

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> UserLogin:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("username")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(UserLogin).filter(UserLogin.username == username).first()
    if user:
        return user
        
    candidate = db.query(CandidateLogin).filter(CandidateLogin.user_id == username).first()
    if candidate:
        return candidate
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="User not found",
        headers={"WWW-Authenticate": "Bearer"},
    )

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check if current_user is CandidateLogin or UserLogin
    if isinstance(current_user, CandidateLogin):
        db_password_bytes = current_user.password.encode('utf-8')
    else:
        db_password_bytes = current_user.password.encode('utf-8')

    if not bcrypt.checkpw(payload.current_password.encode('utf-8'), db_password_bytes):
        raise HTTPException(status_code=400, detail="Incorrect current password.")

    salt = bcrypt.gensalt()
    hashed_pw = bcrypt.hashpw(payload.new_password.encode('utf-8'), salt).decode('utf-8')

    current_user.password = hashed_pw
    if isinstance(current_user, CandidateLogin):
        current_user.has_changed_password = True

    db.commit()
    return {"success": True, "detail": "Password updated successfully."}

class ForgotPasswordRequest(BaseModel):
    username: str

class ResetPasswordRequest(BaseModel):
    username: str
    otp: str
    new_password: str

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(UserLogin).filter(UserLogin.username == payload.username).first()
    candidate = None
    email_to = None
    name = "User"
    
    if user:
        email_to = payload.username # Assuming username is email
        name = user.username
        canonical_username = user.username
    else:
        # Search by request code
        candidate_login = db.query(CandidateLogin).filter(CandidateLogin.user_id == payload.username).first()
        # If not found by request code, search by email
        if not candidate_login:
            from backend.models.candidate import Candidate
            cand = db.query(Candidate).filter(Candidate.email == payload.username).first()
            if cand and cand.login:
                candidate_login = cand.login
                
        if candidate_login:
            # We must use the candidate's actual email, not their request code!
            if candidate_login.candidate:
                email_to = candidate_login.candidate.email
                name = candidate_login.candidate.name
            else:
                email_to = candidate_login.user_id
            # Set canonical username for the JWT token so reset logic finds them
            canonical_username = candidate_login.user_id
        else:
            # Do not leak information, just say success
            return {"success": True, "detail": "If an account exists, a reset link was sent."}
    
    # Generate 6-digit OTP
    import secrets
    from backend.models.otp_verification import OtpVerification
    from backend.utils.email_utils import send_password_reset_otp_email
    
    otp_code = "".join([str(secrets.randbelow(10)) for _ in range(6)])
    expire = datetime.utcnow() + timedelta(minutes=15)
    
    # Store OTP using canonical_username as the key
    db_otp = db.query(OtpVerification).filter(OtpVerification.email == canonical_username).first()
    if db_otp:
        db_otp.otp_code = otp_code
        db_otp.expires_at = expire
        db_otp.is_verified = False
    else:
        new_otp = OtpVerification(email=canonical_username, otp_code=otp_code, expires_at=expire)
        db.add(new_otp)
    db.commit()
    
    background_tasks.add_task(
        send_password_reset_otp_email,
        email_to=email_to,
        name=name,
        otp_code=otp_code
    )
    
    # Return canonical_username so the frontend knows what to send to reset-password
    return {"success": True, "detail": "An OTP has been sent to your email address.", "canonical_username": canonical_username}

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    from backend.models.otp_verification import OtpVerification
    db_otp = db.query(OtpVerification).filter(OtpVerification.email == payload.username).first()
    
    if not db_otp or db_otp.otp_code != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP.")
    if db_otp.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP has expired.")
        
    salt = bcrypt.gensalt()
    hashed_pw = bcrypt.hashpw(payload.new_password.encode('utf-8'), salt).decode('utf-8')
    
    user = db.query(UserLogin).filter(UserLogin.username == payload.username).first()
    if user:
        user.password = hashed_pw
        db.delete(db_otp)
        db.commit()
        return {"success": True, "detail": "Password reset successfully."}
        
    candidate = db.query(CandidateLogin).filter(CandidateLogin.user_id == payload.username).first()
    if candidate:
        candidate.password = hashed_pw
        db.delete(db_otp)
        db.commit()
        return {"success": True, "detail": "Password reset successfully."}
        
    raise HTTPException(status_code=404, detail="User not found")

def get_current_session(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
):
    """Resolve the AdminLoginLog row this token's session was issued for.

    Each device/browser login gets its own row (and its own baseline_at/
    new_request_count), so this must be looked up by the session_id embedded
    in the token rather than "the current session for this user" — otherwise
    concurrent logins on multiple devices would clobber each other's state.
    Returns None for tokens with no session (e.g. Candidate logins).
    """
    from backend.models import AdminLoginLog

    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session_id = payload.get("session_id")
    if session_id is None:
        return None
    session = db.query(AdminLoginLog).filter(AdminLoginLog.id == session_id).first()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session

@router.post("/logout")
def logout(
    current_user: UserLogin = Depends(get_current_user),
    current_session=Depends(get_current_session),
    db: Session = Depends(get_db)
):
    if current_session is not None:
        from backend.models.base import get_ist_now
        # Only this device/browser's session ends here — other active
        # sessions for the same user must be left untouched.
        current_session.logout_time = get_ist_now()
        current_session.is_current = False
        db.commit()

    return {"message": "Logged out successfully"}

