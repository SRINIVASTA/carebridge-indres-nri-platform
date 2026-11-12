from datetime import datetime
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from app.auth.session_manager import DEMO_USERS, require_role
from app.services.database import DatabaseService
from app.services.notifications import NotificationDispatcher
from app.services.pdf_generator import generate_invoice_pdf, generate_visit_vitals_report_pdf
from app.services.storage import VaultStorageService
from app.utils.currency import calculate_invoice_totals, convert_from_inr
from app.utils.validators import is_allowed_file

st.set_page_config(page_title="Care Manager Field Portal — CareBridge", page_icon="🛵", layout="wide")
user = require_role(["CARE_MANAGER", "ADMIN"])

db = DatabaseService()
storage = VaultStorageService()
notifier = NotificationDispatcher()

st.title("Care Manager (Sahayak) Field Operations Portal")
st.caption(
    f"Logged in as **{user['full_name']}** | Police Verification ID: `{user.get('police_clearance_id', 'VERIFIED')}`"
)

tasks = db.list_tasks("CARE_MANAGER", user["id"])
parents = db.get_parents_for_nri("usr-nri-101")
nri_recipient = DEMO_USERS["NRI"]

if not tasks:
    st.info("No assigned field tasks right now.")
    st.stop()

task_map = {f"{t['id']} — {t['title']} [{t['status']}]": t for t in tasks}
selected_label = st.selectbox("Select Assigned Visit / Task", list(task_map.keys()))
task = task_map[selected_label]
parent = next((p for p in parents if p["id"] == task["parent_id"]), parents[0])

st.info(
    f"**Beneficiary:** {parent['full_name']} ({parent['age']} yrs) | "
    f"**Address:** {parent['address']} | "
    f"**Instructions:** {task.get('instructions', 'Standard check-in')}"
)

