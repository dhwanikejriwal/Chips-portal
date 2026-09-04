# 🔄 External Portal Automated Data Sync Guide
### Transitioning from Manual Excel Seeding to One-Way Automated Database Sync
**Project:** CHiPS Aadhaar Management System  
**Audience:** CHiPS Technical Team, External Portal Engineering Team, DevOps  
**Associated Files:**
- Database Models: `KitRegistration`, `Operator`, `OperatorStationMapping`, `OperatorOnboardingDetail`
- Legacy Seeding Scripts: `seed_files/seed_kit_tracker.py`, `seed_files/seed_pending_lists.py`
- Reports System: `docs/REPORT_SECTION_REFERENCE.md`

---

## 1. Executive Summary & Problem Statement

### 1.1 The Current Manual Workflow
Currently, the data powering the **6 Automated System Reports** (`kit_tracker`, `district_wise_kit_count`, `operator_list`, `l1_pending_list`, `l2_pending_list`, `onboard_pending_list`) is populated via manual spreadsheet imports:
1. An administrator downloads Excel workbooks from the external portal (`Kit Tracker Chips.xlsx`, `L1 Pending List.xlsx`, `L2 Pending List.xlsx`, `Operator List.xlsx`, `Onboard Pending List.xlsx`).
2. A developer runs `seed_files/seed_kit_tracker.py` and `seed_files/seed_pending_lists.py`.
3. These scripts execute a destructive `TRUNCATE TABLE ... RESTART IDENTITY CASCADE` and re-insert rows from scratch.

### 1.2 The Goal
To replace manual file seeding with a **secure, automated, one-way incremental API synchronization pipeline** that pulls live updates from the external portal's database directly into our CHiPS PostgreSQL database (`chips_db_new`).

### 1.3 The Safety Guarantee (One-Way Pull)
* **Read-Only / One-Way:** Our system **only initiates HTTP GET requests** to the external portal's API.
* **Zero Outbound Mutation:** Our system has no write credentials or endpoints to modify the external portal's database.
* **Non-Destructive Upsert:** Instead of wiping tables with `TRUNCATE`, incoming records are **upserted** (updated if existing by Station ID / Operator Code, inserted if new), ensuring zero portal downtime.

---

## 2. Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       EXTERNAL PORTAL                       │
│                     (Source of Truth)                       │
│                                                             │
│   [Live MySQL / PostgreSQL Database]                        │
│                           │                                 │
│                           ▼                                 │
│           REST API Service (Protected by API Key)           │
│           GET /api/v1/reports-data/sync?updated_after=...   │
└───────────────────────────┬─────────────────────────────────┘
                            │
               HTTPS / TLS 1.3 (One-Way Pull)
               Headers: X-API-Key: <SECRET_KEY>
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   CHiPS AADHAAR PLATFORM                    │
│                                                             │
│  [Sync Trigger: Scheduled Cron / Admin UI / CLI Worker]     │
│                           │                                 │
│                           ▼                                 │
│      Sync Engine (`backend/services/external_sync.py`)      │
│                           │                                 │
│         ┌─────────────────┼─────────────────┐               │
│         ▼                 ▼                 ▼               │
│    Upsert Kit       Upsert Operator   Upsert Onboarding     │
│   Registration      & Station Map          Details          │
│         │                 │                 │               │
│         └─────────────────┼─────────────────┘               │
│                           ▼                                 │
│               PostgreSQL (`chips_db_new`)                   │
│   (kit_registration_table, operators, mappings, onboarding) │
│                           │                                 │
│                           ▼                                 │
│      Instant Live Reports on CHiPS Admin Dashboard!         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Data Mapping & Schema Alignment

The external API must return records corresponding to the operational kits and operators. Below is the precise field mapping from the legacy Excel sheets to the API JSON keys and internal database columns:

