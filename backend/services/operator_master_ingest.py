# backend/services/operator_master_ingest.py
"""Ingest an operator CSV/Excel upload into the existing `operator_master` table.

Uploads are additive: every file APPENDS to the data already present. A row
whose (name_normalized, aadhar_hash, registrar_code, operator_code, status) identity
already exists is skipped and the stored record is left untouched - the insert relies on the
database's UNIQUE constraint via ON CONFLICT DO NOTHING (Postgres) /
INSERT IGNORE (MySQL), so concurrent uploads cannot race past it.

The plain Aadhar exists only inside :func:`_build_row` - it is hashed and
encrypted there and never persisted, logged or returned.
"""
from __future__ import annotations

import io
import os
import re
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.models.operator_master import OperatorMaster
from backend.utils.aadhar_crypto import (
    AadharKeyError, AadharValueError, decrypt_aadhar, hash_aadhar,
    normalize_aadhar, normalize_name, normalize_status, protect_aadhar,
)

ALLOWED_EXT = {".csv", ".xlsx", ".xls"}
MAX_ROWS = 100_000
_CHUNK = 1000

# Accepted spellings for each field, matched case/space/underscore-insensitively.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "operatorname", "candidatename", "fullname"),
    "aadhar": ("aadhar", "aadhaar", "aadharnumber", "aadhaarnumber",
               "aadharno", "aadhaarno", "uid"),
    "registrar_code": ("registrarcode", "registrar", "registrarcd"),
    "operator_code": ("operatorcode", "operatorid", "opcode", "operatorcd"),
    "status": ("status", "operatorstatus", "currentstatus"),
    "agency": ("agency", "source", "agencyname", "organisation", "organization"),
}
REQUIRED_FIELDS = ("name", "aadhar", "registrar_code", "operator_code", "status")
IDENTITY_FIELDS = ("name_normalized", "aadhar_hash", "registrar_code",
                   "operator_code", "status")


class UploadError(Exception):
    """Fatal problem with the file itself (bad type, unreadable, missing columns)."""


def _key(col: Any) -> str:
    return "".join(ch for ch in str(col).lower() if ch.isalnum())


def _resolve_columns(columns: Iterable[Any]) -> dict[str, Any]:
    """Map our field names onto the actual header labels present in the file."""
    lookup = {_key(c): c for c in columns}
    resolved: dict[str, Any] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lookup:
                resolved[field] = lookup[alias]
                break
    missing = [f for f in REQUIRED_FIELDS if f not in resolved]
    if missing:
        pretty = {"name": "Name", "aadhar": "Aadhar number",
                  "registrar_code": "Registrar code", "operator_code": "Operator code",
                  "status": "Status"}
        raise UploadError(
            "Missing required column(s): "
            + ", ".join(pretty[m] for m in missing)
            + ". Expected headers: Name, Aadhar number, Registrar code, "
              "Operator code, Status (Agency optional)."
        )
    return resolved


def _read_frame(content: bytes, filename: str) -> pd.DataFrame:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise UploadError("Unsupported file type. Upload a .csv, .xlsx or .xls file.")
    try:
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)
        else:
            df = pd.read_excel(io.BytesIO(content), dtype=str, keep_default_na=False)
    except Exception as exc:
        raise UploadError(f"Could not read the file: {exc}")
    if df.empty:
        raise UploadError("The file contains no data rows.")
    if len(df) > MAX_ROWS:
        raise UploadError(f"File has {len(df):,} rows; the limit is {MAX_ROWS:,}.")
    return df


def _cell(row: Any, col: Any) -> str:
    if col is None:
        return ""
    value = row.get(col, "")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _build_row(row: Any, cols: dict[str, Any], default_agency: str) -> dict[str, Any]:
    """Validate one sheet row and return its persistable (protected) form.

    Raises AadharValueError/ValueError with a human-readable reason; the caller
    records that reason against the row instead of aborting the upload.
    """
    name = _cell(row, cols["name"])
    if not name:
        raise ValueError("Name is empty.")

    name_normalized = normalize_name(name)
    if not name_normalized:
        raise ValueError("Name has no usable characters.")

    # normalize_aadhar raises AadharValueError for anything that is not a
    # 12-digit Aadhar. The plain value lives only in this scope.
    aadhar = normalize_aadhar(_cell(row, cols["aadhar"]))
    aadhar_hash, aadhar_encrypted = protect_aadhar(aadhar)
    aadhar_last4 = aadhar[-4:]

    registrar_code = _cell(row, cols["registrar_code"])
    if not registrar_code:
        raise ValueError("Registrar code is empty.")

    # Part of the identity key, so a blank value cannot be tolerated - it would
    # make the row undedupable rather than merely incomplete.
    operator_code = _cell(row, cols["operator_code"])
    if not operator_code:
        raise ValueError("Operator code is empty.")

    # Upper-cased so a casing difference in the sheet cannot fork the identity.
    status = normalize_status(_cell(row, cols["status"]))
    if not status:
        raise ValueError("Status is empty.")

    agency = _cell(row, cols.get("agency")) or default_agency
    return {
        "name": name[:150],
        "name_normalized": name_normalized[:150],
        "aadhar_hash": aadhar_hash,
        "aadhar_encrypted": aadhar_encrypted,
        "aadhar_last4": aadhar_last4,
        "registrar_code": registrar_code[:50],
        "operator_code": operator_code[:100],
        "status": status[:30],
        "agency": (agency or None) and agency[:100],
    }


