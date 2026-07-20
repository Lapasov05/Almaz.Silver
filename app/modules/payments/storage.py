"""Chek (receipt) object storage — S3-mos (MinIO), boto3 (TZ 3/12).

Sinxron boto3 async endpoint'da `asyncio.to_thread` orqali chaqiriladi.
"""
import asyncio
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings

settings = get_settings()


class ReceiptStorage:
    def __init__(self) -> None:
        self._bucket = settings.s3_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name="us-east-1",
            config=Config(signature_version="s3v4"),
        )

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    def _put(self, key: str, data: bytes, content_type: str) -> None:
        self._ensure_bucket()
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    async def upload(self, data: bytes, content_type: str = "image/jpeg", ext: str = "jpg") -> tuple[str, str]:
        """Chekni yuklaydi. (url, key) qaytaradi."""
        key = f"receipts/{uuid.uuid4().hex}.{ext}"
        await asyncio.to_thread(self._put, key, data, content_type)
        url = f"{settings.s3_endpoint_url.rstrip('/')}/{self._bucket}/{key}"
        return url, key
