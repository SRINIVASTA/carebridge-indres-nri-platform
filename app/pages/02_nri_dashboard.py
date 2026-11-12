from datetime import datetime
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from app.auth.session_manager import require_role
from app.services.database import DatabaseService
from app.services.notifications import NotificationDispatcher
from app.services.payments import PaymentGatewayService
from app.services.pdf_generator import generate_invoice_pdf
from app.services.storage import VaultStorageService
from app.utils.currency import calculate_invoice_totals, convert_from_inr, format_currency
from app.utils.validators import validate_indian_phone

st.set_page_config(page_title="NRI Family Dashboard — CareBridge", page_icon="🏠", layout="wide")
user = require_role(["NRI", "ADMIN"])
curr = st.session_state.get("currency", user.get("preferred_currency", "USD"))

db = DatabaseService()
storage = VaultStorageService()
notifier = NotificationDispatcher()
payments = PaymentGatewayService()

parents = db.get_parents_for_nri(user["id"])
wallet = db.get_wallet(user["id"])
tasks = db.list_tasks("NRI", user["id"])

st.title("NRI Family Care & Concierge Dashboard")

# Top KPI Summary + Emergency SOS
k1, k2, k3 = st.columns([2, 2, 1.5])
with k1:
    st.metric("Prepaid INR Expense Wallet", format_currency(float(wallet.get("balance_inr", 0)), curr))
with k2:
    st.metric("Active Care Plan", wallet.get("plan_tier", "PAY_AS_YOU_GO"))
with k3:
    if st.button("🚨 TRIGGER 24/7 EMERGENCY SOS", type="primary", use_container_width=True):
        target_parent = parents[0] if parents else {"id": "par-01", "full_name": "Parent", "city": "India"}
        sos_task = {
            "nri_user_id": user["id"],
            "parent_id": target_parent["id"],
            "parent_name": target_parent["full_name"],
            "care_manager_id": "usr-cm-201",
            "category": "EMERGENCY_SOS",
            "title": f"EMERGENCY SOS — {target_parent['full_name']}",
            "instructions": "Immediate ambulance & hospital triage dispatch requested by NRI family.",
            "scheduled_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "status": "SOS_ACTIVE",
            "service_fee_inr": 0.0,
            "out_of_pocket_inr": 0.0,
        }
        db.create_task(sos_task)
        channels = notifier.dispatch_to_available_channels(
            recipient=user,
            subject="URGENT: CareBridge 24/7 SOS Activated",
            summary_text=f"Emergency dispatch triggered for {target_parent['full_name']} in {target_parent['city']}. Sahayak team alerted.",
        )
        st.error(
            f"SOS Alert Dispatched! Ground response team notified. Confirmation sent via: "
            f"{', '.join(channels) if channels else 'In-App Priority Queue'}."
        )

