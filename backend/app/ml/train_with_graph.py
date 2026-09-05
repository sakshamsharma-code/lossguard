"""
Model 3: Behavioral + Structural (graph) features combined.

This is the core experiment from research-notes.md §3 — comparing this
against the Model 1/2 behavioral-only baseline (train.py) is how we PROVE
the graph layer's value with real numbers, not just assert it.

Run with: python -m app.ml.train_with_graph
(Run app.ml.features and app.graph.ring_detector first — this script
reads their CSV outputs.)
"""

import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    confusion_matrix, roc_auc_score
)
from xgboost import XGBClassifier

BEHAVIORAL_COLS = [
    "return_rate_30d",
    "return_rate_90d",
    "avg_order_value",
    "time_since_signup_days",
    "return_to_purchase_gap_days",
    "category_return_concentration",
]
STRUCTURAL_COLS = [
    "cluster_size",
    "cluster_density",
    "shared_device_count",
    "shared_address_count",
    "shared_payment_method_count",
]
LABEL_COL = "is_fraud"

FALSE_POSITIVE_COST_PER_CASE = 150


def load_merged():
    behavioral = pd.read_csv("data/behavioral_features.csv")
    graph = pd.read_csv("data/graph_features.csv")

    # graph_features.csv is per-user; behavioral is per-return. Join on user_id.
    merged = behavioral.merge(graph, on="user_id", how="left")

    # users with no shared resources won't appear in graph.csv edges but
    # SHOULD still have a row from get_cluster_info_for_all_users / outer
    # merge in ring_detector.py — fillna as a safety net for isolated users
    merged[STRUCTURAL_COLS] = merged[STRUCTURAL_COLS].fillna(
        {"cluster_size": 1, "cluster_density": 0.0, "shared_device_count": 0,
         "shared_address_count": 0, "shared_payment_method_count": 0}
    )
    return merged


def evaluate(model_name, y_true, y_pred, y_proba, refund_amounts):
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    auc = roc_auc_score(y_true, y_proba)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    fp_cost_total = fp * FALSE_POSITIVE_COST_PER_CASE
    fn_mask = (y_true == 1) & (y_pred == 0)
    fn_cost_total = refund_amounts[fn_mask].sum()

    print(f"\n{'=' * 60}\n{model_name}\n{'=' * 60}")
    print(f"Precision: {precision:.3f}  Recall: {recall:.3f}  F1: {f1:.3f}  AUC: {auc:.3f}")
    print(f"FPR: {fpr:.3f}  |  TP:{tp} FP:{fp} TN:{tn} FN:{fn}")
    print(f"FP cost: ₹{fp_cost_total:,.0f}  |  FN cost (money lost): ₹{fn_cost_total:,.0f}")
    print(f"Net cost: ₹{fp_cost_total + fn_cost_total:,.0f}")

    return {
        "model": model_name, "precision": precision, "recall": recall,
        "f1": f1, "auc": auc, "fpr": fpr,
        "fp_cost": fp_cost_total, "fn_cost": fn_cost_total,
        "net_cost": fp_cost_total + fn_cost_total,
    }


def main():
    df = load_merged()
    y = df[LABEL_COL].astype(int)
    refund_amounts = df["refund_amount"]

    all_cols = BEHAVIORAL_COLS + STRUCTURAL_COLS
    X_all = df[all_cols]
    X_behav_only = df[BEHAVIORAL_COLS]

    idx_train, idx_test = train_test_split(
        df.index, test_size=0.25, random_state=42, stratify=y
    )

    y_train, y_test = y.loc[idx_train], y.loc[idx_test]
    refund_test = refund_amounts.loc[idx_test]

    results = []

    def train_and_eval(X, name):
        X_train, X_test = X.loc[idx_train], X.loc[idx_test]
        fraud_ratio = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
        model = XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.1,
            scale_pos_weight=fraud_ratio, eval_metric="logloss", random_state=42
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        result = evaluate(name, y_test.values, y_pred, y_proba, refund_test.values)
        return model, result

    # Re-run behavioral-only here too (same split) for a fair apples-to-apples comparison
    _, result_behav = train_and_eval(X_behav_only, "Model 2 (recomputed): Behavioral only")
    results.append(result_behav)

    model_full, result_full = train_and_eval(X_all, "Model 3: Behavioral + Structural (graph) combined")
    results.append(result_full)

    joblib.dump(model_full, "app/ml/xgb_full_model.joblib")

    print("\n" + "=" * 60)
    print("HONEST COMPARISON — this is the number that proves graph value")
    print("=" * 60)
    summary = pd.DataFrame(results)[["model", "precision", "recall", "f1", "auc", "net_cost"]]
    print(summary.to_string(index=False))

    behav_row, full_row = results[0], results[1]
    print(f"\nRecall improvement:    {behav_row['recall']:.3f} -> {full_row['recall']:.3f} "
          f"({(full_row['recall']-behav_row['recall'])*100:+.1f} pts)")
    print(f"Precision improvement: {behav_row['precision']:.3f} -> {full_row['precision']:.3f} "
          f"({(full_row['precision']-behav_row['precision'])*100:+.1f} pts)")
    print(f"Net cost change:       ₹{behav_row['net_cost']:,.0f} -> ₹{full_row['net_cost']:,.0f} "
          f"({full_row['net_cost']-behav_row['net_cost']:+,.0f})")

    # Feature importance from the combined model — shows how much the
    # structural features actually contribute vs behavioral ones
    importances = pd.Series(model_full.feature_importances_, index=all_cols).sort_values(ascending=False)
    print("\nFeature importances (combined model):")
    print(importances.round(4))


if __name__ == "__main__":
    main()