### 3.1 Kit Entity (`kit_registration_table` -> `KitRegistration`)
| Legacy Excel Column | API JSON Key | CHIPS DB Column | Type / Notes |
| :--- | :--- | :--- | :--- |
| `Station ID` / `Station Id` | `station_id` | `station_id` | `VARCHAR(50)` **(Primary Unique Key)** |
| `District` | `district` | `district` | `VARCHAR(100)` |
| `Machine ID` / `Machine Id` | `machine_id` | `machine_id` | `VARCHAR(255)` |
| `Laptop Serial No.` | `laptop_serial_no` | `laptop_serial_no` | `VARCHAR(255)` |
| `Laptop Name` | `laptop_name` | `laptop_name` | `VARCHAR(255)` |
| `Kit Slot` / `Category` | `kit_slot` | `category` | `VARCHAR(100)` (e.g., `Camp`, `Fixed`) |
| `Block` | `block` | `block` | `VARCHAR(100)` |
| `Locality` | `locality` | `locality` | `VARCHAR(100)` |
| `ASK Address` | `ask_address` | `ask_address` | `VARCHAR(255)` |
| `Station Status` | `station_status` | `station_status` | `VARCHAR(50)` |
| `Station ID Allotted Date` / `Station ID Provided Date` | `station_id_allotted_date` | `station_id_provided_date` | `DATE` (YYYY-MM-DD) |
| `L1 Status` | `l1_status` | `l1_status_id` | `INTEGER` (FK to `master_status.id`: Done=19/2, Pending=1, Rejected=14) |
| `L1 Date` / `L1 Done Date` | `l1_done_date` | `l1_done_date` | `DATE` |
| `L2 Status` | `l2_status` | `l2_status_id` | `INTEGER` (FK to `master_status.id`: Done=20/2/19, Pending=1, Rejected=14) |
| `L2 Date` / `L2 Done Date` | `l2_done_date` | `l2_done_date` | `DATE` |

### 3.2 Operator Entity (`operators` -> `Operator`)
| Legacy Excel Column | API JSON Key | CHIPS DB Column | Type / Notes |
| :--- | :--- | :--- | :--- |
| `Operator Id` | `operator_code` | `user_code` | `VARCHAR(50)` **(Primary Unique Key)** |
| `Operator Name` | `name` | `name` | `VARCHAR(120)` |
| `Operator Mobile` | `mobile` | `mobile` | `VARCHAR(15)` |
| `District` | `district` | `district_id` | `VARCHAR(20)` (Resolved to `district_table.district_code`, e.g. `RAI`) |
| `Operator Status` / `Operator Activation Status` | `status` | `status` | `VARCHAR(50)` (`Active`, `Inactive`, etc.) |
| `Security Deposit Status` / `SD Status` | `security_deposit_status` | `security_deposit_status`| `VARCHAR(50)` |
| `Security Deposit Date` | `security_deposit_date` | `security_deposit_date` | `DATE` |
| `Inactive Reason` / `Operator In-active Reason` | `inactive_reason` | `inactive_reason` | `VARCHAR(255)` |
| `Inactive Date` / `Operator In-active Date` | `inactive_date` | `inactive_date` | `DATE` |

### 3.3 Station Mapping (`operator_station_mappings` -> `OperatorStationMapping`)
| Entity Association | API Source | CHIPS DB Column | Type / Notes |
| :--- | :--- | :--- | :--- |
| Operator FK | `operator.operator_code` | `operator_id` | `INTEGER` (Foreign key to `operators.id`) |
| Operator FK | `operator.operator_code` | `operator_id` | `INTEGER` |
| Station ID | `station_id` | `station_id` | `VARCHAR(50)` |
| Mapping Timestamp | Auto-generated | `mapped_at` | `DATETIME` |

### 3.4 Onboarding Details (`operator_onboarding_details` -> `OperatorOnboardingDetail`)
| Legacy Excel Column | API JSON Key | CHIPS DB Column | Type / Notes |
| :--- | :--- | :--- | :--- |
| Mapping FK | Linked mapping | `mapping_id` | `INTEGER` |
| Operator FK | Linked operator | `operator_id` | `INTEGER` |
| Station ID | `station_id` | `station_id` | `VARCHAR(50)` |
| `Onboarding Status` | `onboarding_status` | `onboarding_status` | `VARCHAR(50)` |
| `Onboard Date` | `onboard_date` | `onboard_date` | `DATE` |
| `Visit Status` | `visit_status` | `visit_status` | `VARCHAR(50)` |
| `Visit Date` | `visit_date` | `visit_date` | `DATE` |
| `18+ Permit` | `permitted_18_plus` | `permitted_18_plus` | `VARCHAR(50)` |
| `Kit Working` | `kit_working_status` | `ask_kit_working_status` | `VARCHAR(50)` |
| `Remark` | `remark` | `remark` | `TEXT` |

