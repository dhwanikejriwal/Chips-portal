"""Seed realistic dummy requests into the live portal tables.

Covers every request section the portal renders:
  Registration (candidate_table) | LMS | NSEIT | Operator Activation |
  Operator Reactivation (grouped) | Station ID | L1 | L2

Request codes follow DDD-MMMMMCCCXNNNN, e.g. RPR-45073387A0001
(or DDD-KNNNN, e.g. RPR-K0038 for Kit / Station ID requests):
  DDD    district short name   (from district_table)
  MMMMM  last 5 digits of the person's mobile
  CCC    district code         (from district_table)
  X      origin: A = new candidate, C = existing CHiPS operator
  NNNN   running number, unique per district

Timestamps are IST (Asia/Kolkata, +05:30), weekdays, 09:00-18:00, spread over
the last ~90 days. Stage order is enforced: created -> forwarded ->
sent_to_uidai -> decided. Only Activation, Reactivation and L2 ever reach UIDAI.

Deterministic (fixed RNG seed) and idempotent: every code it inserts is recorded
in portal_seed_log, and a re-run deletes exactly those rows before reinserting.
Rows created by other seed scripts are left alone even though they share the
same code format.

Portable across installations -- nothing about one database is hard-coded:
  * districts are chosen from those that actually have a DC user, preferring
    PREFERRED_DISTRICTS but falling back to whatever exists;
  * candidate_table's primary key (`id` or `r_id`) is detected at run time;
  * statuses are written as names and resolved through master_status;
  * every timeline is checked to be ordered and in the past before insert.
It needs only a migrated database with district_table rows, a CHiPS admin user
(roleid=1) and at least one DC user (roleid=2). Missing prerequisites stop the
run with an explanatory message before anything is written.

Run:  python seed_portal_requests.py
      python seed_portal_requests.py --clear    (remove seeded rows, insert nothing)
"""
from __future__ import annotations

from collections import defaultdict
import random
import sys
from typing import Any
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, text

from backend.database import SessionLocal
from backend.models.base import to_code
from backend.models.candidate import Candidate
from backend.models.district import District
from backend.models.l1_registration import L1RegistrationRequest, L1RegistrationRemarkHistory
from backend.models.l2_registration import L2RegistrationRequest, L2RegistrationRemark
from backend.models.lms import LMS, LMSRemark
from backend.models.nseit import NSEITRequest, NSEITRemark
from backend.models.operator_activation import OperatorActivationRequest, OperatorActivationRemark
from backend.models.reactivation import (
    OperatorReactivationRequest,
    ReactivationOperator,
    ReactivationRemarkHistory,
)
from backend.models.hold_candidate import HoldCandidate
from backend.models.kit_registration import KitRegistration
from backend.models.operator import Operator
from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
from backend.models.operator_station_mapping import OperatorStationMapping
from backend.models.station_id import StationIDRequest, StationIDRemark
from backend.models.user_login import UserLogin
from backend.routers.kit_registration import create_kit_rows_for_station_ids

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime.now().replace(hour=17, minute=0, second=0, microsecond=0)

# Districts we would like to spread the data across. Anything unavailable on the
# target database is silently swapped for a district that does have a DC user --
# see load_districts(). Nothing here is required to exist.
PREFERRED_DISTRICTS = ["387", "378", "375", "374"]  # Raipur, Durg, Bilaspur, Bastar
MAX_DISTRICTS = 4

CHIPS_ADMIN_ROLE, DC_ROLE = 1, 2

# SCHEMA DRIFT: on the database this was written against, candidate_table's
# primary key is `r_id`, while backend/models/candidate.py declares it as `id`
# (and declares a candidate_document_table that does not exist). The Candidate
# ORM model therefore cannot be used, so Registration/LMS/NSEIT are seeded with
# raw SQL. detect_candidate_pk() resolves the real column name at run time, so
# this works on installations where the model and schema do agree.
CANDIDATE_PK = "r_id"  # overwritten by detect_candidate_pk()

# Rows this script owns are recorded here, so a re-run removes exactly what it
# created. Matching on the code pattern alone is NOT safe: other seed scripts
# (seed_operator_activation_raipur.py) emit the same DDD-MMMMMCCCXNNNN format,
# and pattern-based cleanup would delete their rows too.
SEED_LOG_DDL = """
CREATE TABLE IF NOT EXISTS portal_seed_log (
    id           BIGSERIAL PRIMARY KEY,
    table_name   TEXT NOT NULL,
    request_code TEXT NOT NULL,
    seeded_at    TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (table_name, request_code)
)
"""

rng = random.Random(20260806)

FIRST = [
    "Rajesh", "Priya", "Suresh", "Anita", "Vikas", "Meena", "Dinesh", "Kavita",
    "Manoj", "Sunita", "Rakesh", "Poonam", "Yogesh", "Neha", "Ashok", "Rekha",
    "Deepak", "Shalini", "Hemant", "Jyoti", "Nitin", "Sarita", "Pramod", "Bhavna",
    "Girish", "Tarun", "Lata", "Umesh", "Sanjay", "Archana", "Mukesh", "Seema",
    "Ravi", "Pooja", "Ganesh", "Nisha", "Alok", "Divya", "Harish", "Komal",
    "Prakash", "Ritu", "Naresh", "Swati", "Chandan", "Mamta", "Rohit", "Anjali",
    "Vinod", "Kiran", "Sudhir", "Renu", "Amit", "Geeta", "Bharat", "Usha",
]
LAST = [
    "Sahu", "Verma", "Nirmalkar", "Dewangan", "Yadav", "Patel", "Sinha", "Tandon",
    "Chandrakar", "Baghel", "Kashyap", "Markam", "Netam", "Thakur", "Sonkar",
    "Bhoi", "Jaiswal", "Pandey", "Rathore", "Gupta", "Diwan", "Sahis",
]
QUALIFICATIONS = ["Graduate", "Post Graduate", "Higher Secondary (12th)", "Diploma", "B.Sc"]

REVERT_REASONS = [
    "Marksheet scan unreadable, please re-upload.",
    "Name mismatch between Aadhaar and certificate.",
    "Mobile number not linked to the submitted Aadhaar.",
    "Photograph does not meet size/clarity norms.",
    "Supervisor certificate expired, attach the current one.",
]
UIDAI_REJECTS = [
    "Rejected by UIDAI: operator already active under another EA.",
    "Rejected by UIDAI: biometric authentication failed.",
    "Rejected by UIDAI: certificate validity lapsed before submission.",
    "Rejected by UIDAI: device model not on the certified list.",
]

_used_names: set[str] = set()
_used_mobiles: set[str] = set()
_counters: dict[str, int] = {}


def person() -> tuple[str, str]:
    while True:
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if name not in _used_names:
            _used_names.add(name)
            break
    while True:
        mobile = rng.choice(["94", "96", "98", "70", "77", "88"]) + "".join(
            str(rng.randint(0, 9)) for _ in range(8)
        )
        if mobile[-5:] not in _used_mobiles:
            _used_mobiles.add(mobile[-5:])
            break
    return name, mobile


