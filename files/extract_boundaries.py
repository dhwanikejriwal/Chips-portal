"""
extract_boundaries.py
----------------------
Converts the PostgreSQL custom/directory-format dump (toc.dat + numbered
data file, e.g. 630.dat) containing the `master_layers.cg_district_boundary`
table into a clean GeoJSON file usable directly in a web map.

Requirements:
    - postgresql-client (provides `pg_restore`)
        sudo apt-get install postgresql-client
    - pip install shapely pgdumplib

Usage:
    1. Put toc.dat and the numbered data file (e.g. 630.dat) in a folder,
       e.g. ./dump/
    2. Find the dump-id pg_restore expects for the data file:
         pg_restore --list -Fd ./dump
       Look for a line like:
         6360; 0 21928 TABLE DATA master_layers cg_district_boundary postgres
       The number before the semicolon (6360) is the dump id pg_restore
       expects the data file to be named after (6360.dat), even if your
       exported file was named something else (630.dat). Rename/copy it:
         cp dump/630.dat dump/6360.dat
    3. Run this script:
         python3 extract_boundaries.py ./dump cg_districts.geojson
"""

import sys
import json
import subprocess
from pathlib import Path
from shapely import wkb
from shapely.geometry import mapping


def restore_data_only(dump_dir: Path, table: str = "cg_district_boundary") -> str:
    """Run pg_restore to get the raw COPY data as SQL text (no live DB needed)."""
    out_file = dump_dir / "_data_only.sql"
    subprocess.run(
        [
            "pg_restore", "-Fd", str(dump_dir),
            "-t", table, "--data-only",
            "-f", str(out_file),
        ],
        check=True,
    )
    return out_file.read_text(encoding="utf-8")


def parse_copy_block(sql_text: str):
    """Extract the tab-separated rows between 'FROM stdin;' and '\\.'"""
    start = sql_text.index("FROM stdin;") + len("FROM stdin;\n")
    end = sql_text.index("\\.", start)
    body = sql_text[start:end]
    return [line for line in body.split("\n") if line.strip()]


def rows_to_geojson(rows):
    features = []
    for line in rows:
        gid, dist_h, dist_e, div_cod, sta_cod, dist_cod, geom_hex = line.split("\t")
        geom = wkb.loads(bytes.fromhex(geom_hex))
        features.append({
            "type": "Feature",
            "properties": {
                "gid": int(gid),
                "dist_name": dist_e,
                "dist_name_hi": dist_h,
                "div_code": div_cod,
                "state_code": sta_cod,
                "dist_code": dist_cod,
            },
            "geometry": mapping(geom),
        })
    return {"type": "FeatureCollection", "features": features}


def simplify(geojson, tolerance=0.002):
    """Lighten polygon precision for fast web rendering (degrees, ~0.002 ~ 200m)."""
    from shapely.geometry import shape
    out = {"type": "FeatureCollection", "features": []}
    for f in geojson["features"]:
        geom = shape(f["geometry"]).simplify(tolerance, preserve_topology=True)
        out["features"].append({
            "type": "Feature",
            "properties": f["properties"],
            "geometry": mapping(geom),
        })
    return out


if __name__ == "__main__":
    dump_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "./dump")
    out_path = Path(sys.argv[2] if len(sys.argv) > 2 else "cg_districts.geojson")

    sql_text = restore_data_only(dump_dir)
    rows = parse_copy_block(sql_text)
    print(f"Extracted {len(rows)} district rows")

    fc = rows_to_geojson(rows)
    fc_simplified = simplify(fc)

    out_path.write_text(json.dumps(fc_simplified, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size/1024:.1f} KB)")
