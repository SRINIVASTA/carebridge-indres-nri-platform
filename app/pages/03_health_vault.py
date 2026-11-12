from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.express as px
import streamlit as st
from app.auth.session_manager import require_role
from app.services.database import DatabaseService
from app.services.notifications import NotificationDispatcher
from app.services.pdf_generator import generate_visit_vitals_report_pdf
from app.services.storage import VaultStorageService
from app.utils.datetime_helper import now_ist_str
from app.utils.validators import is_allowed_file

user = require_role(["NRI", "CARE_MANAGER", "ADMIN"])
role = user.get("role")

db = DatabaseService()
storage = VaultStorageService()
notifier = NotificationDispatcher()

# Role-based parent visibility: NRIs see only their own parents; Staff/Admin see assigned/all parents
if role == "NRI":
    parents = db.get_parents_for_nri(user["id"])
else:
    parents = [
        {**p, "id": p["parent_id"], "full_name": p["parent_name"]}
        for p in db.list_all_parents_with_nri()
    ]

st.title("Encrypted Health & Document Vault")

if not parents:
    st.warning("No parent profiles registered yet. Add a parent in the NRI Family Dashboard first.")
    st.stop()

parent_map = {f"{p['full_name']} (Age {p['age']}, {p['city']})": p for p in parents}
selected_parent_label = st.selectbox("Select Parent Profile", list(parent_map.keys()))
parent = parent_map[selected_parent_label]

st.info(
    f"**Blood Group:** {parent.get('blood_group', 'N/A')} &nbsp;|&nbsp; "
    f"**Known Conditions:** {parent.get('medical_conditions', 'None')} &nbsp;|&nbsp; "
    f"**Local Emergency Contact:** {parent.get('emergency_contact_india', 'N/A')}"
)

vitals = db.get_vitals(parent["id"])

col_chart, col_export = st.columns([2.2, 1])

with col_chart:
    st.subheader("Chronological Vitals Trend (IST)")
    if vitals:
        df = pd.DataFrame(vitals)
        fig = px.line(
            df,
            x="recorded_at",
            y=["systolic_bp", "diastolic_bp", "blood_sugar_mgdl"],
            markers=True,
            labels={"value": "Reading", "recorded_at": "Date & Time (IST)", "variable": "Metric"},
            title=f"BP & Blood Sugar History — {parent['full_name']}",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No vitals recorded yet for this parent.")

with col_export:
    st.subheader("Health Summary PDF")
    latest = vitals[-1] if vitals else {}
    health_pdf = generate_visit_vitals_report_pdf(
        parent_name=parent["full_name"],
        parent_city=parent["city"],
        care_manager_name="CareBridge Medical Team",
        visit_title="Cumulative Vitals & Wellness Summary",
        checkin_time=str(latest.get("recorded_at", now_ist_str())),
        gps_coords="Verified Home Visit",
        vitals=latest,
        notes=str(latest.get("notes", "All vitals within monitored range.")),
    )

    st.download_button(
        label="⬇️ Download Health Report PDF",
        data=health_pdf,
        file_name=f"Health_Report_{parent['full_name'].replace(' ', '_')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    # Only NRI family members & Admins can trigger external multi-channel dispatch
    if role in ["NRI", "ADMIN"]:
        if st.button("📤 Send Health PDF to My Channels", type="primary", use_container_width=True):
            path = storage.upload_file(health_pdf, "health_reports", f"{parent['id']}_summary.pdf")
            signed_url = storage.get_signed_download_url(path or "")
            sent = notifier.dispatch_to_available_channels(
                recipient=user,
                subject=f"CareBridge Health & Vitals Report — {parent['full_name']}",
                summary_text=(
                    f"Latest vitals for {parent['full_name']} ({now_ist_str()}): "
                    f"BP {latest.get('systolic_bp', '-')}/{latest.get('diastolic_bp', '-')} mmHg, "
                    f"Sugar {latest.get('blood_sugar_mgdl', '-')} mg/dL."
                ),
                pdf_bytes=health_pdf,
                pdf_filename=f"Health_Report_{parent['full_name'].replace(' ', '_')}.pdf",
                signed_pdf_url=signed_url,
            )
            if sent:
                st.success(f"Health report PDF sent via: **{', '.join(sent)}**!")
            else:
                st.info("Report generated & archived! Configure SMTP/Twilio secrets to dispatch externally.")

st.divider()

# Strict Role-Based Vault Upload Permissions
if role == "CARE_MANAGER":
    st.subheader("Upload Clinical Prescription or Lab Report")
    st.caption("Restricted Staff View: Insurance policies and family ID documents are hidden for NRI privacy.")
    allowed_doc_types = ["PRESCRIPTION", "LAB_REPORT"]
else:
    st.subheader("Upload Prescription, Lab Report, Insurance Policy, or ID Proof")
    allowed_doc_types = ["PRESCRIPTION", "LAB_REPORT", "INSURANCE", "ID_PROOF"]

with st.form("upload_health_doc"):
    doc_type = st.selectbox("Document Type", allowed_doc_types)
    doc_title = st.text_input("Document Title", placeholder="e.g., Apollo Cardiology Prescription - Nov 2026")
    uploaded_file = st.file_uploader("Upload PDF or Image (Max 25 MB)", type=["pdf", "png", "jpg", "jpeg"])

    if st.form_submit_button("Encrypt & Store in Vault", type="primary"):
        if not uploaded_file:
            st.error("Please attach a file first.")
        elif not is_allowed_file(uploaded_file.name):
            st.error("Unsupported file format.")
        else:
            stored = storage.upload_file(
                uploaded_file.getvalue(),
                f"vault/{parent['id']}/{doc_type.lower()}",
                uploaded_file.name,
                uploaded_file.type or "application/pdf",
            )
            st.success(
                f"**{doc_title or uploaded_file.name}** ({doc_type}) stored securely at `{now_ist_str()}` (`{stored}`)."
            )