with st.form("field_visit_report_form"):
    st.subheader("1. Live GPS Check-In & Vitals Log")
    g1, g2 = st.columns(2)
    gps_lat = g1.number_input("GPS Latitude", value=17.7412, format="%.4f")
    gps_lng = g2.number_input("GPS Longitude", value=83.3341, format="%.4f")

    v1, v2, v3, v4 = st.columns(4)
    sys_bp = v1.number_input("Systolic BP (mmHg)", min_value=60, max_value=250, value=124)
    dia_bp = v2.number_input("Diastolic BP (mmHg)", min_value=40, max_value=150, value=78)
    sugar = v3.number_input("Blood Sugar (mg/dL)", min_value=30, max_value=600, value=114)
    pulse = v4.number_input("Pulse (bpm)", min_value=30, max_value=220, value=72)
    spo2 = st.slider("SpO2 Oxygen Saturation (%)", min_value=75, max_value=100, value=98)

    st.subheader("2. Out-of-Pocket Expense Receipt & Visit Summary")
    oop_inr = st.number_input(
        "Out-of-Pocket Expense Paid (INR — Medicines, Lab, Auto/Cab)",
        min_value=0.0,
        max_value=50000.0,
        value=float(task.get("out_of_pocket_inr", 0.0)),
        step=50.0,
    )
    receipt_file = st.file_uploader(
        "Upload Mandatory Vendor Bill / Pharmacy Receipt (PDF/JPG/PNG)",
        type=["pdf", "jpg", "jpeg", "png"],
    )
    visit_notes = st.text_area(
        "Care Manager Field Observations",
        value=task.get("completion_notes", "Parent is cheerful and active. Vitals logged and medicines handed over."),
    )
    auto_dispatch = st.checkbox(
        "Auto-generate Visit Report + Itemized Invoice PDFs and send to NRI's available channels",
        value=True,
    )

    submitted = st.form_submit_button("✅ Complete Visit, Archive PDFs & Notify NRI Family", type="primary")

    if submitted:
        if oop_inr > 0 and not receipt_file and not task.get("receipt_verified"):
            st.error("Receipt photo/PDF is mandatory whenever out-of-pocket expenses are greater than ₹0.")
            st.stop()

        checkin_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        receipt_path = None
        if receipt_file:
            if not is_allowed_file(receipt_file.name):
                st.error("Invalid receipt file type.")
                st.stop()
            receipt_path = storage.upload_file(
                receipt_file.getvalue(),
                f"receipts/{task['id']}",
                receipt_file.name,
                receipt_file.type or "application/octet-stream",
            )

        # Log vitals to Health Vault
        vitals_payload = {
            "parent_id": parent["id"],
            "logged_by": user["id"],
            "systolic_bp": sys_bp,
            "diastolic_bp": dia_bp,
            "blood_sugar_mgdl": sugar,
            "pulse_bpm": pulse,
            "spo2_percent": spo2,
            "notes": visit_notes,
            "recorded_at": datetime.utcnow().strftime("%Y-%m-%d"),
        }
        db.log_vitals(vitals_payload)

        # Update task state
        task.update(
            {
                "status": "COMPLETED",
                "gps_lat": gps_lat,
                "gps_lng": gps_lng,
                "checkin_time": checkin_ts,
                "out_of_pocket_inr": oop_inr,
                "receipt_url": receipt_path,
                "receipt_verified": True if receipt_file else False,
                "completion_notes": visit_notes,
            }
        )

        # Generate Visit Summary PDF & Invoice PDF
        visit_pdf = generate_visit_vitals_report_pdf(
            parent_name=parent["full_name"],
            parent_city=parent["city"],
            care_manager_name=user["full_name"],
            visit_title=task["title"],
            checkin_time=checkin_ts,
            gps_coords=f"{gps_lat}, {gps_lng}",
            vitals=vitals_payload,
            notes=visit_notes,
        )

        svc_fee = float(task.get("service_fee_inr", 1200.0))
        invoice_num = f"CB-INV-{task['id'].replace('TSK-', '')}"
        line_items = [
            {"description": task["title"], "category": task["category"], "amount_inr": svc_fee}
        ]
        if oop_inr > 0:
            line_items.append(
                {
                    "description": "Verified Vendor Receipt Actuals (0% Markup)",
                    "category": "ACTUALS",
                    "amount_inr": oop_inr,
                }
            )

        nri_curr = nri_recipient.get("preferred_currency", "USD")
        invoice_pdf = generate_invoice_pdf(
            invoice_number=invoice_num,
            nri_name=nri_recipient["full_name"],
            nri_email=nri_recipient["email"],
            parent_name=parent["full_name"],
            parent_city=parent["city"],
            currency=nri_curr,
            line_items=line_items,
            service_fee_inr=svc_fee,
            out_of_pocket_inr=oop_inr,
        )

        visit_path = storage.upload_file(visit_pdf, "visit_reports", f"{task['id']}_report.pdf")
        inv_path = storage.upload_file(invoice_pdf, "invoices", f"{invoice_num}.pdf")
        totals = calculate_invoice_totals(svc_fee, oop_inr)

        db.save_invoice(
            {
                "invoice_number": invoice_num,
                "nri_user_id": nri_recipient["id"],
                "task_id": task["id"],
                "currency": nri_curr,
                "service_fee_inr": svc_fee,
                "out_of_pocket_inr": oop_inr,
                "gst_inr": totals["gst_inr"],
                "total_inr": totals["total_inr"],
                "total_converted": convert_from_inr(totals["total_inr"], nri_curr),
                "pdf_storage_path": inv_path,
                "status": "ISSUED",
            }
        )

        st.session_state["last_visit_pdf"] = visit_pdf
        st.session_state["last_invoice_pdf"] = invoice_pdf
        st.session_state["last_invoice_num"] = invoice_num

        if auto_dispatch:
            signed_inv_url = storage.get_signed_download_url(inv_path or "")
            sent_channels = notifier.dispatch_to_available_channels(
                recipient=nri_recipient,
                subject=f"CareBridge Visit Report & Invoice ({invoice_num}) — {parent['full_name']}",
                summary_text=(
                    f"Visit '{task['title']}' completed at {checkin_ts}. "
                    f"BP: {sys_bp}/{dia_bp} mmHg, Sugar: {sugar} mg/dL. "
                    f"Total Invoice: INR {totals['total_inr']:,.2f}."
                ),
                pdf_bytes=invoice_pdf,
                pdf_filename=f"{invoice_num}.pdf",
                signed_pdf_url=signed_inv_url,
            )
            st.success(
                f"Visit completed & archived! Dispatched PDFs via: "
                f"**{', '.join(sent_channels) if sent_channels else 'Vault & Ready for Download'}**."
            )
        else:
            st.success("Visit report and invoice PDFs generated and stored in vault!")

# Direct Download Buttons after Submission
if "last_visit_pdf" in st.session_state:
    d1, d2 = st.columns(2)
    d1.download_button(
        "⬇️ Download Visit & Vitals Summary PDF",
        data=st.session_state["last_visit_pdf"],
        file_name=f"{task['id']}_Visit_Report.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
    d2.download_button(
        "⬇️ Download Itemized Tax Invoice PDF",
        data=st.session_state["last_invoice_pdf"],
        file_name=f"{st.session_state.get('last_invoice_num', 'Invoice')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
