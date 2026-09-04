"""
Sanitize and Normalize DC/EDM Profiles Script.

1. Removes orphan / duplicate legacy logins (e.g. 'dc.raipur@chips.in', 'edm.raipur@chips.in')
2. Ensures exactly 1 DC and 1 EDM per district with standard logins ('dcraipur', 'edmraipur')
3. Updates user_profile_table so ALL 33 districts have 100% dummy names, emails, and phone numbers.
"""
import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
sys.path.append(os.getcwd())

import csv
import bcrypt
from difflib import get_close_matches
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine
from backend.models import District, UserLogin, UserProfile, MasterUserRole

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DUMMY_CSV = os.path.join(THIS_DIR, "Aadhaar_Dist_Resources_Dummy.csv")
if not os.path.exists(DUMMY_CSV):
    DUMMY_CSV = os.path.join(ROOT_DIR, "useful_files", "Aadhaar_Dist_Resources_Dummy.csv")

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def clean_str(val):
    if val is None:
        return ""
    val = str(val).strip().replace('"', '').replace('\n', ' ').replace('\r', ' ')
    return " ".join(val.split())

ALIAS_MAP = {
    "gariaband": "645",
    "gariyaband": "645",
    "gaurellapendramarwahi": "734",
    "gaurelapendramarwahi": "734",
    "gpm": "734",
    "kabirdham": "382",
    "kabeerdham": "382",
    "kanker": "381",
    "uttarbastarkanker": "381",
    "dantewada": "376",
    "dakshinbastardantewada": "376",
    "mohlamanpurambagarhchowki": "761",
    "mohlamanpurambagarhchouki": "761",
    "mohlamanpur": "761",
    "manendragarhchirmiribharatpur": "760",
    "manendragarhchirmiribharatpurmcb": "760",
    "mcb": "760",
    "koriya": "384",
    "korea": "384",
    "balrampur": "649",
    "balrampurramanujganj": "649",
    "balodabazar": "644",
    "balodabazarbhatapara": "644",
    "sarangarhbilaigarh": "763",
    "khairagarhchhuikhadangandai": "759",
    "janjgirchampa": "379",
}

