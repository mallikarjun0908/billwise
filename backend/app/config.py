import os
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database configuration
    database_url: str = "sqlite:///./billwise.db"
    db_host: str | None = None
    db_port: int = 5432
    db_user: str | None = None
    db_pass: str | None = None
    db_name: str | None = None
    cloud_sql_connection_name: str | None = None

    # Firestore configuration
    use_firestore: bool = False
    firestore_project_id: str | None = None
    google_cloud_project: str | None = None

    # Storage configuration
    upload_dir: str = "./uploads"
    # When STORE_UPLOADS is true, stores bill uploads (local disk or Firebase Storage).
    # On public servers or when privacy is prioritized, set STORE_UPLOADS=false.
    store_uploads: bool = True
    firebase_storage_bucket: str = ""
    storage_backend: str = "local"  # "local" | "firebase" | "gcs"

    # AI & Services
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    max_upload_mb: int = 10
    port: int = 8080

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_ignore_empty=True,
    )

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, v: str) -> str:
        """Hosts hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver named."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @model_validator(mode="after")
    def _resolve_cloud_config(self) -> "Settings":
        # Resolve Google Cloud Project ID if set in standard env vars
        if not self.google_cloud_project:
            self.google_cloud_project = (
                os.getenv("GOOGLE_CLOUD_PROJECT")
                or os.getenv("GCP_PROJECT")
                or os.getenv("GCLOUD_PROJECT")
            )
        if not self.firestore_project_id and self.google_cloud_project:
            self.firestore_project_id = self.google_cloud_project

        # If Cloud SQL or DB parameters are provided and database_url was not an explicit Postgres URL
        if self.db_user and self.db_name and (self.database_url.startswith("sqlite") or self.cloud_sql_connection_name):
            pwd = f":{self.db_pass}" if self.db_pass else ""
            if self.cloud_sql_connection_name:
                self.database_url = (
                    f"postgresql+psycopg://{self.db_user}{pwd}@/{self.db_name}"
                    f"?host=/cloudsql/{self.cloud_sql_connection_name}"
                )
            elif self.db_host:
                self.database_url = (
                    f"postgresql+psycopg://{self.db_user}{pwd}@{self.db_host}:{self.db_port}/{self.db_name}"
                )

        # Detect Firebase Cloud Storage bucket from standard Firebase env vars if unset
        if not self.firebase_storage_bucket:
            self.firebase_storage_bucket = (
                os.getenv("FIREBASE_STORAGE_BUCKET")
                or os.getenv("GCS_BUCKET")
                or os.getenv("STORAGE_BUCKET")
                or ""
            )

        # If firebase storage bucket is configured, default storage_backend to firebase
        if self.firebase_storage_bucket and self.storage_backend == "local":
            self.storage_backend = "firebase"

        return self


settings = Settings()
