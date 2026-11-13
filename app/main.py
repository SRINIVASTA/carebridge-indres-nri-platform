from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from app.auth.login_ui import render_auth_portal
from app.auth.session_manager import init_session_state, logout_user
from app.utils.datetime_helper import now_ist_str


def load_custom_css() -> None:
    css_path = Path(__file__).parent / "assets" / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


def render_gateway_home() -> None:
    """Landing / Login view shown when not signed in or on Home."""
    st.title("🩺 CareBridge India — Resident Mobility & NRI Parent Care")
    st.caption(f"Current India Time: `{now_ist_str()}`")
    st.markdown(
        "Trusted mobility assistance, medical escorting, home vitals monitoring, "
        "itemized PDF invoicing, and verified local Care Managers (*Sahayaks*) across India."
    )

    if not st.session_state.get("authenticated"):
        render_auth_portal()
    else:
        user = st.session_state["current_user"]
        ctype = user.get("customer_type", "")
        badge = f" ({ctype.replace('_', ' ').title()})" if ctype and ctype != "STAFF" else ""
        st.success(f"Signed in as **{user['full_name']}** (`{user['role']}`{badge})")
        st.info("Use the navigation menu on the left to open your role-specific workspace.")
def main() -> None:
    st.set_page_config(
        page_title="CareBridge India — Resident Mobility & NRI Parent Care",
        page_icon="🩺",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    load_custom_css()
    init_session_state()

    user = st.session_state.get("current_user") or {}
    is_ind_res = user.get("customer_type") == "INDIAN_RESIDENT"
    dashboard_title = "My Care & Mobility Dashboard" if is_ind_res else "Family & Resident Care Dashboard"

    # Define all pages
    home_page = st.Page(render_gateway_home, title="Home / Sign In", icon="🔐", default=True)
    plans_page = st.Page("pages/01_plans_and_pricing.py", title="Plans & Pricing", icon="💳")
    nri_page = st.Page("pages/02_nri_dashboard.py", title=dashboard_title, icon="🏠")
    vault_page = st.Page("pages/03_health_vault.py", title="Health & Document Vault", icon="🩺")
    cm_page = st.Page("pages/04_care_manager.py", title="Care Manager Field Portal", icon="🛵")
    admin_page = st.Page("pages/05_admin_ops.py", title="Admin Operations Console", icon="🛡️")

    # Build strict role-based navigation menu
    if not st.session_state.get("authenticated") or not user:
        allowed_pages = [home_page, plans_page]
    else:
        role = user.get("role")
        if role in ("INDRES_NRI", "NRI"):
            allowed_pages = [nri_page, vault_page, plans_page]
        elif role == "CARE_MANAGER":
            allowed_pages = [cm_page, vault_page]
        elif role in ("ADMIN", "SYSTEM_ADMIN"):
            allowed_pages = [admin_page, cm_page, nri_page, vault_page, plans_page]
        else:
            allowed_pages = [home_page, plans_page]

    pg = st.navigation(allowed_pages)
    # Sidebar: Currency Switcher, Active Profile & Sign Out
    with st.sidebar:
        st.caption(f"🕒 `{now_ist_str()}`")
        currencies = ["USD", "INR", "GBP", "EUR"]
        default_curr = st.session_state.get("currency", "INR" if is_ind_res else "USD")
        if default_curr not in currencies:
            default_curr = "INR"

        currency = st.selectbox(
            "Display Currency",
            currencies,
            index=currencies.index(default_curr),
        )
        st.session_state["currency"] = currency

        if st.session_state.get("authenticated") and user:
            st.divider()
            st.success(f"**{user['full_name']}**")
            ctype = user.get("customer_type")
            role_label = (
                "Indian Resident"
                if ctype == "INDIAN_RESIDENT"
                else "NRI Sponsor"
                if ctype == "NRI_SPONSOR"
                else user.get("role")
            )
            st.caption(f"Account: `{role_label}`")

            updated_channels = st.multiselect(
                "Delivery Channels",
                ["EMAIL", "WHATSAPP", "SMS"],
                default=user.get("preferred_channels", ["EMAIL", "WHATSAPP"]),
                key="sidebar_channels",
            )
            user["preferred_channels"] = updated_channels

            if st.button("Sign Out", use_container_width=True):
                logout_user()
                st.rerun()

    pg.run()


if __name__ == "__main__":
    main()
