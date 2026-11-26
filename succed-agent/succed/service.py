"""Thin service layer shared by the MCP server and the CLI. Returns plain JSON-able dicts."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Optional

from . import calibration, documents, ingest, outreach, pipeline, returns, thesis as thesis_mod
from .models import CompanyProfile, SearcherAssessment, Thesis
from .scoring import rank_matches, score_company, score_fit, score_searcher
from .store import Store


class Service:
    def __init__(self, db: Optional[str | Path] = None):
        self.store = Store(db) if db else Store()

    # ---------------- Layer 0: searcher selection
    def score_searcher(self, assessment: dict, investor_id: str = "", funded_on: Optional[str] = None) -> dict:
        a = SearcherAssessment.model_validate(assessment)
        r = score_searcher(a)
        self.store.upsert_searcher(a, investor_id, date.fromisoformat(funded_on) if funded_on else None)
        self.store.save_score(r)
        return r.model_dump(mode="json")

    def record_partner_decision(self, subject_id: str, kind: str, decision: str, by_whom: str, reason: str) -> dict:
        s = self.store.latest_score(subject_id, kind)
        self.store.record_decision(subject_id, kind, decision, by_whom, reason, s.score if s else None)
        return {"ok": True, "model_score": s.score if s else None}

    def save_thesis(self, thesis: dict) -> dict:
        t = Thesis.model_validate(thesis)
        self.store.upsert_thesis(t)
        return {"ok": True, "thesis_id": t.thesis_id}

    def size_thesis(self, thesis: dict, scale_factor: float = 1.0) -> dict:
        t = Thesis.model_validate(thesis)
        return thesis_mod.size_universe(t, self.store.companies(), scale_factor)

    # ---------------- Layer 1: origination
    def import_companies(self, path: str) -> dict:
        cos = ingest.dedupe(ingest.load_any(path))
        for c in cos:
            self.store.upsert_company(c)
        return {"imported": len(cos), "ids": [c.company_id for c in cos]}

    def upsert_company(self, company: dict) -> dict:
        c = CompanyProfile.model_validate(company)
        self.store.upsert_company(c)
        return {"ok": True, "company_id": c.company_id}

    # ---------------- Layer 2: screening
    def score_company(self, company_id: str) -> dict:
        c = self.store.company(company_id)
        if not c:
            return {"error": f"company {company_id} not found"}
        r = score_company(c)
        self.store.save_score(r)
        return r.model_dump(mode="json")

    def score_all_companies(self) -> list[dict]:
        out = []
        for c in self.store.companies():
            r = score_company(c)
            self.store.save_score(r)
            out.append({"company_id": c.company_id, "alias": c.alias, "score": r.score,
                        "ci": r.confidence_halfwidth, "band": r.band, "knockouts": r.knockouts})
        return sorted(out, key=lambda x: -x["score"])

    # ---------------- Layer 3: matching
    def match(self, searcher_id: str, top_n: int = 10, similarities: Optional[dict[str, float]] = None) -> dict:
        s = self.store.searcher(searcher_id)
        if not s:
            return {"error": f"searcher {searcher_id} not found"}
        th = self.store.thesis_for(searcher_id)
        if not th:
            return {"error": "no thesis saved for this searcher"}
        ss = self.store.latest_score(searcher_id, "searcher") or score_searcher(s)
        results = []
        for c in self.store.companies():
            cs = self.store.latest_score(c.company_id, "company") or score_company(c)
            f = score_fit(s, ss, th, c, cs, (similarities or {}).get(c.company_id))
            self.store.save_score(f)
            results.append(f)
        ranked = rank_matches(results)
        gated = [r for r in results if r.band == "gated_out"]
        return {
            "searcher_id": searcher_id, "searcher_score": ss.score,
            "introduce": [{"company_id": r.subject_id.split("::")[1], "fit": r.score,
                           "reasons": r.reasons} for r in ranked[:top_n]],
            "hold": [r.subject_id.split("::")[1] for r in results if r.band == "hold"],
            "gated_out_count": len(gated),
        }

    # ---------------- Layer 4: execution
    def draft(self, kind: str, searcher_id: str, company_id: str, body: str) -> dict:
        return {"draft_id": outreach.create_draft(self.store, kind, searcher_id, company_id, body),
                "status": "pending_approval"}

    def approve_draft(self, draft_id: int, approver: str, note: str = "") -> dict:
        outreach.approve(self.store, draft_id, approver, note)
        return {"ok": True}

    def list_drafts(self, status: Optional[str] = None) -> list[dict]:
        return self.store.drafts(status)

    def loi(self, company_id: str, buyer_entity: str, ev_usd_m: float, **kw: Any) -> dict:
        c = self.store.company(company_id)
        if not c:
            return {"error": "company not found"}
        return {"markdown": documents.loi_draft(c, buyer_entity, ev_usd_m, **kw)}

    def ic_memo(self, searcher_id: str, company_id: str, **kw: Any) -> dict:
        c = self.store.company(company_id)
        s = self.store.searcher(searcher_id)
        if not c or not s:
            return {"error": "searcher or company not found"}
        cs = self.store.latest_score(company_id, "company") or score_company(c)
        fit = self.store.latest_score(f"{searcher_id}::{company_id}", "fit")
        case = returns.case_from_dict(kw.pop("case", {})) if kw.get("case") else None
        return {"markdown": documents.ic_memo(c, cs, fit, s.name, case, **kw)}

    def advance(self, searcher_id: str, company_id: str, stage: str, on: Optional[str] = None,
                reason: str = "", entry_ev_ebitda: Optional[float] = None) -> dict:
        pipeline.advance(self.store, searcher_id, company_id, stage, date.fromisoformat(on) if on else date.today(),
                         reason, entry_ev_ebitda)
        return {"ok": True}

    # ---------------- Layer 5: learning & reporting
    def scorecard(self, as_of: Optional[str] = None, investor_id: Optional[str] = None) -> dict:
        return pipeline.scorecard(self.store, date.fromisoformat(as_of) if as_of else None, investor_id)

    def record_outcome(self, subject_id: str, kind: str, outcome: bool) -> dict:
        s = self.store.latest_score(subject_id, kind)
        feats = {d.name: (d.raw or 0.0) for d in s.dimensions} if s else {}
        self.store.record_outcome(subject_id, kind, outcome, feats)
        return {"ok": True, "features_recorded": list(feats)}

    def calibrate(self, kind: str = "searcher") -> dict:
        rows = [{"features": __import__("json").loads(r["features"]), "outcome": r["outcome"]}
                for r in self.store.outcomes(kind)]
        cfg = "scoring/searcher_v1" if kind == "searcher" else "scoring/company_v1"
        return calibration.calibrate(rows, kind, cfg)

    def returns_levers(self, base: Optional[dict] = None, target: Optional[dict] = None) -> list[dict]:
        b = returns.case_from_dict(base or {})
        return returns.lever_table(b, target or returns.SUCCED_TARGET)
