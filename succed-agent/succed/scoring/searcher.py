"""Searcher & Thesis Score (0–100).

The searcher-evaluator agent (LLM) reads CVs, theses, references and interviews and proposes a 0–5
rating per dimension WITH evidence. This module is the deterministic, auditable aggregator:
it drops unevidenced ratings, applies factual caps, weights, bands and records everything.
"""
from __future__ import annotations

from typing import Optional

from .. import config
from ..models import DimensionResult, ScoreResult, SearcherAssessment
from .common import band_for

CFG_NAME = "scoring/searcher_v1"


class ProtectedAttributeError(ValueError):
    pass


def _check_protected(assessment: SearcherAssessment, protected: set[str]) -> None:
    payload = assessment.model_dump()
    leaked = protected & (set(payload["ratings"]) | set(payload["facts"]))
    if leaked:
        raise ProtectedAttributeError(f"Protected attributes may not be scored: {sorted(leaked)}")


def score_searcher(assessment: SearcherAssessment, cfg_name: str = CFG_NAME) -> ScoreResult:
    cfg = config.load(cfg_name)
    _check_protected(assessment, set(cfg.get("protected_attributes", [])))
    scale = float(cfg.get("scale_max", 5))
    adj = cfg.get("adjustments", {})
    min_ev = int(cfg.get("min_evidence_per_dimension", 1))
    facts = assessment.facts

    dims: list[DimensionResult] = []
    warnings: list[str] = []
    missing_weight = 0.0
    total = 0.0

    for name, d in cfg["dimensions"].items():
        w = float(d["weight"])
        r = assessment.ratings.get(name)
        note = ""
        rating: Optional[float] = None
        if r is None:
            warnings.append(f"{d['label']}: not assessed")
        elif len(r.evidence) < min_ev:
            warnings.append(f"{d['label']}: rating ignored (no evidence cited)")
        else:
            rating = r.rating

        # factual caps
        if rating is not None and name == "thesis_quality" and facts.addressable_universe is not None:
            a = adj.get("thesis_quality", {})
            if facts.addressable_universe < a.get("universe_min", 0):
                if rating > a["universe_cap_rating"]:
                    note = f"capped: universe {facts.addressable_universe} < {a['universe_min']}"
                rating = min(rating, a["universe_cap_rating"])
            elif facts.addressable_universe > a.get("universe_max", 10**9):
                if rating > a["universe_broad_cap_rating"]:
                    note = f"capped: universe {facts.addressable_universe} too broad"
                rating = min(rating, a["universe_broad_cap_rating"])
        if rating is not None and name == "commitment_structure":
            a = adj.get("commitment_structure", {})
            if facts.personal_runway_months is not None and facts.personal_runway_months < a.get("min_runway_months", 0):
                if rating > a["low_runway_cap_rating"]:
                    note = f"capped: runway {facts.personal_runway_months}m < {a['min_runway_months']}m"
                rating = min(rating, a["low_runway_cap_rating"])
            if facts.full_time is False:
                rating = min(rating, 1.5)
                note = (note + "; " if note else "") + "capped: not full-time"

        if rating is None:
            missing_weight += w
            pts = 0.0
        else:
            pts = w * rating / scale
        total += pts
        dims.append(DimensionResult(name=name, weight=w, raw=rating, points=round(pts, 2), note=note))

    # Missing dimensions score 0 (conservative) and widen the confidence interval.
    halfwidth = round(2 + 0.5 * missing_weight, 1)
    score = round(total, 1)
    band, action = band_for(score, cfg["bands"])
    reasons = [f"{x.name}: {x.points:.1f}/{x.weight:.0f}" for x in sorted(dims, key=lambda x: -x.points)[:3]]
    return ScoreResult(
        subject_id=assessment.searcher_id, kind="searcher", score=score, band=band, action=action,
        confidence_halfwidth=halfwidth, low_confidence=missing_weight >= 20,
        dimensions=dims, reasons=reasons, warnings=warnings, config_version=cfg["version"],
    )


def in_search_alerts(months_in_search: float, lois_signed: int, owner_convos_per_week: float,
                     companies_screened_last_month: int, cfg_name: str = CFG_NAME) -> list[str]:
    """Dynamic in-search checks reported to the investor board each month."""
    c = config.load(cfg_name)["in_search"]
    alerts = []
    if months_in_search >= c["lo_alert_month"] and lois_signed == 0:
        alerts.append(f"No LOI by month {months_in_search:.0f} (threshold {c['lo_alert_month']}): board check-in + thesis review")
    if owner_convos_per_week < c["min_owner_conversations_per_week"]:
        alerts.append(f"Owner conversations {owner_convos_per_week}/wk below {c['min_owner_conversations_per_week']}")
    if companies_screened_last_month < c["min_companies_screened_per_month"]:
        alerts.append(f"Screened {companies_screened_last_month} companies last month (< {c['min_companies_screened_per_month']})")
    return alerts
