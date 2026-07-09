from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base

class AadhaarDistrictResource(Base):
    __tablename__ = "aadhaar_district_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    district_code: Mapped[str] = mapped_column(String(20), ForeignKey("district_table.district_code"), nullable=False, unique=True)

    # E-DM
    edm_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    edm_contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    edm_email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # District Coordinator
    dc_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dc_contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dc_email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # MTO
    mto_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mto_contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mto_email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Assistant Division Coordinator
    adc_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    adc_contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    adc_email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Relationship
    district: Mapped["District"] = relationship("District", back_populates="aadhaar_resources")
