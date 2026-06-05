# backend/models/station.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.models.base import Base, get_ist_time

class StationKitDetails(Base):
    __tablename__ = "station_kit_details"
    
    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    station_id = Column(String, unique=True, nullable=True)
    kit_number = Column(String, unique=True, nullable=True)
    status = Column(String, default="STATION_ID_PENDING")  # STATION_ID_PENDING, L1_PENDING, L2_APPROVED
    created_at = Column(DateTime, default=get_ist_time)
    
    district = relationship("District")
