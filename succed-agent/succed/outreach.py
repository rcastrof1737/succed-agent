"""Human-in-the-loop queue for anything that leaves the platform.

Agents may only CREATE drafts. Nothing in this package sends email/LinkedIn/WhatsApp. A draft becomes
exportable only after a named human approves it. Volume caps protect owners from spam.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .clock import utcnow
from .store import Store

KINDS = {"owner_outreach", "loi", "ic_memo", "investor_update", "intro"}
MAX_OWNER_OUTREACH_PER_SEARCHER_PER_WEEK = 40
FORBIDDEN_PHRASES = ["guaranteed", "garantizado", "risk-free", "sin riesgo", "we will pay", "pagaremos"]


class OutreachPolicyError(ValueError):
    pass


def create_draft(store: Store, kind: str, searcher_id: str, company_id: str, body: str) -> int:
    if kind not in KINDS:
        raise OutreachPolicyError(f"Unknown draft kind {kind}")
    low = body.lower()
    hits = [p for p in FORBIDDEN_PHRASES if p in low]
    if hits:
        raise OutreachPolicyError(f"Draft contains prohibited claims: {hits}")
    if kind == "owner_outreach":
        week_ago = (utcnow() - timedelta(days=7)).isoformat()
        with store.conn() as c:
            n = c.execute("SELECT COUNT(*) FROM drafts WHERE kind='owner_outreach' AND searcher_id=? AND created_at>=?",
                          (searcher_id, week_ago)).fetchone()[0]
            dup = c.execute("SELECT COUNT(*) FROM drafts WHERE kind='owner_outreach' AND company_id=? AND status!='rejected' "
                            "AND searcher_id!=? AND created_at>=?", (company_id, searcher_id,
                            (utcnow() - timedelta(days=21)).isoformat())).fetchone()[0]
        if n >= MAX_OWNER_OUTREACH_PER_SEARCHER_PER_WEEK:
            raise OutreachPolicyError("Weekly owner-outreach cap reached for this searcher")
        if dup:
            raise OutreachPolicyError("Another searcher holds the 21-day exclusivity window on this owner")
    with store.conn() as c:
        cur = c.execute("INSERT INTO drafts (kind,searcher_id,company_id,body,status,created_at) VALUES (?,?,?,?,?,?)",
                        (kind, searcher_id, company_id, body, "pending_approval", utcnow().isoformat()))
        return int(cur.lastrowid)


def approve(store: Store, draft_id: int, approver: str, note: str = "") -> None:
    if not approver or approver.lower() in {"agent", "claude", "ai", "system"}:
        raise OutreachPolicyError("Approval must come from a named human")
    with store.conn() as c:
        r = c.execute("SELECT status FROM drafts WHERE id=?", (draft_id,)).fetchone()
        if not r:
            raise OutreachPolicyError("Draft not found")
        if r["status"] != "pending_approval":
            raise OutreachPolicyError(f"Draft is {r['status']}")
        c.execute("UPDATE drafts SET status='approved', approved_by=?, approved_at=?, note=? WHERE id=?",
                  (approver, utcnow().isoformat(), note, draft_id))


def reject(store: Store, draft_id: int, approver: str, note: str) -> None:
    with store.conn() as c:
        c.execute("UPDATE drafts SET status='rejected', approved_by=?, approved_at=?, note=? WHERE id=?",
                  (approver, utcnow().isoformat(), note, draft_id))


def export_approved(store: Store) -> list[dict]:
    """Approved drafts, ready for a human to send from their own mailbox/CRM."""
    return store.drafts("approved")
