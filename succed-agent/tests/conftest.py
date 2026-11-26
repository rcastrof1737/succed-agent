import json
from pathlib import Path

import pytest

from succed.cli import load_demo
from succed.models import CompanyProfile, SearcherAssessment, Thesis
from succed.service import Service

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"


@pytest.fixture
def svc(tmp_path):
    return Service(tmp_path / "t.db")


@pytest.fixture
def demo(svc):
    load_demo(svc)
    return svc


@pytest.fixture
def searchers():
    return json.loads((SAMPLE / "searchers.json").read_text(encoding="utf-8"))


@pytest.fixture
def strong_searcher(searchers):
    return SearcherAssessment.model_validate(searchers[0]["assessment"]), Thesis.model_validate(searchers[0]["thesis"])


@pytest.fixture
def good_company():
    return CompanyProfile(
        company_id="c-x", alias="Proyecto Test", country="US", sector="b2b_services", business_model="b2b_services",
        description="Facility maintenance under multi-year contracts", revenue_usd_m=18, ebitda_usd_m=3.2, ev_usd_m=19,
        ebitda_margin_pct=17.8, fcf_conversion_pct=78, recurring_revenue_pct=75, top_customer_pct=8,
        capex_pct_revenue=2, revenue_growth_pct=8, years_of_financials=5, second_tier_management=True,
        owner_transition_months=12, owner_age=64, defensibility_rating=4, improvement_levers=["sales", "pricing"],
    )
