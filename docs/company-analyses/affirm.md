---
tags: [job-search, company-analysis, engineering-manager, fintech]
company: Affirm
ats: Greenhouse
board_slug: affirm
remote: remote-first
captured: 2026-05-19
comp_floor: 315000
comp_median: 450000
comp_ceiling: 900000
---

# Affirm — Company Analysis

> Captured 2026-05-19 during jobTracker scraper expansion. Comp + culture data from levels.fyi, Glassdoor, Blind.

## At a Glance

| Field | Value |
|---|---|
| ATS | Greenhouse |
| Board URL | https://job-boards.greenhouse.io/affirm |
| API | `boards-api.greenhouse.io/v1/boards/affirm/jobs` |
| Tracker config | `greenhouse_boards["affirm"]` |
| Open reqs | 166 (19 EM-titled) |
| Remote policy | **Remote-first** (US/Canada/UK/Poland/Spain) |
| Public | NASDAQ: AFRM (Jan 2021) |
| Founded | 2012 by Max Levchin (PayPal mafia) |
| Headcount | ~2,000 (post-2023 RIF) |

## Salary — Engineering Manager (levels.fyi, early 2026)

| Level | Total Comp Range | Median |
|---|---|---|
| Manager (M1) | $315K – ~$525K | ~$450K |
| Senior Manager (M2) | $400K – $900K | **$625K** |
| Director | $555K – $920K | **$704K** |
| Top reported package | — | **$880K** |

- NYC area median: **$675K**
- Comp = base + RSU + bonus
- RSUs liquid (public co)

## Business

- BNPL (Buy Now, Pay Later) pioneer. "Pay over time" at checkout, no late fees.
- Partners: Amazon, Shopify, Walmart, Target.
- Growth bet: **Affirm Card** (debit hybrid).
- Tech stack historically Python + Kubernetes; ML-heavy for underwriting/fraud.
- Eng org segments: backend, ML, infra, risk/fraud, servicing platform, comms.

## Ratings + Culture

| Source | Rating |
|---|---|
| Glassdoor overall | 3.9 / 5 (607 reviews) |
| Blind | 3.7 / 5 (409 reviews) |
| Comp/benefits | 4.0 |
| Management | **3.2** (weakest) |
| Culture & values (eng) | 4.5 |
| WLB (eng) | 4.1 |

### Themes
- **Compensation strong, management weak.** Recurring split in reviews.
- "Cutthroat ego-driven", "everyone overworked" surface in some reviews.
- Culture reported "took a dive since 2023 RIF, progressively worse" (staff eng).
- Engineers rate Culture & values 4.5 — still high for fintech.

## Risks

- **2023 RIF:** Cut 19% workforce, killed crypto product. Culture downstream.
- **Mgmt rating 3.2:** Validate during loop. Ask about team-specific dynamics.
- **BNPL macro:** Rate-sensitive, CFPB scrutiny, Klarna/Afterpay competition. Stock volatile.
- **AI layoff stance:** Levchin said "not planning AI-related layoffs, full stop" on Q3 FY2026 earnings. Hiring posture: net-positive.

## Fit for Drew (Mid-to-Senior EM, 21+ yrs)

- Mid-to-senior EM bands ($315K–$900K) match target.
- **Remote-first** removes location constraint — high value.
- 19 EM roles open; will pass tracker keyword filter automatically.
- Public co → RSU comp real, not vapor.
- Comp ceiling 30–40% above JPMC equivalent scope.

## Tracker Integration

```python
# src/config.py
greenhouse_boards = {
    ...
    "affirm": {"display_name": "Affirm"},
}
```

Added in commit `fe9311a` (2026-05-19).

## Sources

- [Affirm Greenhouse board](https://job-boards.greenhouse.io/affirm)
- [Levels.fyi — SEM](https://www.levels.fyi/companies/affirm/salaries/software-engineering-manager)
- [Levels.fyi — Senior Manager](https://www.levels.fyi/companies/affirm/salaries/software-engineering-manager/levels/senior-manager)
- [Levels.fyi — Director](https://www.levels.fyi/companies/affirm/salaries/software-engineering-manager/levels/director)
- [Glassdoor reviews](https://www.glassdoor.com/Reviews/Affirm-Reviews-E823564.htm)
- [Blind reviews](https://www.teamblind.com/company/Affirm/reviews)
- [American Banker — Levchin on AI](https://www.americanbanker.com/payments/news/affirms-levchin-does-not-plan-ai-layoffs)
- [FintechFutures — 2023 layoffs](https://www.fintechfutures.com/bnpl-payments/bnpl-fintech-affirm-lays-off-19-of-workforce-nixes-crypto-offering)
