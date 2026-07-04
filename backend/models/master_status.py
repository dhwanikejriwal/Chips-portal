# backend/models/master_status.py
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base

class MasterStatus(Base):
    __tablename__ = "master_status"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
