# backend/routers/operator_activity.py
"""Operator Activity + Kit Tracker API.

All aggregation happens in SQL. Filter params are bound. Query windows wider
than the configured maximum are rejected. See the module-level docstrings of
backend/services/* for the ingestion pipeline.
"""
from __future__ import annotations

import csv
import io
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile,
)
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import func, and_, or_, asc, desc, String, select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.models.base import get_ist_now
from backend.models.operator_daily_activity import (
    OperatorDailyActivity as ODA, ActivityStation, OperatorActivityMaster,
    ActivityUploadBatch, ActivityDailyUploadLog,
)
from backend.models.kit_tracker import KitTracker
from backend.services import activity_config as cfg
from backend.services.registrar_ea_ingest import process_registrar_ea_upload, delete_batch
from backend.services.kit_tracker_ingest import process_kit_tracker_upload
from backend.services.missing_dates import get_missing_dates
from backend.utils.district_mapper import normalize_district_name

router = APIRouter(dependencies=[Depends(get_current_user)])

ALLOWED_EXT = {".xlsx", ".xls", ".csv"}
MEASURES = [
    "New_Aadhaar_Enrolment", "New_Aadhar_18_plus", "Total_Updates",
    "Total_Demographic_Updates", "Total_Biometric_Updates", "NON_MBU", "IS_MBU",
    "COUNT_6AM_TO_10PM", "COUNT_10PM_TO_6AM", "Total_Enrollment_and_Updates",
]
SORTABLE = set(MEASURES) | {"activity_date", "session_operator_id", "station_number",
                            "station_ea_code", "machine_district", "days_active",
                            "stations_count"}


# ────────────────────────────── helpers ──────────────────────────────
def _parse_date(s: Optional[str], field: str) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field} date (use YYYY-MM-DD).")


def _validate_range(frm: Optional[date], to: Optional[date]) -> None:
    if frm and to:
        if to < frm:
            raise HTTPException(status_code=400, detail="'to' must be on or after 'from'.")
        if (to - frm).days > cfg.MAX_QUERY_RANGE_DAYS:
            raise HTTPException(
                status_code=400,
                detail=f"Date range too large (max {cfg.MAX_QUERY_RANGE_DAYS} days).",
            )


# An ODA station is "ECMP" (kit-based) when its station_number exists in the
# Kit Tracker; otherwise the operator is treated as VLE. Both the model filter
# and the profile drill-down key off this same station_id ↔ station_number join.
def _kt_match():
    return func.cast(ODA.station_number, String).in_(select(KitTracker.station_id))


def _operators_by_model(db, model: Optional[str]):
    """Sub-select of session_operator_ids matching the requested model.

    An operator is ECMP if ANY of their stations is in the Kit Tracker, VLE if
    NONE are. Classification is per-operator so aggregates/totals stay consistent.
    """
    if model not in ("ecmp", "vle"):
        return None
    sub = db.query(ODA.session_operator_id).group_by(ODA.session_operator_id)
    flag = func.bool_or(_kt_match())
    return sub.having(flag.is_(True) if model == "ecmp" else flag.is_(False))


def _multi_station_operators(db):
    """Sub-select of operators who worked at more than one distinct station."""
    return (db.query(ODA.session_operator_id).group_by(ODA.session_operator_id)
            .having(func.count(func.distinct(ODA.station_number)) > 1))


def _base_filters(q, frm, to, districts, stations, ea_codes, search, off_hours,
                  model=None, multi_station=False, db=None):
    if frm:
        q = q.filter(ODA.activity_date >= frm)
    if to:
        q = q.filter(ODA.activity_date <= to)
    if districts:
        dist_filters = []
        for d in districts:
            dist_filters.append(ODA.machine_district.ilike(f"%{d}%"))
            if "manendragarh" in d.lower() or "mcb" in d.lower() or "chirmiri" in d.lower():
                dist_filters.extend([
                    ODA.machine_district.ilike("%Manendragarh%"),
                    ODA.machine_district.ilike("%Chirmiri%"),
                    ODA.machine_district.ilike("%Bharatpur%"),
                    ODA.machine_district.ilike("%â€%"),
                ])
        q = q.filter(or_(*dist_filters))
    if stations:
        q = q.filter(ODA.station_number.in_(stations))
    if ea_codes:
        q = q.filter(ODA.station_ea_code.in_(ea_codes))
    if off_hours:
        q = q.filter(ODA.COUNT_10PM_TO_6AM > 0)
    if model and db is not None:
        sub = _operators_by_model(db, model)
        if sub is not None:
            sq = sub.subquery()
            q = q.filter(ODA.session_operator_id.in_(select(sq.c.session_operator_id)))
    if multi_station and db is not None:
        sq = _multi_station_operators(db).subquery()
        q = q.filter(ODA.session_operator_id.in_(select(sq.c.session_operator_id)))
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(or_(
            ODA.session_operator_id.ilike(like),
            func.cast(ODA.station_number, String).ilike(like),
        ))
    return q


