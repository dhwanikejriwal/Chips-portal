"""Cascade the backfilled ALLOTTED Station ID renumbering into dependent tables.

The one-time backfill overwrote ``station_id_requests.station_id_inserted`` for
ALLOTTED requests (old ``STA####`` -> new sequential numeric IDs) but left the
tables that reference the ID *string* untouched, breaking the linkage:

  * kit_registration_table   -> station_id, request_no
  * l1_registration_requests -> station_id
  * l2_registration_requests -> new_station_id

This script rebuilds the old->new mapping (the old value survives in
kit_registration_table.request_no / .station_id, keyed to the request via the
request_no base) and applies it across all three tables in one transaction.

Bijection: within each request_no base, old and new IDs are paired in sorted
order. Batch allotments share a request_no across identical sibling requests, so
any within-batch pairing is equally correct; sorting makes it deterministic and
makes a re-run a true no-op (old == new for every pair).
"""
from collections import defaultdict

from sqlalchemy import text

from backend.database import SessionLocal
from backend.models.base import StatusEnum


def build_mapping(db):
    """Return {old_sid: new_sid} and {kit_id: (new_sid, new_request_no)}."""
    A = StatusEnum.ALLOTTED.value

    kits = db.execute(
        text("SELECT id, request_no, station_id FROM kit_registration_table")
    ).fetchall()
    kit_by_base = defaultdict(list)
    for k in kits:
        suffix = "-" + (k.station_id or "")
        if not (k.request_no and k.station_id and k.request_no.endswith(suffix)):
            raise ValueError(
                f"kit row {k.id} request_no={k.request_no!r} does not match "
                f"'<base>-<station_id>' format; cannot map safely."
            )
        base = k.request_no[: -len(suffix)]
        kit_by_base[base].append((k.id, k.station_id))

    reqs = db.execute(
        text(
            "SELECT request_no, station_id_inserted FROM station_id_requests "
            f"WHERE status_id={A} AND station_id_inserted IS NOT NULL"
        )
    ).fetchall()
    req_by_base = defaultdict(list)
    for r in reqs:
        req_by_base[r.request_no].append(r.station_id_inserted)

    old_to_new = {}
    kit_updates = {}  # kit_id -> (new_sid, new_request_no)
    for base in set(kit_by_base) | set(req_by_base):
        kit_rows = sorted(kit_by_base.get(base, []), key=lambda t: t[1])
        new_ids = sorted(req_by_base.get(base, []))
        if len(kit_rows) != len(new_ids):
            raise ValueError(
                f"count mismatch for base {base!r}: "
                f"{len(kit_rows)} kit rows vs {len(new_ids)} allotted requests."
            )
        for (kit_id, old_sid), new_sid in zip(kit_rows, new_ids):
            old_to_new[old_sid] = new_sid
            kit_updates[kit_id] = (new_sid, f"{base}-{new_sid}")
    return old_to_new, kit_updates


def run():
    db = SessionLocal()
    try:
        old_to_new, kit_updates = build_mapping(db)

        changed = {o: n for o, n in old_to_new.items() if o != n}
        if not changed:
            print("Nothing to cascade: dependent tables already consistent.")
            return

        kit_n = l1_n = l2_n = 0
        for kit_id, (new_sid, new_req_no) in kit_updates.items():
            res = db.execute(
                text(
                    "UPDATE kit_registration_table "
                    "SET station_id=:sid, request_no=:rno "
                    "WHERE id=:id AND station_id <> :sid"
                ),
                {"sid": new_sid, "rno": new_req_no, "id": kit_id},
            )
            kit_n += res.rowcount

        for old_sid, new_sid in changed.items():
            l1_n += db.execute(
                text(
                    "UPDATE l1_registration_requests SET station_id=:new "
                    "WHERE station_id=:old"
                ),
                {"new": new_sid, "old": old_sid},
            ).rowcount
            l2_n += db.execute(
                text(
                    "UPDATE l2_registration_requests SET new_station_id=:new "
                    "WHERE new_station_id=:old"
                ),
                {"new": new_sid, "old": old_sid},
            ).rowcount

        db.commit()
        print(f"Cascade complete. remapped {len(changed)} Station IDs -> "
              f"kit rows updated={kit_n}, l1 rows={l1_n}, l2 rows={l2_n}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
