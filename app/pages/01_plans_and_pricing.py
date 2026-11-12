from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from app.auth.session_manager import init_session_state
from app.utils.currency import format_currency

st.set_page_config(page_title="Plans & Pricing — CareBridge India", page_icon="💳", layout="wide")
init_session_state()

curr = st.session_state.get("currency", "USD")

st.title("Plans & Transparent Rate Card")
st.markdown(
    "All plans include **0% markup on out-of-pocket expenses** (medicines, lab bills, cab fares), "
    "backed by itemized PDF invoices and photo receipts."
)

# Monthly Subscription Tiers
st.subheader("Monthly Care Subscriptions")
plans = [
    {
        "tier": "ESSENTIAL",
        "name": "Essential Errands & Check-Ins",
        "min_inr": 3500,
        "max_inr": 6000,
        "highlights": [
            "2 planned home visits per month",
            "Utility bill payments & banking help",
            "Grocery/pharmacy delivery coordination",
            "GPS check-in & WhatsApp/Email photo summary",
        ],
    },
    {
        "tier": "COMPLETE",
        "name": "Complete Medical + Errands",
        "min_inr": 7500,
        "max_inr": 12500,
        "highlights": [
            "4 weekly home visits (vitals: BP, sugar, SpO2)",
            "Doctor appointment & hospital escorting",
            "Monthly medicine refills & digital Health Vault",
            "24/7 Emergency SOS hospital coordination",
        ],
    },
    {
        "tier": "COUPLE",
        "name": "Comprehensive / Couple Care",
        "min_inr": 14000,
        "max_inr": 22000,
        "highlights": [
            "Weekly visits covering BOTH parents",
            "Priority hospital escorting & lab home collection",
            "Quarterly locked property / flat inspection",
            "Dedicated Senior Care Manager (Sahayak)",
        ],
    },
]

cols = st.columns(3)
for col, plan in zip(cols, plans):
    with col:
        st.markdown(f"### {plan['name']}")
        price_range = f"{format_currency(plan['min_inr'], curr)} – {format_currency(plan['max_inr'], curr)} / mo"
        st.info(f"**{price_range}**")
        for item in plan["highlights"]:
            st.write(f"- {item}")
        if st.button(f"Select {plan['tier']} Plan", key=f"sub_{plan['tier']}", use_container_width=True):
            if st.session_state.get("authenticated"):
                st.session_state["demo_wallet"]["plan_tier"] = plan["tier"]
                st.success(f"Switched active subscription tier to **{plan['tier']}**!")
            else:
                st.warning("Sign in from the Home page to activate this subscription.")

st.divider()

# Pay-As-You-Go On-Demand Rates
st.subheader("Pay-As-You-Go On-Demand Services")
ondemand_services = [
    ("Doctor / Hospital Visit Escort (up to 4 hrs)", 1000, 2500),
    ("Routine Home Wellbeing & Vitals Check", 600, 1200),
    ("Bank, Government, or Pension Life Certificate", 1000, 2000),
    ("Airport Pickup / Drop Assistance (excl. cab/toll)", 1500, 3500),
    ("Property / Locked Flat Inspection with Video", 1500, 3000),
]

for service_name, low_inr, high_inr in ondemand_services:
    c1, c2 = st.columns([3, 2])
    c1.write(f"**{service_name}**")
    c2.write(f"{format_currency(low_inr, curr)} – {format_currency(high_inr, curr)}")
