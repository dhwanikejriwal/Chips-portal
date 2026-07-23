import os
import sys
import pandas as pd
from datetime import datetime, date
import numpy as np

sys.path.append(os.getcwd())

from backend.database import SessionLocal
from backend.models.kit_registration import KitRegistration
from backend.models.operator import Operator
from backend.models.operator_station_mapping import OperatorStationMapping
from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
from backend.models.master_status import MasterStatus
from backend.models.district import District

def get_status_name(status_id, statuses_dict):
    return statuses_dict.get(status_id, "Pending")

def calculate_pending_days(start_date):
    if not start_date:
        return ""
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    delta = date.today() - start_date
    return f"{delta.days} Days pending"

def is_lwe_district(district_name):
    if not district_name:
        return "No"
    
    d = str(district_name).lower().strip()
    
    lwe_aliases = [
        "bastar", "baster",
        "bijapur",
        "dantewada", "dakshin bastar", "dakshin bastar dantewada",
        "kanker", "uttar bastar", "uttar bastar kanker",
        "narayanpur",
        "sukma",
        "mohla-manpur-chowki", "mohla manpur ambagarh chowki", "mohla manpur", "mohla-manpur-ambagarh chouki"
    ]
    
    for alias in lwe_aliases:
        if alias in d:
            return "Yes"
    return "No"

