import hashlib
import json
import secrets
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.utils.datetime_helper import now_ist_str

DB_PATH = Path(__file__).resolve().parent.parent.parent / "carebridge.db"


class DatabaseService:
    """Zero-setup SQLite3 data layer with IST timestamps, auth & seed data."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _hash_password(password: str, salt: Optional[str] = None) -> str:
        salt = salt or secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
        ).hex()
        return f"{salt}${pwd_hash}"

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    customer_type TEXT DEFAULT 'NRI_SPONSOR',
                    phone TEXT NOT NULL,
                    whatsapp_number TEXT,
                    preferred_channels TEXT DEFAULT '["EMAIL", "WHATSAPP"]',
                    country TEXT DEFAULT 'USA',
                    preferred_currency TEXT DEFAULT 'USD',
                    kyc_verified INTEGER DEFAULT 0,
                    police_clearance_id TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS parents (
                    id TEXT PRIMARY KEY,
                    nri_user_id TEXT NOT NULL,
                    is_self_care INTEGER DEFAULT 0,
                    full_name TEXT NOT NULL,
                    age INTEGER NOT NULL,
                    city TEXT NOT NULL,
                    address TEXT NOT NULL,
                    mobility_level TEXT DEFAULT 'INDEPENDENT',
                    home_access_notes TEXT,
                    blood_group TEXT,
                    emergency_contact_india TEXT,
                    medical_conditions TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS wallets (
                    nri_user_id TEXT PRIMARY KEY,
                    plan_tier TEXT DEFAULT 'COUPLE',
                    balance_inr REAL DEFAULT 18500.00,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    nri_user_id TEXT NOT NULL,
                    parent_id TEXT NOT NULL,
                    parent_name TEXT,
                    care_manager_id TEXT,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    instructions TEXT,
                    scheduled_at TEXT NOT NULL,
                    requires_wheelchair_cab INTEGER DEFAULT 0,
                    requires_two_person_lift INTEGER DEFAULT 0,
                    third_party_vendor_type TEXT,
                    status TEXT DEFAULT 'ASSIGNED',
                    gps_lat REAL,
                    gps_lng REAL,
                    checkin_time TEXT,
                    service_fee_inr REAL DEFAULT 0.0,
                    out_of_pocket_inr REAL DEFAULT 0.0,
                    receipt_url TEXT,
                    receipt_verified INTEGER DEFAULT 0,
                    completion_notes TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS invoices (
                    invoice_number TEXT PRIMARY KEY,
                    nri_user_id TEXT NOT NULL,
                    task_id TEXT,
                    currency TEXT DEFAULT 'USD',
                    service_fee_inr REAL DEFAULT 0.0,
                    out_of_pocket_inr REAL DEFAULT 0.0,
                    gst_inr REAL DEFAULT 0.0,
                    total_inr REAL NOT NULL,
                    total_converted REAL NOT NULL,
                    pdf_storage_path TEXT,
                    status TEXT DEFAULT 'PAID',
                    dispatched_channels TEXT DEFAULT '[]',
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS vitals_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id TEXT NOT NULL,
                    logged_by TEXT,
                    systolic_bp INTEGER,
                    diastolic_bp INTEGER,
                    blood_sugar_mgdl INTEGER,
                    pulse_bpm INTEGER,
                    spo2_percent INTEGER,
                    notes TEXT,
                    recorded_at TEXT
                );

                CREATE TABLE IF NOT EXISTS staff_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    target_user_id TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    target_email TEXT NOT NULL,
                    target_role TEXT NOT NULL,
                    performed_by TEXT NOT NULL,
                    details TEXT,
                    timestamp_ist TEXT NOT NULL
                );
                """
            )

            table_migrations = {
                "users": {
                    "customer_type": "TEXT DEFAULT 'NRI_SPONSOR'",
                    "whatsapp_number": "TEXT",
                    "preferred_channels": "TEXT DEFAULT '[\"EMAIL\", \"WHATSAPP\"]'",
                    "country": "TEXT DEFAULT 'USA'",
                    "preferred_currency": "TEXT DEFAULT 'USD'",
                    "kyc_verified": "INTEGER DEFAULT 0",
                    "police_clearance_id": "TEXT",
                    "created_at": "TEXT",
                },
                "parents": {
                    "is_self_care": "INTEGER DEFAULT 0",
                    "mobility_level": "TEXT DEFAULT 'INDEPENDENT'",
                    "home_access_notes": "TEXT",
                    "blood_group": "TEXT",
                    "emergency_contact_india": "TEXT",
                    "medical_conditions": "TEXT",
                    "created_at": "TEXT",
                },
                "wallets": {
                    "plan_tier": "TEXT DEFAULT 'PAY_AS_YOU_GO'",
                    "balance_inr": "REAL DEFAULT 0.0",
                    "updated_at": "TEXT",
                },
                "tasks": {
                    "parent_name": "TEXT",
                    "care_manager_id": "TEXT",
                    "instructions": "TEXT",
                    "requires_wheelchair_cab": "INTEGER DEFAULT 0",
                    "requires_two_person_lift": "INTEGER DEFAULT 0",
                    "third_party_vendor_type": "TEXT",
                    "gps_lat": "REAL",
                    "gps_lng": "REAL",
                    "checkin_time": "TEXT",
                    "service_fee_inr": "REAL DEFAULT 0.0",
                    "out_of_pocket_inr": "REAL DEFAULT 0.0",
                    "receipt_url": "TEXT",
                    "receipt_verified": "INTEGER DEFAULT 0",
                    "completion_notes": "TEXT",
                    "created_at": "TEXT",
                },
                "invoices": {
                    "task_id": "TEXT",
                    "currency": "TEXT DEFAULT 'USD'",
                    "service_fee_inr": "REAL DEFAULT 0.0",
                    "out_of_pocket_inr": "REAL DEFAULT 0.0",
                    "gst_inr": "REAL DEFAULT 0.0",
                    "pdf_storage_path": "TEXT",
                    "status": "TEXT DEFAULT 'PAID'",
                    "dispatched_channels": "TEXT DEFAULT '[]'",
                    "created_at": "TEXT",
                },
                "vitals_logs": {
                    "logged_by": "TEXT",
                    "systolic_bp": "INTEGER",
                    "diastolic_bp": "INTEGER",
                    "blood_sugar_mgdl": "INTEGER",
                    "pulse_bpm": "INTEGER",
                    "spo2_percent": "INTEGER",
                    "notes": "TEXT",
                    "recorded_at": "TEXT",
                },
            }

            for table_name, cols in table_migrations.items():
                existing_cols = {
                    row["name"]
                    for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                }
                for col_name, col_def in cols.items():
                    if col_name not in existing_cols:
                        conn.execute(
                            f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"
                        )

            cur = conn.execute("SELECT COUNT(*) AS cnt FROM parents").fetchone()
            if cur["cnt"] == 0:
                seed_ts = now_ist_str()
                conn.execute(
                    """
                    INSERT INTO parents (
                        id, nri_user_id, is_self_care, full_name, age, city, address,
                        mobility_level, home_access_notes, blood_group,
                        emergency_contact_india, medical_conditions, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "par-01",
                        "usr-nri-101",
                        0,
                        "Dr. Raghavendra Sharma",
                        74,
                        "Visakhapatnam",
                        "Flat 402, Sea Breeze Enclave, MVP Colony, Visakhapatnam",
                        "WALKER_ASSISTED",
                        "4th floor with elevator; security gate pass required",
                        "O+",
                        "+919848099887",
                        "Type 2 Diabetes, Mild Hypertension",
                        seed_ts,
                    ),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO wallets VALUES (?, ?, ?, ?)",
                    ("usr-nri-101", "COUPLE", 18500.00, seed_ts),
                )

            admin_cur = conn.execute(
                "SELECT COUNT(*) AS cnt FROM users WHERE role = 'SYSTEM_ADMIN'"
            ).fetchone()
            if admin_cur["cnt"] == 0:
                seed_ts = now_ist_str()
                conn.execute(
                    """
                    INSERT OR IGNORE INTO users (
                        id, email, password_hash, full_name, role, customer_type, phone,
                        whatsapp_number, preferred_channels, country,
                        preferred_currency, kyc_verified, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "usr-sysadmin-01",
                        "sysadmin@carebridge.in",
                        self._hash_password("SysAdmin@123"),
                        "Master System Admin",
                        "SYSTEM_ADMIN",
                        "SYSTEM",
                        "+919848000001",
                        "+919848000001",
                        '["EMAIL", "WHATSAPP"]',
                        "India",
                        "INR",
                        1,
                        seed_ts,
                    ),
                )

    def register_user(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str,
        phone: str,
        country: str = "USA",
        preferred_currency: str = "USD",
        preferred_channels: Optional[List[str]] = None,
        customer_type: Optional[str] = None,
        self_care_details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new user account (Indian Resident, NRI Sponsor, or Staff) with IST timestamp."""
        clean_email = email.strip().lower()
        channels = preferred_channels or ["EMAIL", "WHATSAPP"]
        user_id = f"usr-{uuid.uuid4().hex[:8]}"
        hashed_pw = self._hash_password(password)
        created_ts = now_ist_str()

        resolved_customer_type = customer_type or (
            "INDIAN_RESIDENT" if country.strip().lower() == "india" else "NRI_SPONSOR"
        )
        if resolved_customer_type == "INDIAN_RESIDENT":
            country = "India"
            preferred_currency = "INR"

        is_customer = role in ("INDRES_NRI", "NRI")
        is_verified = is_customer or role in ("SYSTEM_ADMIN", "ADMIN")

        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE email = ?", (clean_email,)
            ).fetchone()
            if existing:
                raise ValueError("An account with this email already exists. Please sign in.")

            conn.execute(
                """
                INSERT INTO users (
                    id, email, password_hash, full_name, role, customer_type, phone,
                    whatsapp_number, preferred_channels, country, preferred_currency,
                    kyc_verified, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    clean_email,
                    hashed_pw,
                    full_name.strip(),
                    role,
                    resolved_customer_type if is_customer else "STAFF",
                    phone,
                    phone,
                    json.dumps(channels),
                    country,
                    preferred_currency,
                    1 if is_verified else 0,
                    created_ts,
                ),
            )
            if is_customer:
                conn.execute(
                    "INSERT OR IGNORE INTO wallets (nri_user_id, plan_tier, balance_inr, updated_at) VALUES (?, ?, ?, ?)",
                    (user_id, "PAY_AS_YOU_GO", 0.0, created_ts),
                )

            if is_customer and resolved_customer_type == "INDIAN_RESIDENT" and self_care_details:
                self_id = f"par-{uuid.uuid4().hex[:6]}"
                conn.execute(
                    """
                    INSERT INTO parents (
                        id, nri_user_id, is_self_care, full_name, age, city, address,
                        mobility_level, home_access_notes, blood_group,
                        emergency_contact_india, medical_conditions, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self_id,
                        user_id,
                        1,
                        full_name.strip(),
                        int(self_care_details.get("age", 60)),
                        self_care_details.get("city", "Hyderabad"),
                        self_care_details.get("address", ""),
                        self_care_details.get("mobility_level", "WHEELCHAIR_REQUIRED"),
                        self_care_details.get("home_access_notes", ""),
                        self_care_details.get("blood_group", ""),
                        self_care_details.get("emergency_contact_india", phone),
                        self_care_details.get("medical_conditions", ""),
                        created_ts,
                    ),
                )

        return {
            "id": user_id,
            "email": clean_email,
            "full_name": full_name.strip(),
            "role": role,
            "customer_type": resolved_customer_type if is_customer else "STAFF",
            "phone": phone,
            "whatsapp_number": phone,
            "preferred_channels": channels,
            "country": country,
            "preferred_currency": preferred_currency,
            "kyc_verified": is_verified,
            "created_at": created_ts,
        }

    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify email and password against SQLite3 users table."""
        clean_email = email.strip().lower()
        clean_password = password.strip()
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (clean_email,)
            ).fetchone()
            if not row:
                return None
            stored = row["password_hash"]
            if "$" not in stored:
                return None
            salt, _ = stored.split("$", 1)
            if self._hash_password(clean_password, salt) != stored:
                return None

            user = dict(row)
            user.pop("password_hash", None)
            user["preferred_channels"] = json.loads(user.get("preferred_channels") or '["EMAIL"]')
            user["kyc_verified"] = bool(user.get("kyc_verified", 0))
            return user

    def list_all_users(self, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all registered users with IST registration timestamps."""
        with self._get_conn() as conn:
            if role in ("INDRES_NRI", "NRI"):
                rows = conn.execute(
                    """
                    SELECT id, email, full_name, role, customer_type, phone, country,
                           preferred_currency, kyc_verified, police_clearance_id, created_at
                    FROM users WHERE role IN ('INDRES_NRI', 'NRI') ORDER BY rowid DESC
                    """
                ).fetchall()
            elif role:
                rows = conn.execute(
                    """
                    SELECT id, email, full_name, role, customer_type, phone, country,
                           preferred_currency, kyc_verified, police_clearance_id, created_at
                    FROM users WHERE role = ? ORDER BY rowid DESC
                    """,
                    (role,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, email, full_name, role, customer_type, phone, country,
                           preferred_currency, kyc_verified, police_clearance_id, created_at
                    FROM users ORDER BY rowid DESC
                    """
                ).fetchall()
            return [dict(r) for r in rows]

    def verify_staff_kyc(self, user_id: str, police_clearance_id: str, verified: bool = True) -> None:
        """Update Care Manager KYC & Police Clearance status in SQLite3."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET police_clearance_id = ?, kyc_verified = ? WHERE id = ?",
                (police_clearance_id, 1 if verified else 0, user_id),
            )

    def log_staff_action(
        self,
        action: str,
        target_user: Dict[str, Any],
        performed_by: str,
        details: str = "",
    ) -> None:
        """Record employee creation, KYC verification, or deletion in IST audit history."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO staff_audit_logs (
                    action, target_user_id, target_name, target_email,
                    target_role, performed_by, details, timestamp_ist
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action,
                    target_user.get("id", ""),
                    target_user.get("full_name", ""),
                    target_user.get("email", ""),
                    target_user.get("role", ""),
                    performed_by,
                    details,
                    now_ist_str(),
                ),
            )

    def delete_employee_user(self, user_id: str, performed_by: str) -> Dict[str, Any]:
        """Delete an employee (CARE_MANAGER or ADMIN) and record the deletion in audit history."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                raise ValueError("Employee account not found.")
            target = dict(row)
            if target["role"] == "SYSTEM_ADMIN":
                raise ValueError("Master System Admin account cannot be deleted.")

            conn.execute(
                "UPDATE tasks SET care_manager_id = 'UNASSIGNED' WHERE care_manager_id = ? AND status != 'COMPLETED'",
                (user_id,),
            )
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

        self.log_staff_action(
            action="DELETED_EMPLOYEE",
            target_user=target,
            performed_by=performed_by,
            details=f"Removed {target['role']} login ({target['email']})",
        )
        return target

    def list_staff_audit_logs(self) -> List[Dict[str, Any]]:
        """Return chronological history of all employee additions, KYC updates, and deletions."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM staff_audit_logs ORDER BY id DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def add_parent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Allow Indian Residents (self-care) or NRI Sponsors to add a care recipient profile."""
        parent_id = f"par-{uuid.uuid4().hex[:6]}"
        created_ts = now_ist_str()
        owner_id = payload.get("nri_user_id") or payload.get("account_user_id")
        is_self = 1 if payload.get("is_self_care") else 0

        payload["id"] = parent_id
        payload["nri_user_id"] = owner_id
        payload["created_at"] = created_ts

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO parents (
                    id, nri_user_id, is_self_care, full_name, age, city, address,
                    mobility_level, home_access_notes, blood_group,
                    emergency_contact_india, medical_conditions, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    parent_id,
                    owner_id,
                    is_self,
                    payload["full_name"],
                    int(payload["age"]),
                    payload["city"],
                    payload["address"],
                    payload.get("mobility_level", "INDEPENDENT"),
                    payload.get("home_access_notes", ""),
                    payload.get("blood_group", ""),
                    payload.get("emergency_contact_india", ""),
                    payload.get("medical_conditions", ""),
                    created_ts,
                ),
            )
        return payload

    add_care_recipient = add_parent

    def get_parents_for_nri(self, nri_user_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM parents WHERE nri_user_id = ? ORDER BY rowid DESC", (nri_user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    get_recipients_for_user = get_parents_for_nri

    def list_all_parents_with_nri(self) -> List[Dict[str, Any]]:
        """Return every registered care recipient alongside their linked Resident or NRI account."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    p.id AS parent_id,
                    p.full_name AS parent_name,
                    p.is_self_care,
                    p.age,
                    p.city,
                    p.address,
                    p.mobility_level,
                    p.home_access_notes,
                    p.blood_group,
                    p.emergency_contact_india,
                    p.medical_conditions,
                    p.created_at,
                    p.nri_user_id,
                    COALESCE(u.customer_type, 'NRI_SPONSOR') AS customer_type,
                    COALESCE(u.full_name, 'Arjun Sharma (Demo)') AS nri_name,
                    COALESCE(u.email, 'arjun.sharma@example.com') AS nri_email,
                    COALESCE(u.phone, '+14155550199') AS nri_phone
                FROM parents p
                LEFT JOIN users u ON p.nri_user_id = u.id
                ORDER BY p.rowid DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def get_wallet(self, nri_user_id: str) -> Dict[str, Any]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM wallets WHERE nri_user_id = ?", (nri_user_id,)
            ).fetchone()
            return dict(row) if row else {"plan_tier": "PAY_AS_YOU_GO", "balance_inr": 0.0, "updated_at": now_ist_str()}

    def update_wallet_plan(self, nri_user_id: str, plan_tier: str) -> None:
        """Update the subscription plan tier for an Indian Resident or NRI account."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO wallets (nri_user_id, plan_tier, balance_inr, updated_at)
                VALUES (?, ?, 0.0, ?)
                ON CONFLICT(nri_user_id) DO UPDATE SET plan_tier = excluded.plan_tier, updated_at = excluded.updated_at
                """,
                (nri_user_id, plan_tier, now_ist_str()),
            )

    def update_wallet_balance(self, nri_user_id: str, delta_inr: float) -> float:
        wallet = self.get_wallet(nri_user_id)
        new_balance = round(float(wallet.get("balance_inr", 0.0)) + delta_inr, 2)
        if new_balance < 0:
            raise ValueError("Insufficient prepaid wallet balance.")
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE wallets SET balance_inr = ?, updated_at = ? WHERE nri_user_id = ?",
                (new_balance, now_ist_str(), nri_user_id),
            )
        return new_balance

    def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        created_ts = now_ist_str()
        owner_id = payload.get("nri_user_id") or payload.get("booked_by_user_id")
        recipient_id = payload.get("parent_id") or payload.get("recipient_id")

        with self._get_conn() as conn:
            count_row = conn.execute("SELECT COUNT(*) AS cnt FROM tasks").fetchone()
            task_id = payload.get("id") or f"TSK-{1001 + count_row['cnt']}"
            payload["id"] = task_id
            payload["nri_user_id"] = owner_id
            payload["parent_id"] = recipient_id
            payload["created_at"] = created_ts
            conn.execute(
                """
                INSERT INTO tasks (
                    id, nri_user_id, parent_id, parent_name, care_manager_id,
                    category, title, instructions, scheduled_at,
                    requires_wheelchair_cab, requires_two_person_lift,
                    third_party_vendor_type, status,
                    service_fee_inr, out_of_pocket_inr, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    owner_id,
                    recipient_id,
                    payload.get("parent_name", ""),
                    payload.get("care_manager_id", "usr-cm-201"),
                    payload["category"],
                    payload["title"],
                    payload.get("instructions", ""),
                    payload["scheduled_at"],
                    1 if payload.get("requires_wheelchair_cab") else 0,
                    1 if payload.get("requires_two_person_lift") else 0,
                    payload.get("third_party_vendor_type", ""),
                    payload.get("status", "ASSIGNED"),
                    float(payload.get("service_fee_inr", 0.0)),
                    float(payload.get("out_of_pocket_inr", 0.0)),
                    created_ts,
                ),
            )
        return payload

    def assign_task_to_staff(self, task_id: str, care_manager_id: str) -> None:
        """Assign or reassign a care task to a specific Care Manager (Sahayak)."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tasks SET care_manager_id = ?, status = 'ASSIGNED' WHERE id = ?",
                (care_manager_id, task_id),
            )

    def update_task_completion(
        self,
        task_id: str,
        status: str = "COMPLETED",
        gps_lat: Optional[float] = None,
        gps_lng: Optional[float] = None,
        service_fee_inr: Optional[float] = None,
        out_of_pocket_inr: Optional[float] = None,
        receipt_url: Optional[str] = None,
        receipt_verified: Optional[bool] = None,
        completion_notes: Optional[str] = None,
    ) -> None:
        """Update GPS check-in, receipt upload, actuals, and completion notes for a visit."""
        updates: List[str] = ["status = ?"]
        params: List[Any] = [status]

        if gps_lat is not None and gps_lng is not None:
            updates.extend(["gps_lat = ?", "gps_lng = ?", "checkin_time = ?"])
            params.extend([gps_lat, gps_lng, now_ist_str()])
        if service_fee_inr is not None:
            updates.append("service_fee_inr = ?")
            params.append(float(service_fee_inr))
        if out_of_pocket_inr is not None:
            updates.append("out_of_pocket_inr = ?")
            params.append(float(out_of_pocket_inr))
        if receipt_url is not None:
            updates.append("receipt_url = ?")
            params.append(receipt_url)
        if receipt_verified is not None:
            updates.append("receipt_verified = ?")
            params.append(1 if receipt_verified else 0)
        if completion_notes is not None:
            updates.append("completion_notes = ?")
            params.append(completion_notes)

        params.append(task_id)
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )

    def list_tasks(self, role: str, user_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            if role in ("INDRES_NRI", "NRI"):
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE nri_user_id = ? ORDER BY rowid DESC", (user_id,)
                ).fetchall()
            elif role == "CARE_MANAGER":
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE care_manager_id = ? ORDER BY rowid DESC", (user_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM tasks ORDER BY rowid DESC").fetchall()
            return [dict(r) for r in rows]

    def save_invoice(self, invoice_payload: Dict[str, Any]) -> Dict[str, Any]:
        channels_json = json.dumps(invoice_payload.get("dispatched_channels", []))
        created_ts = invoice_payload.get("created_at") or now_ist_str()
        invoice_payload["created_at"] = created_ts
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO invoices (
                    invoice_number, nri_user_id, task_id, currency, service_fee_inr,
                    out_of_pocket_inr, gst_inr, total_inr, total_converted,
                    pdf_storage_path, status, dispatched_channels, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_payload["invoice_number"],
                    invoice_payload["nri_user_id"],
                    invoice_payload.get("task_id"),
                    invoice_payload.get("currency", "INR"),
                    float(invoice_payload.get("service_fee_inr", 0.0)),
                    float(invoice_payload.get("out_of_pocket_inr", 0.0)),
                    float(invoice_payload.get("gst_inr", 0.0)),
                    float(invoice_payload["total_inr"]),
                    float(invoice_payload["total_converted"]),
                    invoice_payload.get("pdf_storage_path"),
                    invoice_payload.get("status", "PAID"),
                    channels_json,
                    created_ts,
                ),
            )
        return invoice_payload

    def list_invoices(self, nri_user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            if nri_user_id:
                rows = conn.execute(
                    "SELECT * FROM invoices WHERE nri_user_id = ? ORDER BY rowid DESC",
                    (nri_user_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM invoices ORDER BY rowid DESC").fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["dispatched_channels"] = json.loads(item.get("dispatched_channels") or "[]")
                results.append(item)
            return results

    def log_vitals(self, vitals_payload: Dict[str, Any]) -> Dict[str, Any]:
        recorded_ts = vitals_payload.get("recorded_at") or now_ist_str()
        vitals_payload["recorded_at"] = recorded_ts
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO vitals_logs (
                    parent_id, logged_by, systolic_bp, diastolic_bp,
                    blood_sugar_mgdl, pulse_bpm, spo2_percent, notes, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vitals_payload["parent_id"],
                    vitals_payload.get("logged_by"),
                    vitals_payload.get("systolic_bp"),
                    vitals_payload.get("diastolic_bp"),
                    vitals_payload.get("blood_sugar_mgdl"),
                    vitals_payload.get("pulse_bpm"),
                    vitals_payload.get("spo2_percent"),
                    vitals_payload.get("notes", ""),
                    recorded_ts,
                ),
            )
        return vitals_payload

    def get_vitals(self, parent_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM vitals_logs WHERE parent_id = ? ORDER BY id ASC", (parent_id,)
            ).fetchall()
            return [dict(r) for r in rows]
