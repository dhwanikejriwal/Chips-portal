from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, get_ist_now, to_name, to_code
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.district import District

class HoldCandidate(Base):
    __tablename__ = "hold_candidate_tb"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    mobile: Mapped[str] = mapped_column(String(15), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(20), ForeignKey("district_table.district_code"), nullable=False)
    qualification: Mapped[str] = mapped_column(String(100), nullable=False)
    lms_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nseit_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    exam_unique_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dob: Mapped[datetime] = mapped_column(Date, nullable=False)
    aadhaar: Mapped[str] = mapped_column(String(12), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    photo_upload: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tenth_marksheet_upload: Mapped[str | None] = mapped_column(String(255), nullable=True)
    marksheet_upload: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_existing_operator: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, onupdate=get_ist_now, nullable=False)
    status_id: Mapped[int | None] = mapped_column(Integer, default=17, nullable=True)
    hold_remark: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Relationships
    district_rel: Mapped["District"] = relationship("District")
