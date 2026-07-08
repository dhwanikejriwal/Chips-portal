from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.candidate import Candidate
    from backend.models.user_login import UserLogin
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.models.base import Base, get_ist_now, to_code, to_name, get_status_expression

class DCRemark(Base):
    __tablename__ = "dc_remark_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    r_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidate_table.r_id"), nullable=False)
    remark: Mapped[str] = mapped_column(String(1000), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, nullable=False)
    
    status_after_code: Mapped[str | None] = mapped_column(String(2), ForeignKey("master_status.code"), nullable=True)

    @hybrid_property
    def status_after(self) -> str | None:
        if self.status_after_code is None:
            return None
        return to_name(self.status_after_code)

    @status_after.setter
    def status_after(self, value: str | None):
        if value is None:
            self.status_after_code = None
        else:
            self.status_after_code = to_code(value)

    @status_after.expression
    def status_after(cls):
        return get_status_expression(cls.status_after_code)

    by: Mapped[int] = mapped_column(Integer, ForeignKey("user_login_table.id"), nullable=False)

    # Relationships
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="dc_remarks")
    author: Mapped["UserLogin"] = relationship("UserLogin", back_populates="dc_remarks")
