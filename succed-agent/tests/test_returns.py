from datetime import date

from succed.returns import SearchCase, evaluate, lever_table, xirr


def test_blueprint_table_reproduced():
    t = {r["scenario"]: r for r in lever_table()}
    assert t["Baseline"]["irr_pct"] == 16.8 and t["Baseline"]["moic"] == 2.26
    assert t["Only search_months"]["irr_pct"] == 17.1
    assert t["Only p_acquire"]["irr_pct"] == 17.3
    assert t["Only entry_multiple"]["irr_pct"] == 19.0
    assert t["Only ebitda_growth"]["irr_pct"] == 19.0
    assert t["All levers (Succed target)"]["irr_pct"] == 22.1
    assert t["All levers (Succed target)"]["moic"] == 2.80


def test_speed_is_the_weakest_lever():
    rows = {r["scenario"]: r["irr_pct"] for r in lever_table()}
    base = rows["Baseline"]
    assert rows["Only search_months"] - base < rows["Only entry_multiple"] - base


def test_xirr_matches_known_value():
    # -100 today, +121 in two years -> 10%
    r = xirr([(date(2024, 1, 1), -100), (date(2026, 1, 1), 121)])
    assert abs(r - 0.10) < 0.002


def test_deal_level_no_search():
    r = evaluate(SearchCase(search_months=0, p_acquire=1.0, search_capital_usd_m=0.0))
    assert r.moic > 1 and r.irr > 0
