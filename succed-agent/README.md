# Succed: AI deal-matching for search funds

Succed connects **searchers** (entrepreneurs through acquisition), **SMB owners** looking for a successor, and **investors** such as Altos Andes Capital. It runs as an agent platform inside **Claude Code**: six specialist subagents cover the five AI layers plus searcher selection, and a deterministic, tested Python engine scores, gates and audits everything the agents propose.

> **Design principle:** the LLM reads and proposes; the engine scores; humans approve anything that leaves the platform.

## The AI layers

| Layer | Claude Code subagent | What it does | Engine (MCP `succed`) |
|---|---|---|---|
| 0. Searcher selection | `searcher-evaluator` | Reads CV, thesis, references and case notes, then rates 7 dimensions with cited evidence | Searcher Score 0–100, bands, factual caps, protected-attribute guard |
| 1. Origination | `origination-agent` | Builds owner-transition target lists from registries and partner feeds; drafts owner outreach | Import/dedupe, outreach queue with caps and 21-day exclusivity |
| 2. Screening | `screening-agent` | Extracts a CompanyProfile from teasers, CIMs and financials with page-level evidence; flags red flags | Company Score 0–100 ± confidence, knock-outs |
| 3. Matching | `matching-agent` | Judges semantic fit and explains each introduction | Fit Index, ≥70/≥70 gate, geography and thesis holds, max 4 searchers per company |
| 4. Diligence and execution | `diligence-agent` | QoE pre-check, LOI (US/ES/CL/MX/CO templates), IC memo with returns model | LOI and memo rendering, pipeline stages |
| 5. Learning loop | `learning-agent` | Weekly investor scorecard, monthly board alerts, quarterly recalibration | Scorecard, in-search alerts, logistic calibration with fairness guard |

See [`docs/architecture.md`](docs/architecture.md) for the full design.

## Quick start

```bash
git clone <this repo> && cd succed-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # add ,agent for the Agent SDK runner
pytest                            # 26 tests
python -m succed.cli demo         # loads SYNTHETIC data (fictitious companies/searchers)
python -m succed.cli match s-001
```

### In Claude Code

```bash
cd succed-agent
claude                            # approve the project MCP server "succed" when prompted
```

Then try:

```
/demo
/screen-company data/sample/teaser_proyecto_faro.md
/match s-001
/draft-outreach s-001 c-001 es
/pilot-scorecard altos-andes 2026-11-26
/returns
```

Outbound drafts wait for a **human** approval, which agents cannot give:

```bash
python -m succed.cli drafts --status pending_approval
python -m succed.cli approve 1 --by "Rodrigo Castro" --note "OK to send from my mailbox"
```

### Headless (scheduled jobs, CI, back-office)

```bash
pip install -e ".[agent]"
python -m succed.agent_runner "/pilot-scorecard altos-andes"
```

The runner uses the same subagents, commands and MCP server. It cannot use Bash, cannot edit files and cannot approve drafts.

### Other MCP clients (Claude Desktop, etc.)

Point the client at `python -m succed.mcp_server` (stdio) and set `SUCCED_DB` to the database path.

## Repository map

```
CLAUDE.md                  operating rules Claude follows in this repo
.claude/agents/            6 subagents (layers 0–5)
.claude/commands/          12 slash commands
.claude/skills/            scoring reference skill
.claude/settings.json      permissions: approvals and network calls denied to agents
.mcp.json                  registers the succed MCP server
succed/                    engine: scoring/, returns, thesis, store, outreach, pipeline, documents, calibration, mcp_server, cli
config/scoring/*.yaml      versioned weights (partners tune them; no code change)
config/investors/          investor profiles (Altos Andes: published criteria + flagged hypotheses)
templates/                 LOIs by jurisdiction, IC memo, owner outreach (ES/EN)
data/sample/               SYNTHETIC demo data only
docs/                      architecture, scoring methodology, governance, pilot playbook, roadmap
tests/                     pytest suite (scoring, gates, policies, returns, calibration, MCP)
```

## Important

- **Demo data is fictitious.** Load real deals into a private database (`SUCCED_DB`), never into `data/sample/`.
- **Not legal or investment advice.** LOIs and memos are drafts for counsel and the investment committee.
- The illustrative IRR/MOIC model (`/returns`) represents a **median** search under stated assumptions. It is not a forecast and not a benchmark.
- Scoring weights are v1 **hypotheses** based on public criteria and the Stanford GSB / IESE search fund studies. Calibrate them on outcomes before relying on them.
