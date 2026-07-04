import sys
import os
import csv
import bcrypt
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import MasterUserRole, District, UserLogin

CSV_PATH = "LGD - Local Government Directory, Government of India.csv"

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def seed_database():
    print("Seeding database values using LGD CSV data...")
    
    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV file not found at '{CSV_PATH}'", file=sys.stderr)
        sys.exit(1)
        
    db: Session = SessionLocal()
    
    try:
        # 1. Seed Roles
        roles_data = [
            {"id": 1, "role": "Admin"},      # CHIPS State Admin
            {"id": 2, "role": "DC"},         # District Coordinator
            {"id": 3, "role": "EDM"},        # District Manager
            {"id": 4, "role": "Candidate"}   # Operator Candidate
        ]
        
        for r in roles_data:
            existing_role = db.query(MasterUserRole).filter_by(id=r["id"]).first()
            if not existing_role:
                db.add(MasterUserRole(id=r["id"], role=r["role"]))
        db.commit()
        print("Roles successfully verified/seeded.")

        # 2. Parse and Seed Districts from CSV
        print("Reading districts from CSV...")
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

        # 3. Seed Default Administrative Users
        # Raipur LGD code is '387' (RYP / RPR in CSV)
        # Bilaspur LGD code is '375' (BLP in CSV)
        users_data = [
            # State-level CHIPS Admin (no district_id)
            {
                "username": "chips_admin",
                "password": hash_password("admin123"),
                "district_id": None,
                "roleid": 1
            },
            # Raipur DC
            {
                "username": "dc_raipur",
                "password": hash_password("dc123"),
                "district_id": "387",
                "roleid": 2
            },
            # Raipur EDM
            {
                "username": "edm_raipur",
                "password": hash_password("edm123"),
                "district_id": "387",
                "roleid": 3
            }
        ]

        for u in users_data:
            existing_user = db.query(UserLogin).filter_by(username=u["username"]).first()
            if existing_user:
                # Update existing user values (e.g. if you changed the password in seed.py)
                existing_user.password = u["password"]
                existing_user.district_id = u["district_id"]
                existing_user.roleid = u["roleid"]
            else:
                db.add(UserLogin(
                    username=u["username"],
                    password=u["password"],
                    district_id=u["district_id"],
                    roleid=u["roleid"]
                ))
        # Delete any user logins that are not in our seed list (e.g. dc_bilaspur)
        seeded_usernames = [u["username"] for u in users_data]
        db.query(UserLogin).filter(~UserLogin.username.in_(seeded_usernames)).delete(synchronize_session=False)
        db.commit()
        print("Default users (Admin, DCs, EDMs) verified/seeded (and stale users deleted).")

        print("\nDatabase seeding completed successfully! Ready to test.")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}", file=sys.stderr)
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
