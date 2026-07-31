# backend/services/registrar_ea_transform.py
"""Pure, DB-free transform of a RegistrarEA upload using DuckDB.

Reimplements the reference pandas transform memory-optimally:
  1. filter to our registrar_code + ea_code (coercing both sides to numbers),
  2. keep + rename the needed measures to business names,
  3. aggregate (SUM) per operator / station / date,
  4. factor machine_address into a stations dimension keyed on
     (station_ea_code, station_number) so the long free-text address never
     sits in the fact-table group key.

DuckDB reads the file directly and does the filter+group-by in SQL in bounded
memory; only the small aggregated result is returned. Nothing is written to
Postgres here — that is the loader's job.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import duckdb

from backend.services.activity_config import DEFAULT_EA_CODE, DEFAULT_REGISTRAR_CODE

# Columns required for the transform to run at all (fail fast if any missing).
REQUIRED_COLUMNS = [
    "Date", "station_registrar_code", "station_ea_code", "session_operator_id",
    "station_number", "machine_district",
    "Count_U_plus_N_plus_Z", "Count_N", "Count_Z", "Count_U",
    "DEMO_UPDATE", "BIO_UPDATE", "NON_MBU", "IS_MBU",
    "COUNT_6AM_TO_10PM", "COUNT_10PM_TO_6AM",
]
# Station-dimension attributes: used when present, tolerated when absent.
OPTIONAL_STATION_COLUMNS = [
    "machine_address", "machine_state", "machine_pincode", "machine_lat", "machine_long",
]

# input measure column -> business name
MEASURE_RENAME = {
    "Count_N": "New_Aadhaar_Enrolment",
    "Count_Z": "New_Aadhar_18_plus",
    "Count_U": "Total_Updates",
    "DEMO_UPDATE": "Total_Demographic_Updates",
    "BIO_UPDATE": "Total_Biometric_Updates",
    "NON_MBU": "NON_MBU",
    "IS_MBU": "IS_MBU",
    "COUNT_6AM_TO_10PM": "COUNT_6AM_TO_10PM",
    "COUNT_10PM_TO_6AM": "COUNT_10PM_TO_6AM",
    "Count_U_plus_N_plus_Z": "Total_Enrollment_and_Updates",
}


class MissingColumnsError(ValueError):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("Missing required column(s): " + ", ".join(missing))


@dataclass
class TransformResult:
    fact_rows: list[dict[str, Any]] = field(default_factory=list)
    station_rows: list[dict[str, Any]] = field(default_factory=list)
    rows_read: int = 0
    rows_after_filter: int = 0
    rejected_rows: list[dict[str, Any]] = field(default_factory=list)
    multi_address_stations: list[dict[str, Any]] = field(default_factory=list)
    biometric_mismatch_count: int = 0
    date_min: Any = None
    date_max: Any = None
    distinct_operators: int = 0


def _normalize(name: str) -> str:
    return "".join(str(name).split()).lower()


def _resolve_columns(actual_cols: list[str]) -> dict[str, str]:
    """Map canonical name -> actual header, case/whitespace-insensitive."""
    lookup = {_normalize(c): c for c in actual_cols}
    resolved: dict[str, str] = {}
    for canon in REQUIRED_COLUMNS + OPTIONAL_STATION_COLUMNS:
        actual = lookup.get(_normalize(canon))
        if actual is not None:
            resolved[canon] = actual
    return resolved


def _build_relation(con: duckdb.DuckDBPyConnection, path: str):
    """Register the uploaded file as an all-varchar DuckDB relation named `src`.

    all_varchar keeps our casting explicit (registrar/EA may arrive as int,
    float or string) rather than trusting the reader's type sniffing.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        # Streamed by DuckDB; never fully materialised in Python. DuckDB can't
        # bind a parameter inside read_csv in a CREATE VIEW, so inline the path
        # with single-quotes escaped.
        safe_path = path.replace("'", "''")
        con.execute(
            f"CREATE TEMP VIEW src AS "
            f"SELECT * FROM read_csv('{safe_path}', all_varchar=true, ignore_errors=true, header=true)"
        )
        return [d[0] for d in con.execute("SELECT * FROM src LIMIT 0").description]
    # .xlsx / .xls -> read with the fast, low-memory calamine engine.
    import pandas as pd
    df = pd.read_excel(path, engine="calamine", dtype=str)
    con.register("src_df", df)
    con.execute("CREATE TEMP VIEW src AS SELECT * FROM src_df")
    return list(df.columns)


