import hashlib
import json
import secrets
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.utils.datetime_helper import now_ist_str


DB_PATH = Path(__file__).resolve().parents[2] / "carebridge.db"


class DatabaseService:
    """Zero-setup SQLite3 data layer with automatic schema creation, auth & seed data."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

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
                    phone TEXT NOT NULL,
                    whatsapp_number TEXT,
                    preferred_channels TEXT DEFAULT '["EMAIL", "WHATSAPP"]',
                    country TEXT DEFAULT 'USA',
                    preferred_currency TEXT DEFAULT 'USD',
                    kyc_verified INTEGER DEFAULT 0,
                    police_clearance_id TEXT
                );

                CREATE TABLE IF NOT EXISTS parents (
                    id TEXT PRIMARY KEY,
                    nri_user_id TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    age INTEGER NOT NULL,
                    city TEXT NOT NULL,
                    address TEXT NOT NULL,
                    blood_group TEXT,
                    emergency_contact_india TEXT,
                    medical_conditions TEXT
                );

                CREATE TABLE IF NOT EXISTS wallets (
                    nri_user_id TEXT PRIMARY KEY,
                    plan_tier TEXT DEFAULT 'COUPLE',
                    balance_inr REAL DEFAULT 18500.00
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
                    status TEXT DEFAULT 'ASSIGNED',
                    gps_lat REAL,
                    gps_lng REAL,
                    checkin_time TEXT,
                    service_fee_inr REAL DEFAULT 0.0,
                    out_of_pocket_inr REAL DEFAULT 0.0,
                    receipt_url TEXT,
                    receipt_verified INTEGER DEFAULT 0,
                    completion_notes TEXT
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
                    dispatched_channels TEXT DEFAULT '[]'
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
                """
            )
            cur = conn.execute("SELECT COUNT(*) FROM parents")
            if cur.fetchone()[0] == 0:
                conn.execute(
                    """
                    INSERT INTO parents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "par-01",
                        "usr-nri-101",
                        "Dr. Raghavendra Sharma",
                        74,
                        "Visakhapatnam",
                        "Flat 402, Sea Breeze Enclave, MVP Colony, Visakhapatnam",
                        "O+",
                        "+919848099887",
                        "Type 2 Diabetes, Mild Hypertension",
                    ),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO wallets VALUES (?, ?, ?)",
                    ("usr-nri-101", "COUPLE", 18500.00),
                )
    @staticmethod
    def _hash_password(password: str, salt: Optional[str] = None) -> str:
        salt = salt or secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
        ).hex()
        return f"{salt}${pwd_hash}"

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
    ) -> Dict[str, Any]:
        """Create a new user account in SQLite3 and initialize a prepaid wallet if NRI."""
        clean_email = email.strip().lower()
        channels = preferred_channels or ["EMAIL", "WHATSAPP"]
        user_id = f"usr-{uuid.uuid4().hex[:8]}"
        hashed_pw = self._hash_password(password)

        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE email = ?", (clean_email,)
            ).fetchone()
            if existing:
                raise ValueError("An account with this email already exists. Please sign in.")

            conn.execute(
                """
                INSERT INTO users (
                    id, email, password_hash, full_name, role, phone,
                    whatsapp_number, preferred_channels, country, preferred_currency, kyc_verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    clean_email,
                    hashed_pw,
                    full_name.strip(),
                    role,
                    phone,
                    phone,
                    json.dumps(channels),
                    country,
                    preferred_currency,
                    1 if role == "NRI" else 0,
                ),
            )
            if role == "NRI":
                conn.execute(
                    "INSERT OR IGNORE INTO wallets (nri_user_id, plan_tier, balance_inr) VALUES (?, ?, ?)",
                    (user_id, "PAY_AS_YOU_GO", 0.0),
                )

        return {
            "id": user_id,
            "email": clean_email,
            "full_name": full_name.strip(),
            "role": role,
            "phone": phone,
            "whatsapp_number": phone,
            "preferred_channels": channels,
            "country": country,
            "preferred_currency": preferred_currency,
            "kyc_verified": role == "NRI",
        }

    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify email and password against SQLite3 users table."""
        clean_email = email.strip().lower()
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
            if self._hash_password(password, salt) != stored:
                return None

            user = dict(row)
            user.pop("password_hash", None)
            user["preferred_channels"] = json.loads(user.get("preferred_channels") or '["EMAIL"]')
            user["kyc_verified"] = bool(user.get("kyc_verified", 0))
            return user

    def add_parent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Allow newly registered NRI users to add their parent's profile."""
        parent_id = f"par-{uuid.uuid4().hex[:6]}"
        payload["id"] = parent_id
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO parents (
                    id, nri_user_id, full_name, age, city, address,
                    blood_group, emergency_contact_india, medical_conditions
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    parent_id,
                    payload["nri_user_id"],
                    payload["full_name"],
                    int(payload["age"]),
                    payload["city"],
                    payload["address"],
                    payload.get("blood_group", ""),
                    payload.get("emergency_contact_india", ""),
                    payload.get("medical_conditions", ""),
                ),
            )
        return payload

    def get_parents_for_nri(self, nri_user_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM parents WHERE nri_user_id = ?", (nri_user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_wallet(self, nri_user_id: str) -> Dict[str, Any]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM wallets WHERE nri_user_id = ?", (nri_user_id,)
            ).fetchone()
            return dict(row) if row else {"plan_tier": "PAY_AS_YOU_GO", "balance_inr": 0.0}

    def update_wallet_balance(self, nri_user_id: str, delta_inr: float) -> float:
        wallet = self.get_wallet(nri_user_id)
        new_balance = round(float(wallet.get("balance_inr", 0.0)) + delta_inr, 2)
        if new_balance < 0:
            raise ValueError("Insufficient prepaid wallet balance.")
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE wallets SET balance_inr = ? WHERE nri_user_id = ?",
                (new_balance, nri_user_id),
            )
        return new_balance
    def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._get_conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            task_id = payload.get("id") or f"TSK-{1001 + count}"
            payload["id"] = task_id
            conn.execute(
                """
                INSERT INTO tasks (
                    id, nri_user_id, parent_id, parent_name, care_manager_id,
                    category, title, instructions, scheduled_at, status,
                    service_fee_inr, out_of_pocket_inr
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    payload["nri_user_id"],
                    payload["parent_id"],
                    payload.get("parent_name", ""),
                    payload.get("care_manager_id", "usr-cm-201"),
                    payload["category"],
                    payload["title"],
                    payload.get("instructions", ""),
                    payload["scheduled_at"],
                    payload.get("status", "ASSIGNED"),
                    float(payload.get("service_fee_inr", 0.0)),
                    float(payload.get("out_of_pocket_inr", 0.0)),
                ),
            )
        return payload

    def list_tasks(self, role: str, user_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            if role == "NRI":
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
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO invoices (
                    invoice_number, nri_user_id, task_id, currency, service_fee_inr,
                    out_of_pocket_inr, gst_inr, total_inr, total_converted,
                    pdf_storage_path, status, dispatched_channels
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_payload["invoice_number"],
                    invoice_payload["nri_user_id"],
                    invoice_payload.get("task_id"),
                    invoice_payload.get("currency", "USD"),
                    float(invoice_payload.get("service_fee_inr", 0.0)),
                    float(invoice_payload.get("out_of_pocket_inr", 0.0)),
                    float(invoice_payload.get("gst_inr", 0.0)),
                    float(invoice_payload["total_inr"]),
                    float(invoice_payload["total_converted"]),
                    invoice_payload.get("pdf_storage_path"),
                    invoice_payload.get("status", "PAID"),
                    channels_json,
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
                    vitals_payload.get("recorded_at"),
                ),
            )
        return vitals_payload

    def get_vitals(self, parent_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM vitals_logs WHERE parent_id = ? ORDER BY id ASC", (parent_id,)
            ).fetchall()
            return [dict(r) for r in rows]
    def list_all_users(self, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all registered users (or filter by role: NRI, CARE_MANAGER, ADMIN)."""
        with self._get_conn() as conn:
            if role:
                rows = conn.execute(
                    "SELECT id, email, full_name, role, phone, country, preferred_currency, kyc_verified, police_clearance_id FROM users WHERE role = ?",
                    (role,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, email, full_name, role, phone, country, preferred_currency, kyc_verified, police_clearance_id FROM users"
                ).fetchall()
            return [dict(r) for r in rows]

    def list_all_parents_with_nri(self) -> List[Dict[str, Any]]:
        """Return every registered parent alongside their linked NRI family member."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    p.id AS parent_id,
                    p.full_name AS parent_name,
                    p.age,
                    p.city,
                    p.address,
                    p.blood_group,
                    p.emergency_contact_india,
                    p.medical_conditions,
                    p.nri_user_id,
                    COALESCE(u.full_name, 'Arjun Sharma (Demo)') AS nri_name,
                    COALESCE(u.email, 'arjun.sharma@example.com') AS nri_email,
                    COALESCE(u.phone, '+14155550199') AS nri_phone
                FROM parents p
                LEFT JOIN users u ON p.nri_user_id = u.id
                ORDER BY p.rowid DESC
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
    def assign_task_to_staff(self, task_id: str, care_manager_id: str) -> None:
        """Assign or reassign a care task to a specific Care Manager (Sahayak)."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tasks SET care_manager_id = ?, status = 'ASSIGNED' WHERE id = ?",
                (care_manager_id, task_id),
            )
