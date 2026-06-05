# backend/models/approvals.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.models.base import Base, get_ist_time

class ApprovalHistory(Base):
    __tablename__ = "approval_history"
    
    id = Column(Integer, primary_key=True, index=True)
    request_type = Column(String, nullable=False)  # e.g., LMS, NOC, ACTIVATION, STATION
    request_id = Column(Integer, nullable=False)
    action_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_taken = Column(String, nullable=False)  # e.g., APPROVED, REJECTED, ESCALATED
    comments = Column(String, nullable=True)
    action_at = Column(DateTime, default=get_ist_time)
    
    action_by_user = relationship("User")
