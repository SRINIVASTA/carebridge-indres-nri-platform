from datetime import datetime
from pathlib import Path
from typing import Optional
import boto3
import streamlit as st

LOCAL_VAULT_DIR = Path(__file__).resolve().parents[2] / "local_vault"


class VaultStorageService:
    """Handles receipts, medical documents, and PDF invoices via Local Vault or AWS S3."""

    def __init__(self) -> None:
        storage_cfg = st.secrets.get("storage", {})
        self.provider = storage_cfg.get("provider", "local").lower()
        self.bucket = storage_cfg.get("bucket_name", "carebridge-vault")

        if self.provider == "s3" and storage_cfg.get("aws_access_key_id"):
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=storage_cfg.get("aws_access_key_id"),
                aws_secret_access_key=storage_cfg.get("aws_secret_access_key"),
                region_name=storage_cfg.get("aws_region", "ap-south-1"),
            )
        else:
            self.s3_client = None
            LOCAL_VAULT_DIR.mkdir(parents=True, exist_ok=True)

    def upload_file(
        self, file_bytes: bytes, folder: str, filename: str, content_type: str = "application/pdf"
    ) -> Optional[str]:
        """Save file bytes to S3 or local_vault/ and return relative storage path."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        object_path = f"{folder}/{timestamp}_{filename}"

        if self.s3_client:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=object_path,
                Body=file_bytes,
                ContentType=content_type,
                ServerSideEncryption="AES256",
            )
            return object_path

        target_file = LOCAL_VAULT_DIR / object_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_bytes(file_bytes)
        return f"local_vault/{object_path}"

    def get_signed_download_url(self, object_path: str, expires_in: int = 3600) -> Optional[str]:
        """Generate a temporary pre-signed URL when using AWS S3."""
        if not object_path or object_path.startswith("local_vault/"):
            return None

        if self.s3_client:
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": object_path},
                ExpiresIn=expires_in,
            )
        return None
