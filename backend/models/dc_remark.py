from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, get_ist_now

class DCRemark(Base):
    __tablename__ = "dc_remark_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    r_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidate_table.r_id"), nullable=False)
    remark: Mapped[str] = mapped_column(String(1000), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, nullable=False)
    status_after: Mapped[str | None] = mapped_column(String(50), nullable=True)
    by: Mapped[int] = mapped_column(Integer, ForeignKey("user_login_table.id"), nullable=False)

    # Relationships
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="dc_remarks")
    author: Mapped["UserLogin"] = relationship("UserLogin", back_populates="dc_remarks")
