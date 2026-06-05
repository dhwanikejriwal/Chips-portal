from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import engine, Base
# 1. Import your brand new router module
from backend.routers import auth, lms, dc_requests, station, approvals

app = FastAPI(
    title="CHIPS Aadhaar Workflow Platform API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

# 2. Register Your Component Routing Hubs
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(lms.router, prefix="/lms", tags=["LMS Video Requests"]) # Clean isolated path!
app.include_router(dc_requests.router, prefix="/dc_requests", tags=["NOC & Activation Requests"])
app.include_router(station.router, prefix="/station", tags=["Station ID Processing"])
app.include_router(approvals.router, prefix="/approvals", tags=["L1/L2 Approvals"])

@app.get("/")
async def root_status_check():
    return {"status": "online", "message": "FastAPI Core Gateway is operational."}