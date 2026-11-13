from datetime import datetime, timedelta
from typing import Any, Dict, List
import streamlit as st


DEMO_USERS: Dict[str, Dict[str, Any]] = {
    "INDRES_NRI": {
        "id": "usr-nri-101",
        "email": "arjun.sharma@example.com",
        "full_name": "Arjun Sharma",
        "role": "INDRES_NRI",
        "customer_type": "NRI_SPONSOR",
        "phone": "+14155550199",
        "whatsapp_number": "+14155550199",
        "preferred_channels": ["EMAIL", "WHATSAPP", "SMS"],
        "country": "USA",
        "preferred_currency": "USD",
        "kyc_verified": True,
    },
    "INDIAN_RESIDENT": {
        "id": "usr-indres-102",
        "email": "lakshmi.rao@example.com",
        "full_name": "Smt. Lakshmi Narayana Rao",
        "role": "INDRES_NRI",
        "customer_type": "INDIAN_RESIDENT",
        "phone": "+919848022334",
        "whatsapp_number": "+919848022334",
        "preferred_channels": ["WHATSAPP", "SMS"],
        "country": "India",
        "preferred_currency": "INR",
        "kyc_verified": True,
    },
    "CARE_MANAGER": {
        "id": "usr-cm-201",
        "email": "ravi.sahayak@carebridgeindia.com",
        "full_name": "Ravi Kumar (Senior Sahayak)",
        "role": "CARE_MANAGER",
        "customer_type": "STAFF",
        "phone": "+919848012345",
        "whatsapp_number": "+919848012345",
        "preferred_channels": ["WHATSAPP", "SMS"],
        "country": "India",
        "preferred_currency": "INR",
        "kyc_verified": True,
        "police_clearance_id": "AP-POL-VSP-88412",
    },
    "ADMIN": {
        "id": "usr-adm-301",
        "email": "ops@carebridgeindia.com",
        "full_name": "Priya Nair (Operations Lead)",
        "role": "ADMIN",
        "customer_type": "STAFF",
        "phone": "+919849054321",
        "whatsapp_number": "+919849054321",
        "preferred_channels": ["EMAIL", "WHATSAPP"],
        "country": "India",
        "preferred_currency": "INR",
        "kyc_verified": True,
    },
}
# Backward-compatible alias
DEMO_USERS["NRI"] = DEMO_USERS["INDRES_NRI"]


