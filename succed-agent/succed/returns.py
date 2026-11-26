"""Investor returns model for one search (probability-weighted) + dated XIRR.

Reproduces the illustrative table in the Succed 2.0 blueprint (§8). ILLUSTRATIVE, not a forecast:
it models a MEDIAN deal; Stanford's 33.9% aggregate is lifted by outliers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date
from typing import Iterable, Sequence


def irr_periodic(cfs: Sequence[float], periods_per_year: int = 12) -> float:
    """Annualised IRR of evenly spaced cash flows (bisection; robust, no numpy dependency)."""
    def npv(r: float) -> float:
        m = (1 + r) ** (1 / periods_per_year) - 1
        return sum(c / (1 + m) ** t for t, c in enumerate(cfs))
    lo, hi = -0.99, 10.0
    if npv(lo) * npv(hi) > 0:
        raise ValueError("IRR not bracketed (check signs of cash flows)")
    for _ in range(300):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def xirr(flows: Iterable[tuple[date, float]]) -> float:
    """XIRR on dated flows (Actual/365), as Excel. Use this for fund-level reporting."""
    fl = sorted(flows)
    t0 = fl[0][0]
    def npv(r: float) -> float:
        return sum(c / (1 + r) ** ((d - t0).days / 365.0) for d, c in fl)
    lo, hi = -0.99, 10.0
    if npv(lo) * npv(hi) > 0:
        raise ValueError("XIRR not bracketed")
    for _ in range(300):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


@dataclass(frozen=True)
class SearchCase:
    search_months: int = 21
    p_acquire: float = 0.58
    entry_multiple: float = 6.4
    ebitda_growth: float = 0.10
    exit_multiple: float = 6.4
    hold_years: int = 5
    ebitda_usd_m: float = 2.5
    search_capital_usd_m: float = 0.55
    step_up: float = 1.5
    senior_debt_pct_ev: float = 0.5
    debt_repaid_share: float = 0.5
    investor_share_of_gains: float = 0.75


@dataclass(frozen=True)
class CaseResult:
    irr: float
    moic: float
    entry_ev: float
    exit_ev: float


def evaluate(case: SearchCase) -> CaseResult:
    ev = case.ebitda_usd_m * case.entry_multiple
    debt = ev * case.senior_debt_pct_ev
    equity = ev - debt
    T = case.search_months + case.hold_years * 12 + 1
    cf = [0.0] * T
    cf[0] -= case.search_capital_usd_m
    new_equity = equity - case.search_capital_usd_m * case.step_up
    cf[case.search_months] -= case.p_acquire * new_equity
    exit_ev = case.ebitda_usd_m * (1 + case.ebitda_growth) ** case.hold_years * case.exit_multiple
    exit_equity = exit_ev - debt * (1 - case.debt_repaid_share)
    gain = exit_equity - equity
    to_investors = equity + (case.investor_share_of_gains * gain if gain > 0 else gain)
    cf[case.search_months + case.hold_years * 12] += case.p_acquire * to_investors
    invested = case.search_capital_usd_m + case.p_acquire * new_equity
    return CaseResult(irr=irr_periodic(cf), moic=case.p_acquire * to_investors / invested,
                      entry_ev=ev, exit_ev=exit_ev)


SUCCED_TARGET = dict(search_months=15, p_acquire=0.68, entry_multiple=5.8, ebitda_growth=0.12)


def lever_table(base: SearchCase = SearchCase(), target: dict = SUCCED_TARGET) -> list[dict]:
    """Isolate each lever, then all together — the blueprint §8 table."""
    rows = [("Baseline", base)]
    for k, v in target.items():
        rows.append((f"Only {k}", replace(base, **{k: v})))
    rows.append(("All levers (Succed target)", replace(base, **target)))
    out = []
    for label, c in rows:
        r = evaluate(c)
        out.append({"scenario": label, **{k: getattr(c, k) for k in target},
                    "irr_pct": round(100 * r.irr, 1), "moic": round(r.moic, 2)})
    return out


def case_from_dict(d: dict) -> SearchCase:
    allowed = set(asdict(SearchCase()))
    return SearchCase(**{k: v for k, v in d.items() if k in allowed})
