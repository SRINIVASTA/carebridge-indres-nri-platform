from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
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
        "👥 Residents, Families & Staff Directory",
        "🛵 Task Dispatch & Actuals Audit",
        "🪪 Staff KYC & Police Clearance",
        "🧾 Invoice Ledger & Re-Send",
        "➕ Manage Employees & History",
    ]
)

# TAB 1: Complete Directory of Indian Residents, NRI Families, and Staff
with tab_dir:
    st.subheader("Registered Care Recipients (Indian Residents & NRI-Sponsored Parents)")
    parents_with_nri = db.list_all_parents_with_nri()
    if parents_with_nri:
        df_parents = pd.DataFrame(parents_with_nri)[
            [
                "parent_id",
                "parent_name",
                "customer_type",
                "age",
                "city",
                "mobility_level",
                "home_access_notes",
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
        st.info("No care recipients registered yet.")

    st.divider()
    col_nri, col_staff = st.columns(2)

    with col_nri:
        st.subheader("All Registered Customers (Indian Residents & NRIs)")
        customer_list = db.list_all_users("INDRES_NRI")
        if customer_list:
            st.dataframe(
                pd.DataFrame(customer_list)[
                    ["id", "full_name", "customer_type", "email", "phone", "country", "preferred_currency"]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Only built-in Demo Customers active. New signups will appear here.")

    with col_staff:
        st.subheader("All Care Managers (Sahayaks) & Admins")
        staff_list = (
            db.list_all_users("CARE_MANAGER")
            + db.list_all_users("ADMIN")
            + db.list_all_users("SYSTEM_ADMIN")
        )
        if staff_list:
            st.dataframe(
                pd.DataFrame(staff_list)[
                    ["id", "full_name", "role", "phone", "kyc_verified", "police_clearance_id"]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No staff accounts found.")
# TAB 2: Assign Tasks to Care Managers & Settle Prepaid Wallet Actuals
with tab_audit:
    st.subheader("Assign Care Managers (Sahayaks) & Audit Out-of-Pocket Receipts")

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

                mobility_tags = []
                if t.get("requires_wheelchair_cab"):
                    mobility_tags.append("♿ Wheelchair Cab")
                if t.get("requires_two_person_lift"):
                    mobility_tags.append("🧑‍🤝‍🧑 2-Person Lift")
                if t.get("third_party_vendor_type"):
                    mobility_tags.append(f"🩺 {t['third_party_vendor_type']}")
                tag_line = f" | {' • '.join(mobility_tags)}" if mobility_tags else ""

                c1.caption(
                    f"Recipient: {t.get('parent_name', 'N/A')} | Scheduled: {t['scheduled_at']} | "
                    f"Assigned ID: `{t.get('care_manager_id', 'Unassigned')}`{tag_line}"
                )

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
                            f"Task '{t['title']}' for {t.get('parent_name', 'Care Recipient')} "
                            f"scheduled at {t['scheduled_at']} has been assigned to you.{tag_line}"
                        ),
                    )
                    st.success(f"Assigned **{t['id']}** to **{chosen_cm['full_name']}**!")
                    st.rerun()

                c3.write(
                    f"Fee: ₹{float(t.get('service_fee_inr', 0)):,.0f} | "
                    f"Actuals: ₹{float(t.get('out_of_pocket_inr', 0)):,.0f}"
                )
                if t.get("out_of_pocket_inr", 0) > 0 and not t.get("receipt_verified"):
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
                            db.update_task_completion(
                                task_id=t["id"],
                                status=t.get("status", "COMPLETED"),
                                receipt_verified=True,
                            )
                            st.success(f"Settled ₹{t['out_of_pocket_inr']:,.2f}. Wallet: ₹{new_bal:,.2f}")
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                else:
                    c3.caption("✅ Verified / No Pending Actuals")
# TAB 3: Ground Staff KYC & Police Verification
with tab_kyc:
    st.subheader("Care Manager (Sahayak) Background & Police Clearance")
    registered_cms = db.list_all_users("CARE_MANAGER")
    if not registered_cms:
        st.info("No registered Care Managers yet. Create one in the **➕ Manage Employees & History** tab first.")
    else:
        staff_options = {f"{s['full_name']} ({s['email']})": s for s in registered_cms}
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
                    db.verify_staff_kyc(cm["id"], police_id, kyc_ok)
                    db.log_staff_action(
                        action="KYC_VERIFIED" if kyc_ok else "KYC_REVOKED",
                        target_user=cm,
                        performed_by=f"{admin['full_name']} ({admin['email']})",
                        details=f"Masked ID: {masked} | Police ID: {police_id} | Verified: {kyc_ok}",
                    )
                    st.session_state["last_kyc_msg"] = (
                        f"Updated **{staff_name}** | Masked ID: `{masked}` | "
                        f"Police Clearance: `{police_id}` | Verified: `{kyc_ok}`"
                    )
                    st.rerun()

        if st.session_state.get("last_kyc_msg"):
            st.success(st.session_state["last_kyc_msg"])

# TAB 4: Invoice Ledger & Multi-Channel Dispatch
with tab_billing:
    st.subheader("Issued Invoices — Download or Re-Dispatch to Customer")
    invoices = db.list_invoices()
    all_users_map = {u["id"]: u for u in db.list_all_users()}
    all_tasks_map = {t["id"]: t for t in db.list_tasks("ADMIN", admin["id"])}
    all_parents_map = {p["parent_id"]: p for p in db.list_all_parents_with_nri()}

    if not invoices:
        st.info("No invoices logged yet. Complete a visit in Care Manager or generate one from the Care Dashboard.")
    else:
        for inv in invoices:
            with st.container(border=True):
                i1, i2, i3 = st.columns([3, 1.5, 1.5])
                i1.markdown(f"**{inv['invoice_number']}** (Task: `{inv.get('task_id', 'N/A')}`)")
                i1.caption(
                    f"Total: {format_currency(float(inv['total_inr']), inv.get('currency', 'INR'))} | "
                    f"Dispatched via: {', '.join(inv.get('dispatched_channels', [])) or 'Archived'}"
                )

                cust_user = all_users_map.get(inv.get("nri_user_id")) or DEMO_USERS["INDRES_NRI"]
                linked_task = all_tasks_map.get(inv.get("task_id"), {})
                linked_parent = all_parents_map.get(linked_task.get("parent_id"), {})

                recipient_name = (
                    linked_parent.get("parent_name")
                    or linked_task.get("parent_name")
                    or cust_user["full_name"]
                )
                recipient_city = linked_parent.get("city", "India")

                pdf_bytes = generate_invoice_pdf(
                    invoice_number=inv["invoice_number"],
                    nri_name=cust_user["full_name"],
                    nri_email=cust_user["email"],
                    parent_name=recipient_name,
                    parent_city=recipient_city,
                    currency=inv.get("currency", "INR"),
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
                        recipient=cust_user,
                        subject=f"CareBridge India Tax Invoice {inv['invoice_number']}",
                        summary_text=f"Attached invoice {inv['invoice_number']} for INR {totals['total_inr']:,.2f}.",
                        pdf_bytes=pdf_bytes,
                        pdf_filename=f"{inv['invoice_number']}.pdf",
                    )
                    st.success(f"Dispatched via: {', '.join(channels) if channels else 'SMTP/Twilio not configured'}")
# TAB 5: System Admin Employee Management, Password Reset & Audit History
with tab_create_emp:
    st.subheader("Provision or Remove Employee Accounts, Reset Passwords & View History")
    if admin.get("role") != "SYSTEM_ADMIN":
        st.warning("🔒 Restricted: Only the **System Admin** (`SYSTEM_ADMIN`) can manage employee logins or reset passwords.")
    else:
        col_add, col_del = st.columns([1.4, 1.0])

        # Left Column: Add Employee
        with col_add:
            st.markdown("#### ➕ Create New Employee Login")
            with st.form("sysadmin_create_emp_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                emp_name = c1.text_input("Employee Full Name *", placeholder="e.g., Suresh Naidu")
                emp_role = c2.selectbox(
                    "Assign Role & Usage Rights *",
                    ["CARE_MANAGER", "ADMIN"],
                    format_func=lambda r: {
                        "CARE_MANAGER": "Care Manager / Sahayak (Field Portal + Vault)",
                        "ADMIN": "Operations Admin (Dispatch, KYC, Billing)",
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
                    elif len(emp_pw.strip()) < 6:
                        st.error("Temporary password must be at least 6 characters.")
                    elif not valid_phone:
                        st.error(fmt_phone)
                    else:
                        try:
                            new_emp = db.register_user(
                                email=emp_email,
                                password=emp_pw.strip(),
                                full_name=emp_name,
                                role=emp_role,
                                phone=fmt_phone,
                                country="India",
                                preferred_currency="INR",
                                preferred_channels=["EMAIL", "WHATSAPP"],
                            )
                            if police_id.strip():
                                db.verify_staff_kyc(new_emp["id"], police_id.strip(), verified=True)

                            db.log_staff_action(
                                action="CREATED_EMPLOYEE",
                                target_user=new_emp,
                                performed_by=f"{admin['full_name']} ({admin['email']})",
                                details=f"Role: {emp_role} | Police ID: {police_id.strip() or 'Pending'}",
                            )
                            st.success(f"✅ Created **{emp_role}** login for **{emp_name}** (`{emp_email}`).")
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))

        # Right Column: Delete Employee
        with col_del:
            st.markdown("#### 🗑️ Delete Employee Login")
            deletable_staff = db.list_all_users("CARE_MANAGER") + db.list_all_users("ADMIN")
            if not deletable_staff:
                st.info("No employee accounts available to delete.")
            else:
                del_map = {
                    f"{u['full_name']} [{u['role']}] — {u['email']}": u for u in deletable_staff
                }
                selected_del_label = st.selectbox("Select Employee to Remove", list(del_map.keys()))
                target_emp = del_map[selected_del_label]
                st.caption(f"User ID: `{target_emp['id']}` | Phone: `{target_emp['phone']}`")

                confirm_del = st.checkbox(
                    f"Confirm permanent deletion of {target_emp['full_name']}",
                    key="confirm_emp_delete",
                )
                if st.button("Delete Employee Account", type="secondary", use_container_width=True):
                    if not confirm_del:
                        st.warning("Please check the confirmation box before deleting.")
                    else:
                        try:
                            removed = db.delete_employee_user(
                                target_emp["id"],
                                performed_by=f"{admin['full_name']} ({admin['email']})",
                            )
                            st.success(f"🗑️ Deleted **{removed['full_name']}** (`{removed['email']}`) and logged to history.")
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))

        # Middle Section: Reset Password for Any Existing Customer or Employee
        st.divider()
        st.markdown("#### 🔑 Reset Password for Any Existing User (Customers & Staff)")
        all_registered_users = db.list_all_users()
        if all_registered_users:
            reset_map = {
                f"{u['full_name']} [{u['role']}] — {u['email']}": u for u in all_registered_users
            }
            r1, r2, r3 = st.columns([2.2, 1.5, 1.2])
            chosen_reset_label = r1.selectbox(
                "Select User Account", list(reset_map.keys()), key="reset_pw_user_sel"
            )
            new_reset_pw = r2.text_input(
                "New Password (min 6 chars)", type="password", key="reset_pw_input"
            )
            r3.write("")
            r3.write("")
            if r3.button("Reset Password", type="primary", use_container_width=True, key="reset_pw_btn"):
                target_u = reset_map[chosen_reset_label]
                try:
                    db.reset_user_password(
                        target_u["id"],
                        new_reset_pw,
                        performed_by=f"{admin['full_name']} ({admin['email']})",
                    )
                    st.success(
                        f"✅ Password updated for **{target_u['email']}**! You can now sign in with the new password."
                    )
                except ValueError as exc:
                    st.error(str(exc))

        # Bottom Section: Complete Employee & Password Audit History
        st.divider()
        st.markdown("#### 📜 Employee Creation, KYC, Password Reset & Deletion History (IST)")
        audit_logs = db.list_staff_audit_logs()
        if audit_logs:
            st.dataframe(
                pd.DataFrame(audit_logs)[
                    [
                        "timestamp_ist",
                        "action",
                        "target_name",
                        "target_email",
                        "target_role",
                        "details",
                        "performed_by",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No employee actions recorded yet. Created, verified, or deleted staff will appear here.")