# ────────────────────────────── uploads ──────────────────────────────
def _save_upload(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Use .xlsx, .xls or .csv.")
    cfg.ensure_dirs()
    dest = os.path.join(cfg.UPLOAD_TMP_DIR, f"{uuid.uuid4().hex}{ext}")
    with open(dest, "wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    return dest


@router.post("/upload")
def upload_activity(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    source: str = Form("registrar_ea"),
    registrar_code: Optional[int] = Form(None),
    ea_code: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if source not in ("registrar_ea", "kit_tracker"):
        raise HTTPException(status_code=400, detail="source must be 'registrar_ea' or 'kit_tracker'.")
    path = _save_upload(file)
    batch_id = str(uuid.uuid4())
    reg = registrar_code or cfg.DEFAULT_REGISTRAR_CODE
    ea = ea_code or cfg.DEFAULT_EA_CODE

    db.add(ActivityUploadBatch(
        batch_id=batch_id, source=source, filename=file.filename,
        uploaded_by=getattr(user, "username", None) or getattr(user, "user_code", None),
        uploaded_at=get_ist_now(), status="uploading", stage="Uploading", progress=5,
        registrar_code=reg if source == "registrar_ea" else None,
        ea_code=ea if source == "registrar_ea" else None,
    ))
    db.commit()

    if source == "registrar_ea":
        background.add_task(process_registrar_ea_upload, batch_id, path, reg, ea)
    else:
        background.add_task(process_kit_tracker_upload, batch_id, path)
    return {"batch_id": batch_id}


@router.get("/upload/{batch_id}")
def upload_status(batch_id: str, db: Session = Depends(get_db)):
    b = db.query(ActivityUploadBatch).filter_by(batch_id=batch_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return {
        "batch_id": b.batch_id, "status": b.status, "stage": b.stage, "progress": b.progress,
        "summary": {
            "rows_read": b.rows_read, "rows_after_filter": b.rows_after_filter,
            "rows_written": b.rows_written, "rows_inserted": b.rows_inserted,
            "rows_updated": b.rows_updated, "rejected_count": b.rejected_count,
            "date_min": b.date_min.isoformat() if b.date_min else None,
            "date_max": b.date_max.isoformat() if b.date_max else None,
            "distinct_operators": b.distinct_operators, "processing_ms": b.processing_ms,
            "note": b.error_detail if b.status == "done" else None,
        },
        "errors": b.error_detail if b.status == "failed" else None,
        "has_rejected": bool(b.rejected_path),
    }


@router.get("/uploads")
def upload_history(db: Session = Depends(get_db), limit: int = Query(50, le=200)):
    rows = (db.query(ActivityUploadBatch)
            .order_by(desc(ActivityUploadBatch.uploaded_at)).limit(limit).all())
    return [{
        "batch_id": b.batch_id, "source": b.source, "filename": b.filename,
        "uploaded_by": b.uploaded_by,
        "uploaded_at": b.uploaded_at.isoformat() if b.uploaded_at else None,
        "status": b.status, "rows_written": b.rows_written,
        "rows_inserted": b.rows_inserted, "rows_updated": b.rows_updated,
        "date_min": b.date_min.isoformat() if b.date_min else None,
        "date_max": b.date_max.isoformat() if b.date_max else None,
    } for b in rows]


@router.delete("/uploads/{batch_id}")
def rollback_batch(batch_id: str, db: Session = Depends(get_db)):
    b = db.query(ActivityUploadBatch).filter_by(batch_id=batch_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Batch not found.")
    if b.source == "kit_tracker":
        deleted = db.query(KitTracker).filter_by(batch_id=batch_id).delete()
        db.query(ActivityUploadBatch).filter_by(batch_id=batch_id).delete()
        db.commit()
    else:
        deleted = delete_batch(db, batch_id)
    return {"deleted_rows": deleted}


@router.get("/rejected/{batch_id}")
def download_rejected(batch_id: str, db: Session = Depends(get_db)):
    b = db.query(ActivityUploadBatch).filter_by(batch_id=batch_id).first()
    if not b or not b.rejected_path or not os.path.exists(b.rejected_path):
        raise HTTPException(status_code=404, detail="No rejected rows for this batch.")
    return FileResponse(b.rejected_path, media_type="text/csv",
                        filename=f"rejected_{batch_id}.csv")


# ─────────────────────────── activity list ───────────────────────────
@router.get("")
@router.get("/")
def list_activity(
    db: Session = Depends(get_db),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    districts: Optional[list[str]] = Query(None),
    stations: Optional[list[int]] = Query(None),
    eaCodes: Optional[list[int]] = Query(None),
    search: Optional[str] = None,
    offHoursOnly: bool = False,
    model: Optional[str] = Query(None, pattern="^(ecmp|vle)$"),
    multiStationOnly: bool = False,
    groupBy: str = Query("operator", pattern="^(operator|daily)$"),
    sortBy: str = "Total_Enrollment_and_Updates",
    sortDir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
):
    frm, dto = _parse_date(from_, "from"), _parse_date(to, "to")
    _validate_range(frm, dto)
    if sortBy not in SORTABLE:
        sortBy = "Total_Enrollment_and_Updates"
    direction = desc if sortDir == "desc" else asc

    measure_sums = [func.coalesce(func.sum(getattr(ODA, m)), 0).label(m) for m in MEASURES]

    # In the multi-station view each station gets its OWN row (grouped by
    # operator+station), so an operator working two stations appears as two rows.
    per_station = groupBy == "operator" and multiStationOnly

    if per_station:
        cols = [
            ODA.session_operator_id, ODA.station_ea_code, ODA.station_number,
            ODA.machine_district,
            func.count(func.distinct(ODA.activity_date)).label("days_active"),
            func.bool_or(_kt_match()).label("is_ecmp"),
            *measure_sums,
        ]
        q = db.query(*cols)
        q = _base_filters(q, frm, dto, districts, stations, eaCodes, search, offHoursOnly,
                          model=model, multi_station=multiStationOnly, db=db)
        q = q.group_by(ODA.session_operator_id, ODA.station_ea_code,
                       ODA.station_number, ODA.machine_district)
        order_col = "days_active" if sortBy == "days_active" else None
        # keep an operator's stations together, then order within by the measure
        q = q.order_by(ODA.session_operator_id,
                       direction(order_col) if order_col else direction(sortBy))
    elif groupBy == "operator":
        # NOTE: measures are summed across ALL of the operator's stations, so the
        # single station/district shown is the MOST RECENT one (resolved below),
        # plus a stations_count so a multi-station operator is obvious.
        cols = [
            ODA.session_operator_id,
            func.count(func.distinct(ODA.activity_date)).label("days_active"),
            func.count(func.distinct(ODA.station_number)).label("stations_count"),
            func.bool_or(_kt_match()).label("is_ecmp"),
            *measure_sums,
        ]
        q = db.query(*cols)
        q = _base_filters(q, frm, dto, districts, stations, eaCodes, search, offHoursOnly,
                          model=model, multi_station=multiStationOnly, db=db)
        q = q.group_by(ODA.session_operator_id)
        order_col = {"days_active": "days_active", "stations_count": "stations_count"}.get(sortBy)
        if order_col:
            q = q.order_by(direction(order_col))
        elif sortBy in MEASURES or sortBy == "session_operator_id":
            q = q.order_by(direction(sortBy))
        else:
            sort_attr = getattr(ODA, sortBy, None)
            if sort_attr is not None:
                q = q.order_by(direction(func.max(sort_attr)))
            else:
                q = q.order_by(direction("Total_Enrollment_and_Updates"))
    else:
        cols = [
            ODA.activity_date, ODA.session_operator_id, ODA.station_ea_code,
            ODA.station_number, ODA.machine_district,
            _kt_match().label("is_ecmp"), *[getattr(ODA, m) for m in MEASURES],
        ]
        q = db.query(*cols)
        q = _base_filters(q, frm, dto, districts, stations, eaCodes, search, offHoursOnly,
                          model=model, multi_station=multiStationOnly, db=db)
        q = q.order_by(direction(sortBy))

    total_rows = q.order_by(None).count()
    page_rows = q.offset((page - 1) * pageSize).limit(pageSize).all()

    # Attach operator names (for the current page only).
    op_ids = {r.session_operator_id for r in page_rows}
    names = dict(db.query(OperatorActivityMaster.session_operator_id,
                          OperatorActivityMaster.operator_name)
                 .filter(OperatorActivityMaster.session_operator_id.in_(op_ids)).all()) if op_ids else {}

    # In operator mode, resolve the MOST-RECENT station/district per operator
    # (DISTINCT ON, newest date first) for the page's operators only.
    recent = {}
    if groupBy == "operator" and not per_station and op_ids:
        sub = (db.query(ODA.session_operator_id, ODA.station_number,
                        ODA.station_ea_code, ODA.machine_district)
               .filter(ODA.session_operator_id.in_(op_ids))
               .distinct(ODA.session_operator_id)
               .order_by(ODA.session_operator_id, desc(ODA.activity_date),
                         desc(ODA.station_number)))
        for row in sub.all():
            recent[row.session_operator_id] = row

    def row_to_dict(r):
        d = {c: getattr(r, c, None) for c in MEASURES}
        d = {k: int(v or 0) for k, v in d.items()}
        d["session_operator_id"] = r.session_operator_id
        d["operator_name"] = names.get(r.session_operator_id)
        d["model"] = "ECMP" if getattr(r, "is_ecmp", False) else "VLE"
        if per_station:
            # one row per operator-station
            d["station_ea_code"] = r.station_ea_code
            d["station_number"] = r.station_number
            d["machine_district"] = r.machine_district
            d["days_active"] = getattr(r, "days_active", None)
            d["stations_count"] = 1
        elif groupBy == "operator":
            rc = recent.get(r.session_operator_id)
            d["station_ea_code"] = rc.station_ea_code if rc else None
            d["station_number"] = rc.station_number if rc else None
            d["machine_district"] = rc.machine_district if rc else None
            d["days_active"] = getattr(r, "days_active", None)
            d["stations_count"] = getattr(r, "stations_count", None)
        else:
            d["station_ea_code"] = getattr(r, "station_ea_code", None)
            d["station_number"] = getattr(r, "station_number", None)
            d["machine_district"] = getattr(r, "machine_district", None)
            d["activity_date"] = r.activity_date.isoformat() if r.activity_date else None
        # Compliance flag from the row's station Kit Tracker record:
        #   active   → operator, station AND onboarding statuses are all Active
        #   inactive → at least one of them is Inactive
        #   unknown  → no Kit Tracker record for the station (e.g. VLE)
        d["status_flag"] = kt_status.get(str(d.get("station_number")), "unknown")
        return d

    # Resolve the three Kit Tracker statuses for every station on this page.
    page_station_ids = set()
    for r in page_rows:
        sn = getattr(r, "station_number", None)
        if sn is None and not per_station and groupBy == "operator":
            rc = recent.get(r.session_operator_id)
            sn = rc.station_number if rc else None
        if sn is not None:
            page_station_ids.add(str(sn))
    kt_status = {}
    if page_station_ids:
        for kt in (db.query(KitTracker.station_id, KitTracker.operator_status,
                            KitTracker.station_status, KitTracker.onboarding_status)
                   .filter(KitTracker.station_id.in_(page_station_ids)).all()):
            all_active = all(
                (s or "").strip().lower() == "active"
                for s in (kt.operator_status, kt.station_status, kt.onboarding_status)
            )
            kt_status[kt.station_id] = "active" if all_active else "inactive"

    rows = [row_to_dict(r) for r in page_rows]

    # Totals over the WHOLE filtered set (not just this page).
    tq = db.query(*measure_sums)
    tq = _base_filters(tq, frm, dto, districts, stations, eaCodes, search, offHoursOnly,
                       model=model, multi_station=multiStationOnly, db=db)
    trow = tq.one()
    totals = {m: int(getattr(trow, m) or 0) for m in MEASURES}

    summary = _summary(db, frm, dto, districts, stations, eaCodes, search, offHoursOnly,
                       totals, model=model, multi_station=multiStationOnly)

    return {
        "rows": rows,
        "totals": totals,
        "summary": summary,
        "pagination": {"page": page, "pageSize": pageSize, "total": total_rows,
                       "pages": (total_rows + pageSize - 1) // pageSize},
    }


def _summary(db, frm, dto, districts, stations, ea_codes, search, off_hours, totals,
             model=None, multi_station=False):
    aq = db.query(func.count(func.distinct(ODA.session_operator_id)))
    aq = _base_filters(aq, frm, dto, districts, stations, ea_codes, search, off_hours,
                       model=model, multi_station=multi_station, db=db)
    active_ops = aq.scalar() or 0

    oq = db.query(func.coalesce(func.sum(ODA.COUNT_10PM_TO_6AM), 0))
    oq = _base_filters(oq, frm, dto, districts, stations, ea_codes, search, off_hours,
                       model=model, multi_station=multi_station, db=db)
    off_hours_txns = int(oq.scalar() or 0)

    result = {**totals, "active_operators": active_ops, "off_hours_transactions": off_hours_txns}

    # % change vs the immediately-preceding window of equal length.
    if frm and dto:
        length = (dto - frm).days + 1
        p_to = frm - timedelta(days=1)
        p_from = p_to - timedelta(days=length - 1)
        pq = db.query(func.coalesce(func.sum(ODA.Total_Enrollment_and_Updates), 0))
        pq = _base_filters(pq, p_from, p_to, districts, stations, ea_codes, search, off_hours,
                           model=model, multi_station=multi_station, db=db)
        prev_total = int(pq.scalar() or 0)
        cur = totals["Total_Enrollment_and_Updates"]
        result["prev_total_enrollment_and_updates"] = prev_total
        result["pct_change_total"] = (
            round((cur - prev_total) / prev_total * 100, 1) if prev_total else None
        )
    return result


@router.get("/filters")
def filters(db: Session = Depends(get_db)):
    raw_districts = [d[0] for d in db.query(ODA.machine_district)
                     .filter(ODA.machine_district.isnot(None)).all()]
    districts = sorted(list({normalize_district_name(d) for d in raw_districts if d and d.strip()}))
    stations = [s[0] for s in db.query(ODA.station_number).distinct()
                .order_by(ODA.station_number).all()]
    ea_codes = [e[0] for e in db.query(ODA.station_ea_code).distinct()
                .order_by(ODA.station_ea_code).all()]
    bounds = db.query(func.min(ODA.activity_date), func.max(ODA.activity_date)).one()
    return {
        "districts": districts, "stations": stations, "eaCodes": ea_codes,
        "minDate": bounds[0].isoformat() if bounds[0] else None,
        "maxDate": bounds[1].isoformat() if bounds[1] else None,
    }


@router.get("/export")
def export_csv(
    db: Session = Depends(get_db),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    districts: Optional[list[str]] = Query(None),
    stations: Optional[list[int]] = Query(None),
    eaCodes: Optional[list[int]] = Query(None),
    search: Optional[str] = None,
    offHoursOnly: bool = False,
    model: Optional[str] = Query(None, pattern="^(ecmp|vle)$"),
    multiStationOnly: bool = False,
    groupBy: str = Query("operator", pattern="^(operator|daily)$"),
    sortBy: str = "Total_Enrollment_and_Updates",
    sortDir: str = Query("desc", pattern="^(asc|desc)$"),
):
    def _run(page):
        return list_activity(
            db=db, from_=from_, to=to, districts=districts, stations=stations,
            eaCodes=eaCodes, search=search, offHoursOnly=offHoursOnly, model=model,
            multiStationOnly=multiStationOnly, groupBy=groupBy,
            sortBy=sortBy, sortDir=sortDir, page=page, pageSize=200,
        )

    def generate():
        buf = io.StringIO()
        w = csv.writer(buf)
        header = (["activity_date"] if groupBy == "daily" else ["days_active"])
        header = ["session_operator_id", "operator_name", "model", "station_ea_code",
                  "station_number", "machine_district"] + header + MEASURES
        w.writerow(header)
        yield buf.getvalue(); buf.seek(0); buf.truncate(0)
        # stream all pages
        page = 1
        while True:
            res = _run(page)
            for r in res["rows"]:
                extra = [r.get("activity_date")] if groupBy == "daily" else [r.get("days_active")]
                w.writerow([r.get("session_operator_id"), r.get("operator_name"),
                            r.get("model"), r.get("station_ea_code"), r.get("station_number"),
                            r.get("machine_district")] + extra + [r.get(m, 0) for m in MEASURES])
            yield buf.getvalue(); buf.seek(0); buf.truncate(0)
            if page >= res["pagination"]["pages"]:
                break
            page += 1

    return StreamingResponse(generate(), media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=operator_activity.csv"})


@router.get("/missing-dates")
def missing_dates(db: Session = Depends(get_db)):
    dates = get_missing_dates(db, force=True)
    return {"count": len(dates), "dates": [d.isoformat() for d in dates]}


# ───────────────────────── operator anomalies ─────────────────────────
# Reconciliation of the uploaded logs against the Kit Tracker, on operator ID
# and station ID. Model rule for this section: a station present in the Kit
# Tracker is Inhouse, a station absent from it is VLE.
ANOMALY_REASONS = {
    "mixed_model": "Operator works across both Inhouse and VLE stations",
    "operator_mismatch": "Log operator differs from Kit Tracker operator",
    "no_kt_operator": "Station has no operator assigned in Kit Tracker",
    "operator_not_in_kt": "Operator ID not present anywhere in Kit Tracker",
    "assigned_elsewhere": "Operator is assigned to a different station in Kit Tracker",
    "kt_multi_station": "Operator is assigned to multiple stations in Kit Tracker",
}


ANOMALY_SORTABLE = {
    "session_operator_id", "operator_name", "station_number", "station_ea_code",
    "machine_district", "model", "kit_tracker_operator", "days_active",
    "Total_Enrollment_and_Updates", "reason",
}


def _norm_code(v) -> str:
    return str(v).strip().lower() if v not in (None, "") else ""


@router.get("/anomalies")
def operator_anomalies(
    db: Session = Depends(get_db),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    districts: Optional[list[str]] = Query(None),
    search: Optional[str] = None,
    sortBy: Optional[str] = None,
    sortDir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
):
    """Operator/station log records that do not reconcile with the Kit Tracker.

    One row per operator+station seen in the logs (aggregated over the filtered
    window). Only flagged rows are returned; clean records are dropped.
    """
    frm, dto = _parse_date(from_, "from"), _parse_date(to, "to")
    _validate_range(frm, dto)

    q = db.query(
        ODA.session_operator_id,
        ODA.station_number,
        ODA.station_ea_code,
        func.max(ODA.machine_district).label("machine_district"),
        func.count(func.distinct(ODA.activity_date)).label("days_active"),
        func.min(ODA.activity_date).label("first_date"),
        func.max(ODA.activity_date).label("last_date"),
        func.coalesce(func.sum(ODA.Total_Enrollment_and_Updates), 0).label("total_eu"),
    )
    q = _base_filters(q, frm, dto, districts, None, None, search, False)
    pairs = q.group_by(ODA.session_operator_id, ODA.station_number,
                       ODA.station_ea_code).all()

    # The whole Kit Tracker is needed (not just the stations in play) so an
    # operator assigned to a station they never logged at is still detectable.
    kt_by_station = {}
    kt_stations_by_operator: dict[str, list[str]] = {}
    for kt in db.query(KitTracker.station_id, KitTracker.operator_code_raw,
                       KitTracker.operator_name_raw).all():
        sid = (kt.station_id or "").strip()
        if not sid:
            continue
        kt_by_station[sid] = kt
        code = _norm_code(kt.operator_code_raw)
        if code:
            kt_stations_by_operator.setdefault(code, []).append(sid)

    # An operator's model set across every station they logged at, used for the
    # mixed-model check (needs the operator's full picture, so it is computed
    # over all pairs before any row is judged).
    models_by_operator: dict[str, set[str]] = {}
    for p in pairs:
        model = "Inhouse" if str(p.station_number) in kt_by_station else "VLE"
        models_by_operator.setdefault(p.session_operator_id, set()).add(model)

    flagged = []
    for p in pairs:
        sid = str(p.station_number)
        kt = kt_by_station.get(sid)
        model = "Inhouse" if kt else "VLE"
        op = p.session_operator_id
        op_norm = _norm_code(op)
        assigned = kt_stations_by_operator.get(op_norm, [])
        codes, reasons = [], []

        def flag(key, detail=None):
            codes.append(key)
            reasons.append(ANOMALY_REASONS[key] + (f" ({detail})" if detail else ""))

        if len(models_by_operator.get(op, ())) > 1:
            flag("mixed_model")

        if kt:
            kt_code = _norm_code(kt.operator_code_raw)
            if not kt_code and not _norm_code(kt.operator_name_raw):
                flag("no_kt_operator")
            elif kt_code != op_norm:
                flag("operator_mismatch")

        if not assigned:
            # Absent from the Kit Tracker is normal for a VLE station, but an
            # Inhouse station's operator is expected to be on the sheet.
            if model == "Inhouse":
                flag("operator_not_in_kt")
        elif sid not in assigned:
            flag("assigned_elsewhere", "Kit Tracker station " + ", ".join(sorted(assigned)))

        if len(assigned) > 1:
            flag("kt_multi_station", ", ".join(sorted(assigned)))

        if not reasons:
            continue
        flagged.append({
            "session_operator_id": op,
            "station_number": p.station_number,
            "station_ea_code": p.station_ea_code,
            "machine_district": p.machine_district,
            "model": model,
            "kit_tracker_operator": (kt.operator_code_raw if kt else None),
            "kit_tracker_operator_name": (kt.operator_name_raw if kt else None),
            "days_active": int(p.days_active or 0),
            "first_date": p.first_date.isoformat() if p.first_date else None,
            "last_date": p.last_date.isoformat() if p.last_date else None,
            "Total_Enrollment_and_Updates": int(p.total_eu or 0),
            "reason_codes": codes,
            "reason": "; ".join(reasons),
        })

    rows_per_operator: dict[str, int] = {}
    for r in flagged:
        rows_per_operator[r["session_operator_id"]] = rows_per_operator.get(
            r["session_operator_id"], 0) + 1

    # Names are resolved for the whole flagged set (not just the page) so the
    # Operator Name column is sortable like the main list's columns.
    op_ids = {r["session_operator_id"] for r in flagged}
    names = dict(db.query(OperatorActivityMaster.session_operator_id,
                          OperatorActivityMaster.operator_name)
                 .filter(OperatorActivityMaster.session_operator_id.in_(op_ids)).all()) if op_ids else {}
    for r in flagged:
        r["operator_name"] = names.get(r["session_operator_id"])

    # Base order: an operator's rows stay together, worst offenders first. A
    # column sort is layered on top of it — Python's sort is stable, so this
    # doubles as the tie-break.
    flagged.sort(key=lambda r: (-rows_per_operator[r["session_operator_id"]],
                                r["session_operator_id"], r["station_number"]))
    if sortBy in ANOMALY_SORTABLE:
        present = [r for r in flagged if r[sortBy] is not None]
        present.sort(key=lambda r: r[sortBy], reverse=(sortDir == "desc"))
        flagged = present + [r for r in flagged if r[sortBy] is None]  # nulls last

    total = len(flagged)
    page_rows = flagged[(page - 1) * pageSize: page * pageSize]

    by_reason = {k: 0 for k in ANOMALY_REASONS}
    for r in flagged:
        for c in set(r["reason_codes"]):
            by_reason[c] += 1

    return {
        "rows": page_rows,
        "totals": {
            "days_active": sum(r["days_active"] for r in flagged),
            "Total_Enrollment_and_Updates": sum(
                r["Total_Enrollment_and_Updates"] for r in flagged),
        },
        "summary": {
            "flagged_records": total,
            "flagged_operators": len(rows_per_operator),
            "records_checked": len(pairs),
            "by_reason": by_reason,
        },
        "reason_labels": ANOMALY_REASONS,
        "pagination": {"page": page, "pageSize": pageSize, "total": total,
                       "pages": (total + pageSize - 1) // pageSize},
    }


# ─────────────────────────── operator drill-down ───────────────────────────
@router.get("/operators/{session_operator_id}")
def operator_profile(session_operator_id: str, db: Session = Depends(get_db)):
    """Operator drill-down profile.

    Real compliance data (deposit, L1/L2, onboarding, contact) comes from the
    Kit Tracker row matching the operator's most-recent station. Operators with
    no Kit Tracker row are VLE — those fields are simply blank.
    """
    m = db.query(OperatorActivityMaster).filter_by(session_operator_id=session_operator_id).first()
    oda_op = db.query(ODA).filter_by(session_operator_id=session_operator_id).first() if not m else None
    kt_op = db.query(KitTracker).filter_by(operator_code_raw=session_operator_id).first() if not m else None

    if not m and not oda_op and not kt_op:
        raise HTTPException(status_code=404, detail="Operator not found.")

    # current posting = most-recent station worked
    recent = (db.query(ODA.station_ea_code, ODA.station_number, ODA.machine_district)
              .filter(ODA.session_operator_id == session_operator_id)
              .order_by(desc(ODA.activity_date)).first())

    station = None
    kt = None
    if recent:
        st = db.query(ActivityStation).filter_by(
            station_ea_code=recent[0], station_number=recent[1]).first()
        station = {
            "station_ea_code": recent[0], "station_number": recent[1],
            "machine_district": recent[2],
            "machine_address": st.machine_address if st else None,
            "machine_state": st.machine_state if st else None,
            "machine_pincode": st.machine_pincode if st else None,
        }
        # Model = ECMP if ANY of the operator's stations is in the Kit Tracker
        # (matches the list's per-operator classification). Prefer the kit record
        # for the most-recent station; else fall back to any station that has one.
        kt = db.query(KitTracker).filter_by(station_id=str(recent[1])).first()
        if not kt:
            op_stations = [str(s[0]) for s in db.query(ODA.station_number).filter(
                ODA.session_operator_id == session_operator_id).distinct().all()]
            if op_stations:
                kt = (db.query(KitTracker)
                      .filter(KitTracker.station_id.in_(op_stations)).first())

    if not kt and kt_op:
        kt = kt_op

    def d(v):
        return v.isoformat() if v else None

    op_name = session_operator_id
    if kt and kt.operator_name_raw:
        op_name = kt.operator_name_raw
    elif m and m.operator_name:
        op_name = m.operator_name
    elif oda_op and oda_op.operator_name:
        op_name = oda_op.operator_name

    model = "ECMP" if kt else "VLE"
    return {
        "session_operator_id": session_operator_id,
        "operator_name": op_name,
        "model": model,
        # Real contact / identity from Kit Tracker (blank for VLE)
        "mobile_number": kt.operator_mobile_raw if kt else None,
        "operator_code": kt.operator_code_raw if kt else None,
        # Onboarding (Kit Tracker)
        "onboarding_status": kt.onboarding_status if kt else None,
        "onboarding_date": d(kt.onboard_date) if kt else None,
        "station_id_allotted_date": d(kt.station_id_allotted_date) if kt else None,
        # Security deposit (Kit Tracker — status/date only; no amount/txn is tracked)
        "security_deposit_status": kt.security_deposit_status if kt else None,
        "security_deposit_date": d(kt.security_deposit_date) if kt else None,
        # L1 / L2 verification
        "l1_status": kt.l1_status if kt else None, "l1_date": d(kt.l1_date) if kt else None,
        "l2_status": kt.l2_status if kt else None, "l2_date": d(kt.l2_date) if kt else None,
        # Operational status
        "operator_status": kt.operator_status if kt else None,
        "station_status": kt.station_status if kt else None,
        "kit_working": kt.kit_working if kt else None,
        "permit_18_plus": kt.permit_18_plus if kt else None,
        "inactive_reason": kt.inactive_reason if kt else None,
        "inactive_date": d(kt.inactive_date) if kt else None,
        # Kit / machine
        "machine_id": kt.machine_id if kt else None,
        "laptop_name": kt.laptop_name if kt else None,
        "laptop_serial_no": kt.laptop_serial_no if kt else None,
        "kit_slot": kt.kit_slot if kt else None,
        # Location classification
        "block": kt.block if kt else None, "category": kt.category if kt else None,
        "locality": kt.locality if kt else None,
        "current_status": (kt.operator_status if kt and kt.operator_status else "ACTIVE"),
        "remarks": kt.remark if kt else None,
        "current_posting": station,
    }


@router.get("/operators/{session_operator_id}/activity")
def operator_activity(
    session_operator_id: str, db: Session = Depends(get_db),
    from_: Optional[str] = Query(None, alias="from"), to: Optional[str] = Query(None),
):
    frm, dto = _parse_date(from_, "from"), _parse_date(to, "to")
    _validate_range(frm, dto)
    q = db.query(ODA).filter(ODA.session_operator_id == session_operator_id)
    if frm:
        q = q.filter(ODA.activity_date >= frm)
    if dto:
        q = q.filter(ODA.activity_date <= dto)
    rows = q.order_by(desc(ODA.activity_date)).all()

    daily = [{
        "activity_date": r.activity_date.isoformat(),
        **{m: int(getattr(r, m) or 0) for m in MEASURES},
        "station_number": r.station_number, "machine_district": r.machine_district,
    } for r in rows]

    totals = {m: sum(d[m] for d in daily) for m in MEASURES}
    off_days = [d["activity_date"] for d in daily if d["COUNT_10PM_TO_6AM"] > 0]
    stations = {}
    for r in rows:
        key = r.station_number
        s = stations.setdefault(key, {"station_number": key, "machine_district": r.machine_district,
                                      "days": set(), "total": 0})
        s["days"].add(r.activity_date)
        s["total"] += int(r.Total_Enrollment_and_Updates or 0)
    stations_out = [{"station_number": s["station_number"], "machine_district": s["machine_district"],
                     "days_worked": len(s["days"]), "total_transactions": s["total"]}
                    for s in stations.values()]

    return {"daily": daily, "totals": totals, "off_hours_dates": off_days,
            "stations": stations_out}


# ─────────────────────────────── kit tracker ───────────────────────────────
@router.post("/kit-tracker/upload")
def upload_kit_tracker(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    path = _save_upload(file)
    batch_id = str(uuid.uuid4())
    db.add(ActivityUploadBatch(
        batch_id=batch_id, source="kit_tracker", filename=file.filename,
        uploaded_by=getattr(user, "username", None) or getattr(user, "user_code", None),
        uploaded_at=get_ist_now(), status="uploading", stage="Uploading", progress=5,
    ))
    db.commit()
    background.add_task(process_kit_tracker_upload, batch_id, path)
    return {"batch_id": batch_id}


@router.get("/kit-tracker")
def list_kit_tracker(
    db: Session = Depends(get_db),
    district: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    sortBy: str = "sr_no",
    sortDir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
):
    q = db.query(KitTracker)
    if district:
        q = q.filter(KitTracker.district_code == district)
    if status:
        q = q.filter(KitTracker.station_status == status)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(or_(
            KitTracker.station_id.ilike(like),
            KitTracker.operator_name_raw.ilike(like),
            KitTracker.operator_code_raw.ilike(like),
            KitTracker.machine_id.ilike(like),
        ))
    sort_col = getattr(KitTracker, sortBy, KitTracker.sr_no)
    q = q.order_by(desc(sort_col) if sortDir == "desc" else asc(sort_col))
    total = q.count()
    rows = q.offset((page - 1) * pageSize).limit(pageSize).all()

    def d(v):
        return v.isoformat() if v else None

    out = [{
        "id": r.id, "sr_no": r.sr_no, "district_code": r.district_code,
        "station_id": r.station_id, "kit_slot": r.kit_slot,
        "station_id_allotted_date": d(r.station_id_allotted_date),
        "machine_id": r.machine_id, "laptop_serial_no": r.laptop_serial_no,
        "laptop_name": r.laptop_name, "operator_id": r.operator_id,
        "operator_name": r.operator_name_raw, "operator_code": r.operator_code_raw,
        "operator_mobile": r.operator_mobile_raw,
        "security_deposit_status": r.security_deposit_status,
        "security_deposit_date": d(r.security_deposit_date),
        "l1_status": r.l1_status, "l1_date": d(r.l1_date),
        "l2_status": r.l2_status, "l2_date": d(r.l2_date),
        "block": r.block, "category": r.category, "locality": r.locality,
        "ask_address": r.ask_address, "operator_status": r.operator_status,
        "inactive_reason": r.inactive_reason, "inactive_date": d(r.inactive_date),
        "permit_18_plus": r.permit_18_plus, "station_status": r.station_status,
        "onboarding_status": r.onboarding_status, "onboard_date": d(r.onboard_date),
        "kit_working": r.kit_working, "visit_status": r.visit_status,
        "visit_date": d(r.visit_date), "remark": r.remark,
    } for r in rows]
    return {"rows": out, "pagination": {"page": page, "pageSize": pageSize, "total": total,
            "pages": (total + pageSize - 1) // pageSize}}
