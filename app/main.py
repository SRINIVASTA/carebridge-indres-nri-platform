from pathlib import Path
import sys

# Ensure project root is on sys.path when launched via `streamlit run app/main.py`
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from app.auth.login_ui import render_auth_portal
from app.auth.session_manager import init_session_state, logout_user
from app.services.database import DatabaseService
from app.utils.currency import format_currency


def load_custom_css() -> None:
    css_path = Path(__file__).parent / "assets" / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(
        page_title="CareBridge India — NRI Parent Care & Concierge",
        page_icon="🩺",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    load_custom_css()
    init_session_state()

    # Sidebar: Currency Switcher, Active User & Communication Channels
    with st.sidebar:
        st.title("🩺 CareBridge India")
        st.caption("Trusted Parent Care & Concierge for NRIs")

        currency = st.selectbox(
            "Display Currency",
            ["USD", "INR", "GBP", "EUR"],
            index=["USD", "INR", "GBP", "EUR"].index(st.session_state.get("currency", "USD")),
        )
        st.session_state["currency"] = currency
        st.divider()

        if st.session_state.get("authenticated") and st.session_state.get("current_user"):
            user = st.session_state["current_user"]
            st.success(f"**{user['full_name']}**")
            st.caption(f"Role: `{user['role']}` | Channels: {', '.join(user.get('preferred_channels', []))}")

            # Allow live toggling of available communication channels
            updated_channels = st.multiselect(
                "Active Delivery Channels",
                ["EMAIL", "WHATSAPP", "SMS"],
                default=user.get("preferred_channels", ["EMAIL", "WHATSAPP"]),
                key="sidebar_channels",
            )
            user["preferred_channels"] = updated_channels

            if st.button("Sign Out", use_container_width=True):
                logout_user()
                st.rerun()
        else:
            st.info("Not signed in. Use the gateway on the right to enter.")

    # Main Gateway View
    st.title("CareBridge India — NRI Parent Care & Concierge")
    st.markdown(
        "Real-time medical escorting, home vitals monitoring, itemized PDF invoicing, "
        "and verified local concierge support (*Sahayaks*) for your parents in India."
    )

    if not st.session_state.get("authenticated"):
        render_auth_portal()
        return

    user = st.session_state["current_user"]
    db = DatabaseService()
    curr = st.session_state["currency"]

    st.subheader(f"Welcome back, {user['full_name']}")
    col1, col2, col3, col4 = st.columns(4)
    wallet = db.get_wallet(user["id"])
    parents = db.get_parents_for_nri("usr-nri-101")
    tasks = db.list_tasks(user["role"], user["id"])

    with col1:
        st.metric("Active Plan", wallet.get("plan_tier", "COUPLE"))
    with col2:
        st.metric("Prepaid Expense Wallet", format_currency(float(wallet.get("balance_inr", 0)), curr))
    with col3:
        st.metric("Registered Parents", len(parents))
    with col4:
        st.metric("Active / Logged Tasks", len(tasks))

    st.divider()
    st.markdown("### Quick Navigation")
    st.info(
        "Use the **left sidebar navigation menu** to open:\n"
        "- **01 Plans and Pricing**: Compare monthly USD/INR subscriptions and on-demand rates.\n"
        "- **02 NRI Dashboard**: Schedule tasks, top up wallet, trigger SOS, and download/send PDF invoices.\n"
        "- **03 Health Vault**: View BP/sugar charts, encrypted prescriptions, and export PDF health reports.\n"
        "- **04 Care Manager**: Log GPS check-ins, parent vitals, receipts, and dispatch visit reports.\n"
        "- **05 Admin Ops**: Verify ground staff KYC/Police clearance, audit actuals, and issue GST invoices."
    )


if __name__ == "__main__":
    main()