def init_session_state() -> None:
    """Initialize global session state, currency preferences, and demo seed records."""
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("current_user", None)
    st.session_state.setdefault("currency", "USD")

    if "demo_parents" not in st.session_state:
        st.session_state["demo_parents"] = [
            {
                "id": "par-01",
                "nri_user_id": "usr-nri-101",
                "is_self_care": 0,
                "full_name": "Dr. Raghavendra Sharma",
                "age": 74,
                "city": "Visakhapatnam",
                "address": "Flat 402, Sea Breeze Enclave, MVP Colony, Visakhapatnam",
                "mobility_level": "WALKER_ASSISTED",
                "home_access_notes": "4th floor with elevator; security gate pass required",
                "blood_group": "O+",
                "emergency_contact_india": "+919848099887",
                "medical_conditions": "Type 2 Diabetes, Mild Hypertension",
            },
            {
                "id": "par-02",
                "nri_user_id": "usr-nri-101",
                "is_self_care": 0,
                "full_name": "Smt. Meenakshi Sharma",
                "age": 69,
                "city": "Visakhapatnam",
                "address": "Flat 402, Sea Breeze Enclave, MVP Colony, Visakhapatnam",
                "mobility_level": "WHEELCHAIR_REQUIRED",
                "home_access_notes": "Needs wheelchair ramp at lobby entrance",
                "blood_group": "B+",
                "emergency_contact_india": "+919848099887",
                "medical_conditions": "Osteoarthritis (Knee)",
            },
            {
                "id": "par-03",
                "nri_user_id": "usr-indres-102",
                "is_self_care": 1,
                "full_name": "Smt. Lakshmi Narayana Rao",
                "age": 67,
                "city": "Hyderabad",
                "address": "Plot 18, Road No. 4, Banjara Hills, Hyderabad",
                "mobility_level": "WHEELCHAIR_REQUIRED",
                "home_access_notes": "Ground floor residence; wheelchair cab needed for hospital visits",
                "blood_group": "A+",
                "emergency_contact_india": "+919848022334",
                "medical_conditions": "Post-Hip Replacement Recovery",
            },
        ]

    st.session_state.setdefault(
        "demo_wallet", {"plan_tier": "COUPLE", "balance_inr": 18500.00}
    )

    if "demo_tasks" not in st.session_state:
        now = datetime.utcnow()
        st.session_state["demo_tasks"] = [
            {
                "id": "TSK-1001",
                "nri_user_id": "usr-nri-101",
                "parent_id": "par-01",
                "parent_name": "Dr. Raghavendra Sharma",
                "care_manager_id": "usr-cm-201",
                "category": "MEDICAL_ESCORT",
                "title": "Cardiology Follow-up at Apollo Health City",
                "instructions": "Collect fasting lipid profile and accompany for 10:30 AM consult.",
                "scheduled_at": (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
                "requires_wheelchair_cab": 0,
                "requires_two_person_lift": 0,
                "third_party_vendor_type": "",
                "status": "ASSIGNED",
                "service_fee_inr": 1500.0,
                "out_of_pocket_inr": 0.0,
                "receipt_verified": False,
            },
            {
                "id": "TSK-1000",
                "nri_user_id": "usr-nri-101",
                "parent_id": "par-02",
                "parent_name": "Smt. Meenakshi Sharma",
                "care_manager_id": "usr-cm-201",
                "category": "VITALS_CHECK",
                "title": "Weekly Home Vitals & Physiotherapy Check",
                "instructions": "Log BP, blood sugar, and monthly pharmacy refill.",
                "scheduled_at": (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
                "requires_wheelchair_cab": 1,
                "requires_two_person_lift": 0,
                "third_party_vendor_type": "Physiotherapist",
                "status": "COMPLETED",
                "gps_lat": 17.7412,
                "gps_lng": 83.3341,
                "checkin_time": (now - timedelta(days=2)).strftime("%Y-%m-%d 09:45 UTC"),
                "service_fee_inr": 800.0,
                "out_of_pocket_inr": 1420.0,
                "receipt_verified": True,
                "completion_notes": "Vitals stable. Monthly prescription medicines delivered with pharmacy bill.",
            },
        ]

    if "demo_vitals" not in st.session_state:
        now = datetime.utcnow()
        st.session_state["demo_vitals"] = [
            {
                "parent_id": "par-01",
                "systolic_bp": 134,
                "diastolic_bp": 84,
                "blood_sugar_mgdl": 128,
                "pulse_bpm": 74,
                "spo2_percent": 98,
                "notes": "Morning fasting check",
                "recorded_at": (now - timedelta(days=14)).strftime("%Y-%m-%d"),
            },
            {
                "parent_id": "par-01",
                "systolic_bp": 128,
                "diastolic_bp": 80,
                "blood_sugar_mgdl": 116,
                "pulse_bpm": 72,
                "spo2_percent": 98,
                "notes": "Post-walk check",
                "recorded_at": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
            },
            {
                "parent_id": "par-01",
                "systolic_bp": 124,
                "diastolic_bp": 78,
                "blood_sugar_mgdl": 112,
                "pulse_bpm": 70,
                "spo2_percent": 99,
                "notes": "Routine Sahayak visit",
                "recorded_at": now.strftime("%Y-%m-%d"),
            },
        ]


def login_as_role(role: str, custom_profile: Dict[str, Any] | None = None) -> None:
    """Authenticate user into session state."""
    profile = custom_profile or DEMO_USERS[role].copy()
    st.session_state["authenticated"] = True
    st.session_state["current_user"] = profile
    st.session_state["currency"] = profile.get("preferred_currency", "USD")


def logout_user() -> None:
    """Clear current user session."""
    st.session_state["authenticated"] = False
    st.session_state["current_user"] = None


def require_role(allowed_roles: List[str]) -> Dict[str, Any]:
    """Guard a Streamlit page so only authorized roles can view it."""
    init_session_state()
    if not st.session_state.get("authenticated") or not st.session_state.get("current_user"):
        st.warning("Please sign in from the **Home / Gateway** page to access this portal.")
        st.stop()

    user = st.session_state["current_user"]
    expanded_allowed = set(allowed_roles)
    if "INDRES_NRI" in expanded_allowed or "NRI" in expanded_allowed:
        expanded_allowed.update({"INDRES_NRI", "NRI"})

    if user.get("role") not in expanded_allowed:
        st.error(
            f"Access Denied: Your role (**{user.get('role')}**) does not have permission for this module."
        )
        st.stop()
    return user
