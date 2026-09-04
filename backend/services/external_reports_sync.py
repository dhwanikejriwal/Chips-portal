"""
External Reports Data Synchronization Service
============================================
Pulls operational kit, operator, and onboarding status updates from the external
portal via REST API and upserts them into CHiPS PostgreSQL database.

Enables one-way, automated synchronization with zero downtime and replaces
manual Excel sheet seeding (seed_kit_tracker.py & seed_pending_lists.py).

Usage:
    # Run from CLI as dry run (no changes written to DB):
    python -m backend.services.external_reports_sync --dry-run

    # Run live sync from CLI:
    python -m backend.services.external_reports_sync

    # Import in router:
    from backend.services.external_reports_sync import sync_reports_data_from_external
"""
import os
import sys
import logging
import argparse
from datetime import datetime, date, timezone
from typing import Dict, Any, Optional, List

import requests
from sqlalchemy.orm import Session
from sqlalchemy import select

# Ensure project root is in path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.database import SessionLocal
from backend.models.kit_registration import KitRegistration
from backend.models.operator import Operator
from backend.models.operator_station_mapping import OperatorStationMapping
from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
from backend.models.master_status import MasterStatus
from backend.utils.district_mapper import normalize_district_name

logger = logging.getLogger("reports_sync")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

EXTERNAL_PORTAL_API_URL = os.getenv("EXTERNAL_PORTAL_API_URL", "https://api.externalportal.gov.in").rstrip("/")
EXTERNAL_PORTAL_API_KEY = os.getenv("EXTERNAL_PORTAL_API_KEY", "")
EXTERNAL_PORTAL_TIMEOUT = int(os.getenv("EXTERNAL_PORTAL_TIMEOUT_SECONDS", "30"))


