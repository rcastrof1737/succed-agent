"""Domain models. Every score carries its config version, inputs and explanations so it can be audited."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from .clock import utcnow


# ---------------------------------------------------------------- searcher side
class Evidence(BaseModel):
    text: str = Field(..., min_length=3, description="Quote or fact supporting the rating")
    source: str = Field("", description="Where it came from: cv, reference:<name>, interview, case, thesis")


class DimensionRating(BaseModel):
    rating: float = Field(..., ge=0, le=5)
    evidence: list[Evidence] = Field(default_factory=list)


class SearcherFacts(BaseModel):
    """Deterministic facts the engine can check. No protected attributes belong here."""
    etas_training: Optional[bool] = None
    has_partner: Optional[bool] = None
    full_time: Optional[bool] = None
    personal_runway_months: Optional[float] = None
    addressable_universe: Optional[int] = Field(None, description="From thesis builder")
    strengths: list[str] = Field(default_factory=list, description="Operator strengths tags, e.g. sales, ops, pricing, digital")
    geographies: list[str] = Field(default_factory=list, description="ISO-like codes the searcher can operate in")


class SearcherAssessment(BaseModel):
    searcher_id: str
    name: str
    ratings: dict[str, DimensionRating]
    facts: SearcherFacts = Field(default_factory=SearcherFacts)
    syndicate_capacity_usd_m: Optional[float] = Field(None, description="Equity the searcher's investors can fund")
    assessed_by: str = "searcher-evaluator-agent"


class Thesis(BaseModel):
    thesis_id: str
    searcher_id: str
    sectors: list[str] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)
    ev_usd_m: tuple[float, float] = (10.0, 30.0)
    ebitda_usd_m: tuple[float, float] = (1.5, 5.0)
    min_recurring_pct: float = 0.0
    business_models: list[str] = Field(default_factory=list, description="e.g. b2b_services, saas, distribution")
    keywords: list[str] = Field(default_factory=list)
    text: str = ""


# ---------------------------------------------------------------- company side
class CompanyProfile(BaseModel):
    company_id: str
    alias: str = Field(..., description="Code name shown before NDA (never the legal name)")
    country: str
    sector: str
    business_model: str = ""
    description: str = ""
    source: str = Field("manual", description="manual | partner:<name> | registry | off_market_agent")
    # financials in USD millions
    revenue_usd_m: Optional[float] = None
    ebitda_usd_m: Optional[float] = None
    ev_usd_m: Optional[float] = None
    ebitda_margin_pct: Optional[float] = None
    fcf_conversion_pct: Optional[float] = None
    recurring_revenue_pct: Optional[float] = None
    top_customer_pct: Optional[float] = None
    capex_pct_revenue: Optional[float] = None
    revenue_growth_pct: Optional[float] = None
    years_of_financials: Optional[int] = None
    # transition
    second_tier_management: Optional[bool] = None
    owner_transition_months: Optional[float] = None
    owner_age: Optional[int] = Field(None, description="Owner age is a transition-readiness signal for the COMPANY, never a searcher input")
    defensibility_rating: Optional[float] = Field(None, ge=0, le=5)
    improvement_levers: list[str] = Field(default_factory=list, description="e.g. sales, pricing, digital, ops, m&a")
    flags: dict[str, bool] = Field(default_factory=dict)
    evidence: dict[str, str] = Field(default_factory=dict, description="field -> page/quote in source docs")

    @field_validator("country")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    def derived(self) -> dict[str, Any]:
        d = self.model_dump()
        if d["ebitda_margin_pct"] is None and self.revenue_usd_m and self.ebitda_usd_m is not None:
            d["ebitda_margin_pct"] = round(100 * self.ebitda_usd_m / self.revenue_usd_m, 2)
        return d


# ---------------------------------------------------------------- results
class DimensionResult(BaseModel):
    name: str
    weight: float
    raw: Optional[float]            # 0–5 rating or 0..1 subscore before weighting
    points: float                   # contribution to 0–100
    note: str = ""


class ScoreResult(BaseModel):
    subject_id: str
    kind: str                       # searcher | company | fit
    score: float
    band: str = ""
    action: str = ""
    confidence_halfwidth: Optional[float] = None
    low_confidence: bool = False
    dimensions: list[DimensionResult] = Field(default_factory=list)
    knockouts: list[str] = Field(default_factory=list)
    route: Optional[str] = None
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    config_version: str
    computed_at: datetime = Field(default_factory=utcnow)

    @property
    def lower_bound(self) -> float:
        return self.score - (self.confidence_halfwidth or 0)


class Stage(str, Enum):
    SOURCED = "sourced"
    CONTACTED = "contacted"
    CALL = "call"
    NDA = "nda"
    IOI = "ioi"
    LOI = "loi"
    DILIGENCE = "diligence"
    CLOSED = "closed"
    LOST = "lost"


STAGE_ORDER = [s for s in Stage if s not in (Stage.LOST,)]


class PipelineEvent(BaseModel):
    searcher_id: str
    company_id: str
    stage: Stage
    on: date
    reason: str = ""
    entry_ev_ebitda: Optional[float] = None
