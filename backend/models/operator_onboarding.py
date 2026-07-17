from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.models.base import Base, get_ist_time

class OperatorOnboarding(Base):
    __tablename__ = "operator_onboardings"

    id = Column(Integer, primary_key=True, index=True)
    operator_id = Column(Integer, ForeignKey("operators.id", ondelete="CASCADE"), nullable=False, index=True)
    station_id = Column(String(50), nullable=False, index=True)
    
    onboarding_status = Column(String(50), nullable=False)
    ask_kit_working_status = Column(String(50), nullable=False)
    permitted_18_plus = Column(String(50), nullable=False)
    remark = Column(Text, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=get_ist_time)

    # Relationships
    operator = relationship("Operator")
