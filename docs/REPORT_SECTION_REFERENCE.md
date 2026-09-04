# Reports Section - Architecture, Data Sources & Working Reference

> **Document Purpose:** Complete technical reference and workflow guide for the **Reports Section** in the CHiPS Aadhaar Project. This document details how reports are generated, where their underlying data originates, how the frontend and backend communicate, and how each specific report is calculated.

---

## 1. System Architecture Overview

The application utilizes a two-tier architecture consisting of a **Flask frontend application** and a **FastAPI backend service**, backed by a **PostgreSQL database** and local file storage.

```
       +-------------------------------------------------------------+
       |                         Client Browser                      |
       |  (UI: reports_dash.html + JavaScript: report_scripts.html)   |
       +-------------------------------------------------------------+
                                    |
                                    | HTTP Requests / AJAX
                                    v
       +-------------------------------------------------------------+
       |               Flask Web Application (Frontend)              |
       |               app/blueprints/report.py                      |
       |   - Renders Dashboard (Jinja2)                              |
       |   - Role-Based Access (CHiPS Admin vs DC / EDM)             |
       |   - Transparent API Proxy (/reports/proxy/* -> FastAPI)     |
       +-------------------------------------------------------------+
                                    |
                                    | Proxy Forwarding (Requests)
                                    v
       +-------------------------------------------------------------+
       |                  FastAPI Backend Server                     |
       |                  backend/routers/report.py                  |
       |   - Business Logic & Aggregations (Pandas)                  |
       |   - Excel Multi-sheet Generation (OpenPyXL)                 |
       |   - Raw Dataset Schema Auto-detection & Validation          |
       +-------------------------------------------------------------+
                   |                                     |
                   | SQLAlchemy ORM Queries              | File I/O
                   v                                     v
       +-----------------------+              +----------------------+
       |   PostgreSQL Database |              | Local File System    |
       |   (10+ Core Models)   |              | uploads/reports/*.xlsx
       +-----------------------+              +----------------------+
```

---

## 2. Core Code Files & Locations

