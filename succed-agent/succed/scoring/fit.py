"""Fit Index: pairwise searcher x company, gated on both scores >= 70."""
from __future__ import annotations

from typing import Optional

from .. import config
from ..models import CompanyProfile, DimensionResult, ScoreResult, SearcherAssessment, Thesis

CFG_NAME = "scoring/fit_v1"


def _in(v: Optional[float], lo_hi: tuple[float, float]) -> Optional[float]:
    if v is None:
        return None
    lo, hi = lo_hi
    if lo <= v <= hi:
        return 1.0
    gap = (lo - v) / lo if v < lo else (v - hi) / hi
    return max(0.0, 1 - 2 * gap)          # 50% outside band -> 0


def thesis_match(th: Thesis, co: CompanyProfile) -> tuple[float, list[str]]:
    parts, notes = [], []
    sectors = {s.lower() for s in th.sectors}
    if sectors:
        hit = co.sector.lower() in sectors or any(k.lower() in co.description.lower() for k in th.keywords)
        parts.append(1.0 if hit else 0.0)
        notes.append("sector match" if hit else "sector outside thesis")
    if th.geographies:
        g = co.country in {x.upper() for x in th.geographies}
        parts.append(1.0 if g else 0.0)
        notes.append("geography match" if g else f"{co.country} outside thesis geographies")
    for label, val, band in (("EV", co.ev_usd_m, th.ev_usd_m), ("EBITDA", co.ebitda_usd_m, th.ebitda_usd_m)):
        s = _in(val, band)
        if s is not None:
            parts.append(s)
            notes.append(f"{label} in band" if s == 1 else f"{label} outside band ({val})")
    if th.business_models and co.business_model:
        bm = co.business_model.lower() in {b.lower() for b in th.business_models}
        parts.append(1.0 if bm else 0.4)
    if th.min_recurring_pct and co.recurring_revenue_pct is not None:
        parts.append(1.0 if co.recurring_revenue_pct >= th.min_recurring_pct else 0.3)
    return (sum(parts) / len(parts) if parts else 0.5), notes


def operator_match(s: SearcherAssessment, co: CompanyProfile) -> tuple[float, str]:
    strengths = {x.lower() for x in s.facts.strengths}
    levers = {x.lower() for x in co.improvement_levers}
    if not strengths or not levers:
        return 0.5, "operator match unknown (no strengths/levers tagged)"
    overlap = strengths & levers
    return len(overlap) / len(levers), f"searcher strengths cover levers: {sorted(overlap) or 'none'}"


def score_fit(searcher: SearcherAssessment, searcher_score: ScoreResult, thesis: Thesis,
              company: CompanyProfile, company_score: ScoreResult,
              semantic_similarity: Optional[float] = None, cfg_name: str = CFG_NAME) -> ScoreResult:
    cfg = config.load(cfg_name)
    g = cfg["gate"]
    c_for_gate = company_score.score
    if g.get("use_lower_bound_when_low_confidence") and company_score.low_confidence:
        c_for_gate = company_score.lower_bound
    gate_fail = []
    if searcher_score.score < g["searcher_min"]:
        gate_fail.append(f"Searcher {searcher_score.score} < {g['searcher_min']}")
    if c_for_gate < g["company_min"]:
        gate_fail.append(f"Company {c_for_gate:.1f} < {g['company_min']}" +
                         (" (lower bound, low confidence)" if c_for_gate != company_score.score else ""))
    if company_score.route:
        gate_fail.append(f"Company routed to {company_score.route}")

    w = cfg["components"]
    tm, tnotes = thesis_match(thesis, company)
    om, onote = operator_match(searcher, company)
    if searcher.syndicate_capacity_usd_m is not None and company.ev_usd_m is not None:
        need = company.ev_usd_m * cfg["equity_share_of_ev"]
        ic = min(1.0, searcher.syndicate_capacity_usd_m / need) if need else 1.0
        inote = f"syndicate {searcher.syndicate_capacity_usd_m}M vs equity need ~{need:.1f}M"
    else:
        ic, inote = 0.5, "investor capacity unknown"
    qb = (searcher_score.score + company_score.score) / 200
    sim = semantic_similarity if semantic_similarity is not None else 0.5

    comps = {
        "thesis_match": (tm, "; ".join(tnotes)),
        "operator_match": (om, onote),
        "investor_capacity": (ic, inote),
        "quality_base": (qb, f"mean of scores {searcher_score.score}/{company_score.score}"),
        "semantic_similarity": (sim, "agent-provided" if semantic_similarity is not None else "not provided (0.5 neutral)"),
    }
    dims = [DimensionResult(name=k, weight=w[k], raw=round(v, 3), points=round(w[k] * v, 2), note=n)
            for k, (v, n) in comps.items()]
    fit = round(sum(x.points for x in dims), 1)
    passed = not gate_fail
    intro = cfg.get("introduce", {"min_fit": 70})
    holds = []
    if fit < intro["min_fit"]:
        holds.append(f"Fit {fit} < {intro['min_fit']}")
    if tm < intro.get("min_thesis_match", 0):
        holds.append(f"Thesis match {tm:.2f} < {intro['min_thesis_match']}")
    if intro.get("require_thesis_geography") and thesis.geographies and \
            company.country not in {g.upper() for g in thesis.geographies}:
        holds.append(f"{company.country} outside thesis geographies")
    introduce = passed and not holds
    return ScoreResult(
        subject_id=f"{searcher.searcher_id}::{company.company_id}", kind="fit",
        score=fit if passed else 0.0,
        band="introduce" if introduce else ("hold" if passed else "gated_out"),
        action=("Propose introduction (human approval required)" if introduce
                else "Keep in watchlist" if passed else "Do not introduce"),
        dimensions=dims, knockouts=gate_fail, warnings=holds,
        reasons=[n for _, n in comps.values()][:3], config_version=cfg["version"],
    )


def rank_matches(results: list[ScoreResult], cfg_name: str = CFG_NAME) -> list[ScoreResult]:
    """Rank and enforce max searchers per company (exclusivity / anti-spam for owners)."""
    cap = config.load(cfg_name)["exclusivity"]["max_searchers_per_company"]
    ranked = sorted((r for r in results if r.band == "introduce"), key=lambda r: -r.score)
    per_company: dict[str, int] = {}
    out = []
    for r in ranked:
        cid = r.subject_id.split("::")[1]
        if per_company.get(cid, 0) < cap:
            per_company[cid] = per_company.get(cid, 0) + 1
            out.append(r)
    return out
