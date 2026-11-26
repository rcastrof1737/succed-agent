"""Render LOI drafts and Investment Committee memos from templates (string.Template: no code execution).

All outputs are DRAFTS for counsel/partner review. They are queued via outreach.create_draft.
"""
from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Optional

from .models import CompanyProfile, ScoreResult
from .returns import SearchCase, evaluate

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
JURISDICTIONS = {"US", "ES", "CL", "MX", "CO"}


def render(name: str, **values) -> str:
    tpl = Template((TEMPLATES / name).read_text(encoding="utf-8"))
    return tpl.safe_substitute({k: ("" if v is None else v) for k, v in values.items()})


def loi_draft(company: CompanyProfile, buyer_entity: str, ev_usd_m: float, cash_at_close_pct: float = 80,
              seller_note_pct: float = 10, rollover_pct: float = 10, exclusivity_days: int = 60,
              transition_months: int = 6, jurisdiction: Optional[str] = None) -> str:
    j = (jurisdiction or company.country).upper()
    if j not in JURISDICTIONS:
        j = "US"
    if abs(cash_at_close_pct + seller_note_pct + rollover_pct - 100) > 1e-6:
        raise ValueError("Consideration mix must sum to 100%")
    return render(f"loi_{j}.md", alias=company.alias, buyer=buyer_entity, ev=f"{ev_usd_m:,.2f}",
                  cash=cash_at_close_pct, note=seller_note_pct, rollover=rollover_pct,
                  exclusivity=exclusivity_days, transition=transition_months,
                  ebitda=company.ebitda_usd_m, multiple=(f"{ev_usd_m / company.ebitda_usd_m:.1f}x"
                                                         if company.ebitda_usd_m else "n/a"))


def ic_memo(company: CompanyProfile, company_score: ScoreResult, fit: Optional[ScoreResult],
            searcher_name: str, case: Optional[SearchCase] = None, thesis_summary: str = "",
            qoe_findings: str = "", risks: str = "") -> str:
    case = case or SearchCase(search_months=0, p_acquire=1.0, ebitda_usd_m=company.ebitda_usd_m or 2.5,
                              entry_multiple=(company.ev_usd_m / company.ebitda_usd_m)
                              if company.ev_usd_m and company.ebitda_usd_m else 6.0,
                              search_capital_usd_m=0.0)
    r = evaluate(case)
    dims = "\n".join(f"| {d.name} | {d.weight:.0f} | {'' if d.raw is None else d.raw} | {d.points:.1f} | {d.note} |"
                     for d in company_score.dimensions)
    return render("ic_memo.md", alias=company.alias, country=company.country, sector=company.sector,
                  searcher=searcher_name, company_score=company_score.score,
                  ci=company_score.confidence_halfwidth, fit=fit.score if fit else "n/a",
                  knockouts="; ".join(company_score.knockouts) or "none",
                  dims=dims, revenue=company.revenue_usd_m, ebitda=company.ebitda_usd_m,
                  margin=company.derived().get("ebitda_margin_pct"), recurring=company.recurring_revenue_pct,
                  top_customer=company.top_customer_pct, entry_ev=f"{r.entry_ev:.1f}",
                  exit_ev=f"{r.exit_ev:.1f}", irr=f"{100 * r.irr:.1f}%", moic=f"{r.moic:.2f}x",
                  growth=f"{100 * case.ebitda_growth:.0f}%", hold=case.hold_years,
                  leverage=f"{100 * case.senior_debt_pct_ev:.0f}%",
                  thesis=thesis_summary or "_to complete_", qoe=qoe_findings or "_pending QoE pre-check_",
                  risks=risks or "_to complete_")
