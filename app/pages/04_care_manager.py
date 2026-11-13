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
from app.utils.datetime_helper import now_ist_str
from app.utils.validators import is_allowed_file

user = require_role(["CARE_MANAGER", "ADMIN"])

db = DatabaseService()
storage = VaultStorageService()
notifier = NotificationDispatcher()

st.title("Care Manager (Sahayak) Field Operations Portal")
st.caption(
    f"Logged in as **{user['full_name']}** | Current IST: `{now_ist_str()}` | "
    f"Police ID: `{user.get('police_clearance_id', 'VERIFIED')}`"
)

tasks = (
    db.list_tasks("CARE_MANAGER", user["id"])
    if user["role"] == "CARE_MANAGER"
    else db.list_tasks("ADMIN", user["id"])
)
all_parents = [
    {**p, "id": p["parent_id"], "full_name": p["parent_name"]}
    for p in db.list_all_parents_with_nri()
]
all_users_by_id = {u["id"]: u for u in db.list_all_users()}

if not tasks:
    st.info("No assigned field tasks right now.")
    st.stop()

task_map = {f"{t['id']} — {t['title']} ({t['scheduled_at']}) [{t['status']}]": t for t in tasks}
selected_label = st.selectbox("Select Assigned Visit / Task", list(task_map.keys()))
task = task_map[selected_label]

parent = next(
    (p for p in all_parents if p["id"] == task["parent_id"]),
    {
        "id": task["parent_id"],
        "full_name": task.get("parent_name", "Care Recipient"),
        "age": 70,
        "city": "India",
        "address": "Registered Address",
        "mobility_level": "INDEPENDENT",
        "home_access_notes": "",
    },
)

# Resolve actual customer recipient (Indian Resident or NRI Sponsor)
customer_recipient = (
    all_users_by_id.get(task.get("nri_user_id"))
    or {
        "id": task.get("nri_user_id", DEMO_USERS["INDRES_NRI"]["id"]),
        "full_name": parent.get("nri_name", DEMO_USERS["INDRES_NRI"]["full_name"]),
        "email": parent.get("nri_email", DEMO_USERS["INDRES_NRI"]["email"]),
        "phone": parent.get("nri_phone", DEMO_USERS["INDRES_NRI"]["phone"]),
        "preferred_currency": "INR" if parent.get("customer_type") == "INDIAN_RESIDENT" else "USD",
        "preferred_channels": ["EMAIL", "WHATSAPP"],
    }
)

mobility_badge = str(parent.get("mobility_level", "INDEPENDENT")).replace("_", " ").title()
access_notes = parent.get("home_access_notes") or "Standard access"

st.info(
    f"**Beneficiary:** {parent['full_name']} ({parent['age']} yrs) | "
    f"**Mobility Status:** `{mobility_badge}`\n\n"
    f"**Address:** {parent['address']} | **Home Access Notes:** {access_notes}\n\n"
    f"**Task Instructions:** {task.get('instructions', 'Standard check-in')}"
)

# High-Visibility Mobility & Vendor Alerts for Ground Sahayak
mobility_alerts = []
if task.get("requires_wheelchair_cab"):
    mobility_alerts.append("♿ **Wheelchair-Accessible Cab / Ramp Vehicle Required**")
if task.get("requires_two_person_lift"):
    mobility_alerts.append("🧑‍🤝‍🧑 **2-Person Lift / Transfer Assistance Required**")
if task.get("third_party_vendor_type"):
    mobility_alerts.append(f"🩺 **Coordinate Specialist/Vendor:** {task['third_party_vendor_type']}")
if parent.get("mobility_level") in ("WHEELCHAIR_REQUIRED", "BEDRIDDEN", "POST_SURGERY_RECOVERY"):
    mobility_alerts.append(f"⚠️ **Recipient Mobility Level:** `{mobility_badge}` — Carry transfer belt / check ramp access")

if mobility_alerts:
    st.warning(" | ".join(mobility_alerts))
