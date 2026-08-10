# backend/routers/kit_registration.py
import math
from datetime import date
from typing import Optional, List
from sqlalchemy import case

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.routers.auth import get_current_user
from backend.database import get_db
from backend.models.base import StatusEnum, get_ist_now, to_name
from backend.models.kit_registration import KitRegistration
from backend.models.station_id import StationIDRequest
from backend.models.l1_registration import L1RegistrationRequest
from backend.models.l2_registration import L2RegistrationRequest
from backend.models.master_status import MasterStatus

router = APIRouter(dependencies=[Depends(get_current_user)])


# ── Status buckets (mapped from the real L1 / L2 request lifecycles) ──────────
# L1 request is "done" once APPROVED or REVIEWED; pending while PENDING/REAPPLIED.
L1_DONE_STATES = {StatusEnum.L1_DONE.value, StatusEnum.APPROVED.value}
L1_PENDING_STATES = {StatusEnum.PENDING.value, StatusEnum.REAPPLIED.value}
# L2 request is "done" once APPROVED or L2_DONE; pending while PENDING/REAPPLIED/SENT_TO_UIDAI.
L2_DONE_STATES = {StatusEnum.L2_DONE.value, StatusEnum.APPROVED.value}
L2_PENDING_STATES = {
    StatusEnum.PENDING.value,
    StatusEnum.REAPPLIED.value,
    StatusEnum.SENT_TO_UIDAI.value,
}


def _ist_today() -> date:
    return get_ist_now().date()


def _status_name(status_id: Optional[int]) -> Optional[str]:
    if not status_id:
        return None
    return to_name(status_id).replace("_", " ").title()


# ─────────────────────────────────────────────────────────────
# Service helpers (application-layer replacements for the DB triggers)
# ─────────────────────────────────────────────────────────────

def create_kit_rows_for_station_ids(
    db: Session,
    station_ids: List[str],
    district: Optional[str] = None,
    provided_date: Optional[date] = None,
    request_no: Optional[str] = None,
):
    """Auto-create a Kit Registration row for each allotted Station ID.

    Mirrors the "after Station ID allotment" trigger: L1 starts Pending, L2 NULL.
    Idempotent per station_id (skips ones already tracked). Does NOT commit —
    the caller commits within its own transaction.
    """
    if provided_date is None:
        provided_date = _ist_today()

    for sid in station_ids:
        sid = (sid or "").strip()
        if not sid:
            continue
        exists = db.query(KitRegistration).filter(KitRegistration.station_id == sid).first()
        if exists:
            continue
        db.add(KitRegistration(
            request_no=request_no,
            station_id=sid,
            district=district,
            station_id_provided_date=provided_date,
            l1_status_id=StatusEnum.PENDING.value,
            l2_status_id=None,
        ))


def _mark_l1_done(kit: KitRegistration):
    """L1 -> Done: stamp date and auto-start L2 as Pending (trigger #3, part 1)."""
    kit.l1_status_id = StatusEnum.L1_DONE.value
    kit.l1_done_date = _ist_today()
    if kit.l2_status_id is None:
        kit.l2_status_id = StatusEnum.PENDING.value


def _mark_l2_done(kit: KitRegistration):
    """L2 -> Done: stamp completion date (trigger #3, part 2)."""
    kit.l2_status_id = StatusEnum.L2_DONE.value
    kit.l2_done_date = _ist_today()


def _l2_done_date(l2: L2RegistrationRequest) -> Optional[date]:
    """Best-effort completion date for an approved L2 request (no reviewed_at column)."""
    approved_marks = [
        rm.created_at for rm in l2.remarks
        if rm.status_after_id == StatusEnum.APPROVED.value and rm.created_at
    ]
    if approved_marks:
        return max(approved_marks).date()
    return l2.submitted_at.date() if l2.submitted_at else None


