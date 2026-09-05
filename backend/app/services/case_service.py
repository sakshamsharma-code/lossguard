"""
Case service — composes: DB data -> behavioral features -> graph features ->
ML risk score -> expected loss -> decision tier.
"""

import pandas as pd
from app.db.database import SessionLocal
from app.db import models
from app.ml.predict import predict_risk
from app.graph.ring_detector import load_links, build_graph, project_to_user_graph, get_cluster_info_for_user
from app.decision.decision_engine import decide_tier
from app.models.schemas import CaseEvidence, ClusterInfo, CaseSummary

_graph_cache = None


def _get_cached_graph():
    global _graph_cache
    if _graph_cache is None:
        db = SessionLocal()
        links = load_links(db)
        db.close()
        G = build_graph(links)
        _graph_cache = project_to_user_graph(G)
    return _graph_cache


def _get_shared_counts_for_user(db, user_id: str) -> dict:
    all_links = pd.read_sql(db.query(models.DeviceAddressPaymentLink).statement, db.bind)
    user_row = all_links[all_links["user_id"] == user_id]
    if user_row.empty:
        return {"shared_device_count": 0, "shared_address_count": 0, "shared_payment_method_count": 0}

    device_id = user_row["device_id"].values[0]
    address_id = user_row["address_id"].values[0]
    payment_id = user_row["payment_method_id"].values[0]

    shared_device = max(all_links[all_links["device_id"] == device_id]["user_id"].nunique() - 1, 0)
    shared_address = max(all_links[all_links["address_id"] == address_id]["user_id"].nunique() - 1, 0)
    shared_payment = max(all_links[all_links["payment_method_id"] == payment_id]["user_id"].nunique() - 1, 0)

    return {
        "shared_device_count": int(shared_device),
        "shared_address_count": int(shared_address),
        "shared_payment_method_count": int(shared_payment),
    }


def _compute_behavioral_features(db, ret: models.Return) -> dict:
    user_id = ret.user_id
    return_date = pd.Timestamp(ret.return_date)

    orders = pd.read_sql(db.query(models.Order).filter(models.Order.user_id == user_id).statement, db.bind)
    returns = pd.read_sql(db.query(models.Return).filter(models.Return.user_id == user_id).statement, db.bind)
    user = db.query(models.User).filter(models.User.user_id == user_id).first()

    orders["order_date"] = pd.to_datetime(orders["order_date"])
    returns["return_date"] = pd.to_datetime(returns["return_date"])

    window_30 = return_date - pd.Timedelta(days=30)
    window_90 = return_date - pd.Timedelta(days=90)

    orders_30 = orders[orders["order_date"] >= window_30]
    orders_90 = orders[orders["order_date"] >= window_90]
    returns_30 = returns[returns["return_date"] >= window_30]
    returns_90 = returns[returns["return_date"] >= window_90]

    return_rate_30d = len(returns_30) / len(orders_30) if len(orders_30) > 0 else 0.0
    return_rate_90d = len(returns_90) / len(orders_90) if len(orders_90) > 0 else 0.0
    avg_order_value = orders["order_value"].mean() if len(orders) > 0 else 0.0
    time_since_signup = (return_date - pd.Timestamp(user.signup_date)).days if user else 0

    this_order = orders[orders["order_id"] == ret.order_id]
    order_date_val = this_order["order_date"].values[0] if len(this_order) > 0 else return_date
    return_to_purchase_gap = (return_date - pd.Timestamp(order_date_val)).days

    top_cat_share = orders["category"].value_counts(normalize=True).iloc[0] if len(orders) > 0 else 0.0
    order_value = this_order["order_value"].values[0] if len(this_order) > 0 else 0.0

    return {
        "return_rate_30d": round(float(return_rate_30d), 4),
        "return_rate_90d": round(float(return_rate_90d), 4),
        "avg_order_value": round(float(avg_order_value), 2),
        "time_since_signup_days": max(int(time_since_signup), 0),
        "return_to_purchase_gap_days": max(int(return_to_purchase_gap), 0),
        "category_return_concentration": round(float(top_cat_share), 4),
        "order_value": round(float(order_value), 2),
        "customer_lifetime_value": round(float(user.ltv_score), 2) if user else 0.0,
    }


def build_case_evidence(return_id: str) -> CaseEvidence:
    db = SessionLocal()
    try:
        ret = db.query(models.Return).filter(models.Return.return_id == return_id).first()
        if ret is None:
            raise ValueError(f"Return {return_id} not found")

        behavioral = _compute_behavioral_features(db, ret)
        user_graph = _get_cached_graph()
        cluster = get_cluster_info_for_user(user_graph, ret.user_id)
        shared_counts = _get_shared_counts_for_user(db, ret.user_id)

        model_input = {
            "return_rate_30d": behavioral["return_rate_30d"],
            "return_rate_90d": behavioral["return_rate_90d"],
            "avg_order_value": behavioral["avg_order_value"],
            "time_since_signup_days": behavioral["time_since_signup_days"],
            "return_to_purchase_gap_days": behavioral["return_to_purchase_gap_days"],
            "category_return_concentration": behavioral["category_return_concentration"],
            "cluster_size": cluster["cluster_size"],
            "cluster_density": cluster["cluster_density"],
            **shared_counts,
        }

        risk_score = predict_risk(model_input)
        decision = decide_tier(risk_score, ret.refund_amount)

        return CaseEvidence(
            return_id=ret.return_id,
            user_id=ret.user_id,
            return_rate_30d=behavioral["return_rate_30d"],
            return_rate_90d=behavioral["return_rate_90d"],
            avg_order_value=behavioral["avg_order_value"],
            time_since_signup_days=behavioral["time_since_signup_days"],
            shared_device_count=shared_counts["shared_device_count"],
            shared_address_count=shared_counts["shared_address_count"],
            shared_payment_method_count=shared_counts["shared_payment_method_count"],
            cluster_info=ClusterInfo(
                cluster_size=cluster["cluster_size"],
                cluster_density=cluster["cluster_density"],
                linked_user_ids=cluster["linked_user_ids"],
            ),
            order_value=behavioral["order_value"],
            refund_amount=ret.refund_amount,
            customer_lifetime_value=behavioral["customer_lifetime_value"],
            risk_score=risk_score,
            expected_loss=decision.expected_loss,
            decision_tier=decision.decision_tier,
        )
    finally:
        db.close()


def list_case_summaries(limit: int = 100) -> list:
    db = SessionLocal()
    try:
        # Use random sampling instead of first-N, so fraud-ring cases
        # (inserted later in seed order) aren't systematically excluded
        # from a capped-limit sample — matters for both /cases and /stats.
        all_returns = db.query(models.Return).all()
        import random
        random.seed(7)
        if len(all_returns) > limit:
            returns = random.sample(all_returns, limit)
        else:
            returns = all_returns

        summaries = []
        for ret in returns:
            evidence = build_case_evidence(ret.return_id)
            summaries.append(CaseSummary(
                return_id=evidence.return_id,
                user_id=evidence.user_id,
                risk_score=evidence.risk_score,
                expected_loss=evidence.expected_loss,
                decision_tier=evidence.decision_tier,
                refund_amount=evidence.refund_amount,
            ))
        summaries.sort(key=lambda s: s.expected_loss, reverse=True)
        return summaries
    finally:
        db.close()