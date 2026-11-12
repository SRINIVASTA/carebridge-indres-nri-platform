import smtplib
from email.message import EmailMessage
from typing import Dict, List, Optional
import streamlit as st
from twilio.rest import Client


class NotificationDispatcher:
    """Dispatches alerts and PDF reports/invoices across Email, WhatsApp, and SMS."""

    def __init__(self) -> None:
        notif_cfg = st.secrets.get("notifications", {})
        self.twilio_sid = notif_cfg.get("twilio_account_sid", "")
        self.twilio_token = notif_cfg.get("twilio_auth_token", "")
        self.whatsapp_from = notif_cfg.get("twilio_whatsapp_from", "whatsapp:+14155238886")
        self.sms_from = notif_cfg.get("twilio_sms_from", "+14155238886")

        self.smtp_host = notif_cfg.get("smtp_host", "")
        self.smtp_port = int(notif_cfg.get("smtp_port", 587))
        self.smtp_user = notif_cfg.get("smtp_user", "")
        self.smtp_password = notif_cfg.get("smtp_password", "")

        self.twilio_client = (
            Client(self.twilio_sid, self.twilio_token)
            if self.twilio_sid and self.twilio_token
            else None
        )

    def send_email_with_pdf(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        pdf_bytes: Optional[bytes] = None,
        pdf_filename: str = "CareBridge_Report.pdf",
    ) -> bool:
        """Send an email with an optional PDF invoice or visit report attached."""
        if not (self.smtp_host and self.smtp_user and self.smtp_password):
            return False
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = self.smtp_user
            msg["To"] = to_email
            msg.set_content(body_text)

            if pdf_bytes:
                msg.add_attachment(
                    pdf_bytes,
                    maintype="application",
                    subtype="pdf",
                    filename=pdf_filename,
                )

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            return True
        except Exception:
            return False

    def send_whatsapp(
        self, to_phone: str, message: str, media_url: Optional[str] = None
    ) -> bool:
        """Send WhatsApp alert with optional signed PDF link."""
        if not self.twilio_client or not to_phone:
            return False
        try:
            formatted_to = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
            kwargs: Dict[str, object] = {
                "from_": self.whatsapp_from,
                "to": formatted_to,
                "body": message,
            }
            if media_url:
                kwargs["media_url"] = [media_url]
            self.twilio_client.messages.create(**kwargs)
            return True
        except Exception:
            return False

    def send_sms(self, to_phone: str, message: str) -> bool:
        """Send plain SMS alert with summary and download link."""
        if not self.twilio_client or not to_phone:
            return False
        try:
            clean_to = to_phone.replace("whatsapp:", "")
            self.twilio_client.messages.create(
                from_=self.sms_from,
                to=clean_to,
                body=message[:1500],
            )
            return True
        except Exception:
            return False

    def dispatch_to_available_channels(
        self,
        recipient: Dict[str, any],
        subject: str,
        summary_text: str,
        pdf_bytes: Optional[bytes] = None,
        pdf_filename: str = "CareBridge_Document.pdf",
        signed_pdf_url: Optional[str] = None,
    ) -> List[str]:
        """
        Automatically send the report/invoice across all communication channels
        configured and available for the NRI user (Email, WhatsApp, SMS).
        """
        sent_channels: List[str] = []
        prefs = [c.upper() for c in recipient.get("preferred_channels", ["EMAIL", "WHATSAPP"])]

        email = recipient.get("email")
        if "EMAIL" in prefs and email:
            if self.send_email_with_pdf(email, subject, summary_text, pdf_bytes, pdf_filename):
                sent_channels.append("EMAIL")

        wa_phone = recipient.get("whatsapp_number") or recipient.get("phone")
        link_suffix = f"\nDownload PDF: {signed_pdf_url}" if signed_pdf_url else ""
        if "WHATSAPP" in prefs and wa_phone:
            if self.send_whatsapp(wa_phone, f"*{subject}*\n{summary_text}{link_suffix}", signed_pdf_url):
                sent_channels.append("WHATSAPP")

        sms_phone = recipient.get("phone")
        if "SMS" in prefs and sms_phone:
            if self.send_sms(sms_phone, f"{subject}: {summary_text}{link_suffix}"):
                sent_channels.append("SMS")

        return sent_channels
