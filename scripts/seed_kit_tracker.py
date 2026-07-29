import os
import sys
import pandas as pd
from datetime import datetime
import numpy as np

sys.path.append(os.getcwd())

from backend.database import SessionLocal
from backend.models.kit_registration import KitRegistration
from backend.models.operator import Operator
from backend.models.operator_station_mapping import OperatorStationMapping
from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
from sqlalchemy import text

def clean_date(d):
    if pd.isna(d) or d == '-' or not d:
        return None
    try:
        if isinstance(d, datetime):
            return d.date()
        return pd.to_datetime(d).date()
    except:
        return None

def clean_str(s):
    if pd.isna(s) or s == '-':
        return None
    return str(s).strip()

def map_status(status_str):
    if not status_str: return None
    s = str(status_str).lower().strip()
    if 'uidai' in s: return 6 # Sent to UIDAI
    if 'chips' in s: return 5 # Sent to CHiPS
    if 'done' in s: return 18 # Done
    if 'approved' in s or s == 'yes': return 2 # Approved
    if 'pending' in s or s == 'no': return 1 # Pending
    if 'rejected' in s: return 14 # Rejected
    return None

def seed_tracker():
    db = SessionLocal()
    
    print("Clearing target tables...")
    # Using CASCADE to safely wipe operators if they have relations
    db.execute(text("TRUNCATE TABLE operator_onboarding_details, operator_station_mappings, operators, kit_registration_table CASCADE"))
    db.commit()
    
    print("Reading Excel...")
    df = pd.read_excel('sample reports/Kit Tracker Chips.xlsx', header=1)
    df = df.replace({np.nan: None})
    
    inserted_ops = {}
    inserted_kits = {}
    
    for idx, row in df.iterrows():
        station_id = clean_str(row.get('Station ID'))
        if not station_id:
            continue
            
        op_id_str = clean_str(row.get('Operator Id'))
        op_name = clean_str(row.get('Operator Name')) or "Unknown"
        
        # 1. Operator
        op = None
        if op_id_str:
            if op_id_str not in inserted_ops:
                op = Operator(
                    user_code=op_id_str,
                    name=op_name,
                    mobile=clean_str(row.get('Operator Mobile')),
                    security_deposit_status=clean_str(row.get('Security Deposit Status')),
                    security_deposit_date=clean_date(row.get('Security Deposit Date')),
                    status=clean_str(row.get('Operator Status')) or "Inactive",
                    inactive_reason=clean_str(row.get('Inactive Reason')),
                    inactive_date=clean_date(row.get('Inactive Date'))
                )
                db.add(op)
                db.flush()
                inserted_ops[op_id_str] = op
            else:
                op = inserted_ops[op_id_str]
                
        # 2. Kit Registration
        if station_id not in inserted_kits:
            kit = KitRegistration(
                station_id=station_id,
                district=clean_str(row.get('District')),
                machine_id=clean_str(row.get('Machine ID')),
                laptop_serial_no=clean_str(row.get('Laptop Serial No.')),
                laptop_name=clean_str(row.get('Laptop Name')),
                station_id_provided_date=clean_date(row.get('Station ID  Allotted Date')),
                l1_status_id=map_status(row.get('L1 Status')),
                l1_done_date=clean_date(row.get('L1 Date')),
                l2_status_id=map_status(row.get('L2 Status')),
                l2_done_date=clean_date(row.get('L2 Date')),
                block=clean_str(row.get('Block')),
                category=clean_str(row.get('Category')),
                locality=clean_str(row.get('Locality')),
                ask_address=clean_str(row.get('ASK Address')),
                station_status=clean_str(row.get('Station Status'))
            )
            db.add(kit)
            db.flush()
            inserted_kits[station_id] = kit
            
        # 3. Mapping and Onboarding
        if op:
            mapping = OperatorStationMapping(
                operator_id=op.id,
                station_id=station_id,
                mapped_at=datetime.now()
            )
            db.add(mapping)
            db.flush()
            
            onboarding = OperatorOnboardingDetail(
                mapping_id=mapping.id,
                operator_id=op.id,
                station_id=station_id,
                onboarding_status=clean_str(row.get('Onboarding Status')) or "Inactive",
                onboard_date=clean_date(row.get('Onboard Date')),
                ask_kit_working_status=clean_str(row.get('Kit Working')) or "Inactive",
                permitted_18_plus=clean_str(row.get('18+ Permit')) or "No",
                visit_status=clean_str(row.get('Visit Status')),
                visit_date=clean_date(row.get('Visit Date')),
                remark=clean_str(row.get('Remark'))
            )
            db.add(onboarding)
            db.flush()
            
    db.commit()
    db.close()
    print(f"Kit Tracker Seeding Complete! Seeded {len(inserted_kits)} kits and {len(inserted_ops)} operators.")

if __name__ == "__main__":
    seed_tracker()
