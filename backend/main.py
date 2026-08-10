import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from alembic.config import Config
from alembic import command

# Ensure the root directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(title="Chips Portal API")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import traceback
from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    try:
        os.makedirs("c:\\chips-portal", exist_ok=True)
        with open("c:\\chips-portal\\error.log", "a") as f:
            f.write(f"Exception on {request.url}:\n")
            f.write(traceback.format_exc())
            f.write("\n")
    except Exception:
        print(traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": str(exc)})

# Register routers (Friend's / Shared)
from backend.routers.auth import router as auth_router
from backend.routers.candidate_register import router as candidate_register_router
from backend.routers.selection import router as selection_router
from backend.routers.candidate import router as candidate_router
from backend.routers.lms_manage import router as lms_manage_router
from backend.routers.nseit_manage import router as nseit_manage_router
from backend.routers.monitoring import router as monitoring_router
from backend.routers.l1_registration import router as l1_registration_router
from backend.routers.reactivation import router as reactivation_router
from backend.routers.l2_registration import router as l2_registration_router
from backend.routers.operator_activation import router as operator_activation_router
from backend.models.station_id import StationIDRequest, StationIDRemark

from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
from backend.routers.station_id import router as station_id_router
from backend.routers.operator_mapping import router as operator_mapping_router
from backend.routers.operator_onboarding import router as operator_onboarding_router
from backend.routers.notifications import router as notifications_router
from backend.routers.dc_dashboard import router as dc_dashboard_router
from backend.routers.chips_dashboard import router as chips_dashboard_router
from backend.routers.report import router as report_router
from backend.routers.kit_registration import router as kit_registration_router
from backend.routers.operator_activity import router as operator_activity_router
from backend.routers.operator_data import router as operator_data_router

app.include_router(auth_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(candidate_register_router, prefix="/api")
app.include_router(selection_router, prefix="/api")
app.include_router(candidate_router, prefix="/api")
app.include_router(lms_manage_router, prefix="/api")
app.include_router(nseit_manage_router, prefix="/api")
app.include_router(monitoring_router, prefix="/api")
app.include_router(l1_registration_router, prefix="/l1-registration")
app.include_router(reactivation_router, prefix="/reactivation")
app.include_router(l2_registration_router, prefix="/l2-registration")
app.include_router(operator_activation_router, prefix="/operator-activation")
app.include_router(station_id_router, prefix="/station-id")
app.include_router(operator_mapping_router, prefix="/operator-mapping")
app.include_router(operator_onboarding_router, prefix="/operator-onboarding")
app.include_router(dc_dashboard_router)
app.include_router(chips_dashboard_router)
app.include_router(report_router, prefix="/api/reports")
app.include_router(kit_registration_router, prefix="/kit-registration")
app.include_router(operator_activity_router, prefix="/operator-activity")
app.include_router(operator_data_router, prefix="/operator-data")



@app.on_event("startup")
def run_migrations():
    print("Automatically checking and applying database migrations...")
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ini_path = os.path.join(base_dir, "alembic.ini")
        
        alembic_cfg = Config(ini_path)
        alembic_cfg.set_main_option("script_location", os.path.join(base_dir, "migrations"))
        
        try:
            from backend.database import engine
            from sqlalchemy import text
            import backend.models
            from backend.models.base import Base
            Base.metadata.create_all(bind=engine)
            with engine.begin() as conn:
                conn.execute(text("DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='candidate_table' AND column_name='r_id') THEN ALTER TABLE candidate_table RENAME COLUMN r_id TO id; END IF; END $$;"))
                conn.execute(text("ALTER TABLE candidate_table ADD COLUMN IF NOT EXISTS exam_unique_code VARCHAR(100);"))
                conn.execute(text("ALTER TABLE candidate_login_table ADD COLUMN IF NOT EXISTS has_changed_password INTEGER DEFAULT 0;"))
                conn.execute(text("DROP TABLE IF EXISTS operator_kit_mappings;"))
                conn.execute(text("ALTER TABLE kit_registration_table ADD COLUMN IF NOT EXISTS block VARCHAR(100);"))
                conn.execute(text("ALTER TABLE kit_registration_table ADD COLUMN IF NOT EXISTS category VARCHAR(100);"))
                conn.execute(text("ALTER TABLE kit_registration_table ADD COLUMN IF NOT EXISTS locality VARCHAR(100);"))
                conn.execute(text("ALTER TABLE kit_registration_table ADD COLUMN IF NOT EXISTS ask_address VARCHAR(255);"))
                conn.execute(text("ALTER TABLE kit_registration_table ADD COLUMN IF NOT EXISTS station_status VARCHAR(50);"))
                conn.execute(text("ALTER TABLE operators ADD COLUMN IF NOT EXISTS inactive_reason VARCHAR(255);"))
                conn.execute(text("ALTER TABLE operators ADD COLUMN IF NOT EXISTS inactive_date DATE;"))
                conn.execute(text("ALTER TABLE operators ADD COLUMN IF NOT EXISTS security_deposit_status VARCHAR(50);"))
                conn.execute(text("ALTER TABLE operators ADD COLUMN IF NOT EXISTS security_deposit_date DATE;"))
                conn.execute(text("ALTER TABLE kit_registration_table ALTER COLUMN machine_id TYPE VARCHAR(255);"))
                conn.execute(text("ALTER TABLE kit_registration_table ALTER COLUMN laptop_serial_no TYPE VARCHAR(255);"))
                conn.execute(text("ALTER TABLE kit_registration_table ALTER COLUMN laptop_name TYPE VARCHAR(255);"))
                conn.execute(text("ALTER TABLE kit_registration_table ALTER COLUMN category TYPE VARCHAR(100);"))
                conn.execute(text("ALTER TABLE operator_activation_requests ADD COLUMN IF NOT EXISTS is_mailed INTEGER DEFAULT 0;"))
                conn.execute(text("ALTER TABLE operator_reactivation_requests ADD COLUMN IF NOT EXISTS is_mailed INTEGER DEFAULT 0;"))
                conn.execute(text("ALTER TABLE l2_registration_requests ADD COLUMN IF NOT EXISTS is_mailed INTEGER DEFAULT 0;"))

            print("Success: Checked and added new columns if missing!")
        except Exception as e:
            with open("migration_error.log", "w") as f:
                f.write(f"Error checking/adding columns: {str(e)}")
            print(f"Error checking/adding columns: {e}", file=sys.stderr)

        try:
            command.upgrade(alembic_cfg, "head")
            print("Success: Database schema automatically synchronized to latest revision!")
        except Exception as e:
            try:
                command.stamp(alembic_cfg, "head")
                print("Database schema version stamped to head successfully.")
            except Exception:
                pass
            print(f"Alembic sync completed (tables already present).", file=sys.stderr)

        # Automatic Database Seeding Pipeline (runs on fresh setup when UserLogin is empty)
        try:
            from backend.database import SessionLocal
            from backend.models.user_login import UserLogin
            db = SessionLocal()
            is_empty = False
            try:
                is_empty = (db.query(UserLogin).count() == 0)
            finally:
                db.close()

            if is_empty:
                print("\n[Auto-Init] Fresh database detected! Automatically executing complete database seeding pipeline...")
                import seed
                seed.main()
                print("[Auto-Init] Success: Full database auto-seeding completed!\n")
        except Exception as e:
            print(f"Auto-seed check failed: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Migration error: {e}", file=sys.stderr)

@app.get("/")
def read_root():
    return {"message": "Chips API Backend is online."}
