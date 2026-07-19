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
from backend.models.operator_onboarding import OperatorOnboarding
from backend.routers.station_id import router as station_id_router
from backend.routers.operator_mapping import router as operator_mapping_router
from backend.routers.operator_onboarding import router as operator_onboarding_router
from backend.routers.notifications import router as notifications_router
from backend.routers.dashboard import router as dashboard_router
from backend.routers.report import router as report_router
from backend.routers.station_id import router as station_id_router
from backend.routers.kit_registration import router as kit_registration_router
from backend.routers.notifications import router as notifications_router
from backend.routers.dashboard import router as dashboard_router

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
app.include_router(dashboard_router, prefix="/dashboard")
app.include_router(report_router, prefix="/api/reports")
app.include_router(kit_registration_router, prefix="/kit-registration")
app.include_router(dashboard_router, prefix="/dashboard")



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
            from backend.models.base import Base
            Base.metadata.create_all(bind=engine)
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE candidate_table ADD COLUMN IF NOT EXISTS exam_unique_code VARCHAR(100);"))
                conn.execute(text("ALTER TABLE candidate_login_table ADD COLUMN IF NOT EXISTS has_changed_password BOOLEAN DEFAULT FALSE;"))
                conn.execute(text("DROP TABLE IF EXISTS operator_kit_mappings;"))

            print("Success: Checked and added new columns if missing!")
        except Exception as e:
            with open("migration_error.log", "w") as f:
                f.write(f"Error checking/adding columns: {str(e)}")
            print(f"Error checking/adding columns: {e}", file=sys.stderr)

        try:
            command.upgrade(alembic_cfg, "head")
            print("Success: Database schema automatically synchronized to latest revision!")
        except Exception as e:
            print(f"Alembic upgrade failed: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Migration error: {e}", file=sys.stderr)

@app.get("/")
def read_root():
    return {"message": "Chips API Backend is online."}
