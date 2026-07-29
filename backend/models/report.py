from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from backend.models.base import Base, get_ist_time

class ReportHistory(Base):
    __tablename__ = "report_history"

    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String(100), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=True)
    file_path = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=get_ist_time)
