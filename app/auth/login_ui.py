import streamlit as st
from app.auth.session_manager import login_as_role
from app.services.database import DatabaseService
from app.utils.validators import validate_indian_phone, validate_international_phone


def render_auth_portal() -> None:
    """Render Shared Sign In, Customer Sign Up (Indian Resident & NRI Sponsor), and Quick Demo."""
    db = DatabaseService()
    st.markdown("### Sign In or Create Your CareBridge Account")

    tab_login, tab_signup, tab_demo = st.tabs(
        [
            "🔐 Sign In (Customers & Employees)",
            "📝 Create Customer Account (Sign Up)",
            "⚡ Quick Role Demo",
        ]
    )

    # TAB 1: Shared Password Login & Self-Service Password Reset
    with tab_login:
        st.caption(
            "Sign in with your registered Indian Resident / NRI email or your System Admin-issued Employee credentials."
        )
        with st.form("real_login_form"):
            email = st.text_input("Email Address", placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.error("Please enter both your email and password.")
                else:
                    user = db.authenticate_user(email, password)
                    if user:
                        login_as_role(user["role"], user)
                        st.success(f"Welcome back, {user['full_name']}!")
                        st.rerun()
                    else:
                        st.error("Invalid email or password. Please try again or reset your password below.")

        with st.expander("🔑 Forgot Password? Reset Your Password"):
            st.caption(
                "Verify your registered Email Address and Mobile Number (E.164 format, e.g., +919848012345) "
                "to set a new password."
            )
            with st.form("self_reset_pw_form", clear_on_submit=True):
                r_email = st.text_input("Registered Email Address *", placeholder="you@example.com")
                r_phone = st.text_input(
                    "Registered Mobile / WhatsApp Number *", placeholder="+919848012345 or +14155550199"
                )
                r1, r2 = st.columns(2)
                r_new_pw = r1.text_input("New Password * (min 6 chars)", type="password")
                r_confirm_pw = r2.text_input("Confirm New Password *", type="password")

                if st.form_submit_button("Reset My Password", use_container_width=True):
                    if not r_email.strip() or not r_phone.strip():
                        st.error("Please enter both your registered email and mobile number.")
                    elif r_new_pw.strip() != r_confirm_pw.strip():
                        st.error("New passwords do not match.")
                    else:
                        try:
                            db.self_reset_password(r_email, r_phone, r_new_pw)
                            st.success(
                                "✅ Password reset successfully! You can now sign in above with your new password."
                            )
                        except ValueError as exc:
                            st.error(str(exc))

    # TAB 2: Create New Customer Account (Indian Resident Self-Care or NRI Sponsor)
    with tab_signup:
        st.caption(
            "Choose whether you are an Indian Resident seeking personal mobility/home assistance "
            "or an NRI Sponsor booking care for parents in India."
        )

        account_mode = st.radio(
            "Who are you registering for? *",
            [
                "INDIAN_RESIDENT",
                "NRI_SPONSOR",
            ],
            format_func=lambda m: {
                "INDIAN_RESIDENT": "🇮🇳 Indian Resident (I live in India & need home/mobility assistance)",
                "NRI_SPONSOR": "🌍 NRI / Family Sponsor (Booking care for parents in India)",
            }[m],
            horizontal=True,
        )

        is_resident = account_mode == "INDIAN_RESIDENT"

        with st.form("signup_form"):
            col1, col2 = st.columns(2)
            full_name = col1.text_input(
                "Full Name *",
                placeholder="e.g., Smt. Lakshmi Rao" if is_resident else "e.g., Karthik Reddy",
            )
            email = col2.text_input("Email Address *", placeholder="you@example.com")

            col3, col4 = st.columns(2)
            phone = col3.text_input(
                "Mobile / WhatsApp (E.164) *",
                placeholder="+919848012345" if is_resident else "+14155550199",
            )
            if is_resident:
                country = col4.text_input("Country of Residence", value="India", disabled=True)
            else:
                country = col4.selectbox(
                    "Country of Residence",
                    ["USA", "UK", "Canada", "UAE", "Singapore", "Australia", "Other"],
                )

            col5, col6 = st.columns(2)
            password = col5.text_input("Create Password * (min 6 chars)", type="password")
            confirm_pw = col6.text_input("Confirm Password *", type="password")

            col7, col8 = st.columns(2)
            if is_resident:
                currency = col7.text_input("Billing Currency", value="INR", disabled=True)
            else:
                currency = col7.selectbox("Preferred Billing Currency", ["USD", "INR", "GBP", "EUR"])

            channels = col8.multiselect(
                "Preferred Channels for PDF Invoices & Visit Reports",
                ["EMAIL", "WHATSAPP", "SMS"],
                default=["WHATSAPP", "EMAIL"],
            )
            # Extra Self-Care & Mobility Profile Section for Indian Residents
            self_care_details = None
            if is_resident:
                st.divider()
                st.markdown("#### ♿ Your Mobility & Home Care Profile")
                r1, r2, r3 = st.columns([1, 1.5, 2])
                res_age = r1.number_input("Your Age *", min_value=18, max_value=120, value=65)
                res_city = r2.text_input("City in India *", placeholder="e.g., Hyderabad / Visakhapatnam")
                res_mobility = r3.selectbox(
                    "Mobility Assistance Level *",
                    [
                        "WHEELCHAIR_REQUIRED",
                        "WALKER_ASSISTED",
                        "BEDRIDDEN",
                        "POST_SURGERY_RECOVERY",
                        "INDEPENDENT",
                    ],
                    format_func=lambda lvl: {
                        "WHEELCHAIR_REQUIRED": "Wheelchair Required (Unable to walk)",
                        "WALKER_ASSISTED": "Walker / Cane Assisted",
                        "BEDRIDDEN": "Bedridden / Homebound Care",
                        "POST_SURGERY_RECOVERY": "Post-Surgery / Temporary Immobility",
                        "INDEPENDENT": "Independent (Errands & Escort Only)",
                    }[lvl],
                )

                res_address = st.text_input(
                    "Complete Residential Address *",
                    placeholder="Flat/House No., Street, Landmark, PIN Code",
                )

                r4, r5, r6 = st.columns([1, 1.5, 2])
                res_blood = r4.selectbox(
                    "Blood Group", ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-", "Unknown"]
                )
                res_emg_phone = r5.text_input(
                    "Local Emergency Contact (+91)", placeholder="+919848099887"
                )
                res_access = r6.text_input(
                    "Home Access / Lift / Ramp Notes",
                    placeholder="e.g., 2nd floor with lift; needs wheelchair ramp at gate",
                )
                res_cond = st.text_input(
                    "Medical Conditions / Support Notes",
                    placeholder="e.g., Knee osteoarthritis, post-stroke mobility support",
                )

                self_care_details = {
                    "age": res_age,
                    "city": res_city.strip(),
                    "address": res_address.strip(),
                    "mobility_level": res_mobility,
                    "home_access_notes": res_access.strip(),
                    "blood_group": res_blood,
                    "emergency_contact_india": res_emg_phone.strip(),
                    "medical_conditions": res_cond.strip(),
                }

            create_btn = st.form_submit_button(
                "Create Customer Account & Sign In", type="primary", use_container_width=True
            )
            if create_btn:
                valid_phone, fmt_phone = (
                    validate_indian_phone(phone) if is_resident else validate_international_phone(phone)
                )
                if not full_name.strip() or not email.strip():
                    st.error("Full name and email are required.")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters long.")
                elif password != confirm_pw:
                    st.error("Passwords do not match.")
                elif not valid_phone:
                    st.error(fmt_phone)
                elif not channels:
                    st.error("Select at least one communication channel.")
                elif is_resident and (
                    not self_care_details["city"] or not self_care_details["address"]
                ):
                    st.error("City and complete residential address are required for Indian Resident care.")
                else:
                    if is_resident and self_care_details["emergency_contact_india"]:
                        ok_emg, fmt_emg = validate_indian_phone(
                            self_care_details["emergency_contact_india"]
                        )
                        if not ok_emg:
                            st.error(f"Emergency contact error: {fmt_emg}")
                            st.stop()
                        self_care_details["emergency_contact_india"] = fmt_emg

                    try:
                        new_user = db.register_user(
                            email=email,
                            password=password,
                            full_name=full_name,
                            role="INDRES_NRI",
                            phone=fmt_phone,
                            country="India" if is_resident else country,
                            preferred_currency="INR" if is_resident else currency,
                            preferred_channels=channels,
                            customer_type=account_mode,
                            self_care_details=self_care_details,
                        )
                        login_as_role("INDRES_NRI", new_user)
                        st.success("Account created! Redirecting to your Care Dashboard...")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

    # TAB 3: 1-Click Demo Accounts
    with tab_demo:
        st.caption("Instant preview using pre-populated sample profiles (no signup needed).")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("Demo: Indian Resident", use_container_width=True):
                login_as_role("INDIAN_RESIDENT")
                st.rerun()
        with c2:
            if st.button("Demo: NRI Sponsor", use_container_width=True):
                login_as_role("INDRES_NRI")
                st.rerun()
        with c3:
            if st.button("Demo: Care Manager", use_container_width=True):
                login_as_role("CARE_MANAGER")
                st.rerun()
        with c4:
            if st.button("Demo: Admin Ops", use_container_width=True):
                login_as_role("ADMIN")
                st.rerun()
