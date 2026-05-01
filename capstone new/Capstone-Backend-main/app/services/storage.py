import os
from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, UploadFile, status


def _get_optional_env(keys: Sequence[str]) -> Optional[str]:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None


def _get_required_env(keys: Sequence[str]) -> str:
    value = _get_optional_env(keys)
    if not value:
        key_names = ", ".join(keys)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Missing required environment variable. Set one of: {key_names}",
        )
    return value


def _create_r2_client() -> Any:
    endpoint_url = _get_required_env(("CLOUDFLARE_R2_ENDPOINT", "R2_ENDPOINT"))
    access_key_id = _get_required_env(("CLOUDFLARE_R2_ACCESS_KEY_ID", "R2_ACCESS_KEY_ID"))
    secret_access_key = _get_required_env(("CLOUDFLARE_R2_SECRET_ACCESS_KEY", "R2_SECRET_ACCESS_KEY"))
    region = _get_optional_env(("CLOUDFLARE_R2_REGION", "R2_REGION")) or "auto"

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _build_object_key(filename: str, folder: str) -> str:
    extension = Path(filename).suffix.lower()
    clean_folder = folder.strip().strip("/")
    clean_folder = clean_folder or "uploads"
    return f"{clean_folder}/{uuid4().hex}{extension}"


def _get_file_size(upload_file: UploadFile) -> int:
    current_position = upload_file.file.tell()
    upload_file.file.seek(0, os.SEEK_END)
    file_size = upload_file.file.tell()
    upload_file.file.seek(current_position)
    return file_size


def _build_public_url(object_key: str) -> str:
    public_base_url = _get_optional_env(("CLOUDFLARE_R2_PUBLIC_URL", "R2_PUBLIC_BASE_URL"))
    if public_base_url:
        return f"{public_base_url.rstrip('/')}/{object_key}"

    endpoint_url = _get_optional_env(("CLOUDFLARE_R2_ENDPOINT", "R2_ENDPOINT"))
    bucket_name = _get_required_env(("CLOUDFLARE_R2_BUCKET_NAME", "R2_BUCKET_NAME"))

    if endpoint_url:
        return f"{endpoint_url.rstrip('/')}/{bucket_name}/{object_key}"

    account_id = _get_optional_env(("R2_ACCOUNT_ID",))
    if account_id:
        return f"https://{bucket_name}.{account_id}.r2.cloudflarestorage.com/{object_key}"

    return f"{bucket_name}/{object_key}"


def _get_max_file_size() -> int:
    raw_value = _get_optional_env(("CLOUDFLARE_R2_MAX_FILE_SIZE_BYTES", "R2_MAX_FILE_SIZE_BYTES")) or "10485760"
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid file size configuration for CLOUDFLARE_R2_MAX_FILE_SIZE_BYTES",
        ) from exc

    if value <= 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLOUDFLARE_R2_MAX_FILE_SIZE_BYTES must be greater than 0",
        )

    return value


def upload_file_to_r2(
    file: UploadFile,
    folder: str = "uploads",
    allowed_content_prefix: Optional[str] = None,
) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File name is required",
        )

    content_type = file.content_type or "application/octet-stream"
    if allowed_content_prefix and not content_type.startswith(allowed_content_prefix):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only files with content type '{allowed_content_prefix}*' are allowed",
        )

    file_size = _get_file_size(file)
    max_file_size = _get_max_file_size()
    if file_size > max_file_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max allowed size is {max_file_size} bytes",
        )

    bucket_name = _get_required_env(("CLOUDFLARE_R2_BUCKET_NAME", "R2_BUCKET_NAME"))
    object_key = _build_object_key(file.filename, folder)

    try:
        client = _create_r2_client()
        file.file.seek(0)
        client.upload_fileobj(
            Fileobj=file.file,
            Bucket=bucket_name,
            Key=object_key,
            ExtraArgs={"ContentType": content_type},
        )
    except (BotoCoreError, ClientError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to upload file to Cloudflare R2",
        )

    return {
        "filename": file.filename,
        "key": object_key,
        "url": _build_public_url(object_key),
        "content_type": content_type,
        "size": file_size,
    }
