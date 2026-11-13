from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    INDRES_NRI = "INDRES_NRI"  # Unified role for Indian Residents & NRI Sponsors
    NRI = "NRI"  # Kept for backward compatibility with existing DB records
    CARE_MANAGER = "CARE_MANAGER"
    ADMIN = "ADMIN"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


class CustomerType(str, Enum):
    INDIAN_RESIDENT = "INDIAN_RESIDENT"  # Self-care resident living in India
    NRI_SPONSOR = "NRI_SPONSOR"  # NRI or out-of-city family booking for loved ones


class MobilityLevel(str, Enum):
    INDEPENDENT = "INDEPENDENT"
    WALKER_ASSISTED = "WALKER_ASSISTED"
    WHEELCHAIR_REQUIRED = "WHEELCHAIR_REQUIRED"
    BEDRIDDEN = "BEDRIDDEN"
    POST_SURGERY_RECOVERY = "POST_SURGERY_RECOVERY"


class PlanTier(str, Enum):
    PAY_AS_YOU_GO = "PAY_AS_YOU_GO"
    ESSENTIAL = "ESSENTIAL"
    COMPLETE = "COMPLETE"
    COUPLE = "COUPLE"
    RESIDENT_MOBILITY_CARE = "RESIDENT_MOBILITY_CARE"  # Dedicated plan for homebound residents


class TaskCategory(str, Enum):
    MEDICAL_ESCORT = "MEDICAL_ESCORT"
    IN_HOME_MEDICAL = "IN_HOME_MEDICAL"  # Home physio, lab sample collection, equipment setup
    VITALS_CHECK = "VITALS_CHECK"
    BANK_GOV_ERRAND = "BANK_GOV_ERRAND"  # Doorstep banking, Jeevan Pramaan, notary, UDID/KYC
    HOME_MAINTENANCE = "HOME_MAINTENANCE"  # Plumber, electrician, grab-bar/ramp installation
    DAILY_ERRANDS_GROCERY = "DAILY_ERRANDS_GROCERY"  # Groceries, pharmacy refills, home grooming
    ASSISTED_OUTING = "ASSISTED_OUTING"  # Wheelchair cab outings, temple/social visits
    AIRPORT_ASSIST = "AIRPORT_ASSIST"
    PROPERTY_CHECK = "PROPERTY_CHECK"
    EMERGENCY_SOS = "EMERGENCY_SOS"
    CUSTOM_REQUEST = "CUSTOM_REQUEST"


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
    customer_type: Optional[CustomerType] = CustomerType.NRI_SPONSOR
    phone: str
    whatsapp_number: Optional[str] = None
    preferred_channels: List[DeliveryChannel] = [DeliveryChannel.EMAIL, DeliveryChannel.WHATSAPP]
    country: str = "India"
    preferred_currency: str = "INR"
    kyc_verified: bool = False
    police_clearance_id: Optional[str] = None


class CareRecipientProfile(BaseModel):
    id: Optional[str] = None
    account_user_id: str  # Links to either the Indian Resident's own user ID or NRI Sponsor's ID
    is_self_care: bool = False  # True when an Indian Resident books for themselves
    full_name: str
    age: int = Field(..., ge=1, le=120)  # Supports residents of any age needing mobility/care support
    city: str
    address: str
    mobility_level: MobilityLevel = MobilityLevel.INDEPENDENT
    home_access_notes: Optional[str] = None  # e.g., "2nd floor with lift", "Wheelchair ramp needed"
    blood_group: Optional[str] = None
    emergency_contact_india: Optional[str] = None
    medical_conditions: Optional[str] = None


# Alias kept so existing imports of ParentProfile across database.py/pages continue working
ParentProfile = CareRecipientProfile


class TaskRequest(BaseModel):
    id: Optional[str] = None
    booked_by_user_id: str
    recipient_id: str
    category: TaskCategory
    title: str
    description: Optional[str] = ""
    scheduled_at: datetime
    requires_wheelchair_cab: bool = False
    requires_two_person_lift: bool = False
    third_party_vendor_type: Optional[str] = None  # e.g., "Physiotherapist", "Bank Officer", "Plumber"
    status: TaskStatus = TaskStatus.PENDING


class VitalsEntry(BaseModel):
    recipient_id: str
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
    client_name: str  # NRI Sponsor or Indian Resident name
    client_email: str
    recipient_name: str  # Care recipient name (same as client_name for self-care residents)
    recipient_city: str
    currency: str = "INR"
    items: List[InvoiceLineItem]
    service_fee_inr: float = 0.0
    out_of_pocket_inr: float = 0.0
    gst_rate: float = 0.18  # 18% GST on service fee only (0% on actuals pass-through)
    issued_at: datetime = Field(default_factory=datetime.utcnow)