---

## 4. API Contract Specification (External Portal)

The API contract and expected response format for synchronization:
* **API Endpoint:** `https://api.externalportal.gov.in/api/v1/sync/kit-tracker`
* **Method:** `GET`
* **Authentication Header:**
  ```http
  Authorization: Bearer <API_TOKEN>
  ```
* **Security & SSL:** When invoking via `curl.exe` on internal servers with internal SSL certificates, use the `-k` flag. In Python `requests`, set `verify=False`.

### 4.1 Production JSON Response Schema
The API returns three synchronized arrays in a single response:
```json
{
  "source_system": "KIT_TRACKER_PORTAL",
  "status": true,
  "status_code": 200,
  "msg": "record fetched",
  "operators": [
    {
      "operator_code": "OP_DUMMY_001",
      "operator_name": "John Doe",
      "mobile": "0000000000",
      "sd_status": "Y",
      "security_deposit_date": "2025-01-01 00:00:00",
      "active_status": "A",
      "operator_inactive_reason": null,
      "operator_inactive_date": null
    }
  ],
  "kits_details": [
    {
      "station_id": "ST_DUMMY_001",
      "district_code": 000,
      "machine_id": "MCH_DUMMY_001",
      "laptop_serial_no": "LPT_DUMMY_001",
      "laptop_name": "DUMMY_LAPTOP",
      "station_id_provided_date": "2025-01-01 00:00:00",
      "l1_machine_reg_status": "Y",
      "l1_machine_reg_date": "2025-01-01 00:00:00",
      "l2_machine_reg_status": "Y",
      "l2_machine_reg_date": "2025-01-01 00:00:00",
      "block_code": 000,
      "category": 1,
      "locality": "U",
      "ask_address": "Dummy Address",
      "station_id_status": "A"
    }
  ],
  "onboard_details": [
    {
      "station_id": "ST_DUMMY_001",
      "operator_code": "OP_DUMMY_001",
      "onboarding_status": "A",
      "onboard_date": "2025-01-01 00:00:00",
      "ask_kit_working_status": "Y",
      "permitted_18_plus": "N",
      "visit_status": "N",
      "visit_date": null,
      "remark": null
    }
  ]
}
```

### 4.2 Status Flag Conversion Matrix

| Entity | API Field | API Value | Meaning | CHiPS DB Target |
| :--- | :--- | :--- | :--- | :--- |
| **Kit** | `l1_machine_reg_status` | `"Y"` | L1 Registration Done | `l1_status_id = 19` |
| **Kit** | `l1_machine_reg_status` | `"N"` | L1 Registration Pending | `l1_status_id = 1` |
| **Kit** | `l2_machine_reg_status` | `"Y"` | L2 Registration Done | `l2_status_id = 20` |
| **Kit** | `l2_machine_reg_status` | `"STU"` | Under Processing | `l2_status_id = 17` |
| **Kit** | `l2_machine_reg_status` | `"N"` | L2 Registration Pending | `l2_status_id = 1` |
| **Kit** | `station_id_status` | `"A"` | Station Active | `station_status = "Active"` |
| **Kit** | `locality` | `"U"` / `"R"` | Urban / Rural | `locality = "Urban"` / `"Rural"` |
| **Kit** | `district_code` | `000` | LGD District Code | Looked up in `district_table` |
| **Operator**| `active_status` | `"A"` | Active | `status = "Active"` |
| **Operator**| `sd_status` | `"Y"` | Yes | `security_deposit_status = "Yes"` |
| **Onboarding**| `onboarding_status`| `"A"` | Active | `onboarding_status = "Active"` |
| **Onboarding**| `ask_kit_working_status`| `"Y"` | Working | `ask_kit_working_status = "Working"` |
| **Onboarding**| `permitted_18_plus` | `"Y"` | Permitted 18+ | `permitted_18_plus = "Yes"` |
| **Onboarding**| `visit_status` | `"Y"` | Visit Completed | `visit_status = "Completed"` |

