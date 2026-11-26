"""MCP server exposing Succed's deterministic engine to Claude Code / Claude Desktop / Agent SDK.

Run:  python -m succed.mcp_server         (stdio; registered in .mcp.json)
The LLM agents read documents and propose structured inputs; these tools score, store and gate them.
No tool here sends anything outside the platform.
"""
from __future__ import annotations

import os
from typing import Any, Optional

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore

from .service import Service

INSTRUCTIONS = (
    "Succed scoring engine for search funds. Scores are decision support: always show the breakdown, "
    "confidence and warnings; never present a score as a fact about a person. Outreach, LOIs and memos are "
    "created as drafts that require a named human approval. Never invent financial figures: pass None when unknown."
)

mcp = _Server(name="succed", instructions=INSTRUCTIONS)
_svc: Optional[Service] = None


def svc() -> Service:
    global _svc
    if _svc is None:
        _svc = Service(os.environ.get("SUCCED_DB") or None)
    return _svc


# ----------------------------------------------------------------- searcher selection
@mcp.tool()
def score_searcher(assessment: dict[str, Any], investor_id: str = "", funded_on: Optional[str] = None) -> dict:
    """Aggregate an evidence-backed SearcherAssessment into the 0–100 Searcher Score.
    assessment = {searcher_id, name, ratings: {dimension: {rating 0-5, evidence: [{text, source}]}},
    facts: {etas_training, has_partner, full_time, personal_runway_months, addressable_universe, strengths, geographies},
    syndicate_capacity_usd_m}. Dimensions: operator_capability, search_readiness, thesis_quality, thesis_founder_fit,
    coachability_judgment, network_origination, commitment_structure. Protected attributes are rejected."""
    return svc().score_searcher(assessment, investor_id, funded_on)


@mcp.tool()
def record_partner_decision(subject_id: str, kind: str, decision: str, by_whom: str, reason: str) -> dict:
    """Log a partner decision/override (approve, decline, coach, fund) with a written reason, next to the model score."""
    return svc().record_partner_decision(subject_id, kind, decision, by_whom, reason)


@mcp.tool()
def save_thesis(thesis: dict[str, Any]) -> dict:
    """Save a structured thesis {thesis_id, searcher_id, sectors, geographies, ev_usd_m:[lo,hi], ebitda_usd_m:[lo,hi],
    min_recurring_pct, business_models, keywords, text}."""
    return svc().save_thesis(thesis)


@mcp.tool()
def size_thesis(thesis: dict[str, Any], scale_factor: float = 1.0) -> dict:
    """Thesis Builder: count companies in the dataset matching the thesis; warns if universe < 300 or > 20,000."""
    return svc().size_thesis(thesis, scale_factor)


# ----------------------------------------------------------------- origination & screening
@mcp.tool()
def import_companies(path: str) -> dict:
    """Import companies from a CSV/JSON file (partner feeds, broker exports, registry pulls)."""
    return svc().import_companies(path)


@mcp.tool()
def upsert_company(company: dict[str, Any]) -> dict:
    """Create/update a CompanyProfile extracted by the screening agent. Use code-name `alias`, never the legal name.
    Unknown numbers must be omitted (null), not guessed. Put page/quote references in `evidence`."""
    return svc().upsert_company(company)


@mcp.tool()
def score_company(company_id: str) -> dict:
    """Company Score 0–100 with confidence interval, knock-outs and per-dimension breakdown."""
    return svc().score_company(company_id)


@mcp.tool()
def score_all_companies() -> list:
    """Re-score every company in the store; returns a ranked list."""
    return svc().score_all_companies()


# ----------------------------------------------------------------- matching
@mcp.tool()
def match(searcher_id: str, top_n: int = 10, similarities: Optional[dict[str, float]] = None) -> dict:
    """Fit Index for one searcher against all companies. Gate: Searcher >= 70 AND Company >= 70 (lower bound if
    low confidence). Max 4 searchers per company. `similarities` = optional {company_id: 0..1} semantic scores."""
    return svc().match(searcher_id, top_n, similarities)


# ----------------------------------------------------------------- execution
@mcp.tool()
def create_draft(kind: str, searcher_id: str, company_id: str, body: str) -> dict:
    """Queue an outbound artefact (owner_outreach | loi | ic_memo | investor_update | intro) for HUMAN approval.
    Enforces weekly caps, 21-day owner exclusivity and prohibited claims. Nothing is sent."""
    return svc().draft(kind, searcher_id, company_id, body)


@mcp.tool()
def list_drafts(status: Optional[str] = None) -> list:
    """List drafts (pending_approval | approved | rejected)."""
    return svc().list_drafts(status)


@mcp.tool()
def draft_loi(company_id: str, buyer_entity: str, ev_usd_m: float, cash_at_close_pct: float = 80,
              seller_note_pct: float = 10, rollover_pct: float = 10, exclusivity_days: int = 60,
              transition_months: int = 6, jurisdiction: Optional[str] = None) -> dict:
    """Render a non-binding LOI draft from the jurisdiction template (US, ES, CL, MX, CO)."""
    return svc().loi(company_id, buyer_entity, ev_usd_m, cash_at_close_pct=cash_at_close_pct,
                     seller_note_pct=seller_note_pct, rollover_pct=rollover_pct,
                     exclusivity_days=exclusivity_days, transition_months=transition_months, jurisdiction=jurisdiction)


@mcp.tool()
def draft_ic_memo(searcher_id: str, company_id: str, thesis_summary: str = "", qoe_findings: str = "",
                  risks: str = "", case: Optional[dict[str, Any]] = None) -> dict:
    """Assemble an Investment Committee memo draft from scores, financials and the deal-level returns model."""
    kw: dict[str, Any] = dict(thesis_summary=thesis_summary, qoe_findings=qoe_findings, risks=risks)
    if case:
        kw["case"] = case
    return svc().ic_memo(searcher_id, company_id, **kw)


@mcp.tool()
def advance_pipeline(searcher_id: str, company_id: str, stage: str, on: Optional[str] = None, reason: str = "",
                     entry_ev_ebitda: Optional[float] = None) -> dict:
    """Record a pipeline stage: sourced, contacted, call, nda, ioi, loi, diligence, closed, lost (lost needs a reason)."""
    return svc().advance(searcher_id, company_id, stage, on, reason, entry_ev_ebitda)


# ----------------------------------------------------------------- learning & reporting
@mcp.tool()
def scorecard(as_of: Optional[str] = None, investor_id: Optional[str] = None) -> dict:
    """Weekly investor scorecard: companies scored, % >= 70, funnel, entry multiples, partner agreement, board alerts."""
    return svc().scorecard(as_of, investor_id)


@mcp.tool()
def record_outcome(subject_id: str, kind: str, outcome: bool) -> dict:
    """Record an outcome (e.g. searcher acquired a company; company closed) for the learning loop."""
    return svc().record_outcome(subject_id, kind, outcome)


@mcp.tool()
def calibrate(kind: str = "searcher") -> dict:
    """Suggest re-weighted scores from recorded outcomes (needs >= 30). Suggestion only; partners publish new versions."""
    return svc().calibrate(kind)


@mcp.tool()
def returns_levers(base: Optional[dict[str, Any]] = None, target: Optional[dict[str, Any]] = None) -> list:
    """Illustrative investor IRR/MOIC for one median search, isolating each Succed lever (search time, acquisition
    probability, entry multiple, EBITDA growth). Illustrative, not a forecast."""
    return svc().returns_levers(base, target)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
