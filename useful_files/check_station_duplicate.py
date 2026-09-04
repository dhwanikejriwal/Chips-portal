import os
import sys
import json
import collections
import urllib3
import requests
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = os.getenv("EXTERNAL_PORTAL_API_URL", "")
API_KEY = os.getenv("EXTERNAL_PORTAL_API_KEY", "")

print("=" * 80)
print(" COMPREHENSIVE AUDIT OF ALL API RECORDS ACROSS ALL SECTIONS")
print(f" Source URL: {API_URL}")
print("=" * 80)

headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {API_KEY}" if not API_KEY.startswith("Bearer ") else API_KEY,
    "X-API-Key": API_KEY
}

try:
    print("[*] Fetching live payload from government API...")
    resp = requests.get(API_URL, headers=headers, timeout=30, verify=False)
    resp.raise_for_status()
    payload = resp.json()
except Exception as e:
    print(f"[-] Error connecting to API: {e}")
    sys.exit(1)

kits = payload.get("kits_details", [])
operators = payload.get("operators", [])
onboard = payload.get("onboard_details", [])

print(f"[OK] Payload received successfully:")
print(f"     - Kits Details:       {len(kits):,} records")
print(f"     - Operators:          {len(operators):,} records")
print(f"     - Onboarding Details: {len(onboard):,} records")
print("=" * 80)

def find_duplicates(items, key_func, name):
    counts = collections.defaultdict(list)
    for idx, item in enumerate(items):
        key = key_func(item)
        if key:
            counts[key].append((idx, item))
    dups = {k: v for k, v in counts.items() if len(v) > 1}
    return dups

# ─────────────────────────────────────────────────────────────
# 1. KITS DETAILS AUDIT
# ─────────────────────────────────────────────────────────────
print("\n[SECTION 1: KITS DETAILS AUDIT]")
print(f"Total Rows: {len(kits)}")

# Check duplicate station_id
dup_station = find_duplicates(kits, lambda k: str(k.get("station_id") or "").strip() or None, "station_id")
if dup_station:
    print(f"  [WARN] Duplicate station_id found: {len(dup_station)} unique ID(s) repeated across {sum(len(v) for v in dup_station.values())} rows")
    for sid, occurrences in dup_station.items():
        print(f"\n  --> Station ID '{sid}' appears {len(occurrences)} times:")
        for idx, item in occurrences:
            print(f"      Row {idx+1}: Provided Date={item.get('station_id_provided_date')}, Status={item.get('station_id_status')}, District={item.get('district_code')}")
        # Print differing fields
        first = occurrences[0][1]
        for idx, other in occurrences[1:]:
            diffs = [f"{k}: '{first.get(k)}' vs '{other.get(k)}'" for k in set(first) | set(other) if first.get(k) != other.get(k)]
            if diffs:
                print(f"      Field Differences: {', '.join(diffs)}")
else:
    print("  [OK] station_id: 100% Unique (Zero duplicates)")

# Check duplicate machine_id
dup_machine = find_duplicates(kits, lambda k: str(k.get("machine_id") or "").strip() or None, "machine_id")
if dup_machine:
    print(f"\n  [INFO] Duplicate machine_id found: {len(dup_machine)} machine(s) shared across kits:")
    for mid, occ in list(dup_machine.items())[:5]:
        sids = [o[1].get('station_id') for o in occ]
        print(f"      Machine '{mid}' associated with {len(occ)} station IDs: {sids}")
    if len(dup_machine) > 5:
        print(f"      ... and {len(dup_machine) - 5} more shared machine IDs")
else:
    print("  [OK] machine_id: 100% Unique")

# Check duplicate laptop_serial_no
dup_laptop = find_duplicates(kits, lambda k: str(k.get("laptop_serial_no") or "").strip() or None, "laptop_serial_no")
if dup_laptop:
    print(f"\n  [INFO] Duplicate laptop_serial_no found: {len(dup_laptop)} laptop serial(s) shared across kits:")
    for sn, occ in list(dup_laptop.items())[:5]:
        sids = [o[1].get('station_id') for o in occ]
        print(f"      Laptop SN '{sn}' associated with {len(occ)} station IDs: {sids}")
    if len(dup_laptop) > 5:
        print(f"      ... and {len(dup_laptop) - 5} more shared serial numbers")
else:
    print("  [OK] laptop_serial_no: 100% Unique")

# ─────────────────────────────────────────────────────────────
# 2. OPERATORS AUDIT
# ─────────────────────────────────────────────────────────────
print("\n" + "-" * 80)
print("[SECTION 2: OPERATORS AUDIT]")
print(f"Total Rows: {len(operators)}")

# Check duplicate operator_code / Operator Id
dup_op_codes = find_duplicates(operators, lambda o: str(o.get("operator_code") or o.get("Operator Id") or "").strip() or None, "operator_code")
if dup_op_codes:
    print(f"  [WARN] Duplicate operator_code found: {len(dup_op_codes)} operator ID(s) repeated:")
    for opc, occ in dup_op_codes.items():
        print(f"      Operator '{opc}' appears {len(occ)} times: names={[o[1].get('operator_name') or o[1].get('name') for o in occ]}")
