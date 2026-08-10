import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import update, or_
from backend.database import SessionLocal
from backend.models.district import District
from backend.models.operator_daily_activity import OperatorDailyActivity, ActivityStation

def run_migration():
    db = SessionLocal()
    try:
        print("Starting district normalization migration...")

        # 1. Update district_table
        updates = {
            "Dakshin Bastar Dantewada": "Dantewada",
            "Uttar Bastar Kanker": "Kanker",
            "Kabeerdham": "Kawardha"
        }

        for old_name, new_name in updates.items():
            print(f"Updating district_table: {old_name} -> {new_name}")
            db.execute(
                update(District)
                .where(District.district_name == old_name)
                .values(district_name=new_name)
            )
        
        # 2. Update operator_daily_activity (ODA)
        # Also catch specific aliases that we know exist
        db.execute(update(OperatorDailyActivity).where(OperatorDailyActivity.machine_district.ilike('%kanker%')).values(machine_district='Kanker'))
        db.execute(update(OperatorDailyActivity).where(OperatorDailyActivity.machine_district.ilike('%dantewada%')).values(machine_district='Dantewada'))
        db.execute(update(OperatorDailyActivity).where(OperatorDailyActivity.machine_district.ilike('%kawardha%')).values(machine_district='Kawardha'))
        db.execute(update(OperatorDailyActivity).where(OperatorDailyActivity.machine_district.ilike('%kabeerdham%')).values(machine_district='Kawardha'))
        db.execute(update(OperatorDailyActivity).where(OperatorDailyActivity.machine_district.ilike('%kabirdham%')).values(machine_district='Kawardha'))

        # 3. Update activity_station
        db.execute(update(ActivityStation).where(ActivityStation.machine_district.ilike('%kanker%')).values(machine_district='Kanker'))
        db.execute(update(ActivityStation).where(ActivityStation.machine_district.ilike('%dantewada%')).values(machine_district='Dantewada'))
        db.execute(update(ActivityStation).where(ActivityStation.machine_district.ilike('%kawardha%')).values(machine_district='Kawardha'))
        db.execute(update(ActivityStation).where(ActivityStation.machine_district.ilike('%kabeerdham%')).values(machine_district='Kawardha'))
        db.execute(update(ActivityStation).where(ActivityStation.machine_district.ilike('%kabirdham%')).values(machine_district='Kawardha'))
        
        db.commit()
        print("Migration completed successfully.")

    except Exception as e:
        db.rollback()
        print(f"Error during migration: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
