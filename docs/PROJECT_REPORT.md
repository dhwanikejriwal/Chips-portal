# CHiPS LMS Credentials Portal — Project Report

## 1. Overview

The **CHiPS LMS Credentials Portal** is a web portal built for the **Chhattisgarh Infotech Promotion Society (CHiPS)**. It streamlines the end-to-end lifecycle of **Aadhaar operator onboarding**, document verification, and the assignment of **LMS / NSEIT credentials**.

The system covers three primary user journeys:

1. **Candidate Onboarding & Tracking** — public registration (Photo, Aadhaar, Marksheets), status tracking via Request Code, and a candidate dashboard to view assigned LMS/NSEIT credentials.
2. **District Coordinator (DC) Portal** — district-scoped pending queues, approve/reject workflow (auto credential generation), automated candidate emails, and CSV export.
3. **CHiPS Admin / EDM Portal** — centralized cross-district view, LMS & NSEIT status management, and global filtered/bulk export.

Additional operational modules include operator activation, reactivation, station-ID allocation, kit registration, L1/L2 registration workflows, monitoring dashboards, and **Operator Activity ingestion (ETL over uploaded spreadsheets)**.

---

## 2. Architecture

The project uses a **decoupled, two-tier architecture** separating presentation from business logic:

| Tier | Component | Port | Responsibility |
|------|-----------|------|----------------|
| Presentation | **Flask Frontend Proxy** | 5000 | Serves HTML templates, static assets, handles session/login, proxies data calls to the API |
| Application | **FastAPI Backend Gateway** | 8000 | REST API, business logic, Pydantic validation, JWT auth, background email, ETL, OCR |
| Data | **PostgreSQL** | 5432 | Persistent relational store accessed via SQLAlchemy ORM |

**Request flow:** `Browser ⇄ (Fetch API / HTML) ⇄ Flask Proxy (5000) ⇄ (REST / JWT) ⇄ FastAPI (8000) ⇄ (SQLAlchemy) ⇄ PostgreSQL`

The frontend (`app/`) is organized into **blueprints** (one per feature) mirrored by matching **routers** in the backend (`backend/`), giving a clean 1:1 feature separation between the two services.

---

## 3. Technology Stack

### 3.1 Core Language & Runtime

| Technology | Purpose of Use |
|------------|----------------|
| **Python 3.12+** | Primary implementation language for both frontend proxy and backend API |
| **uv / pyproject.toml** | Dependency resolution and lockfile management (`uv.lock`, `requirements.txt`) |

### 3.2 Backend (FastAPI Service)

| Technology | Purpose of Use |
|------------|----------------|
| **FastAPI** | High-performance REST API framework serving all business logic endpoints |
| **Uvicorn** | ASGI server that runs the FastAPI application |
| **Starlette** | Underlying ASGI toolkit (routing, middleware, CORS) used by FastAPI |
| **Pydantic** (`pydantic[email]`) | Request/response validation, schema modeling, and email field validation |
| **python-jose[cryptography]** | JWT token generation and verification for stateless authentication |
| **passlib[bcrypt] / bcrypt** | Secure password hashing and verification |
| **python-multipart** | Parsing multipart form data (file uploads, OAuth2 form logins) |
| **fastapi-mail** | Sending transactional emails (approval/rejection notifications) via SMTP |

### 3.3 Frontend (Flask Service)

| Technology | Purpose of Use |
|------------|----------------|
| **Flask** | Frontend proxy server rendering HTML layouts and routing browser requests |
| **Flask-Login** | Session-based user login/authentication on the frontend |
| **Jinja2** | Server-side HTML templating engine |
| **Werkzeug** | WSGI utilities underpinning Flask (routing, request handling) |
| **Tailwind CSS + Vanilla CSS** | Styling — utility-first classes combined with modular custom CSS (`tokens.css`, per-feature stylesheets) |
| **JavaScript (native `fetch`)** | Dynamic, no-reload data interactions with the backend API |
| **SweetAlert2** | Interactive popups / confirmation & error dialogs |

### 3.4 Database & ORM

| Technology | Purpose of Use |
|------------|----------------|
| **PostgreSQL** | Primary relational database |
| **SQLAlchemy** | ORM defining models and querying the database |
| **Flask-SQLAlchemy** | Flask integration layer for SQLAlchemy |
| **psycopg / psycopg2-binary** | PostgreSQL database drivers (v3 and v2 binary builds) |
| **Alembic** | Database schema migrations (versioned in `migrations/`) |
| **Flask-Migrate** | Flask wrapper around Alembic for migration commands |

