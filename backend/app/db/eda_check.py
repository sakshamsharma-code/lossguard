"""
Quick EDA / sanity check on the synthetic dataset.
Run with: python -m app.db.eda_check
"""

import pandas as pd
from app.db.database import SessionLocal
from app.db import models


def load_dataframes(db):
    users = pd.read_sql(db.query(models.User).statement, db.bind)
    orders = pd.read_sql(db.query(models.Order).statement, db.bind)
    returns = pd.read_sql(db.query(models.Return).statement, db.bind)
    return users, orders, returns


def main():
    db = SessionLocal()
    users, orders, returns = load_dataframes(db)
    db.close()

    print("=" * 60)
    print("BASIC COUNTS")
    print("=" * 60)
    print(f"Users:   {len(users)}")
    print(f"Orders:  {len(orders)}")
    print(f"Returns: {len(returns)}")

    print("\n" + "=" * 60)
    print("RETURN RATE BY CATEGORY (genuine vs fraud mixed in)")
    print("=" * 60)
    merged = orders.merge(returns[["order_id", "is_fraud"]], on="order_id", how="left")
    merged["returned"] = merged["is_fraud"].notna()
    cat_stats = merged.groupby("category")["returned"].mean() * 100
    print(cat_stats.round(1))

    print("\n" + "=" * 60)
    print("RETURN RATE PER USER — genuine vs fraud-ring")
    print("=" * 60)
    user_returns = returns.groupby("user_id").size().rename("n_returns")
    user_orders = orders.groupby("user_id").size().rename("n_orders")
    user_stats = pd.concat([user_orders, user_returns], axis=1).fillna(0)
    user_stats["return_rate"] = user_stats["n_returns"] / user_stats["n_orders"]

    fraud_user_ids = set(returns[returns["is_fraud"] == True]["user_id"])
    user_stats["is_fraud_ring_member"] = user_stats.index.isin(fraud_user_ids)

    print(user_stats.groupby("is_fraud_ring_member")["return_rate"].describe()[
        ["mean", "std", "min", "max"]
    ].round(3))

    print("\n⚠️  Key check: if fraud-ring and genuine return_rate ranges OVERLAP")
    print("    significantly, that's expected — it proves behavioral signal")
    print("    alone can't cleanly separate them (our core thesis).")

    print("\n" + "=" * 60)
    print("SHARED IDENTIFIER CHECK (structural signal sanity check)")
    print("=" * 60)
    dup_devices = users["device_id"].value_counts()
    shared_devices = dup_devices[dup_devices > 1]
    print(f"Devices shared by >1 user: {len(shared_devices)}")
    print(f"Users involved in device-sharing: {shared_devices.sum()}")

    dup_addr = users["address_id"].value_counts()
    shared_addr = dup_addr[dup_addr > 1]
    print(f"Addresses shared by >1 user: {len(shared_addr)}")

    dup_pay = users["payment_method_id"].value_counts()
    shared_pay = dup_pay[dup_pay > 1]
    print(f"Payment methods shared by >1 user: {len(shared_pay)}")

    print("\n✅ EDA complete. If shared-identifier counts are near 0, the fraud")
    print("   ring generation logic isn't working — check seed_data.py.")


if __name__ == "__main__":
    main()