from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
# 1. Import your brand new router module
from backend.routers import auth,lms

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
# app.include_router(station.router, prefix="/station", tags=["Station ID Processing"])
# app.include_router(l1.router, prefix="/l1", tags=["L1 Workflow"])
# app.include_router(l2.router, prefix="/l2", tags=["L2 Workflow"])

@app.get("/")
async def root_status_check():
    return {"status": "online", "message": "FastAPI Core Gateway is operational."}