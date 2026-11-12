from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    NRI = "NRI"
    CARE_MANAGER = "CARE_MANAGER"
    ADMIN = "ADMIN"


class PlanTier(str, Enum):
    PAY_AS_YOU_GO = "PAY_AS_YOU_GO"
    ESSENTIAL = "ESSENTIAL"
    COMPLETE = "COMPLETE"
    COUPLE = "COUPLE"


class TaskCategory(str, Enum):
    MEDICAL_ESCORT = "MEDICAL_ESCORT"
    VITALS_CHECK = "VITALS_CHECK"
    BANK_GOV_ERRAND = "BANK_GOV_ERRAND"
    AIRPORT_ASSIST = "AIRPORT_ASSIST"
    PROPERTY_CHECK = "PROPERTY_CHECK"
    EMERGENCY_SOS = "EMERGENCY_SOS"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    SOS_ACTIVE = "SOS_ACTIVE"


class DeliveryChannel(str, Enum):
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"


class UserProfile(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    phone: str
    whatsapp_number: Optional[str] = None
    preferred_channels: List[DeliveryChannel] = [DeliveryChannel.EMAIL, DeliveryChannel.WHATSAPP]
    country: str = "USA"
    preferred_currency: str = "USD"
    kyc_verified: bool = False
    police_clearance_id: Optional[str] = None


class ParentProfile(BaseModel):
    id: Optional[str] = None
    nri_user_id: str
    full_name: str
    age: int = Field(..., ge=45, le=120)
    city: str
    address: str
    blood_group: Optional[str] = None
    emergency_contact_india: Optional[str] = None
    medical_conditions: Optional[str] = None


class VitalsEntry(BaseModel):
    parent_id: str
    logged_by: str
    systolic_bp: Optional[int] = Field(None, ge=60, le=260)
    diastolic_bp: Optional[int] = Field(None, ge=40, le=160)
    blood_sugar_mgdl: Optional[int] = Field(None, ge=30, le=600)
    pulse_bpm: Optional[int] = Field(None, ge=30, le=220)
    spo2_percent: Optional[int] = Field(None, ge=70, le=100)
    notes: Optional[str] = ""
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class InvoiceLineItem(BaseModel):
    description: str
    category: str
    amount_inr: float


class InvoiceRecord(BaseModel):
    invoice_number: str
    nri_name: str
    nri_email: str
    parent_name: str
    parent_city: str
    currency: str = "USD"
    items: List[InvoiceLineItem]
    service_fee_inr: float = 0.0
    out_of_pocket_inr: float = 0.0
    gst_rate: float = 0.18  # 18% GST on service fee only (0% on actuals pass-through)
    issued_at: datetime = Field(default_factory=datetime.utcnow)
