"""SQLite store. Append-only audit log for scores, approvals and pipeline events.

Swap for Postgres/Supabase in production (same tables; see docs/architecture.md).
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from .clock import utcnow
from .models import CompanyProfile, PipelineEvent, ScoreResult, SearcherAssessment, Thesis

DEFAULT_DB = Path(os.environ.get("SUCCED_DB", Path(__file__).resolve().parent.parent / "data" / "succed.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS investors (id TEXT PRIMARY KEY, name TEXT, profile JSON);
CREATE TABLE IF NOT EXISTS searchers (id TEXT PRIMARY KEY, name TEXT, investor_id TEXT, funded_on TEXT,
                                      assessment JSON, updated_at TEXT);
CREATE TABLE IF NOT EXISTS theses (id TEXT PRIMARY KEY, searcher_id TEXT, body JSON, updated_at TEXT);
CREATE TABLE IF NOT EXISTS companies (id TEXT PRIMARY KEY, alias TEXT, country TEXT, sector TEXT,
                                      source TEXT, profile JSON, updated_at TEXT);
CREATE TABLE IF NOT EXISTS scores (rowid INTEGER PRIMARY KEY AUTOINCREMENT, subject_id TEXT, kind TEXT,
                                   score REAL, band TEXT, config_version TEXT, result JSON, computed_at TEXT);
CREATE TABLE IF NOT EXISTS pipeline_events (rowid INTEGER PRIMARY KEY AUTOINCREMENT, searcher_id TEXT,
                                   company_id TEXT, stage TEXT, on_date TEXT, reason TEXT, entry_ev_ebitda REAL);
CREATE TABLE IF NOT EXISTS drafts (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, searcher_id TEXT,
                                   company_id TEXT, body TEXT, status TEXT, created_at TEXT,
                                   approved_by TEXT, approved_at TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS decisions (rowid INTEGER PRIMARY KEY AUTOINCREMENT, subject_id TEXT, kind TEXT,
                                   decision TEXT, by_whom TEXT, reason TEXT, model_score REAL, at TEXT);
CREATE TABLE IF NOT EXISTS outcomes (subject_id TEXT, kind TEXT, outcome INTEGER, features JSON, recorded_at TEXT);
"""


def _now() -> str:
    return utcnow().isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | str = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    # ------------------------------------------------------------ upserts
    def upsert_searcher(self, a: SearcherAssessment, investor_id: str = "", funded_on: Optional[date] = None) -> None:
        with self.conn() as c:
            c.execute("INSERT OR REPLACE INTO searchers VALUES (?,?,?,?,?,?)",
                      (a.searcher_id, a.name, investor_id, funded_on.isoformat() if funded_on else None,
                       a.model_dump_json(), _now()))

    def upsert_thesis(self, t: Thesis) -> None:
        with self.conn() as c:
            c.execute("INSERT OR REPLACE INTO theses VALUES (?,?,?,?)", (t.thesis_id, t.searcher_id, t.model_dump_json(), _now()))

    def upsert_company(self, co: CompanyProfile) -> None:
        with self.conn() as c:
            c.execute("INSERT OR REPLACE INTO companies VALUES (?,?,?,?,?,?,?)",
                      (co.company_id, co.alias, co.country, co.sector, co.source, co.model_dump_json(), _now()))

    def save_score(self, r: ScoreResult) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO scores (subject_id,kind,score,band,config_version,result,computed_at) VALUES (?,?,?,?,?,?,?)",
                      (r.subject_id, r.kind, r.score, r.band, r.config_version, r.model_dump_json(), r.computed_at.isoformat()))

    def add_event(self, e: PipelineEvent) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO pipeline_events (searcher_id,company_id,stage,on_date,reason,entry_ev_ebitda) VALUES (?,?,?,?,?,?)",
                      (e.searcher_id, e.company_id, e.stage.value, e.on.isoformat(), e.reason, e.entry_ev_ebitda))

    def record_decision(self, subject_id: str, kind: str, decision: str, by_whom: str, reason: str,
                        model_score: Optional[float]) -> None:
        if not reason or len(reason.strip()) < 5:
            raise ValueError("A written reason is required for every partner decision/override")
        with self.conn() as c:
            c.execute("INSERT INTO decisions (subject_id,kind,decision,by_whom,reason,model_score,at) VALUES (?,?,?,?,?,?,?)",
                      (subject_id, kind, decision, by_whom, reason, model_score, _now()))

    def record_outcome(self, subject_id: str, kind: str, outcome: bool, features: dict[str, float]) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO outcomes VALUES (?,?,?,?,?)", (subject_id, kind, int(outcome), json.dumps(features), _now()))

    # ------------------------------------------------------------ reads
    def searchers(self) -> list[SearcherAssessment]:
        with self.conn() as c:
            return [SearcherAssessment.model_validate_json(r["assessment"]) for r in c.execute("SELECT assessment FROM searchers")]

    def searcher(self, sid: str) -> Optional[SearcherAssessment]:
        with self.conn() as c:
            r = c.execute("SELECT assessment FROM searchers WHERE id=?", (sid,)).fetchone()
        return SearcherAssessment.model_validate_json(r["assessment"]) if r else None

    def searcher_meta(self, sid: str) -> dict[str, Any]:
        with self.conn() as c:
            r = c.execute("SELECT investor_id, funded_on FROM searchers WHERE id=?", (sid,)).fetchone()
        return dict(r) if r else {}

    def thesis_for(self, sid: str) -> Optional[Thesis]:
        with self.conn() as c:
            r = c.execute("SELECT body FROM theses WHERE searcher_id=? ORDER BY updated_at DESC", (sid,)).fetchone()
        return Thesis.model_validate_json(r["body"]) if r else None

    def companies(self) -> list[CompanyProfile]:
        with self.conn() as c:
            return [CompanyProfile.model_validate_json(r["profile"]) for r in c.execute("SELECT profile FROM companies")]

    def company(self, cid: str) -> Optional[CompanyProfile]:
        with self.conn() as c:
            r = c.execute("SELECT profile FROM companies WHERE id=?", (cid,)).fetchone()
        return CompanyProfile.model_validate_json(r["profile"]) if r else None

    def latest_score(self, subject_id: str, kind: str) -> Optional[ScoreResult]:
        with self.conn() as c:
            r = c.execute("SELECT result FROM scores WHERE subject_id=? AND kind=? ORDER BY rowid DESC LIMIT 1",
                          (subject_id, kind)).fetchone()
        return ScoreResult.model_validate_json(r["result"]) if r else None

    def events(self, searcher_id: Optional[str] = None) -> list[dict[str, Any]]:
        q, args = "SELECT * FROM pipeline_events", ()
        if searcher_id:
            q, args = q + " WHERE searcher_id=?", (searcher_id,)
        with self.conn() as c:
            return [dict(r) for r in c.execute(q + " ORDER BY on_date, rowid", args)]

    def drafts(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        q, args = "SELECT * FROM drafts", ()
        if status:
            q, args = q + " WHERE status=?", (status,)
        with self.conn() as c:
            return [dict(r) for r in c.execute(q + " ORDER BY id", args)]

    def outcomes(self, kind: str) -> list[dict[str, Any]]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM outcomes WHERE kind=?", (kind,))]

    def decisions(self) -> list[dict[str, Any]]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM decisions ORDER BY rowid")]
