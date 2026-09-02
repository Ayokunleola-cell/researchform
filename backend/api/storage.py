"""
S3-compatible storage operations with local filesystem fallback
When MinIO/S3 is unavailable (local dev without Docker), files are stored in ./local_storage/
"""
import hashlib
import io
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional
from config import settings

# Local storage root (used when S3 is unavailable)
LOCAL_STORAGE_ROOT = Path(__file__).parent / "local_storage"
LOCAL_STORAGE_ROOT.mkdir(exist_ok=True)

_S3_AVAILABLE: Optional[bool] = None


def _check_s3():
    global _S3_AVAILABLE
    if _S3_AVAILABLE is not None:
        return _S3_AVAILABLE
    try:
        import boto3
        from botocore.exceptions import ClientError, EndpointResolutionError, NoRegionError
        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
        client.list_buckets()
        _S3_AVAILABLE = True
    except Exception:
        _S3_AVAILABLE = False
    return _S3_AVAILABLE


def _s3_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    )


def _local_path(bucket: str, key: str) -> Path:
    p = LOCAL_STORAGE_ROOT / bucket / key
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# removed top-level magic import
ALLOWED_MIMES = [
    "application/pdf", "image/jpeg", "image/png", "text/csv", 
    "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip", "application/x-zip-compressed", "application/json",
    "application/octet-stream" # some valid binary datasets
]

def validate_file_security(file_bytes: bytes):
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ValueError(f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB")
        
    try:
        import magic
        detected_mime = magic.from_buffer(file_bytes, mime=True)
    except Exception:
        detected_mime = "application/octet-stream"
    if detected_mime not in ALLOWED_MIMES:
        if detected_mime == "text/plain":
            pass # Often happens for CSVs
        else:
            raise ValueError(f"Security Policy: File type {detected_mime} is forbidden.")

def upload_file(
    file_bytes: bytes,
    bucket: str,
    key: str,
    content_type: str = "application/octet-stream",
) -> str:
    validate_file_security(file_bytes)
    
    if _check_s3():
        try:
            client = _s3_client()
            client.put_object(
                Bucket=bucket, Key=key, Body=file_bytes,
                ContentType=content_type, ServerSideEncryption="AES256",
            )
            return key
        except Exception:
            pass
    # Local fallback
    _local_path(bucket, key).write_bytes(file_bytes)
    return key

def upload_file_obj(file_obj, bucket: str, key: str, content_type: str = "application/octet-stream") -> str:
    data = file_obj.read() if hasattr(file_obj, "read") else file_obj
    return upload_file(data, bucket, key, content_type)


def get_presigned_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    if _check_s3():
        try:
            client = _s3_client()
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except Exception:
            pass
    # Local fallback — return a local API URL the frontend can use
    return f"http://localhost:8000/api/local-storage/{bucket}/{key}"

def copy_between_buckets(src_bucket: str, src_key: str, dst_bucket: str, dst_key: str) -> str:
    if _check_s3():
        try:
            client = _s3_client()
            client.copy_object(
                CopySource={"Bucket": src_bucket, "Key": src_key},
                Bucket=dst_bucket, Key=dst_key,
                ServerSideEncryption="AES256",
            )
            return dst_key
        except Exception:
            pass
    # Local fallback
    src = _local_path(src_bucket, src_key)
    dst = _local_path(dst_bucket, dst_key)
    if src.exists():
        shutil.copy2(src, dst)
    return dst_key


def delete_file(bucket: str, key: str) -> bool:
    if _check_s3():
        try:
            _s3_client().delete_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            pass
    p = _local_path(bucket, key)
    if p.exists():
        p.unlink()
    return True


def compute_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def get_file_bytes(bucket: str, key: str) -> bytes:
    if _check_s3():
        try:
            response = _s3_client().get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except Exception:
            pass
    p = _local_path(bucket, key)
    if p.exists():
        return p.read_bytes()
    raise FileNotFoundError(f"File not found: {bucket}/{key}")


def make_dataset_key(seller_id: str, dataset_id: str, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return f"datasets/{seller_id}/{dataset_id}/{uuid.uuid4().hex}{ext}"


def make_thumbnail_key(dataset_id: str) -> str:
    return f"thumbnails/{dataset_id}.jpg"


def make_sample_key(dataset_id: str) -> str:
    return f"samples/{dataset_id}_preview.csv"


def generate_thumbnail_from_csv(file_bytes: bytes, dataset_id: str) -> Optional[str]:
    try:
        from PIL import Image, ImageDraw
        import pandas as pd

        df = pd.read_csv(io.BytesIO(file_bytes), nrows=5)
        n_rows_hint = "?"
        try:
            full = pd.read_csv(io.BytesIO(file_bytes))
            n_rows_hint = str(len(full))
        except Exception:
            pass

        img = Image.new("RGB", (400, 200), color=(225, 245, 238))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 400, 60], fill=(15, 110, 86))
        draw.text((20, 15), "DataNest Dataset", fill="white")
        draw.text((20, 80), f"Columns: {len(df.columns)}", fill=(44, 44, 42))
        draw.text((20, 110), f"Rows: {n_rows_hint}", fill=(44, 44, 42))
        draw.text((20, 140), f"Preview: {', '.join(df.columns[:4])}", fill=(136, 135, 128))

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        buf.seek(0)
        key = make_thumbnail_key(dataset_id)
        upload_file(buf.read(), settings.S3_BUCKET_THUMBNAILS, key, "image/jpeg")
        return key
    except Exception:
        return None


def extract_csv_sample(file_bytes: bytes, dataset_id: str, n_rows: int = 10) -> Optional[str]:
    try:
        import pandas as pd
        df = pd.read_csv(io.BytesIO(file_bytes), nrows=n_rows)
        csv_bytes = df.to_csv(index=False).encode()
        key = make_sample_key(dataset_id)
        upload_file(csv_bytes, settings.S3_BUCKET_SAMPLES, key, "text/csv")
        return key
    except Exception:
        return None


def ensure_buckets_exist():
    """Create S3 buckets if using real S3/MinIO, else ensure local dirs exist."""
    buckets = [
        settings.S3_BUCKET_DATASETS,
        settings.S3_BUCKET_THUMBNAILS,
        settings.S3_BUCKET_SAMPLES,
        settings.S3_BUCKET_ID_DOCS,
    ]
    if _check_s3():
        client = _s3_client()
        for bucket in buckets:
            try:
                client.head_bucket(Bucket=bucket)
            except Exception:
                try:
                    client.create_bucket(Bucket=bucket)
                except Exception:
                    pass
    else:
        # Ensure local dirs exist
        for bucket in buckets:
            (LOCAL_STORAGE_ROOT / bucket).mkdir(parents=True, exist_ok=True)
