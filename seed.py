import os
from backend.database import SessionLocal, engine, Base
from backend.models import District, User, UserRole, CredentialRequest
from bcrypt import hashpw, gensalt

def seed_database():
    print("Initializing database seeding sequence...")
    
    # Auto-create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 1. Clear existing test records gracefully to prevent duplicates
        db.query(CredentialRequest).delete()
        db.query(User).delete()
        db.query(District).delete()
        db.commit()
        
        # 2. Add baseline state districts visible in your UI layout
        raipur = District(name="Raipur")
        bilaspur = District(name="Bilaspur")
        durg = District(name="Durg")
        db.add_all([raipur, bilaspur, durg])
        db.commit()
        print("Districts ('Raipur', 'Bilaspur', 'Durg') created successfully.")
        
        # 3. Encrypt default administrative passwords using bcrypt
        hashed_dc_pass = hashpw(b"password123", gensalt()).decode('utf-8')
        hashed_chips_pass = hashpw(b"admin123", gensalt()).decode('utf-8')
        
        # 4. Generate default user profiles matching your frontend credentials mockup
        dc_user = User(
            username="dc_raipur", 
            password_hash=hashed_dc_pass, 
            role=UserRole.DC, 
            district_id=raipur.id
        )
        chips_user = User(
            username="chips_admin", 
            password_hash=hashed_chips_pass, 
            role=UserRole.CHIPS_ADMIN
        )
        
        db.add_all([dc_user, chips_user])
        db.commit()
        print("Default profiles ('dc_raipur', 'chips_admin') generated seamlessly.")
        print("\n Database successfully loaded with structural project elements!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()