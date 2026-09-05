"""
Run this once to create all tables: `python -m app.db.init_db`
"""

from app.db.database import engine, Base
from app.db import models  # noqa: F401 — import so tables register on Base


def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created: users, orders, returns, device_address_payment_links")


if __name__ == "__main__":
    init_db()