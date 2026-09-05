"""
Feature engineering for LossGuard ML baseline.

Builds a per-RETURN feature table (one row per return, since that's the
unit of decision — "should this specific return be flagged?").

Behavioral (soft) features only, at this stage — structural/graph features
get joined in separately later (app/graph/ring_detector.py) so we can
measure, in isolation, how much behavior alone can predict (Model 1),
then how much graph adds on top (Model 2+). See research-notes.md §3
("research experiment" comparing Model 1..4).

Run with: python -m app.ml.features   (prints a preview + saves CSV)
"""

import pandas as pd
from datetime import date

from app.db.database import SessionLocal
from app.db import models


def load_raw(db):
    users = pd.read_sql(db.query(models.User).statement, db.bind)
    orders = pd.read_sql(db.query(models.Order).statement, db.bind)
    returns = pd.read_sql(db.query(models.Return).statement, db.bind)
    return users, orders, returns


def build_features(users: pd.DataFrame, orders: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    returns["return_date"] = pd.to_datetime(returns["return_date"])
    users["signup_date"] = pd.to_datetime(users["signup_date"])

    rows = []

    # Precompute per-user order/return aggregates once (avoid re-querying per row)
    orders_by_user = orders.groupby("user_id")
    returns_by_user = returns.groupby("user_id")

    for _, ret in returns.iterrows():
        user_id = ret["user_id"]
        order_id = ret["order_id"]
        return_date = ret["return_date"]

        user_orders = orders_by_user.get_group(user_id) if user_id in orders_by_user.groups else pd.DataFrame()
        user_returns = returns_by_user.get_group(user_id) if user_id in returns_by_user.groups else pd.DataFrame()

        # windows relative to THIS return's date
        window_30 = return_date - pd.Timedelta(days=30)
        window_90 = return_date - pd.Timedelta(days=90)

        orders_30 = user_orders[user_orders["order_date"] >= window_30]
        orders_90 = user_orders[user_orders["order_date"] >= window_90]
        returns_30 = user_returns[user_returns["return_date"] >= window_30]
        returns_90 = user_returns[user_returns["return_date"] >= window_90]

        return_rate_30d = len(returns_30) / len(orders_30) if len(orders_30) > 0 else 0.0
        return_rate_90d = len(returns_90) / len(orders_90) if len(orders_90) > 0 else 0.0

        avg_order_value = user_orders["order_value"].mean() if len(user_orders) > 0 else 0.0

        user_signup = users.loc[users["user_id"] == user_id, "signup_date"].values[0]
        time_since_signup_days = (return_date - pd.Timestamp(user_signup)).days

        this_order = orders[orders["order_id"] == order_id]
        order_date_val = this_order["order_date"].values[0] if len(this_order) > 0 else return_date
        return_to_purchase_gap_days = (return_date - pd.Timestamp(order_date_val)).days

        # category concentration: share of user's returns in the most
        # common category among their orders
        if len(user_orders) > 0:
            top_cat_share = user_orders["category"].value_counts(normalize=True).iloc[0]
        else:
            top_cat_share = 0.0

        order_value = this_order["order_value"].values[0] if len(this_order) > 0 else 0.0

        rows.append({
            "return_id": ret["return_id"],
            "user_id": user_id,
            "order_id": order_id,
            "return_rate_30d": round(return_rate_30d, 4),
            "return_rate_90d": round(return_rate_90d, 4),
            "avg_order_value": round(avg_order_value, 2),
            "time_since_signup_days": max(time_since_signup_days, 0),
            "return_to_purchase_gap_days": max(return_to_purchase_gap_days, 0),
            "category_return_concentration": round(top_cat_share, 4),
            "order_value": round(order_value, 2),
            "refund_amount": round(ret["refund_amount"], 2),
            "is_fraud": bool(ret["is_fraud"]),
        })

    return pd.DataFrame(rows)


def main():
    db = SessionLocal()
    users, orders, returns = load_raw(db)
    db.close()

    features = build_features(users, orders, returns)
    features.to_csv("data/behavioral_features.csv", index=False)

    print(f"✅ Built {len(features)} feature rows -> data/behavioral_features.csv")
    print(f"\nFraud rate in feature set: {features['is_fraud'].mean() * 100:.1f}%")
    print("\nPreview:")
    print(features.head())
    print("\nFeature summary by fraud label:")
    print(features.groupby("is_fraud")[
        ["return_rate_30d", "return_rate_90d", "avg_order_value", "time_since_signup_days"]
    ].mean().round(3))


if __name__ == "__main__":
    main()