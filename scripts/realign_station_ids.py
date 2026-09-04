import os
import sys
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import SessionLocal
from backend.models.station_id import StationIDRequest, StationIDRemark
from backend.models.district import District
from backend.models.station_id_master import StationIDMaster
from backend.models.base import StatusEnum
from backend.utils.district_mapper import normalize_district_name

def realign_all_station_ids():
    excel_path = os.path.join(os.path.dirname(__file__), '..', 'sample reports', 'District_Next_Station_IDs.xlsx')
    df = pd.read_excel(excel_path)
    
    initial_starts = {}
    for _, row in df.iterrows():
        d_name = str(row['District']).strip()
        norm_name = normalize_district_name(d_name).lower()
        initial_starts[norm_name] = int(row['Start Station ID'])

    db = SessionLocal()
    try:
        districts = db.query(District).all()
        
        # Group approved / allotted requests by district
        all_approved = db.query(StationIDRequest).filter(
            StationIDRequest.status_id.in_([StatusEnum.APPROVED.value, StatusEnum.ALLOTTED.value, 2, 18])
        ).order_by(StationIDRequest.id.asc()).all()

        # Group by request_no to avoid treating existing sibling rows as separate requests
        seen_req_nos = set()
        distinct_approved = []
        for r in all_approved:
            if r.request_no and r.request_no in seen_req_nos:
                continue
            if r.request_no:
                seen_req_nos.add(r.request_no)
            distinct_approved.append(r)

        print(f"Total distinct approved requests to realign: {len(distinct_approved)}")

        # Delete any existing extra sibling rows for these requests first to start clean
        for r in distinct_approved:
            if r.request_no:
                db.query(StationIDRequest).filter(
                    StationIDRequest.request_no == r.request_no,
                    StationIDRequest.id != r.id
                ).delete(synchronize_session=False)

        db.flush()

        # Process per district
        for dist in districts:
            dist_code = str(dist.district_code)
            dist_name = dist.district_name
            norm_name = normalize_district_name(dist_name).lower()

            base_start = initial_starts.get(norm_name)
            if not base_start:
                master = db.query(StationIDMaster).filter(StationIDMaster.district_code == dist_code).first()
                base_start = int(master.start_station_id) if master else 10000

            curr_id = base_start

            # Find distinct approved requests for this district
            dist_reqs = [r for r in distinct_approved if str(r.district_id) == dist_code]
            # Sort by request_no / id
            dist_reqs.sort(key=lambda x: (x.request_no or '', x.id))

            for req in dist_reqs:
                kits = req.number_of_kits if req.number_of_kits and req.number_of_kits > 0 else 1
                assigned_ids = [curr_id + i for i in range(kits)]
                curr_id += kits

                # Update primary row
                req.station_id_inserted = str(assigned_ids[0])
                req.status_id = StatusEnum.ALLOTTED.value

                # Create sibling rows if kits > 1
                for extra_sid in assigned_ids[1:]:
                    sibling = StationIDRequest(
                        request_no=req.request_no,
                        dc_id=req.dc_id,
                        district_id=req.district_id,
                        model=req.model,
                        user_type=req.user_type,
                        user_type_custom_reason=req.user_type_custom_reason,
                        slot=req.slot,
                        number_of_kits=kits,
                        status_id=StatusEnum.ALLOTTED.value,
                        station_id_inserted=str(extra_sid),
                        submitted_at=req.submitted_at,
                        reviewed_at=req.reviewed_at or req.submitted_at,
                        reviewed_by=req.reviewed_by or 1,
                    )
                    db.add(sibling)
                    db.flush()
                    db.add(StationIDRemark(
                        request_id=sibling.id,
                        author_id=req.reviewed_by or 1,
                        author_role="chips_admin",
                        remark="Station ID credentials successfully assigned.",
                        status_after_id=StatusEnum.ALLOTTED.value,
                    ))

                print(f"[{dist_name}] {req.request_no}: Allotted {len(assigned_ids)} IDs -> {assigned_ids}")

            # Update or create StationIDMaster
            master = db.query(StationIDMaster).filter(StationIDMaster.district_code == dist_code).first()
            if master:
                master.start_station_id = curr_id
                master.district_name = dist_name
            else:
                db.add(StationIDMaster(
                    district_code=dist_code,
                    district_name=dist_name,
                    start_station_id=curr_id
                ))

        db.commit()
        print("\nAll Station IDs successfully realigned and synchronized with StationIDMaster!")
    except Exception as e:
        db.rollback()
        print(f"Error during realignment: {e}")
        raise
    finally:
        db.close()

if __name__ == '__main__':
    realign_all_station_ids()
