import os
from backend.database import SessionLocal, engine, Base
from backend.models import District, User, UserRole, CredentialRequest
from bcrypt import hashpw, gensalt
from sqlalchemy import inspect, text

def seed_database():
    print("Initializing database seeding sequence...")
    
    # Active tables owned by this application
    our_table_names = {
        "districts",
        "users",
        "credential_requests",
        "noc_requests",
        "station_kit_details",
        "approval_history"
    }
    
    # 1. Update/Align schemas dynamically without dropping tables or violating foreign keys
    print("Aligning database schemas with current models...")
    inspector = inspect(engine)
    
    # 0. Align custom enum types in PostgreSQL to ensure new states like REVERTED/REAPPLIED exist
    print("Aligning custom enum values in database...")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for val in ["PENDING", "ASSIGNED", "REVERTED", "REAPPLIED"]:
            try:
                conn.execute(text(f"ALTER TYPE requeststatus ADD VALUE '{val}'"))
            except Exception:
                pass
        for val in ["DC", "CHIPS_ADMIN"]:
            try:
                conn.execute(text(f"ALTER TYPE userrole ADD VALUE '{val}'"))
            except Exception:
                pass
                
    # Filter metadata tables to only create ours
    our_tables_metadata = [
        Base.metadata.tables[name] for name in our_table_names 
        if name in Base.metadata.tables
    ]
    
    # Only create/update our project tables, ignoring others
    Base.metadata.create_all(bind=engine, tables=our_tables_metadata)
    
    with engine.begin() as conn:
        for table_name in our_table_names:
            if table_name not in Base.metadata.tables:
                continue
                
            table = Base.metadata.tables[table_name]
            
            # Get existing columns in the database table
            try:
                columns_in_db = {col['name']: col for col in inspector.get_columns(table_name)}
            except Exception:
                # Table might not exist yet (although create_all should have created it)
                continue
            
            # Add missing columns
            for column in table.columns:
                col_name = column.name
                if col_name not in columns_in_db:
                    col_type_str = str(column.type.compile(dialect=engine.dialect))
                    null_str = "NULL" if column.nullable else "NOT NULL"
                    default_clause = ""
                    
                    if not column.nullable:
                        if col_type_str.startswith("VARCHAR") or col_type_str == "TEXT":
                            default_clause = " DEFAULT ''"
                        elif "INT" in col_type_str or "FLOAT" in col_type_str or "NUMERIC" in col_type_str:
                            default_clause = " DEFAULT 0"
                        elif col_type_str == "BOOLEAN":
                            default_clause = " DEFAULT FALSE"
                        elif "TIMESTAMP" in col_type_str or "DATE" in col_type_str:
                            default_clause = " DEFAULT CURRENT_TIMESTAMP"
                        elif col_type_str == "JSON":
                            default_clause = " DEFAULT '[]'"
                            
                    alter_query = f'ALTER TABLE "{table_name}" ADD COLUMN "{col_name}" {col_type_str}{default_clause} {null_str}'
                    print(f"Executing DDL: {alter_query}")
                    conn.execute(text(alter_query))
            
            # Drop obsolete columns (e.g. operator_phone/operator_email from NOC tables)
            for col_in_db in columns_in_db:
                if col_in_db not in table.columns:
                    alter_query = f'ALTER TABLE "{table_name}" DROP COLUMN "{col_in_db}" CASCADE'
                    print(f"Executing DDL: {alter_query}")
                    conn.execute(text(alter_query))

    db = SessionLocal()
    try:
        # 2. Add baseline state districts if they don't already exist
        for d_name in ["Raipur", "Bilaspur", "Durg"]:
            existing_d = db.query(District).filter(District.name == d_name).first()
            if not existing_d:
                db.add(District(name=d_name))
        db.commit()
        print("Default districts aligned.")
        
        # Fetch रायपुर for DC linking
        raipur = db.query(District).filter(District.name == "Raipur").first()
        
        # 3. Encrypt default passwords
        hashed_dc_pass = hashpw(b"password123", gensalt()).decode('utf-8')
        hashed_chips_pass = hashpw(b"admin123", gensalt()).decode('utf-8')
        
        # 4. Generate default user profiles if not present
        dc_user = db.query(User).filter(User.username == "dc_raipur").first()
        if not dc_user:
            dc_user = User(
                username="dc_raipur", 
                password_hash=hashed_dc_pass, 
                role=UserRole.DC, 
                district_id=raipur.id if raipur else None
            )
            db.add(dc_user)
            
        chips_user = db.query(User).filter(User.username == "chips_admin").first()
        if not chips_user:
            chips_user = User(
                username="chips_admin", 
                password_hash=hashed_chips_pass, 
                role=UserRole.CHIPS_ADMIN
            )
            db.add(chips_user)
            
        db.commit()
        print("Default profiles ('dc_raipur', 'chips_admin') verified/created.")
        print("\nDatabase successfully aligned and loaded with structural project elements!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()