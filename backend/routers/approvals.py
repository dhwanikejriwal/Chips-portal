# backend/routers/approvals.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.approvals import ApprovalHistory

router = APIRouter()

@router.get("/history")
def get_approval_history(db: Session = Depends(get_db)):
    return db.query(ApprovalHistory).all()
