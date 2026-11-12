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
from app.utils.validators import mask_aadhaar, validate_international_phone

admin = require_role(["ADMIN", "SYSTEM_ADMIN"])

db = DatabaseService()
notifier = NotificationDispatcher()

st.title("Admin Operations, Member Directory & Dispatch Console")

tab_dir, tab_audit, tab_kyc, tab_billing, tab_create_emp = st.tabs(
    [
        "👥 Members, Parents & Staff Directory",
        "🛵 Task Dispatch & Actuals Audit",
        "🪪 Staff KYC & Police Clearance",
        "🧾 Invoice Ledger & Re-Send",
        "➕ Create Employee Login",
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
        staff_list = (
            db.list_all_users("CARE_MANAGER")
            + db.list_all_users("ADMIN")
            + db.list_all_users("SYSTEM_ADMIN")
        )
        if staff_list:
            st.dataframe(
                pd.DataFrame(staff_list)[["id", "full_name", "role", "phone", "kyc_verified", "police_clearance_id"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Only built-in Demo Staff (`Ravi Kumar`, `Priya Nair`) active. New staff accounts appear here.")
# TAB 2: Assign Tasks to Care Managers & Settle Prepaid Wallet Actuals
with tab_audit:
    st.subheader("Assign Care Managers (Sahayaks) & Audit Out-of-Pocket Receipts")

    # Build available Care Manager pool (registered staff + built-in demo Sahayak)
    cm_pool = db.list_all_users("CARE_MANAGER")
    demo_cm = DEMO_USERS["CARE_MANAGER"]
    if not any(c["id"] == demo_cm["id"] for c in cm_pool):
        cm_pool.append(demo_cm)
    cm_map = {f"{c['full_name']} ({c['phone']})": c for c in cm_pool}
    cm_labels = list(cm_map.keys())

    all_tasks = db.list_tasks("ADMIN", admin["id"])
    if not all_tasks:
        st.info("No tasks booked yet.")
    else:
        for t in all_tasks:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2.8, 2.2, 1.8])
                c1.markdown(f"**{t['id']} — {t['title']}** (`{t['status']}`)")
                c1.caption(
                    f"Parent: {t.get('parent_name', 'N/A')} | Scheduled: {t['scheduled_at']} | "
                    f"Assigned ID: `{t.get('care_manager_id', 'Unassigned')}`"
                )

                # Care Manager Assignment Selector
                current_idx = next(
                    (i for i, c in enumerate(cm_pool) if c["id"] == t.get("care_manager_id")), 0
                )
                chosen_cm_label = c2.selectbox(
                    "Assign Sahayak",
                    cm_labels,
                    index=current_idx,
                    key=f"cm_sel_{t['id']}",
                    label_visibility="collapsed",
                )
                if c2.button("Assign & Alert Sahayak", key=f"assign_btn_{t['id']}", use_container_width=True):
                    chosen_cm = cm_map[chosen_cm_label]
                    db.assign_task_to_staff(t["id"], chosen_cm["id"])
                    notifier.dispatch_to_available_channels(
                        recipient=chosen_cm,
                        subject=f"New CareBridge Assignment: {t['id']}",
                        summary_text=(
                            f"Task '{t['title']}' for {t.get('parent_name', 'Parent')} "
                            f"scheduled at {t['scheduled_at']} has been assigned to you."
                        ),
                    )
                    st.success(f"Assigned **{t['id']}** to **{chosen_cm['full_name']}**!")
                    st.rerun()

                # Out-of-Pocket Wallet Settlement
                c3.write(
                    f"Fee: ₹{float(t.get('service_fee_inr', 0)):,.0f} | "
                    f"Actuals: ₹{float(t.get('out_of_pocket_inr', 0)):,.0f}"
                )
                if t.get("out_of_pocket_inr", 0) > 0 and not t.get("wallet_settled"):
                    if c3.button(
                        "Approve & Deduct Wallet",
                        key=f"settle_{t['id']}",
                        type="primary",
                        use_container_width=True,
                    ):
                        try:
                            new_bal = db.update_wallet_balance(
                                t["nri_user_id"], -float(t["out_of_pocket_inr"])
                            )
                            t["wallet_settled"] = True
                            t["receipt_verified"] = True
                            st.success(f"Settled ₹{t['out_of_pocket_inr']:,.2f}. Wallet: ₹{new_bal:,.2f}")
                        except ValueError as exc:
                            st.error(str(exc))
                else:
                    c3.caption("✅ Verified / No Pending Actuals")

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
        kyc_ok = st.checkbox(
            "Mark KYC & Police Background Check Verified", value=bool(cm.get("kyc_verified", False))
        )

        if st.form_submit_button("Save Verification Status", type="primary"):
            masked = mask_aadhaar(aadhaar_input)
            if masked == "INVALID-ID":
                st.error("Aadhaar number must contain exactly 12 digits.")
            else:
                if cm["id"].startswith("usr-cm-201"):
                    DEMO_USERS["CARE_MANAGER"]["police_clearance_id"] = police_id
                    DEMO_USERS["CARE_MANAGER"]["kyc_verified"] = kyc_ok
                else:
                    db.verify_staff_kyc(cm["id"], police_id, kyc_ok)

                st.session_state["last_kyc_msg"] = (
                    f"Updated **{staff_name}** | Masked ID: `{masked}` | "
                    f"Police Clearance: `{police_id}` | Verified: `{kyc_ok}`"
                )
                st.rerun()

    if st.session_state.get("last_kyc_msg"):
        st.success(st.session_state["last_kyc_msg"])

    # Live status table right inside Tab 3
    st.divider()
    st.markdown("#### Current Care Manager Verification Ledger")
    current_cms = db.list_all_users("CARE_MANAGER") or [DEMO_USERS["CARE_MANAGER"]]
    st.dataframe(
        pd.DataFrame(current_cms)[["id", "full_name", "phone", "kyc_verified", "police_clearance_id"]],
        use_container_width=True,
        hide_index=True,
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

# TAB 5: System Admin Employee Provisioning
with tab_create_emp:
    st.subheader("Provision New Employee Account & Access Rights")
    if admin.get("role") != "SYSTEM_ADMIN":
        st.warning("🔒 Restricted: Only the **System Admin** (`SYSTEM_ADMIN`) can create new employee logins.")
    else:
        st.caption(
            "Create login credentials for field Care Managers or Operations Admins. "
            "Employees sign in via the main Home / Sign In tab."
        )
        with st.form("sysadmin_create_emp_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            emp_name = c1.text_input("Employee Full Name *", placeholder="e.g., Suresh Naidu")
            emp_role = c2.selectbox(
                "Assign Role & Usage Rights *",
                ["CARE_MANAGER", "ADMIN"],
                format_func=lambda r: {
                    "CARE_MANAGER": "Care Manager / Sahayak (Field Portal + Health Vault)",
                    "ADMIN": "Operations Admin (Dispatch, KYC Audit, Billing & Portals)",
                }[r],
            )

            c3, c4 = st.columns(2)
            emp_email = c3.text_input("Employee Email (Login ID) *", placeholder="suresh@carebridge.in")
            emp_phone = c4.text_input("Mobile / WhatsApp (E.164) *", placeholder="+919848012345")

            c5, c6 = st.columns(2)
            emp_pw = c5.text_input("Temporary Password * (min 6 chars)", type="password")
            police_id = c6.text_input("Police Clearance ID (Optional)", placeholder="AP-POL-VSP-99102")

            if st.form_submit_button("Create Employee Login", type="primary", use_container_width=True):
                valid_phone, fmt_phone = validate_international_phone(emp_phone)
                if not emp_name.strip() or not emp_email.strip():
                    st.error("Employee name and email are required.")
                elif len(emp_pw) < 6:
                    st.error("Temporary password must be at least 6 characters.")
                elif not valid_phone:
                    st.error(fmt_phone)
                else:
                    try:
                        new_emp = db.register_user(
                            email=emp_email,
                            password=emp_pw,
                            full_name=emp_name,
                            role=emp_role,
                            phone=fmt_phone,
                            country="India",
                            preferred_currency="INR",
                            preferred_channels=["EMAIL", "WHATSAPP"],
                        )
                        if police_id.strip():
                            db.verify_staff_kyc(new_emp["id"], police_id.strip(), verified=True)
                        st.success(
                            f"✅ Created **{emp_role}** login for **{emp_name}** (`{emp_email}`). "
                            f"Share these credentials so they can sign in on the Home / Sign In screen."
                        )
                    except ValueError as exc:
                        st.error(str(exc))
