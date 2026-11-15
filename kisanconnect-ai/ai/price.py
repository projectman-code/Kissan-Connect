"""AI smart price suggestion.

A RandomForest model is trained on first run (a few seconds) using seasonal
price patterns for every crop in the catalog, then saved next to this file.
Replace `_training_data()` with real mandi data to make it production grade.
"""
import math
import os
from datetime import date

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor

from .catalog import CROPS, MONTHS

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "price_model.joblib")
NAMES = list(CROPS)
GRADE_FACTOR = {"A": 1.18, "B": 1.0, "C": 0.85}
GRADE_NUM = {"A": 2, "B": 1, "C": 0}
_model = None


def _features(crop, month, grade, organic):
    info = CROPS[crop]
    return [
        NAMES.index(crop), month,
        math.sin(2 * math.pi * month / 12), math.cos(2 * math.pi * month / 12),
        GRADE_NUM.get(grade, 1), 1 if organic else 0, info["base"],
    ]


def _true_price(crop, month, grade, organic):
    info = CROPS[crop]
    seasonal = 1 + 0.28 * math.cos(2 * math.pi * (month - info["harvest"]) / 12)
    return info["base"] * seasonal * GRADE_FACTOR[grade] * (1.22 if organic else 1.0)


def _training_data(n=7000, seed=7):
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(n):
        crop = NAMES[rng.integers(len(NAMES))]
        month = int(rng.integers(1, 13))
        grade = "ABC"[rng.integers(3)]
        organic = int(rng.integers(2))
        X.append(_features(crop, month, grade, organic))
        y.append(_true_price(crop, month, grade, organic) * (1 + rng.normal(0, 0.04)))
    return np.array(X), np.array(y)


def ensure_model():
    global _model
    if _model is not None:
        return _model
    if os.path.exists(MODEL_PATH):
        try:
            _model = joblib.load(MODEL_PATH)
            return _model
        except Exception:
            pass
    X, y = _training_data()
    _model = RandomForestRegressor(n_estimators=80, max_depth=12, random_state=1, n_jobs=1)
    _model.fit(X, y)
    try:
        joblib.dump(_model, MODEL_PATH, compress=3)
    except OSError:
        pass
    return _model


def suggest_price(crop, grade="B", organic=False, month=None):
    """Return a fair-price suggestion, or None when the crop is not in the catalog."""
    if crop not in CROPS:
        return None
    month = month or date.today().month
    grade = grade if grade in GRADE_NUM else "B"
    model = ensure_model()
    x = np.array([_features(crop, month, grade, organic)])
    per_tree = np.array([t.predict(x)[0] for t in model.estimators_])
    suggested = float(per_tree.mean())
    low, high = np.percentile(per_tree, 10), np.percentile(per_tree, 90)
    low = min(low, suggested * 0.95)
    high = max(high, suggested * 1.05)

    yearly = np.mean([model.predict(np.array([_features(crop, m, grade, organic)]))[0] for m in range(1, 13)])
    diff = (suggested - yearly) / yearly * 100
    best_month = min(range(1, 13), key=lambda m: abs(m - CROPS[crop]["harvest"]))
    if diff <= -6:
        trend = f"Harvest season: prices are about {abs(diff):.0f}% below the yearly average. Consider storing some stock for {MONTHS[(best_month + 3) % 12]}."
    elif diff >= 6:
        trend = f"Off-season: prices are about {diff:.0f}% above the yearly average. A good time to sell."
    else:
        trend = "Prices are close to the yearly average this month."
    return {
        "crop": crop, "unit": CROPS[crop]["unit"], "grade": grade, "organic": bool(organic),
        "suggested": round(suggested, 1), "low": round(low, 1), "high": round(high, 1),
        "trend": trend, "month": MONTHS[month - 1],
    }
