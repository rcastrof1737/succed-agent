"""Command line for partners and operators.  `succed --help`

Human-only actions (approving drafts, recording partner decisions) live here on purpose:
agents can create drafts through MCP but cannot approve them.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .service import Service

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "sample"


def _print(x) -> None:
    print(json.dumps(x, indent=2, ensure_ascii=False, default=str))


def load_demo(svc: Service) -> dict:
    """Load the SYNTHETIC demo dataset (fictitious companies and searchers)."""
    out = svc.import_companies(str(SAMPLE / "companies.csv"))
    searchers = json.loads((SAMPLE / "searchers.json").read_text(encoding="utf-8"))
    for s in searchers:
        svc.score_searcher(s["assessment"], s.get("investor_id", ""), s.get("funded_on"))
        svc.save_thesis(s["thesis"])
    svc.score_all_companies()
    return {"companies": out["imported"], "searchers": len(searchers)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="succed", description=__doc__)
    p.add_argument("--db", help="SQLite path (default data/succed.db or $SUCCED_DB)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo", help="Load synthetic demo data and score it")
    a = sub.add_parser("score-searcher", help="Score a SearcherAssessment JSON file")
    a.add_argument("file")
    a.add_argument("--investor", default="")
    a.add_argument("--funded-on")
    a = sub.add_parser("import", help="Import companies CSV/JSON")
    a.add_argument("file")
    sub.add_parser("score-companies")
    a = sub.add_parser("match")
    a.add_argument("searcher_id")
    a.add_argument("--top", type=int, default=10)
    a = sub.add_parser("scorecard")
    a.add_argument("--as-of")
    a.add_argument("--investor")
    a = sub.add_parser("drafts")
    a.add_argument("--status")
    a = sub.add_parser("approve", help="HUMAN approval of a draft")
    a.add_argument("draft_id", type=int)
    a.add_argument("--by", required=True, help="Your name")
    a.add_argument("--note", default="")
    a = sub.add_parser("decide", help="Record a partner decision with reason")
    a.add_argument("subject_id")
    a.add_argument("--kind", default="searcher")
    a.add_argument("--decision", required=True)
    a.add_argument("--by", required=True)
    a.add_argument("--reason", required=True)
    sub.add_parser("returns", help="Illustrative IRR/MOIC lever table")
    a = sub.add_parser("calibrate")
    a.add_argument("--kind", default="searcher")
    args = p.parse_args(argv)
    svc = Service(args.db)

    if args.cmd == "demo":
        _print(load_demo(svc))
    elif args.cmd == "score-searcher":
        _print(svc.score_searcher(json.loads(Path(args.file).read_text()), args.investor, args.funded_on))
    elif args.cmd == "import":
        _print(svc.import_companies(args.file))
    elif args.cmd == "score-companies":
        _print(svc.score_all_companies())
    elif args.cmd == "match":
        _print(svc.match(args.searcher_id, args.top))
    elif args.cmd == "scorecard":
        _print(svc.scorecard(args.as_of, args.investor))
    elif args.cmd == "drafts":
        _print(svc.list_drafts(args.status))
    elif args.cmd == "approve":
        _print(svc.approve_draft(args.draft_id, args.by, args.note))
    elif args.cmd == "decide":
        _print(svc.record_partner_decision(args.subject_id, args.kind, args.decision, args.by, args.reason))
    elif args.cmd == "returns":
        _print(svc.returns_levers())
    elif args.cmd == "calibrate":
        _print(svc.calibrate(args.kind))
    return 0


if __name__ == "__main__":
    sys.exit(main())
