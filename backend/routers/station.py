# backend/routers/station.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.station import StationKitDetails

router = APIRouter()

@router.get("/kits")
def get_station_kits(db: Session = Depends(get_db)):
    return db.query(StationKitDetails).all()
