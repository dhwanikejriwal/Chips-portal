"""
Clear Baseline Tables Script.

Clears only the tables seeded by seed_login_districts_profiles.py:
- user_profile_table
- user_login_table
- district_table
- master_user_roles (or master_role_table)
- master_status_table

Resets auto-increment primary key sequences back to 1.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from backend.database import SessionLocal, engine
import backend.models

TARGET_TABLES = [
    "user_profile_table",
    "user_login_table",
    "district_table",
    "master_user_role",
    "master_status_table"
]

def clear_baseline_tables():
    print("==========================================================")
    print("  CLEARING BASELINE TABLES SEEDED BY SEED_LOGIN_DISTRICTS_PROFILES.PY")
    print("==========================================================")
    db = SessionLocal()
    try:
        with engine.begin() as conn:
            # Filter existing target tables in public schema
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                  AND table_type = 'BASE TABLE';
            """))
            existing = [row[0] for row in result.fetchall()]
            
            tables_to_truncate = [f'"{t}"' for t in TARGET_TABLES if t in existing]
            
            if tables_to_truncate:
                table_list = ", ".join(tables_to_truncate)
                print(f"Truncating {len(tables_to_truncate)} baseline tables with RESTART IDENTITY CASCADE...")
                conn.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE;"))
                print("\nSuccess: Baseline tables cleared and sequences reset!")
            else:
                print("No matching baseline tables found in database.")
    except Exception as e:
        print(f"\nError clearing baseline tables: {e}", file=sys.stderr)
    finally:
        db.close()

if __name__ == "__main__":
    clear_baseline_tables()
