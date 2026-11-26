"""Pipeline KPIs, the weekly pilot scorecard and in-search board alerts."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import median
from typing import Optional

from .models import Stage
from .scoring.searcher import in_search_alerts
from .store import Store

REACHED = {
    "contacted": {"contacted", "call", "nda", "ioi", "loi", "diligence", "closed"},
    "nda": {"nda", "ioi", "loi", "diligence", "closed"},
    "ioi": {"ioi", "loi", "diligence", "closed"},
    "loi": {"loi", "diligence", "closed"},
    "closed": {"closed"},
}


def _months_between(a: date, b: date) -> float:
    return (b - a).days / 30.44


def scorecard(store: Store, as_of: Optional[date] = None, investor_id: Optional[str] = None) -> dict:
    """Weekly scorecard for the investor (blueprint §11)."""
    as_of = as_of or date.today()
    with store.conn() as c:
        comp_scores = [dict(r) for r in c.execute(
            "SELECT subject_id, score FROM scores s WHERE kind='company' AND rowid=(SELECT MAX(rowid) FROM scores WHERE subject_id=s.subject_id AND kind='company')")]
        fit_rows = [dict(r) for r in c.execute(
            "SELECT subject_id, score, band FROM scores s WHERE kind='fit' AND rowid=(SELECT MAX(rowid) FROM scores WHERE subject_id=s.subject_id AND kind='fit')")]
        dec = [dict(r) for r in c.execute("SELECT * FROM decisions")]
    events = store.events()
    stages_by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    loi_mult: list[float] = []
    for e in events:
        stages_by_pair[(e["searcher_id"], e["company_id"])].add(e["stage"])
        if e["stage"] in ("loi", "closed") and e["entry_ev_ebitda"]:
            loi_mult.append(e["entry_ev_ebitda"])
    funnel = {k: sum(1 for s in stages_by_pair.values() if s & v) for k, v in REACHED.items()}

    # partner agreement with model on searcher decisions
    agree = [d for d in dec if d["model_score"] is not None and d["kind"] == "searcher"]
    agreement = None
    if agree:
        ok = sum(1 for d in agree if (d["model_score"] >= 70) == (d["decision"] in ("approve", "fund", "advance")))
        agreement = round(ok / len(agree), 2)

    alerts = {}
    for s in store.searchers():
        meta = store.searcher_meta(s.searcher_id)
        if investor_id and meta.get("investor_id") != investor_id:
            continue
        if not meta.get("funded_on"):
            continue
        m = _months_between(date.fromisoformat(meta["funded_on"]), as_of)
        evs = store.events(s.searcher_id)
        lois = sum(1 for e in evs if e["stage"] == "loi")
        contacted_4w = sum(1 for e in evs if e["stage"] == "contacted" and (as_of - date.fromisoformat(e["on_date"])).days <= 28)
        sourced_30d = sum(1 for e in evs if e["stage"] == "sourced" and (as_of - date.fromisoformat(e["on_date"])).days <= 30)
        a = in_search_alerts(m, lois, contacted_4w / 4, sourced_30d)
        if a:
            alerts[s.name] = a

    n = len(comp_scores)
    return {
        "as_of": as_of.isoformat(),
        "companies_scored": n,
        "pct_company_ge_70": round(100 * sum(1 for r in comp_scores if r["score"] >= 70) / n, 1) if n else 0.0,
        "matches_introduce": sum(1 for r in fit_rows if r["band"] == "introduce"),
        "funnel": funnel,
        "median_entry_ev_ebitda_at_loi": round(median(loi_mult), 2) if loi_mult else None,
        "partner_agreement_with_searcher_score": agreement,
        "alerts": alerts,
    }


def advance(store: Store, searcher_id: str, company_id: str, stage: str, on: date, reason: str = "",
            entry_ev_ebitda: Optional[float] = None) -> None:
    from .models import PipelineEvent
    st = Stage(stage)
    if st == Stage.LOST and not reason:
        raise ValueError("Lost deals require a reason (feeds the learning loop)")
    store.add_event(PipelineEvent(searcher_id=searcher_id, company_id=company_id, stage=st, on=on,
                                  reason=reason, entry_ev_ebitda=entry_ev_ebitda))