def _insert_ignore(db: Session, rows: list[dict[str, Any]]) -> int:
    """Insert rows, skipping the ones that violate the identity UNIQUE key.

    Returns the number of rows actually inserted.
    """
    if not rows:
        return 0
    dialect = db.bind.dialect.name if db.bind is not None else "postgresql"
    table = OperatorMaster.__table__

    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(table).values(rows).on_conflict_do_nothing(
            index_elements=list(IDENTITY_FIELDS)
        )
    elif dialect in ("mysql", "mariadb"):
        from sqlalchemy.dialects.mysql import insert as my_insert
        base = my_insert(table).values(rows)
        # MySQL's equivalent of INSERT IGNORE without silencing other errors.
        stmt = base.on_duplicate_key_update(id=table.c.id)
    else:  # sqlite and friends
        from sqlalchemy.dialects.sqlite import insert as lite_insert
        stmt = lite_insert(table).values(rows).on_conflict_do_nothing(
            index_elements=list(IDENTITY_FIELDS)
        )

    result = db.execute(stmt)
    return int(result.rowcount or 0)


def process_upload(
    db: Session, content: bytes, filename: str, default_agency: str = "",
) -> dict[str, Any]:
    """Validate, protect and append one uploaded file.

    Returns a summary: inserted / duplicates / invalid counts plus the invalid
    row detail (row number + reason) for display and CSV download.
    """
    df = _read_frame(content, filename)
    cols = _resolve_columns(df.columns)

    prepared: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    # Duplicates inside the same file: the DB would reject them anyway, but
    # collapsing here keeps the "duplicates skipped" count honest.
    seen: set[tuple[str, ...]] = set()
    in_file_dupes = 0

    for offset, (_, row) in enumerate(df.iterrows()):
        excel_row = offset + 2  # +1 for the header, +1 for 1-based numbering
        try:
            record = _build_row(row, cols, default_agency)
        except AadharKeyError:
            raise  # key misconfiguration is fatal, not a per-row problem
        except (AadharValueError, ValueError) as exc:
            invalid.append({
                "row": excel_row,
                "name": _cell(row, cols["name"])[:150],
                "registrar_code": _cell(row, cols["registrar_code"])[:50],
                "operator_code": _cell(row, cols["operator_code"])[:100],
                "status": _cell(row, cols["status"])[:30],
                "reason": str(exc),
            })
            continue

        identity = tuple(record[f] for f in IDENTITY_FIELDS)
        if identity in seen:
            in_file_dupes += 1
            continue
        seen.add(identity)
        prepared.append(record)

    inserted = 0
    try:
        for i in range(0, len(prepared), _CHUNK):
            inserted += _insert_ignore(db, prepared[i:i + _CHUNK])
        db.commit()
    except Exception:
        db.rollback()
        raise

    duplicates = (len(prepared) - inserted) + in_file_dupes
    return {
        "filename": filename,
        "total_rows": int(len(df)),
        "inserted": inserted,
        "duplicates": duplicates,
        "invalid": len(invalid),
        "invalid_rows": invalid[:500],
        "invalid_truncated": len(invalid) > 500,
    }


def search_by_aadhar(db: Session, aadhar: str) -> list[OperatorMaster]:
    """Look up records by hashed Aadhar. The plain value is never queried."""
    normalize_aadhar(aadhar)  # raises AadharValueError on a malformed input
    digest = hash_aadhar(aadhar)
    return (
        db.query(OperatorMaster)
        .filter(OperatorMaster.aadhar_hash == digest)
        .order_by(OperatorMaster.created_at.desc())
        .all()
    )


NAME_SEARCH_LIMIT = 200


def search_by_name_last4(
    db: Session, name: str, last4: str, code: str = "",
) -> list[OperatorMaster]:
    """Find candidates by partial name + last four Aadhar digits.

    The name is matched as a substring of the stored `name_normalized`, so
    "vivek" finds "Vivek Kumar Sahu". The last 4 digits still match exactly,
    which is what keeps the result set small.

    This is deliberately a "find candidates" lookup: name + last 4 is not
    unique, so callers must handle several matches. An optional registrar or
    operator code narrows the result when supplied.
    """
    normalized = normalize_name(name)
    if not normalized:
        raise ValueError("Enter the operator's name.")
    digits = re.sub(r"\D", "", str(last4 or ""))
    if len(digits) != 4:
        raise ValueError("Enter exactly the last 4 digits of the Aadhar number.")

    # Escape LIKE wildcards so a literal % or _ typed by the user cannot widen
    # the match to everything.
    pattern = "%" + normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    q = db.query(OperatorMaster).filter(
        OperatorMaster.name_normalized.like(pattern, escape="\\"),
        OperatorMaster.aadhar_last4 == digits,
    )
    code = (code or "").strip()
    if code:
        q = q.filter(or_(OperatorMaster.registrar_code == code,
                         OperatorMaster.operator_code == code))
    # Ordered by name so the several matches of a partial search read sensibly.
    return (q.order_by(OperatorMaster.name_normalized.asc(),
                       OperatorMaster.created_at.desc())
             .limit(NAME_SEARCH_LIMIT).all())


def backfill_last4(db: Session, chunk: int = 500) -> int:
    """Fill aadhar_last4 on rows written before the column existed.

    Decrypts aadhar_encrypted server-side; the plain value never leaves this
    function. Returns the number of rows updated.
    """
    updated = 0
    while True:
        rows = (db.query(OperatorMaster)
                .filter(OperatorMaster.aadhar_last4.is_(None))
                .limit(chunk).all())
        if not rows:
            break
        for rec in rows:
            rec.aadhar_last4 = decrypt_aadhar(rec.aadhar_encrypted)[-4:]
            updated += 1
        db.commit()
    return updated