### 3.5 Background Tasks & Caching

| Technology | Purpose of Use |
|------------|----------------|
| **Celery** | Distributed task queue for asynchronous/background jobs |
| **Redis** | Message broker / cache backend supporting Celery and caching |
| **kombu / amqp / billiard / vine** | Messaging primitives underpinning Celery |

### 3.6 Data Processing & ETL (Operator Activity module)

| Technology | Purpose of Use |
|------------|----------------|
| **DuckDB** | In-memory analytical ETL engine for processing uploaded activity files |
| **python-calamine** | Fast, low-memory reader for large `.xlsx` files |
| **pandas / numpy** | Tabular data manipulation and numeric processing |
| **openpyxl** | Reading/writing Excel workbooks (exports) |

### 3.7 OCR & Fuzzy Matching (Document Verification)

| Technology | Purpose of Use |
|------------|----------------|
| **pytesseract** | OCR — extracting text from uploaded documents (Aadhaar, marksheets) |
| **pdf2image** | Converting PDF pages to images for OCR |
| **Pillow** | Image loading/processing pipeline for OCR |
| **thefuzz / python-Levenshtein** | Fuzzy string matching to reconcile OCR text against submitted data |

### 3.8 Utilities & Configuration

| Technology | Purpose of Use |
|------------|----------------|
| **python-dotenv** | Loading environment/config from `.env` (DB URL, secrets, SMTP) |
| **requests** | HTTP client — Flask proxy calling the FastAPI backend |
| **email-validator** | Validating email address format (via Pydantic) |
| **cryptography** | Cryptographic backend for JWT and secure mail |

### 3.9 Internationalization (i18n)

| Technology | Purpose of Use |
|------------|----------------|
| **Custom i18n (`i18n.js` + `en.json` / `hi.json`)** | English/Hindi language toggle (`ENABLE_LANGUAGE_TOGGLE`) for the UI |
| **GeoJSON (Chhattisgarh districts)** | District-level map/boundary visualization on monitoring dashboards |

### 3.10 Testing

| Technology | Purpose of Use |
|------------|----------------|
| **pytest** | Unit testing (e.g. `tests/test_registrar_ea_transform.py`), with `.pytest_cache` present |

---

## 4. Project Structure

| Path | Role |
|------|------|
| `app/` | Flask frontend proxy — `blueprints/` (feature routes), `templates/`, `static/` (css/js/i18n), `utils/`, `config.py` |
| `backend/` | FastAPI service — `routers/` (API endpoints), `models/` (SQLAlchemy models), `services/` (ETL/ingest logic), `utils/` (OCR), `main.py`, `database.py` |
| `migrations/` | Alembic migration scripts |
| `seed*.py` | Database seeding scripts (baseline accounts, station-ID master, operator activity) |
| `data/` , `uploads/` | Uploaded/ingested files (activity uploads, rejected records) |
| `tests/` | Pytest suite |
| `docs/` | Documentation (e.g. `OPERATOR_ACTIVITY.md`, this report) |

**Feature parity:** each frontend blueprint (`auth`, `candidate`, `lms_manage`, `nseit_manage`, `l1_registration`, `l2_registration`, `operator_activation`, `reactivation`, `station_id`, `kit_registration`, `operator_mapping`, `operator_onboarding`, `monitoring`, `dashboard`, `operator_activity_dashboard`) maps to a corresponding backend router.

---

## 5. Key Technical Notes

- **CORS** is enabled wide-open (`allow_origins=["*"]`) on the FastAPI service to permit the Flask proxy and browser fetch calls.
- **Auto-migrations on startup:** `backend/main.py` runs `Base.metadata.create_all`, applies idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` guards, and executes `alembic upgrade head` automatically when the API boots.
- **Global exception handler** logs unhandled exceptions to `c:\chips-portal\error.log` and returns a JSON 500.
- **Authentication is dual-layered:** JWT (stateless) on the FastAPI backend and Flask-Login sessions on the frontend proxy.
- **Two Postgres drivers** are bundled (`psycopg` v3 and `psycopg2-binary`) — the v2 binary build is intentionally included to avoid native C compilation issues on Windows.

---

*Report generated: 2026-07-24*
