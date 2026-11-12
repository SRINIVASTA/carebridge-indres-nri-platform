from pathlib import Path
import pytest

from app.services.database import DatabaseService
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


def test_system_admin_seeded_and_employee_lifecycle(tmp_path: Path) -> None:
    """Verify SYSTEM_ADMIN seed, employee creation, KYC verification, deletion & audit logs."""
    test_db = DatabaseService(db_path=tmp_path / "test_rbac.db")

    # 1. Verify default SYSTEM_ADMIN is seeded and can authenticate
    sysadmin = test_db.authenticate_user("sysadmin@carebridge.in", "SysAdmin@123")
    assert sysadmin is not None
    assert sysadmin["role"] == "SYSTEM_ADMIN"
    assert sysadmin["kyc_verified"] is True

    # 2. Create a CARE_MANAGER employee (starts unverified until KYC)
    emp = test_db.register_user(
        email="suresh.test@carebridge.in",
        password="Sahayak@123",
        full_name="Suresh Naidu",
        role="CARE_MANAGER",
        phone="+919848011223",
        country="India",
        preferred_currency="INR",
    )
    assert emp["role"] == "CARE_MANAGER"
    assert emp["kyc_verified"] is False
    test_db.log_staff_action(
        "CREATED_EMPLOYEE",
        emp,
        performed_by=sysadmin["email"],
        details="Initial hire",
    )

    # 3. Verify Staff KYC & Police Clearance
    test_db.verify_staff_kyc(emp["id"], "AP-POL-VSP-99102", verified=True)
    updated_cm = test_db.authenticate_user("suresh.test@carebridge.in", "Sahayak@123")
    assert updated_cm is not None
    assert updated_cm["kyc_verified"] is True
    assert updated_cm["police_clearance_id"] == "AP-POL-VSP-99102"

    # 4. Verify SYSTEM_ADMIN cannot be deleted, while regular employees can
    with pytest.raises(ValueError, match="cannot be deleted"):
        test_db.delete_employee_user(sysadmin["id"], performed_by=sysadmin["email"])

    removed = test_db.delete_employee_user(emp["id"], performed_by=sysadmin["email"])
    assert removed["email"] == "suresh.test@carebridge.in"
    assert test_db.authenticate_user("suresh.test@carebridge.in", "Sahayak@123") is None

    # 5. Verify audit history recorded both creation and deletion
    logs = test_db.list_staff_audit_logs()
    actions = [entry["action"] for entry in logs]
    assert "CREATED_EMPLOYEE" in actions
    assert "DELETED_EMPLOYEE" in actions
