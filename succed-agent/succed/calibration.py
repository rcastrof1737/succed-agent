"""Learning loop: calibrate score weights against outcomes (acquired? closed? exit MOIC >= 2?).

Plain-numpy L2 logistic regression + AUC. Outputs SUGGESTED weights only; partners approve and
publish a new config version. Refuses protected attributes and tiny samples.
"""
from __future__ import annotations

import numpy as np

from .config import load

MIN_SAMPLES = 30


def _auc(y: np.ndarray, p: np.ndarray) -> float:
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    wins = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(wins / (len(pos) * len(neg)))


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1.0, iters: int = 3000, lr: float = 0.1) -> np.ndarray:
    Xb = np.hstack([np.ones((X.shape[0], 1)), X])
    w = np.zeros(Xb.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-Xb @ w))
        grad = Xb.T @ (p - y) / len(y) + l2 * np.r_[0, w[1:]] / len(y)
        w -= lr * grad
    return w


def calibrate(rows: list[dict], kind: str = "searcher", cfg_name: str = "scoring/searcher_v1") -> dict:
    """rows: [{'features': {dimension: value}, 'outcome': 0/1}, ...]"""
    cfg = load(cfg_name)
    protected = set(cfg.get("protected_attributes", []))
    dims = list(cfg["dimensions"])
    if len(rows) < MIN_SAMPLES:
        return {"status": "insufficient_data", "n": len(rows), "min_required": MIN_SAMPLES,
                "message": "Keep partner-set weights; collect more outcomes."}
    for r in rows:
        leaked = protected & set(r["features"])
        if leaked:
            raise ValueError(f"Protected attributes in training features: {sorted(leaked)}")
    X = np.array([[float(r["features"].get(d, 0.0)) for d in dims] for r in rows])
    y = np.array([int(r["outcome"]) for r in rows], dtype=float)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = (X - mu) / sd
    w = fit_logistic(Z, y)
    p = 1 / (1 + np.exp(-np.hstack([np.ones((len(Z), 1)), Z]) @ w))
    current = np.array([cfg["dimensions"][d]["weight"] for d in dims], dtype=float)
    p_cur = Z @ (current / current.sum())
    coef = np.clip(w[1:], 0, None)
    suggested = (100 * coef / coef.sum()) if coef.sum() > 0 else current
    # shrink toward partner weights (50/50) to avoid overfitting small samples
    blended = 0.5 * current + 0.5 * suggested
    return {
        "status": "ok", "n": len(rows), "positive_rate": round(float(y.mean()), 3),
        "auc_current_weights": round(_auc(y, p_cur), 3),
        "auc_fitted": round(_auc(y, p), 3),
        "current_weights": dict(zip(dims, current.round(1).tolist())),
        "suggested_weights_blended": dict(zip(dims, blended.round(1).tolist())),
        "note": "Suggestion only. Publish as a new config version after partner sign-off; in-sample AUC is optimistic.",
    }
