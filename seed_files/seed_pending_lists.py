import os
import sys

# Ensure root project directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.getcwd())

import pandas as pd
from datetime import datetime
import numpy as np

from backend.database import SessionLocal
from backend.models.kit_registration import KitRegistration
from backend.models.operator import Operator
from backend.models.operator_station_mapping import OperatorStationMapping
from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
from sqlalchemy.orm.exc import NoResultFound

def clean_date(d):
    if pd.isna(d) or d == '-' or not d:
        return None
    try:
        if isinstance(d, datetime):
            return d.date()
        return pd.to_datetime(d, format='mixed').date()
    except:
        return None

def clean_str(s):
    if pd.isna(s) or s == '-':
        return None
    return str(s).strip()

def map_status(status_str):
    if not status_str: return None
    s = str(status_str).lower()
    if 'done' in s or 'approved' in s or 'yes' in s: return 3
    if 'pending' in s or 'no' in s: return 1
    if 'rejected' in s: return 4
    return None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run():
    db = SessionLocal()
    
    l1_file = os.path.join(BASE_DIR, 'sample reports', 'L1 Pending List (1) chips.xlsx')
    l2_file = os.path.join(BASE_DIR, 'sample reports', 'L2 Pending List (1) chips.xlsx')
    op_file = os.path.join(BASE_DIR, 'sample reports', 'Operator List (2) chips.xlsx')
    onboard_file = os.path.join(BASE_DIR, 'sample reports', 'Onboard Pending List (1) chips.xlsx')

    for fname, path in [('L1 List', l1_file), ('L2 List', l2_file), ('Operator List', op_file), ('Onboard List', onboard_file)]:
        if not os.path.exists(path):
            print(f"Warning: File '{fname}' not found at '{path}'. Skipping {fname}.")
            db.close()
            return
    
    # Existing Kits
    existing_kits = {k[0] for k in db.query(KitRegistration.station_id).all()}
    
    # Process L1
    df_l1 = pd.read_excel(l1_file, header=1)
    df_l1 = df_l1.replace({np.nan: None})
    added_kits = 0
    for idx, row in df_l1.iterrows():
        station_id = clean_str(row.get('Station ID') or row.get('Station Id'))
        if not station_id: continue
        if station_id not in existing_kits:
            kit = KitRegistration(
                station_id=station_id,
                district=clean_str(row.get('District')),
                category=clean_str(row.get('Kit Slot')),
                station_id_provided_date=clean_date(row.get('Station ID Provided Date')),
                l1_status_id=map_status(row.get('L1 Status'))
            )
            db.add(kit)
            existing_kits.add(station_id)
            added_kits += 1
            
    # Process L2
    df_l2 = pd.read_excel(l2_file, header=1)
    df_l2 = df_l2.replace({np.nan: None})
    for idx, row in df_l2.iterrows():
        station_id = clean_str(row.get('Station ID') or row.get('Station Id'))
        if not station_id: continue
        if station_id not in existing_kits:
            kit = KitRegistration(
                station_id=station_id,
                district=clean_str(row.get('District')),
                category=clean_str(row.get('Kit Slot')),
                machine_id=clean_str(row.get('Machine Id')),
                laptop_serial_no=clean_str(row.get('Laptop Serial No.')),
                laptop_name=clean_str(row.get('Laptop Name')),
                station_id_provided_date=clean_date(row.get('Station ID Provided Date')),
                l1_status_id=map_status(row.get('L1 Status')),
                l1_done_date=clean_date(row.get('L1 Done Date')),
                l2_status_id=map_status(row.get('L2 Status')),
                l2_done_date=clean_date(row.get('L2 Done Date'))
            )
            db.add(kit)
            existing_kits.add(station_id)
            added_kits += 1

    # Process Operators
    from backend.models.district import District
    districts = db.query(District).all()
    dist_map = {d.district_name.lower().strip(): d.district_code for d in districts}

    existing_ops = {o[0] for o in db.query(Operator.user_code).all()}
    df_op = pd.read_excel(op_file, header=1)
    df_op = df_op.replace({np.nan: None})
    added_ops = 0
    for idx, row in df_op.iterrows():
        op_id_str = clean_str(row.get('Operator Id'))
        dist_name = clean_str(row.get('District'))
        if not op_id_str: continue
        
        dist_code = dist_map.get(dist_name.lower().strip(), dist_name) if dist_name else None
        
        if op_id_str not in existing_ops:
            op = Operator(
                user_code=op_id_str,
                district_id=dist_code,
                name=clean_str(row.get('Operator Name')) or "Unknown",
                mobile=clean_str(row.get('Operator Mobile')),
                security_deposit_status=clean_str(row.get('SD Status')),
                security_deposit_date=clean_date(row.get('Security Deposit Date')),
                status=clean_str(row.get('Operator Activation Status (User Credentials Created)')) or "Inactive",
                inactive_reason=clean_str(row.get('Operator In-active Reason')),
                inactive_date=clean_date(row.get('Operator In-active Date'))
            )
            db.add(op)
            existing_ops.add(op_id_str)
            added_ops += 1
            
    db.flush()
    
    # Process Onboard Pending List
    df_onb = pd.read_excel(onboard_file, header=1)
    df_onb = df_onb.replace({np.nan: None})
    added_onb = 0
    
    for idx, row in df_onb.iterrows():
        station_id = clean_str(row.get('Station ID') or row.get('Station Id'))
        if not station_id: continue
        
        # See if there's a mapping
        mapping = db.query(OperatorStationMapping).filter_by(station_id=station_id).first()
        if mapping:
            existing_onb = db.query(OperatorOnboardingDetail).filter_by(
                station_id=station_id, 
                operator_id=mapping.operator_id
            ).first()
            if not existing_onb:
                onb = OperatorOnboardingDetail(
                    mapping_id=mapping.id,
                    operator_id=mapping.operator_id,
                    station_id=station_id,
                    onboarding_status=clean_str(row.get('On-Boarding Status')) or "Pending",
                    onboard_date=clean_date(row.get('On-Boarding Date /(Pending days)')),
                    ask_kit_working_status="Unknown",
                    permitted_18_plus="Unknown"
                )
                db.add(onb)
                added_onb += 1
    
    from sqlalchemy import text
    try:
        for tbl in ['kit_registration_table', 'operators', 'operator_onboarding_details', 'operator_station_mappings']:
            db.execute(text(f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), COALESCE((SELECT MAX(id) FROM {tbl}), 0) + 1, false);"))
    except Exception:
        db.rollback()

    db.commit()
    db.close()
    print(f"Added kits: {added_kits}, Added ops: {added_ops}, Added onboardings: {added_onb}")

if __name__ == '__main__':
    run()
