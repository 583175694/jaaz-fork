import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class COSConfig:
    secret_id: str
    secret_key: str
    bucket: str
    region: str
    public_base_url: str
    key_prefix: str


def _normalize_prefix(prefix: str) -> str:
    return prefix.strip().strip("/")


def load_cos_config() -> Optional[COSConfig]:
    secret_id = os.getenv("COS_SECRET_ID", "").strip()
    secret_key = os.getenv("COS_SECRET_KEY", "").strip()
    bucket = os.getenv("COS_BUCKET", "").strip()
    region = os.getenv("COS_REGION", "").strip()
    public_base_url = os.getenv("COS_PUBLIC_BASE_URL", "").strip().rstrip("/")
    key_prefix = _normalize_prefix(os.getenv("COS_KEY_PREFIX", "generated"))

    if not all((secret_id, secret_key, bucket, region, public_base_url)):
        return None

    return COSConfig(
        secret_id=secret_id,
        secret_key=secret_key,
        bucket=bucket,
        region=region,
        public_base_url=public_base_url,
        key_prefix=key_prefix,
    )


def _create_cos_client(config: COSConfig):
    from qcloud_cos import CosConfig, CosS3Client

    cos_config = CosConfig(
        Region=config.region,
        SecretId=config.secret_id,
        SecretKey=config.secret_key,
        Scheme="https",
    )
    return CosS3Client(cos_config)


class StorageService:
    def __init__(self) -> None:
        self.cos_config = load_cos_config()

    def is_cos_enabled(self) -> bool:
        return self.cos_config is not None

    def build_object_key(self, filename: str) -> str:
        safe_filename = os.path.basename(filename)
        if not safe_filename:
            raise ValueError("filename is required")

        if self.cos_config and self.cos_config.key_prefix:
            return f"{self.cos_config.key_prefix}/{safe_filename}"
        return safe_filename

    def build_public_url(self, key: str) -> str:
        if not self.cos_config:
            raise RuntimeError("COS is not configured")
        return f"{self.cos_config.public_base_url}/{key.lstrip('/')}"

    def upload_local_file(
        self,
        local_path: str,
        filename: str,
        content_type: str | None = None,
    ) -> str | None:
        if not self.cos_config:
            return None

        key = self.build_object_key(filename)
        client = _create_cos_client(self.cos_config)
        client.upload_file(
            Bucket=self.cos_config.bucket,
            Key=key,
            LocalFilePath=local_path,
            EnableMD5=True,
        )
        return self.build_public_url(key)


storage_service = StorageService()