---

## 5. Step-by-Step Setup Guide

### Step 1: Configure Environment Variables
In `.env` on your local development system and on the Rocky Linux VM:

```ini
# External Portal API Connectivity
EXTERNAL_PORTAL_API_URL=https://api.externalportal.gov.in/api/v1/sync/kit-tracker
EXTERNAL_PORTAL_API_KEY=your_secret_api_key_here
EXTERNAL_PORTAL_TIMEOUT_SECONDS=30
```

### Step 2: Test API Connectivity & Response Preview
Run the response inspector tool:
```powershell
.venv\Scripts\python useful_files/check_api_response.py --url "https://api.externalportal.gov.in/api/v1/sync/kit-tracker" --key "YOUR_API_KEY_HERE"
```

### Step 3: Run Live Dry-Run Ingestion (No Database Commit)
Test the ingestion engine without modifying any database tables:
```powershell
.venv\Scripts\python -m backend.services.external_reports_sync --dry-run
```

### Step 4: Execute Full Live Database Sync
When ready to synchronize your database with the live portal:
```powershell
# Option A: Exact Mirror sync (default - inserts, updates, and prunes obsolete records)
.venv\Scripts\python -m backend.services.external_reports_sync

# Option B: Additive sync (inserts and updates only; NEVER deletes or prunes old records)
.venv\Scripts\python -m backend.services.external_reports_sync --no-exact-mirror
```

> [!NOTE]
> **Exact Mirror Mode (Enabled by default):**
> The sync engine operates in **Exact Mirror** mode. It updates changed records, inserts new records, and prunes old test records that no longer exist in the government portal, ensuring your database is an exact 1-to-1 replica. To disable pruning and keep old records untouched, pass `--no-exact-mirror`.


### Step 5: Automate with Scheduled Background Execution
On the Rocky Linux VM:
```bash
# Edit crontab on Rocky Linux VM
crontab -e

# Option A: Automated 2-hour sync with Exact Mirror (Default - keeps DB in 1-to-1 sync)
0 */2 * * * docker exec chips-backend python -m backend.services.external_reports_sync >> /var/log/chips_sync.log 2>&1

# Option B: Automated 2-hour sync WITHOUT Pruning (Never deletes/prunes any records)
0 */2 * * * docker exec chips-backend python -m backend.services.external_reports_sync --no-exact-mirror >> /var/log/chips_sync.log 2>&1
```

---

## 6. District Resolution & Aliases Handling

To guarantee that district names align seamlessly between external data and the CHiPS database:
1. **Primary Lookup (District Code):**
   The external API provides integer LGD district codes. The sync engine directly maps this to `district_table.district_code`.
2. **Secondary Lookup (Normalized Name):**
   If district text is provided, [`backend/utils/district_mapper.py`](file:///d:/project/Aadhar-Project/backend/utils/district_mapper.py) normalizes variants to the standard master name.

---

## 7. Future Roadmap: Two-Way (Bidirectional) Synchronization

If ground-level operational changes made on CHiPS (e.g. visit verification, remarks, operator status updates) need to flow back to the external portal:

### 7.1 Key Requirements
1. **Source Origin Tracking:**
   Payloads must include `"sync_origin": "CHIPS"` to prevent ping-pong / infinite update loops.
2. **Field-Level Ownership:**
   * **External Portal Owns:** Hardware allotment (`station_id`, `machine_id`, `laptop_serial_no`, `l1_machine_reg_status`).
   * **CHiPS Portal Owns:** Field operations (`visit_status`, `visit_date`, `ask_kit_working_status`, `remark`).
3. **Outbox Pattern:**
   CHiPS writes changes to a local `sync_outbox` table, and an outbound worker pushes them to the external portal's `POST /api/v1/sync/push-batch` endpoint with automatic retry on failure.
