"""One-time backfill of Station IDs for existing requests.

For each district independently:
  1. Select all requests that are ALLOTTED or SENT_TO_CHIPS ("under process").
  2. Order them strictly by submitted_at ASC, with the primary key (id) ASC as a
     deterministic tie-breaker for equal timestamps.
  3. Walk the ordered list applying the core allocation rule -- the earliest
     request gets the district's current start_station_id, the next gets +1, and
     so on -- overwriting any existing station_id_inserted.
  4. The district's start_station_id counter ends at (last assigned ID + 1) so
     future requests continue seamlessly.

Each district is processed in its own transaction, and the whole thing is
idempotent: re-running it re-derives every ID from the (advanced) counter using
the same atomic allocation primitive, so it can never double-assign across runs.
Because allocation always advances the counter, re-running assigns a fresh block
each time -- see the idempotency note below.

Which statuses count as "allotted or under process" is defined once in
BACKFILL_STATUS_IDS; adjust there if the business mapping changes.
"""
import sys

from sqlalchemy import text

from backend.database import SessionLocal
from backend.models.base import StatusEnum
from backend.models.station_id import StationIDRequest
from backend.services.station_id_allocation import (
    allocate_station_ids,
    MissingStationMasterError,
)

# "allotted" = ALLOTTED; "under process" = SENT_TO_CHIPS (sent to CHIPS, being
# handled). New/pending-review (PENDING, REAPPLIED) and REVERTED are excluded.
BACKFILL_STATUS_IDS = [StatusEnum.ALLOTTED.value, StatusEnum.SENT_TO_CHIPS.value]


def _district_codes(db):
    rows = db.execute(
        text("SELECT district_code FROM station_id_master ORDER BY district_code")
    ).all()
    return [r.district_code for r in rows]


def backfill_district(db, district_code: str) -> int:
    """Backfill one district in its own transaction.

    Returns the number of requests assigned (0 if nothing to do or already
    backfilled). Idempotent: if the district's targeted requests already hold
    the exact consecutive block ending at (counter - 1) -- i.e. a previous run
    finished this district -- it makes no changes and leaves the counter alone.
    """
    # Lock the master counter first so a concurrent allocation cannot interleave
    # with our read of it or with the request rewrite below.
    counter_row = db.execute(
        text(
            "SELECT start_station_id FROM station_id_master "
            "WHERE district_code = :dc FOR UPDATE"
        ),
        {"dc": str(district_code)},
    ).first()
    if counter_row is None:
        raise MissingStationMasterError(
            f"No station_id_master row for district_code={district_code!r}; "
            "cannot allocate a Station ID."
        )
    current_counter = int(counter_row.start_station_id)

    # Lock the district's request rows we are about to rewrite.
    requests = (
        db.query(StationIDRequest)
        .filter(
            StationIDRequest.district_id == str(district_code),
            StationIDRequest.status_id.in_(BACKFILL_STATUS_IDS),
        )
        .order_by(
            StationIDRequest.submitted_at.asc(),
            StationIDRequest.id.asc(),
        )
        .with_for_update()
        .all()
    )

    if not requests:
        # District with a master row but no pending requests: counter untouched.
        db.rollback()
        return 0

    # Idempotency guard: if these requests already hold the consecutive block
    # [counter - N, ..., counter - 1], a previous run finished this district.
    n = len(requests)
    expected = [str(current_counter - n + i) for i in range(n)]
    if [r.station_id_inserted for r in requests] == expected:
        db.rollback()
        return 0

    # One atomic reservation of the exact block we need; advances the counter to
    # (last assigned + 1) in the same statement.
    ids = allocate_station_ids(db, district_code, count=n)
    for req, new_id in zip(requests, ids):
        req.station_id_inserted = str(new_id)

    db.commit()
    return n


def run():
    db = SessionLocal()
    try:
        codes = _district_codes(db)
    finally:
        db.close()

    total = 0
    touched = 0
    for code in codes:
        db = SessionLocal()
        try:
            n = backfill_district(db, code)
            if n:
                touched += 1
                total += n
                print(f"  district {code}: assigned {n} Station ID(s)")
        except MissingStationMasterError as e:
            db.rollback()
            print(f"ERROR: {e}", file=sys.stderr)
            raise
        except Exception:
            db.rollback()
            print(f"ERROR while backfilling district {code}", file=sys.stderr)
            raise
        finally:
            db.close()

    print(f"Done. districts touched={touched}, total requests assigned={total}")


if __name__ == "__main__":
    run()
