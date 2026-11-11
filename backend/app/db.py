import logging
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _create_db_engine():
    """Create a resilient SQLAlchemy engine supporting Cloud SQL, PostgreSQL, and SQLite fallback."""
    db_url = settings.database_url

    # Check for SQLite
    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite:///", "")
        if db_path and db_path != ":memory:":
            try:
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            except OSError:
                # In serverless/read-only container environments, redirect SQLite to /tmp
                db_url = "sqlite:////tmp/billwise.db"

        return create_engine(db_url, connect_args={"check_same_thread": False})

    # PostgreSQL / Cloud SQL configuration with connection pooling
    try:
        return create_engine(
            db_url,
            pool_pre_ping=True,      # Verify connection validity before dispensing from pool
            pool_size=5,             # Concurrency-safe connection pool for container instances
            max_overflow=10,
            pool_recycle=300,        # Recycle idle connections every 5 minutes
        )
    except Exception as e:
        logger.warning(
            "Failed to initialize database engine with %s (%s). Falling back to SQLite.",
            db_url,
            e,
        )
        fallback_url = "sqlite:////tmp/billwise.db" if os.getenv("K_SERVICE") else "sqlite:///./billwise.db"
        return create_engine(fallback_url, connect_args={"check_same_thread": False})


engine = _create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Optional Google Cloud Firestore Support
_firestore_client = None


def get_firestore_client():
    """Initialize and cache Google Cloud Firestore client if configured."""
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client

    if not (settings.use_firestore or settings.firestore_project_id or settings.database_url.lower() == "firestore"):
        return None

    try:
        from google.cloud import firestore

        project_id = settings.firestore_project_id or settings.google_cloud_project or None
        _firestore_client = firestore.Client(project=project_id)
        logger.info("Initialized Firestore client for project: %s", project_id or "default")
        return _firestore_client
    except Exception as err:
        logger.warning("Could not initialize Firestore client: %s. Using SQL database.", err)
        return None


def is_firestore_enabled() -> bool:
    """Check whether Firestore mode is active and available."""
    return get_firestore_client() is not None