def generate_reports():
    db = SessionLocal()
    os.makedirs('scripts/reports', exist_ok=True)
    
    statuses = {s.id: s.name for s in db.query(MasterStatus).all()}
    
    # Pre-fetch data
    kits = db.query(KitRegistration).all()
    operators = db.query(Operator).all()
    mappings = db.query(OperatorStationMapping).all()
    onboardings = db.query(OperatorOnboardingDetail).all()
    districts_list = db.query(District).all()
    
    mapping_dict = {m.station_id: m for m in mappings}
    op_dict = {o.id: o for o in operators}
    onb_dict = {o.station_id: o for o in onboardings}
    dist_dict = {d.district_code: d.district_name for d in districts_list}
    
    # 1. L1 Pending List
    l1_data = []
    sr_no = 1
    for k in kits:
        status_name = get_status_name(k.l1_status_id, statuses)
        if status_name.lower() not in ['done', 'approved', 'yes']:
            l1_data.append({
                "SR No.": sr_no,
                "District": k.district,
                "Is LWE District": is_lwe_district(k.district),
                "Kit Slot": k.category,
                "Station ID": k.station_id,
                "Station ID Provided Date": k.station_id_provided_date,
                "L1 Status": "No",
                "L1 Status Date /(Pending days)": calculate_pending_days(k.station_id_provided_date)
            })
            sr_no += 1
    pd.DataFrame(l1_data).to_excel('scripts/reports/L1 Pending List.xlsx', index=False)
    
    # 2. L2 Pending List
    l2_data = []
    sr_no = 1
    for k in kits:
        l1_name = get_status_name(k.l1_status_id, statuses)
        l2_name = get_status_name(k.l2_status_id, statuses)
        if l1_name.lower() in ['done', 'approved', 'yes'] and l2_name.lower() not in ['done', 'approved', 'yes']:
            l2_data.append({
                "SR No.": sr_no,
                "District": k.district,
                "Is LWE District": is_lwe_district(k.district),
                "Kit Slot": k.category,
                "Station Id": k.station_id,
                "Machine Id": k.machine_id,
                "Laptop Serial No.": k.laptop_serial_no,
                "Laptop Name": k.laptop_name,
                "Station ID Provided Date": k.station_id_provided_date,
                "L1 Status": "Yes",
                "L1 Done Date": k.l1_done_date,
                "L2 Status": l2_name,
                "L2 Done Date /(Pending days)": calculate_pending_days(k.l1_done_date),
                "Current Stay Status": l2_name
            })
            sr_no += 1
    pd.DataFrame(l2_data).to_excel('scripts/reports/L2 Pending List.xlsx', index=False)
    
    # 3. Operator List
    op_data = []
    sr_no = 1
    for o in operators:
        # Find kit for this operator
        op_mapping = [m for m in mappings if m.operator_id == o.id]
        kit = next((k for k in kits if op_mapping and k.station_id == op_mapping[0].station_id), None)
        
        dist_name = kit.district if kit else dist_dict.get(o.district_id, "")
        
        op_data.append({
            "SR No.": sr_no,
            "District": dist_name,
            "Is LWE District": is_lwe_district(dist_name),
            "Operator Name": o.name,
            "Operator Id": o.user_code,
            "Operator Mobile": o.mobile,
            "SD Status": o.security_deposit_status,
            "Security Deposit Date": o.security_deposit_date,
            "Block": kit.block if kit else "",
            "Location Category": kit.category if kit else "",
            "Locality": kit.locality if kit else "",
            "ASK (Aadhaar Sewa Kendra) Address": kit.ask_address if kit else "",
            "Operator Activation Status (User Credentials Created)": o.status,
            "Operator In-active Reason": o.inactive_reason,
            "Operator In-active Date": o.inactive_date,
            "NSEIT Certificate No": o.nseit_certificate_number,
            "Certificate Issue Date": o.nseit_certification_date,
            "Certificate Validity": o.nseit_certificate_expiry_date,
            "Create Date": o.created_at,
            "Update Date": o.updated_at
        })
        sr_no += 1
    pd.DataFrame(op_data).to_excel('scripts/reports/Operator List.xlsx', index=False)
    
    # 4. Onboard Pending List
    onb_data = []
    sr_no = 1
    for k in kits:
        l2_name = get_status_name(k.l2_status_id, statuses)
        if l2_name.lower() in ['done', 'approved', 'yes']:
            onb = onb_dict.get(k.station_id)
            status_onb = onb.onboarding_status if onb else "Pending"
            if status_onb.lower() not in ['done', 'active', 'yes']:
                onb_data.append({
                    "SR No.": sr_no,
                    "District": k.district,
                    "Is LWE District": is_lwe_district(k.district),
                    "Kit Slot": k.category,
                    "Station Id": k.station_id,
                    "Machine Id": k.machine_id,
                    "Laptop Serial No.": k.laptop_serial_no,
                    "Laptop Name": k.laptop_name,
                    "Station ID Provided Date": k.station_id_provided_date,
                    "L1 Status": "Yes",
                    "L1 Done Date": k.l1_done_date,
                    "L2 Status": "Yes",
                    "L2 Done Date": k.l2_done_date,
                    "On-Boarding Status": status_onb,
                    "On-Boarding Date /(Pending days)": calculate_pending_days(k.l2_done_date)
                })
                sr_no += 1
    pd.DataFrame(onb_data).to_excel('scripts/reports/Onboard Pending List.xlsx', index=False)
    
    # 5. District wise kit count
    # Aggregate data by District
    districts = set([k.district for k in kits if k.district])
    dist_data = []
    sr_no = 1
    for d in districts:
        d_kits = [k for k in kits if k.district == d]
        
        # We need to map to the multi-header, but pandas doesn't do multi-header well without MultiIndex.
        # We'll just create a flat dictionary that matches the column order of the template.
        sd_yes = 0
        sd_pending = 0
        sd_camp = 0
        
        l1_yes = 0
        l1_no = 0
        l2_yes = 0
        l2_no = 0
        l2_chips = 0
        l2_uidai = 0
        
        op_active = 0
        op_inactive = 0
        onb_active = 0
        onb_inactive = 0
        
        st_active = 0
        st_inactive = 0
        ask_active = 0
        ask_inactive = 0
        
        for k in d_kits:
            # L1
            l1_name = get_status_name(k.l1_status_id, statuses).lower()
            if l1_name in ['done', 'yes', 'approved']: l1_yes += 1
            else: l1_no += 1
            
            # L2
            l2_name = get_status_name(k.l2_status_id, statuses).lower()
            if l2_name in ['done', 'yes', 'approved']: l2_yes += 1
            elif 'chips' in l2_name: l2_chips += 1
            elif 'uidai' in l2_name: l2_uidai += 1
            else: l2_no += 1
            
            # Status
            if (k.station_status or '').lower() == 'active': st_active += 1
            else: st_inactive += 1
            
            # OP and ONB
            mapping = mapping_dict.get(k.station_id)
            if mapping:
                op = op_dict.get(mapping.operator_id)
                if op:
                    if op.security_deposit_status == 'Yes': sd_yes += 1
                    elif op.security_deposit_status == 'Camp': sd_camp += 1
                    else: sd_pending += 1
                    
                    if (op.status or '').lower() == 'active': op_active += 1
                    else: op_inactive += 1
                    
                onb = onb_dict.get(k.station_id)
                if onb:
                    if (onb.onboarding_status or '').lower() == 'active': onb_active += 1
                    else: onb_inactive += 1
                    
                    if (onb.ask_kit_working_status or '').lower() == 'active': ask_active += 1
                    else: ask_inactive += 1
                else:
                    onb_inactive += 1
                    ask_inactive += 1
            else:
                sd_pending += 1
                op_inactive += 1
                onb_inactive += 1
                ask_inactive += 1
                
        dist_data.append({
            "S.No": sr_no,
            "District": d,
            "Is LWE District": is_lwe_district(d),
            "Total Machine": len(d_kits),
            "Alloted Station Id": len(d_kits),
            
            "Security Deposit (Camp)": sd_camp,
            "Security Deposit (Yes)": sd_yes,
            "Security Deposit (Pending)": sd_pending,
            
            "L1 Status (No)": l1_no,
            "L1 Status (Yes)": l1_yes,
            
            "L2 Status (No)": l2_no,
            "L2 Status (Yes)": l2_yes,
            "L2 Status (Send to CHiPS)": l2_chips,
            "L2 Status (Send to UIDAI)": l2_uidai,
            
            "Operator Activation (Active)": op_active,
            "Operator Activation (Inactive SentToChips)": op_inactive,
            
            "Operator Onboarding (Active)": onb_active,
            "Operator Onboarding (Inactive)": onb_inactive,
            
            "Station ID Status (Active)": st_active,
            "Station ID Status (Inactive)": st_inactive,
            
            "ASK Kit Working Status (Active)": ask_active,
            "ASK Kit Working Status (Inactive)": ask_inactive,
        })
        sr_no += 1
        
    df_dist = pd.DataFrame(dist_data)
    
    # We can write it out simply
    df_dist.to_excel('scripts/reports/District wise kit count.xlsx', index=False)
    
    print("Reports generated in scripts/reports/")

if __name__ == '__main__':
    generate_reports()
