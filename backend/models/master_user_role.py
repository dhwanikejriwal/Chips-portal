from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.user_login import UserLogin

class MasterUserRole(Base):
    __tablename__ = "master_user_role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationships
    users: Mapped[list["UserLogin"]] = relationship("UserLogin", back_populates="role")