def _reconcile_kit_table(db: Session) -> None:
    """Reconcile the kit table with all three sources of allotted Station IDs:

      * station_id_requests (allotted) -> row exists with request_no/district/date
      * l1_registration_requests       -> drives L1 status / L1 done date
      * l2_registration_requests       -> drives L2 status / L2 done date

    Rows are created for any Station ID seen in L1/L2 that isn't tracked yet, and
    existing rows are updated to reflect the current request statuses. Persists
    changes so the physical table always mirrors the live request data.
    """
    today = _ist_today()

    # Allotment facts: station_id -> (request_no, district_name, provided_date)
    allot = {}
    for s in db.query(StationIDRequest).filter(
        StationIDRequest.status_id == StatusEnum.ALLOTTED.value,
        StationIDRequest.station_id_inserted.isnot(None),
    ).all():
        prov = s.reviewed_at or s.submitted_at
        prov = prov.date() if prov else None
        dname = s.district.district_name if s.district else None
        for sid in str(s.station_id_inserted).split(","):
            sid = sid.strip()
            if sid and sid not in allot:
                allot[sid] = (s.request_no, dname, prov)

    # Latest L1 / L2 request per Station ID
    l1_by_station = {}
    for req in db.query(L1RegistrationRequest).order_by(L1RegistrationRequest.id.asc()).all():
        sid = (req.station_id or "").strip()
        if sid:
            l1_by_station[sid] = req
    l2_by_station = {}
    for req in db.query(L2RegistrationRequest).order_by(L2RegistrationRequest.id.asc()).all():
        sid = (req.new_station_id or "").strip()
        if sid:
            l2_by_station[sid] = req

    kits = {k.station_id: k for k in db.query(KitRegistration).all()}
    all_sids = set(kits) | set(allot) | set(l1_by_station) | set(l2_by_station)

    changed = False
    for sid in all_sids:
        req_no, dname, prov = allot.get(sid, (None, None, None))
        # Request number carries the Station ID suffix so each kit row is uniquely
        # traceable (matches L1/L2 request_code/request_no), while the batch prefix
        # is preserved for tracking across stages.
        disp_req_no = f"{req_no}-{sid}" if req_no else None
        kit = kits.get(sid)

        if kit is None:
            # Fall back to L1/L2 request district when the station isn't in allotment
            l1 = l1_by_station.get(sid)
            l2 = l2_by_station.get(sid)
            if dname is None and l1 is not None and l1.district:
                dname = l1.district.district_name
            if dname is None and l2 is not None and l2.district:
                dname = l2.district.district_name
            kit = KitRegistration(
                request_no=disp_req_no,
                station_id=sid,
                district=dname,
                station_id_provided_date=prov,
                l1_status_id=StatusEnum.PENDING.value,
                l2_status_id=None,
            )
            db.add(kit)
            kits[sid] = kit
            changed = True
        else:
            # Fill when missing, and self-heal any legacy unsuffixed value (== batch code).
            if disp_req_no and kit.request_no in (None, "", req_no) and kit.request_no != disp_req_no:
                kit.request_no = disp_req_no
                changed = True
            if not kit.district and dname:
                kit.district = dname
                changed = True
            if not kit.station_id_provided_date and prov:
                kit.station_id_provided_date = prov
                changed = True

        # ── Sync L1 from the L1 registration request ──
        l1 = l1_by_station.get(sid)
        if l1 is not None:
            if kit.l1_status_id != l1.status_id:
                kit.l1_status_id = l1.status_id
                changed = True
            if l1.status_id in L1_DONE_STATES:
                if kit.l1_done_date is None:
                    upd = getattr(l1, "updated_at", None)
                    kit.l1_done_date = upd.date() if upd else today
                    changed = True
                if kit.l2_status_id is None:
                    kit.l2_status_id = StatusEnum.PENDING.value
                    changed = True
            elif kit.l1_done_date is not None:
                kit.l1_done_date = None
                changed = True

        # ── Sync L2 from the L2 registration request ──
        l2 = l2_by_station.get(sid)
        if l2 is not None:
            if kit.l2_status_id != l2.status_id:
                kit.l2_status_id = l2.status_id
                changed = True
            if l2.status_id in L2_DONE_STATES:
                if kit.l2_done_date is None:
                    kit.l2_done_date = _l2_done_date(l2) or today
                    changed = True
            elif kit.l2_done_date is not None:
                kit.l2_done_date = None
                changed = True

    if changed:
        db.commit()


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────

