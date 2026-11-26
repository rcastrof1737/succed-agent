import pytest

from succed.models import DimensionRating, Evidence, SearcherAssessment
from succed.scoring import rank_matches, score_company, score_fit, score_searcher
from succed.scoring.searcher import ProtectedAttributeError, in_search_alerts


def test_strong_searcher_passes_gate(strong_searcher):
    a, _ = strong_searcher
    r = score_searcher(a)
    assert r.score >= 70
    assert r.band in ("fast_track", "standard_review")
    assert abs(sum(d.points for d in r.dimensions) - r.score) < 0.2
    assert r.config_version == "searcher-v1.0"


def test_unevidenced_rating_is_ignored(searchers):
    a = SearcherAssessment.model_validate(searchers[2]["assessment"])
    r = score_searcher(a)
    net = next(d for d in r.dimensions if d.name == "network_origination")
    assert net.raw is None and net.points == 0
    assert any("no evidence" in w for w in r.warnings)


def test_factual_caps_apply(searchers):
    a = SearcherAssessment.model_validate(searchers[2]["assessment"])  # universe 80, part-time, 12m runway
    r = score_searcher(a)
    tq = next(d for d in r.dimensions if d.name == "thesis_quality")
    cs = next(d for d in r.dimensions if d.name == "commitment_structure")
    assert tq.raw == 2.5 and "universe" in tq.note
    assert cs.raw <= 1.5
    assert r.score < 70


def test_protected_attribute_rejected():
    a = SearcherAssessment(searcher_id="x", name="x", ratings={
        "age": DimensionRating(rating=5, evidence=[Evidence(text="should never be scored", source="cv")])})
    with pytest.raises(ProtectedAttributeError):
        score_searcher(a)


def test_good_company_scores_high(good_company):
    r = score_company(good_company)
    assert r.score >= 80 and r.band == "pass" and not r.knockouts
    assert r.confidence_halfwidth == 3.0  # complete data


def test_knockouts(good_company):
    c = good_company.model_copy(update={"top_customer_pct": 40})
    assert score_company(c).score <= 55
    c = good_company.model_copy(update={"flags": {"distressed": True}})
    assert score_company(c).score <= 30
    c = good_company.model_copy(update={"ebitda_usd_m": 0.7, "ev_usd_m": 4})
    r = score_company(c)
    assert r.route == "self_funded_tier" and r.band == "below_threshold"


def test_missing_data_lowers_confidence_not_invents(good_company):
    c = good_company.model_copy(update={"fcf_conversion_pct": None, "years_of_financials": None,
                                        "second_tier_management": None, "owner_transition_months": None,
                                        "recurring_revenue_pct": None, "capex_pct_revenue": None})
    r = score_company(c)
    assert r.confidence_halfwidth > 3
    assert r.low_confidence
    assert r.score < score_company(good_company).score


def test_ev_inferred_is_flagged(good_company):
    r = score_company(good_company.model_copy(update={"ev_usd_m": None}))
    assert any("inferred" in w for w in r.warnings)


def test_fit_gate_and_ranking(strong_searcher, good_company):
    a, th = strong_searcher
    ss = score_searcher(a)
    cs = score_company(good_company)
    f = score_fit(a, ss, th, good_company, cs, semantic_similarity=0.9)
    assert f.band == "introduce" and f.score >= 70
    weak = good_company.model_copy(update={"company_id": "c-y", "flags": {"distressed": True}})
    fw = score_fit(a, ss, th, weak, score_company(weak))
    assert fw.band == "gated_out" and fw.score == 0
    # exclusivity cap: 6 searchers on one company -> max 4 kept
    clones = [f.model_copy(update={"subject_id": f"s{i}::c-x", "score": 70 + i}) for i in range(6)]
    assert len(rank_matches(clones)) == 4


def test_low_confidence_uses_lower_bound(strong_searcher, good_company):
    a, th = strong_searcher
    sparse = good_company.model_copy(update={"fcf_conversion_pct": None, "years_of_financials": None,
                                             "second_tier_management": None, "owner_transition_months": None,
                                             "capex_pct_revenue": None})
    cs = score_company(sparse)
    f = score_fit(a, score_searcher(a), th, sparse, cs)
    if cs.low_confidence and cs.lower_bound < 70:
        assert f.band == "gated_out"


def test_in_search_alerts():
    alerts = in_search_alerts(months_in_search=7, lois_signed=0, owner_convos_per_week=2, companies_screened_last_month=10)
    assert len(alerts) == 3 and "No LOI" in alerts[0]
