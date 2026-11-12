import streamlit as st
from app.auth.session_manager import login_as_role
from app.services.database import DatabaseService
from app.utils.validators import validate_international_phone


def render_auth_portal() -> None:
    """Render Real Sign In, Account Registration (Sign Up), and Quick Demo Login."""
    db = DatabaseService()
    st.markdown("### Sign In or Create Your CareBridge Account")

    tab_login, tab_signup, tab_demo = st.tabs(
        ["🔐 Sign In (Email & Password)", "📝 Create Account (Sign Up)", "⚡ Quick Role Demo"]
    )

    # TAB 1: Real Password Login
    with tab_login:
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
                        st.error("Invalid email or password. Please try again or create an account.")
    # TAB 2: Create New Account (Sign Up)
    with tab_signup:
        with st.form("signup_form"):
            col1, col2 = st.columns(2)
            full_name = col1.text_input("Full Name *", placeholder="e.g., Karthik Reddy")
            role = col2.selectbox(
                "Account Role *",
                ["NRI", "CARE_MANAGER", "ADMIN"],
                format_func=lambda r: {
                    "NRI": "NRI Family Member (Book Care for Parents)",
                    "CARE_MANAGER": "Care Manager / Sahayak (India Ground Staff)",
                    "ADMIN": "Operations Admin",
                }[r],
            )

            col3, col4 = st.columns(2)
            email = col3.text_input("Email Address *", placeholder="karthik@example.com")
            phone = col4.text_input("Mobile / WhatsApp (E.164) *", placeholder="+14155550199 or +919848012345")

            col5, col6 = st.columns(2)
            password = col5.text_input("Create Password * (min 6 chars)", type="password")
            confirm_pw = col6.text_input("Confirm Password *", type="password")

            col7, col8 = st.columns(2)
            country = col7.selectbox(
                "Country of Residence",
                ["USA", "UK", "Canada", "UAE", "Singapore", "Australia", "India"],
            )
            currency = col8.selectbox("Preferred Billing Currency", ["USD", "INR", "GBP", "EUR"])

            channels = st.multiselect(
                "Preferred Channels for PDF Invoices & Visit Reports",
                ["EMAIL", "WHATSAPP", "SMS"],
                default=["EMAIL", "WHATSAPP"],
            )

            create_btn = st.form_submit_button("Create Account & Sign In", type="primary", use_container_width=True)

            if create_btn:
                valid_phone, fmt_phone = validate_international_phone(phone)
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
                else:
                    try:
                        new_user = db.register_user(
                            email=email,
                            password=password,
                            full_name=full_name,
                            role=role,
                            phone=fmt_phone,
                            country=country,
                            preferred_currency=currency,
                            preferred_channels=channels,
                        )
                        login_as_role(role, new_user)
                        st.success("Account created! Redirecting to your portal...")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

    # TAB 3: 1-Click Demo Accounts
    with tab_demo:
        st.caption("Instant preview using pre-populated sample profiles (no signup needed).")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Demo: NRI Family (Arjun)", use_container_width=True):
                login_as_role("NRI")
                st.rerun()
        with c2:
            if st.button("Demo: Care Manager (Ravi)", use_container_width=True):
                login_as_role("CARE_MANAGER")
                st.rerun()
        with c3:
            if st.button("Demo: Admin Ops (Priya)", use_container_width=True):
                login_as_role("ADMIN")
                st.rerun()
