from app.utils.validators import (
    is_allowed_file,
    mask_aadhaar,
    validate_indian_phone,
    validate_international_phone,
)


def test_phone_validators() -> None:
    ok_in, fmt_in = validate_indian_phone("98480 12345")
    assert ok_in is True
    assert fmt_in == "+919848012345"

    bad_in, _ = validate_indian_phone("12345")
    assert bad_in is False

    ok_us, fmt_us = validate_international_phone("+1 (415) 555-0199")
    assert ok_us is True
    assert fmt_us == "+14155550199"


def test_aadhaar_masking() -> None:
    assert mask_aadhaar("4512 8890 1234") == "XXXX-XXXX-1234"
    assert mask_aadhaar("12345") == "INVALID-ID"


def test_allowed_file_extensions() -> None:
    assert is_allowed_file("apollo_prescription.pdf") is True
    assert is_allowed_file("pharmacy_bill.JPG") is True
    assert is_allowed_file("malware.exe") is False
