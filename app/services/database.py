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
                    full_name TEXT NOT NULL,
                    age INTEGER NOT NULL,
                    city TEXT NOT NULL,
                    address TEXT NOT NULL,
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
                """
            )

            # Auto-migrate missing columns on existing SQLite databases
            existing_cols = {
                row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
            }
            migrations = {
                "whatsapp_number": "TEXT",
                "preferred_channels": "TEXT DEFAULT '[\"EMAIL\", \"WHATSAPP\"]'",
                "country": "TEXT DEFAULT 'USA'",
                "preferred_currency": "TEXT DEFAULT 'USD'",
                "kyc_verified": "INTEGER DEFAULT 0",
                "police_clearance_id": "TEXT",
                "created_at": "TEXT",
            }
            for col_name, col_def in migrations.items():
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")

            # Seed sample parent & wallet if parents table is empty
            cur = conn.execute("SELECT COUNT(*) FROM parents")
            if cur.fetchone() == 0:
                seed_ts = now_ist_str()
                conn.execute(
                    """
                    INSERT INTO parents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        seed_ts,
                    ),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO wallets VALUES (?, ?, ?, ?)",
                    ("usr-nri-101", "COUPLE", 18500.00, seed_ts),
                )

            # Seed default SYSTEM_ADMIN account if none exists
            admin_cur = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'SYSTEM_ADMIN'"
            )
            if admin_cur.fetchone() == 0:
                seed_ts = now_ist_str()
                conn.execute(
                    """
                    INSERT OR IGNORE INTO users (
                        id, email, password_hash, full_name, role, phone,
                        whatsapp_number, preferred_channels, country,
                        preferred_currency, kyc_verified, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "usr-sysadmin-01",
                        "sysadmin@carebridge.in",
                        self._hash_password("SysAdmin@123"),
                        "Master System Admin",
                        "SYSTEM_ADMIN",
                        "+919848000001",
                        "+919848000001",
                        '["EMAIL", "WHATSAPP"]',
                        "India",
                        "INR",
                        1,
                        seed_ts,
                    ),
                )
