import hashlib
import re


def normalize_phone(phone):
    """Strip non-digit characters, keep leading +."""
    if not phone:
        return ""
    phone = phone.strip()
    if phone.startswith("+"):
        return "+" + re.sub(r"[^\d]", "", phone[1:])
    return re.sub(r"[^\d]", "", phone)


def normalize_email(email):
    """Lowercase and strip whitespace."""
    if not email:
        return ""
    return email.strip().lower()


def hash_sha256(value):
    """SHA256 hash a string. Returns lowercase hex digest."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_phone(phone):
    """Normalize phone, strip leading +, then SHA256 hash.

    Meta requires phone as digits-only (no +) before hashing.
    """
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    digits_only = normalized.lstrip("+")
    if not digits_only:
        return None
    return hash_sha256(digits_only)


def hash_email(email):
    """Normalize email then SHA256 hash."""
    normalized = normalize_email(email)
    if not normalized:
        return None
    return hash_sha256(normalized)
