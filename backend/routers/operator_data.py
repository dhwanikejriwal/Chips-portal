# backend/routers/operator_data.py
"""Operator Data Management API - upload and Aadhar search.

Security rules enforced here:
  * every endpoint requires a valid bearer token;
  * upload and reveal additionally require the Admin role;
  * search results carry the MASKED Aadhar only - the decrypted value is
    returned exclusively by /reveal, to an authenticated admin, and is never
    written to a log or an error message.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user_login import UserLogin
from backend.models.operator_master import OperatorMaster
from backend.routers.auth import get_current_user
from backend.services.operator_master_ingest import (
    ALLOWED_EXT, UploadError, process_upload, search_by_aadhar, search_by_name_last4,
)
from backend.utils.aadhar_crypto import (
    AadharKeyError, AadharValueError, decrypt_aadhar, mask_from_encrypted,
)

router = APIRouter(dependencies=[Depends(get_current_user)])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _require_admin(current_user=Depends(get_current_user)) -> UserLogin:
    """Admin-only gate for upload and Aadhar reveal."""
    role = getattr(getattr(current_user, "role", None), "role", None)
    if not isinstance(current_user, UserLogin) or role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user


def _serialize(rec: OperatorMaster) -> dict:
    return {
        "id": rec.id,
        "name": rec.name,
        "agency": rec.agency or "—",
        "registrar_code": rec.registrar_code,
        "operator_code": rec.operator_code,
        "status": rec.status,
        "created_at": rec.created_at.strftime("%d %b %Y, %I:%M %p") if rec.created_at else "",
        "aadhar_masked": mask_from_encrypted(rec.aadhar_encrypted),
    }


# ────────────────────────────── upload ──────────────────────────────
@router.post("/upload")
async def upload_operators(
    file: UploadFile = File(...),
    agency: str = Form(""),
    db: Session = Depends(get_db),
    _admin: UserLogin = Depends(_require_admin),
):
    """Append a CSV/Excel of operators. Existing records are never overwritten."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )
    try:
        return process_upload(db, content, file.filename or "", agency.strip())
    except UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except AadharKeyError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/upload/template")
def upload_template():
    """The exact headers the uploader expects, for the on-page hint."""
    return {
        "required": ["Name", "Aadhar number", "Registrar code", "Operator code", "Status"],
        "optional": ["Agency"],
        "allowed_extensions": sorted(ALLOWED_EXT),
    }


# ────────────────────────────── search ──────────────────────────────
@router.get("/search")
def search_operators(
    aadhar: str = Query(..., min_length=1, max_length=32),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Find records by hashed Aadhar. Returns masked values only."""
    try:
        records = search_by_aadhar(db, aadhar)
    except AadharValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except AadharKeyError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    role = getattr(getattr(current_user, "role", None), "role", None)
    return {
        "count": len(records),
        "can_reveal": role == "Admin",
        "results": [_serialize(r) for r in records],
    }


@router.get("/search-by-name")
def search_by_name(
    name: str = Query(..., min_length=1, max_length=150),
    last4: str = Query(..., min_length=1, max_length=8),
    code: str = Query("", max_length=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Find candidates by name + last 4 Aadhar digits. Masked results only.

    May legitimately return several records - name + last 4 is not unique.
    """
    try:
        records = search_by_name_last4(db, name, last4, code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except AadharKeyError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    role = getattr(getattr(current_user, "role", None), "role", None)
    return {
        "count": len(records),
        "can_reveal": role == "Admin",
        "results": [_serialize(r) for r in records],
    }


class RevealRequest(BaseModel):
    record_id: int


@router.post("/reveal")
def reveal_aadhar(
    payload: RevealRequest,
    db: Session = Depends(get_db),
    _admin: UserLogin = Depends(_require_admin),
):
    """Decrypt one record's Aadhar. Admin-only; decryption happens here, server-side."""
    record = db.query(OperatorMaster).filter(OperatorMaster.id == payload.record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found.")
    try:
        return {"id": record.id, "aadhar": decrypt_aadhar(record.aadhar_encrypted)}
    except AadharKeyError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception:
        # Never surface cipher internals to the client.
        raise HTTPException(status_code=500, detail="Unable to decrypt this record.")