def _serialize(k: KitRegistration, status_names: dict,
               l1_has_request: bool, l2_has_request: bool) -> dict:
    today = _ist_today()

    l1_pending_days = None
    if k.l1_status_id in L1_PENDING_STATES and k.station_id_provided_date:
        l1_pending_days = (today - k.station_id_provided_date).days

    l2_pending_days = None
    if k.l2_status_id in L2_PENDING_STATES and k.l1_done_date:
        l2_pending_days = (today - k.l1_done_date).days

    l1_name = "L1 Done" if k.l1_status_id in L1_DONE_STATES else (status_names.get(k.l1_status_id) if k.l1_status_id else None)
    l2_name = "L2 Done" if k.l2_status_id in L2_DONE_STATES else (status_names.get(k.l2_status_id) if k.l2_status_id else None)

    return {
        "id": k.id,
        "request_no": k.request_no or "—",
        "station_id": k.station_id,
        "district": k.district or "—",
        "station_id_provided_date": str(k.station_id_provided_date) if k.station_id_provided_date else "—",
        "l1_status": l1_name or "—",
        "l1_done_date": str(k.l1_done_date) if k.l1_done_date else "—",
        "l1_pending_days": l1_pending_days,
        "l2_status": l2_name or "Not Started",
        "l2_done_date": str(k.l2_done_date) if k.l2_done_date else "—",
        "l2_pending_days": l2_pending_days,
        # Manual "Mark Done" only makes sense for stations with no driving L1/L2 request
        "l1_actionable": (k.l1_status_id in L1_PENDING_STATES) and not l1_has_request,
        "l2_actionable": (k.l2_status_id in L2_PENDING_STATES) and not l2_has_request,
    }


def _build_kit_query(db: Session, search: str, sort_by: str, sort_order: str):
    query = db.query(KitRegistration)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (KitRegistration.request_no.ilike(search_term)) |
            (KitRegistration.station_id.ilike(search_term)) |
            (KitRegistration.district.ilike(search_term))
        )

    if sort_by == 'l1_pending_days':
        is_pending = KitRegistration.l1_status_id.in_(L1_PENDING_STATES)
        order_col = KitRegistration.station_id_provided_date.asc() if sort_order == 'desc' else KitRegistration.station_id_provided_date.desc()
        query = query.order_by(
            case((is_pending, 0), else_=1),
            order_col.nullslast(),
            KitRegistration.id.desc()
        )
    elif sort_by == 'l2_pending_days':
        is_pending = KitRegistration.l2_status_id.in_(L2_PENDING_STATES)
        order_col = KitRegistration.l1_done_date.asc() if sort_order == 'desc' else KitRegistration.l1_done_date.desc()
        query = query.order_by(
            case((is_pending, 0), else_=1),
            order_col.nullslast(),
            KitRegistration.id.desc()
        )
    else:
        query = query.order_by(
            KitRegistration.station_id_provided_date.desc().nullslast(),
            KitRegistration.id.desc(),
        )
        
    return query


