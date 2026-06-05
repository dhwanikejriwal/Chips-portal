# backend/routers/dc_requests.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.dc_requests import NocRequest, ActivationRequest, ReactivationRequest

router = APIRouter()

@router.get("/noc")
def get_noc_requests(db: Session = Depends(get_db)):
    return db.query(NocRequest).all()

@router.get("/activation")
def get_activation_requests(db: Session = Depends(get_db)):
    return db.query(ActivationRequest).all()

@router.get("/reactivation")
def get_reactivation_requests(db: Session = Depends(get_db)):
    return db.query(ReactivationRequest).all()
