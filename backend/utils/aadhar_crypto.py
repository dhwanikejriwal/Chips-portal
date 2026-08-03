# backend/utils/aadhar_crypto.py
"""Aadhar protection helpers.

Aadhar is never stored in plain text. Every record keeps two derived forms:

* ``aadhar_hash``      - keyed HMAC-SHA256, deterministic. Used for matching,
                         the UNIQUE constraint and search.
* ``aadhar_encrypted`` - AES-256-GCM ciphertext, reversible. Used ONLY for
                         authenticated + authorized admin display.

Both keys live in the application layer (env vars / secrets manager / KMS) and
never in the database. The database only ever sees hashes and ciphertext.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import unicodedata

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AADHAR_HMAC_KEY_ENV = "AADHAR_HMAC_KEY"
AADHAR_ENC_KEY_ENV = "AADHAR_ENC_KEY"

_NONCE_LEN = 12  # AES-GCM standard nonce size


class AadharKeyError(RuntimeError):
    """Raised when a required Aadhar key is missing or malformed."""


class AadharValueError(ValueError):
    """Raised when the supplied Aadhar number is not a valid 12-digit value."""


# --------------------------------------------------------------------------- #
# Key loading
# --------------------------------------------------------------------------- #
def _load_key(env_name: str, expected_len: int | None = None) -> bytes:
    raw = os.getenv(env_name)
    if not raw:
        raise AadharKeyError(f"{env_name} is not set; Aadhar cannot be processed.")
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception:
        key = raw.encode("utf-8")
    if expected_len is not None and len(key) != expected_len:
        raise AadharKeyError(
            f"{env_name} must decode to {expected_len} bytes, got {len(key)}."
        )
    return key


def keys_configured() -> bool:
    """True when both keys are present and usable (checked at startup/upload)."""
    try:
        _load_key(AADHAR_HMAC_KEY_ENV)
        _load_key(AADHAR_ENC_KEY_ENV, expected_len=32)
        return True
    except AadharKeyError:
        return False


# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #
def normalize_aadhar(value: str | int | None) -> str:
    """Strip spaces/hyphens and validate a 12-digit Aadhar number."""
    if value is None:
        raise AadharValueError("Aadhar number is required.")
    text = str(value).strip()
    # Excel often hands back numeric cells as '223845978553.0'
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".")[0]
    digits = re.sub(r"\D", "", text)
    if len(digits) != 12:
        raise AadharValueError("Aadhar number must contain exactly 12 digits.")
    if digits[0] in "01":
        raise AadharValueError("Aadhar number cannot start with 0 or 1.")
    return digits


def normalize_status(value: str | None) -> str:
    """Upper-case and collapse whitespace in a status value.

    Part of the identity key, so 'Deboarded', 'DEBOARDED' and ' deboarded '
    must all resolve to one value - otherwise a casing difference in the sheet
    would create a spurious extra record.
    """
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).upper()


def normalize_name(value: str | None) -> str:
    """Trim, collapse internal whitespace and lower-case the name.

    Part of the record identity (name_normalized + aadhar_hash + registrar_code),
    so the same person written 'Raj  Kiran' and 'raj kiran' collapses to one row.
    """
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


# --------------------------------------------------------------------------- #
# Hashing (matching / search / uniqueness)
# --------------------------------------------------------------------------- #
def hash_aadhar(value: str | int) -> str:
    """Keyed HMAC-SHA256 of the normalized Aadhar, hex encoded (64 chars)."""
    key = _load_key(AADHAR_HMAC_KEY_ENV)
    normalized = normalize_aadhar(value)
    return hmac.new(key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_aadhar(value: str | int, stored_hash: str) -> bool:
    """Constant-time comparison of a candidate Aadhar against a stored hash."""
    try:
        return hmac.compare_digest(hash_aadhar(value), stored_hash or "")
    except AadharValueError:
        return False


# --------------------------------------------------------------------------- #
# Encryption (admin display only)
# --------------------------------------------------------------------------- #
def encrypt_aadhar(value: str | int) -> str:
    """AES-256-GCM encrypt the normalized Aadhar. Returns base64(nonce||ct)."""
    key = _load_key(AADHAR_ENC_KEY_ENV, expected_len=32)
    normalized = normalize_aadhar(value)
    nonce = os.urandom(_NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, normalized.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt_aadhar(token: str) -> str:
    """Reverse of :func:`encrypt_aadhar`.

    Server-side only, and only after the caller has been authenticated AND
    authorized as an admin. Never return the result to a non-admin.
    """
    if not token:
        raise AadharValueError("No encrypted Aadhar value to decrypt.")
    key = _load_key(AADHAR_ENC_KEY_ENV, expected_len=32)
    blob = base64.b64decode(token)
    nonce, ct = blob[:_NONCE_LEN], blob[_NONCE_LEN:]
    return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")


def mask_aadhar(value: str | int | None) -> str:
    """``XXXX-XXXX-1234`` - the default representation, even for admins."""
    try:
        normalized = normalize_aadhar(value)
    except AadharValueError:
        return ""
    return f"XXXX-XXXX-{normalized[-4:]}"


def mask_from_encrypted(token: str) -> str:
    """Masked form derived from ciphertext, so callers never touch plain text."""
    try:
        return mask_aadhar(decrypt_aadhar(token))
    except Exception:
        return "XXXX-XXXX-XXXX"


def protect_aadhar(value: str | int) -> tuple[str, str]:
    """Return ``(aadhar_hash, aadhar_encrypted)`` for one Aadhar number."""
    normalized = normalize_aadhar(value)
    return hash_aadhar(normalized), encrypt_aadhar(normalized)


def generate_keys() -> dict[str, str]:
    """Helper for provisioning: fresh base64 keys for the two env vars."""
    return {
        AADHAR_HMAC_KEY_ENV: base64.b64encode(os.urandom(32)).decode("ascii"),
        AADHAR_ENC_KEY_ENV: base64.b64encode(os.urandom(32)).decode("ascii"),
    }
