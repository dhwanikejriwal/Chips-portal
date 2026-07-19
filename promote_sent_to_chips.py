"""Retire the SENT_TO_CHIPS ("under process") station-id status.

Per product decision (2026-07-16): "under process" is no longer a distinct
category in the Station ID section.

  * SENT_TO_CHIPS requests that already hold a station_id_inserted are, in
    effect, allotted -> promote to ALLOTTED so they appear in the log history,
    stamping reviewed_at and creating their kit-registration rows (mirroring the
    normal allot flow).
  * SENT_TO_CHIPS requests without a station_id -> demote to PENDING (they are
    just awaiting review). None exist today, but handled for completeness.

Transactional and idempotent (re-running finds no SENT_TO_CHIPS rows left).
"""
from sqlalchemy import text

from backend.database import SessionLocal
from backend.models.base import StatusEnum, get_ist_now
from backend.models.station_id import StationIDRequest
from backend.routers.kit_registration import create_kit_rows_for_station_ids


def run():
    db = SessionLocal()
    try:
        S = StatusEnum.SENT_TO_CHIPS.value
        rows = db.query(StationIDRequest).filter(StationIDRequest.status_id == S).all()
        promoted = demoted = 0
        now = get_ist_now()
        for r in rows:
            sid = (r.station_id_inserted or "").strip()
            if sid:
                r.status_id = StatusEnum.ALLOTTED.value
                if r.reviewed_at is None:
                    r.reviewed_at = now
                create_kit_rows_for_station_ids(
                    db,
                    station_ids=[sid],
                    district=(r.district.district_name if r.district else None),
                    request_no=r.request_no,
                )
                promoted += 1
            else:
                r.status_id = StatusEnum.PENDING.value
                demoted += 1
        db.commit()
        remaining = db.execute(
            text(f"SELECT count(*) FROM station_id_requests WHERE status_id={S}")
        ).scalar()
        print(f"Done. promoted->ALLOTTED={promoted}, demoted->PENDING={demoted}, "
              f"SENT_TO_CHIPS remaining={remaining}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
