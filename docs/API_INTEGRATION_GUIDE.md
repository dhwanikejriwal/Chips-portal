# 📘 End-to-End Dynamic API Integration Guide
### Transitioning from Manual Excel Imports to Automated Live Data Sync
**Project:** CHIPS Aadhar Management System  
**Audience:** Development Teams, Tech Leads & Integration Engineers  

---

## 📑 Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Integration Architecture (How it Works)](#2-integration-architecture)
3. [Field Mapping: Excel Columns vs API JSON Payload](#3-field-mapping-excel-vs-api-json)
4. [API Contract Specifications for the External Team](#4-api-contract-specifications)
5. [Backend Sync Implementation (CHIPS Side)](#5-backend-sync-implementation)
6. [Scheduled Automation (Cron / Background Worker)](#6-scheduled-automation)
7. [Security & UIDAI Compliance Standards](#7-security--uidai-compliance)
8. [End-to-End Testing & Verification Checklist](#8-testing--verification-checklist)

---

## 1. Executive Summary

Previously, operator and candidate records were populated periodically using manual spreadsheet uploads (`.xlsx` / `.csv`) containing fields such as **Name**, **Aadhar number**, **Registrar code**, **Operator code**, **Status**, and **Agency**.

### The Objective
To replace manual Excel uploads with a **secure, automated, incremental (delta) synchronization pipeline** between the live external platform and the CHIPS PostgreSQL database.

---

## 2. Integration Architecture

We implement an **Incremental Pull (Delta Sync)** model paired with an optional **Push (Webhook)** trigger:

```
┌──────────────────────────────┐                         ┌──────────────────────────────┐
│       EXTERNAL PLATFORM      │                         │         CHIPS SYSTEM         │
│         (Source of Truth)    │                         │      (Aadhar-Project VM)     │
├──────────────────────────────┤                         ├──────────────────────────────┤
│                              │                         │                              │
│  [Live Database]             │                         │   [Celery / APScheduler /   │
│         │                    │                         │    FastAPI Background Worker]│
│         ▼                    │                         │              │               │
│  REST API Gateway            │    GET /api/v1/sync     │              ▼               │
│  - /api/v1/operators/sync    │ <────────────────────── │   Trigger Sync Service       │
│    ?updated_after=ISO_TIME   │                         │   (Pass last sync timestamp) │
│                              │  JSON Payload (Delta)   │              │               │
│                              │ ──────────────────────> │              ▼               │
│                              │                         │   Validate & Hash / Encrypt  │
│                              │                         │   (HMAC-SHA256 & AES-256)    │
│                              │                         │              │               │
│                              │                         │              ▼               │
│                              │                         │   Upsert into Database:      │
│                              │                         │   - operator_master          │
│                              │                         │   - candidate_table          │
│                              │                         │   - lms_table / nseit        │
│                              │                         │              │               │
│                              │                         │              ▼               │
│                              │                         │   Write Sync Logs / Audit    │
└──────────────────────────────┘                         └──────────────────────────────┘
```

---

## 3. Field Mapping: Excel Columns vs API JSON

Here is the exact mapping from the previous Excel template to the API JSON keys and the internal database columns:

### 3.1 Operator Master Mapping

| Previous Excel Header | Expected API JSON Key | CHIPS DB Column (`operator_master`) | Data Type & Notes |
|---|---|---|---|
| **Name** | `name` | `name`, `name_normalized` | `VARCHAR(150)` (Normalized automatically) |
| **Aadhar number** | `aadhar_number` / `aadhaar_last4` | `aadhar_hash`, `aadhar_encrypted`, `aadhar_last4` | Plain 12-digits or masked. Server generates HMAC & AES-256. |
| **Registrar code** | `registrar_code` | `registrar_code` | `VARCHAR(50)` (e.g. `REG001`) |
| **Operator code** | `operator_code` | `operator_code` | `VARCHAR(100)` (Unique per operator) |
| **Status** | `status` | `status` | `VARCHAR(30)` (`ACTIVE`, `DEACTIVATED`, `SUSPENDED`) |
| **Agency** | `agency` | `agency` | `VARCHAR(100)` (e.g., `CHIPS`, `CSC`, `IPPB`) |
| *(New / Auto)* | `updated_at` | `updated_at` | `ISO-8601 Timestamp` (Used for delta sync) |

---

## 4. API Contract Specifications

Provide this exact contract to the external engineering team.

### 4.1 Delta Operator Sync Endpoint
* **Method:** `GET`
* **Path:** `/api/v1/operators/sync`
* **Headers:**
  ```http
  X-API-Key: <SECRET_KEY>
  Accept: application/json
  ```
* **Query Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `updated_after` | string (ISO-8601) | **Yes** | e.g. `2026-08-31T00:00:00+05:30`. Only returns records created/modified after this timestamp. |
| `page` | integer | No | Page number (default: 1) |
| `page_size` | integer | No | Records per page (default: 200, max: 1000) |

* **Sample Response (200 OK):**
```json
{
  "success": true,
  "timestamp": "2026-08-31T15:30:00+05:30",
  "total_records": 125,
  "page": 1,
  "page_size": 200,
  "data": [
    {
      "operator_code": "OP_98765",
      "registrar_code": "001",
      "agency": "CHIPS",
      "name": "Amit Sharma",
      "aadhar_number": "XXXXXXXX1234",
      "mobile": "9876543210",
      "email": "amit.sharma@example.com",
      "district_code": "RAI",
      "status": "ACTIVE",
      "updated_at": "2026-08-31T14:15:22+05:30"
    }
  ]
}
```

---

## 5. Backend Sync Implementation (CHIPS Side)

Here is the architectural pattern for the sync client to be added into the CHIPS backend:

### 5.1 Sync Service Module (`backend/services/external_sync.py`)

```python
import os
import logging
import requests
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.models.operator_master import OperatorMaster
from backend.services.operator_master_ingest import _normalize_name, _normalize_status
from backend.utils.aadhar_crypto import hash_aadhar, encrypt_aadhar

logger = logging.getLogger("sync_service")

EXTERNAL_API_BASE_URL = os.getenv("EXTERNAL_PLATFORM_URL", "https://api.externalplatform.gov.in")
EXTERNAL_API_KEY = os.getenv("EXTERNAL_PLATFORM_API_KEY", "")

def sync_operators_from_external(db: Session, last_sync_time: datetime = None) -> dict:
    """
    Fetches changed operator records from the external platform and upserts them into operator_master.
    """
    headers = {
        "X-API-Key": EXTERNAL_API_KEY,
        "Accept": "application/json"
    }
    
    params = {
        "page": 1,
        "page_size": 500
    }
    if last_sync_time:
        params["updated_after"] = last_sync_time.isoformat()

    added_count = 0
    updated_count = 0
    
    while True:
        try:
            response = requests.get(
                f"{EXTERNAL_API_BASE_URL}/api/v1/operators/sync",
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch data from external API: {e}")
            raise

        records = payload.get("data", [])
        if not records:
            break

        for item in records:
            op_code = item.get("operator_code", "").strip()
            reg_code = item.get("registrar_code", "").strip()
            name = item.get("name", "").strip()
            status = _normalize_status(item.get("status", "ACTIVE"))
            agency = (item.get("agency") or "").strip()
            aadhar_raw = str(item.get("aadhar_number", "")).strip()

            if not (op_code and reg_code and name and aadhar_raw):
                continue

            name_norm = _normalize_name(name)
            aadhar_h = hash_aadhar(aadhar_raw)
            aadhar_enc = encrypt_aadhar(aadhar_raw)
            last4 = aadhar_raw[-4:] if len(aadhar_raw) >= 4 else ""

            # Check if record already exists based on composite unique constraint
            existing = db.query(OperatorMaster).filter(
                OperatorMaster.name_normalized == name_norm,
                OperatorMaster.aadhar_hash == aadhar_h,
                OperatorMaster.registrar_code == reg_code,
                OperatorMaster.operator_code == op_code,
                OperatorMaster.status == status
            ).first()

            if existing:
                # Update non-identity attributes if changed
                if existing.agency != agency:
                    existing.agency = agency
                    updated_count += 1
            else:
                new_op = OperatorMaster(
                    name=name,
                    name_normalized=name_norm,
                    aadhar_hash=aadhar_h,
                    aadhar_encrypted=aadhar_enc,
                    aadhar_last4=last4,
                    registrar_code=reg_code,
                    operator_code=op_code,
                    status=status,
                    agency=agency
                )
                db.add(new_op)
                added_count += 1

        db.commit()

        # Check for next page
        total_records = payload.get("total_records", 0)
        if params["page"] * params["page_size"] >= total_records:
            break
        params["page"] += 1

    return {
        "status": "success",
        "added": added_count,
        "updated": updated_count,
        "synced_at": datetime.now(timezone.utc).isoformat()
    }
```

---

## 6. Scheduled Automation

### Option A: Background Scheduled Job via APScheduler
Run the sync script periodically (e.g., every 30 minutes) inside the backend container:

```python
# In backend/main.py
from apscheduler.schedulers.background import BackgroundScheduler
from backend.database import SessionLocal
from backend.services.external_sync import sync_operators_from_external

scheduler = BackgroundScheduler()

def scheduled_job():
    with SessionLocal() as db:
        sync_operators_from_external(db)

# Run every 30 minutes
scheduler.add_job(scheduled_job, 'interval', minutes=30)
scheduler.start()
```

### Option B: Linux Cron Job on Rocky Linux VM
Alternatively, run an automated command via crontab on the VM:
```bash
# Edit crontab
crontab -e

# Run sync worker every hour inside the docker container
0 * * * * docker exec chips-backend python -m backend.scripts.run_sync >> /home/aadhar/logs/sync.log 2>&1
```

---

## 7. Security & UIDAI Compliance Standards

1. **Aadhaar Data Protection:**
   - Plaintext Aadhaar must **NEVER** be stored directly in the database.
   - The sync worker immediately converts plain Aadhaar into:
     - `aadhar_hash` (HMAC-SHA256) for search and duplicate prevention.
     - `aadhar_encrypted` (AES-256-GCM) for secured admin-only reveal.
     - `aadhar_last4` for partial masking.
2. **Network Security:**
   - Communication must use **TLS 1.3 / HTTPS**.
   - The external platform must whitelist our VM's Static Public IP.
3. **Audit Trail:**
   - Every sync operation must log timestamp, number of inserted/updated rows, and any validation errors without logging sensitive PII.

---

## 8. Testing & Verification Checklist

- [ ] **Step 1: Staging API Connectivity**
  - Verify `curl -H "X-API-Key: ..."` returns `200 OK` from the VM.
- [ ] **Step 2: Dry Run Test**
  - Fetch 10 sample records from the staging API and verify field mapping.
- [ ] **Step 3: Duplicate Prevention Test**
  - Run sync twice with the same data. Verify zero duplicates are inserted.
- [ ] **Step 4: Delta Sync Verification**
  - Update a record in the source platform.
  - Call API with `?updated_after=<timestamp>`.
  - Verify only the modified record is returned.
- [ ] **Step 5: Load / Pagination Verification**
  - Test pulling 1,000+ records to confirm pagination handles offsets correctly.
- [ ] **Step 6: Production Cutover**
  - Perform initial baseline sync.
  - Enable background scheduler for recurring syncs.