_issued: list[tuple[str, str]] = []  # (table_name, request_code) for the seed log

# Districts are handed out round-robin, not at random, so every bucket lands in
# every district. Random choice left some districts with empty tabs, which reads
# as "the section is broken" when you log in as that DC.
_rr: dict[str, int] = {}


def next_district(districts, key: str):
    i = _rr.get(key, 0)
    _rr[key] = i + 1
    return districts[i % len(districts)]


def make_code(short: str, code: str, mobile: str, origin: str, table: str | None = None) -> str:
    n = _counters.get(short, 0) + 1
    _counters[short] = n
    rc = f"{short}-{mobile[-5:]}{code}{origin}{n:04d}"
    if table:
        _issued.append((table, rc))
    return rc


def make_kit_code(short: str, table: str | None = None) -> str:
    key = f"KIT_{short}"
    n = _counters.get(key, 0) + 1
    _counters[key] = n
    rc = f"{short}-K{n:04d}"
    if table:
        _issued.append((table, rc))
    return rc


_allotted_stations: list[dict[str, str]] = []
_approved_l1_stations: list[dict[str, str]] = []
_used_l1_codes: set[str] = set()
_used_l2_codes: set[str] = set()
_used_l2_sids: set[str] = set()


_used_l2_request_nos: set[str] = set()
_l2_assigned_counts: dict[str, int] = defaultdict(int)


def get_done_l1_station(dcode: str, short: str) -> tuple[str, str, str]:
    """Return (station_req_no, station_id, combined_code) from approved L1 registrations.
    Limits to 2 assignments per district so remaining approved L1 stations stay in Awaiting L2.
    """
    if _l2_assigned_counts[dcode] < 2:
        matching = [item for item in _approved_l1_stations if item["dcode"] == dcode and item["station_id"] not in _used_l2_sids]
        if matching:
            item = matching[0]
            sid = item["station_id"]
            req_code = item["request_code"]
            if req_code not in _used_l2_request_nos:
                _used_l2_sids.add(sid)
                _used_l2_request_nos.add(req_code)
                _l2_assigned_counts[dcode] += 1
                req_no = req_code.replace(sid, "") if sid in req_code else f"{short}-K0001"
                return req_no, sid, req_code

    return get_allotted_station(dcode, short, kind="l2_unlinked")


def get_allotted_station(dcode: str, short: str, kind: str = "l1") -> tuple[str, str, str]:
    """Return (station_req_no, station_id, combined_code) directly from the allotted station pool."""
    approved_l1_sids = {item["station_id"] for item in _approved_l1_stations} if kind == "l2_unlinked" else set()

    matching = [item for item in _allotted_stations if item["dcode"] == dcode and item["station_id"] not in approved_l1_sids]
    if not matching:
        matching = [item for item in _allotted_stations if item["station_id"] not in approved_l1_sids]
    if not matching:
        matching = _allotted_stations

    used_set = _used_l1_codes if kind == "l1" else _used_l2_request_nos

    if matching:
        for item in matching:
            req_no, sid = item["request_no"], item["station_id"]
            code = f"{req_no}{sid}"
            if code not in used_set:
                used_set.add(code)
                return req_no, sid, code

        # Cycle over matching allotted station IDs with a unique request_no
        item = rng.choice(matching)
        sid = item["station_id"]
        while True:
            unique_req = make_kit_code(short)
            code = f"{unique_req}{sid}"
            if code not in used_set:
                used_set.add(code)
                return unique_req, sid, code

    dummy_req = make_kit_code(short)
    sid = "10001"
    return dummy_req, sid, f"{dummy_req}{sid}"


# ------------------------------------------------------------------ timestamps
def business(dt: datetime) -> datetime:
    while dt.weekday() >= 5:  # Sat/Sun -> roll to Monday
        dt += timedelta(days=1)
        dt = dt.replace(hour=rng.randint(9, 16))
    if dt.hour < 9 or dt.hour >= 18:
        dt = dt.replace(hour=rng.randint(9, 17))
    return dt.replace(minute=rng.choice([5, 12, 20, 27, 35, 41, 48, 55]), second=0, microsecond=0)


def created(lo_days: int, hi_days: int) -> datetime:
    return business(NOW - timedelta(days=rng.randint(lo_days, hi_days), hours=rng.randint(0, 8)))


def plus(dt: datetime, lo_h: int, hi_h: int) -> datetime:
    """Next stage, snapped to business hours and never earlier than `dt`."""
    nxt = business(dt + timedelta(hours=rng.randint(lo_h, hi_h)))
    while nxt <= dt:
        nxt = business(nxt + timedelta(days=1))
    return nxt


SUBMIT_TO_FORWARD = (3, 48)     # candidate -> DC forwards: hours to ~2 days
FORWARD_TO_UIDAI = (24, 72)     # DC -> CHiPS hands to UIDAI: 1-3 days
UIDAI_DECISION = (72, 240)      # UIDAI offline batch: 3-10 days (biggest gap)
CHIPS_DECISION = (2, 48)        # CHiPS-only decision: same day to ~2 days

def business_back(dt: datetime) -> datetime:
    """Like business(), but rolls weekends BACKWARD to the previous Friday.

    business() rolls forward, so using it while walking a timeline backwards
    never converges -- a Saturday becomes the following Monday, which is later
    than where we started.
    """
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
        dt = dt.replace(hour=rng.randint(10, 17))
    if dt.hour < 9 or dt.hour >= 18:
        dt = dt.replace(hour=rng.randint(9, 17))
    return dt.replace(minute=rng.choice([5, 12, 20, 27, 35, 41, 48, 55]), second=0, microsecond=0)


def minus(dt: datetime, lo_h: int, hi_h: int) -> datetime:
    """Previous stage: `dt` minus a gap, snapped to business hours, always earlier."""
    prv = business_back(dt - timedelta(hours=rng.randint(lo_h, hi_h)))
    while prv >= dt:
        prv = business_back(prv - timedelta(days=1))
    return prv


def uidai_cycle(i: int, n: int):
    """Timestamps for one decided (approved/rejected) request, strictly within the last ~20 days."""
    d = created(1, 5) if i < 2 else created(4, 12)
    s = minus(d, 12, 36)
    f = minus(s, 6, 24)
    c = minus(f, 3, 18)
    return c, f, s, d


def chips_cycle(i: int, n: int):
    """Timestamps for a request CHiPS decides itself (no UIDAI leg), strictly in the past."""
    d = created(1, 4)
    c = minus(d, 2, 48)
    return c, d


_horizon = datetime.now()


def check_timeline(label: str, *stamps: datetime | None) -> None:
    """Guard: stages move forward and nothing is dated in the future."""
    seen = [s for s in stamps if s is not None]
    if seen != sorted(seen):
        raise SystemExit(f"{label}: stage timestamps out of order -> {seen}")
    if seen and seen[-1] > _horizon:
        raise SystemExit(f"{label}: timestamp in the future -> {seen[-1]}")


