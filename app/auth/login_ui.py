import streamlit as st
from app.auth.session_manager import DEMO_USERS, login_as_role
from app.utils.validators import validate_international_phone


def render_auth_portal() -> None:
    """Render 1-click role demo login alongside custom NRI/Staff onboarding."""
    st.markdown("### Sign In to CareBridge India")
    tab_demo, tab_custom = st.tabs(["Quick Role Access (Demo)", "NRI / Staff Login & Preferences"])

    with tab_demo:
        st.caption(
            "Explore each stakeholder view instantly, or customize communication channels in the next tab."
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("#### NRI Family Portal")
            st.write("Book care visits, manage prepaid INR wallet, download/send PDF invoices, & SOS.")
            if st.button("Enter as NRI (Arjun Sharma)", type="primary", use_container_width=True):
                login_as_role("NRI")
                st.rerun()

        with col2:
            st.markdown("#### Care Manager (Sahayak)")
            st.write("GPS check-in, log parent vitals, upload receipts, & auto-dispatch visit PDFs.")
            if st.button("Enter as Care Manager", use_container_width=True):
                login_as_role("CARE_MANAGER")
                st.rerun()

        with col3:
            st.markdown("#### Admin Operations")
            st.write("Verify staff KYC/Police ID, audit receipts, & issue GST PDF invoices.")
            if st.button("Enter as Admin Ops", use_container_width=True):
                login_as_role("ADMIN")
                st.rerun()

    with tab_custom:
        with st.form("custom_login_form"):
            role = st.selectbox("Select Portal Role", ["NRI", "CARE_MANAGER", "ADMIN"])
            full_name = st.text_input("Full Name", value=DEMO_USERS[role]["full_name"])
            email = st.text_input("Email Address (for PDF Invoices & Reports)", value=DEMO_USERS[role]["email"])
            phone = st.text_input(
                "Mobile / WhatsApp Number (E.164 format)", value=DEMO_USERS[role]["phone"]
            )
            currency = st.selectbox("Preferred Billing Currency", ["USD", "INR", "GBP", "EUR"])
            channels = st.multiselect(
                "Available Communication Channels for PDF Reports & Invoices",
                ["EMAIL", "WHATSAPP", "SMS"],
                default=["EMAIL", "WHATSAPP"],
            )
            submitted = st.form_submit_button("Launch Portal", type="primary")

            if submitted:
                valid_phone, formatted_phone = validate_international_phone(phone)
                if not valid_phone:
                    st.error(formatted_phone)
                elif not channels:
                    st.error("Select at least one communication channel.")
                else:
                    profile = DEMO_USERS[role].copy()
                    profile.update(
                        {
                            "full_name": full_name.strip(),
                            "email": email.strip(),
                            "phone": formatted_phone,
                            "whatsapp_number": formatted_phone,
                            "preferred_currency": currency,
                            "preferred_channels": channels,
                        }
                    )
                    login_as_role(role, profile)
                    st.rerun()
