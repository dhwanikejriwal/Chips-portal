"""Per-district sequential Station ID allocation.

``station_id_master.start_station_id`` is a live counter holding the NEXT
available Station ID for a district (despite its name it is not a fixed
constant). The core allocation rule is:

    read start_station_id -> assign it -> increment start_station_id by 1

This read-assign-increment must be atomic so two concurrent requests in the
same district can never receive the same ID. We achieve that with a single
``UPDATE ... RETURNING`` on the master row (Postgres takes a row-level lock
for the duration of the update), which both reserves the block of IDs and
advances the counter in one statement.

Every allocation path in the app -- the one-time backfill and each future
request -- must go through :func:`allocate_station_ids` so the counter stays
consistent.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session


class MissingStationMasterError(Exception):
    """Raised when a district has no ``station_id_master`` row.

    We fail loudly rather than silently skipping: a request in a district with
    no master counter cannot be allocated an ID safely.
    """


def allocate_station_ids(db: Session, district_code: str, count: int = 1) -> list[int]:
    """Atomically reserve ``count`` sequential Station IDs for ``district_code``.

    Returns the assigned IDs in ascending order (e.g. ``[44153, 44154]``) and
    advances the district's ``start_station_id`` counter by ``count`` in the
    same statement. Race-safe: the ``UPDATE ... RETURNING`` locks the master
    row, so concurrent callers serialise and never collide.

    The caller is responsible for writing the returned IDs onto the request
    rows and committing; this function does not commit so it can compose inside
    a larger transaction.

    Raises :class:`MissingStationMasterError` if the district has no master row.
    """
    if count < 1:
        raise ValueError("count must be >= 1")

    # Reserve the block [old_start, old_start + count) and advance the counter
    # atomically. RETURNING gives us the value *before* the increment.
    row = db.execute(
        text(
            """
            UPDATE station_id_master
               SET start_station_id = start_station_id + :count
             WHERE district_code = :district_code
         RETURNING start_station_id - :count AS first_id
            """
        ),
        {"count": count, "district_code": str(district_code)},
    ).first()

    if row is None:
        raise MissingStationMasterError(
            f"No station_id_master row for district_code={district_code!r}; "
            "cannot allocate a Station ID."
        )

    first_id = int(row.first_id)
    return list(range(first_id, first_id + count))


def allocate_station_id(db: Session, district_code: str) -> int:
    """Convenience wrapper: allocate and return a single Station ID."""
    return allocate_station_ids(db, district_code, count=1)[0]


def advance_counter_past(db: Session, district_code: str, station_ids) -> None:
    """Ensure the district counter sits past every ID in ``station_ids``.

    The counter is a high-water mark of the next available ID. Whenever IDs are
    allotted -- whether auto-allocated or entered manually by the CHIPS Admin --
    the counter must move to ``max(current, highest_allotted + 1)`` so future
    allocations and recommendations never collide with an already-used ID.
    Non-numeric values are ignored. Does not commit.
    """
    numeric = [int(s) for s in station_ids if str(s).strip().isdigit()]
    if not numeric:
        return
    db.execute(
        text(
            "UPDATE station_id_master "
            "SET start_station_id = GREATEST(start_station_id, :high) "
            "WHERE district_code = :dc"
        ),
        {"high": max(numeric) + 1, "dc": str(district_code)},
    )