def ist(dt: datetime) -> datetime:
    return dt.replace(tzinfo=IST)


# ----------------------------------------------------------------- DB helpers
def load_districts(db) -> tuple[list[tuple[str, str]], dict[str, int]]:
    """Pick districts to seed, and the DC user that owns each.

    Every request row needs a real DC user, so only districts that actually have
    one (roleid=DC_ROLE) are usable. PREFERRED_DISTRICTS is a wish list, not a
    requirement: whichever of them qualify are used, and if fewer than two do,
    any other qualifying districts fill the gap. This is what lets the script run
    on a database that was set up independently of this one.
    """
    dc_by_district: dict[str, int] = {}
    for uid, dist in db.execute(
        select(UserLogin.id, UserLogin.district_id)
        .where(UserLogin.roleid == DC_ROLE, UserLogin.district_id.is_not(None))
        .order_by(UserLogin.id)
    ).all():
        dc_by_district.setdefault(str(dist), uid)

    if not dc_by_district:
        raise SystemExit(
            f"no DC users (roleid={DC_ROLE}) with a district in user_login_table -- "
            "seed the districts and their DC logins first"
        )

    names = {
        str(code): short
        for short, code in db.execute(
            select(District.district_short_name, District.district_code)
        ).all()
    }

    chosen = [c for c in PREFERRED_DISTRICTS if c in dc_by_district and c in names]
    if len(chosen) < 2:
        extra = sorted(c for c in dc_by_district if c in names and c not in chosen)
        chosen += extra[: MAX_DISTRICTS - len(chosen)]
    chosen = chosen[:MAX_DISTRICTS]

    if not chosen:
        raise SystemExit("no district has both a district_table row and a DC user")

    return [(names[c], c) for c in chosen], {c: dc_by_district[c] for c in chosen}


def load_admin(db) -> int:
    admin = db.scalar(
        select(UserLogin.id).where(UserLogin.roleid == CHIPS_ADMIN_ROLE).order_by(UserLogin.id)
    )
    if admin is None:
        raise SystemExit(f"no CHiPS admin user (roleid={CHIPS_ADMIN_ROLE}) found")
    return admin


def detect_candidate_pk(db) -> str:
    """Return candidate_table's primary key column name.

    This database calls it `r_id` while backend/models/candidate.py declares
    `id`; other installations may match the model. Detecting it keeps the script
    portable instead of pinning one spelling.
    """
    global CANDIDATE_PK
    cols = {r[0] for r in db.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'candidate_table'"
    )).all()}
    if not cols:
        raise SystemExit("candidate_table does not exist -- run the migrations first")
    for candidate in ("r_id", "id"):
        if candidate in cols:
            CANDIDATE_PK = candidate
            return candidate
    raise SystemExit(f"candidate_table has neither 'r_id' nor 'id'; columns are {sorted(cols)}")


def owned(db, table: str) -> list[str]:
    """Request codes this script previously inserted into `table`."""
    return [r[0] for r in db.execute(
        text("SELECT request_code FROM portal_seed_log WHERE table_name = :t"), {"t": table}
    ).all()]


