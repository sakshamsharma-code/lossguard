"""
Loads the trained combined model (behavioral + structural) and exposes
predict_risk(features_dict) -> float for the API layer.
"""

import joblib
import pandas as pd

MODEL_PATH = "app/ml/xgb_full_model.joblib"

ALL_COLS = [
    "return_rate_30d",
    "return_rate_90d",
    "avg_order_value",
    "time_since_signup_days",
    "return_to_purchase_gap_days",
    "category_return_concentration",
    "cluster_size",
    "cluster_density",
    "shared_device_count",
    "shared_address_count",
    "shared_payment_method_count",
]

_model = None


def _load_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    return _model


def predict_risk(features: dict) -> float:
    """features: dict with keys matching ALL_COLS. Returns risk score in [0,1]."""
    model = _load_model()
    row = pd.DataFrame([{col: features.get(col, 0) for col in ALL_COLS}])
    proba = model.predict_proba(row)[:, 1][0]
    return float(round(proba, 4))