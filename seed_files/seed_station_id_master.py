"""Seed station_id_master from station_id_master.xlsx.

Idempotent: upserts by district_code. Skips codes not present in district_table.
"""
import os
import sys

# Ensure root project directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.getcwd())

import pandas as pd
from backend.database import SessionLocal
from backend.models.station_id_master import StationIDMaster
from backend.models.district import District


def run():
    df = pd.read_excel("useful_files/station_id_master.xlsx")
    db = SessionLocal()
    try:
        valid_codes = {c for (c,) in db.query(District.district_code).all()}
        inserted = updated = skipped = 0
        for _, row in df.iterrows():
            code = str(int(row["district_code"]))
            name = str(row["district_name"]).strip()
            start = int(row["start_station_id"])
            if code not in valid_codes:
                print(f"  SKIP (no district): {code} {name}")
                skipped += 1
                continue
            existing = db.query(StationIDMaster).filter_by(district_code=code).one_or_none()
            if existing:
                existing.district_name = name
                existing.start_station_id = start
                updated += 1
            else:
                db.add(StationIDMaster(district_code=code, district_name=name, start_station_id=start))
                inserted += 1
        db.commit()
        print(f"Done. inserted={inserted} updated={updated} skipped={skipped}")
        print("Total rows:", db.query(StationIDMaster).count())
    finally:
        db.close()


if __name__ == "__main__":
    run()
