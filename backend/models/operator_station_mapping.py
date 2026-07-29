from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.models.base import Base, get_ist_time

class OperatorStationMapping(Base):
    __tablename__ = "operator_station_mappings"

    id = Column(Integer, primary_key=True, index=True)
    operator_id = Column(Integer, ForeignKey("operators.id", ondelete="CASCADE"), nullable=False, index=True)
    station_id = Column(String(50), nullable=False, index=True)
    
    mapped_at = Column(DateTime, nullable=False, default=get_ist_time)

    # Relationships
    operator = relationship("Operator")