def sanitize_profiles():
    print("==========================================================")
    print("  SANITIZING DC / EDM / MTO PROFILES WITH 100% DUMMY DATA")
    print("==========================================================")
    
    db: Session = SessionLocal()
    try:
        # 1. Fetch all districts from database
        districts = db.query(District).all()
        print(f"Loaded {len(districts)} districts from database.")
        
        # Build district lookup mappings
        dist_by_code = {d.district_code: d for d in districts}
        dist_lookup = {}
        for d in districts:
            clean_name = "".join(ch for ch in d.district_name.lower() if ch.isalnum())
            dist_lookup[clean_name] = d.district_code
            if d.district_short_name:
                dist_lookup[d.district_short_name.lower()] = d.district_code
            
        def match_district_code(name):
            if not name: return None
            c_name = "".join(ch for ch in name.lower() if ch.isalnum())
            if c_name in ALIAS_MAP:
                return ALIAS_MAP[c_name]
            if c_name in dist_lookup:
                return dist_lookup[c_name]
            for k, v in dist_lookup.items():
                if k in c_name or c_name in k:
                    return v
            # Fuzzy match fallback
            keys = list(dist_lookup.keys())
            matches = get_close_matches(c_name, keys, n=1, cutoff=0.5)
            if matches:
                return dist_lookup[matches[0]]
            return None

        # 2. Read dummy CSV data
        if not os.path.exists(DUMMY_CSV):
            print(f"Error: CSV not found at {DUMMY_CSV}", file=sys.stderr)
            return

        with open(DUMMY_CSV, mode='r', encoding='utf-8') as f:
            rows = list(csv.reader(f))[2:] # Skip 2 headers

        processed_districts = set()

        for r in rows:
            if not r or len(r) < 5: continue
            raw_dist = clean_str(r[1])
            dist_code = match_district_code(raw_dist)
            if not dist_code:
                print(f"Warning: Could not match district '{raw_dist}'")
                continue

            dist_obj = dist_by_code.get(dist_code)
            dist_clean_slug = dist_obj.district_name.lower().replace(" ", "").replace("-", "") if dist_obj else raw_dist.lower().replace(" ", "")
            
            processed_districts.add(dist_code)

            # Roles to seed
            roles_spec = [
                {"role_id": 3, "role_name": "EDM", "name": clean_str(r[2]), "phone": clean_str(r[3]), "email": clean_str(r[4]), "prefix": "edm"},
                {"role_id": 2, "role_name": "DC", "name": clean_str(r[5]), "phone": clean_str(r[6]), "email": clean_str(r[7]), "prefix": "dc"},
            ]
            if len(r) > 8 and clean_str(r[8]):
                roles_spec.append({"role_id": 5, "role_name": "MTO", "name": clean_str(r[8]), "phone": clean_str(r[9]), "email": clean_str(r[10]) if len(r) > 10 else None, "prefix": "mto"})
            if len(r) > 11 and clean_str(r[11]):
                roles_spec.append({"role_id": 6, "role_name": "ADC", "name": clean_str(r[11]), "phone": clean_str(r[12]), "email": clean_str(r[13]) if len(r) > 13 else None, "prefix": "adc"})

            for spec in roles_spec:
                role_id = spec["role_id"]
                dummy_name = spec["name"] or f"{spec['prefix'].upper()}{dist_clean_slug}"
                dummy_phone = spec["phone"] or "123456789"
                dummy_email = spec["email"] or f"{spec['prefix']}{dist_clean_slug}@gmail.com"
                canonical_username = f"{spec['prefix']}{dist_clean_slug}"
                canonical_password = hash_password(f"{canonical_username}123")

                # Find all logins for this district and role
                matching_users = db.query(UserLogin).filter(
                    UserLogin.district_id == dist_code,
                    UserLogin.roleid == role_id
                ).all()

                primary_user = None
                if matching_users:
                    primary_user = matching_users[0]
                    # Update credentials to clean username
                    primary_user.username = canonical_username
                    primary_user.password = canonical_password
                    primary_user.is_active = 1

                    # Remove legacy duplicate accounts for this district+role if any
                    for extra_u in matching_users[1:]:
                        db.query(UserProfile).filter(UserProfile.user_id == extra_u.id).delete(synchronize_session=False)
                        # Reassign any foreign keys from extra_u to primary_user or delete
                        db.query(UserLogin).filter(UserLogin.id == extra_u.id).delete(synchronize_session=False)
                else:
                    # Also check by canonical username
                    existing_by_name = db.query(UserLogin).filter(UserLogin.username.ilike(canonical_username)).first()
                    if existing_by_name:
                        primary_user = existing_by_name
                        primary_user.district_id = dist_code
                        primary_user.roleid = role_id
                        primary_user.is_active = 1
                    else:
                        primary_user = UserLogin(
                            username=canonical_username,
                            password=canonical_password,
                            district_id=dist_code,
                            roleid=role_id,
                            is_active=1,
                            has_changed_password=0
                        )
                        db.add(primary_user)
                        db.flush()

                # Now update/create UserProfile with 100% clean dummy data
                profile = db.query(UserProfile).filter(UserProfile.user_id == primary_user.id).first()
                if not profile:
                    profile = UserProfile(
                        user_id=primary_user.id,
                        full_name=dummy_name,
                        email=dummy_email,
                        phone=dummy_phone
                    )
                    db.add(profile)
                else:
                    profile.full_name = dummy_name
                    profile.email = dummy_email
                    profile.phone = dummy_phone

        db.commit()
        print(f"\nSuccessfully sanitized and updated profiles for {len(processed_districts)} districts.")

        # 3. Clean up any lingering legacy logins with '@chips.in' or email-style usernames that are inactive/orphaned
        legacy_users = db.query(UserLogin).filter(
            UserLogin.username.like("%@chips.in%"),
            UserLogin.roleid.in_([2, 3])
        ).all()
        for lu in legacy_users:
            # Check if canonical user exists for this district
            canonical_exists = db.query(UserLogin).filter(
                UserLogin.district_id == lu.district_id,
                UserLogin.roleid == lu.roleid,
                UserLogin.id != lu.id
            ).first()
            if canonical_exists:
                db.query(UserProfile).filter(UserProfile.user_id == lu.id).delete(synchronize_session=False)
                db.query(UserLogin).filter(UserLogin.id == lu.id).delete(synchronize_session=False)
        db.commit()

        print("\nAll DC and EDM accounts and profiles are now 100% uniform and sanitized!")
        print("Ready to test.")
    except Exception as e:
        db.rollback()
        print(f"Error sanitizing profiles: {e}", file=sys.stderr)
    finally:
        db.close()

if __name__ == "__main__":
    sanitize_profiles()
