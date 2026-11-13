from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from app.auth.session_manager import init_session_state
from app.services.database import DatabaseService
from app.utils.currency import format_currency

init_session_state()
db = DatabaseService()

user = st.session_state.get("current_user") or {}
is_ind_res = user.get("customer_type") == "INDIAN_RESIDENT"
curr = st.session_state.get("currency", "INR" if is_ind_res else "USD")

st.title("Plans & Transparent Rate Card")
st.markdown("All plans include **0% markup on out-of-pocket expenses**, backed by itemized PDF invoices and photo receipts.")

# Monthly Subscription Tiers
st.subheader("Monthly Care Subscriptions")
plans = [
    ("ESSENTIAL", "Essential Errands & Check-Ins", 3500, 6000, ["2 planned home visits/month", "Utility bills & doorstep banking", "Grocery & pharmacy refills", "GPS check-in & WhatsApp/Email update"]),
    ("RESIDENT_MOBILITY_CARE", "♿ Resident Mobility & Homebound Care", 9000, 15000, ["6 assisted visits/month (bedridden/non-walking)", "Wheelchair cab & 2-person transfer", "In-home lab, physio & medicine refills", "24/7 Emergency SOS & hospital triage"]),
    ("COMPLETE", "Complete Medical + Errands", 7500, 12500, ["4 weekly home visits (vitals)", "Doctor appointment & hospital escort", "Monthly medicine refills & Health Vault", "24/7 Emergency SOS coordination"]),
    ("COUPLE", "Comprehensive / Couple Care", 14000, 22000, ["Weekly visits for both parents/spouses", "Priority hospital escort & lab collection", "Quarterly property inspection", "Dedicated Senior Care Manager (Sahayak)"]),
]

cols = st.columns(2)
for idx, (tier, name, min_inr, max_inr, highlights) in enumerate(plans):
    with cols[idx % 2], st.container(border=True):
        st.markdown(f"### {name}")
        st.info(f"**{format_currency(min_inr, curr)} – {format_currency(max_inr, curr)} / mo**")
        for item in highlights:
            st.write(f"- {item}")
        if st.button(f"Select {tier} Plan", key=f"sub_{tier}", use_container_width=True):
            if st.session_state.get("authenticated") and user.get("id"):
                db.update_wallet_plan(user["id"], tier)
                st.session_state["demo_wallet"]["plan_tier"] = tier
                st.success(f"Switched active subscription tier to **{tier}**!")
            else:
                st.warning("Sign in from the Home page to activate this subscription.")

st.divider()

# Pay-As-You-Go On-Demand Rates
st.subheader("Pay-As-You-Go On-Demand Services")
ondemand_services = [
    ("Wheelchair-Assisted Hospital / Doctor Escort (up to 4 hrs)", 1200, 2800),
    ("In-Home Medical Support (Lab Sample, Physio / Nursing Setup)", 800, 1800),
    ("Routine Home Wellbeing & Vitals Check", 600, 1200),
    ("Doorstep Bank, Government, or Pension Life Certificate", 1000, 2000),
    ("Assisted Social / Temple Outing (excl. wheelchair cab)", 1000, 2200),
    ("Airport Pickup / Drop Assistance (excl. cab/toll)", 1500, 3500),
    ("Property / Locked Flat Inspection with Video", 1500, 3000),
]

for service_name, low_inr, high_inr in ondemand_services:
    c1, c2 = st.columns([3, 2])
    c1.write(f"**{service_name}**")
    c2.write(f"{format_currency(low_inr, curr)} – {format_currency(high_inr, curr)}")
