# backend/services/kit_tracker_ingest.py
"""Ingest the operational 'Kit Tracker.xlsx' into the kit_tracker table.

Free-text District/Operator values are resolved to IDs (district_table,
operators) where a match exists; the raw values are always retained. Rows are
upserted on station_id so re-uploading the sheet refreshes rather than dupes.
"""
from __future__ import annotations

import os
import time
import traceback
from datetime import date, datetime
from difflib import get_close_matches

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.district import District
from backend.models.operator import Operator
from backend.models.kit_tracker import KitTracker
from backend.models.operator_daily_activity import ActivityUploadBatch
from backend.services import activity_config as cfg

# Kit Tracker header -> our field name.
COLUMN_MAP = {
    "SR No.": "sr_no", "District": "_district", "Kit Slot": "kit_slot",
    "Station ID": "station_id", "Station ID  Allotted Date": "station_id_allotted_date",
    "Machine ID": "machine_id", "Laptop Serial No.": "laptop_serial_no",
    "Laptop Name": "laptop_name", "Operator Name": "operator_name_raw",
    "Operator Id": "operator_code_raw", "Operator Mobile": "operator_mobile_raw",
    "Security Deposit Status": "security_deposit_status", "Security Deposit Date": "security_deposit_date",
    "L1 Status": "l1_status", "L1 Date": "l1_date", "L2 Status": "l2_status", "L2 Date": "l2_date",
    "Block": "block", "Category": "category", "Locality": "locality", "ASK Address": "ask_address",
    "Operator Status": "operator_status", "Inactive Reason": "inactive_reason",
    "Inactive Date": "inactive_date", "18+ Permit": "_permit_18_plus",
    "Station Status": "station_status", "Onboarding Status": "onboarding_status",
    "Onboard Date": "onboard_date", "Kit Working": "_kit_working",
    "Visit Status": "visit_status", "Visit Date": "visit_date", "Remark": "remark",
}
DATE_FIELDS = {"station_id_allotted_date", "security_deposit_date", "l1_date", "l2_date",
               "inactive_date", "onboard_date", "visit_date"}


def _norm(s: str) -> str:
    return "".join(str(s).split()).lower()


def _parse_date(val):
    if val in (None, "", "None"):
        return None
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _yes_no(val):
    if val in (None, "", "None"):
        return None
    return 1 if str(val).strip().lower() in ("yes", "y", "true", "1") else 0


def _clean(val):
    if val in (None, "", "None"):
        return None
    return str(val).strip()


def _build_district_index(db: Session) -> dict[str, str]:
    idx = {}
    for d in db.query(District).all():
        idx[_norm(d.district_name)] = d.district_code
        if d.district_short_name:
            idx[_norm(d.district_short_name)] = d.district_code
    return idx


def _resolve_district(name, idx, name_keys) -> str | None:
    if not name:
        return None
    key = _norm(name)
    if key in idx:
        return idx[key]
    match = get_close_matches(key, name_keys, n=1, cutoff=0.85)
    return idx[match[0]] if match else None


def process_kit_tracker_upload(batch_id: str, file_path: str) -> None:
    import openpyxl
    started = time.time()
    db = SessionLocal()
    try:
        _set_batch(db, batch_id, status="validating", stage="Validating columns", progress=10)

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        rows = ws.iter_rows(values_only=True)

        # First non-empty row before the header is a title ('Kit Tracker'); the
        # header is the row containing 'Station ID'.
        header = None
        for r in rows:
            if r and any(_norm(c or "") == "stationid" for c in r):
                header = list(r)
                break
        if header is None:
            raise ValueError("Could not locate the Kit Tracker header row (no 'Station ID' column).")

        norm_map = {_norm(k): v for k, v in COLUMN_MAP.items()}
        col_field = {}
        for i, h in enumerate(header):
            field = norm_map.get(_norm(h or ""))
            if field:
                col_field[i] = field
        if not any(f == "station_id" for f in col_field.values()):
            raise ValueError("Required column 'Station ID' missing from Kit Tracker sheet.")

        district_idx = _build_district_index(db)
        name_keys = list(district_idx.keys())
        operator_by_code = {
            _norm(o.user_code): o.id for o in db.query(Operator).all() if o.user_code
        }

        _set_batch(db, batch_id, status="aggregating", stage="Transforming rows", progress=45)

        payload = []
        seen_stations = set()
        rows_read = 0
        for r in rows:
            if not r or all(c in (None, "") for c in r):
                continue
            rows_read += 1
            rec = {}
            district_name = None
            for i, field in col_field.items():
                val = r[i] if i < len(r) else None
                if field == "_district":
                    district_name = _clean(val)
                elif field == "_permit_18_plus":
                    rec["permit_18_plus"] = _yes_no(val)
                elif field == "_kit_working":
                    rec["kit_working"] = _yes_no(val)
                elif field in DATE_FIELDS:
                    rec[field] = _parse_date(val)
                elif field == "sr_no":
                    try:
                        rec["sr_no"] = int(val) if val not in (None, "") else None
                    except (TypeError, ValueError):
                        rec["sr_no"] = None
                else:
                    rec[field] = _clean(val)

            station_id = rec.get("station_id")
            if not station_id or station_id in seen_stations:
                continue
            seen_stations.add(station_id)

            rec["district_code"] = _resolve_district(district_name, district_idx, name_keys)
            rec["operator_id"] = operator_by_code.get(_norm(rec.get("operator_code_raw") or ""))
            rec["batch_id"] = batch_id
            rec["created_at"] = _ist()
            rec["updated_at"] = _ist()
            payload.append(rec)

        _set_batch(db, batch_id, status="writing", stage="Writing to DB", progress=75)
        inserted, updated = _upsert(db, payload)

        _set_batch(
            db, batch_id, status="done", stage="Done", progress=100,
            rows_read=rows_read, rows_after_filter=len(payload),
            rows_written=inserted + updated, rows_inserted=inserted, rows_updated=updated,
            rejected_count=0, processing_ms=int((time.time() - started) * 1000),
        )
    except Exception as e:
        _set_batch(db, batch_id, status="failed", stage="Error",
                   error_detail=(str(e) + "\n" + traceback.format_exc())[-4000:])
    finally:
        db.close()
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass


def _ist():
    from backend.models.base import get_ist_now
    return get_ist_now()


def _set_batch(db: Session, batch_id: str, **fields) -> None:
    db.query(ActivityUploadBatch).filter_by(batch_id=batch_id).update(fields)
    db.commit()


_KIT_CHUNK = 500


def _upsert(db: Session, payload: list[dict]) -> tuple[int, int]:
    inserted = 0
    total = 0
    update_fields = [c.name for c in KitTracker.__table__.columns
                     if c.name not in ("id", "station_id", "created_at")]
    for i in range(0, len(payload), _KIT_CHUNK):
        chunk = payload[i:i + _KIT_CHUNK]
        stmt = pg_insert(KitTracker.__table__).values(chunk)
        set_ = {f: getattr(stmt.excluded, f) for f in update_fields}
        stmt = stmt.on_conflict_do_update(index_elements=["station_id"], set_=set_)
        from sqlalchemy import text
        stmt = stmt.returning(text("(xmax = 0) AS inserted"))
        for (was_insert,) in db.execute(stmt):
            total += 1
            if was_insert:
                inserted += 1
        db.commit()
    return inserted, total - inserted
