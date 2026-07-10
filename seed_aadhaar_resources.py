import os
import csv
import sys
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import District, AadhaarDistrictResource

CSV_PATH = "Aadhaar Dist Resources - updated (2).xlsx - All.csv"

def clean_name(name: str) -> str:
    if not name:
        return ""
    # Remove whitespace, hyphens, dots, case-insensitive
    return "".join(c for c in name.lower() if c.isalnum())

def get_district_mappings(db: Session):
    districts = db.query(District).all()
    mappings = {}
    for d in districts:
        # Standard cleaning
        norm_name = clean_name(d.district_name)
        mappings[norm_name] = d.district_code
        
        # Add common aliases/substrings
        if "bhatapara" in norm_name:
            mappings[clean_name("balodabazar")] = d.district_code
            mappings[clean_name("balodabazarbhatapara")] = d.district_code
        if "ramanujganj" in norm_name:
            mappings[clean_name("balrampur")] = d.district_code
        if "champa" in norm_name:
            mappings[clean_name("janjgir")] = d.district_code
            mappings[clean_name("janjgirchampa")] = d.district_code
        if "kawardha" in norm_name or "kabeerdham" in norm_name:
            mappings[clean_name("kabirdham")] = d.district_code
        if "gariyaband" in norm_name:
            mappings[clean_name("gariaband")] = d.district_code
        if "korea" in norm_name:
            mappings[clean_name("koriya")] = d.district_code
        if "gpm" in norm_name or "gaurela" in norm_name:
            mappings[clean_name("gaurelapendramarwahi")] = d.district_code
            mappings[clean_name("gaurellapendramarwahi")] = d.district_code
        if "manpur" in norm_name:
            mappings[clean_name("mohlamanpurambagarhchowki")] = d.district_code
            mappings[clean_name("mohlamanpur")] = d.district_code
            mappings[clean_name("mohlamanpurambagarh")] = d.district_code
        if "chhuikhadan" in norm_name:
            mappings[clean_name("khairagarhchhuikhadangandai")] = d.district_code
            mappings[clean_name("khairagarh")] = d.district_code
        if "chirmiri" in norm_name:
            mappings[clean_name("manendragarhchirmiribharatpur")] = d.district_code
            mappings[clean_name("manendragarh")] = d.district_code
        if "bilaigarh" in norm_name:
            mappings[clean_name("sarangarhbilaigarh")] = d.district_code
            mappings[clean_name("sarangarh")] = d.district_code
            
    return mappings

def seed_aadhaar_resources():
    print("Seeding Aadhaar District Resources...")
    
    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV file not found at '{CSV_PATH}'", file=sys.stderr)
        sys.exit(1)
        
    db: Session = SessionLocal()
    
    try:
        mappings = get_district_mappings(db)
        
        # Clear existing resources
        db.query(AadhaarDistrictResource).delete()
        db.commit()
        
        with open(CSV_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
        # Row 0 and Row 1 are headers. Data starts from Row 2.
        # Header structure:
        # Col 0: S.No., Col 1: District
        # E-DM: Col 2 (Name), Col 3 (Contact No.), Col 4 (E-mail)
        # DC: Col 5 (Name), Col 6 (Contact No.), Col 7 (E-mail)
        # MTO: Col 8 (Name), Col 9 (Contact No.), Col 10 (E-mail)
        # Assistant Division Coordinator: Col 11 (Name), Col 12 (Contact No.), Col 13 (E-mail)
        
        seeded_count = 0
        unmatched = []
        
        for idx in range(2, len(rows)):
            row = rows[idx]
            if not row or len(row) < 2:
                continue
                
            s_no = row[0].strip()
            district_name = row[1].strip()
            if not s_no or not district_name:
                continue
                
            clean_dist = clean_name(district_name)
            dist_code = mappings.get(clean_dist)
            
            if not dist_code:
                # Try partial match or prefix
                matched = False
                for k, code in mappings.items():
                    if k in clean_dist or clean_dist in k:
                        dist_code = code
                        matched = True
                        break
                if not matched:
                    unmatched.append(district_name)
                    continue
            
            # Helper to clean multi-line or whitespace values
            def clean_field(val: str) -> str:
                if not val:
                    return ""
                cleaned = val.replace('\n', ' ').replace('\r', ' ').strip()
                return cleaned if cleaned.lower() != "none" else ""
                
            edm_name = clean_field(row[2])
            edm_contact = clean_field(row[3])
            edm_email = clean_field(row[4])
            
            dc_name = clean_field(row[5])
            dc_contact = clean_field(row[6])
            dc_email = clean_field(row[7])
            
            mto_name = clean_field(row[8]) if len(row) > 8 else ""
            mto_contact = clean_field(row[9]) if len(row) > 9 else ""
            mto_email = clean_field(row[10]) if len(row) > 10 else ""
            
            adc_name = clean_field(row[11]) if len(row) > 11 else ""
            adc_contact = clean_field(row[12]) if len(row) > 12 else ""
            adc_email = clean_field(row[13]) if len(row) > 13 else ""
            
            # Check for existing entry
            existing = db.query(AadhaarDistrictResource).filter_by(district_code=dist_code).first()
            if existing:
                # Update
                existing.edm_name = edm_name
                existing.edm_contact = edm_contact
                existing.edm_email = edm_email
                existing.dc_name = dc_name
                existing.dc_contact = dc_contact
                existing.dc_email = dc_email
                existing.mto_name = mto_name
                existing.mto_contact = mto_contact
                existing.mto_email = mto_email
                existing.adc_name = adc_name
                existing.adc_contact = adc_contact
                existing.adc_email = adc_email
            else:
                # Create
                res = AadhaarDistrictResource(
                    district_code=dist_code,
                    edm_name=edm_name,
                    edm_contact=edm_contact,
                    edm_email=edm_email,
                    dc_name=dc_name,
                    dc_contact=dc_contact,
                    dc_email=dc_email,
                    mto_name=mto_name,
                    mto_contact=mto_contact,
                    mto_email=mto_email,
                    adc_name=adc_name,
                    adc_contact=adc_contact,
                    adc_email=adc_email
                )
                db.add(res)
            
            seeded_count += 1
            
        db.commit()
        print(f"Successfully seeded {seeded_count} district resources.")
        if unmatched:
            print(f"Warning: Could not match districts: {unmatched}")
            
    except Exception as e:
        db.rollback()
        print(f"Error seeding district resources: {e}", file=sys.stderr)
    finally:
        db.close()

if __name__ == "__main__":
    seed_aadhaar_resources()
