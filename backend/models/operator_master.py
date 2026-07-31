# backend/models/operator_master.py
"""Operator master rows managed from the Operator Data Management page.

Maps the EXISTING `operator_master` table - this model must stay in step with
the live schema; it does not define new columns.

Aadhar is never stored in plain text. It is persisted as a keyed HMAC
(`aadhar_hash`, used for matching/search/uniqueness) and as AES-256-GCM
ciphertext (`aadhar_encrypted`, decrypted server-side for authorized admins
only). Both keys live in the application layer - see
`backend/utils/aadhar_crypto.py`.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint, Index
from backend.models.base import Base, get_ist_now


class OperatorMaster(Base):
    __tablename__ = "operator_master"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # --- Name ---
    name = Column(String(150), nullable=False)
    # Trimmed, whitespace-collapsed, lower-cased; part of the identity key
    # (name_normalized + aadhar_hash + registrar_code + operator_code + status).
    name_normalized = Column(String(150), nullable=False, index=True)

    # --- Aadhar (never plain text) ---
    # Keyed HMAC-SHA256 hex digest - matching, search and uniqueness.
    aadhar_hash = Column(String(64), nullable=False, index=True)
    # AES-256-GCM, base64(nonce||ciphertext) - admin display only. No unique
    # constraint: the ciphertext differs on every encryption.
    aadhar_encrypted = Column(Text, nullable=False)
    # Last four digits in the clear - the lookup key for the "name + last 4"
    # search mode, which cannot use aadhar_hash (a hash of four digits has no
    # relationship to the hash of the full number). Not part of the identity.
    aadhar_last4 = Column(String(4), nullable=True)

    # --- Source ---
    registrar_code = Column(String(50), nullable=False, index=True)
    # Part of the identity key, so NOT NULL: Postgres treats NULLs as distinct
    # inside a UNIQUE constraint and a missing value would defeat deduplication.
    operator_code = Column(String(100), nullable=False, index=True)
    # Also part of the identity key: an operator who is deboarded and later
    # onboarded keeps both rows, so the table records the history of each state
    # rather than overwriting it. Stored upper-cased (see normalize_status).
    status = Column(String(30), nullable=False, index=True)
    # Owning agency/source - operators are not only CHIPS.
    agency = Column(String(100), nullable=True, index=True)

    created_at = Column(DateTime, nullable=False, default=get_ist_now)
    updated_at = Column(DateTime, nullable=False, default=get_ist_now, onupdate=get_ist_now)

    __table_args__ = (
        UniqueConstraint(
            "name_normalized", "aadhar_hash", "registrar_code", "operator_code", "status",
            name="uq_operator_master_identity",
        ),
        Index("ix_operator_master_registrar_agency", "registrar_code", "agency"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<OperatorMaster id={self.id} name={self.name!r} "
            f"registrar_code={self.registrar_code!r} agency={self.agency!r}>"
        )
