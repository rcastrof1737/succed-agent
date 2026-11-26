"""Company Score (0–100) with confidence interval and structured knock-outs."""
from __future__ import annotations

from typing import Any, Optional

from .. import config
from ..models import CompanyProfile, DimensionResult, ScoreResult
from .common import OPS, piecewise

CFG_NAME = "scoring/company_v1"


def _completeness(d: dict[str, Any], required: list[str]) -> float:
    present = sum(1 for f in required if d.get(f) is not None)
    return present / len(required) if required else 1.0


def score_company(company: CompanyProfile, cfg_name: str = CFG_NAME) -> ScoreResult:
    cfg = config.load(cfg_name)
    d = company.derived()
    warnings: list[str] = []

    if d.get("ev_usd_m") is None and d.get("ebitda_usd_m") is not None:
        mult = cfg["assumed_ev_ebitda_multiple"]
        d["ev_usd_m"] = d["ebitda_usd_m"] * mult
        warnings.append(f"EV inferred at {mult}x EBITDA (assumption, not a quote)")

    completeness = _completeness(d, cfg["required_fields"])
    dims: list[DimensionResult] = []
    total = 0.0

    for name, spec in cfg["dimensions"].items():
        w = float(spec["weight"])
        sub: Optional[float]
        note = ""
        if spec.get("computed") == "completeness":
            sub = completeness
            note = f"{completeness:.0%} of required fields"
        elif "parts" in spec:
            acc, share_used = 0.0, 0.0
            for p in spec["parts"]:
                v = d.get(p["field"])
                if p.get("bool"):
                    s = None if v is None else (1.0 if v else 0.0)
                else:
                    s = piecewise(v, p["points"])
                if s is not None:
                    acc += s * p["share"]
                    share_used += p["share"]
            # re-normalise over available parts, but haircut for missing ones
            sub = None if share_used == 0 else (acc / share_used) * (0.5 + 0.5 * share_used)
            if 0 < share_used < 1:
                note = f"partial data ({share_used:.0%} of inputs)"
        else:
            sub = piecewise(d.get(spec["field"]), spec["points"])
        if sub is None:
            warnings.append(f"{name}: no data")
            pts = 0.0
        else:
            pts = w * sub
        total += pts
        dims.append(DimensionResult(name=name, weight=w, raw=None if sub is None else round(sub, 3),
                                    points=round(pts, 2), note=note))

    score = total
    knock, route = [], None
    flags = d.get("flags") or {}
    for k in cfg.get("knockouts", []):
        hit = False
        if "flag" in k:
            hit = bool(flags.get(k["flag"]))
        else:
            v = d.get(k["field"])
            hit = v is not None and OPS[k["op"]](v, k["value"])
        if not hit:
            continue
        knock.append(k["reason"])
        if k["effect"] == "cap":
            score = min(score, k["cap"])
        elif k["effect"] == "route":
            route = k["route"]

    c = cfg["confidence"]
    halfwidth = round(c["base"] + c["spread"] * (1 - completeness), 1)
    low_conf = completeness < c["low_confidence_below_completeness"]
    score = round(score, 1)
    top = sorted((x for x in dims if x.raw is not None), key=lambda x: -(x.points / x.weight))
    reasons = [f"strong {x.name} ({x.raw:.2f})" for x in top[:3]]
    reasons += [f"weak {x.name} ({x.raw:.2f})" for x in top[-2:] if x.raw is not None and x.raw < 0.5]
    passed = score >= cfg["pass_threshold"] and route is None
    return ScoreResult(
        subject_id=company.company_id, kind="company", score=score,
        band="pass" if passed else "below_threshold",
        action="Eligible for matching" if passed else ("Route: " + route if route else "Do not match"),
        confidence_halfwidth=halfwidth, low_confidence=low_conf, dimensions=dims, knockouts=knock,
        route=route, reasons=reasons, warnings=warnings, config_version=cfg["version"],
    )
