from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.district import District


class StationIDMaster(Base):
    __tablename__ = "station_id_master"

    district_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("district_table.district_code"), primary_key=True
    )
    district_name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_station_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationship
    district: Mapped["District"] = relationship("District", back_populates="station_id_master")
