"""
SQLAlchemy ORM models — mirrors docs/dataset-schema.md exactly.
Four tables: users, orders, returns, device_address_payment_links.
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True, index=True)
    signup_date = Column(Date, nullable=False)
    device_id = Column(String, index=True)
    address_id = Column(String, index=True)
    payment_method_id = Column(String, index=True)
    ltv_score = Column(Float, default=0.0)  # customer_lifetime_value proxy

    orders = relationship("Order", back_populates="user")
    returns = relationship("Return", back_populates="user")


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.user_id"), index=True)
    order_date = Column(Date, nullable=False)
    order_value = Column(Float, nullable=False)
    category = Column(String, index=True)  # e.g. apparel, electronics, beauty

    user = relationship("User", back_populates="orders")
    return_record = relationship("Return", back_populates="order", uselist=False)


class Return(Base):
    __tablename__ = "returns"

    return_id = Column(String, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.order_id"), index=True)
    user_id = Column(String, ForeignKey("users.user_id"), index=True)
    return_date = Column(Date, nullable=False)
    refund_amount = Column(Float, nullable=False)
    reason_code = Column(String)

    # Ground-truth label — ONLY exists because this is synthetic training/eval
    # data. In a real deployment this would not be known in advance; it's
    # used here purely to generate realistic data and measure model
    # precision/recall against a held-out set.
    is_fraud = Column(Boolean, default=False)

    order = relationship("Order", back_populates="return_record")
    user = relationship("User", back_populates="returns")


class DeviceAddressPaymentLink(Base):
    """
    Feeds the graph engine (app/graph/ring_detector.py).
    One row per user, capturing which device/address/payment identifiers
    they used — this is what lets us build a shared-resource graph across
    users without duplicating data already on the User table.
    """
    __tablename__ = "device_address_payment_links"

    link_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), index=True)
    device_id = Column(String, index=True)
    address_id = Column(String, index=True)
    payment_method_id = Column(String, index=True)


class DecisionLog(Base):
    """Human-in-the-loop record — the only place a real action is logged."""
    __tablename__ = "decision_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    return_id = Column(String, ForeignKey("returns.return_id"), index=True)
    action = Column(String, nullable=False)
    reviewer_note = Column(String, nullable=True)
    logged_at = Column(Date, nullable=False)