# Add Parent Expander (Auto-expanded if a newly registered NRI has 0 parents)
with st.expander("👨‍👩‍👧 Register / Add Parent Profile in India", expanded=(len(parents) == 0)):
    with st.form("add_parent_form"):
        p1, p2, p3 = st.columns([2, 1, 1.5])
        p_name = p1.text_input("Parent's Full Name *", placeholder="e.g., Sri Venkata Subba Rao")
        p_age = p2.number_input("Age *", min_value=45, max_value=120, value=70)
        p_city = p3.text_input("City in India *", placeholder="e.g., Visakhapatnam / Hyderabad")

        p_address = st.text_input("Complete Residential Address *", placeholder="Flat/House No., Street, Landmark, PIN")

        p4, p5, p6 = st.columns([1, 1.5, 2])
        p_blood = p4.selectbox("Blood Group", ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-", "Unknown"])
        p_phone = p5.text_input("Parent / Local Emergency Phone (+91)", placeholder="+919848012345")
        p_cond = p6.text_input("Known Medical Conditions", placeholder="e.g., Hypertension, Diabetes")

        if st.form_submit_button("Save Parent Profile", type="primary"):
            if not p_name.strip() or not p_city.strip() or not p_address.strip():
                st.error("Parent name, city, and residential address are required.")
            else:
                fmt_in_phone = p_phone.strip()
                if fmt_in_phone:
                    ok_in, res_phone = validate_indian_phone(fmt_in_phone)
                    if not ok_in:
                        st.error(res_phone)
                        st.stop()
                    fmt_in_phone = res_phone

                db.add_parent(
                    {
                        "nri_user_id": user["id"],
                        "full_name": p_name.strip(),
                        "age": p_age,
                        "city": p_city.strip(),
                        "address": p_address.strip(),
                        "blood_group": p_blood,
                        "emergency_contact_india": fmt_in_phone,
                        "medical_conditions": p_cond.strip(),
                    }
                )
                st.success(f"Added **{p_name.strip()}** to your family care profile!")
                st.rerun()

st.divider()

tab_book, tab_invoices, tab_wallet = st.tabs(
    ["Schedule Care / Errand", "Invoices & PDF Reports (Download & Send)", "Top Up Prepaid Wallet"]
)
# TAB 1: Schedule a Task
with tab_book:
    st.subheader("Book Medical Escort, Vitals Check, or Concierge Errand")
    if not parents:
        st.warning("Please register at least one parent profile above before booking a care visit.")
    else:
        with st.form("schedule_task_form"):
            parent_map = {f"{p['full_name']} ({p['city']})": p for p in parents}
            selected_label = st.selectbox("Select Parent", list(parent_map.keys()))
            category = st.selectbox(
                "Service Category",
                [
                    "MEDICAL_ESCORT",
                    "VITALS_CHECK",
                    "BANK_GOV_ERRAND",
                    "AIRPORT_ASSIST",
                    "PROPERTY_CHECK",
                ],
            )
            title = st.text_input("Task Title", placeholder="e.g., Quarterly Eye Checkup at LV Prasad Eye Institute")
            instructions = st.text_area(
                "Detailed Instructions for Care Manager (Sahayak)",
                placeholder="Carry previous prescription folder; arrange wheelchair at entrance.",
            )
            col_d, col_t, col_fee = st.columns(3)
            visit_date = col_d.date_input("Preferred Date")
            visit_time = col_t.time_input("Preferred Time")
            est_fee_inr = col_fee.number_input("Estimated Service Fee (INR)", min_value=500.0, max_value=10000.0, value=1200.0, step=100.0)

            if st.form_submit_button("Confirm & Assign Care Manager", type="primary"):
                chosen_parent = parent_map[selected_label]
                new_task = {
                    "nri_user_id": user["id"],
                    "parent_id": chosen_parent["id"],
                    "parent_name": chosen_parent["full_name"],
                    "care_manager_id": "usr-cm-201",
                    "category": category,
                    "title": title or f"{category.replace('_', ' ').title()} Visit",
                    "instructions": instructions,
                    "scheduled_at": f"{visit_date} {visit_time}",
                    "status": "ASSIGNED",
                    "service_fee_inr": est_fee_inr,
                    "out_of_pocket_inr": 0.0,
                }
                db.create_task(new_task)
                st.success("Care task booked and assigned to Senior Care Manager (Ravi Kumar)!")
                st.rerun()

    st.markdown("### Recent & Active Care Tasks")
    for t in tasks:
        with st.expander(f"[{t['status']}] {t['title']} — {t.get('parent_name', '')} ({t['scheduled_at']})"):
            st.write(f"**Instructions:** {t.get('instructions', 'N/A')}")
            st.write(
                f"**Service Fee:** {format_currency(float(t.get('service_fee_inr', 0)), curr)} | "
                f"**Out-of-Pocket Actuals:** {format_currency(float(t.get('out_of_pocket_inr', 0)), curr)}"
            )
            if t.get("completion_notes"):
                st.info(f"**Sahayak Visit Note:** {t['completion_notes']}")
# TAB 2: Generate, Download & Dispatch PDF Invoices
with tab_invoices:
    st.subheader("Itemized PDF Invoices & Multi-Channel Delivery")
    st.caption(
        f"Available communication channels for **{user['full_name']}**: "
        f"`{', '.join(user.get('preferred_channels', ['EMAIL', 'WHATSAPP']))}` "
        f"(Email: `{user.get('email')}`, Phone/WA: `{user.get('phone')}`)"
    )

    if not tasks:
        st.info("No tasks available to invoice yet.")
    else:
        task_options = {f"{t['id']} — {t['title']} ({t['status']})": t for t in tasks}
        chosen_task_key = st.selectbox("Select Care Visit / Task for Invoice PDF", list(task_options.keys()))
        sel_task = task_options[chosen_task_key]

        fallback_parent = {"full_name": sel_task.get("parent_name", "Parent"), "city": "India"}
        parent_obj = next((p for p in parents if p["id"] == sel_task["parent_id"]), fallback_parent)
        svc_fee = float(sel_task.get("service_fee_inr", 1200.0))
        oop_amt = float(sel_task.get("out_of_pocket_inr", 0.0))

        line_items = [
            {
                "description": f"{sel_task['title']} (CareBridge Concierge Fee)",
                "category": sel_task["category"],
                "amount_inr": svc_fee,
            }
        ]
        if oop_amt > 0:
            line_items.append(
                {
                    "description": "Verified Pharmacy / Lab / Transport Actuals (Receipt Attached)",
                    "category": "ACTUALS_0_GST",
                    "amount_inr": oop_amt,
                }
            )

        invoice_num = f"CB-INV-{sel_task['id'].replace('TSK-', '')}"
        pdf_bytes = generate_invoice_pdf(
            invoice_number=invoice_num,
            nri_name=user["full_name"],
            nri_email=user["email"],
            parent_name=parent_obj["full_name"],
            parent_city=parent_obj["city"],
            currency=curr,
            line_items=line_items,
            service_fee_inr=svc_fee,
            out_of_pocket_inr=oop_amt,
        )

        totals = calculate_invoice_totals(svc_fee, oop_amt)
        st.write(
            f"**Invoice Total:** {format_currency(totals['total_inr'], curr)} "
            f"(includes ₹{totals['gst_inr']:,.2f} GST on service fee; ₹{oop_amt:,.2f} pass-through actuals)"
        )

        col_dl, col_send = st.columns(2)
        with col_dl:
            st.download_button(
                label="⬇️ Download Itemized PDF Invoice",
                data=pdf_bytes,
                file_name=f"{invoice_num}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        with col_send:
            if st.button("📤 Send PDF Invoice to Available Channels", type="primary", use_container_width=True):
                stored_path = storage.upload_file(pdf_bytes, "invoices", f"{invoice_num}.pdf")
                signed_url = storage.get_signed_download_url(stored_path or "")
                summary_msg = (
                    f"Invoice {invoice_num} for {parent_obj['full_name']} ({sel_task['title']}): "
                    f"Total {format_currency(totals['total_inr'], curr)}."
                )
                dispatched = notifier.dispatch_to_available_channels(
                    recipient=user,
                    subject=f"CareBridge India Invoice {invoice_num}",
                    summary_text=summary_msg,
                    pdf_bytes=pdf_bytes,
                    pdf_filename=f"{invoice_num}.pdf",
                    signed_pdf_url=signed_url,
                )
                db.save_invoice(
                    {
                        "invoice_number": invoice_num,
                        "nri_user_id": user["id"],
                        "task_id": sel_task["id"],
                        "currency": curr,
                        "service_fee_inr": svc_fee,
                        "out_of_pocket_inr": oop_amt,
                        "gst_inr": totals["gst_inr"],
                        "total_inr": totals["total_inr"],
                        "total_converted": convert_from_inr(totals["total_inr"], curr),
                        "pdf_storage_path": stored_path,
                        "status": "PAID",
                        "dispatched_channels": dispatched,
                    }
                )
                if dispatched:
                    st.success(f"Invoice PDF sent via: **{', '.join(dispatched)}**!")
                else:
                    st.warning(
                        "Invoice archived in vault! Configure SMTP/Twilio keys in `.streamlit/secrets.toml` "
                        "to enable live Email/WhatsApp/SMS delivery."
                    )

# TAB 3: Prepaid Wallet Top-Up
with tab_wallet:
    st.subheader("Top Up Prepaid Expense Wallet")
    st.write("Used strictly for verified out-of-pocket medical, lab, and utility actuals.")
    topup_inr = st.number_input("Top-Up Amount (INR)", min_value=1000.0, max_value=100000.0, value=5000.0, step=1000.0)
    gateway = st.radio(
        "Payment Gateway",
        ["Stripe (International USD/GBP/EUR Card)", "Razorpay (Indian UPI / NetBanking / Card)"],
        horizontal=True,
    )
    if st.button("Add Funds to Prepaid Wallet", type="primary"):
        if "Stripe" in gateway:
            amt_foreign = convert_from_inr(topup_inr, curr if curr != "INR" else "USD")
            res = payments.create_stripe_payment_intent(
                amt_foreign, curr if curr != "INR" else "USD", {"nri_user_id": user["id"]}
            )
        else:
            res = payments.create_razorpay_order(topup_inr, f"topup_{user['id']}")
        new_bal = db.update_wallet_balance(user["id"], topup_inr)
        st.success(
            f"Added ₹{topup_inr:,.2f} via {res['provider']} (Ref: `{res['id']}`). "
            f"New Wallet Balance: **{format_currency(new_bal, curr)}**"
        )
