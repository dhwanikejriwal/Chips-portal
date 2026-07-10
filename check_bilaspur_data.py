from backend.database import SessionLocal
from backend.models.lms import LMS
from backend.models.nseit import NSEITRequest
from backend.models.operator_activation import OperatorActivationRequest
from backend.models.reactivation import OperatorReactivationRequest
from backend.models.candidate import Candidate
from backend.models.district import District

db = SessionLocal()
try:
    dist = db.query(District).filter(District.district_name == 'Bilaspur').first()
    if dist:
        code = dist.district_code
        print(f"Bilaspur District Code: {code}")
        
        # Count LMS
        lms_cnt = db.query(LMS).join(Candidate).filter(Candidate.district == code).count()
        print(f"LMS requests for Bilaspur: {lms_cnt}")
        
        # Count NSEIT
        nseit_cnt = db.query(NSEITRequest).join(Candidate).filter(Candidate.district == code).count()
        print(f"NSEIT requests for Bilaspur: {nseit_cnt}")
        
        # Count Operator Activation
        act_reqs = db.query(OperatorActivationRequest).filter(OperatorActivationRequest.district_id == code).all()
        print(f"Operator Activation requests for Bilaspur: {len(act_reqs)}")
        for r in act_reqs:
            print(f"  ID: {r.id}, Name: {r.name_as_per_aadhaar}, Status: {r.status}")
            
        # Count Reactivation
        react_cnt = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.district_id == code).count()
        print(f"Reactivation requests for Bilaspur: {react_cnt}")
finally:
    db.close()