@router.get("/all")
def get_all_kit_registrations(
    page: int = 1,
    per_page: int = 50,
    search: str = "",
    sort_by: str = "",
    sort_order: str = "desc",
    db: Session = Depends(get_db)
):
    """Full kit-registration tracker for the frontend table (newest first).

    Reconciles L1/L2 status from the live registration-request tables first,
    so pending / approved / other statuses are reflected automatically.
    """
    _reconcile_kit_table(db)

    status_names = {ms.id: ms.name for ms in db.query(MasterStatus).all()}

    l1_stations = {
        (r.station_id or "").strip()
        for r in db.query(L1RegistrationRequest.station_id).all()
    }
    l2_stations = {
        (r.new_station_id or "").strip()
        for r in db.query(L2RegistrationRequest.new_station_id).all()
    }

    query = _build_kit_query(db, search, sort_by, sort_order)
    total = query.count()
    
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    
    items = [
        _serialize(r, status_names, r.station_id in l1_stations, r.station_id in l2_stations)
        for r in rows
    ]
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": math.ceil(total / per_page) if per_page > 0 else 0,
        "per_page": per_page
    }


@router.patch("/{kit_id}/l1-done")
def mark_l1_done(kit_id: int, db: Session = Depends(get_db)):
    kit = db.query(KitRegistration).filter(KitRegistration.id == kit_id).first()
    if not kit:
        raise HTTPException(status_code=404, detail="Kit registration record not found.")
    if kit.l1_status_id in [StatusEnum.L1_DONE.value, 19]:
        raise HTTPException(status_code=400, detail="L1 is already marked Done.")
    _mark_l1_done(kit)
    db.commit()
    return {"success": True, "message": "L1 marked Done. L2 started as Pending."}


@router.patch("/{kit_id}/l2-done")
def mark_l2_done(kit_id: int, db: Session = Depends(get_db)):
    kit = db.query(KitRegistration).filter(KitRegistration.id == kit_id).first()
    if not kit:
        raise HTTPException(status_code=404, detail="Kit registration record not found.")
    if kit.l2_status_id is None:
        raise HTTPException(status_code=400, detail="L2 has not started yet. Complete L1 first.")
    if kit.l2_status_id in [StatusEnum.L2_DONE.value, StatusEnum.APPROVED.value]:
        raise HTTPException(status_code=400, detail="L2 is already marked Done.")
    _mark_l2_done(kit)
    db.commit()
    return {"success": True, "message": "L2 marked Done. Kit registration complete."}


@router.get("/export-excel")
def export_kit_registration_excel(
    search: str = "",
    sort_by: str = "",
    sort_order: str = "desc",
    db: Session = Depends(get_db)
):
    """Exports all information corresponding to the requested tracking entries."""
    _reconcile_kit_table(db)

    status_names = {ms.id: ms.name for ms in db.query(MasterStatus).all()}

    l1_stations = {
        (r.station_id or "").strip()
        for r in db.query(L1RegistrationRequest.station_id).all()
    }
    l2_stations = {
        (r.new_station_id or "").strip()
        for r in db.query(L2RegistrationRequest.new_station_id).all()
    }

    query = _build_kit_query(db, search, sort_by, sort_order)
    rows = query.all()

    export_data = []
    for idx, r in enumerate(rows):
        serialized = _serialize(r, status_names, r.station_id in l1_stations, r.station_id in l2_stations)
        serialized["s_no"] = idx + 1
        serialized["machine_id"] = r.machine_id or "—"
        serialized["laptop_serial_no"] = r.laptop_serial_no or "—"
        serialized["laptop_name"] = r.laptop_name or "—"
        export_data.append(serialized)

    column_mappings = {
        "s_no": "S.No",
        "request_no": "Request No",
        "station_id": "Station ID",
        "district": "District",
        "station_id_provided_date": "Station ID Provided Date",
        "l1_status": "L1 Status",
        "l1_done_date": "L1 Done Date",
        "l1_pending_days": "L1 Pending Days",
        "l2_status": "L2 Status",
        "l2_done_date": "L2 Done Date",
        "l2_pending_days": "L2 Pending Days",
        "machine_id": "Machine ID",
        "laptop_serial_no": "Laptop Serial No",
        "laptop_name": "Laptop Name"
    }

    from backend.utils.exporter import generate_csv_export
    return generate_csv_export(export_data, column_mappings, "kit_registration_status")
