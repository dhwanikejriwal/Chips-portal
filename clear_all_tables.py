"""
Clear All Tables Script.

Truncates all user tables in the PostgreSQL database, CASCADE deleting all rows
and restarting all auto-increment sequences back to 1.
"""
import sys
import os

# Ensure root project directory is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from backend.database import SessionLocal, engine
import backend.models  # Load all models for SQLAlchemy awareness


def clear_all_tables():
    print("==========================================================")
    print("  WARNING: TRUNCATING ALL TABLES IN THE DATABASE")
    print("==========================================================")
    db = SessionLocal()
    try:
        with engine.begin() as conn:
            # Query all base tables in the public schema except alembic migration tracking
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                  AND table_type = 'BASE TABLE' 
                  AND table_name != 'alembic_version';
            """))
            tables = [f'"{row[0]}"' for row in result.fetchall()]
            
            if tables:
                table_list = ", ".join(tables)
                print(f"Truncating {len(tables)} tables with RESTART IDENTITY CASCADE...")
                conn.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE;"))
                print("\nSuccess: All database tables have been cleared and sequences reset!")
            else:
                print("No tables found in public schema to truncate.")
    except Exception as e:
        print(f"\nError clearing database tables: {e}", file=sys.stderr)
    finally:
        db.close()


if __name__ == "__main__":
    clear_all_tables()
