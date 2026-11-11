import logging
import uuid
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)

# Cached Cloud Storage client
_gcs_client = None


def get_storage_client():
    """Retrieve or initialize the Google Cloud / Firebase Storage client."""
    global _gcs_client
    if _gcs_client is not None:
        return _gcs_client

    try:
        from google.cloud import storage

        project_id = settings.firestore_project_id or settings.google_cloud_project or None
        _gcs_client = storage.Client(project=project_id)
        return _gcs_client
    except Exception as err:
        logger.warning("Could not initialize Google Cloud Storage client: %s", err)
        return None


def save_upload(data: bytes, content_type: str) -> str:
    """Save an uploaded bill file to Firebase Cloud Storage or local disk.

    Args:
        data: Raw file bytes.
        content_type: MIME type of the file.

    Returns:
        The stored path/URI or 'not stored' if store_uploads is disabled.
    """
    if not settings.store_uploads:
        return "not stored"

    ext_map = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
    ext = ext_map.get(content_type, ".bin")
    file_id = f"{uuid.uuid4().hex}{ext}"

    # Use Firebase Cloud Storage if configured
    if settings.firebase_storage_bucket:
        try:
            client = get_storage_client()
            if client:
                bucket = client.bucket(settings.firebase_storage_bucket)
                blob_name = f"bills/{file_id}"
                blob = bucket.blob(blob_name)
                blob.upload_from_string(data, content_type=content_type)
                cloud_uri = f"gs://{settings.firebase_storage_bucket}/{blob_name}"
                logger.info("Uploaded bill to Firebase Cloud Storage: %s", cloud_uri)
                return cloud_uri
        except Exception as err:
            logger.warning(
                "Firebase Cloud Storage upload to bucket '%s' failed: %s. Falling back to local disk.",
                settings.firebase_storage_bucket,
                err,
            )

    # Local disk fallback
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    local_file = upload_path / file_id
    local_file.write_bytes(data)
    return str(local_file)


def read_upload(stored_path: str) -> bytes | None:
    """Read a stored bill from Firebase Cloud Storage or local disk."""
    if not stored_path or stored_path == "not stored":
        return None

    if stored_path.startswith("gs://"):
        try:
            parts = stored_path[5:].split("/", 1)
            if len(parts) == 2:
                bucket_name, blob_name = parts
                client = get_storage_client()
                if client:
                    bucket = client.bucket(bucket_name)
                    blob = bucket.blob(blob_name)
                    return blob.download_as_bytes()
        except Exception as err:
            logger.warning("Failed to read from Cloud Storage %s: %s", stored_path, err)
            return None

    local_path = Path(stored_path)
    if local_path.is_file():
        return local_path.read_bytes()

    return None
