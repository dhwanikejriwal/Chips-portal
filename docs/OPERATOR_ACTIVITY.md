# Operator Activity — Dashboard Section

Tracks daily productivity of Aadhaar enrolment operators (new enrolments, 18+,
demographic/biometric updates, MBU split, off-hours) per operator / station /
day, plus a **Kit Tracker** master table. Two ingestion pipelines feed it:

| Source file | Loaded into | Notes |
|---|---|---|
| `Kit Tracker.xlsx` | `kit_tracker` | Operational master, one row per Station ID. District/operator resolved to IDs. |
| `RegistrarEA…csv/xlsx` | `operator_daily_activity` (+ `activity_stations`, `operator_activity_master`) | Only the **aggregated** filter+group-by result is stored; the raw file is discarded. |

## Architecture

```
Browser (Jinja page + operator_activity.js)
   │  fetch()  /auth/chips/operator-activity/*        (Flask blueprint, adds bearer token)
   ▼
Flask proxy (app/blueprints/operator_activity_dashboard.py)
   │  requests → 127.0.0.1:8000/operator-activity/*
   ▼
FastAPI router (backend/routers/operator_activity.py)
   │  all aggregation in SQL (Postgres)
   ▼
Ingestion services (backend/services/*)
   • registrar_ea_transform.py — DuckDB reads the file, filters+aggregates in bounded memory
   • registrar_ea_ingest.py     — idempotent upsert, quarantine, batch tracking, cleanup
   • kit_tracker_ingest.py      — openpyxl stream, district/operator ID resolution, upsert
   • missing_dates.py           — daily-upload gap detection → notification reminder
```

## Ingestion (memory-optimised)

- **DuckDB** reads the uploaded CSV/XLSX directly (`read_csv` streaming; calamine for xlsx),
  runs the whole filter + group-by in SQL in an in-memory ephemeral database, and returns
  only the ~aggregated rows. Postgres never sees the raw file. The file is **deleted** after.
- Filter is configurable: `REGISTRAR_CODE` / `EA_CODE` (`.env`, default `986` / `2084`),
  overridable per upload. Both sides coerced to numbers before comparing.
- `machine_address` is factored into `activity_stations` (keyed on
  `(station_ea_code, station_number)`) so the long free-text address stays out of the fact
  group key. Stations mapping to >1 address are flagged on the job summary.
- Idempotent: unique key `(activity_date, station_ea_code, session_operator_id, station_number)`
  with `ON CONFLICT DO UPDATE` — re-uploading the same day never double-counts.
- Rows with unparseable dates / negative counts are **quarantined** and offered as a
  downloadable CSV on the job summary.
- Processing runs on **FastAPI BackgroundTasks**; the modal polls `/upload/{batch_id}`.

## Missing-date reminder

The RegistrarEA file is expected daily. `activity_daily_upload_log` records each covered
date; `missing_dates.py` walks from `ACTIVITY_TRACKING_START` (or the earliest covered date)
to *yesterday* and reports gaps. Gaps surface:
- on the page as an amber banner (`GET /operator-activity/missing-dates`), and
- in the existing **notification bell** for Admin/EDM (merged into
  `/api/notifications/summary` as a `reminders[]` entry).

## API (FastAPI, prefix `/operator-activity`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/upload` | multipart: `file`, `source` (`registrar_ea`\|`kit_tracker`), optional `registrar_code`/`ea_code` → `{batch_id}` |
| GET | `/upload/{batch_id}` | job status/stage/progress/summary/errors |
| GET | `/uploads` | upload history |
| DELETE | `/uploads/{batch_id}` | roll back a batch |
| GET | `/rejected/{batch_id}` | quarantined rows CSV |
| GET | `/` | list — see params below → `{rows, totals, summary, pagination}` |
| GET | `/filters` | distinct districts / stations / eaCodes + min/max date |
| GET | `/export` | streamed CSV of the current filtered+sorted set |
| GET | `/missing-dates` | gap dates for the reminder |
| GET | `/anomalies` | operator/station log records that don't reconcile with the Kit Tracker — see below |
| GET | `/operators/{session_operator_id}` | drill-down profile |
| GET | `/operators/{session_operator_id}/activity?from&to` | per-operator daily activity, stations, off-hours |
| POST | `/kit-tracker/upload` | multipart xlsx → `{batch_id}` |
| GET | `/kit-tracker` | kit tracker list (`district`, `status`, `search`, `sortBy`, `sortDir`, `page`, `pageSize`) |

### List query params (`GET /operator-activity`)
`from`, `to` (YYYY-MM-DD), `districts[]`, `stations[]`, `eaCodes[]`, `search`,
`offHoursOnly` (bool), `groupBy` (`operator`\|`daily`), `sortBy`, `sortDir` (`asc`\|`desc`),
`page`, `pageSize` (≤200). Ranges wider than `ACTIVITY_MAX_RANGE_DAYS` (default 366) → 400.

## Operator Anomalies (`GET /operator-activity/anomalies`)

Reconciles the uploaded logs against the Kit Tracker on **operator ID** and
**station ID**. Params: `from`, `to`, `districts[]`, `search`, `page`, `pageSize`.

Model rule for this subsection: a station ID **present** in the Kit Tracker is
`Inhouse`; a station ID **absent** from it is `VLE`. (The main list calls the same
classification `ECMP`/`VLE`, and applies it per-operator rather than per-station.)

One row per operator+station pair seen in the logs, aggregated over the window.
Only flagged rows are returned; a row carries every reason it tripped:

| Code | Meaning |
|---|---|
| `mixed_model` | operator logs at both an Inhouse and a VLE station |
| `operator_mismatch` | Kit Tracker assigns a different operator to that station |
| `no_kt_operator` | station is in the Kit Tracker with no operator assigned |
| `operator_not_in_kt` | Inhouse station, but the log operator is nowhere in the Kit Tracker |
| `assigned_elsewhere` | the log operator is assigned to (an)other station(s) in the Kit Tracker |
| `kt_multi_station` | the Kit Tracker assigns this operator to more than one station |

`summary.by_reason` counts overlap, since one record can trip several checks.

## Config (`.env`)

```
REGISTRAR_CODE=986
EA_CODE=2084
ACTIVITY_TRACKING_START=2026-07-14     # optional; else earliest covered date
ACTIVITY_MAX_RANGE_DAYS=366            # optional
ACTIVITY_UPLOAD_DIR=...                # optional (default <root>/data/activity_uploads)
ACTIVITY_REJECTED_DIR=...              # optional (default <root>/data/activity_rejected)
```

## Frontend wiring

- Page: `GET /auth/chips/operator-activity` (Flask) → `app/templates/operator_activity/index.html`
  + `app/static/js/operator_activity.js` + `app/static/css/operator_activity.css`.
- Nav: added under the Admin sidebar in `app/templates/partials/sidebar.html`
  (`Operator activity`). Filter state is serialised to the URL query string (shareable,
  survives refresh/back). Drill-down opens as a slide-over with `#op=<id>` in the URL.

## Setup

```bash
pip install -r requirements.txt          # adds duckdb, python-calamine, fastapi-mail
alembic upgrade head                     # creates the 6 tables (a1b2c3d4e5f6)
# ...upload a RegistrarEA file via the UI, then optionally:
python seed_operator_activity.py         # fill demo profile data for the drill-down
```

## Tests

```bash
python -m pytest tests/test_registrar_ea_transform.py -q
```
Covers the registrar/EA filter, rename map, group-by sums, address factoring, rejected-row
quarantine, missing-column fail-fast, case/whitespace-insensitive headers, and bounded
memory on a 500k-row synthetic file.
