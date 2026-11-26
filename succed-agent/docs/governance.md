# Governance, compliance and controls

## Human-in-the-loop controls (enforced in code)

| Control | Where |
|---|---|
| Agents can create drafts but cannot approve them; the approver must be a named human | `outreach.approve`, MCP has no approve tool, `.claude/settings.json` denies `succed approve` |
| Weekly owner-outreach cap per searcher (40); 21-day owner exclusivity | `outreach.create_draft` |
| Prohibited claims in drafts ("guaranteed", "risk-free", promises to pay) | `outreach.FORBIDDEN_PHRASES` |
| Max 4 searchers introduced per company | `scoring/fit.rank_matches` |
| Partner decisions and overrides need a written reason | `store.record_decision` |
| Lost deals need a reason | `pipeline.advance` |
| Protected attributes rejected | `config._validate`, `scoring/searcher._check_protected`, `calibration.calibrate` |
| Every score stores its config version and full breakdown | `scores` table |

## Regulatory checklist before going live (get local counsel)

- **Success fees and intermediation:** broker/finder licensing varies by US state; check securities rules if Succed touches investor syndication (US, Spain/CNMV, Chile/CMF, Mexico, Colombia).
- **Data protection:** Chile Law 21.719; GDPR (Spain/EU); US state privacy laws. Lawful basis for owner outreach; retention limits; data subject rights.
- **Data sourcing:** licensed data and official registries; respect site terms; no scraping behind logins.
- **SBA 7(a):** eligibility is deal- and borrower-specific; verify against the current SOP. It is not a default assumption.
- **Merger control and foreign investment:** thresholds by country (see the LOI templates).

## Scoring-config change log

| Date | Version | Change | Approved by |
|---|---|---|---|
| 2026-11-26 | searcher-v1.0 / company-v1.0 / fit-v1.0 | Initial hypotheses from the Succed 2.0 blueprint | _pending partner sign-off_ |