with st.form("field_visit_report_form"):
    st.subheader("1. Live GPS Check-In & Vitals Log")
    g1, g2 = st.columns(2)
    gps_lat = g1.number_input("GPS Latitude", value=17.3850, format="%.4f")
    gps_lng = g2.number_input("GPS Longitude", value=78.4867, format="%.4f")

    v1, v2, v3, v4 = st.columns(4)
    sys_bp = v1.number_input("Systolic BP (mmHg)", min_value=60, max_value=250, value=124)
    dia_bp = v2.number_input("Diastolic BP (mmHg)", min_value=40, max_value=150, value=78)
    sugar = v3.number_input("Blood Sugar (mg/dL)", min_value=30, max_value=600, value=114)
    pulse = v4.number_input("Pulse (bpm)", min_value=30, max_value=220, value=72)
    spo2 = st.slider("SpO2 Oxygen Saturation (%)", min_value=75, max_value=100, value=98)

    st.subheader("2. Out-of-Pocket Expense Receipt & Visit Summary")
    oop_inr = st.number_input(
        "Out-of-Pocket Expense Paid (INR — Medicines, Lab, Wheelchair Cab/Auto)",
        min_value=0.0,
        max_value=50000.0,
        value=float(task.get("out_of_pocket_inr", 0.0)),
        step=50.0,
    )
    no_bill_voucher = st.checkbox(
        "🧾 Unbilled Petty Cash / Auto / Parking Expense (No printed vendor receipt available — max ₹500)",
        value=False,
    )
    unbilled_reason = st.text_input(
        "Expense Breakdown / Route Note (Required if unbilled)",
        placeholder="e.g., To & fro local auto fare from home to bank branch (₹200)",
    )
    receipt_file = st.file_uploader(
        "Upload Printed Vendor Bill / Pharmacy / Cab Receipt (PDF/JPG/PNG)",
        type=["pdf", "jpg", "jpeg", "png"],
    )
    visit_notes = st.text_area(
        "Care Manager Field Observations",
        value=task.get("completion_notes")
        or "Beneficiary picked up from home, assisted safely, and dropped back home.",
    )
    auto_dispatch = st.checkbox(
        "Auto-generate Visit Report + Itemized Invoice PDFs and send to Member's available channels",
        value=True,
    )

    submitted = st.form_submit_button("✅ Complete Visit, Archive PDFs & Notify Member", type="primary")

    if submitted:
        if oop_inr > 0 and not receipt_file and not task.get("receipt_verified"):
            if not no_bill_voucher:
                st.error(
                    "Please upload a receipt photo/PDF, OR check 'Unbilled Petty Cash / Auto Expense' if no bill was issued."
                )
                st.stop()
            if oop_inr > 500:
                st.error("Unbilled cash expenses above ₹500 require a printed receipt or UPI screenshot.")
                st.stop()
            if not unbilled_reason.strip():
                st.error("Please enter the route/expense breakdown note for unbilled auto/cash expenses.")
                st.stop()

        checkin_ts = now_ist_str()
        receipt_path = task.get("receipt_url")
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
        elif oop_inr > 0 and no_bill_voucher:
            receipt_path = f"UNBILLED_VOUCHER: {unbilled_reason.strip()}"

        # Log vitals with full IST Date & Time
        vitals_payload = {
            "parent_id": parent["id"],
            "logged_by": user["id"],
            "systolic_bp": sys_bp,
            "diastolic_bp": dia_bp,
            "blood_sugar_mgdl": sugar,
            "pulse_bpm": pulse,
            "spo2_percent": spo2,
            "notes": visit_notes,
            "recorded_at": checkin_ts,
        }
        db.log_vitals(vitals_payload)

        # Persist task completion in SQLite3
        svc_fee = float(task.get("service_fee_inr", 1200.0))
        db.update_task_completion(
            task_id=task["id"],
            status="COMPLETED",
            gps_lat=gps_lat,
            gps_lng=gps_lng,
            service_fee_inr=svc_fee,
            out_of_pocket_inr=oop_inr,
            receipt_url=receipt_path,
            receipt_verified=bool(receipt_file or task.get("receipt_verified")),
            completion_notes=visit_notes,
        )

        # Generate Visit Summary PDF & Invoice PDF with IST Date & Time
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

        invoice_num = f"CB-INV-{task['id'].replace('TSK-', '')}"
        line_items = [
            {"description": task["title"], "category": task["category"], "amount_inr": svc_fee}
        ]
        if oop_inr > 0:
            line_items.append(
                {
                    "description": "Verified Vendor / Pharmacy / Wheelchair Cab Actuals (0% Markup)",
                    "category": "ACTUALS",
                    "amount_inr": oop_inr,
                }
            )

        cust_curr = customer_recipient.get("preferred_currency", "INR")
        invoice_pdf = generate_invoice_pdf(
            invoice_number=invoice_num,
            nri_name=customer_recipient["full_name"],
            nri_email=customer_recipient["email"],
            parent_name=parent["full_name"],
            parent_city=parent["city"],
            currency=cust_curr,
            line_items=line_items,
            service_fee_inr=svc_fee,
            out_of_pocket_inr=oop_inr,
            issued_at=checkin_ts,
        )

        storage.upload_file(visit_pdf, "visit_reports", f"{task['id']}_report.pdf")
        inv_path = storage.upload_file(invoice_pdf, "invoices", f"{invoice_num}.pdf")
        totals = calculate_invoice_totals(svc_fee, oop_inr)

        db.save_invoice(
            {
                "invoice_number": invoice_num,
                "nri_user_id": task.get("nri_user_id", customer_recipient["id"]),
                "task_id": task["id"],
                "currency": cust_curr,
                "service_fee_inr": svc_fee,
                "out_of_pocket_inr": oop_inr,
                "gst_inr": totals["gst_inr"],
                "total_inr": totals["total_inr"],
                "total_converted": convert_from_inr(totals["total_inr"], cust_curr),
                "pdf_storage_path": inv_path,
                "status": "ISSUED",
                "created_at": checkin_ts,
            }
        )

        st.session_state["last_visit_pdf"] = visit_pdf
        st.session_state["last_invoice_pdf"] = invoice_pdf
        st.session_state["last_invoice_num"] = invoice_num

        if auto_dispatch:
            signed_inv_url = storage.get_signed_download_url(inv_path or "")
            sent_channels = notifier.dispatch_to_available_channels(
                recipient=customer_recipient,
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
                f"Visit completed at **{checkin_ts}**! Dispatched PDFs via: "
                f"**{', '.join(sent_channels) if sent_channels else 'Vault & Ready for Download'}**."
            )
        else:
            st.success(f"Visit report and invoice PDFs generated at **{checkin_ts}** and stored in vault!")

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