def transform_file(
    path: str,
    registrar_code: int = DEFAULT_REGISTRAR_CODE,
    ea_code: int = DEFAULT_EA_CODE,
    temp_dir: str | None = None,
) -> TransformResult:
    con = duckdb.connect(database=":memory:")
    try:
        if temp_dir:
            con.execute(f"SET temp_directory = '{temp_dir}'")
        actual_cols = _build_relation(con, path)

        resolved = _resolve_columns(actual_cols)
        missing = [c for c in REQUIRED_COLUMNS if c not in resolved]
        if missing:
            raise MissingColumnsError(missing)

        def col(canon: str) -> str:
            return '"' + resolved[canon].replace('"', '""') + '"'

        rows_read = con.execute("SELECT COUNT(*) FROM src").fetchone()[0]

        # Coerce both sides of the registrar/EA filter to numbers.
        where = (
            f"TRY_CAST({col('station_registrar_code')} AS BIGINT) = {int(registrar_code)} "
            f"AND TRY_CAST({col('station_ea_code')} AS BIGINT) = {int(ea_code)}"
        )

        # Build a typed, filtered base relation once.
        measure_selects = ",\n".join(
            f"COALESCE(TRY_CAST({col(src)} AS INTEGER), 0) AS \"{dst}\""
            for src, dst in MEASURE_RENAME.items()
        )
        station_extra = ",\n".join(
            f"{col(c)} AS {c}" if c in resolved else f"NULL AS {c}"
            for c in OPTIONAL_STATION_COLUMNS
        )
        con.execute(f"""
            CREATE TEMP VIEW base AS
            SELECT
                TRY_CAST({col('Date')} AS DATE) AS activity_date,
                TRY_CAST({col('station_ea_code')} AS INTEGER) AS station_ea_code,
                {col('session_operator_id')} AS session_operator_id,
                TRY_CAST({col('station_number')} AS INTEGER) AS station_number,
                {col('machine_district')} AS machine_district,
                {station_extra},
                {measure_selects}
            FROM src
            WHERE {where}
        """)

        rows_after_filter = con.execute("SELECT COUNT(*) FROM base").fetchone()[0]

        # Quarantine: unparseable date, null station identity, or negative count.
        measure_cols = list(MEASURE_RENAME.values())
        neg_clause = " OR ".join(f'"{m}" < 0' for m in measure_cols)
        rejected = con.execute(f"""
            SELECT * FROM base
            WHERE activity_date IS NULL
               OR station_ea_code IS NULL
               OR station_number IS NULL
               OR {neg_clause}
        """).to_arrow_table().to_pylist()

        # Valid rows only for aggregation.
        con.execute(f"""
            CREATE TEMP VIEW valid AS
            SELECT * FROM base
            WHERE activity_date IS NOT NULL
              AND station_ea_code IS NOT NULL
              AND station_number IS NOT NULL
              AND NOT ({neg_clause})
        """)

        # --- Fact aggregation: SUM measures per operator/station/date ---
        sum_selects = ",\n".join(f'SUM("{m}") AS "{m}"' for m in measure_cols)
        fact_rows = con.execute(f"""
            SELECT activity_date, station_ea_code, session_operator_id,
                   station_number, any_value(machine_district) AS machine_district,
                   {sum_selects}
            FROM valid
            GROUP BY activity_date, station_ea_code, session_operator_id, station_number
        """).to_arrow_table().to_pylist()

        # --- Stations dimension (address factored out of the group key) ---
        station_rows = con.execute("""
            SELECT station_ea_code, station_number,
                   any_value(machine_address) AS machine_address,
                   any_value(machine_district) AS machine_district,
                   any_value(machine_state) AS machine_state,
                   any_value(machine_pincode) AS machine_pincode,
                   any_value(machine_lat) AS machine_lat,
                   any_value(machine_long) AS machine_long
            FROM valid
            GROUP BY station_ea_code, station_number
        """).to_arrow_table().to_pylist()

        # Flag stations whose station_number maps to >1 distinct address.
        multi = con.execute("""
            SELECT station_ea_code, station_number,
                   COUNT(DISTINCT machine_address) AS address_count
            FROM valid
            WHERE machine_address IS NOT NULL
            GROUP BY station_ea_code, station_number
            HAVING COUNT(DISTINCT machine_address) > 1
        """).to_arrow_table().to_pylist()

        # Data-quality warn: Total_Biometric_Updates == NON_MBU + IS_MBU
        bio_mismatch = con.execute("""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM valid
                GROUP BY activity_date, station_ea_code, session_operator_id, station_number
                HAVING SUM("Total_Biometric_Updates") <> SUM("NON_MBU") + SUM("IS_MBU")
            )
        """).fetchone()[0]

        stats = con.execute("""
            SELECT MIN(activity_date), MAX(activity_date),
                   COUNT(DISTINCT session_operator_id)
            FROM valid
        """).fetchone()

        return TransformResult(
            fact_rows=fact_rows,
            station_rows=station_rows,
            rows_read=rows_read,
            rows_after_filter=rows_after_filter,
            rejected_rows=rejected,
            multi_address_stations=multi,
            biometric_mismatch_count=bio_mismatch,
            date_min=stats[0],
            date_max=stats[1],
            distinct_operators=stats[2] or 0,
        )
    finally:
        con.close()
