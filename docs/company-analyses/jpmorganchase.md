---
tags: [job-search, company-analysis, engineering-manager, financial-services]
company: JPMorganChase
ats: Oracle HCM Cloud
tenant: jpmc
site_number: CX_1001
remote: 3-day in-office minimum
captured: 2026-05-19
comp_floor: 170000
comp_median: 272000
comp_ceiling: 600000
---

# JPMorganChase — Company Analysis

> Captured 2026-05-19 during jobTracker scraper expansion. Comp + culture data from levels.fyi, Glassdoor, Indeed, SEC filings.

## At a Glance

| Field | Value |
|---|---|
| ATS | Oracle HCM Cloud (Oracle Recruiting CE) |
| Board URL | https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs |
| API | `jpmc.fa.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions` |
| Tracker config | `oracle_companies["jpmc"]` |
| Open reqs (global) | 7,381 |
| US EM-titled (filtered) | ~25 per scrape |
| Remote policy | **3-day in-office min** (Tue–Thu, trending toward 5) |
| Public | NYSE: JPM |
| CEO | Jamie Dimon (since 2005) |
| Assets | ~$4.1T (largest US bank) |
| Tech budget 2026 | **~$19.8B** (+10% YoY, largest in industry) |
| Technologists globally | ~63,000 |

## Salary — Engineering Manager (levels.fyi, May 2026)

| Level (JPMC ladder) | Total Comp Range | Median |
|---|---|---|
| **Vice President (VP)** — first mgr level | $170K – $350K | **$247K** |
| **Executive Director (ED)** | $355K – $430K | **$399K** |
| **Managing Director (MD)** | $500K+ (sparse data) | ~$600K+ |

- US median all mgr levels: **$272K**
- Base/bonus/stock mix: ~70/15/15 typical
- Stock liquid (JPM)

### Comp Reality Check vs Affirm

| Comparison | Affirm | JPMC |
|---|---|---|
| Entry mgr median | $450K (M1) | $247K (VP) |
| Senior mgr median | $625K (M2) | $399K (ED) |
| Top tier | $880K | ~$600K (MD) |

**JPMC pays 30–40% less than Affirm at equivalent scope.** Trade-off: stability vs upside.

## Business + Tech Footprint

- **Lines:** Consumer/Community Banking (Chase), Corporate & Investment Bank, Commercial Banking, Asset & Wealth Mgmt.
- **Tech investment:** Self-claimed largest tech spend in finance.
- **AI focus:** Doubled generative AI use cases YoY. Heavy push on customer service + software engineering productivity.
- **Key US tech hubs:** NYC (383 Madison), Jersey City, Plano TX, Columbus OH, Wilmington DE, Houston.
- **Intl hubs:** Bengaluru, London, Mumbai.

## JPMC Ladder (EM Roles)

- **Associate** → **VP** (first mgr, 5–10 reports)
- **VP** → **ED** (mgr of mgrs, 15–30 ICs across)
- **ED** → **MD** (senior leadership)

⚠️ **Title inflation:** JPMC VP ≠ startup VP. JPMC VP ≈ industry "Senior Manager" / "Manager II". External recruiters discount the title.

## Ratings + Culture

| Source | Rating |
|---|---|
| Glassdoor (J.P. Morgan, overall) | ~3.9 / 5 |
| Indeed | ~3.9 / 5 (19K+ reviews) |
| Culture/values (eng) | mixed by team |
| RTO sentiment | **negative** |

### Themes from Eng Reviews
- **Heavy compliance overhead:** Model risk reviews, security gates, documentation. Slower velocity than Affirm/Stripe.
- **Team quality varies enormously** by division. IB tech ≠ Consumer Banking tech ≠ Asset Mgmt tech.
- "Cares more about RTO than productive work" — recurring complaint.
- VP→ED promo path: 2–4 years typical, requires cross-team influence + owning a system through full lifecycle.
- Stability strong, comp predictable, bonuses tied to firm-wide perf + individual rating.

## Risks

- **RTO pressure:** 3 days minimum, trending to 5. Dimon publicly anti-remote. **Killer if WFH-only.**
- **AI displacement narrative:** Dimon explicit — "displaced people from AI, offer them other jobs." "Redeployment plans" = roles eliminated, re-skill or exit. Eng less at risk than ops but not immune.
- **Targeted RIFs 2025–2026:** Tech, ops, corporate banking teams hit. Quiet trim ongoing.
- **Title inflation drag:** Moving from JPMC ED → senior IC elsewhere can read as step-back.
- **Process-heavy culture:** If you optimize for velocity + autonomy (Affirm-style), JPMC will frustrate.
- **Comp ceiling:** Even MD typically caps below Big Tech principal levels. Cash-heavy, less stock upside.

## Fit for Drew (Mid-to-Senior EM, 21+ yrs)

### Fits
- 21+ yrs experience + EM track = JPMC ED bands ($355K–$430K) achievable.
- Massive volume of EM roles (~25 US active, refreshes weekly).
- Multiple US metros (NYC, Plano, Columbus, Wilmington, Jersey City, Houston).
- Tech budget guarantees hiring through downturns.
- AI-focused EM roles emerging — interesting modernization work.

### Doesn't Fit
- Comp 30–40% below Affirm at equivalent scope.
- 3-day RTO minimum, no remote option.
- Slower process, more compliance overhead, less product latitude.
- Promo VP→ED slow; lateral ED hires possible but title-sensitive.

## Recommendation

Use JPMC as **breadth/floor**, not target. Tracker filter should prefer:
- `Executive Director` titles (skip plain VP — likely below comp floor)
- US metros within commute of intended residence
- Areas: AI/ML, payments tech, modernization, platform engineering

Skip generic "Manager of Software Engineering" reqs (VP-level, below comp floor).

### Suggested Tracker Tweak

Add company-specific keyword preference favoring `"Executive Director"` or `"Sr Manager"` over plain `"Manager of Software Engineering"`. Or add comp-floor filter on LLM tailor step.

## Tracker Integration

```python
# src/config.py
oracle_companies = {
    "jpmc": {
        "display_name": "JPMorganChase",
        "tenant": "jpmc",
        "site_number": "CX_1001",
    },
}
```

New scraper file `src/scrapers/oracle.py`. Reusable for Citi, BofA, Disney, IBM, Wells Fargo (all Oracle HCM). Added in commit `fe9311a` (2026-05-19).

## Sources

- [Levels.fyi — JPMC SEM](https://www.levels.fyi/companies/jpmorgan-chase/salaries/software-engineering-manager)
- [Levels.fyi — VP SEM](https://www.levels.fyi/companies/jpmorgan-chase/salaries/software-engineering-manager/levels/vice-president)
- [Levels.fyi — ED SEM](https://www.levels.fyi/companies/jpmorgan-chase/salaries/software-engineering-manager/levels/executive-director)
- [Glassdoor — J.P. Morgan Software Engineer](https://www.glassdoor.com/Reviews/J-P-Morgan-Software-Engineer-Reviews-EI_IE145.0,10_KO11,28.htm)
- [TheStreet — JPMC workforce/layoffs 2026](https://www.thestreet.com/investing/stocks/jpmorgan-chase-employees)
- [Fortune — Dimon on AI displacement](https://fortune.com/2026/02/25/jamie-dimon-society-prepare-ai-job-displacement/)
- [HRExecutive — Dimon AI displacement quote](https://hrexecutive.com/jpmorgan-ceo-we-have-displaced-people-from-ai-and-we-offer-them-other-jobs/)
- [JPMC Oracle careers portal](https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs)
