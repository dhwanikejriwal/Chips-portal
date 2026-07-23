from sqlalchemy import Column, Integer, String, Text, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from backend.models.base import Base, get_ist_time

class OperatorOnboardingDetail(Base):
    __tablename__ = "operator_onboarding_details"

    id = Column(Integer, primary_key=True, index=True)
    mapping_id = Column(Integer, ForeignKey("operator_station_mappings.id", ondelete="CASCADE"), nullable=False, index=True)
    operator_id = Column(Integer, ForeignKey("operators.id", ondelete="CASCADE"), nullable=False, index=True)
    station_id = Column(String(50), nullable=False, index=True)
    
    onboarding_status = Column(String(50), nullable=False)
    onboard_date = Column(Date, nullable=True)
    ask_kit_working_status = Column(String(50), nullable=False)
    permitted_18_plus = Column(String(50), nullable=False)
    visit_status = Column(String(50), nullable=True)
    visit_date = Column(Date, nullable=True)
    remark = Column(Text, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=get_ist_time)

    # Relationships
    mapping = relationship("OperatorStationMapping")
    operator = relationship("Operator")
