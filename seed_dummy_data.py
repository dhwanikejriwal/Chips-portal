# -*- coding: utf-8 -*-
"""
seed_dummy_data.py
==================
Idempotent and reset-capable seed script for the Aadhaar Operator Portal.
It clears all operational tables (except login configurations) and seeds a new dataset.
It strictly respects sequence of events:
- Candidates: Candidate Register -> LMS -> NSEIT -> Operator Activation
- Station IDs: Station ID Request -> L1 Registration -> L2 Registration
- Timing gaps are realistic to allow metric analysis.
"""

import sys, os, random, bcrypt
from datetime import datetime, timedelta, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import (
    MasterUserRole, District, UserLogin,
    Candidate, CandidateLogin, DCRemark,
    LMS, LMSRemark,
    NSEITRequest, NSEITRemark,
)
from backend.models.l1_registration import L1RegistrationRequest, L1RegistrationRemarkHistory
from backend.models.reactivation import (
    OperatorReactivationRequest, ReactivationOperator,
    ReactivationDocument, ReactivationRemarkHistory,
)
from backend.models.l2_registration import L2RegistrationRequest, L2RegistrationRemark
from backend.models.operator_activation import (
    OperatorActivationRequest, ActivationDocument, OperatorActivationRemark,
)
from backend.models.station_id import StationIDRequest, StationIDRemark

# ─────────────────────────────── helpers ────────────────────────────────────

