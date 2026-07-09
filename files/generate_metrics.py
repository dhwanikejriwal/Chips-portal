"""
generate_metrics.py
--------------------
Builds district_metrics.json — the per-district Aadhaar metrics consumed
by the dashboard. Ships with realistic-looking SAMPLE data (no real Aadhaar
numbers were available from the uploaded files, which only contained
boundary geometry).

>>> REPLACE THIS WITH YOUR REAL DATA <<<
Swap the body of build_sample_metrics() for a function that reads your
real source (CSV, Excel, database query, UIDAI API, etc.) and returns a
dict shaped exactly like this, keyed by the district's English name
(must match `dist_name` in cg_districts.geojson):

{
  "Raipur": {
    "population": 1334926,
    "saturation": 98.8,              # % of population enrolled
    "enrolled": 1318906,
    "child_saturation_5_17": 85.6,   # % of 5-17 age group enrolled
    "monthly_updates": 11111,        # demographic/biometric update requests
    "rejection_rate": 1.1,           # % of applications rejected
    "enrollment_centers": 39
  },
  ...
}

Usage:
    python3 generate_metrics.py cg_districts_simplified.geojson district_metrics.json
"""

import sys
import json
import random


def get_district_names(geojson_path: str):
    fc = json.load(open(geojson_path, encoding="utf-8"))
    return [f["properties"]["dist_name"] for f in fc["features"]]


def build_sample_metrics(names, seed=42):
    random.seed(seed)
    data = {}
    for n in names:
        pop = random.randint(450_000, 2_900_000)
        sat = round(random.uniform(88.5, 99.8), 1)
        enrolled = int(pop * sat / 100)
        child = round(random.uniform(72, 96), 1)
        updates = random.randint(800, 18_000)
        rejection = round(random.uniform(0.3, 4.2), 1)
        centers = random.randint(8, 65)
        data[n] = {
            "population": pop,
            "saturation": sat,
            "enrolled": enrolled,
            "child_saturation_5_17": child,
            "monthly_updates": updates,
            "rejection_rate": rejection,
            "enrollment_centers": centers,
        }
    return data


if __name__ == "__main__":
    geojson_path = sys.argv[1] if len(sys.argv) > 1 else "cg_districts_simplified.geojson"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "district_metrics.json"

    names = get_district_names(geojson_path)
    metrics = build_sample_metrics(names)

    json.dump(metrics, open(out_path, "w", encoding="utf-8"))
    print(f"Wrote {out_path} for {len(metrics)} districts")
