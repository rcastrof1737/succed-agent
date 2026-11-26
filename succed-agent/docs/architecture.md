# Architecture

## Two layers, one contract

```
             ┌────────────────────────── Claude Code / Agent SDK ──────────────────────────┐
  people ──► │ main session ─ slash commands ─► subagents (layers 0–5)                     │
             │   reads documents, searches the web, judges, drafts, explains               │
             └───────────────┬─────────────────────────────────────────────────────────────┘
                             │ MCP (stdio) — typed tools, JSON in/out
             ┌───────────────▼─────────────────────────────────────────────────────────────┐
             │ succed engine (Python, deterministic, tested)                               │
             │  scoring/ searcher · company · fit      returns.py   thesis.py              │
             │  outreach.py (approval queue, caps)     pipeline.py  documents.py           │
             │  calibration.py (learning loop)         store.py (SQLite → Postgres)        │
             └─────────────────────────────────────────────────────────────────────────────┘
                             ▲
             partners / ops ─┘  CLI: approve drafts, record decisions (human-only actions)
```

**Why the split?** LLMs are excellent at reading a 60-page CIM or a reference call note, and poor at being consistent, auditable calculators. Every number that drives a decision is computed by versioned Python with tests. The agents' job is to supply structured, evidence-backed inputs and to explain the outputs.

## Data model (store.py)

| Table | Purpose |
|---|---|
| `searchers` | SearcherAssessment JSON (ratings + evidence + facts), investor, funding date |
| `theses` | Structured thesis per searcher |
| `companies` | CompanyProfile JSON (alias only before NDA, evidence map) |
| `scores` | Append-only score log with config version and full breakdown |
| `pipeline_events` | Stage transitions, entry multiple at LOI, lost reasons |
| `drafts` | Outbound artefacts and approval status (who, when, note) |
| `decisions` | Partner decisions next to the model score (agreement tracking) |
| `outcomes` | Labelled outcomes and features for calibration |

Production: move to Postgres (for example Supabase, already used by the Lovable front end) with row-level security per investor. The table shapes stay the same.

## Front end (Lovable) integration path

1. Deploy the MCP server with the `streamable-http` transport behind auth, or wrap `succed.service.Service` in a small FastAPI app.
2. The Lovable app (succed.lovable.app) calls these endpoints for the searcher deal feed, the investor cockpit and the owner "meet your successor" flow.
3. Claude Code remains the analyst workbench; the web app is the product surface.

## Model choice per agent (cost and quality)

| Agent | Model | Reason |
|---|---|---|
| searcher-evaluator, diligence-agent | Opus | High-stakes judgment and long documents |
| origination, screening, matching, learning | Sonnet | Volume work with structured outputs |
| Bulk extraction at scale (future) | Haiku | Batch pre-filtering of registry data |