def hp(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def rand_mobile() -> str:
    return "9" + str(random.randint(100000000, 999999999))

def rand_aadhaar() -> str:
    return str(random.randint(200000000000, 999999999999))

def rand_dob() -> date:
    year  = random.randint(1975, 2000)
    month = random.randint(1, 12)
    day   = random.randint(1, 28)
    return date(year, month, day)

def rand_pincode() -> str:
    return str(random.randint(490001, 497999))

def rand_pan() -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return (
        "".join(random.choices(letters, k=5))
        + str(random.randint(1000, 9999))
        + random.choice(letters)
    )

QUALIFICATIONS = [
    "10th Pass", "12th Pass", "Diploma in IT",
    "B.Sc. Computer Science", "BCA", "MCA", "B.Tech",
    "B.Com", "BA", "Diploma in Electronics",
]
FIRST_NAMES = [
    "Rahul", "Priya", "Amit", "Sunita", "Vijay", "Rekha", "Deepak",
    "Anita", "Suresh", "Kavita", "Manoj", "Pooja", "Ravi", "Nisha",
    "Arun", "Geeta", "Sanjay", "Meena", "Rohit", "Shanti", "Dinesh",
    "Lata", "Ashok", "Pushpa", "Vinod", "Savita", "Ramesh", "Usha",
    "Ajay", "Kiran", "Harish", "Manju", "Pankaj", "Sangeeta", "Nitin",
    "Vandana", "Sunil", "Asha", "Bharat", "Ritu", "Naresh", "Anjali",
    "Hemant", "Seema", "Rakesh", "Madhuri", "Shyam", "Radha", "Trilok", "Saroj",
]
LAST_NAMES = [
    "Sahu", "Verma", "Sharma", "Yadav", "Patel", "Gupta", "Tiwari",
    "Singh", "Thakur", "Chandrakar", "Dewangan", "Kosare", "Netam",
    "Markam", "Baghel", "Soni", "Jain", "Agrawal", "Nishad", "Kashyap",
    "Bhardwaj", "Mishra", "Pandey", "Dubey", "Chouhan", "Rajput",
]

OPERATOR_ROLES = ["Operator", "Supervisor", "Enrolment Agency"]
MODEL_TYPES    = ["ECMP", "UCL", "VLE"]
SOFT_VERSIONS  = ["2.0.1", "2.1.0", "3.0.2", "3.1.5", "4.0.0"]

SEED_DISTRICTS = [
    {"code": "387", "name": "Raipur",    "short": "RPR"},
    {"code": "375", "name": "Bilaspur",  "short": "BLP"},
    {"code": "378", "name": "Durg",      "short": "DRG"},
    {"code": "383", "name": "Korba",     "short": "KRB"},
    {"code": "386", "name": "Raigarh",   "short": "RGR"},
    {"code": "385", "name": "Mahasamund","short": "MHS"},
    {"code": "388", "name": "Rajnandgaon","short": "RJN"},
    {"code": "377", "name": "Dhamtari",  "short": "DMT"},
    {"code": "389", "name": "Surguja",   "short": "SRG"},
    {"code": "379", "name": "Janjgir-Champa", "short": "JCH"},
]

def _rand_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def get_timeline_timestamps(base_days_ago, step_gaps):
    """
    Generates a list of cascading datetimes starting from base_days_ago in the past
    with randomized hours/minutes.
    """
    times = []
    current_time = datetime.utcnow() + timedelta(hours=5, minutes=30) - timedelta(days=base_days_ago)
    times.append(current_time)
    for gap in step_gaps:
        current_time += timedelta(days=gap, hours=random.randint(0, 4), minutes=random.randint(0, 59))
        times.append(current_time)
    return times

# ──────────────────────────────── main ──────────────────────────────────────

def seed():
    db: Session = SessionLocal()
    print("=" * 60)
    print("  Aadhaar Operator Portal - Reset & Seed script")
    print("=" * 60)

    try:
        # -- Step 0. Truncate operational data --
        print("\n[0/5] Truncating operational tables...")
        db.query(StationIDRemark).delete()
        db.query(StationIDRequest).delete()
        db.query(OperatorActivationRemark).delete()
        db.query(ActivationDocument).delete()
        db.query(OperatorActivationRequest).delete()
        db.query(L2RegistrationRemark).delete()
        db.query(L2RegistrationRequest).delete()
        db.query(ReactivationDocument).delete()
        db.query(ReactivationRemarkHistory).delete()
        db.query(ReactivationOperator).delete()
        db.query(OperatorReactivationRequest).delete()
        db.query(L1RegistrationRemarkHistory).delete()
        db.query(L1RegistrationRequest).delete()
        db.query(NSEITRemark).delete()
        db.query(NSEITRequest).delete()
        db.query(LMSRemark).delete()
        db.query(LMS).delete()
        db.query(DCRemark).delete()
        db.query(CandidateLogin).delete()
        db.query(Candidate).delete()
        db.commit()
        print("      [OK] Operational tables cleared.")

        # -- 1. Roles --
        print("\n[1/5] Seeding roles...")
        for rid, role in [(1, "Admin"), (2, "DC"), (3, "EDM"), (4, "Candidate")]:
            if not db.get(MasterUserRole, rid):
                db.add(MasterUserRole(id=rid, role=role))
        db.commit()
        print("      [OK] Roles verified.")

        # -- 2. Districts --
        print("\n[2/5] Seeding districts...")
        for i, d in enumerate(SEED_DISTRICTS, start=1):
            if not db.get(District, d["code"]):
                db.add(District(
                    district_code=d["code"], id=i,
                    district_name=d["name"], district_short_name=d["short"],
                ))
        db.commit()
        print(f"      [OK] {len(SEED_DISTRICTS)} districts verified.")

        # -- 3. Admin & DC Users --
        print("\n[3/5] Seeding admin / DC users...")
        _ensure_user(db, "chips_admin", "admin123", None, 1)
        dc_map: dict[str, UserLogin] = {}
        for d in SEED_DISTRICTS:
            dc_un  = f"dc_{d['short'].lower()}"
            edm_un = f"edm_{d['short'].lower()}"
            dc  = _ensure_user(db, dc_un,  "dc123",  d["code"], 2)
            _    = _ensure_user(db, edm_un, "edm123", d["code"], 3)
            dc_map[d["code"]] = dc
        db.commit()
        admin_user = db.query(UserLogin).filter_by(username="chips_admin").first()
        print(f"      [OK] DC and admin users verified.")

        # -- 4. Seeding candidate pipeline --
        print("\n[4/5] Seeding candidate pipeline (Registration -> LMS -> NSEIT -> Activation)...")
        _seed_candidate_pipeline(db, dc_map, admin_user)
        db.commit()
        print("      [OK] Candidate pipeline seeded.")

        # -- 5. Seeding station registration pipeline --
        print("\n[5/5] Seeding station registration pipeline (Station ID -> L1 -> L2)...")
        _seed_station_pipeline(db, dc_map, admin_user)
        _seed_reactivations(db, dc_map, admin_user)
        db.commit()
        print("      [OK] Station registration and reactivations seeded.")

        # -- Summary --
        _print_summary(db)

    except Exception as e:
        db.rollback()
        import traceback
        print(f"\n[ERROR]: {e}", file=sys.stderr)
        traceback.print_exc()
    finally:
        db.close()


# ═════════════════════════════ pipeline seeders ═════════════════════════════

def _ensure_user(db, username, password, district_id, roleid) -> UserLogin:
    u = db.query(UserLogin).filter_by(username=username).first()
    if not u:
        u = UserLogin(
            username=username,
            password=hp(password),
            district_id=district_id,
            roleid=roleid,
        )
        db.add(u)
        db.flush()
    return u


def _seed_candidate_pipeline(db: Session, dc_map: dict, admin_user: UserLogin):
    districts = list(dc_map.keys())
    candidate_counters = {d: 0 for d in districts}

    # Generate 100 candidates with strict status distributions
    # 30 Pending, 15 Rejected, 55 Approved
    statuses = ["Pending"] * 30 + ["Rejected"] * 15 + ["Approved"] * 55
    random.shuffle(statuses)

    for i in range(100):
        dist_code = districts[i % len(districts)]
        short = next(d["short"] for d in SEED_DISTRICTS if d["code"] == dist_code)
        dc_user = dc_map[dist_code]

        # Generate request code using short name
        candidate_counters[dist_code] += 1
        req_code = f"{short}-A{candidate_counters[dist_code]:04d}"

        status = statuses[i]
        name = _rand_name()
        email = f"{name.lower().replace(' ', '.')}.{i+1}@example.com"
        mobile = rand_mobile()
        aadhaar = rand_aadhaar()

        base_days_ago = random.randint(30, 180)
        t = get_timeline_timestamps(base_days_ago, [2, 3, 2, 4, 3, 4, 2])

        # Create Candidate
        c = Candidate(
            request_code=req_code,
            name=name,
            mobile=mobile,
            email=email,
            district=dist_code,
            qualification=random.choice(QUALIFICATIONS),
            dob=rand_dob(),
            aadhaar=aadhaar,
            address=f"Village {random.randint(1,99)}, Ward {random.randint(1,20)}, {next(d['name'] for d in SEED_DISTRICTS if d['code'] == dist_code)}",
            pincode=rand_pincode(),
            is_existing_operator=random.choice([True, False]),
            status=status,
            created_at=t[0],
            updated_at=t[1]
        )
        db.add(c)
        db.flush()

        # Create DC Remark
        remark_text = {
            "Pending": "Application received. Verification in progress.",
            "Approved": "Application reviewed and approved.",
            "Rejected": "Invalid marksheet submitted. Documents rejected.",
        }[status]

        db.add(DCRemark(
            r_id=c.r_id,
            remark=remark_text,
            time=t[1],
            by=dc_user.id,
            status_after=status,
        ))

        if status != "Approved":
            continue

        # Create CandidateLogin for approved candidate
        c_login = CandidateLogin(
            r_id=c.r_id,
            user_id=email,
            password=hp("Test@123")
        )
        db.add(c_login)
        db.flush()

        # Next: LMS stage (only for Approved candidates)
        # 55 Candidates:
        # 10 Pending LMS, 6 Reverted LMS, 4 Reverted by CHiPS LMS, 4 Reapplied LMS, 31 Completed (Approved/Skipped) LMS
        lms_pool = (
            ["Pending"] * 10 +
            ["Reverted"] * 6 +
            ["Reverted by CHiPS"] * 4 +
            ["Reapplied"] * 4 +
            ["Approved"] * 21 +
            ["Skipped"] * 10
        )
        lms_status = lms_pool[i % len(lms_pool)]

        lms = LMS(
            r_id=c.r_id,
            status=lms_status,
            created_at=t[2],
            updated_at=t[3]
        )
        db.add(lms)
        db.flush()

        # LMS Remarks
        _add_lms_remarks(db, lms, lms_status, dc_user, admin_user, c_login, t[2], t[3])

        if lms_status in ["Approved", "Skipped"]:
            c.lms_id = f"LMS{c.r_id:05d}"
            # Next: NSEIT stage
            # 31 Candidates who completed LMS:
            # 10 Pending NSEIT, 6 Reverted NSEIT, 4 Reverted by CHiPS NSEIT, 4 Reapplied NSEIT, 7 Completed (Approved/Skipped) NSEIT
            nseit_pool = (
                ["Pending"] * 10 +
                ["Reverted"] * 6 +
                ["Reverted by CHiPS"] * 4 +
                ["Reapplied"] * 4 +
                ["Approved"] * 4 +
                ["Skipped"] * 3
            )
            nseit_status = nseit_pool[i % len(nseit_pool)]

            nseit = NSEITRequest(
                r_id=c.r_id,
                status=nseit_status,
                created_at=t[4],
                updated_at=t[5]
            )
            db.add(nseit)
            db.flush()

            # NSEIT Remarks
            _add_nseit_remarks(db, nseit, nseit_status, dc_user, admin_user, c_login, t[4], t[5])

            if nseit_status in ["Approved", "Skipped"]:
                c.nseit_id = f"NSEIT{c.r_id:05d}"
                c.exam_unique_code = f"EXAM-{c.r_id:05d}"

                # Next: Operator Activation stage
                # 7 candidates who completed NSEIT:
                # 2 sent_to_chips, 2 sent_to_uidai, 2 approved, 1 reverted
                act_pool = ["sent_to_chips", "sent_to_uidai", "approved", "reverted"]
                act_status = act_pool[i % len(act_pool)]

                act_req = OperatorActivationRequest(
                    request_no=req_code,  # propagated same request code!
                    dc_id=dc_user.id,
                    district_id=dist_code,
                    role=random.choice(OPERATOR_ROLES),
                    name_as_per_aadhaar=name,
                    registrar_code=f"REG{random.randint(100,999)}",
                    ea_code=f"EA{random.randint(100,999)}",
                    user_code=f"UC{random.randint(1000,9999)}",
                    nseit_certificate_number=c.nseit_id,
                    operator_mobile=mobile,
                    primary_email=email,
                    operator_aadhaar=aadhaar[-4:],
                    pan_number=rand_pan(),
                    nseit_certification_date=t[5].date(),
                    nseit_certificate_expiry_date=(t[5] + timedelta(days=365*3)).date(),
                    pincode=c.pincode,
                    status=act_status,
                    submitted_at=t[6],
                    reviewed_at=t[7] if act_status in ["approved", "reverted", "sent_to_uidai"] else None,
                    reviewed_by=admin_user.id if act_status in ["approved", "reverted", "sent_to_uidai"] else None,
                )
                db.add(act_req)
                db.flush()

                # Activation Docs
                for doc_type in ["hard_copy_form", "aadhaar_photo", "pan_card", "passbook", "nseit_certificate", "excel_sheet"]:
                    db.add(ActivationDocument(
                        request_id=act_req.id,
                        doc_type=doc_type,
                        file_path=f"uploads/operator_activation/{dc_user.id}/{act_req.id}/{doc_type}.pdf",
                        original_filename=f"{doc_type}.pdf",
                        file_size_bytes=random.randint(50000, 150000),
                        mime_type="application/pdf",
                        uploaded_at=t[6],
                    ))

                # Activation Remarks
                if act_status in ["approved", "reverted", "sent_to_uidai"]:
                    remark_msg = {
                        "approved": "All documents verified. Activation approved.",
                        "reverted": "PAN card copy is blurred. Please resubmit.",
                        "sent_to_uidai": "Sent to UIDAI: All documents verified.",
                    }[act_status]

                    db.add(OperatorActivationRemark(
                        request_id=act_req.id,
                        author_id=admin_user.id,
                        author_role="chips_admin",
                        remark=remark_msg,
                        created_at=t[7]
                    ))


def _add_lms_remarks(db, lms, status, dc_user, admin_user, c_login, c_time, u_time):
    if status == "Pending":
        db.add(LMSRemark(lms_id=lms.id, remark="LMS request submitted by candidate.", candidate_by_id=c_login.id, status_after="Pending", time=c_time))
    elif status == "Approved":
        db.add(LMSRemark(lms_id=lms.id, remark="LMS request submitted.", candidate_by_id=c_login.id, status_after="Pending", time=c_time))
        db.add(LMSRemark(lms_id=lms.id, remark="LMS details verified & approved.", admin_by_id=admin_user.id, status_after="Approved", time=u_time))
    elif status == "Skipped":
        db.add(LMSRemark(lms_id=lms.id, remark="Request skipped. Candidate provided existing LMS ID.", candidate_by_id=c_login.id, status_after="Skipped", time=c_time))
    elif status == "Reverted":
        db.add(LMSRemark(lms_id=lms.id, remark="LMS request submitted.", candidate_by_id=c_login.id, status_after="Pending", time=c_time))
        db.add(LMSRemark(lms_id=lms.id, remark="Document mismatch. Reverting back to candidate.", admin_by_id=dc_user.id, status_after="Reverted", time=u_time))
    elif status == "Reverted by CHiPS":
        db.add(LMSRemark(lms_id=lms.id, remark="LMS request submitted.", candidate_by_id=c_login.id, status_after="Pending", time=c_time))
        db.add(LMSRemark(lms_id=lms.id, remark="Reverted by state admin for verification.", admin_by_id=admin_user.id, status_after="Reverted by CHiPS", time=u_time))
    elif status == "Reapplied":
        db.add(LMSRemark(lms_id=lms.id, remark="LMS request submitted.", candidate_by_id=c_login.id, status_after="Pending", time=c_time - timedelta(days=2)))
        db.add(LMSRemark(lms_id=lms.id, remark="Reverted for correction.", admin_by_id=dc_user.id, status_after="Reverted", time=c_time - timedelta(days=1)))
        db.add(LMSRemark(lms_id=lms.id, remark="Corrected and resubmitted.", candidate_by_id=c_login.id, status_after="Reapplied", time=c_time))


def _add_nseit_remarks(db, nseit, status, dc_user, admin_user, c_login, c_time, u_time):
    if status == "Pending":
        db.add(NSEITRemark(nseit_id=nseit.id, remark="NSEIT request submitted by candidate.", candidate_by_id=c_login.id, status_after="Pending", time=c_time))
    elif status == "Approved":
        db.add(NSEITRemark(nseit_id=nseit.id, remark="NSEIT details submitted.", candidate_by_id=c_login.id, status_after="Pending", time=c_time))
        db.add(NSEITRemark(nseit_id=nseit.id, remark="NSEIT verification completed. Approved.", admin_by_id=admin_user.id, status_after="Approved", time=u_time))
    elif status == "Skipped":
        db.add(NSEITRemark(nseit_id=nseit.id, remark="Skipped. Candidate provided existing NSEIT certificate.", candidate_by_id=c_login.id, status_after="Skipped", time=c_time))
    elif status == "Reverted":
        db.add(NSEITRemark(nseit_id=nseit.id, remark="NSEIT request submitted.", candidate_by_id=c_login.id, status_after="Pending", time=c_time))
        db.add(NSEITRemark(nseit_id=nseit.id, remark="Certificate copy is not readable.", admin_by_id=dc_user.id, status_after="Reverted", time=u_time))
    elif status == "Reverted by CHiPS":
        db.add(NSEITRemark(nseit_id=nseit.id, remark="NSEIT request submitted.", candidate_by_id=c_login.id, status_after="Pending", time=c_time))
        db.add(NSEITRemark(nseit_id=nseit.id, remark="CHIPS admin reverted due to name match issue.", admin_by_id=admin_user.id, status_after="Reverted by CHiPS", time=u_time))
    elif status == "Reapplied":
        db.add(NSEITRemark(nseit_id=nseit.id, remark="NSEIT request submitted.", candidate_by_id=c_login.id, status_after="Pending", time=c_time - timedelta(days=2)))
        db.add(NSEITRemark(nseit_id=nseit.id, remark="Reverted by state admin.", admin_by_id=admin_user.id, status_after="Reverted by CHiPS", time=c_time - timedelta(days=1)))
        db.add(NSEITRemark(nseit_id=nseit.id, remark="Reapplied with certificate scan.", candidate_by_id=c_login.id, status_after="Reapplied", time=c_time))


# ──────────────────────────── station pipeline ────────────────────────────

def _seed_station_pipeline(db: Session, dc_map: dict, admin_user: UserLogin):
    districts = list(dc_map.keys())
    station_counters = {d: 0 for d in districts}

    # 100 Station ID requests:
    # 35 sent_to_chips, 20 reverted, 15 reapplied, 30 approved
    statuses = ["sent_to_chips"] * 35 + ["reverted"] * 20 + ["reapplied"] * 15 + ["approved"] * 30
    random.shuffle(statuses)

    for i in range(100):
        dist_code = districts[i % len(districts)]
        short = next(d["short"] for d in SEED_DISTRICTS if d["code"] == dist_code)
        dc_user = dc_map[dist_code]

        # Station ID request_no format: short_name-KXXXX
        station_counters[dist_code] += 1
        req_no = f"{short}-K{station_counters[dist_code]:04d}"

        status = statuses[i]
        base_days_ago = random.randint(20, 150)
        t = get_timeline_timestamps(base_days_ago, [2, 3, 2, 4, 3])

        station_id_inserted = None
        if status == "approved":
            station_id_inserted = f"STA{random.randint(1000, 9999)}"

        req = StationIDRequest(
            request_no=req_no,
            dc_id=dc_user.id,
            district_id=dist_code,
            model=random.choice(["ECMP", "UCL"]),
            user_type=random.choice(["new_user", "machine_id", "custom"]),
            user_type_custom_reason="Enrolment EA reallocation." if random.choice([True, False]) else None,
            number_of_kits=random.randint(1, 3),
            status=status,
            station_id_inserted=station_id_inserted,
            submitted_at=t[0],
            reviewed_at=t[1] if status in ["approved", "reverted", "reapplied"] else None,
            reviewed_by=admin_user.id if status in ["approved", "reverted", "reapplied"] else None
        )
        db.add(req)
        db.flush()

        # Station Remarks
        if status in ["reverted", "reapplied"]:
            db.add(StationIDRemark(request_id=req.id, author_id=admin_user.id, author_role="chips_admin", remark="Please specify kit serial numbers.", created_at=t[1]))
        if status == "reapplied":
            db.add(StationIDRemark(request_id=req.id, author_id=dc_user.id, author_role="dc", remark="Updated and reapplied.", created_at=t[2]))
        if status == "approved":
            db.add(StationIDRemark(request_id=req.id, author_id=admin_user.id, author_role="chips_admin", remark=f"Allotted Station ID: {station_id_inserted}", created_at=t[1]))

        if status != "approved":
            continue

        # Next: L1 Registration (for approved Station IDs)
        # 30 approved Station IDs:
        # 10 L1 pending/reapplied/reverted, 20 L1 approved (which can go to L2)
        l1_pool = ["PENDING"] * 5 + ["REVERTED"] * 3 + ["REAPPLIED"] * 2 + ["APPROVED"] * 20
        l1_status = l1_pool[i % len(l1_pool)]

        l1_req = L1RegistrationRequest(
            request_code=req_no,  # Reuse same request_no!
            district_id=dist_code,
            station_id=station_id_inserted,
            machine_id=f"MCH{random.randint(10000, 99999)}",
            operator_name=_rand_name(),
            operator_id=f"OP{random.randint(10000, 99999)}",
            model_type=req.model,
            software_version=random.choice(SOFT_VERSIONS),
            uv_id=f"UV{random.randint(1000, 9999)}",
            uv_password="Secure@1234",
            status=l1_status,
            created_at=t[2],
            updated_at=t[3]
        )
        db.add(l1_req)
        db.flush()

        # L1 Remarks
        db.add(L1RegistrationRemarkHistory(request_code=req_no, remark="L1 Registration request submitted.", action="SUBMITTED", user_role="dc", timestamp=t[2]))
        if l1_status == "APPROVED":
            db.add(L1RegistrationRemarkHistory(request_code=req_no, remark="L1 credentials verified and approved.", action="APPROVED", user_role="chips_admin", timestamp=t[3]))
        elif l1_status == "REVERTED":
            db.add(L1RegistrationRemarkHistory(request_code=req_no, remark="Machine ID mismatch. Reverting.", action="REVERTED", user_role="chips_admin", timestamp=t[3]))

        if l1_status != "APPROVED":
            continue

        # Next: L2 Registration
        # 20 L1 approved requests:
        # 8 pending/reverted/reapplied L2, 12 L2 approved/sent_to_uidai
        l2_pool = ["sent_to_chips"] * 3 + ["reverted"] * 3 + ["reapplied"] * 2 + ["approved"] * 8 + ["sent_to_uidai"] * 4
        l2_status = l2_pool[i % len(l2_pool)]

        l2_req = L2RegistrationRequest(
            request_no=req_no,  # Reuse same request_no!
            dc_id=dc_user.id,
            district_id=dist_code,
            client_version="4.0.0",
            new_station_id=station_id_inserted,
            ea_code=f"EA{random.randint(100, 999)}",
            reg_code=f"REG{random.randint(100, 999)}",
            new_machine_id=l1_req.machine_id,
            client_type=req.model,
            old_station_id=f"OLD{random.randint(1000, 9999)}",
            reason_for_l2_registration="Machine migration and activation.",
            old_machine_id=f"OLDMCH{random.randint(10000, 99999)}",
            tech_center_remarks="Technically verified." if l2_status in ["approved", "sent_to_uidai"] else None,
            operator_name=l1_req.operator_name,
            operator_id=l1_req.operator_id,
            unique_id=f"UID{random.randint(10000, 99999)}",
            block=f"Block {random.randint(1, 10)}",
            address_of_govt_premises=f"Govt Premises Building, {short} District",
            status=l2_status,
            uidai_remarks="UIDAI reviewed." if l2_status in ["approved", "sent_to_uidai"] else None,
            submitted_at=t[4],
            reviewed_at=t[5] if l2_status in ["approved", "sent_to_uidai", "reverted"] else None,
            reviewed_by=admin_user.id if l2_status in ["approved", "sent_to_uidai", "reverted"] else None,
        )
        db.add(l2_req)
        db.flush()

        # L2 Remarks
        if l2_status in ["reverted", "reapplied"]:
            db.add(L2RegistrationRemark(request_id=l2_req.id, author_id=admin_user.id, author_role="chips_admin", remark="Check old machine ID mapping.", created_at=t[5]))
        if l2_status == "reapplied":
            db.add(L2RegistrationRemark(request_id=l2_req.id, author_id=dc_user.id, author_role="dc", remark="Reapplied with corrected old machine ID.", created_at=t[5] + timedelta(hours=1)))
        if l2_status in ["approved", "sent_to_uidai"]:
            db.add(L2RegistrationRemark(request_id=l2_req.id, author_id=admin_user.id, author_role="chips_admin", remark="L2 registration request approved.", created_at=t[5]))


# ──────────────────────────── reactivation ────────────────────────────────

def _seed_reactivations(db: Session, dc_map: dict, admin_user: UserLogin):
    districts = list(dc_map.keys())
    reactivation_counters = {d: 0 for d in districts}

    # 50 reactivation batch requests
    statuses = ["PENDING"] * 15 + ["REVIEWED"] * 15 + ["REVERTED"] * 10 + ["REAPPLIED"] * 5 + ["SENT_TO_UIDAI"] * 5

    for i in range(50):
        dist_code = districts[i % len(districts)]
        short = next(d["short"] for d in SEED_DISTRICTS if d["code"] == dist_code)
        dc_user = dc_map[dist_code]

        # Format Reactivation request_code: short_name-RXXXX
        reactivation_counters[dist_code] += 1
        req_code = f"{short}-R{reactivation_counters[dist_code]:04d}"

        status = statuses[i]
        days_ago = random.randint(5, 120)
        op_count = random.randint(2, 4)

        req = OperatorReactivationRequest(
            request_code=req_code,
            dc_id=dc_user.id,
            district_id=dist_code,
            operator_count=op_count,
            training_date=date.today() - timedelta(days=random.randint(10, 90)),
            status=status,
            created_at=datetime.utcnow() - timedelta(days=days_ago),
            updated_at=datetime.utcnow() - timedelta(days=days_ago - 2),
        )
        db.add(req)
        db.flush()

        # Remarks
        db.add(ReactivationRemarkHistory(request_code=req_code, remark_history="Reactivation batch request submitted.", sender_role="DC", timestamp=req.created_at))
        if status in ["REVIEWED", "SENT_TO_UIDAI"]:
            db.add(ReactivationRemarkHistory(request_code=req_code, remark_history="Reactivation batch verified.", sender_role="CHIPS_ADMIN", timestamp=req.updated_at))

        # Operators in the batch
        for j in range(op_count):
            op_name = _rand_name()
            db.add(ReactivationOperator(
                request_code=req_code,
                role=random.choice(OPERATOR_ROLES),
                operator_name=op_name,
                registrar_code="REG123",
                ea_code="EA999",
                user_code=f"UC{random.randint(1000, 9999)}",
                certificate_number=f"NSEIT{random.randint(10000, 99999)}",
                lms_certificate_id=f"LMS{random.randint(10000, 99999)}",
                operator_mobile=rand_mobile(),
                email_id=f"{op_name.lower().replace(' ', '')}@example.com",
                aadhaar_number=rand_aadhaar(),
                certification_date=date.today() - timedelta(days=200),
                model_type=random.choice(MODEL_TYPES),
                status="ACTIVATED" if status == "REVIEWED" else "PENDING",
            ))

        # Docs
        db.add(ReactivationDocument(
            request_code=req_code,
            doc_type="training_photo",
            path=f"/storage/reactivation_docs/{req_code}/training_photo.jpg",
            original_filename="training_photo.jpg",
            file_size=102400
        ))


# ──────────────────────────── summary report ─────────────────────────────

def _print_summary(db):
    print("\n" + "=" * 60)
    print("  SEED COMPLETE — Table Summary")
    print("=" * 60)
    tables = [
        ("master_user_role",                MasterUserRole),
        ("district_table",                  District),
        ("user_login_table",                UserLogin),
        ("candidate_table",                 Candidate),
        ("candidate_login_table",           CandidateLogin),
        ("dc_remark_table",                 DCRemark),
        ("LMS_table",                       LMS),
        ("lms_remark_table",                LMSRemark),
        ("nseit_request_table",             NSEITRequest),
        ("nseit_request_remark_table",      NSEITRemark),
        ("l1_registration_requests",        L1RegistrationRequest),
        ("l1_registration_remark_history",  L1RegistrationRemarkHistory),
        ("operator_reactivation_requests",  OperatorReactivationRequest),
        ("reactivation_operators",          ReactivationOperator),
        ("reactivation_remark_history",     ReactivationRemarkHistory),
        ("reactivation_documents",          ReactivationDocument),
        ("l2_registration_requests",        L2RegistrationRequest),
        ("l2_registration_remarks",         L2RegistrationRemark),
        ("operator_activation_requests",    OperatorActivationRequest),
        ("operator_activation_remarks",     OperatorActivationRemark),
        ("station_id_requests",             StationIDRequest),
        ("station_id_remarks",              StationIDRemark),
    ]
    total = 0
    for name, model in tables:
        count = db.query(model).count()
        total += count
        print(f"  {name:<42} {count:>5} rows")
    print(f"  {'-' * 48}")
    print(f"  {'TOTAL':42} {total:>5} rows")
    print("=" * 60)
    print("\n[DONE] All tables populated with sequential, timed dummy data!\n")


if __name__ == "__main__":
    seed()