| Component | File Path | Responsibility |
| :--- | :--- | :--- |
| **Backend Router** | [`backend/routers/report.py`](file:///d:/project/Aadhar-Project/backend/routers/report.py) | Houses all data extraction algorithms, pandas aggregations, dataset validation, Excel writer, and preview/download API endpoints. |
| **Database Model** | [`backend/models/report.py`](file:///d:/project/Aadhar-Project/backend/models/report.py) | Defines the `ReportHistory` table for tracking uploaded and generated custom reports. |
| **District Utilities** | [`backend/utils/district_mapper.py`](file:///d:/project/Aadhar-Project/backend/utils/district_mapper.py) | Provides centralized master maps for Division mappings, LWE (Left Wing Extremism) district detection, and name normalization. |
| **Flask Blueprint** | [`app/blueprints/report.py`](file:///d:/project/Aadhar-Project/app/blueprints/report.py) | Renders the HTML template, controls DC vs Admin permissions, and proxies client AJAX calls to FastAPI backend. |
| **Frontend UI Template**| [`app/templates/report/reports_dash.html`](file:///d:/project/Aadhar-Project/app/templates/report/reports_dash.html) | The HTML structure, pills/tabs navigation, report cards, history list, file upload form, and preview modal. |
| **Frontend Scripts** | [`app/templates/report/report_scripts.html`](file:///d:/project/Aadhar-Project/app/templates/report/report_scripts.html) | Client-side logic: AJAX calls, live search, sorting by pending, pagination rendering, modal fullscreen, drilldowns. |
| **Stylesheets** | [`app/static/css/chips/reports.css`](file:///d:/project/Aadhar-Project/app/static/css/chips/reports.css) | Styling for report cards, preview table, responsive modal, and KPI stat blocks. |

---

## 3. Two Main Modules in Reports Section

The Reports dashboard is divided into two primary functional areas:
1. **Automated System Reports** (Live portal data directly from database)
2. **Custom Dataset Uploads** (Raw third-party portal exports processed into standardized multi-sheet reports)

---

## 4. Module 1: Automated System Reports (`system-requests`)

These reports are generated dynamically on demand from the portal's live PostgreSQL tables using SQLAlchemy and Pandas.

### A. List of Reports & Their Database Sources

#### 1. Kit Tracker (`kit_tracker`)
* **Purpose:** Complete master dataset capturing station ID allotment, laptop hardware details, mapped operators, security deposits, L1/L2 approval status, deployment locations, and field onboarding statuses.
* **Data Sources (Tables / Models):**
  * `KitRegistration` (`kit_registration_table`)
  * `Operator` (`operators`)
  * `OperatorStationMapping` (`operator_station_mappings`)
  * `OperatorOnboardingDetail` (`operator_onboarding_details`)
  * `MasterStatus` (`master_statuses`)
* **Calculations & Special Logic:**
  * Maps `KitRegistration.station_id` -> `OperatorStationMapping.station_id` -> `Operator.id`.
  * Joins onboarding status from `OperatorOnboardingDetail`.
  * Computes `is_lwe_district(district)` based on Chhattisgarh master map.
  * Formats mobile numbers (removes float suffixes like `.0`).

#### 2. District Wise Kit Count (`district_wise_kit_count`)
* **Purpose:** District-level executive summary matrix displaying kits, operator credentials, L1/L2 status, security deposits, and operational ask-kit health.
* **Data Sources (Tables / Models):**
  * `District` (`districts`)
  * `KitRegistration`, `Operator`, `OperatorStationMapping`, `OperatorOnboardingDetail`, `MasterStatus`
* **Structure:** MultiIndex hierarchical columns in pandas/Excel:
  * Total Machine & Allotted Station IDs
  * Security Deposit (Camp / Yes / Pending)
  * L1 Status (Yes / No)
  * L2 Status (Yes / No / Send to CHiPS / Send to UIDAI)
  * Operator Activation Status (Active / Inactive SentToChips)
  * Operator Onboarding Status (Active / Inactive)
  * Station ID Status (Active / Inactive)
  * ASK Kit Working Status (Active / Inactive)
* **Interactive Drill-down:**
  * Clicking on any district row opens a **District Station Details View** (`/system/district_wise_kit_count/details/{district_name}`).
  * Provides station-by-station breakdown, status filters, and instant KPI counter tiles (Pending L1, Pending L2, Pending SD, Inactive Ops, Inactive Stations).

#### 3. Operator List (`operator_list`)
* **Purpose:** Directory of all Aadhaar operators with credentials, contact details, security deposit dates, mapped kit location, certificate numbers, and validity periods.
* **Data Sources (Tables / Models):**
  * `Operator` (`operators`)
  * `KitRegistration` (`kit_registration_table`)
  * `OperatorStationMapping` (`operator_station_mappings`)
  * `District` (`districts`)
  * `Candidate` (`candidate_table`)
  * `OperatorActivationRequest` (`operator_activation_requests`)
* **Special Logic:**
  * Implements a fallback lookup for district resolution: Kit district -> Operator `district_id` -> Activation Request -> Candidate registration code/mobile.

#### 4. L1 Pending List (`l1_pending_list`)
* **Purpose:** Tracks all machine kits that have received a Station ID but have not completed Level-1 (L1) registration.
* **Data Sources (Tables / Models):**
  * `KitRegistration`, `MasterStatus`, `Operator`, `OperatorStationMapping`
* **Filter Rule:**
  * Kit where `l1_status_id` is NOT in `[19, 2]` and status is NOT `'done' / 'approved' / 'yes'`.
* **Calculated Metrics:**
  * `calculate_pending_days(station_id_provided_date)`: Days elapsed from station allotment to today.
  * Rows pending > 7 days are automatically flagged with a reddish warning tint in the UI table preview.

#### 5. L2 Pending List (`l2_pending_list`)
* **Purpose:** Tracks kits that have passed L1 registration successfully but are still pending Level-2 (L2) registration/UIDAI approval.
* **Data Sources (Tables / Models):**
  * `KitRegistration`, `MasterStatus`, `Operator`, `OperatorStationMapping`
* **Filter Rule:**
  * Kit where L1 IS completed (`l1_status_id in [19, 2]`), but L2 is NOT completed (`l2_status_id not in [2, 19]`).
* **Calculated Metrics:**
  * `calculate_pending_days(l1_done_date)`: Elapsed days between L1 completion and today.

#### 6. Onboard Pending List (`onboard_pending_list`)
* **Purpose:** Tracks operators who have completed both L1 and L2 milestones but have not yet completed physical/system onboarding to commence enrollments.
* **Data Sources (Tables / Models):**
  * `KitRegistration`, `MasterStatus`, `Operator`, `OperatorStationMapping`, `OperatorOnboardingDetail`
* **Filter Rule:**
  * Kit where L2 IS completed, but `onboarding_status` is not `'done' / 'active' / 'yes' / 'onboarded'`.
* **Calculated Metrics:**
  * `calculate_pending_days(l2_done_date)`.

#### 7. LMS Request Summary (`lms_summary`)
* **Purpose:** District-wise breakdown of candidate LMS (Learning Management System) training enrollments.
* **Data Sources (Tables / Models):**
  * `District` (`districts`)
  * `LMS` (`lms_requests`)
  * `Candidate` (`candidate_table`)
* **Metrics Aggregated:**
  * Total LMS Requests, Approved LMS, Pending LMS, Rejected LMS.
* **Interactive Drill-down:**
  * Clicking any district loads candidate-level details (`/system/lms_summary/details/{district_name}`).

#### 8. NSEIT Request Summary (`nseit_summary`)
* **Purpose:** District-wise summary of candidates registered for NSEIT certification examination.
* **Data Sources (Tables / Models):**
  * `District` (`districts`)
  * `NSEITRequest` (`nseit_requests`)
  * `Candidate` (`candidate_table`)
* **Metrics Aggregated:**
  * Total NSEIT Requests, Approved NSEIT, Pending NSEIT, Rejected NSEIT.
* **Interactive Drill-down:**
  * Clicking any district loads candidate-level details (`/system/nseit_summary/details/{district_name}`).

---

## 5. Module 2: Custom Dataset Uploads (`custom-datasets`)

This feature processes raw administrative CSV / Excel files uploaded by the state administrative team (e.g. from the central UIDAI or education portals) into structured, multi-tab analytical reports.

### A. The Ingestion & Processing Pipeline

1. **Upload & Header Auto-Detection:**
   * Uses `_detect_header_row()` to scan the first 20 rows of the uploaded file for keywords like `District`, `S.No`, `Sr No`, `State`.
   * Automatically handles files with metadata banners or notes at the top.

2. **Dataset Signature Detection & Strict Validation:**
   The backend inspects column names to automatically detect the dataset type and enforce correctness:

   | Category | Internal Type | Detection Signature / Keywords | Key Required Columns |
   | :--- | :--- | :--- | :--- |
   | **Centenarian District Report** | `cenetarian_district_report` | `alive`, `deceased`, `verifiable`, `centenarian` | `Alive Total`, `Deceased Total`, `Not verifiable Total`, `Pending Total` |
   | **MBU District Wise Report** | `mbu_district_wise` | `mbu`, `student`, `aadhaar verified` | `Total Student`, `MBU Pending (Age 5-15)`, `MBU Pending (Age 15 and above)` |
   | **18 Plus Pendency** | `18_plus_pendency` | `approved at state`, `rejected at state`, `pending at state`, `web service`, `18 plus` | `Total Approved`, `Total Rejected`, `Total Pending` |

   * **Mismatch Protection:** If the file does not match any recognized schema, or if the user selected "18 Plus Pendency" but uploaded an "MBU Report", the backend throws a descriptive HTTP 400 error explaining the exact mismatch.
   * **Duplicate Prevention:** Client checks filename against previously uploaded reports and blocks redundant uploads.

3. **Data Cleaning & Normalization:**
   * Strips non-data metadata rows (e.g., `(1)`, `(2)`, `Total`).
   * Normalizes district names via `backend.utils.district_mapper.normalize_district_name()`.
   * Cleans contact/mobile columns to prevent scientific notation formatting.

4. **Derived Metrics Calculation:**
   * **MBU Pendency:**
     $$\text{Total Pending} = \text{MBU Pending (Age 5-15)} + \text{MBU Pending (Age 15 and above)}$$
     $$\text{MBU Pendency \%} = \left(\frac{\text{Total Pending}}{\text{Total Students Aadhaar Provided}}\right) \times 100$$
   * **18 Plus & Centenarian:**
     $$\text{Total Requests} = \text{Total Approved} + \text{Total Rejected} + \text{Total Pending}$$
     $$\text{Pending \%} = \left(\frac{\text{Total Pending}}{\text{Total Requests}}\right) \times 100$$

5. **Multi-Sheet Excel Generation (OpenPyXL):**
   The backend generates an `.xlsx` file containing multiple tabs:
   * **`Combined` Tab:** Complete state-level compilation sorted alphabetically by District. If any master district from the database is missing in the dataset, it is auto-injected with `0` counts so reports remain complete.
   * **`LWE` Tab:** Filtered subset containing only districts designated as Left Wing Extremism affected.
   * **Division Tabs:** Separate sheets for each administrative division:
     * `Bilaspur Div`
     * `Raipur Div`
     * `Durg Div`
     * `Bastar Div`
     * `Surguja Div`
   * **Academic Year Tabs:** If the dataset contains an `Academic Year` column, individual tabs are generated per academic session.

6. **Storage & History Logging:**
   * Output file saved to: `uploads/reports/report_{report_type}_{timestamp}_{uuid}.xlsx`.
   * Record logged in `report_history` database table:
     * `id`, `report_type`, `filename`, `original_filename`, `file_path`, `created_at`.

---

## 6. Frontend Features & User Experience

* **Role-Based Access Control:**
  * **CHiPS Admin:** Unrestricted access to all 8 system reports and custom dataset uploads.
  * **District Coordinator (DC / EDM):** Restricted to their assigned district. "Custom Dataset Uploads" is hidden. Multi-sheet views only display tabs relevant to their district/division.
* **Interactive Modal Preview:**
  * Paginated table rendering (10, 25, 50, 100 rows per page).
  * Live search input filtering across Station ID, Operator Name, and District.
  * "Sort by Requests" / "Sort by Pending" button for quick prioritization.
  * Toggle Fullscreen mode for viewing wide tables comfortably.
  * Direct "Download Excel" button preserving all active filters.

---

## 7. Complete API Route Reference

| HTTP Method | Route URL | Query / Form Parameters | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/reports/system/{report_name}/preview` | `lwe`, `division`, `district`, `search`, `page`, `page_size` | Returns HTML preview table & pagination metadata for a system report. |
| `GET` | `/api/reports/system/{report_name}/download` | `lwe`, `division`, `district` | Downloads formatted `.xlsx` spreadsheet for the specified system report. |
| `GET` | `/api/reports/system/district_wise_kit_count/details/{district_name}` | `page`, `page_size`, `search`, `l1`, `l2`, `sd`, `op`, `st` | Fetches station-level drill-down rows & KPI statistics for a single district. |
| `GET` | `/api/reports/system/district_wise_kit_count/details/{district_name}/download` | Filter params | Downloads station-level Excel sheet for a specific district. |
| `GET` | `/api/reports/system/{report_name}/details/{district_code}` | `page`, `page_size`, `search` | Fetches LMS or NSEIT drill-down candidate rows for a single district. |
| `POST`| `/api/reports/generate` | `report_type`, `file` (multipart), `district` (opt) | Validates uploaded dataset, computes metrics, creates multi-sheet Excel file, and logs history. |
| `GET` | `/api/reports/history` | *None* | Returns list of all previously processed custom dataset reports. |
| `GET` | `/api/reports/preview/{report_id}` | *None* | Generates HTML preview for each sheet of an uploaded custom report. |
| `GET` | `/api/reports/download/{report_id}` | *None* | Downloads the stored multi-sheet Excel file by report ID. |
| `DELETE`| `/api/reports/{report_id}` | *None* | Deletes the report record from DB and deletes the `.xlsx` file from the project directory. |

---

## 8. Report Storage, Deletion & Self-Healing Path Resolution (VM Architecture)

* **Storage Location on VM:**
  * In the Rocky Linux target VM (`VM_CONFIG.txt` & `docker-compose.yml`), the application runs inside Docker with the external Docker volume `uploads_data` (`chips-portal_uploads_data`), which resides on the dedicated **250 GB Data Disk** (e.g. `/data/docker-volumes/` or `/data/docker`).
  * Inside the container, this volume is mounted at `/app/uploads`. All generated Excel and CSV reports are written to `/app/uploads/reports/` (`REPORTS_DIR`).
* **Environment-Aware Path Resolution:**
  * To accommodate environment differences between Windows host development and Docker containers (`/app/uploads/reports/` vs local Windows workspace `uploads/reports/`), the system dynamically checks:
    1. Direct database `file_path`.
    2. Local/mounted `REPORTS_DIR` using `filename`.
    3. Local/mounted `REPORTS_DIR` using the basename of `file_path`.
    4. VM container paths (`/app/uploads/reports/`, `/data/uploads/reports/`, etc.).
* **Deletion Guarantee on VM:**
  * When `DELETE /api/reports/{report_id}` is executed:
    1. The server gathers all possible candidate file paths on disk (including `/app/uploads/reports/{filename}` inside the VM volume).
    2. Calls `os.remove` on all matching physical `.xlsx` files, ensuring the file is **completely deleted from the VM's storage volume**.
    3. Deletes the `ReportHistory` database record from PostgreSQL.
    4. The frontend unmounts the deleted row from the UI and updates the history cards.
