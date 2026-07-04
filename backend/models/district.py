from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base

class District(Base):
    __tablename__ = "district_table"

    district_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    id: Mapped[int] = mapped_column(Integer, nullable=False)
    district_name: Mapped[str] = mapped_column(String(100), nullable=False)
    district_short_name: Mapped[str] = mapped_column(String(10), nullable=False)
    
    # District Coordinator (DC) Info
    dc_name: Mapped[str] = mapped_column(String(100), nullable=True)
    dc_email: Mapped[str] = mapped_column(String(100), nullable=True)
    dc_phone: Mapped[str] = mapped_column(String(20), nullable=True)

    # Relationships
    users: Mapped[list["UserLogin"]] = relationship("UserLogin", back_populates="district")
    candidates: Mapped[list["Candidate"]] = relationship("Candidate", back_populates="district_rel")
