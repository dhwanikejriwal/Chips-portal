import os
from datetime import datetime, timedelta
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from backend.database import get_db
from backend.models import UserLogin, CandidateLogin

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "your_super_secret_key_change_me_in_production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

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
            "r_id": candidate_login.r_id
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

        access_token = create_access_token(data=token_data)
        district_name = user.district.district_name if user.district else ""

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
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
