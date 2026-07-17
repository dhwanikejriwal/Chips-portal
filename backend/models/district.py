from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.candidate import Candidate
    from backend.models.user_login import UserLogin

class District(Base):
    __tablename__ = "district_table"

    district_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    id: Mapped[int] = mapped_column(Integer, nullable=False)
    district_name: Mapped[str] = mapped_column(String(100), nullable=False)
    district_short_name: Mapped[str] = mapped_column(String(10), nullable=False)
    
    # Registration Settings
    registration_open: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    registration_start_date: Mapped[str] = mapped_column(String(50), nullable=True)
    registration_end_date: Mapped[str] = mapped_column(String(50), nullable=True)
    registration_opened_at: Mapped[str] = mapped_column(String(50), nullable=True)

    # Relationships
    users: Mapped[list["UserLogin"]] = relationship("UserLogin", back_populates="district")
    candidates: Mapped[list["Candidate"]] = relationship("Candidate", back_populates="district_rel")
    