else:
    print("  [OK] operator_code: 100% Unique (Zero duplicates)")

# Check duplicate mobile numbers
dup_mobiles = find_duplicates(operators, lambda o: str(o.get("mobile") or "").strip() or None, "mobile")
if dup_mobiles:
    print(f"  [INFO] Duplicate mobile numbers found: {len(dup_mobiles)} mobile number(s) shared among multiple operators:")
    for mob, occ in list(dup_mobiles.items())[:5]:
        ops = [f"{o[1].get('operator_code') or o[1].get('Operator Id')} ({o[1].get('operator_name') or o[1].get('name')})" for o in occ]
        print(f"      Mobile '{mob}' shared by: {', '.join(ops)}")
    if len(dup_mobiles) > 5:
        print(f"      ... and {len(dup_mobiles) - 5} more shared mobiles")
else:
    print("  [OK] mobile: 100% Unique")

# ─────────────────────────────────────────────────────────────
# 3. ONBOARDING DETAILS AUDIT
# ─────────────────────────────────────────────────────────────
print("\n" + "-" * 80)
print("[SECTION 3: ONBOARDING DETAILS AUDIT]")
print(f"Total Rows: {len(onboard)}")

# Check duplicate station_id in onboarding
dup_onb_station = find_duplicates(onboard, lambda b: str(b.get("station_id") or "").strip() or None, "station_id")
if dup_onb_station:
    print(f"  [WARN] Duplicate station_id found in onboarding: {len(dup_onb_station)} station(s):")
    for sid, occ in dup_onb_station.items():
        print(f"      Station '{sid}' appears {len(occ)} times in onboarding rows.")
else:
    print("  [OK] station_id in onboarding: 100% Unique (Zero duplicates)")

# Check duplicate operator_code in onboarding
dup_onb_op = find_duplicates(onboard, lambda b: str(b.get("operator_code") or "").strip() or None, "operator_code")
if dup_onb_op:
    print(f"  [INFO] Multiple station mappings for single operator: {len(dup_onb_op)} operator(s) mapped to multiple stations:")
    for opc, occ in list(dup_onb_op.items())[:5]:
        sids = [o[1].get("station_id") for o in occ]
        print(f"      Operator '{opc}' mapped to {len(sids)} stations: {sids}")
    if len(dup_onb_op) > 5:
        print(f"      ... and {len(dup_onb_op) - 5} more operators with multiple station mappings")
else:
    print("  [OK] operator_code in onboarding: 100% Unique")

# ─────────────────────────────────────────────────────────────
# 4. CROSS-DATASET INTEGRITY AUDIT
# ─────────────────────────────────────────────────────────────
print("\n" + "-" * 80)
print("[SECTION 4: CROSS-DATASET INTEGRITY]")

all_kit_stations = {str(k.get("station_id")).strip() for k in kits if k.get("station_id")}
all_onb_stations = {str(b.get("station_id")).strip() for b in onboard if b.get("station_id")}
all_op_ids = {str(o.get("operator_code") or o.get("Operator Id")).strip() for o in operators if o.get("operator_code") or o.get("Operator Id")}
all_onb_ops = {str(b.get("operator_code")).strip() for b in onboard if b.get("operator_code")}

orphan_onb_stations = all_onb_stations - all_kit_stations
orphan_onb_ops = all_onb_ops - all_op_ids

print(f"  - Onboarding records without a matching Kit:     {len(orphan_onb_stations)}")
if orphan_onb_stations:
    print(f"    Sample unmatched stations: {list(orphan_onb_stations)[:5]}")

print(f"  - Onboarding records without a matching Operator: {len(orphan_onb_ops)}")
if orphan_onb_ops:
    print(f"    Sample unmatched operators: {list(orphan_onb_ops)[:5]}")

print(f"  - Kits with NO onboarding records:               {len(all_kit_stations - all_onb_stations)}")

# ─────────────────────────────────────────────────────────────
# 5. SUMMARY
# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print(" COMPLETE AUDIT SUMMARY:")
print("=" * 80)
print(f" 1. Primary Key Duplicates (Direct Root Cause of sync re-update):")
print(f"    - Kits Details (station_id duplicates):       {list(dup_station.keys()) if dup_station else 'NONE'}")
print(f"    - Operators (operator_code duplicates):      {list(dup_op_codes.keys()) if dup_op_codes else 'NONE'}")
print(f"    - Onboarding (station_id duplicates):        {list(dup_onb_station.keys()) if dup_onb_station else 'NONE'}")
print(f" 2. Shared Assets in Payload:")
print(f"    - Machine IDs shared by >1 kit:              {len(dup_machine)}")
print(f"    - Laptop Serial Numbers shared by >1 kit:    {len(dup_laptop)}")
print(f"    - Mobile numbers shared by >1 operator:      {len(dup_mobiles)}")
print("=" * 80)
