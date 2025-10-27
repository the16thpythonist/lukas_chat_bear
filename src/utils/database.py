"""
Database connection and session management.

Provides SQLAlchemy engine and session factory for database operations.
"""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.utils.logger import logger


# Database URL from environment or default
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/lukas.db")

# Create SQLAlchemy engine
# For SQLite, enable foreign keys and WAL mode for better concurrency
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging (useful for debugging)
    pool_pre_ping=True,  # Verify connections before using
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)


# Enable SQLite optimizations
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Set SQLite pragmas for better performance.

    - foreign_keys: Enable foreign key constraints
    - journal_mode: Use Write-Ahead Logging for better concurrency
    - synchronous: NORMAL provides good balance of safety and performance
    """
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
        logger.debug("SQLite pragmas set: foreign_keys=ON, journal_mode=WAL, synchronous=NORMAL")


# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db_session() -> Session:
    """
    Create a new database session.

    Returns:
        SQLAlchemy Session instance

    Example:
        session = get_db_session()
        try:
            # Use session
            session.commit()
        finally:
            session.close()
    """
    return SessionLocal()


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Automatically commits on success or rolls back on exception.

    Yields:
        SQLAlchemy Session instance

    Example:
        with get_db() as db:
            user = db.query(TeamMember).first()
            # Changes are auto-committed
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """
    Initialize the database.

    This should be called by Alembic migrations, not directly.
    Use: alembic upgrade head
    """
    from src.models import Base
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")


def check_db_connection() -> bool:
    """
    Check if database connection is working.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
