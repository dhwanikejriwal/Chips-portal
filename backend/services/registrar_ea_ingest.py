# backend/services/registrar_ea_ingest.py
"""Load a transformed RegistrarEA result into Postgres and orchestrate the job.

Only aggregated rows are persisted; the uploaded file is deleted afterwards.
Writes are idempotent upserts so re-uploading the same day never double-counts.
"""
from __future__ import annotations

import csv
import os
import time
import traceback
from datetime import date

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.operator_daily_activity import (
    OperatorDailyActivity, ActivityStation, OperatorActivityMaster,
    ActivityUploadBatch, ActivityDailyUploadLog,
)
from backend.services import activity_config as cfg
from backend.services.registrar_ea_transform import (
    transform_file, TransformResult, MissingColumnsError, MEASURE_RENAME,
)
from backend.utils.district_mapper import normalize_district_name

MEASURE_COLS = list(MEASURE_RENAME.values())
FACT_KEY = ["activity_date", "station_ea_code", "session_operator_id", "station_number"]
_CHUNK = 2000


def _to_int(v) -> int:
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _set_batch(db: Session, batch_id: str, **fields) -> None:
    db.query(ActivityUploadBatch).filter_by(batch_id=batch_id).update(fields)
    db.commit()


def _upsert_facts(db: Session, fact_rows: list[dict], batch_id: str) -> tuple[int, int]:
    """Idempotent upsert into operator_daily_activity. Returns (inserted, updated)."""
    inserted = 0
    total = 0
    for i in range(0, len(fact_rows), _CHUNK):
        chunk = fact_rows[i:i + _CHUNK]
        payload = []
        for r in chunk:
            row = {
                "activity_date": r["activity_date"],
                "station_ea_code": _to_int(r["station_ea_code"]),
                "session_operator_id": r["session_operator_id"],
                "station_number": _to_int(r["station_number"]),
                "machine_district": normalize_district_name(r.get("machine_district")) if r.get("machine_district") else None,
                "batch_id": batch_id,
            }
            for m in MEASURE_COLS:
                row[m] = _to_int(r.get(m))
            payload.append(row)

        stmt = pg_insert(OperatorDailyActivity.__table__).values(payload)
        update_cols = {m: getattr(stmt.excluded, m) for m in MEASURE_COLS}
        update_cols["machine_district"] = stmt.excluded.machine_district
        update_cols["batch_id"] = stmt.excluded.batch_id
        stmt = stmt.on_conflict_do_update(
            constraint="uq_operator_daily_activity_key", set_=update_cols
        ).returning(text("(xmax = 0) AS inserted"))
        res = db.execute(stmt)
        for (was_insert,) in res:
            total += 1
            if was_insert:
                inserted += 1
        db.commit()
    return inserted, total - inserted


def _upsert_stations(db: Session, station_rows: list[dict]) -> None:
    for i in range(0, len(station_rows), _CHUNK):
        chunk = station_rows[i:i + _CHUNK]
        payload = [{
            "station_ea_code": _to_int(r["station_ea_code"]),
            "station_number": _to_int(r["station_number"]),
            "machine_address": r.get("machine_address"),
            "machine_district": normalize_district_name(r.get("machine_district")) if r.get("machine_district") else None,
            "machine_state": r.get("machine_state"),
            "machine_pincode": r.get("machine_pincode"),
            "machine_lat": r.get("machine_lat"),
            "machine_long": r.get("machine_long"),
        } for r in chunk]
        stmt = pg_insert(ActivityStation.__table__).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["station_ea_code", "station_number"],
            set_={
                "machine_address": stmt.excluded.machine_address,
                "machine_district": stmt.excluded.machine_district,
                "machine_state": stmt.excluded.machine_state,
                "machine_pincode": stmt.excluded.machine_pincode,
                "machine_lat": stmt.excluded.machine_lat,
                "machine_long": stmt.excluded.machine_long,
            },
        )
        db.execute(stmt)
        db.commit()


def _stub_operators(db: Session, fact_rows: list[dict]) -> None:
    """Auto-create a stub operator_activity_master row for any new operator."""
    seen = {r["session_operator_id"] for r in fact_rows}
    if not seen:
        return
    payload = [{"session_operator_id": sid, "operator_name": sid} for sid in seen]
    for i in range(0, len(payload), _CHUNK):
        stmt = pg_insert(OperatorActivityMaster.__table__).values(payload[i:i + _CHUNK])
        stmt = stmt.on_conflict_do_nothing(index_elements=["session_operator_id"])
        db.execute(stmt)
        db.commit()


