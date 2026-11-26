"""Thesis Builder: size the addressable universe of a thesis over a company dataset."""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from .models import CompanyProfile, Thesis

MIN_UNIVERSE = 300
MAX_UNIVERSE = 20000


def in_thesis(th: Thesis, c: CompanyProfile, ebitda_tolerance: float = 0.0) -> bool:
    if th.geographies and c.country not in {g.upper() for g in th.geographies}:
        return False
    if th.sectors:
        sect = c.sector.lower() in {s.lower() for s in th.sectors}
        kw = any(k.lower() in (c.description or "").lower() for k in th.keywords)
        if not (sect or kw):
            return False
    if c.ebitda_usd_m is not None:
        lo, hi = th.ebitda_usd_m
        if not (lo * (1 - ebitda_tolerance) <= c.ebitda_usd_m <= hi * (1 + ebitda_tolerance)):
            return False
    if th.min_recurring_pct and c.recurring_revenue_pct is not None and c.recurring_revenue_pct < th.min_recurring_pct:
        return False
    return True


def size_universe(th: Thesis, companies: Iterable[CompanyProfile], scale_factor: float = 1.0) -> dict:
    """Count matching companies. `scale_factor` extrapolates a sample to the full registry
    (e.g. sample of 1,000 out of 50,000 -> 50). Extrapolations are flagged as estimates."""
    matches = [c for c in companies if in_thesis(th, c)]
    est = round(len(matches) * scale_factor)
    warnings = []
    if est < MIN_UNIVERSE:
        warnings.append(f"Universe ~{est} < {MIN_UNIVERSE}: thesis likely too narrow for a 2-year search")
    if est > MAX_UNIVERSE:
        warnings.append(f"Universe ~{est} > {MAX_UNIVERSE}: thesis too broad to drive focused outreach")
    return {
        "thesis_id": th.thesis_id,
        "matches_in_dataset": len(matches),
        "estimated_universe": est,
        "is_estimate": scale_factor != 1.0,
        "by_country": dict(Counter(c.country for c in matches)),
        "by_sector": dict(Counter(c.sector for c in matches)),
        "warnings": warnings,
        "sample_ids": [c.company_id for c in matches[:20]],
    }
