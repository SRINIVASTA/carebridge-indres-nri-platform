from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st
from app.auth.session_manager import DEMO_USERS, require_role
from app.services.database import DatabaseService
from app.services.notifications import NotificationDispatcher
from app.services.pdf_generator import generate_invoice_pdf
from app.utils.currency import calculate_invoice_totals, format_currency
from app.utils.validators import mask_aadhaar

st.set_page_config(page_title="Admin Operations — CareBridge India", page_icon="🛡️", layout="wide")
admin = require_role(["ADMIN"])

db = DatabaseService()
notifier = NotificationDispatcher()

st.title("Admin Operations, Member Directory & Invoice Console")

tab_dir, tab_audit, tab_kyc, tab_billing = st.tabs(
    [
        "👥 Members, Parents & Staff Directory",
        "✅ Task & Actuals Audit",
        "🪪 Staff KYC & Police Clearance",
        "🧾 Invoice Ledger & Re-Send",
    ]
)

# TAB 1: Complete Directory of NRI Members, Linked Parents, and Staff
with tab_dir:
    st.subheader("Registered NRI Families & Linked Parents in India")
    parents_with_nri = db.list_all_parents_with_nri()
    if parents_with_nri:
        df_parents = pd.DataFrame(parents_with_nri)[
            [
                "parent_id",
                "parent_name",
                "age",
                "city",
                "blood_group",
                "medical_conditions",
                "emergency_contact_india",
                "nri_name",
                "nri_email",
                "nri_phone",
            ]
        ]
        st.dataframe(df_parents, use_container_width=True, hide_index=True)
    else:
        st.info("No parents registered yet.")

    st.divider()
    col_nri, col_staff = st.columns(2)

    with col_nri:
        st.subheader("All Registered NRI Members")
        nri_list = db.list_all_users("NRI")
        if nri_list:
            st.dataframe(
                pd.DataFrame(nri_list)[["id", "full_name", "email", "phone", "country", "preferred_currency"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Only built-in Demo NRI (`Arjun Sharma`) active. New signups will appear here.")

    with col_staff:
        st.subheader("All Care Managers (Sahayaks) & Admins")
        staff_list = db.list_all_users("CARE_MANAGER") + db.list_all_users("ADMIN")
        if staff_list:
            st.dataframe(
                pd.DataFrame(staff_list)[["id", "full_name", "role", "phone", "kyc_verified", "police_clearance_id"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Only built-in Demo Staff (`Ravi Kumar`, `Priya Nair`) active. New staff signups appear here.")

# TAB 2: Audit Tasks & Settle Prepaid Wallet Actuals
with tab_audit:
    st.subheader("Verify Field Receipts & Settle Wallet Deductions")
    all_tasks = db.list_tasks("ADMIN", admin["id"])
    for t in all_tasks:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1.5])
            c1.markdown(f"**{t['id']} — {t['title']}** (`{t['status']}`)")
            c1.caption(f"Parent: {t.get('parent_name', 'N/A')} | Scheduled: {t['scheduled_at']}")
            c2.write(f"Service Fee: ₹{float(t.get('service_fee_inr', 0)):,.2f}")
            c2.write(f"Out-of-Pocket: ₹{float(t.get('out_of_pocket_inr', 0)):,.2f}")

            if t.get("out_of_pocket_inr", 0) > 0 and not t.get("wallet_settled"):
                if c3.button("Approve & Deduct Wallet", key=f"settle_{t['id']}", type="primary"):
                    try:
                        new_bal = db.update_wallet_balance(
                            t["nri_user_id"], -float(t["out_of_pocket_inr"])
                        )
                        t["wallet_settled"] = True
                        t["receipt_verified"] = True
                        st.success(f"Settled ₹{t['out_of_pocket_inr']:,.2f}. Remaining NRI wallet: ₹{new_bal:,.2f}")
                    except ValueError as exc:
                        st.error(str(exc))
            else:
                c3.success("Verified / Settled" if t.get("wallet_settled") else "No Pending Actuals")
# TAB 3: Ground Staff KYC & Police Verification
with tab_kyc:
    st.subheader("Care Manager (Sahayak) Background & Police Clearance")
    registered_cms = db.list_all_users("CARE_MANAGER")
    staff_options = {f"{s['full_name']} ({s['email']})": s for s in registered_cms}
    if not staff_options:
        demo_cm = DEMO_USERS["CARE_MANAGER"]
        staff_options[f"{demo_cm['full_name']} (Demo)"] = demo_cm

    selected_staff_label = st.selectbox("Select Care Manager to Verify", list(staff_options.keys()))
    cm = staff_options[selected_staff_label]

    with st.form("kyc_verify_form"):
        staff_name = st.text_input("Care Manager Full Name", value=cm["full_name"])
        aadhaar_input = st.text_input("12-Digit Aadhaar Number (Stored Masked)", value="451288901234")
        police_id = st.text_input(
            "State Police Clearance Certificate ID",
            value=cm.get("police_clearance_id") or "AP-POL-VSP-88412",
        )
        kyc_ok = st.checkbox("Mark KYC & Police Background Check Verified", value=bool(cm.get("kyc_verified", True)))

        if st.form_submit_button("Save Verification Status", type="primary"):
            masked = mask_aadhaar(aadhaar_input)
            if masked == "INVALID-ID":
                st.error("Aadhaar number must contain exactly 12 digits.")
            else:
                if not cm["id"].startswith("usr-cm-201"):
                    db.verify_staff_kyc(cm["id"], police_id, kyc_ok)
                st.success(
                    f"Updated **{staff_name}** | Masked ID: `{masked}` | "
                    f"Police Clearance: `{police_id}` | Verified: `{kyc_ok}`"
                )

# TAB 4: Invoice Ledger & Multi-Channel Dispatch
with tab_billing:
    st.subheader("Issued Invoices — Download or Re-Dispatch to NRI")
    invoices = db.list_invoices()
    nri_user = DEMO_USERS["NRI"]

    if not invoices:
        st.info("No invoices logged yet. Complete a visit in Care Manager or generate one from NRI Dashboard.")
    else:
        for inv in invoices:
            with st.container(border=True):
                i1, i2, i3 = st.columns([3, 1.5, 1.5])
                i1.markdown(f"**{inv['invoice_number']}** (Task: `{inv.get('task_id', 'N/A')}`)")
                i1.caption(
                    f"Total: {format_currency(float(inv['total_inr']), inv.get('currency', 'USD'))} | "
                    f"Dispatched via: {', '.join(inv.get('dispatched_channels', [])) or 'Archived'}"
                )

                pdf_bytes = generate_invoice_pdf(
                    invoice_number=inv["invoice_number"],
                    nri_name=nri_user["full_name"],
                    nri_email=nri_user["email"],
                    parent_name="Dr. Raghavendra Sharma",
                    parent_city="Visakhapatnam",
                    currency=inv.get("currency", "USD"),
                    line_items=[
                        {
                            "description": f"CareBridge Care Service ({inv.get('task_id')})",
                            "category": "CARE_SERVICE",
                            "amount_inr": float(inv.get("service_fee_inr", 0)),
                        },
                        {
                            "description": "Out-of-Pocket Actuals (0% Markup)",
                            "category": "ACTUALS",
                            "amount_inr": float(inv.get("out_of_pocket_inr", 0)),
                        },
                    ],
                    service_fee_inr=float(inv.get("service_fee_inr", 0)),
                    out_of_pocket_inr=float(inv.get("out_of_pocket_inr", 0)),
                )

                i2.download_button(
                    "⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=f"{inv['invoice_number']}.pdf",
                    mime="application/pdf",
                    key=f"dl_{inv['invoice_number']}",
                )
                if i3.button("📤 Re-Send PDF", key=f"resend_{inv['invoice_number']}"):
                    totals = calculate_invoice_totals(
                        float(inv.get("service_fee_inr", 0)),
                        float(inv.get("out_of_pocket_inr", 0)),
                    )
                    channels = notifier.dispatch_to_available_channels(
                        recipient=nri_user,
                        subject=f"CareBridge India Tax Invoice {inv['invoice_number']}",
                        summary_text=f"Attached invoice {inv['invoice_number']} for INR {totals['total_inr']:,.2f}.",
                        pdf_bytes=pdf_bytes,
                        pdf_filename=f"{inv['invoice_number']}.pdf",
                    )
                    st.success(f"Dispatched via: {', '.join(channels) if channels else 'SMTP/Twilio not configured'}")