def parse_date_val(d: Any) -> Optional[date]:
    """Safely converts various date representations to a python date object."""
    if not d or str(d).strip() in ("", "-", "None", "null"):
        return None
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    val_str = str(d).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(val_str[:10], fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def parse_clean_str(s: Any) -> Optional[str]:
    """Cleans strings, converting empty or placeholder strings to None."""
    if s is None:
        return None
    val = str(s).strip()
    if val in ("", "-", "None", "null", "NaN"):
        return None
    return val


def map_status_to_id(status_val: Any, is_l2: bool = False) -> Optional[int]:
    """
    Exact status mapping aligned with seed_kit_tracker.py and seed_pending_lists.py:
    'uidai'    -> 6  (Sent to UIDAI)
    'chips'    -> 5  (Sent to CHiPS)
    'done'     -> 19 (L1 Done) / 20 (L2 Done) / 18 (Done)
    'approved' or 'yes' -> 2 (Approved)
    'pending'  or 'no'  -> 1 (Pending)
    'rejected' -> 14 (Rejected)
    """
    if not status_val:
        return 1  # Pending
    s = str(status_val).lower().strip()
    if 'uidai' in s:
        return 6
    if 'chips' in s:
        return 5
    if 'l2 done' in s or 'l2_done' in s:
        return 20
    if 'l1 done' in s or 'l1_done' in s:
        return 19
    if 'done' in s:
        return 20 if is_l2 else 19
    if 'approved' in s or s == 'yes':
        return 2
    if 'pending' in s or s == 'no':
        return 1
    if 'rejected' in s:
        return 14
    return 1


def extract_payload_anomalies(raw_kits: List[Dict[str, Any]], raw_ops: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Audits incoming external portal payload and extracts data anomalies:
    1. Duplicate station_id occurrences in kits_details.
    2. machine_id shared across multiple distinct station IDs.
    3. laptop_serial_no shared across multiple distinct station IDs.
    4. mobile numbers shared across multiple operators.
    """
    import collections
    anomalies = {
        "duplicate_stations": [],
        "shared_machines": [],
        "shared_laptops": [],
        "shared_mobiles": []
    }

    # 1. Duplicate station_id in kits
    station_map = collections.defaultdict(list)
    for idx, item in enumerate(raw_kits):
        sid = parse_clean_str(item.get("station_id"))
        if sid:
            station_map[sid].append((idx + 1, item))
    for sid, occ in station_map.items():
        if len(occ) > 1:
            diffs = []
            first = occ[0][1]
            for _, other in occ[1:]:
                for k in set(first) | set(other):
                    if first.get(k) != other.get(k):
                        diffs.append(f"{k}: '{first.get(k)}' vs '{other.get(k)}'")
            anomalies["duplicate_stations"].append({
                "station_id": sid,
                "count": len(occ),
                "rows": [
                    {
                        "row": o[0],
                        "provided_date": str(o[1].get("station_id_provided_date") or o[1].get("station_id_allotted_date") or "N/A"),
                        "status": str(o[1].get("station_id_status") or o[1].get("station_status") or "A"),
                        "district": str(o[1].get("district_code") or o[1].get("district") or "N/A")
                    }
                    for o in occ
                ],
                "diffs": list(set(diffs))
            })

    # 2. Shared machine_id across distinct station IDs
    machine_map = collections.defaultdict(set)
    for item in raw_kits:
        mid = parse_clean_str(item.get("machine_id"))
        sid = parse_clean_str(item.get("station_id"))
        if mid and sid:
            machine_map[mid].add(sid)
    for mid, sids in machine_map.items():
        if len(sids) > 1:
            anomalies["shared_machines"].append({
                "machine_id": mid,
                "station_ids": sorted(list(sids))
            })

    # 3. Shared laptop_serial_no across distinct station IDs
    laptop_map = collections.defaultdict(set)
    for item in raw_kits:
        sn = parse_clean_str(item.get("laptop_serial_no"))
        sid = parse_clean_str(item.get("station_id"))
        if sn and sid:
            laptop_map[sn].add(sid)
    for sn, sids in laptop_map.items():
        if len(sids) > 1:
            anomalies["shared_laptops"].append({
                "laptop_serial_no": sn,
                "station_ids": sorted(list(sids))
            })

    # 4. Shared mobile across operators
    mobile_map = collections.defaultdict(set)
    for item in raw_ops:
        mob = parse_clean_str(item.get("mobile"))
        op_code = parse_clean_str(item.get("operator_code") or item.get("Operator Id"))
        op_name = parse_clean_str(item.get("operator_name") or item.get("name")) or ""
        if mob and op_code:
            mobile_map[mob].add(f"{op_code} ({op_name})" if op_name else op_code)
    for mob, ops in mobile_map.items():
        if len(ops) > 1:
            anomalies["shared_mobiles"].append({
                "mobile": mob,
                "operators": sorted(list(ops))
            })

    return anomalies


def sync_reports_data_from_external(
    db: Session,
    updated_after: Optional[datetime] = None,
    dry_run: bool = False,
    max_pages: int = 50,
    exact_mirror: bool = True
) -> Dict[str, Any]:
    """
    Executes a one-way pull from the external portal's kit tracker sync API
    and idempotently upserts kits, operators, mappings, and onboarding details.
    When exact_mirror=True, entries in the local database that are no longer
    present in the external portal payload are pruned.
    """
    auth_header = EXTERNAL_PORTAL_API_KEY
    if auth_header and not auth_header.startswith("Bearer "):
        auth_header = f"Bearer {auth_header}"

    headers = {
        "Accept": "application/json",
        "Authorization": auth_header,
        "X-API-Key": EXTERNAL_PORTAL_API_KEY
    }

    endpoint = f"{EXTERNAL_PORTAL_API_URL}"
    # If the configured URL is the base URL without endpoint path, append default
    if not any(endpoint.endswith(s) for s in ("get-kit-details", "kit-tracker", "sync")):
        endpoint = f"{endpoint}/api/kit-data/get-kit-details"

    params: Dict[str, Any] = {}
    if updated_after:
        params["updated_after"] = updated_after.isoformat()

    stats = {
        "kits_created": 0,
        "kits_updated": 0,
        "kits_pruned": 0,
        "operators_created": 0,
        "operators_updated": 0,
        "operators_pruned": 0,
        "mappings_created": 0,
        "mappings_pruned": 0,
        "onboarding_created": 0,
        "onboarding_updated": 0,
        "anomalies": {
            "duplicate_stations": [],
            "shared_machines": [],
            "shared_laptops": [],
            "shared_mobiles": []
        },
        "dry_run": dry_run,
        "exact_mirror": exact_mirror,
        "synced_at": datetime.now(timezone.utc).isoformat()
    }

    # Pre-cache existing lookups to minimize round-trips
    from backend.models.district import District
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    dist_records = db.query(District).all()
    # Map both district_code (string/int) and district_name (all aliases) to district objects
    dist_by_code = {str(d.district_code).strip(): d for d in dist_records if d.district_code}
    dist_by_name = {}
    for d in dist_records:
        if d.district_name:
            dist_by_name[d.district_name.lower().strip()] = d
            norm = normalize_district_name(d.district_name)
            if norm:
                dist_by_name[norm.lower().strip()] = d
        if d.district_short_name:
            dist_by_name[d.district_short_name.lower().strip()] = d

    existing_kits = {k.station_id: k for k in db.query(KitRegistration).all() if k.station_id}
    existing_ops = {o.user_code: o for o in db.query(Operator).all() if o.user_code}
    existing_mappings = {m.station_id: m for m in db.query(OperatorStationMapping).all() if m.station_id}
    existing_onboard = {b.station_id: b for b in db.query(OperatorOnboardingDetail).all() if b.station_id}

    logger.info(f"Connecting to live API at: {endpoint} (dry_run={dry_run})...")

    try:
        resp = requests.get(endpoint, headers=headers, params=params, timeout=EXTERNAL_PORTAL_TIMEOUT, verify=False)
        resp.raise_for_status()
        payload = resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"External API request failed: {e}")
        raise

    # -------------------------------------------------------------
    # FORMAT A: Live CG State Portal Payload Structure
    # Top keys: ['operators', 'kits_details', 'onboard_details']
    # -------------------------------------------------------------
    if "kits_details" in payload or "operators" in payload:
        raw_ops = payload.get("operators", [])
        raw_kits = payload.get("kits_details", [])
        raw_onboard = payload.get("onboard_details", [])
        logger.info(f"Received live CG portal dataset: {len(raw_kits)} kits, {len(raw_ops)} operators, {len(raw_onboard)} onboarding rows.")

        # Extract audit anomalies from the live external payload before deduplication
        stats["anomalies"] = extract_payload_anomalies(raw_kits, raw_ops)

        # Deduplicate incoming records by unique identifier to handle duplicate API rows (e.g. repeated station_id)
        deduped_ops = {}
        for item in raw_ops:
            op_code = parse_clean_str(item.get("operator_code") or item.get("Operator Id"))
            if op_code and op_code not in deduped_ops:
                deduped_ops[op_code] = item
        raw_ops = list(deduped_ops.values())

        deduped_kits = {}
        for item in raw_kits:
            sid = parse_clean_str(item.get("station_id"))
            if not sid:
                continue
            if sid not in deduped_kits:
                deduped_kits[sid] = item
            else:
                # Keep the record with latest provided date or richer information
                ex_date = str(deduped_kits[sid].get("station_id_provided_date") or "")
                curr_date = str(item.get("station_id_provided_date") or "")
                if curr_date > ex_date:
                    deduped_kits[sid] = item
        raw_kits = list(deduped_kits.values())

        deduped_onboard = {}
        for item in raw_onboard:
            sid = parse_clean_str(item.get("station_id"))
            if not sid:
                continue
            if sid not in deduped_onboard:
                deduped_onboard[sid] = item
            else:
                if item.get("operator_code") or item.get("onboarding_status"):
                    deduped_onboard[sid] = item
        raw_onboard = list(deduped_onboard.values())

        # 1. Process Operators
        for item in raw_ops:
            op_code = parse_clean_str(item.get("operator_code") or item.get("Operator Id"))
            if not op_code:
                continue

            name = parse_clean_str(item.get("operator_name") or item.get("name")) or "Unknown"
            mobile = parse_clean_str(item.get("mobile"))
            raw_act = parse_clean_str(item.get("active_status") or item.get("status")) or "A"
            status = "Active" if raw_act in ("A", "Active", "1") else "Inactive"

            raw_sd = parse_clean_str(item.get("sd_status") or item.get("security_deposit_status"))
            sd_status = "Yes" if raw_sd in ("Y", "Yes") else ("Challan" if raw_sd == "C" else ("No" if raw_sd == "N" else raw_sd))
            sd_date = parse_date_val(item.get("security_deposit_date"))
            inact_reason = parse_clean_str(item.get("operator_inactive_reason") or item.get("inactive_reason"))
            inact_date = parse_date_val(item.get("operator_inactive_date") or item.get("inactive_date"))

            op = existing_ops.get(op_code)
            if not op:
                op = Operator(
                    user_code=op_code,
                    name=name,
                    mobile=mobile,
                    status=status,
                    security_deposit_status=sd_status,
                    security_deposit_date=sd_date,
                    inactive_reason=inact_reason,
                    inactive_date=inact_date
                )
                if not dry_run:
                    db.add(op)
                    db.flush()
                existing_ops[op_code] = op
                stats["operators_created"] += 1
            else:
                changed = False
                if name and op.name != name: op.name = name; changed = True
                if mobile and op.mobile != mobile: op.mobile = mobile; changed = True
                if status and op.status != status: op.status = status; changed = True
                if sd_status and op.security_deposit_status != sd_status: op.security_deposit_status = sd_status; changed = True
                if sd_date and op.security_deposit_date != sd_date: op.security_deposit_date = sd_date; changed = True
                if inact_reason and op.inactive_reason != inact_reason: op.inactive_reason = inact_reason; changed = True
                if inact_date and op.inactive_date != inact_date: op.inactive_date = inact_date; changed = True
                if changed:
                    stats["operators_updated"] += 1

        # 2. Process Kits
        for item in raw_kits:
            station_id = parse_clean_str(item.get("station_id"))
            if not station_id:
                continue

            dist_code_str = str(item.get("district_code") or "").strip()
            dist_obj = dist_by_code.get(dist_code_str)
            district_name = dist_obj.district_name if dist_obj else None
            if not district_name:
                raw_dist = parse_clean_str(item.get("district"))
                if raw_dist:
                    norm_d = normalize_district_name(raw_dist)
                    d_match = dist_by_name.get(norm_d.lower().strip()) or dist_by_name.get(raw_dist.lower().strip())
                    district_name = d_match.district_name if d_match else norm_d

            machine_id = parse_clean_str(item.get("machine_id"))
            laptop_sn = parse_clean_str(item.get("laptop_serial_no"))
            laptop_name = parse_clean_str(item.get("laptop_name"))
            allotted_date = parse_date_val(item.get("station_id_provided_date") or item.get("station_id_allotted_date"))
            block = str(item.get("block_code") or "").strip() or parse_clean_str(item.get("block"))
            category = str(item.get("category") or "").strip() or parse_clean_str(item.get("kit_slot"))
            locality = "Urban" if item.get("locality") == "U" else ("Rural" if item.get("locality") == "R" else parse_clean_str(item.get("locality")))
            ask_address = parse_clean_str(item.get("ask_address"))
            st_status = "Active" if item.get("station_id_status") == "A" else parse_clean_str(item.get("station_status")) or "Active"

            l1_raw = item.get("l1_machine_reg_status")
            l2_raw = item.get("l2_machine_reg_status")
            l1_id = 19 if l1_raw in ("Y", "1") else 1
            l2_id = 20 if l2_raw in ("Y", "1") else (17 if l2_raw == "STU" else 1)
            l1_date = parse_date_val(item.get("l1_machine_reg_date"))
            l2_date = parse_date_val(item.get("l2_machine_reg_date"))

            kit = existing_kits.get(station_id)
            if not kit:
                kit = KitRegistration(
                    station_id=station_id,
                    district=district_name,
                    machine_id=machine_id,
                    laptop_serial_no=laptop_sn,
                    laptop_name=laptop_name,
                    category=category,
                    block=block,
                    locality=locality,
                    ask_address=ask_address,
                    station_status=st_status,
                    station_id_provided_date=allotted_date,
                    l1_status_id=l1_id,
                    l2_status_id=l2_id,
                    l1_done_date=l1_date,
                    l2_done_date=l2_date
                )
                if not dry_run:
                    db.add(kit)
                    db.flush()
                existing_kits[station_id] = kit
                stats["kits_created"] += 1
            else:
                changed = False
                if district_name and kit.district != district_name: kit.district = district_name; changed = True
                if machine_id and kit.machine_id != machine_id: kit.machine_id = machine_id; changed = True
                if laptop_sn and kit.laptop_serial_no != laptop_sn: kit.laptop_serial_no = laptop_sn; changed = True
                if laptop_name and kit.laptop_name != laptop_name: kit.laptop_name = laptop_name; changed = True
                if category and kit.category != category: kit.category = category; changed = True
                if block and kit.block != block: kit.block = block; changed = True
                if locality and kit.locality != locality: kit.locality = locality; changed = True
                if ask_address and kit.ask_address != ask_address: kit.ask_address = ask_address; changed = True
                if st_status and kit.station_status != st_status: kit.station_status = st_status; changed = True
                if allotted_date and kit.station_id_provided_date != allotted_date: kit.station_id_provided_date = allotted_date; changed = True
                if l1_id and kit.l1_status_id != l1_id: kit.l1_status_id = l1_id; changed = True
                if l2_id and kit.l2_status_id != l2_id: kit.l2_status_id = l2_id; changed = True
                if l1_date and kit.l1_done_date != l1_date: kit.l1_done_date = l1_date; changed = True
                if l2_date and kit.l2_done_date != l2_date: kit.l2_done_date = l2_date; changed = True
                if changed:
                    stats["kits_updated"] += 1

        # 3. Process Onboard & Mappings
        for item in raw_onboard:
            station_id = parse_clean_str(item.get("station_id"))
            op_code = parse_clean_str(item.get("operator_code"))
            if not station_id or not op_code:
                continue

            op = existing_ops.get(op_code)
            kit = existing_kits.get(station_id)
            if not op or not kit:
                continue

            # Ensure operator's district_id is synchronized with their mapped kit
            if kit.district:
                norm_d = normalize_district_name(kit.district)
                d_match = dist_by_name.get(norm_d.lower().strip()) or dist_by_name.get(kit.district.lower().strip())
                if d_match and op.district_id != d_match.district_code:
                    op.district_id = d_match.district_code

            # Mapping
            mapping = existing_mappings.get(station_id)
            if not mapping:
                mapping = OperatorStationMapping(
                    station_id=station_id,
                    operator_id=op.id,
                    mapped_at=datetime.now()
                )
                if not dry_run:
                    db.add(mapping)
                    db.flush()
                existing_mappings[station_id] = mapping
                stats["mappings_created"] += 1
            elif mapping.operator_id != op.id:
                mapping.operator_id = op.id
                if not dry_run:
                    db.flush()

            # Onboarding
            raw_onb = item.get("onboarding_status")
            onb_status = "Active" if raw_onb == "A" else ("Inactive" if raw_onb == "I" else (raw_onb or "Inactive"))
            onb_date = parse_date_val(item.get("onboard_date"))
            perm_18 = "Yes" if item.get("permitted_18_plus") == "Y" else ("No" if item.get("permitted_18_plus") == "N" else "Unknown")
            ask_working = "Working" if item.get("ask_kit_working_status") == "Y" else "Inactive"
            visit_status = "Completed" if item.get("visit_status") == "Y" else ("Pending" if item.get("visit_status") == "N" else None)
            visit_date = parse_date_val(item.get("visit_date"))
            remark = parse_clean_str(item.get("remark"))

            onboard = existing_onboard.get(station_id)
            if not onboard:
                onboard = OperatorOnboardingDetail(
                    mapping_id=mapping.id,
                    operator_id=op.id,
                    station_id=station_id,
                    onboarding_status=onb_status,
                    onboard_date=onb_date,
                    visit_status=visit_status,
                    visit_date=visit_date,
                    remark=remark,
                    ask_kit_working_status=ask_working,
                    permitted_18_plus=perm_18
                )
                if not dry_run:
                    db.add(onboard)
                    db.flush()
                existing_onboard[station_id] = onboard
                stats["onboarding_created"] += 1
            else:
                onb_changed = False
                if mapping and onboard.mapping_id != mapping.id:
                    onboard.mapping_id = mapping.id
                    onb_changed = True
                if op and onboard.operator_id != op.id:
                    onboard.operator_id = op.id
                    onb_changed = True
                if onb_status and onboard.onboarding_status != onb_status:
                    onboard.onboarding_status = onb_status
                    onb_changed = True
                if onb_date and onboard.onboard_date != onb_date:
                    onboard.onboard_date = onb_date
                    onb_changed = True
                if visit_status and onboard.visit_status != visit_status:
                    onboard.visit_status = visit_status
                    onb_changed = True
                if visit_date and onboard.visit_date != visit_date:
                    onboard.visit_date = visit_date
                    onb_changed = True
                if remark and onboard.remark != remark:
                    onboard.remark = remark
                    onb_changed = True
                if ask_working and onboard.ask_kit_working_status != ask_working:
                    onboard.ask_kit_working_status = ask_working
                    onb_changed = True
                if perm_18 and onboard.permitted_18_plus != perm_18:
                    onboard.permitted_18_plus = perm_18
                    onb_changed = True
                if onb_changed:
                    stats["onboarding_updated"] += 1

        # 4. Exact Mirror Pruning Phase (removes obsolete records not present in external portal)
        if exact_mirror:
            api_kit_ids = {str(k.get("station_id")).strip() for k in raw_kits if k.get("station_id")}
            api_op_codes = {str(o.get("operator_code") or o.get("Operator Id")).strip() for o in raw_ops if o.get("operator_code") or o.get("Operator Id")}

            # 4.1 Prune KitRegistrations not in API
            extra_kits = db.query(KitRegistration).filter(~KitRegistration.station_id.in_(api_kit_ids)).all()
            stats["kits_pruned"] = len(extra_kits)
            if not dry_run and extra_kits:
                db.query(KitRegistration).filter(~KitRegistration.station_id.in_(api_kit_ids)).delete(synchronize_session=False)

            # 4.2 Prune Operators not in API
            extra_ops = db.query(Operator).filter(~Operator.user_code.in_(api_op_codes)).all()
            stats["operators_pruned"] = len(extra_ops)
            if not dry_run and extra_ops:
                extra_op_ids = [o.id for o in extra_ops]
                from backend.models.kit_tracker import KitTracker
                db.query(KitTracker).filter(KitTracker.operator_id.in_(extra_op_ids)).update({KitTracker.operator_id: None}, synchronize_session=False)
                db.query(OperatorOnboardingDetail).filter(OperatorOnboardingDetail.operator_id.in_(extra_op_ids)).delete(synchronize_session=False)
                db.query(OperatorStationMapping).filter(OperatorStationMapping.operator_id.in_(extra_op_ids)).delete(synchronize_session=False)
                db.query(Operator).filter(Operator.id.in_(extra_op_ids)).delete(synchronize_session=False)

            # 4.3 Prune Mappings & Onboarding details not in API kit set
            extra_mappings = db.query(OperatorStationMapping).filter(~OperatorStationMapping.station_id.in_(api_kit_ids)).all()
            stats["mappings_pruned"] = len(extra_mappings)
            if not dry_run and extra_mappings:
                db.query(OperatorOnboardingDetail).filter(~OperatorOnboardingDetail.station_id.in_(api_kit_ids)).delete(synchronize_session=False)
                db.query(OperatorStationMapping).filter(~OperatorStationMapping.station_id.in_(api_kit_ids)).delete(synchronize_session=False)

        if not dry_run:
            db.commit()

        logger.info(f"Live sync complete. Stats: {stats}")
        return stats

    # -------------------------------------------------------------
    # FORMAT B: Paginated Unified 'data' array
    # -------------------------------------------------------------
    params["page"] = 1
    params["page_size"] = 200

    while params["page"] <= max_pages:
        records = payload.get("data", [])
        if not records:
            break
        for item in records:
            station_id = parse_clean_str(item.get("station_id") or item.get("Station ID") or item.get("Station Id"))
            if not station_id:
                continue

            # 1. Upsert KitRegistration (Exactly matching seed_kit_tracker & seed_pending_lists)
            kit = existing_kits.get(station_id)
            raw_dist = parse_clean_str(item.get("district") or item.get("District"))
            district_val = None
            if raw_dist:
                norm_d = normalize_district_name(raw_dist)
                d_match = dist_by_name.get(norm_d.lower().strip()) or dist_by_name.get(raw_dist.lower().strip())
                district_val = d_match.district_name if d_match else norm_d
            machine_id = parse_clean_str(item.get("machine_id") or item.get("Machine ID") or item.get("Machine Id"))
            laptop_sn = parse_clean_str(item.get("laptop_serial_no") or item.get("Laptop Serial No."))
            laptop_name = parse_clean_str(item.get("laptop_name") or item.get("Laptop Name"))
            kit_slot = parse_clean_str(item.get("kit_slot") or item.get("Kit Slot") or item.get("category") or item.get("Category"))
            block = parse_clean_str(item.get("block") or item.get("Block"))
            locality = parse_clean_str(item.get("locality") or item.get("Locality"))
            ask_address = parse_clean_str(item.get("ask_address") or item.get("ASK Address"))
            station_status = parse_clean_str(item.get("station_status") or item.get("Station Status")) or "Active"
            allotted_date = parse_date_val(
                item.get("station_id_allotted_date") or item.get("Station ID  Allotted Date") or item.get("Station ID Provided Date")
            )

            # Workflow fields inside payload or nested
            workflow = item.get("workflow") or {}
            l1_status_str = workflow.get("l1_status") or item.get("l1_status") or item.get("L1 Status")
            l2_status_str = workflow.get("l2_status") or item.get("l2_status") or item.get("L2 Status")
            l1_id = map_status_to_id(l1_status_str, is_l2=False)
            l2_id = map_status_to_id(l2_status_str, is_l2=True)
            l1_date = parse_date_val(workflow.get("l1_done_date") or item.get("l1_done_date") or item.get("L1 Date") or item.get("L1 Done Date"))
            l2_date = parse_date_val(workflow.get("l2_done_date") or item.get("l2_done_date") or item.get("L2 Date") or item.get("L2 Done Date"))

            if not kit:
                kit = KitRegistration(
                    station_id=station_id,
                    district=district_val,
                    machine_id=machine_id,
                    laptop_serial_no=laptop_sn,
                    laptop_name=laptop_name,
                    category=kit_slot,
                    block=block,
                    locality=locality,
                    ask_address=ask_address,
                    station_status=station_status,
                    station_id_provided_date=allotted_date,
                    l1_status_id=l1_id,
                    l2_status_id=l2_id,
                    l1_done_date=l1_date,
                    l2_done_date=l2_date
                )
                if not dry_run:
                    db.add(kit)
                    db.flush()
                existing_kits[station_id] = kit
                stats["kits_created"] += 1
            else:
                changed = False
                if district_val and kit.district != district_val: kit.district = district_val; changed = True
                if machine_id and kit.machine_id != machine_id: kit.machine_id = machine_id; changed = True
                if laptop_sn and kit.laptop_serial_no != laptop_sn: kit.laptop_serial_no = laptop_sn; changed = True
                if laptop_name and kit.laptop_name != laptop_name: kit.laptop_name = laptop_name; changed = True
                if kit_slot and kit.category != kit_slot: kit.category = kit_slot; changed = True
                if block and kit.block != block: kit.block = block; changed = True
                if locality and kit.locality != locality: kit.locality = locality; changed = True
                if ask_address and kit.ask_address != ask_address: kit.ask_address = ask_address; changed = True
                if station_status and kit.station_status != station_status: kit.station_status = station_status; changed = True
                if allotted_date and kit.station_id_provided_date != allotted_date: kit.station_id_provided_date = allotted_date; changed = True
                if l1_id and kit.l1_status_id != l1_id: kit.l1_status_id = l1_id; changed = True
                if l2_id and kit.l2_status_id != l2_id: kit.l2_status_id = l2_id; changed = True
                if l1_date and kit.l1_done_date != l1_date: kit.l1_done_date = l1_date; changed = True
                if l2_date and kit.l2_done_date != l2_date: kit.l2_done_date = l2_date; changed = True
                if changed:
                    stats["kits_updated"] += 1

            # 2. Upsert Operator (Resolves district code just like seed_pending_lists.py)
            op_data = item.get("operator") or {}
            op_code = parse_clean_str(op_data.get("operator_code") or item.get("operator_code") or item.get("Operator Id"))
            op = None
            if op_code:
                op_name = parse_clean_str(op_data.get("name") or item.get("operator_name") or item.get("Operator Name")) or "Unknown"
                op_mobile = parse_clean_str(op_data.get("mobile") or item.get("operator_mobile") or item.get("Operator Mobile"))
                op_status = parse_clean_str(
                    op_data.get("status") or item.get("operator_status") or item.get("Operator Status") or item.get("Operator Activation Status (User Credentials Created)")
                ) or "Inactive"
                sd_status = parse_clean_str(
                    op_data.get("security_deposit_status") or item.get("security_deposit_status") or item.get("Security Deposit Status") or item.get("SD Status")
                )
                sd_date = parse_date_val(op_data.get("security_deposit_date") or item.get("security_deposit_date") or item.get("Security Deposit Date"))
                inact_reason = parse_clean_str(
                    op_data.get("inactive_reason") or item.get("inactive_reason") or item.get("Inactive Reason") or item.get("Operator In-active Reason")
                )
                inact_date = parse_date_val(
                    op_data.get("inactive_date") or item.get("inactive_date") or item.get("Inactive Date") or item.get("Operator In-active Date")
                )

                # Resolve district_id to district_code
                resolved_dist_code = None
                if district_val:
                    norm_d = normalize_district_name(district_val)
                    d_match = dist_by_name.get(norm_d.lower().strip()) or dist_by_name.get(district_val.lower().strip())
                    if d_match:
                        resolved_dist_code = d_match.district_code

                op = existing_ops.get(op_code)
                if not op:
                    op = Operator(
                        user_code=op_code,
                        name=op_name,
                        mobile=op_mobile,
                        status=op_status,
                        security_deposit_status=sd_status,
                        security_deposit_date=sd_date,
                        inactive_reason=inact_reason,
                        inactive_date=inact_date,
                        district_id=resolved_dist_code
                    )
                    if not dry_run:
                        db.add(op)
                        db.flush()
                    existing_ops[op_code] = op
                    stats["operators_created"] += 1
                else:
                    op_changed = False
                    if op_name and op.name != op_name: op.name = op_name; op_changed = True
                    if op_mobile and op.mobile != op_mobile: op.mobile = op_mobile; op_changed = True
                    if op_status and op.status != op_status: op.status = op_status; op_changed = True
                    if sd_status and op.security_deposit_status != sd_status: op.security_deposit_status = sd_status; op_changed = True
                    if sd_date and op.security_deposit_date != sd_date: op.security_deposit_date = sd_date; op_changed = True
                    if inact_reason and op.inactive_reason != inact_reason: op.inactive_reason = inact_reason; op_changed = True
                    if inact_date and op.inactive_date != inact_date: op.inactive_date = inact_date; op_changed = True
                    if resolved_dist_code and op.district_id != resolved_dist_code: op.district_id = resolved_dist_code; op_changed = True
                    if op_changed:
                        stats["operators_updated"] += 1

            # 3. Upsert OperatorStationMapping (Links op.id to station_id)
            mapping = None
            if op and kit:
                mapping = existing_mappings.get(station_id)
                if not mapping:
                    mapping = OperatorStationMapping(
                        station_id=station_id,
                        operator_id=op.id,
                        mapped_at=datetime.now()
                    )
                    if not dry_run:
                        db.add(mapping)
                        db.flush()
                    existing_mappings[station_id] = mapping
                    stats["mappings_created"] += 1
                elif mapping.operator_id != op.id:
                    mapping.operator_id = op.id
                    if not dry_run:
                        db.flush()

            # 4. Upsert OperatorOnboardingDetail (mapping_id is required foreign key)
            if op and mapping:
                onboard = existing_onboard.get(station_id)
                onb_status_str = parse_clean_str(
                    workflow.get("onboarding_status") or item.get("onboarding_status") or item.get("Onboarding Status") or item.get("On-Boarding Status")
                ) or "Inactive"
                onb_date = parse_date_val(
                    workflow.get("onboard_date") or item.get("onboard_date") or item.get("Onboard Date") or item.get("On-Boarding Date /(Pending days)")
                )
                visit_status = parse_clean_str(workflow.get("visit_status") or item.get("visit_status") or item.get("Visit Status"))
                visit_date = parse_date_val(workflow.get("visit_date") or item.get("visit_date") or item.get("Visit Date"))
                remark = parse_clean_str(workflow.get("remark") or item.get("remark") or item.get("Remark"))
                ask_working = parse_clean_str(
                    workflow.get("kit_working_status") or item.get("kit_working_status") or item.get("Kit Working")
                ) or "Inactive"
                permitted_18 = parse_clean_str(
                    workflow.get("permitted_18_plus") or item.get("permitted_18_plus") or item.get("18+ Permit")
                ) or "No"

                if not onboard:
                    onboard = OperatorOnboardingDetail(
                        mapping_id=mapping.id,
                        operator_id=op.id,
                        station_id=station_id,
                        onboarding_status=onb_status_str,
                        onboard_date=onb_date,
                        visit_status=visit_status,
                        visit_date=visit_date,
                        remark=remark,
                        ask_kit_working_status=ask_working,
                        permitted_18_plus=permitted_18
                    )
                    if not dry_run:
                        db.add(onboard)
                        db.flush()
                    existing_onboard[station_id] = onboard
                    stats["onboarding_created"] += 1
                else:
                    onb_changed = False
                    if mapping and onboard.mapping_id != mapping.id:
                        onboard.mapping_id = mapping.id
                        onb_changed = True
                    if op and onboard.operator_id != op.id:
                        onboard.operator_id = op.id
                        onb_changed = True
                    if onb_status_str and onboard.onboarding_status != onb_status_str:
                        onboard.onboarding_status = onb_status_str
                        onb_changed = True
                    if onb_date and onboard.onboard_date != onb_date:
                        onboard.onboard_date = onb_date
                        onb_changed = True
                    if visit_status and onboard.visit_status != visit_status:
                        onboard.visit_status = visit_status
                        onb_changed = True
                    if visit_date and onboard.visit_date != visit_date:
                        onboard.visit_date = visit_date
                        onb_changed = True
                    if remark and onboard.remark != remark:
                        onboard.remark = remark
                        onb_changed = True
                    if ask_working and onboard.ask_kit_working_status != ask_working:
                        onboard.ask_kit_working_status = ask_working
                        onb_changed = True
                    if permitted_18 and onboard.permitted_18_plus != permitted_18:
                        onboard.permitted_18_plus = permitted_18
                        onb_changed = True
                    if onb_changed:
                        stats["onboarding_updated"] += 1

        if not dry_run:
            db.commit()

        total_records = payload.get("total_records", 0)
        if params["page"] * params["page_size"] >= total_records:
            break
        params["page"] += 1

    logger.info(f"Sync complete. Stats: {stats}")
    return stats


def main():
    parser = argparse.ArgumentParser(description="Synchronize report entities from external portal")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without committing to DB")
    parser.add_argument("--pages", type=int, default=10, help="Maximum number of pages to pull")
    parser.add_argument("--no-exact-mirror", action="store_true", help="Disable pruning of records not present in external API")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        results = sync_reports_data_from_external(
            db,
            dry_run=args.dry_run,
            max_pages=args.pages,
            exact_mirror=not args.no_exact_mirror
        )
        print("\n--- SYNC RESULTS SUMMARY ---")
        for k, v in results.items():
            print(f"  {k}: {v}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
