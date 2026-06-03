from datetime import datetime
import enum
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# 1. Systemic Roles for the Portal Users
class UserRole(enum.Enum):
    DC = "dc"
    CHIPS_ADMIN = "chips_admin"

# 2. Workflow states for the Operator Credentials Request
class RequestStatus(enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"

class District(db.Model):
    __tablename__ = "districts"
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    # Relationships to let teammates easily look up associated tables
    users = db.relationship("User", backref="district_details", lazy=True)
    requests = db.relationship("CredentialRequest", backref="district_details", lazy=True)

class User(db.Model):
    __tablename__ = "users"
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.DC)
    
    # Link a DC to their designated district (Will be NULL for CHIPS admin)
    district_id = db.Column(db.Integer, db.ForeignKey("districts.id"), nullable=True)

class CredentialRequest(db.Model):
    __tablename__ = "credential_requests"
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Operator Information parameters filled out by the State DC
    operator_first_name = db.Column(db.String(100), nullable=False)
    operator_middle_name = db.Column(db.String(100), nullable=True)
    operator_last_name = db.Column(db.String(100), nullable=False)
    operator_phone = db.Column(db.String(15), nullable=False)
    operator_email = db.Column(db.String(150), nullable=False)
    
    # Tracking references
    district_id = db.Column(db.Integer, db.ForeignKey("districts.id"), nullable=False)
    submitted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    
    # Indexed states for fast Daily/Weekly dashboard aggregation filters
    status = db.Column(db.Enum(RequestStatus), default=RequestStatus.PENDING, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Credentials generated and provided exclusively by CHIPS admin
    generated_login_id = db.Column(db.String(100), unique=True, nullable=True)
    generated_password_raw = db.Column(db.String(100), nullable=True)