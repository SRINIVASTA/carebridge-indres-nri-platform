from datetime import datetime
from typing import Optional
import boto3
import streamlit as st
from supabase import create_client


class VaultStorageService:
    """Handles encrypted medical documents, receipts, and generated PDF invoices."""

    def __init__(self) -> None:
        storage_cfg = st.secrets.get("storage", {})
        self.provider = storage_cfg.get("provider", "supabase").lower()
        self.bucket = storage_cfg.get("bucket_name", "carebridge-vault")

        if self.provider == "s3":
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=storage_cfg.get("aws_access_key_id"),
                aws_secret_access_key=storage_cfg.get("aws_secret_access_key"),
                region_name=storage_cfg.get("aws_region", "ap-south-1"),
            )
            self.sb_client = None
        else:
            sb_cfg = st.secrets.get("supabase", {})
            url = sb_cfg.get("url", "")
            key = sb_cfg.get("service_role_key") or sb_cfg.get("anon_key", "")
            self.sb_client = create_client(url, key) if url and key else None
            self.s3_client = None

    def upload_file(
        self, file_bytes: bytes, folder: str, filename: str, content_type: str = "application/pdf"
    ) -> Optional[str]:
        """Upload file bytes and return storage path."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        object_path = f"{folder}/{timestamp}_{filename}"

        if self.provider == "s3" and self.s3_client:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=object_path,
                Body=file_bytes,
                ContentType=content_type,
                ServerSideEncryption="AES256",
            )
            return object_path

        if self.sb_client:
            self.sb_client.storage.from_(self.bucket).upload(
                path=object_path,
                file=file_bytes,
                file_options={"content-type": content_type},
            )
            return object_path

        return f"local_demo/{object_path}"

    def get_signed_download_url(self, object_path: str, expires_in: int = 3600) -> Optional[str]:
        """Generate a temporary pre-signed URL for WhatsApp/SMS PDF delivery."""
        if not object_path or object_path.startswith("local_demo/"):
            return None

        if self.provider == "s3" and self.s3_client:
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": object_path},
                ExpiresIn=expires_in,
            )

        if self.sb_client:
            res = self.sb_client.storage.from_(self.bucket).create_signed_url(
                object_path, expires_in
            )
            return res.get("signedURL")
        return None
