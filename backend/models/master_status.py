# backend/models/master_status.py
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base

class MasterStatus(Base):
    __tablename__ = "master_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
