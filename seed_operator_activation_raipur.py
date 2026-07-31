"""Seed 4 dummy Operator Activation requests submitted by DC Raipur.

Mirrors backend/routers/operator_activation.py::submit_operator_activation so the
rows are indistinguishable from real portal submissions: PENDING status, a
portal-format request_no, and an initial "submitted by DC" remark. No document
files are attached (nothing is uploaded), matching a request whose files are
pending review.

Run:  python seed_operator_activation_raipur.py
"""
from datetime import datetime, timedelta

from backend.database import SessionLocal
from backend.models.district import District
from backend.models.base import StatusEnum, get_ist_time
from backend.models.operator_activation import (
    OperatorActivationRequest,
    OperatorActivationRemark,
)

DC_ID = 2            # dc_raipur
DISTRICT_ID = "387"  # Raipur
REGISTRAR_CODE = "986"
EA_CODE = "2084"
PINCODE = "492001"

# Four realistic Chhattisgarh operators.
PEOPLE = [
    {
        "name": "Rajesh Kumar Sahu", "mobile": "9826145073",
        "email": "rajesh.sahu@example.in", "aadhaar": "4821",
        "pan": "AJKPS4821K", "user_code": "986_2084_RPR_Rajesh",
        "cert": "NSEIT-583201",
    },
    {
        "name": "Priya Verma", "mobile": "9425367188",
        "email": "priya.verma@example.in", "aadhaar": "7305",
        "pan": "BXVPV7305L", "user_code": "986_2084_RPR_Priya",
        "cert": "NSEIT-591744",
    },
    {
        "name": "Suresh Nirmalkar", "mobile": "9691052934",
        "email": "suresh.nirmalkar@example.in", "aadhaar": "1968",
        "pan": "CQWPN1968M", "user_code": "986_2084_RPR_Suresh",
        "cert": "NSEIT-604612",
    },
    {
        "name": "Anita Dewangan", "mobile": "9754820611",
        "email": "anita.dewangan@example.in", "aadhaar": "5540",
        "pan": "DRTPD5540N", "user_code": "986_2084_RPR_Anita",
        "cert": "NSEIT-612087",
    },
]


def seed():
    db = SessionLocal()
    try:
        dist = db.query(District).filter(District.district_code == DISTRICT_ID).first()
        short = (dist.district_short_name if dist and dist.district_short_name else "OA")

        base = db.query(OperatorActivationRequest).count()
        created = []
        for i, p in enumerate(PEOPLE):
            # Skip if a request already exists for this mobile/email (submit guard).
            dup = (db.query(OperatorActivationRequest)
                   .filter((OperatorActivationRequest.operator_mobile == p["mobile"]) |
                           (OperatorActivationRequest.primary_email == p["email"]))
                   .first())
            if dup:
                print(f"  skip {p['name']} — request already exists (#{dup.id})")
                continue

            n = base + len(created) + 1
            req_no = f"{short}-{p['mobile'][-5:]}{DISTRICT_ID}A{n:04d}"
            cert_date = datetime(2024, 9, 12) + timedelta(days=i * 11)
            req = OperatorActivationRequest(
                dc_id=DC_ID,
                district_id=DISTRICT_ID,
                role="Operator",
                name_as_per_aadhaar=p["name"],
                registrar_code=REGISTRAR_CODE,
                ea_code=EA_CODE,
                user_code=p["user_code"],
                nseit_certificate_number=p["cert"],
                operator_mobile=p["mobile"],
                primary_email=p["email"],
                operator_aadhaar=p["aadhaar"],
                pan_number=p["pan"],
                nseit_certification_date=cert_date,
                nseit_certificate_expiry_date=cert_date + timedelta(days=730),
                pincode=PINCODE,
                status_id=StatusEnum.PENDING.value,
                request_no=req_no,
                submitted_at=get_ist_time() - timedelta(days=len(PEOPLE) - i),
            )
            db.add(req)
            db.flush()
            db.add(OperatorActivationRemark(
                request_id=req.id,
                author_id=DC_ID,
                author_role="dc",
                remark="Activation request submitted by District Coordinator.",
                status_after="pending",
            ))
            created.append(req)
            print(f"  + {req_no}  {p['name']}  (id {req.id})")

        db.commit()
        print(f"Seeded {len(created)} operator activation request(s) for DC Raipur.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
