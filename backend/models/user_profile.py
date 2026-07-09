from sqlalchemy import String, Integer, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.user_login import UserLogin

class UserProfile(Base):
    __tablename__ = "user_profile_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_login_table.id"), unique=True, nullable=False)
    
    full_name: Mapped[str] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(150), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    
    # We keep authorization/auth (like role and is_active) in the UserLogin table,
    # but we can link back to the user here.
    user: Mapped["UserLogin"] = relationship("UserLogin", back_populates="profile")
