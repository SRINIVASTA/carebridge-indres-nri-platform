import re
from typing import Tuple

ALLOWED_DOC_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


def validate_indian_phone(phone: str) -> Tuple[bool, str]:
    """Validate Indian mobile number (+91 followed by 10 digits starting 6-9)."""
    cleaned = re.sub(r"[\s\-()]", "", phone)
    if re.match(r"^(\+91|91)?[6-9]\d{9}$", cleaned):
        digits = cleaned[-10:]
        return True, f"+91{digits}"
    return False, "Enter a valid 10-digit Indian mobile number (e.g., +919876543210)."


def validate_international_phone(phone: str) -> Tuple[bool, str]:
    """Validate E.164 international phone format for NRI WhatsApp/SMS alerts."""
    cleaned = re.sub(r"[\s\-()]", "", phone)
    if re.match(r"^\+[1-9]\d{7,14}$", cleaned):
        return True, cleaned
    return False, "Use international E.164 format starting with '+' (e.g., +14155550199)."


def mask_aadhaar(aadhaar_number: str) -> str:
    """Mask first 8 digits of a 12-digit Indian Aadhaar ID for KYC privacy."""
    digits = re.sub(r"\D", "", aadhaar_number)
    if len(digits) != 12:
        return "INVALID-ID"
    return f"XXXX-XXXX-{digits[-4:]}"


def is_allowed_file(filename: str) -> bool:
    """Check if uploaded receipt or medical report extension is permitted."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_DOC_EXTENSIONS
