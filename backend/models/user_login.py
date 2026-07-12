from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING
from backend.models.base import Base

from backend.models.master_user_role import MasterUserRole
from backend.models.district import District
from backend.models.dc_remark import DCRemark
from backend.models.lms import LMSRemark
from backend.models.nseit import NSEITRemark

if TYPE_CHECKING:
    from backend.models.user_profile import UserProfile

class UserLogin(Base):
    __tablename__ = "user_login_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    district_id: Mapped[str | None] = mapped_column(String(20), ForeignKey("district_table.district_code"), nullable=True)
    roleid: Mapped[int] = mapped_column(Integer, ForeignKey("master_user_role.id"), nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    role: Mapped["MasterUserRole"] = relationship("MasterUserRole", back_populates="users")
    district: Mapped["District | None"] = relationship("District", back_populates="users")
    profile: Mapped["UserProfile"] = relationship("UserProfile", back_populates="user", uselist=False)
    
    dc_remarks: Mapped[list["DCRemark"]] = relationship("DCRemark", back_populates="author")
    
    lms_remarks_written: Mapped[list["LMSRemark"]] = relationship("LMSRemark", foreign_keys="[LMSRemark.sender_id]", primaryjoin="LMSRemark.sender_id == UserLogin.id", viewonly=True)
    
    nseit_remarks_written: Mapped[list["NSEITRemark"]] = relationship("NSEITRemark", foreign_keys="[NSEITRemark.sender_id]", primaryjoin="NSEITRemark.sender_id == UserLogin.id", viewonly=True)

