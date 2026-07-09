# Aadhaar Chhattisgarh District Dashboard — Full Package

## What's in here

| File | What it is |
|---|---|
| **dashboard.html** | ✅ The dashboard, ready to open. Single self-contained file (D3 loaded from CDN, all data + JS inlined). Just double-click / open in a browser. |
| dashboard_standalone.html | Same dashboard, but split into 3 files (html / js / data) for readability — needs `dashboard.js` and `dashboard_data.js` next to it on disk. |
| dashboard.js | Map rendering + interactivity logic (D3). |
| dashboard_data.js | Embeds `CG_GEOJSON` (district boundaries) and `DISTRICT_METRICS` (per-district stats) as JS globals. |
| cg_districts_simplified.geojson | District boundaries, simplified for web (~400 KB, 33 districts). Use this for the map. |
| cg_districts.geojson | Same boundaries at full original precision (~19 MB) — keep for GIS/analysis work, too heavy for the browser. |
| district_metrics.json | The per-district Aadhaar numbers (currently **sample/placeholder data** — see below). |
| extract_boundaries.py | Script that produced the GeoJSON from your original `toc.dat` + `630.dat` (a PostgreSQL dump of `master_layers.cg_district_boundary`). Re-run if you get an updated boundary dump. |
| generate_metrics.py | Script that produced `district_metrics.json`. Replace its data source with your real Aadhaar feed. |
| build_combined.py | Rebuilds `dashboard.html` (single-file) from the 3-file version, after you edit `dashboard.js` / `dashboard_data.js`. |

## Quick start

Just open **dashboard.html** in any browser. That's it — everything is bundled in.

## Where your original data went

Your uploads (`toc.dat`, `630.dat`) were a PostgreSQL **directory-format dump**, not flat files — `toc.dat` is the table-of-contents and `630.dat` was the compressed data for one table: `master_layers.cg_district_boundary`. I used `pg_restore` to pull out the COPY data without needing a live database, then decoded the geometry column (WKB hex) with `shapely` into GeoJSON. Result: all **33 official districts** of Chhattisgarh, in English + Hindi names, with division/state/district codes.

## Plugging in real Aadhaar numbers

`district_metrics.json` is currently **synthetic** — your uploads only had boundary shapes, no enrollment data. To use real numbers:

1. Get your data into a dict keyed by district name (must exactly match the `dist_name` values in the geojson — see the list inside `generate_metrics.py`'s docstring or just open `cg_districts_simplified.geojson`).
2. Each district needs these 7 fields (rename/add more if you adapt `dashboard.js` to match):
   ```json
   {
     "population": 1334926,
     "saturation": 98.8,
     "enrolled": 1318906,
     "child_saturation_5_17": 85.6,
     "monthly_updates": 11111,
     "rejection_rate": 1.1,
     "enrollment_centers": 39
   }
   ```
3. Save that as the new `district_metrics.json`.
4. Update `dashboard_data.js`'s `DISTRICT_METRICS = {...}` block with the new JSON (or re-run `build_combined.py` after editing the 3-file version).

## Editing the dashboard

Work in the 3-file version (`dashboard_standalone.html` + `dashboard.js` + `dashboard_data.js`) since it's much easier to read/diff than the inlined single file. When you're done, run:

```bash
python3 build_combined.py
```

to regenerate the single-file `dashboard_combined.html` (rename to `dashboard.html` to replace the shareable version).

## Re-extracting boundaries (if you get an updated GIS dump)

```bash
sudo apt-get install postgresql-client
pip install shapely pgdumplib
mkdir dump && cp toc.dat 630.dat dump/
pg_restore --list -Fd dump   # find the dump-id pg_restore expects, e.g. "6360"
cp dump/630.dat dump/6360.dat
python3 extract_boundaries.py dump cg_districts.geojson
```

## Stack used

- **D3.js v7** (geo projection + path rendering + DOM binding) — loaded from cdnjs, no build step
- Vanilla JS/HTML/CSS — no React/bundler, runs anywhere
- `d3.geoMercator().fitExtent(...)` crops the projection exactly to Chhattisgarh's bounding box, so no neighboring states ever appear on screen