def _write_rejected_csv(batch_id: str, rejected: list[dict]) -> str | None:
    if not rejected:
        return None
    cfg.ensure_dirs()
    path = os.path.join(cfg.REJECTED_DIR, f"rejected_{batch_id}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rejected[0].keys()))
        w.writeheader()
        w.writerows(rejected)
    return path


def _record_daily_log(db: Session, batch_id: str, result: TransformResult) -> None:
    """One row per covered date -> feeds the missing-date reminder."""
    from collections import Counter
    counts = Counter(r["activity_date"] for r in result.fact_rows)
    for d, n in counts.items():
        stmt = pg_insert(ActivityDailyUploadLog.__table__).values(
            activity_date=d, batch_id=batch_id, row_count=n
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["activity_date"],
            set_={"batch_id": stmt.excluded.batch_id, "row_count": stmt.excluded.row_count},
        )
        db.execute(stmt)
    db.commit()


def process_registrar_ea_upload(batch_id: str, file_path: str,
                                registrar_code: int, ea_code: int) -> None:
    """Background entrypoint. Transforms, upserts, records, and cleans up.

    Every failure is captured onto the batch row so the UI shows a specific
    reason rather than a generic error.
    """
    started = time.time()
    db = SessionLocal()
    try:
        _set_batch(db, batch_id, status="validating", stage="Validating columns", progress=10)

        large = os.path.getsize(file_path) > 50 * 1024 * 1024
        temp_dir = cfg.UPLOAD_TMP_DIR if large else None
        cfg.ensure_dirs()

        _set_batch(db, batch_id, status="aggregating", stage="Filtering + Aggregating", progress=45)
        result = transform_file(file_path, registrar_code, ea_code, temp_dir=temp_dir)

        _set_batch(db, batch_id, status="writing", stage="Writing to DB", progress=70)
        _upsert_stations(db, result.station_rows)
        _stub_operators(db, result.fact_rows)
        inserted, updated = _upsert_facts(db, result.fact_rows, batch_id)
        _record_daily_log(db, batch_id, result)

        rejected_path = _write_rejected_csv(batch_id, result.rejected_rows)
        elapsed_ms = int((time.time() - started) * 1000)

        _set_batch(
            db, batch_id, status="done", stage="Done", progress=100,
            rows_read=result.rows_read, rows_after_filter=result.rows_after_filter,
            rows_written=inserted + updated, rows_inserted=inserted, rows_updated=updated,
            rejected_count=len(result.rejected_rows), rejected_path=rejected_path,
            date_min=result.date_min, date_max=result.date_max,
            distinct_operators=result.distinct_operators, processing_ms=elapsed_ms,
            error_detail=_quality_note(result),
        )

        # Refresh the missing-date reminder snapshot after new data lands.
        try:
            from backend.services.missing_dates import refresh_missing_dates
            refresh_missing_dates(db)
        except Exception:
            pass
    except MissingColumnsError as e:
        _set_batch(db, batch_id, status="failed", stage="Validating columns",
                   error_detail=str(e))
    except Exception:
        _set_batch(db, batch_id, status="failed", stage="Error",
                   error_detail=traceback.format_exc()[-4000:])
    finally:
        db.close()
        # The uploaded file is discarded once processed.
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass


def _quality_note(result: TransformResult) -> str | None:
    notes = []
    if result.multi_address_stations:
        notes.append(
            f"{len(result.multi_address_stations)} station(s) map to >1 address "
            "(kept most recent)."
        )
    if result.biometric_mismatch_count:
        notes.append(
            f"{result.biometric_mismatch_count} group(s) where "
            "Total_Biometric_Updates != NON_MBU + IS_MBU."
        )
    return " ".join(notes) or None


def delete_batch(db: Session, batch_id: str) -> int:
    """Roll back a batch: delete its fact rows and the batch record."""
    deleted = db.query(OperatorDailyActivity).filter_by(batch_id=batch_id).delete()
    db.query(ActivityDailyUploadLog).filter_by(batch_id=batch_id).delete()
    db.query(ActivityUploadBatch).filter_by(batch_id=batch_id).delete()
    db.commit()
    return deleted
