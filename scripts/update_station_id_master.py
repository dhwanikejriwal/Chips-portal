import sys
import os

# Ensure the root of the project is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import SessionLocal
from backend.models.station_id_master import StationIDMaster
from backend.models.district import District

def update_station_id_master(updates: list):
    """
    Update or create StationIDMaster records based on the provided updates.
    
    Args:
        updates: A list of dictionaries with keys:
                 'district_code', 'start_station_id'
                 Example: [{'district_code': '01', 'start_station_id': 1000}]
    """
    db = SessionLocal()
    try:
        # Get all districts to fetch district names
        districts = {d.district_code: d.district_name for d in db.query(District).all()}
        
        updated_count = 0
        created_count = 0

        for update_data in updates:
            d_code = update_data.get('district_code')
            new_start_id = update_data.get('start_station_id')

            if d_code not in districts:
                print(f"Warning: District code {d_code} not found in the District table. Skipping.")
                continue

            # Check if record exists
            record = db.query(StationIDMaster).filter(StationIDMaster.district_code == d_code).first()

            if record:
                record.start_station_id = new_start_id
                # Update district name just in case it changed
                record.district_name = districts[d_code]
                updated_count += 1
                print(f"Updated: {districts[d_code]} (Code: {d_code}) -> Start Station ID: {new_start_id}")
            else:
                new_record = StationIDMaster(
                    district_code=d_code,
                    district_name=districts[d_code],
                    start_station_id=new_start_id
                )
                db.add(new_record)
                created_count += 1
                print(f"Created: {districts[d_code]} (Code: {d_code}) -> Start Station ID: {new_start_id}")

        db.commit()
        print(f"\nSummary: {updated_count} records updated, {created_count} records created.")

    except Exception as e:
        db.rollback()
        print(f"Error occurred during update: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import pandas as pd
    
    excel_path = r"sample reports\District_Next_Station_IDs.xlsx"
    print(f"Reading data from {excel_path}...")
    
    try:
        df = pd.read_excel(excel_path)
        
        db = SessionLocal()
        districts = {d.district_name.lower().strip(): d.district_code for d in db.query(District).all()}
        db.close()
        
        DATA_TO_UPDATE = []
        for index, row in df.iterrows():
            district_name = str(row['District']).strip()
            start_id = int(row['Start Station ID'])
            
            d_code = districts.get(district_name.lower())
            if not d_code:
                print(f"Warning: District '{district_name}' not found in the database. Skipping.")
                continue
                
            DATA_TO_UPDATE.append({
                "district_code": d_code,
                "start_station_id": start_id
            })
            
        if not DATA_TO_UPDATE:
            print("No valid data found to update.")
        else:
            print(f"Found {len(DATA_TO_UPDATE)} valid records. Starting StationIDMaster update...")
            update_station_id_master(DATA_TO_UPDATE)
            
    except Exception as e:
        print(f"Error reading excel file: {e}")
