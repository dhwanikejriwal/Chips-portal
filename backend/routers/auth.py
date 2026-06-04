from datetime import datetime, timedelta
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import User

# Security Configurations (Matches your shared .env profiles)
SECRET_KEY = "your-secret-key-here"  # In prod, fetch from os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Database session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None
    role: str | None = None

# Utility security helpers
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate security credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

# Role-Based Access Control Guardrail Decorator-class
class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = [r.lower() for r in allowed_roles]

    def __call__(self, user: User = Depends(get_current_user)):
        if hasattr(user.role, "value"):
            user_role_str = str(user.role.value).lower()
        elif hasattr(user.role, "name"):
            user_role_str = user.role.name.lower()
        else:
            user_role_str = str(user.role).split(".")[-1].lower()

        if user_role_str not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You do not possess the required role permissions."
            )
        return user

# =====================================================================
# CORE LOGIN API ROUTE
# =====================================================================
@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 1. Fetch user from PostgreSQL
    user = db.query(User).filter(User.username == form_data.username).first()
    
    # 2. Validate existence and password hash matches
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password mapping",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 3. Create token embedded with user authorization details
    if hasattr(user.role, "value"):
        role_string = str(user.role.value).lower()
    elif hasattr(user.role, "name"):
        role_string = user.role.name.lower()
    else:
        role_string = str(user.role).split(".")[-1].lower()
    
    access_token = create_access_token(
        data={"sub": user.username, "role": role_string}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    if hasattr(current_user.role, "value"):
        role_string = str(current_user.role.value).lower()
    else:
        role_string = current_user.role.name.lower()
    return {
        "username": current_user.username,
        "role": role_string,
        "district_id": current_user.district_id,
        "district_name": current_user.district_details.name if current_user.district_details else None
    }