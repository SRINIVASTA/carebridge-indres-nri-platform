from typing import Any, Dict
import razorpay
import streamlit as st
import stripe


class PaymentGatewayService:
    """Handles Stripe (USD/GBP/EUR) and Razorpay (INR) checkout & wallet top-ups."""

    def __init__(self) -> None:
        pay_cfg = st.secrets.get("payments", {})
        self.stripe_key = pay_cfg.get("stripe_secret_key", "")
        self.rzp_id = pay_cfg.get("razorpay_key_id", "")
        self.rzp_secret = pay_cfg.get("razorpay_key_secret", "")

        if self.stripe_key and not self.stripe_key.startswith("sk_test_..."):
            stripe.api_key = self.stripe_key

        self.rzp_client = (
            razorpay.Client(auth=(self.rzp_id, self.rzp_secret))
            if self.rzp_id and self.rzp_secret and "your_razorpay" not in self.rzp_secret
            else None
        )

    def create_stripe_payment_intent(
        self, amount_major: float, currency: str, metadata: Dict[str, str]
    ) -> Dict[str, Any]:
        """Create a Stripe PaymentIntent for international NRI cards."""
        if not stripe.api_key:
            return {
                "provider": "STRIPE_DEMO",
                "status": "succeeded",
                "id": "pi_demo_carebridge_9981",
                "amount": amount_major,
                "currency": currency.upper(),
            }
        intent = stripe.PaymentIntent.create(
            amount=int(round(amount_major * 100)),
            currency=currency.lower(),
            metadata=metadata,
        )
        return {"provider": "STRIPE", "id": intent.id, "client_secret": intent.client_secret}

    def create_razorpay_order(self, amount_inr: float, receipt_id: str) -> Dict[str, Any]:
        """Create a Razorpay Order for INR UPI/NetBanking/Card wallet top-ups."""
        if not self.rzp_client:
            return {
                "provider": "RAZORPAY_DEMO",
                "status": "paid",
                "id": f"order_demo_{receipt_id}",
                "amount_inr": amount_inr,
            }
        order = self.rzp_client.order.create(
            {
                "amount": int(round(amount_inr * 100)),
                "currency": "INR",
                "receipt": receipt_id,
                "payment_capture": 1,
            }
        )
        return {"provider": "RAZORPAY", "id": order["id"], "amount_inr": amount_inr}
