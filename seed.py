import sys
import os
import csv
import bcrypt
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import MasterUserRole, District, UserLogin, MasterStatus
from backend.models.base import StatusEnum

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

        # 1.5. Seed Master Status
        status_names = {
            StatusEnum.PENDING: "Pending",
            StatusEnum.APPROVED: "Approved",
            StatusEnum.REVERTED: "Reverted",
            StatusEnum.REAPPLIED: "Reapplied",
            StatusEnum.SENT_TO_CHIPS: "Sent to CHiPS",
            StatusEnum.SENT_TO_UIDAI: "Sent to UIDAI",
            StatusEnum.UIDAI_APPROVED: "UIDAI Approved",
            StatusEnum.UIDAI_REJECTED: "UIDAI Rejected",
            StatusEnum.REVIEWED: "Reviewed",
            StatusEnum.ASSIGNED: "Assigned",
            StatusEnum.FORWARDED: "Forwarded",
            StatusEnum.FORWARDED_AGAIN: "Forwarded Again",
            StatusEnum.SKIPPED: "Skipped",
            StatusEnum.REJECTED: "Rejected",
            StatusEnum.REVERTED_BY_CHIPS: "Reverted by CHiPS",
            StatusEnum.APPROVED_LEGACY: "Approved Legacy",
            StatusEnum.ALLOTTED: "Allotted",
            StatusEnum.DONE: "Done"
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
            {"username": "chips_admin", "password": hash_password("AdminPassword@456"), "district_id": None, "roleid": 1},
            {"username": "indrajeetsen03@gmail.com", "password": hash_password("edmbalod123"), "district_id": "646", "roleid": 3},
            {"username": "kheeleshgangber@gmail.com", "password": hash_password("dcbalod123"), "district_id": "646", "roleid": 2},
            {"username": "edm-balodabazar.cg@gov.in", "password": hash_password("edmbalod123"), "district_id": "646", "roleid": 3},
            {"username": "lokeshdewangan6666@gmail.com", "password": hash_password("dcbalod123"), "district_id": "646", "roleid": 2},
            {"username": "deva.checking@gmail.com", "password": hash_password("edmbalrampurramanujganj123"), "district_id": "649", "roleid": 3},
            {"username": "tkumar749@gmail.com", "password": hash_password("dcbalrampurramanujganj123"), "district_id": "649", "roleid": 2},
            {"username": "bastar.degs@gmail.com", "password": hash_password("edmbastar123"), "district_id": "374", "roleid": 3},
            {"username": "s.ramkar281988@gmail.com", "password": hash_password("dcbastar123"), "district_id": "374", "roleid": 2},
            {"username": "mkverma9009@gmail.com", "password": hash_password("edmbemetara123"), "district_id": "650", "roleid": 3},
            {"username": "mukuldhurandhar.md@gmail.com", "password": hash_password("dcbemetara123"), "district_id": "650", "roleid": 2},
            {"username": "edmbijapur@gmail.com", "password": hash_password("edmbijapur123"), "district_id": "636", "roleid": 3},
            {"username": "santoshmorla21@gmail.com", "password": hash_password("dcbijapur123"), "district_id": "636", "roleid": 2},
            {"username": "kitu1702@gmail.com", "password": hash_password("edmbilaspur123"), "district_id": "375", "roleid": 3},
            {"username": "romilsahu02@gmail.com", "password": hash_password("dcbilaspur123"), "district_id": "375", "roleid": 2},
            {"username": "chipsdantewada@gmail.com", "password": hash_password("edmdakshinbastardantewada123"), "district_id": "376", "roleid": 3},
            {"username": "nraycruse65@gmail.com", "password": hash_password("dcdakshinbastardantewada123"), "district_id": "376", "roleid": 2},
            {"username": "edm.dhamtari2017@gmail.com", "password": hash_password("edmdhamtari123"), "district_id": "377", "roleid": 3},
            {"username": "dewanganhorilal08@gmail.com", "password": hash_password("dcdhamtari123"), "district_id": "377", "roleid": 2},
            {"username": "shrutiagrawal.be@gmail.com", "password": hash_password("edmdurg123"), "district_id": "378", "roleid": 3},
            {"username": "richavivek2415@gmail.com", "password": hash_password("dcdurg123"), "district_id": "378", "roleid": 2},
            {"username": "edm.gariyaband@gmail.com", "password": hash_password("edmgariyaband123"), "district_id": "645", "roleid": 3},
            {"username": "dc.gariaband@gmail.com", "password": hash_password("dcgariyaband123"), "district_id": "645", "roleid": 2},
            {"username": "ghanshyams175@gmail.com", "password": hash_password("edmgaurelapendramarwahi123"), "district_id": "734", "roleid": 3},
            {"username": "geet1292@gmail.com", "password": hash_password("dcgaurelapendramarwahi123"), "district_id": "734", "roleid": 2},
            {"username": "sskumar898555@gmail.com", "password": hash_password("edmjanjgirchampa123"), "district_id": "379", "roleid": 3},
            {"username": "dharam.pal102@gmail.com", "password": hash_password("dcjanjgirchampa123"), "district_id": "379", "roleid": 2},
            {"username": "neelankarbasu05@gmail.com", "password": hash_password("edmjashpur123"), "district_id": "380", "roleid": 3},
            {"username": "SVIVEK448@GMAIL.COM", "password": hash_password("dcjashpur123"), "district_id": "380", "roleid": 2},
            {"username": "edmkabirdham@gmail.com", "password": hash_password("edmkabeerdham123"), "district_id": "382", "roleid": 3},
            {"username": "lakhansahu200@gmail.com", "password": hash_password("dckabeerdham123"), "district_id": "382", "roleid": 2},
            {"username": "myghanshu@gmail.com", "password": hash_password("edmuttarbastarkanker123"), "district_id": "381", "roleid": 3},
            {"username": "paras.chandak7@gmail.com", "password": hash_password("dcuttarbastarkanker123"), "district_id": "381", "roleid": 2},
            {"username": "chipskondagaon@gmail.com", "password": hash_password("edmkondagaon123"), "district_id": "643", "roleid": 3},
            {"username": "Somshubham500@Gmail.Com", "password": hash_password("dckondagaon123"), "district_id": "643", "roleid": 2},
            {"username": "mtmith88@gmail.com", "password": hash_password("edmkhairagarhchhuikhadangandai123"), "district_id": "759", "roleid": 3},
            {"username": "pankajsolanki201@gmail.com", "password": hash_password("dckhairagarhchhuikhadangandai123"), "district_id": "759", "roleid": 2},
            {"username": "chips.korba@gmail.com", "password": hash_password("edmkorba123"), "district_id": "383", "roleid": 3},
            {"username": "rakesh_ap87@yahoo.in", "password": hash_password("edmkorea123"), "district_id": "384", "roleid": 3},
            {"username": "shantanu.roy04@gmail.com", "password": hash_password("dckorea123"), "district_id": "384", "roleid": 2},
            {"username": "bhupendra.ambilkar@yahoo.com", "password": hash_password("edmmahasamund123"), "district_id": "385", "roleid": 3},
            {"username": "mulchandnishad94@gmail.com", "password": hash_password("dcmahasamund123"), "district_id": "385", "roleid": 2},
            {"username": "degsgpm@gmail.com", "password": hash_password("edmmanendragarhchirmiribharatpur(mcb)123"), "district_id": "760", "roleid": 3},
            {"username": "pradhan.ganesh08@gmail.com", "password": hash_password("dcmanendragarhchirmiribharatpur(mcb)123"), "district_id": "760", "roleid": 2},
            {"username": "degsmmac@gmail.com", "password": hash_password("edmmohlamanpurambagarhchouki123"), "district_id": "761", "roleid": 3},
            {"username": "skumare102@gmail.com", "password": hash_password("dcmohlamanpurambagarhchouki123"), "district_id": "761", "roleid": 2},
            {"username": "2012sonam@gmail.com", "password": hash_password("edmmungeli123"), "district_id": "647", "roleid": 3},
            {"username": "ajaynishad818@gmail.com", "password": hash_password("dcmungeli123"), "district_id": "647", "roleid": 2},
            {"username": "kamrankhan.edm@gmail.com", "password": hash_password("edmnarayanpur123"), "district_id": "637", "roleid": 3},
            {"username": "cst.472@gmail.com", "password": hash_password("dcnarayanpur123"), "district_id": "637", "roleid": 2},
            {"username": "edm.raigarh@gmail.com", "password": hash_password("edmraigarh123"), "district_id": "386", "roleid": 3},
            {"username": "raveemca2008@gmail.com", "password": hash_password("dcraigarh123"), "district_id": "386", "roleid": 2},
            {"username": "sharma.kirti28@gmail.com", "password": hash_password("edmraipur123"), "district_id": "387", "roleid": 3},
            {"username": "shyamal0783@gmail.com", "password": hash_password("dcraipur123"), "district_id": "387", "roleid": 2},
            {"username": "saurabhmishra2985@gmail.com", "password": hash_password("edmrajnandgaon123"), "district_id": "388", "roleid": 3},
            {"username": "rajputankit.tc:s@gmail.com", "password": hash_password("dcrajnandgaon123"), "district_id": "388", "roleid": 2},
            {"username": "edmsarangarhbilaigarh@gmail.com", "password": hash_password("edmsarangarhbilaigarh123"), "district_id": "763", "roleid": 3},
            {"username": "gs47722@gmail.com", "password": hash_password("dcsarangarhbilaigarh123"), "district_id": "763", "roleid": 2},
            {"username": "dushyantsoni.soni@gmail.com", "password": hash_password("edmsakti123"), "district_id": "762", "roleid": 3},
            {"username": "saif4222@gmail.com", "password": hash_password("dcsakti123"), "district_id": "762", "roleid": 2},
            {"username": "shd4686@gmail.com", "password": hash_password("edmsukma123"), "district_id": "642", "roleid": 3},
            {"username": "varun.vs653@gmail.com", "password": hash_password("dcsukma123"), "district_id": "642", "roleid": 2},
            {"username": "edm.surajpur@gmail.com", "password": hash_password("edmsurajpur123"), "district_id": "648", "roleid": 3},
            {"username": "vikas65.vk@gmail.com", "password": hash_password("dcsurajpur123"), "district_id": "648", "roleid": 2},
            {"username": "vaibhav.masters1@gmail.com", "password": hash_password("edmsurguja123"), "district_id": "389", "roleid": 3},
            {"username": "vtiwari8510@gmail.com", "password": hash_password("dcsurguja123"), "district_id": "389", "roleid": 2}
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
        
            
        db.commit()
        print("Default users (Admin, DCs, EDMs) verified/seeded. Login credentials verified and updated.")

        print("\nDatabase seeding completed successfully! Ready to test.")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}", file=sys.stderr)
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
