from datetime import date

import pytest

from succed import calibration, outreach
from succed.config import ConfigError, _validate


def test_demo_flow_end_to_end(demo):
    m = demo.match("s-001")
    assert m["searcher_score"] >= 70
    assert m["introduce"], "strong demo searcher should get at least one introduction"
    for x in m["introduce"]:
        assert x["fit"] >= 70
        assert demo.store.company(x["company_id"]).country in ("US", "ES")  # thesis geographies only
    m3 = demo.match("s-003")
    assert m3["introduce"] == [] and m3["searcher_score"] < 70
    sc = demo.scorecard(as_of="2026-11-26")
    assert sc["companies_scored"] == 40
    assert "Demo Searcher B" in sc["alerts"]  # funded Jan 2026, no LOI by month 6


def test_thesis_sizing_warns_on_small_universe(demo, searchers):
    r = demo.size_thesis(searchers[2]["thesis"])
    assert r["estimated_universe"] < 300 and r["warnings"]


def test_outreach_requires_human_approval(demo):
    d = demo.draft("owner_outreach", "s-001", "c-001", "Hola, me gustaría conversar sobre el futuro de su empresa.")
    assert d["status"] == "pending_approval"
    with pytest.raises(outreach.OutreachPolicyError):
        demo.approve_draft(d["draft_id"], "claude")
    demo.approve_draft(d["draft_id"], "Partner Name")
    assert demo.list_drafts("approved")[0]["approved_by"] == "Partner Name"


def test_outreach_policies(demo):
    with pytest.raises(outreach.OutreachPolicyError):
        demo.draft("owner_outreach", "s-001", "c-002", "Le pagaremos un precio garantizado")
    demo.draft("owner_outreach", "s-001", "c-003", "Hola, conversemos con calma.")
    with pytest.raises(outreach.OutreachPolicyError, match="exclusivity"):
        demo.draft("owner_outreach", "s-002", "c-003", "Hola, conversemos con calma.")


def test_loi_and_memo_render(demo):
    loi = demo.loi("c-001", "Demo Search LLC", 17.3, jurisdiction="CL")["markdown"]
    assert "BORRADOR" in loi and "US$17.30 millones" in loi and "FNE" in loi
    with pytest.raises(ValueError):
        demo.loi("c-001", "X", 10, cash_at_close_pct=90)
    memo = demo.ic_memo("s-001", "c-001", risks="- concentration")["markdown"]
    assert "Investment memo" in memo and "$" not in memo.replace("US$", "")


def test_pipeline_and_lost_reason(demo):
    demo.advance("s-001", "c-001", "contacted", "2026-11-01")
    demo.advance("s-001", "c-001", "loi", "2026-11-20", entry_ev_ebitda=5.9)
    with pytest.raises(ValueError):
        demo.advance("s-001", "c-002", "lost", "2026-11-20")
    sc = demo.scorecard(as_of="2026-11-26")
    assert sc["funnel"]["loi"] == 1 and sc["median_entry_ev_ebitda_at_loi"] == 5.9


def test_partner_decision_needs_reason(demo):
    with pytest.raises(ValueError):
        demo.record_partner_decision("s-001", "searcher", "approve", "Partner", "")
    demo.record_partner_decision("s-001", "searcher", "approve", "Partner", "Strong operator, focused thesis")
    assert demo.scorecard()["partner_agreement_with_searcher_score"] == 1.0


def test_calibration_guards():
    assert calibration.calibrate([{"features": {}, "outcome": 1}] * 5)["status"] == "insufficient_data"
    with pytest.raises(ValueError):
        calibration.calibrate([{"features": {"gender": 1}, "outcome": 1}] * 40)


def test_calibration_recovers_signal():
    import numpy as np
    rng = np.random.default_rng(0)
    rows = []
    for _ in range(200):
        f = {d: float(rng.uniform(0, 5)) for d in ["operator_capability", "search_readiness", "thesis_quality",
             "thesis_founder_fit", "coachability_judgment", "network_origination", "commitment_structure"]}
        p = 1 / (1 + np.exp(-(f["operator_capability"] - 2.5) * 1.5))
        rows.append({"features": f, "outcome": int(rng.uniform() < p)})
    r = calibration.calibrate(rows)
    assert r["status"] == "ok" and r["auc_fitted"] > 0.75
    sw = r["suggested_weights_blended"]
    assert sw["operator_capability"] == max(sw.values())


def test_config_validation():
    with pytest.raises(ConfigError):
        _validate("x", {"dimensions": {"a": {"weight": 60}, "b": {"weight": 30}}})
    with pytest.raises(ConfigError):
        _validate("x", {"dimensions": {"age": {"weight": 100}}, "protected_attributes": ["age"]})


def test_mcp_server_registers_tools():
    import asyncio
    from succed import mcp_server
    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert {"score_searcher", "score_company", "match", "create_draft", "scorecard", "calibrate"} <= names
    assert "approve_draft" not in names  # approval is human-only (CLI)
