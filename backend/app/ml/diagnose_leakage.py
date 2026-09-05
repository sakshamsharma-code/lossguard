"""
Diagnostic: check per-feature separation power to find why the model is
scoring suspiciously well (likely one feature is acting as a near-perfect
proxy for the label, undermining the "behavior alone is weak" thesis).

Run with: python -m app.ml.diagnose_leakage
"""

import pandas as pd

FEATURE_COLS = [
    "return_rate_30d",
    "return_rate_90d",
    "avg_order_value",
    "time_since_signup_days",
    "return_to_purchase_gap_days",
    "category_return_concentration",
]


def main():
    df = pd.read_csv("data/behavioral_features.csv")

    print("Per-feature mean/std by fraud label — look for features where")
    print("fraud and genuine barely overlap (mean gap >> combined std):\n")

    for col in FEATURE_COLS:
        stats = df.groupby("is_fraud")[col].agg(["mean", "std", "min", "max"])
        print(f"--- {col} ---")
        print(stats.round(3))
        genuine_mean = stats.loc[False, "mean"]
        fraud_mean = stats.loc[True, "mean"]
        pooled_std = (stats.loc[False, "std"] + stats.loc[True, "std"]) / 2
        gap_ratio = abs(fraud_mean - genuine_mean) / max(pooled_std, 0.001)
        print(f"   -> separation ratio (higher = more suspicious): {gap_ratio:.2f}\n")


if __name__ == "__main__":
    main()