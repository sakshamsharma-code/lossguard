"""
Pydantic schemas — these define the shape of API requests/responses.
Kept separate from db/models.py (SQLAlchemy) on purpose: DB shape and API
shape are allowed to diverge (e.g. CaseEvidence below is a computed
composite, not a single table).
"""

from pydantic import BaseModel
from typing import List, Optional
from datetime import date


# ---------- Basic entities ----------

class UserOut(BaseModel):
    user_id: str
    signup_date: date
    ltv_score: float

    class Config:
        from_attributes = True


class ReturnOut(BaseModel):
    return_id: str
    order_id: str
    user_id: str
    return_date: date
    refund_amount: float
    reason_code: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- Structural / graph ----------

class ClusterInfo(BaseModel):
    cluster_size: int
    cluster_density: float
    linked_user_ids: List[str]
    days_since_cluster_formed: Optional[int] = None


# ---------- Case evidence bundle (the core composite object) ----------

class CaseEvidence(BaseModel):
    return_id: str
    user_id: str

    # behavioral (soft)
    return_rate_30d: float
    return_rate_90d: float
    avg_order_value: float
    time_since_signup_days: int

    # structural (hard)
    shared_device_count: int
    shared_address_count: int
    shared_payment_method_count: int
    cluster_info: ClusterInfo

    # financial
    order_value: float
    refund_amount: float
    customer_lifetime_value: float

    # computed outputs
    risk_score: float          # 0.0 - 1.0
    expected_loss: float       # risk_score * refund_amount
    decision_tier: str         # "auto_approve" | "verify" | "manual_review"


class CaseSummary(BaseModel):
    """Lightweight version used for the dashboard list view."""
    return_id: str
    user_id: str
    risk_score: float
    expected_loss: float
    decision_tier: str
    refund_amount: float


# ---------- Decisions (human-in-the-loop) ----------

class DecisionRequest(BaseModel):
    action: str          # "approve" | "reject" | "verify"
    reviewer_note: Optional[str] = None


class DecisionResult(BaseModel):
    return_id: str
    action: str
    reviewer_note: Optional[str] = None
    logged_at: date


# ---------- Dashboard stats ----------

class DashboardStats(BaseModel):
    total_cases: int
    high_risk_count: int
    medium_risk_count: int
    potential_rings: int
    total_expected_loss_today: float


# ---------- LLM explanation ----------

class ExplainResponse(BaseModel):
    return_id: str
    summary: str