def clear(db) -> None:
    """Remove only the rows this script created, children first.

    Scoped by portal_seed_log, never by code pattern -- other seed scripts use
    the same code format and their rows must survive.
    """
    db.execute(text(SEED_LOG_DDL))

    codes = owned(db, "candidate_table")
    if codes:
        # candidate_table is addressed by raw SQL -- see the note on CANDIDATE_PK.
        for remark_tbl, req_tbl in (("lms_remark_table", '"LMS_table"'),
                                    ("nseit_request_remark_table", "nseit_request_table")):
            db.execute(text(f"""
                DELETE FROM {remark_tbl} WHERE request_id IN (
                    SELECT q.id FROM {req_tbl} q JOIN candidate_table c
                        ON q.request_id = c.{CANDIDATE_PK}
                    WHERE c.request_code = ANY(:codes))
            """), {"codes": codes})
        for req_tbl in ('"LMS_table"', "nseit_request_table"):
            db.execute(text(f"""
                DELETE FROM {req_tbl} WHERE request_id IN (
                    SELECT {CANDIDATE_PK} FROM candidate_table WHERE request_code = ANY(:codes))
            """), {"codes": codes})
        db.execute(text("DELETE FROM candidate_table WHERE request_code = ANY(:codes)"),
                   {"codes": codes})

    # These parents cascade to their remark/operator children.
    for model, col, tname in (
        (OperatorActivationRequest, OperatorActivationRequest.request_no, "operator_activation_requests"),
        (OperatorReactivationRequest, OperatorReactivationRequest.request_code, "operator_reactivation_requests"),
        (StationIDRequest, StationIDRequest.request_no, "station_id_requests"),
        (L1RegistrationRequest, L1RegistrationRequest.request_code, "l1_registration_requests"),
        (L2RegistrationRequest, L2RegistrationRequest.request_no, "l2_registration_requests"),
        (Operator, Operator.user_code, "operators"),
        (HoldCandidate, HoldCandidate.request_code, "hold_candidate_tb"),
        (KitRegistration, KitRegistration.request_no, "kit_registration_table"),
    ):
        codes = owned(db, tname)
        if codes:
            for obj in db.scalars(select(model).where(col.in_(codes))).all():
                db.delete(obj)

    db.execute(text("DELETE FROM portal_seed_log"))
    db.flush()

    # Reset PostgreSQL sequence counters for cleared tables using savepoints
    seq_tables = [
        ("candidate_table", CANDIDATE_PK),
        ('"LMS_table"', "id"),
        ("lms_remark_table", "id"),
        ("nseit_request_table", "id"),
        ("nseit_request_remark_table", "id"),
        ("operator_activation_requests", "id"),
        ("operator_activation_remarks", "id"),
        ("operator_reactivation_requests", "id"),
        ("operator_reactivation_remarks", "id"),
        ("station_id_requests", "id"),
        ("l1_registration_requests", "id"),
        ("l2_registration_requests", "id"),
        ("operators", "id"),
        ("hold_candidate_tb", "id"),
        ("kit_registration_table", "id"),
    ]
    for tbl, pk_col in seq_tables:
        try:
            with db.begin_nested():
                db.execute(text(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{tbl}', '{pk_col}'),
                        COALESCE((SELECT MAX({pk_col}) FROM {tbl}), 0) + 1,
                        false
                    );
                """))
        except Exception:
            pass


def record_owned(db) -> None:
    """Log every code inserted this run so the next run can clean up precisely."""
    if _issued:
        db.execute(
            text("INSERT INTO portal_seed_log (table_name, request_code) VALUES (:t, :c)"),
            [{"t": t, "c": c} for t, c in _issued],
        )


# -------------------------------------------------------------------- sections
def insert_candidate_sql():
    """Built per call: CANDIDATE_PK is only known after detect_candidate_pk()."""
    return text(f"""
        INSERT INTO candidate_table
            (request_code, name, mobile, email, district, qualification, lms_id, nseit_id,
             dob, aadhaar, address, pincode, is_existing_operator, status_id, created_at, updated_at)
        VALUES
            (:request_code, :name, :mobile, :email, :district, :qualification, :lms_id, :nseit_id,
             :dob, :aadhaar, :address, :pincode, :is_existing_operator, :status_id, :created_at, :updated_at)
        RETURNING {CANDIDATE_PK}
    """)


def new_candidate(db, short, dcode, name, mobile, status, c, updated,
                  origin="C", lms_id=None, nseit_id=None) -> int:
    """Insert a candidate row and return its primary key."""
    return db.execute(insert_candidate_sql(), {
        "request_code": make_code(short, dcode, mobile, origin, "candidate_table"),
        "name": name, "mobile": mobile,
        "email": f"{name.split()[0].lower()}.{mobile[-4:]}@example.in",
        "district": dcode,
        "qualification": rng.choice(QUALIFICATIONS),
        "lms_id": lms_id, "nseit_id": nseit_id,
        "dob": date(rng.randint(1988, 2002), rng.randint(1, 12), rng.randint(1, 28)),
        "aadhaar": "".join(str(rng.randint(0, 9)) for _ in range(12)),
        "address": f"Ward {rng.randint(1, 40)}, {short} Nagar",
        "pincode": f"49{rng.randint(1000, 9999)}",
        "is_existing_operator": 0,
        "status_id": to_code(status),
        "created_at": c, "updated_at": updated,
    }).scalar_one()


_approved_candidates_pool: list[dict[str, Any]] = []
_lms_approved_candidates: list[dict[str, Any]] = []
_nseit_approved_candidates: list[dict[str, Any]] = []


def seed_registration(db, districts, dcs, admin, counts):
    """candidate_table. Never reaches UIDAI."""
    plan = [("Pending", 5, "pending"), ("Approved", 60, "approved"), ("Rejected", 5, "rejected")]
    for status, n, bucket in plan:
        for i in range(n):
            short, dcode = next_district(districts, bucket)
            name, mobile = person()
            if bucket == "pending":
                c, d = created(1, 15), None
            else:
                d = created(1, 4)
                c = minus(d, 2, 48)
            cand_id = new_candidate(db, short, dcode, name, mobile, status, c, d, origin="C")
            counts[f"registration/{bucket}"] += 1

            if bucket == "approved":
                _approved_candidates_pool.append({
                    "cand_id": cand_id,
                    "short": short,
                    "dcode": dcode,
                    "name": name,
                    "mobile": mobile,
                    "email": f"{name.split()[0].lower()}.{mobile[-4:]}@example.in",
                    "aadhaar": str(rng.randint(1000, 9999)),
                    "pan": f"{rng.choice('ABCDEFGH')}{rng.choice('JKLMNP')}{rng.choice('QRSTUV')}P{rng.choice('ABCDEFGH')}{rng.randint(1000, 9999)}{rng.choice('KLMN')}",
                    "pincode": f"49{rng.randint(1000, 9999)}",
                    "created_at": c,
                })


def seed_credential(db, districts, dcs, admin, counts, kind):
    """LMS / NSEIT. Sequentially linked candidate pipeline. Never reaches UIDAI."""
    Req, Remark, label = (
        (LMS, LMSRemark, "LMS login") if kind == "lms" else (NSEITRequest, NSEITRemark, "NSEIT exam")
    )
    n_appr = 35 if kind == "lms" else 20
    plan = [
        ("Pending", "pending", 4, "Credential request raised; awaiting DC scrutiny."),
        ("Forwarded", "forwarded_to_chips", 4, "Forwarded to CHiPS by DC for credential creation."),
        ("Approved", "approved", n_appr, f"{label} credentials generated and shared with the candidate."),
        ("Reverted", "reverted", 4, None),
    ]
    for status, bucket, n, note in plan:
        for _ in range(n):
            short, dcode = next_district(districts, bucket)
            if bucket == "pending":
                c, f, d = created(1, 14), None, None
            elif bucket == "forwarded_to_chips":
                f = created(1, 4)
                c = minus(f, 3, 24)
                d = None
            else:
                d = created(1, 4)
                f = minus(d, 2, 24)
                c = minus(f, 3, 24)

            issued = bucket == "approved"
            lms_code = f"LMS{rng.randint(100000, 999999)}" if (issued and kind == "lms") else None
            nseit_code = f"NSEIT{rng.randint(100000, 999999)}" if (issued and kind == "nseit") else None

            # Enforce strict sequential pipeline:
            # - LMS: Candidate MUST first be Approved in Candidate Selection (_approved_candidates_pool)
            # - NSEIT: Candidate MUST first be Approved in LMS stage (_lms_approved_candidates)
            if kind == "lms":
                if _approved_candidates_pool:
                    cand_info = _approved_candidates_pool.pop(0)
                else:
                    name, mobile = person()
                    cand_id = new_candidate(db, short, dcode, name, mobile, "Approved", c, d or f or c, origin="C")
                    cand_info = {
                        "cand_id": cand_id, "short": short, "dcode": dcode,
                        "name": name, "mobile": mobile,
                        "email": f"{name.split()[0].lower()}.{mobile[-4:]}@example.in",
                        "aadhaar": str(rng.randint(1000, 9999)),
                        "pan": f"{rng.choice('ABCDEFGH')}{rng.choice('JKLMNP')}{rng.choice('QRSTUV')}P{rng.choice('ABCDEFGH')}{rng.randint(1000, 9999)}{rng.choice('KLMN')}",
                        "pincode": f"49{rng.randint(1000, 9999)}",
                        "created_at": c,
                    }
                cand_id = cand_info["cand_id"]
                if issued:
                    db.execute(text("UPDATE candidate_table SET lms_id = :lid WHERE id = :cid"), {"lid": lms_code, "cid": cand_id})
                    cand_info["lms_id"] = lms_code
                    _lms_approved_candidates.append(cand_info)

            else:  # kind == "nseit"
                if _lms_approved_candidates:
                    cand_info = _lms_approved_candidates.pop(0)
                elif _approved_candidates_pool:
                    cand_info = _approved_candidates_pool.pop(0)
                else:
                    name, mobile = person()
                    cand_id = new_candidate(db, short, dcode, name, mobile, "Approved", c, d or f or c, origin="C", lms_id=f"LMS{rng.randint(100000, 999999)}")
                    cand_info = {
                        "cand_id": cand_id, "short": short, "dcode": dcode,
                        "name": name, "mobile": mobile,
                        "email": f"{name.split()[0].lower()}.{mobile[-4:]}@example.in",
                        "aadhaar": str(rng.randint(1000, 9999)),
                        "pan": f"{rng.choice('ABCDEFGH')}{rng.choice('JKLMNP')}{rng.choice('QRSTUV')}P{rng.choice('ABCDEFGH')}{rng.randint(1000, 9999)}{rng.choice('KLMN')}",
                        "pincode": f"49{rng.randint(1000, 9999)}",
                        "created_at": c,
                    }
                cand_id = cand_info["cand_id"]
                if issued:
                    db.execute(text("UPDATE candidate_table SET nseit_id = :nid WHERE id = :cid"), {"nid": nseit_code, "cid": cand_id})
                    cand_info["nseit_cert_no"] = f"NSEIT-{rng.randint(500000, 699999)}"
                    cand_info["nseit_cert_date"] = (d or c).date() if isinstance(d or c, datetime) else d or c
                    _nseit_approved_candidates.append(cand_info)

            req = Req(request_id=cand_id, status=status, created_at=c, updated_at=d or f)
            db.add(req)
            db.flush()

            db.add(Remark(request_id=req.id, remark="Request submitted by candidate.",
                          time=c, status_after="Pending", sender_id=None, is_public=1))
            if f:
                db.add(Remark(request_id=req.id, remark="Forwarded to CHiPS by DC.",
                              time=f, status_after="Forwarded", sender_id=dcs[dcode], is_public=1))
            if d:
                db.add(Remark(request_id=req.id, remark=note or rng.choice(REVERT_REASONS),
                              time=d, status_after=status, sender_id=admin, is_public=1))
            counts[f"{kind}/{bucket}"] += 1


def seed_activation(db, districts, dcs, admin, counts):
    """operator_activation_requests. Sequentially linked to NSEIT-passed candidates. Reaches UIDAI."""
    plan = [
        ("Pending", "pending", 5, "Activation request submitted; pending scrutiny."),
        ("Sent to UIDAI", "sent_to_uidai", 5, "Included in the UIDAI activation batch; awaiting decision."),
        ("Approved", "approved", 8, "Approved by UIDAI; operator ID activated."),
        ("Rejected", "rejected", 6, None),
        ("Reverted", "reverted", 5, None),
    ]
    for status, bucket, n, note in plan:
        for i in range(n):
            short, dcode = next_district(districts, bucket)
            f = s = d = None
            if bucket == "pending":
                c, f, s, d = created(1, 12), None, None, None
            elif bucket == "sent_to_uidai":
                s = created(1, 4)
                f = minus(s, 12, 36)
                c = minus(f, 3, 18)
                d = None
            elif bucket == "reverted":
                d = created(1, 4)
                f = minus(d, 6, 24)
                c = minus(f, 3, 18)
                s = None
            else:
                c, f, s, d = uidai_cycle(i, n)

            check_timeline(f"activation/{bucket}", c, f, s, d)

            # Sequential workflow vs Direct activation request:
            # - Origin C: Candidate followed full workflow (Selection -> LMS -> NSEIT -> Activation)
            # - Origin A: Direct activation request filled on activation page without prior workflow association
            if _nseit_approved_candidates:
                cand_info = _nseit_approved_candidates.pop(0)
                origin_code = "C"
                name = cand_info["name"]
                mobile = cand_info["mobile"]
                email = cand_info["email"]
                aadhaar_val = cand_info["aadhaar"]
                pan_val = cand_info["pan"]
                pincode_val = cand_info["pincode"]
                cert_no = cand_info.get("nseit_cert_no") or f"NSEIT-{rng.randint(500000, 699999)}"
                cert_date = cand_info.get("nseit_cert_date") or (c - timedelta(days=rng.randint(60, 300))).date()
            else:
                origin_code = "A"
                name, mobile = person()
                email = f"{name.split()[0].lower()}.{mobile[-4:]}@example.in"
                aadhaar_val = str(rng.randint(1000, 9999))
                pan_val = f"{rng.choice('ABCDEFGH')}{rng.choice('JKLMNP')}{rng.choice('QRSTUV')}P{rng.choice('ABCDEFGH')}{rng.randint(1000, 9999)}{rng.choice('KLMN')}"
                pincode_val = f"49{rng.randint(1000, 9999)}"
                cert_no = f"NSEIT-{rng.randint(500000, 699999)}"
                cert_date = (c - timedelta(days=rng.randint(60, 300))).date()

            mailed_val = 1 if (bucket == "pending" and i >= 3) else 0
            req = OperatorActivationRequest(
                request_no=make_code(short, dcode, mobile, origin_code, "operator_activation_requests"),
                dc_id=dcs[dcode], district_id=dcode, role="Operator",
                name_as_per_aadhaar=name,
                registrar_code="986", ea_code="2084",
                user_code=f"986_2084_{short}_{name.split()[0]}",
                nseit_certificate_number=cert_no,
                operator_mobile=mobile,
                primary_email=email,
                operator_aadhaar=aadhaar_val,
                pan_number=pan_val,
                nseit_certification_date=datetime.combine(cert_date, datetime.min.time()) if isinstance(cert_date, date) else cert_date,
                nseit_certificate_expiry_date=datetime.combine(
                    (cert_date if isinstance(cert_date, date) else cert_date.date()) + timedelta(days=1095), datetime.min.time()),
                pincode=pincode_val,
                status=status,
                is_mailed=mailed_val,
                submitted_at=c,
                reviewed_at=d or s,
            )
            db.add(req)
            db.flush()

            db.add(OperatorActivationRemark(request_id=req.id, author_id=dcs[dcode], author_role="dc",
                                            remark="Activation request submitted by DC.",
                                            status_after="Pending", created_at=c))
            if f and bucket != "pending":
                db.add(OperatorActivationRemark(request_id=req.id, author_id=dcs[dcode], author_role="dc",
                                                remark="Documents verified and forwarded to CHiPS.",
                                                status_after="Sent to CHiPS", created_at=f))
            if s:
                db.add(OperatorActivationRemark(request_id=req.id, author_id=admin, author_role="chips_admin",
                                                remark="Handed to UIDAI in the activation batch.",
                                                status_after="Sent to UIDAI", created_at=s))
            if d:
                text = note or (rng.choice(UIDAI_REJECTS) if bucket == "rejected" else rng.choice(REVERT_REASONS))
                db.add(OperatorActivationRemark(request_id=req.id, author_id=admin, author_role="chips_admin",
                                                remark=text, status_after=status, created_at=d))
            counts[f"operator_activation/{bucket}"] += 1


def seed_reactivation(db, districts, dcs, admin, counts):
    """Grouped: 9 groups of 4-8 existing operators, one parent request each. Origin C.

    Operator rows carry the status the UI filters on (PENDING / SENT_TO_UIDAI /
    APPROVED / REJECTED / REVERTED). The parent batch uses the status the router
    assigns it: REVIEWED once UIDAI has decided, not APPROVED/REJECTED
    (backend/routers/reactivation.py sets req.status_id = REVIEWED there).
    """
    # bucket -> (operator status, parent status)
    STATES = {
        "pending":       ("Pending", "Pending"),
        "sent_to_uidai": ("Sent to UIDAI", "Sent to UIDAI"),
        "approved":      ("Approved", "Reviewed"),
        "rejected":      ("Rejected", "Reviewed"),
        "reverted":      ("Reverted", "Reverted"),
    }
    plan = ["pending", "pending", "pending", "sent_to_uidai", "sent_to_uidai",
            "approved", "approved", "rejected", "reverted"]
    for gi, bucket in enumerate(plan, start=1):
        short, dcode = districts[(gi - 1) % len(districts)]
        size = rng.randint(4, 8)
        status, parent_status = STATES[bucket]

        if bucket == "pending":
            c, f, s, d = created(1 + gi, 3 + gi * 2), None, None, None
        elif bucket == "sent_to_uidai":
            s = created(1, 4)
            f = minus(s, 12, 36)
            c = minus(f, 3, 18)
            d = None
        elif bucket in ("approved", "rejected"):
            d = created(1, 4)
            s = minus(d, 12, 36)
            f = minus(s, 6, 24)
            c = minus(f, 3, 18)
        elif bucket == "reverted":
            d = created(1, 4)
            f = minus(d, 6, 24)
            c = minus(f, 3, 18)
            s = None
        training = business((s or f or c) + timedelta(days=rng.randint(2, 6))).replace(hour=10, minute=0)

        check_timeline(f"reactivation/{bucket}", c, f, s, d)

        # The parent request carries the group's own code; NNNN stays unique per district.
        _, group_mobile = person()
        parent = OperatorReactivationRequest(
            request_code=make_code(short, dcode, group_mobile, "C", "operator_reactivation_requests"),
            dc_id=dcs[dcode], district_id=dcode,
            operator_count=size, training_date=training.date(),
            status=parent_status,
            is_mailed=1 if (bucket == "pending" and gi == 2) else 0,
            created_at=ist(c), updated_at=ist(d or s or f or c),
            reviewed_by=admin if (d or s) else None,
        )
        db.add(parent)
        db.flush()

        for _ in range(size):
            name, mobile = person()
            db.add(ReactivationOperator(
                request_id=parent.id, role="Operator", operator_name=name,
                registrar_code="986", ea_code="2084",
                user_code=make_code(short, dcode, mobile, "C"),
                certificate_number=f"NSEIT-{rng.randint(500000, 699999)}",
                lms_certificate_id=f"LMS{rng.randint(100000, 999999)}",
                operator_mobile=mobile,
                email_id=f"{name.split()[0].lower()}.{mobile[-4:]}@example.in",
                aadhaar_number=str(rng.randint(1000, 9999)),
                certification_date=(c - timedelta(days=rng.randint(200, 900))).date(),
                model_type=rng.choice(["ECMP", "UCL"]),
                status=status,
                reject_reason=(rng.choice(UIDAI_REJECTS) if bucket == "rejected"
                               else rng.choice(REVERT_REASONS) if bucket == "reverted" else None),
            ))
            counts[f"operator_reactivation/{bucket}"] += 1

        db.add(ReactivationRemarkHistory(
            request_id=parent.id, sender_role="dc", author_id=dcs[dcode],
            remark_history=f"Reactivation batch of {size} operators submitted. "
                           f"Training slot: {training:%d-%b-%Y %H:%M}.",
            status_after="Pending", timestamp=ist(c)))
        if s:
            db.add(ReactivationRemarkHistory(
                request_id=parent.id, sender_role="chips_admin", author_id=admin,
                remark_history="Group forwarded to UIDAI in the reactivation batch.",
                status_after="Sent to UIDAI", timestamp=ist(s)))
        if d:
            closing = {
                "approved": "Reactivation approved by UIDAI for the full group.",
                "rejected": rng.choice(UIDAI_REJECTS),
                "reverted": rng.choice(REVERT_REASONS),
            }[bucket]
            db.add(ReactivationRemarkHistory(
                request_id=parent.id, sender_role="chips_admin", author_id=admin,
                remark_history=closing, status_after=status, timestamp=ist(d)))
        counts[f"__reactivation_groups"] += 1


def seed_station_id(db, districts, dcs, admin, counts):
    """station_id_requests -- a DC batch request for kits, not a per-person one. Stops at CHiPS."""
    # The portal's Station ID tabs are PENDING/REAPPLIED, ALLOTTED and REVERTED
    # (app/templates/station_id/chips_list.html). It has no separate rejected
    # state -- CHiPS reverts rather than rejects -- so "reverted/rejected" is
    # filled with REVERTED rows.
    plan = [
        ("Pending", "pending", 5, "Station ID requested; awaiting allotment from the CHiPS pool."),
        ("Allotted", "allotted", 16, "Station IDs allotted from the district quota."),
        ("Reverted", "reverted", 6, None),
    ]
    for status, bucket, n, note in plan:
        for i in range(n):
            short, dcode = next_district(districts, bucket)
            _, mobile = person()
            if bucket == "pending":
                c, d = created(1, 14), None
            else:
                c, d = chips_cycle(i, n)
            check_timeline(f"station_id/{bucket}", c, d)
            kits = rng.randint(2, 12)
            station_list = [str(rng.randint(10000, 99999)) for _ in range(kits)] if bucket == "allotted" else []
            req = StationIDRequest(
                request_no=make_kit_code(short, "station_id_requests"),
                dc_id=dcs[dcode], district_id=dcode,
                model=rng.choice(["ECMP", "UCL"]),
                user_type=rng.choice(["new_user", "machine_id"]),
                number_of_kits=1 if bucket == "allotted" else kits,
                slot=rng.choice(["937 slot", "300 slot"]),
                status=status,
                station_id_inserted=station_list[0] if station_list else None,
                submitted_at=c, reviewed_at=d, reviewed_by=admin if d else None,
            )
            db.add(req)
            db.flush()

            db.add(StationIDRemark(request_id=req.id, author_id=dcs[dcode], author_role="dc",
                                   remark=f"Requested {kits if bucket != 'allotted' else 1} Station ID for the district.",
                                   status_after="Pending", created_at=c))
            if d:
                db.add(StationIDRemark(
                    request_id=req.id, author_id=admin, author_role="chips_admin",
                    remark=note or "Station ID credentials successfully assigned.",
                    status_after=status, created_at=d))
            counts[f"station_id/{bucket}"] += 1

            if bucket == "allotted":
                for sid in station_list:
                    _allotted_stations.append({
                        "dcode": dcode,
                        "short": short,
                        "request_no": req.request_no,
                        "station_id": sid,
                    })

                # Create sibling rows for remaining allotted Station IDs so each Station ID has its own single row
                for extra_sid in station_list[1:]:
                    sibling = StationIDRequest(
                        request_no=req.request_no,
                        dc_id=dcs[dcode], district_id=dcode,
                        model=req.model, user_type=req.user_type,
                        number_of_kits=1,
                        slot=req.slot,
                        status=status,
                        station_id_inserted=extra_sid,
                        submitted_at=c, reviewed_at=d, reviewed_by=admin,
                    )
                    db.add(sibling)
                    db.flush()
                    db.add(StationIDRemark(request_id=sibling.id, author_id=dcs[dcode], author_role="dc",
                                           remark="Requested Station ID for the district.",
                                           status_after="Pending", created_at=c))
                    db.add(StationIDRemark(request_id=sibling.id, author_id=admin, author_role="chips_admin",
                                           remark=note or "Station ID credentials successfully assigned.",
                                           status_after=status, created_at=d))
                    counts[f"station_id/{bucket}"] += 1

                try:
                    dist_name = dict(districts).get(short, short)
                    create_kit_rows_for_station_ids(
                        db,
                        station_ids=station_list,
                        district=dist_name,
                        request_no=req.request_no,
                    )
                    _issued.append(("kit_registration_table", req.request_no))
                except Exception:
                    pass


def seed_l1(db, districts, dcs, admin, counts):
    """l1_registration_requests -- device registration. Stops at CHiPS."""
    plan = [
        ("Pending", "pending", 4, "L1 kit request pending CHiPS verification."),
        ("Approved", "approved", 32, "L1 request approved; device whitelisted at CHiPS."),
        ("Reverted", "reverted", 4, None),
    ]
    for status, bucket, n, note in plan:
        for i in range(n):
            short, dcode = next_district(districts, bucket)
            name, mobile = person()
            if bucket == "pending":
                c, d = created(1, 15), None
            else:
                c, d = chips_cycle(i, n)
            check_timeline(f"l1/{bucket}", c, d)
            _, sid, combined_code = get_allotted_station(dcode, short, kind="l1")
            _issued.append(("l1_registration_requests", combined_code))
            req = L1RegistrationRequest(
                request_code=combined_code,
                district_id=dcode,
                station_id=sid,
                machine_id=f"MC{rng.randint(100000, 999999)}",
                operator_name=name,
                operator_id=f"OP{rng.randint(10000, 99999)}",
                model_type=rng.choice(["ECMP", "UCL"]),
                software_version=rng.choice(["3.6.2", "3.7.0", "3.7.4"]),
                laptop_serial_no=f"SN{rng.randint(1000000, 9999999)}",
                laptop_brand=rng.choice(["HP", "Acer"]),
                uv_id=f"UV{rng.randint(10000, 99999)}",
                uv_password=f"Uv@{rng.randint(1000, 9999)}",
                status=status,
                dc_id=dcs[dcode],
                reviewed_by=admin if d else None,
                created_at=c, updated_at=d or c,
            )
            db.add(req)
            db.flush()
            if bucket == "approved":
                _approved_l1_stations.append({
                    "dcode": dcode,
                    "short": short,
                    "station_id": sid,
                    "request_code": req.request_code,
                })
            db.add(L1RegistrationRemarkHistory(
                request_id=req.id, remark="L1 registration submitted by DC.",
                status_after="Pending", user_role="dc", author_id=dcs[dcode], timestamp=c))
            if d:
                db.add(L1RegistrationRemarkHistory(
                    request_id=req.id,
                    remark=note or "Reverted: L1 device invoice/serial proof not attached.",
                    status_after=status, user_role="chips_admin", author_id=admin, timestamp=d))
            counts[f"l1/{bucket}"] += 1


_approved_l2_stations: list[dict[str, str]] = []


def seed_l2(db, districts, dcs, admin, counts):
    """l2_registration_requests -- device registration that reaches UIDAI."""
    plan = [
        ("Pending", "pending", 5, "L2 kit request raised by operator; under scrutiny."),
        ("Sent to UIDAI", "sent_to_uidai", 5, "L2 registration pushed to UIDAI; awaiting device approval."),
        ("Approved", "approved", 16, "L2 device approved by UIDAI and mapped to the operator."),
        ("Rejected", "rejected", 5, None),
        ("Reverted", "reverted", 5, None),
    ]
    for status, bucket, n, note in plan:
        for i in range(n):
            short, dcode = next_district(districts, bucket)
            name, mobile = person()
            f = s = d = None
            if bucket == "pending":
                c, f, s, d = created(1, 12), None, None, None
            elif bucket == "sent_to_uidai":
                s = created(1, 4)
                f = minus(s, 12, 36)
                c = minus(f, 3, 18)
                d = None
            elif bucket == "reverted":
                d = created(1, 4)
                f = minus(d, 6, 24)
                c = minus(f, 3, 18)
                s = None
            else:
                c, f, s, d = uidai_cycle(i, n)

            check_timeline(f"l2/{bucket}", c, f, s, d)
            _, sid, combined_code = get_done_l1_station(dcode, short)
            _issued.append(("l2_registration_requests", combined_code))
            mailed_val = 1 if (bucket == "pending" and i >= 3) else 0
            req = L2RegistrationRequest(
                request_no=combined_code,
                dc_id=dcs[dcode], district_id=dcode,
                client_version=rng.choice(["3.6.2", "3.7.0", "3.7.4"]),
                new_station_id=sid,
                ea_code="2084", reg_code="986",
                new_machine_id=f"MC{rng.randint(100000, 999999)}",
                client_type=rng.choice(["ECMP", "UCL"]),
                old_station_id=str(rng.randint(10000, 99999)),
                reason_for_l2_registration="Laptop replaced after hardware failure.",
                old_machine_id=f"MC{rng.randint(100000, 999999)}",
                operator_name=name,
                operator_id=f"OP{rng.randint(10000, 99999)}",
                unique_id=f"UID{rng.randint(100000, 999999)}",
                block=f"{short} Block {rng.randint(1, 6)}",
                address_of_govt_premises=f"Tehsil Office, Ward {rng.randint(1, 40)}, {short}",
                status=status,
                is_mailed=mailed_val,
                uidai_remarks=(rng.choice(UIDAI_REJECTS) if bucket == "rejected"
                               else ("Device approved." if bucket == "approved" else None)),
                submitted_at=c,
            )
            db.add(req)
            db.flush()
            if bucket == "approved":
                _approved_l2_stations.append({
                    "dcode": dcode,
                    "short": short,
                    "station_id": sid,
                    "dc_id": dcs[dcode],
                })
            db.add(L2RegistrationRemark(request_id=req.id, author_id=dcs[dcode], author_role="dc",
                                        remark="L2 registration submitted by DC.",
                                        status_after="Pending", created_at=c))
            if f and bucket != "pending":
                db.add(L2RegistrationRemark(request_id=req.id, author_id=dcs[dcode], author_role="dc",
                                            remark="Verified and forwarded to CHiPS.",
                                            status_after="Sent to CHiPS", created_at=f))
            if s:
                db.add(L2RegistrationRemark(request_id=req.id, author_id=admin, author_role="chips_admin",
                                            remark="Submitted to UIDAI for device approval.",
                                            status_after="Sent to UIDAI", created_at=s))
            if d:
                db.add(L2RegistrationRemark(
                    request_id=req.id, author_id=admin, author_role="chips_admin",
                    remark=note or (rng.choice(REVERT_REASONS) if bucket == "reverted"
                                    else rng.choice(UIDAI_REJECTS)),
                    status_after=status, created_at=d))
            counts[f"l2/{bucket}"] += 1


def seed_operator_mapping(db, districts, dcs, admin, counts):
    """Seed unmapped operators and pre-mapped operator-station records for all DC/EDM user accounts in the target districts."""
    for short, dcode in districts:
        app_l2_stations = [s["station_id"] for s in _approved_l2_stations if s["dcode"] == dcode]
        if not app_l2_stations:
            app_l2_stations = [s["station_id"] for s in _allotted_stations if s["dcode"] == dcode]

        # Use only the first 2 approved L2 station IDs for pre-mapping so the remaining stay unmapped for the Station ID dropdown
        premapped_sids = app_l2_stations[:2] if len(app_l2_stations) >= 2 else app_l2_stations

        # Find ALL DC / EDM user login IDs for this district so whichever DC/EDM account logs in sees the mappings
        dc_user_ids = db.scalars(
            select(UserLogin.id).where(
                UserLogin.district_id == dcode,
                UserLogin.roleid.in_([2, 3])
            )
        ).all()
        if not dc_user_ids and dcode in dcs:
            dc_user_ids = [dcs[dcode]]

        for dc_uid in dc_user_ids:
            # 1. Seed 2 Pre-Mapped Operators for this DC user using approved L2 station IDs (shows up in Operator Mapping table)
            for i, station_id_val in enumerate(premapped_sids):
                name, mobile = person()
                user_code = f"986_2084_{short}_MAP_U{dc_uid}_{i+1:02d}"
                _issued.append(("operators", user_code))

                cert_date = date(2023, 1, 15)
                op = Operator(
                    user_code=user_code,
                    name=name,
                    mobile=mobile,
                    email=f"{name.split()[0].lower()}.{mobile[-4:]}@example.in",
                    aadhaar_last4=str(rng.randint(1000, 9999)),
                    pan_number=f"ABCDE{rng.randint(1000, 9999)}F",
                    role="Operator",
                    registrar_code="986",
                    ea_code="2084",
                    nseit_certificate_number=f"NSEIT-{rng.randint(500000, 699999)}",
                    nseit_certification_date=datetime.combine(cert_date, datetime.min.time()),
                    nseit_certificate_expiry_date=datetime.combine(cert_date + timedelta(days=1095), datetime.min.time()),
                    pincode=f"49{rng.randint(1000, 9999)}",
                    status="Inactive",
                    mapped_dc_id=dc_uid,
                    district_id=dcode,
                )
                db.add(op)
                db.flush()

                st_mapping = OperatorStationMapping(
                    operator_id=op.id,
                    station_id=station_id_val,
                    mapped_at=NOW - timedelta(days=rng.randint(2, 20)),
                )
                db.add(st_mapping)
                db.flush()

                onboarding = OperatorOnboardingDetail(
                    mapping_id=st_mapping.id,
                    operator_id=op.id,
                    station_id=station_id_val,
                    onboarding_status="Mapped",
                    onboard_date=(NOW - timedelta(days=rng.randint(1, 15))).date(),
                    ask_kit_working_status="Working",
                    permitted_18_plus="Yes",
                    remark="Mapped and verified by DC.",
                )
                db.add(onboarding)
                counts["operator_mapping/mapped"] += 1

            # 2. Seed 3 Unmapped Operators for this DC user (shows up in DC Mapping dropdown)
            for i in range(3):
                name, mobile = person()
                user_code = f"986_2084_{short}_UNMAP_U{dc_uid}_{i+1:02d}"
                _issued.append(("operators", user_code))

                cert_date = date(2023, 5, 10)
                op = Operator(
                    user_code=user_code,
                    name=name,
                    mobile=mobile,
                    email=f"{name.split()[0].lower()}.{mobile[-4:]}@example.in",
                    aadhaar_last4=str(rng.randint(1000, 9999)),
                    pan_number=f"VWXYZ{rng.randint(1000, 9999)}K",
                    role="Operator",
                    registrar_code="986",
                    ea_code="2084",
                    nseit_certificate_number=f"NSEIT-{rng.randint(500000, 699999)}",
                    nseit_certification_date=datetime.combine(cert_date, datetime.min.time()),
                    nseit_certificate_expiry_date=datetime.combine(cert_date + timedelta(days=1095), datetime.min.time()),
                    pincode=f"49{rng.randint(1000, 9999)}",
                    status="Inactive",
                    mapped_dc_id=dc_uid,
                    district_id=dcode,
                )
                db.add(op)
                counts["operator_mapping/unmapped"] += 1


def seed_hold_candidates(db, districts, dcs, admin, counts):
    """Seed candidate records into hold_candidate_tb."""
    for short, dcode in districts:
        for i in range(2):
            name, mobile = person()
            c = created(5, 40)
            cand = HoldCandidate(
                request_code=make_code(short, dcode, mobile, "A", "hold_candidate_tb"),
                name=name,
                mobile=mobile,
                email=f"{name.split()[0].lower()}.{mobile[-4:]}@example.in",
                district=dcode,
                qualification=rng.choice(QUALIFICATIONS),
                dob=date(rng.randint(1988, 2002), rng.randint(1, 12), rng.randint(1, 28)),
                aadhaar="".join(str(rng.randint(0, 9)) for _ in range(12)),
                address=f"Ward {rng.randint(1, 40)}, {short} Nagar",
                pincode=f"49{rng.randint(1000, 9999)}",
                is_existing_operator=0,
                status_id=to_code("On Hold"),
                hold_remark="Qualification certificate under secondary verification.",
                created_at=c,
                updated_at=c,
            )
            db.add(cand)
            counts["hold_candidates/on_hold"] += 1


# ------------------------------------------------------------------------ main
def main() -> None:
    clear_only = "--clear" in sys.argv
    db = SessionLocal()
    try:
        districts, dcs = load_districts(db)
        admin = load_admin(db)
        pk = detect_candidate_pk(db)
        print("districts:  ", ", ".join(f"{s}/{c}" for s, c in districts))
        print("DC users:   ", ", ".join(f"{c}->{u}" for c, u in sorted(dcs.items())))
        print(f"CHiPS admin: {admin}    candidate_table PK: {pk}")

        clear(db)
        if clear_only:
            db.commit()
            print("cleared previously seeded rows; nothing inserted")
            return

        from collections import defaultdict
        counts: dict[str, int] = defaultdict(int)

        seed_registration(db, districts, dcs, admin, counts)
        seed_credential(db, districts, dcs, admin, counts, "lms")
        seed_credential(db, districts, dcs, admin, counts, "nseit")
        seed_activation(db, districts, dcs, admin, counts)
        seed_reactivation(db, districts, dcs, admin, counts)
        seed_station_id(db, districts, dcs, admin, counts)
        seed_l1(db, districts, dcs, admin, counts)
        seed_l2(db, districts, dcs, admin, counts)
        seed_operator_mapping(db, districts, dcs, admin, counts)
        seed_hold_candidates(db, districts, dcs, admin, counts)

        record_owned(db)
        db.commit()

        groups = counts.pop("__reactivation_groups", 0)
        total = sum(counts.values())
        print(f"\nseeded {total} request rows across {len(set(k.split('/')[0] for k in counts))} sections")
        for key in sorted(counts):
            print(f"  {key:38} {counts[key]}")
        print(f"  reactivation groups                    {groups}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
