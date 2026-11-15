"""Demand forecast: which crops will sell best in the coming months.

A RandomForest learns seasonal demand patterns (summer fruit, winter greens,
festival spices and dairy ...) and the result is blended with the platform's
own recent orders so it gets sharper as real data arrives.
"""
import math
from collections import defaultdict
from datetime import date

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from .catalog import CAT_SEASON, CROPS, MONTHS

NAMES = list(CROPS)
_model = None


def _seasonal_demand(crop, month):
    info = CROPS[crop]
    peak, amp = CAT_SEASON[info["cat"]]
    festive = 0.15 if (month in (10, 11) and info["cat"] in ("Dairy", "Spices", "Oilseeds", "Fruits")) else 0.0
    return info["pop"] * 10 * (1 + amp * math.cos(2 * math.pi * (month - peak) / 12) + festive)


def _model_ready():
    global _model
    if _model is None:
        rng = np.random.default_rng(3)
        X, y = [], []
        for crop in NAMES:
            for month in range(1, 13):
                for _ in range(6):
                    X.append([NAMES.index(crop), month])
                    y.append(_seasonal_demand(crop, month) * (1 + rng.normal(0, 0.05)))
        _model = RandomForestRegressor(n_estimators=60, max_depth=10, random_state=2, n_jobs=1)
        _model.fit(np.array(X), np.array(y))
    return _model


def forecast(recent_orders, months_ahead=3, top_n=6, today=None):
    """recent_orders: iterable of (product_name, quantity) from the last ~60 days."""
    today = today or date.today()
    model = _model_ready()

    sold = defaultdict(float)
    for name, qty in recent_orders:
        sold[name] += float(qty)
    max_sold = max(sold.values()) if sold else 0

    def live_boost(crop):
        return 1 + (0.4 * sold.get(crop, 0) / max_sold if max_sold else 0)

    def scores(month):
        raw = {c: float(model.predict(np.array([[NAMES.index(c), month]]))[0]) * live_boost(c) for c in NAMES}
        top = max(raw.values())
        return {c: v / top * 100 for c, v in raw.items()}

    now_scores = scores(today.month)
    result = []
    for step in range(1, months_ahead + 1):
        m = (today.month - 1 + step) % 12 + 1
        year = today.year + ((today.month - 1 + step) // 12)
        sc = scores(m)
        ranked = sorted(sc, key=sc.get, reverse=True)[:top_n]
        result.append({
            "label": f"{MONTHS[m - 1]} {year}",
            "top": [{
                "crop": c, "emoji": CROPS[c]["emoji"], "cat": CROPS[c]["cat"],
                "index": round(sc[c]), "delta": round(sc[c] - now_scores[c]),
            } for c in ranked],
        })
    hot_now = sorted(now_scores, key=now_scores.get, reverse=True)[:top_n]
    return {
        "months": result,
        "now": [{"crop": c, "emoji": CROPS[c]["emoji"], "index": round(now_scores[c])} for c in hot_now],
        "live_orders": bool(sold),
    }
