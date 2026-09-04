import sys
import os

# Ensure root project directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.getcwd())

import csv
import bcrypt
from sqlalchemy import text
from sqlalchemy.orm import Session
from difflib import get_close_matches
from backend.database import SessionLocal
from backend.models import MasterUserRole, District, UserLogin, MasterStatus, UserProfile
from backend.models.base import StatusEnum

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "useful_files", "LGD - Local Government Directory, Government of India.csv")

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def clean_str(val):
    if val is None:
        return ""
    val = str(val).strip().replace('"', '').replace('\n', ' ').replace('\r', ' ')
    val = " ".join(val.split())
    if val.endswith('.0'):
        val = val[:-2]
    return val

def seed_database():
    print("Seeding database values...")
    
    db: Session = SessionLocal()
    
    try:
        # 0. Ensure database columns are compatible
        print("Executing database schema migration updates...")
        db.execute(text("ALTER TABLE user_profile_table ALTER COLUMN phone TYPE VARCHAR(100);"))
        db.execute(text("ALTER TABLE user_login_table ALTER COLUMN username DROP NOT NULL;"))
        db.execute(text("ALTER TABLE user_login_table ALTER COLUMN password DROP NOT NULL;"))
        db.commit()

        # 0.5. Clean up legacy duplicates to prevent unique constraint failures
        print("Cleaning up legacy case-insensitive duplicate UserLogin/UserProfile accounts...")
        
        # 1. Delete all logins where username is NULL (MTO/ADC without email) to clear duplicates
        no_login_users = db.query(UserLogin).filter(UserLogin.username.is_(None)).all()
        no_login_ids = [u.id for u in no_login_users]
        if no_login_ids:
            db.query(UserProfile).filter(UserProfile.user_id.in_(no_login_ids)).delete(synchronize_session=False)
            db.query(UserLogin).filter(UserLogin.id.in_(no_login_ids)).delete(synchronize_session=False)
            db.commit()
            db.expunge_all()

        # Reset sequences after cleanup so new auto-increment IDs stay compact
        try:
            db.execute(text("SELECT setval(pg_get_serial_sequence('user_login_table', 'id'), COALESCE((SELECT MAX(id) FROM user_login_table), 0) + 1, false);"))
            db.execute(text("SELECT setval(pg_get_serial_sequence('user_profile_table', 'id'), COALESCE((SELECT MAX(id) FROM user_profile_table), 0) + 1, false);"))
            db.commit()
            db.expunge_all()
        except Exception:
            pass
            
        # 2. Find and delete case-insensitive duplicates of usernames (e.g. svivek448@gmail.com)
        all_users = db.query(UserLogin).all()
        seen_usernames = {}
        to_delete_ids = []
        for u in all_users:
            if u.username:
                u_lower = u.username.lower()
                if u_lower in seen_usernames:
                    old_user = seen_usernames[u_lower]
                    if u.id > old_user.id:
                        to_delete_ids.append(u.id)
                    else:
                        to_delete_ids.append(old_user.id)
                        seen_usernames[u_lower] = u
                else:
                    seen_usernames[u_lower] = u
        if to_delete_ids:
            db.query(UserProfile).filter(UserProfile.user_id.in_(to_delete_ids)).delete(synchronize_session=False)
            db.query(UserLogin).filter(UserLogin.id.in_(to_delete_ids)).delete(synchronize_session=False)
            db.commit()
            db.expunge_all()
            print(f"Removed {len(to_delete_ids)} legacy duplicate user account(s).")

        # 1. Seed Roles
        roles_data = [
            {"id": 1, "role": "Admin"},      # CHIPS State Admin
            {"id": 2, "role": "DC"},         # District Coordinator
            {"id": 3, "role": "EDM"},        # District Manager
            {"id": 4, "role": "Candidate"},  # Operator Candidate
            {"id": 5, "role": "MTO"},
            {"id": 6, "role": "Assistant Division Coordinator"}
        ]
        
        for r in roles_data:
            existing_role = db.query(MasterUserRole).filter_by(id=r["id"]).first()
            if not existing_role:
                db.add(MasterUserRole(id=r["id"], role=r["role"]))
        db.commit()
        print("Roles successfully verified/seeded.")

        # 1.5. Seed Master Status
        status_names = {
            StatusEnum.PENDING: "Pending",
            StatusEnum.APPROVED: "Approved",
            StatusEnum.REVERTED: "Reverted",
            StatusEnum.REAPPLIED: "Reapplied",
            StatusEnum.SENT_TO_UIDAI: "Sent to UIDAI",
            StatusEnum.FORWARDED: "Forwarded",
            StatusEnum.FORWARDED_AGAIN: "Forwarded Again",
            StatusEnum.SKIPPED: "Skipped",
            StatusEnum.REJECTED: "Rejected",
            StatusEnum.REVERTED_BY_CHIPS: "Reverted by CHiPS",
            StatusEnum.APPROVED_LEGACY: "Approved Legacy",
            StatusEnum.ON_HOLD: "On Hold",
            StatusEnum.ALLOTTED: "Allotted",
            StatusEnum.L1_DONE: "L1 Done",
            StatusEnum.L2_DONE: "L2 Done"
        }
        for status_enum, name in status_names.items():
            existing_status = db.query(MasterStatus).filter_by(id=status_enum.value).first()
            if not existing_status:
                db.add(MasterStatus(id=status_enum.value, name=name))
            else:
                existing_status.name = name
        db.commit()
        print("Master statuses successfully verified/seeded.")
        # 2. Parse and Seed Districts from CSV
        print("Reading districts from CSV...")
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Clean up empty rows if any
                    if not row.get("District LGD Code"):
                        continue
                    
                    lgd_code = row["District LGD Code"].strip()
                    s_no = int(row["S No"].strip())
                    name = row["District Name (In In English)" if "District Name (In In English)" in row else "District Name (In English)"].strip()
                    short_name = row["Short Name of District"].strip()
                    
                    existing_district = db.query(District).filter_by(district_code=lgd_code).first()
                    if not existing_district:
                        db.add(District(
                            district_code=lgd_code,
                            id=s_no,
                            district_name=name,
                            district_short_name=short_name
                        ))
            db.commit()
            print("All districts from LGD CSV successfully verified/seeded.")
        else:
            print(f"Warning: CSV file not found at '{CSV_PATH}'. Skipping district seeding.", file=sys.stderr)

        # 3. Seed Default Administrative Users
        # Raipur LGD code is '387' (RPR in CSV)
        # Bilaspur LGD code is '375' (BLP in CSV)
        users_data = [
            {"username": "chips_admin", "password": hash_password("admin123"), "district_id": None, "roleid": 1},
            {"username": "chips_admin2", "password": hash_password("admin456"), "district_id": None, "roleid": 1},
            #Balod
            {"username": "edmbalod", "password": hash_password("edmbalod123"), "district_id": "646", "roleid": 3},
            {"username": "dcbalod", "password": hash_password("dcbalod123"), "district_id": "646", "roleid": 2},
            #balodabazar
            {"username": "edmbalodabazar", "password": hash_password("edmbalodabazar123"), "district_id": "644", "roleid": 3},
            {"username": "dcbalodabazar", "password": hash_password("dcbalodabazar123"), "district_id": "644", "roleid": 2},
            #balrampur
            {"username": "edmbalrampurramanujganj", "password": hash_password("edmbalrampurramanujganj123"), "district_id": "649", "roleid": 3},
            {"username": "dcbalrampurramanujganj", "password": hash_password("dcbalrampurramanujganj123"), "district_id": "649", "roleid": 2},
            #bastar
            {"username": "edmbastar", "password": hash_password("edmbastar123"), "district_id": "374", "roleid": 3},
            {"username": "dcbastar", "password": hash_password("dcbastar123"), "district_id": "374", "roleid": 2},
            #bemetara
            {"username": "edmbemetara", "password": hash_password("edmbemetara123"), "district_id": "650", "roleid": 3},
            {"username": "dcbemetara", "password": hash_password("dcbemetara123"), "district_id": "650", "roleid": 2},
            #bijapur
            {"username": "edmbijapur", "password": hash_password("edmbijapur123"), "district_id": "636", "roleid": 3},
            {"username": "dcbijapur", "password": hash_password("dcbijapur123"), "district_id": "636", "roleid": 2},
            #bilaspur
            {"username": "edmbilaspur", "password": hash_password("edmbilaspur123"), "district_id": "375", "roleid": 3},
            {"username": "dcbilaspur", "password": hash_password("dcbilaspur123"), "district_id": "375", "roleid": 2},
            #dantewada
            {"username": "edmdakshinbastardantewada", "password": hash_password("edmdakshinbastardantewada123"), "district_id": "376", "roleid": 3},
            {"username": "dcdakshinbastardantewada", "password": hash_password("dcdakshinbastardantewada123"), "district_id": "376", "roleid": 2},
            #dhamtari
            {"username": "edmdhamtari", "password": hash_password("edmdhamtari123"), "district_id": "377", "roleid": 3},
            {"username": "dcdhamtari", "password": hash_password("dcdhamtari123"), "district_id": "377", "roleid": 2},
            #durg
            {"username": "edmdurg", "password": hash_password("edmdurg123"), "district_id": "378", "roleid": 3},
            {"username": "dcdurg", "password": hash_password("dcdurg123"), "district_id": "378", "roleid": 2},
            #gariyaband
            {"username": "edmgariyaband", "password": hash_password("edmgariyaband123"), "district_id": "645", "roleid": 3},
            {"username": "dcgariyaband", "password": hash_password("dcgariyaband123"), "district_id": "645", "roleid": 2},
            #gaurela-pendra-marwahi
            {"username": "edmgaurelapendramarwahi", "password": hash_password("edmgaurelapendramarwahi123"), "district_id": "734", "roleid": 3},
            {"username": "dcgaurelapendramarwahi", "password": hash_password("dcgaurelapendramarwahi123"), "district_id": "734", "roleid": 2},
            #janjgir-champa
            {"username": "edmjanjgirchampa", "password": hash_password("edmjanjgirchampa123"), "district_id": "379", "roleid": 3},
            {"username": "dcjanjgirchampa", "password": hash_password("dcjanjgirchampa123"), "district_id": "379", "roleid": 2},
            #jashpur
            {"username": "edmjashpur", "password": hash_password("edmjashpur123"), "district_id": "380", "roleid": 3},
            {"username": "dcjashpur", "password": hash_password("dcjashpur123"), "district_id": "380", "roleid": 2},
            #kabirdham
            {"username": "edmkabeerdham", "password": hash_password("edmkabeerdham123"), "district_id": "382", "roleid": 3},
            {"username": "dckabeerdham", "password": hash_password("dckabeerdham123"), "district_id": "382", "roleid": 2},
            #kanker
            {"username": "edmuttarbastarkanker", "password": hash_password("edmuttarbastarkanker123"), "district_id": "381", "roleid": 3},
            {"username": "dcuttarbastarkanker", "password": hash_password("dcuttarbastarkanker123"), "district_id": "381", "roleid": 2},
            #kondagaon
            {"username": "edmkondagaon", "password": hash_password("edmkondagaon123"), "district_id": "643", "roleid": 3},
            {"username": "dckondagaon", "password": hash_password("dckondagaon123"), "district_id": "643", "roleid": 2},
            #khairagarh-chhuikhadan-gandai
            {"username": "edmkhairagarhchhuikhadangandai", "password": hash_password("edmkhairagarhchhuikhadangandai123"), "district_id": "759", "roleid": 3},
            {"username": "dckhairagarhchhuikhadangandai", "password": hash_password("dckhairagarhchhuikhadangandai123"), "district_id": "759", "roleid": 2},
            #korba
            {"username": "edmkorba", "password": hash_password("edmkorba123"), "district_id": "383", "roleid": 3},
            #korea
            {"username": "edmkorea", "password": hash_password("edmkorea123"), "district_id": "384", "roleid": 3},
            {"username": "dckorea", "password": hash_password("dckorea123"), "district_id": "384", "roleid": 2},
            #mahasamund
            {"username": "edmmahasamund", "password": hash_password("edmmahasamund123"), "district_id": "385", "roleid": 3},
            {"username": "dcmahasamund", "password": hash_password("dcmahasamund123"), "district_id": "385", "roleid": 2},
            #manendragarh-chirmiri-bharatpur(mcb)
            {"username": "edmmanendragarhchirmiribharatpur(mcb)", "password": hash_password("edmmanendragarhchirmiribharatpur(mcb)123"), "district_id": "760", "roleid": 3},
            {"username": "dcmanendragarhchirmiribharatpur(mcb)", "password": hash_password("dcmanendragarhchirmiribharatpur(mcb)123"), "district_id": "760", "roleid": 2},
            #mohla-manpur-amba(mau)
            {"username": "edmmohlamanpurambagarhchouki", "password": hash_password("edmmohlamanpurambagarhchouki123"), "district_id": "761", "roleid": 3},
            {"username": "dcmohlamanpurambagarhchouki", "password": hash_password("dcmohlamanpurambagarhchouki123"), "district_id": "761", "roleid": 2},
            #mungeli
            {"username": "edmmungeli", "password": hash_password("edmmungeli123"), "district_id": "647", "roleid": 3},
            {"username": "dcmungeli", "password": hash_password("dcmungeli123"), "district_id": "647", "roleid": 2},
            #narayanpur
            {"username": "edmnarayanpur", "password": hash_password("edmnarayanpur123"), "district_id": "637", "roleid": 3},
            {"username": "dcnarayanpur", "password": hash_password("dcnarayanpur123"), "district_id": "637", "roleid": 2},
            #raigarh
            {"username": "edmraigarh", "password": hash_password("edmraigarh123"), "district_id": "386", "roleid": 3},
            {"username": "dcraigarh", "password": hash_password("dcraigarh123"), "district_id": "386", "roleid": 2},
            #raipur
            {"username": "edmraipur", "password": hash_password("edmraipur123"), "district_id": "387", "roleid": 3},
            {"username": "dcraipur", "password": hash_password("dcraipur123"), "district_id": "387", "roleid": 2},
            #rajnandgaon
            {"username": "edmrajnandgaon", "password": hash_password("edmrajnandgaon123"), "district_id": "388", "roleid": 3},
            {"username": "dcrajnandgaon", "password": hash_password("dcrajnandgaon123"), "district_id": "388", "roleid": 2},
            #sarangarh-bhilaigarh
            {"username": "edmsarangarhbilaigarh", "password": hash_password("edmsarangarhbilaigarh123"), "district_id": "763", "roleid": 3},
            {"username": "dcsarangarhbilaigarh", "password": hash_password("dcsarangarhbilaigarh123"), "district_id": "763", "roleid": 2},
            #sakti
            {"username": "edmsakti", "password": hash_password("edmsakti123"), "district_id": "762", "roleid": 3},
            {"username": "dcsakti", "password": hash_password("dcsakti123"), "district_id": "762", "roleid": 2},
            #sukma
            {"username": "edmsukma", "password": hash_password("edmsukma123"), "district_id": "642", "roleid": 3},
            {"username": "dcsukma", "password": hash_password("dcsukma123"), "district_id": "642", "roleid": 2},
            #surajpur
            {"username": "edmsurajpur", "password": hash_password("edmsurajpur123"), "district_id": "648", "roleid": 3},
            {"username": "dcsurajpur", "password": hash_password("dcsurajpur123"), "district_id": "648", "roleid": 2},
            #surguja
            {"username": "edmsurguja", "password": hash_password("edmsurguja123"), "district_id": "389", "roleid": 3},
            {"username": "dcsurguja", "password": hash_password("dcsurguja123"), "district_id": "389", "roleid": 2}
        ]

        for u in users_data:
            username_lower = u["username"].lower()
            dist_id = u["district_id"]
            role_id = u["roleid"]

            # 1. Find user by exact username match first
            existing_user = db.query(UserLogin).filter(UserLogin.username.ilike(username_lower)).first()

            # 2. If not found by username, find by district & role
            if not existing_user and dist_id is not None:
                existing_user = db.query(UserLogin).filter(
                    UserLogin.district_id == dist_id,
                    UserLogin.roleid == role_id
                ).first()

            if existing_user:
                # Check if another record already has this username (to avoid UniqueViolation when updating)
                conflict_user = db.query(UserLogin).filter(
                    UserLogin.username.ilike(username_lower),
                    UserLogin.id != existing_user.id
                ).first()
                if conflict_user:
                    db.query(UserProfile).filter(UserProfile.user_id == conflict_user.id).delete(synchronize_session=False)
                    db.query(UserLogin).filter(UserLogin.id == conflict_user.id).delete(synchronize_session=False)
                    db.flush()

                existing_user.username = username_lower
                existing_user.password = u["password"]
                existing_user.district_id = dist_id
                existing_user.roleid = role_id
            else:
                db.add(UserLogin(
                    username=username_lower,
                    password=u["password"],
                    district_id=dist_id,
                    roleid=role_id
                ))
        
        db.commit()
        print("Default users (Admin, DCs, EDMs) verified/seeded. Login credentials verified and updated.")

        # 4. Parse and Seed Resource Contacts from CSV (EDM, DC, MTO, ADC)
        #original profiles
        #resource_csv = os.path.join(BASE_DIR, "sample reports", "Aadhaar Dist Resources - updated (2).xlsx - All (1).csv")
        
        #dummy profiles
        resource_csv = os.path.join(BASE_DIR, "useful_files", "Aadhaar_Dist_Resources_Dummy.csv")
        
        if os.path.exists(resource_csv):
            print(f"Reading resources and profiles from '{resource_csv}'...")
            with open(resource_csv, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            # Skip first 2 header rows
            data_rows = rows[2:]
            
            # Load all districts from DB to map clean names
            districts = db.query(District).all()
            dist_map = {d.district_name.lower().replace("-", " ").replace(" ", ""): d.district_code for d in districts}
            
            def get_district_code(name):
                if not name:
                    return None
                name_clean = name.lower().replace("-", " ").replace(" ", "").strip()
                if name_clean in dist_map:
                    return dist_map[name_clean]
                
                # Substring matching (e.g. 'balrampur' in 'balrampurramanujganj')
                for k, v in dist_map.items():
                    if k in name_clean or name_clean in k:
                        return v

                # Fuzzy matching fallback
                keys = list(dist_map.keys())
                matches = get_close_matches(name_clean, keys, n=1, cutoff=0.6)
                if matches:
                    return dist_map[matches[0]]
                
                return None

            for row in data_rows:
                if not row or len(row) < 5:
                    continue
                district_name = clean_str(row[1])
                if not district_name:
                    continue
                
                dist_code = get_district_code(district_name)
                if not dist_code:
                    print(f"Warning: Could not resolve district code for '{district_name}'")
                    continue

                # Config for roles/positions in the CSV row
                people = [
                    {"role_id": 3, "role_name": "EDM", "name_idx": 2, "phone_idx": 3, "email_idx": 4, "pwd_prefix": "edm", "auto_create_login": True},
                    {"role_id": 2, "role_name": "DC", "name_idx": 5, "phone_idx": 6, "email_idx": 7, "pwd_prefix": "dc", "auto_create_login": True},
                    {"role_id": 5, "role_name": "MTO", "name_idx": 8, "phone_idx": 9, "email_idx": 10, "pwd_prefix": "mto", "auto_create_login": False},
                    {"role_id": 6, "role_name": "Assistant Division Coordinator", "name_idx": 11, "phone_idx": 12, "email_idx": 13, "pwd_prefix": "adc", "auto_create_login": False}
                ]

                for person in people:
                    if len(row) <= person["email_idx"]:
                        continue
                    name = clean_str(row[person["name_idx"]])
                    phone = clean_str(row[person["phone_idx"]])
                    email = clean_str(row[person["email_idx"]])

                    if not name or name.lower() in ("none", "null", "-"):
                        continue

                    # Strictly extract email and phone from CSV without any default fallback strings
                    csv_email = email if (email and email.lower() not in ("none", "null", "-")) else None
                    csv_phone = phone if (phone and phone.lower() not in ("none", "null", "-")) else None

                    # Look up existing user by district and role (seeded in users_data above)
                    user = db.query(UserLogin).filter(
                        UserLogin.district_id == dist_code,
                        UserLogin.roleid == person["role_id"]
                    ).first()

                    if not user:
                        # Create UserLogin record
                        if person["auto_create_login"]:
                            # Standard auto-created credentialed login
                            role_prefix = person["pwd_prefix"]
                            dist_clean = district_name.lower().replace(' ', '').replace('-', '')
                            username_val = f"{role_prefix}{dist_clean}"
                            pwd_plain = f"{role_prefix}{dist_clean}123"
                            pwd_hashed = hash_password(pwd_plain)
                            user = UserLogin(
                                username=username_val,
                                password=pwd_hashed,
                                district_id=dist_code,
                                roleid=person["role_id"],
                                is_active=1,
                                has_changed_password=0
                            )
                        else:
                            # Create an un-credentialed (no login) UserLogin record
                            user = UserLogin(
                                username=None,
                                password=None,
                                district_id=dist_code,
                                roleid=person["role_id"],
                                is_active=1,
                                has_changed_password=0
                            )
                        db.add(user)
                        db.flush()

                    user_id_val = user.id
                    # Create or update UserProfile strictly using CSV values
                    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id_val).first()
                    if not profile:
                        profile = UserProfile(
                            user_id=user_id_val,
                            full_name=name,
                            email=csv_email,
                            phone=csv_phone
                        )
                        db.add(profile)
                    else:
                        profile.full_name = name
                        profile.email = csv_email
                        profile.phone = csv_phone

            db.commit()
            print("Resource users and profiles successfully verified/seeded from CSV.")
        else:
            print(f"Warning: Resource CSV file not found at '{resource_csv}'. Skipping profile seeding.")

        print("\nDatabase seeding completed successfully! Ready to test.")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}", file=sys.stderr)
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
