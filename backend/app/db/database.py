"""
Database connection setup for LossGuard.
Uses SQLite for now (fast, zero-config). Can swap to Postgres later by
just changing DATABASE_URL — SQLAlchemy handles the rest.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./lossguard.db"

# check_same_thread=False needed for SQLite + FastAPI (multiple requests,
# same thread pool)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=20,
    max_overflow=40,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session per request, closes after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()