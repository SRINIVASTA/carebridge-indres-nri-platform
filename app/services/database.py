from typing import Any, Dict, List, Optional
import streamlit as st
from supabase import Client, create_client


@st.cache_resource
def get_supabase_client() -> Optional[Client]:
    """Initialize cached Supabase client from st.secrets."""
    sb_cfg = st.secrets.get("supabase", {})
    url = sb_cfg.get("url", "")
    key = sb_cfg.get("service_role_key") or sb_cfg.get("anon_key", "")
    if not url or not key or "your-project-id" in url:
        return None
    return create_client(url, key)


class DatabaseService:
    """Data access layer with graceful in-memory demo fallback when offline."""

    def __init__(self) -> None:
        self.client = get_supabase_client()

    def get_parents_for_nri(self, nri_user_id: str) -> List[Dict[str, Any]]:
        if self.client:
            res = (
                self.client.table("parents")
                .select("*")
                .eq("nri_user_id", nri_user_id)
                .execute()
            )
            return res.data or []
        return st.session_state.get("demo_parents", [])

    def get_wallet(self, nri_user_id: str) -> Dict[str, Any]:
        if self.client:
            res = (
                self.client.table("wallets")
                .select("*")
                .eq("nri_user_id", nri_user_id)
                .single()
                .execute()
            )
            return res.data or {"plan_tier": "COMPLETE", "balance_inr": 15000.0}
        return st.session_state.get(
            "demo_wallet", {"plan_tier": "COMPLETE", "balance_inr": 15000.0}
        )

    def update_wallet_balance(self, nri_user_id: str, delta_inr: float) -> float:
        wallet = self.get_wallet(nri_user_id)
        new_balance = round(float(wallet.get("balance_inr", 0.0)) + delta_inr, 2)
        if new_balance < 0:
            raise ValueError("Insufficient prepaid wallet balance.")
        if self.client:
            self.client.table("wallets").update({"balance_inr": new_balance}).eq(
                "nri_user_id", nri_user_id
            ).execute()
        else:
            st.session_state["demo_wallet"]["balance_inr"] = new_balance
        return new_balance

    def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.client:
            res = self.client.table("tasks").insert(payload).execute()
            return res.data[0]
        tasks = st.session_state.setdefault("demo_tasks", [])
        payload["id"] = f"TSK-{1001 + len(tasks)}"
        tasks.insert(0, payload)
        return payload

    def list_tasks(self, role: str, user_id: str) -> List[Dict[str, Any]]:
        if self.client:
            query = self.client.table("tasks").select("*").order("created_at", desc=True)
            if role == "NRI":
                query = query.eq("nri_user_id", user_id)
            elif role == "CARE_MANAGER":
                query = query.eq("care_manager_id", user_id)
            return query.execute().data or []
        return st.session_state.get("demo_tasks", [])

    def save_invoice(self, invoice_payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.client:
            res = self.client.table("invoices").insert(invoice_payload).execute()
            return res.data[0]
        invoices = st.session_state.setdefault("demo_invoices", [])
        invoices.insert(0, invoice_payload)
        return invoice_payload

    def list_invoices(self, nri_user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.client:
            query = self.client.table("invoices").select("*").order("created_at", desc=True)
            if nri_user_id:
                query = query.eq("nri_user_id", nri_user_id)
            return query.execute().data or []
        all_inv = st.session_state.get("demo_invoices", [])
        if nri_user_id:
            return [i for i in all_inv if i.get("nri_user_id") == nri_user_id]
        return all_inv

    def log_vitals(self, vitals_payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.client:
            res = self.client.table("vitals_logs").insert(vitals_payload).execute()
            return res.data[0]
        logs = st.session_state.setdefault("demo_vitals", [])
        logs.append(vitals_payload)
        return vitals_payload

    def get_vitals(self, parent_id: str) -> List[Dict[str, Any]]:
        if self.client:
            res = (
                self.client.table("vitals_logs")
                .select("*")
                .eq("parent_id", parent_id)
                .order("recorded_at", desc=False)
                .execute()
            )
            return res.data or []
        return [v for v in st.session_state.get("demo_vitals", []) if v.get("parent_id") == parent_id]
