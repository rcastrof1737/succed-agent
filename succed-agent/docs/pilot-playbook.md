# 90-day pilot playbook (Altos Andes)

Goal: 1–2 portfolio searchers; **10 companies with Company ≥ 70 and Fit ≥ 70 within 14 days**; then **≥ 3 LOIs or 1 close** by day 90.

| Window | Commands | Exit criterion |
|---|---|---|
| Days 0–14 | `/evaluate-searcher` (back-fill the pilot searchers), `/build-thesis`, import partner feeds, `/screen-company` on each teaser, `/match` | 10 introductions with partner review of every score |
| Days 15–45 | `/source`, `/draft-outreach` (approved by a human), back-test the Searcher Score on past applicants plus `succed decide` | ≥ 15 owner conversations; ≥ 80% partner agreement on past cases |
| Days 46–90 | `/draft-loi`, `/ic-memo`, `/pilot-scorecard` every Monday | ≥ 3 LOIs or 1 close; first LOI before month 6 of search |

## Weekly cadence

- **Monday:** run `/pilot-scorecard altos-andes` and send it to the partners.
- **Daily:** check the approval queue with `python -m succed.cli drafts --status pending_approval`.
- **Monthly:** board review of in-search alerts for each searcher.
- **Quarterly:** `/calibrate` model review.

## What to measure, so the IRR/MOIC levers become evidence

- Entry EV/EBITDA at LOI for Succed-sourced vs broker-sourced deals (`advance_pipeline … entry_ev_ebitda`).
- Months to first LOI.
- Share of introductions that reach a partner meeting.
- Score-to-outcome correlation (calibration AUC).
