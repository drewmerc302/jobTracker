---
tags: [job-search, company-analysis, engineering-manager, consulting, big-4, not-in-tracker]
company: Deloitte
ats: Avature
board_url: https://apply.deloitte.com/en_US/careers/SearchJobs
remote: hybrid + client-site driven
captured: 2026-05-19
comp_floor: 130000
comp_median: 209000
comp_ceiling: 388000
tracker_status: deferred — Avature scraper not built
---

# Deloitte — Company Analysis

> Captured 2026-05-19 during scraper expansion research. **Not currently in tracker.** Avature scraper deferred — see "Scraper Decision" below.

## At a Glance

| Field | Value |
|---|---|
| ATS | **Avature** (white-labeled on apply.deloitte.com) |
| Board URL | https://apply.deloitte.com/en_US/careers/SearchJobs |
| URL pattern | `/en_US/careers/JobDetail/{slug}/{id}` |
| API | **No public REST.** HTML scrape only. |
| Pagination | Server-rendered, `jobOffset` query param |
| Tracker status | **Deferred** (not added) |
| Org type | Big 4 professional services / privately held partnership |
| Revenue (FY24 global) | ~$67.2B |
| US workforce | ~170,000+ |

## Salary — Engineering Manager / Senior Manager (levels.fyi + Glassdoor, 2026)

| Level | Total Comp Range | Median |
|---|---|---|
| **Manager** (5–7 yrs) | $130K – $245K | **$190K** |
| **Senior Manager** (8–12 yrs) | $170K – $285K | **$239K** |
| **Senior Manager** (Glassdoor) | $188K – $323K | **$244K** |
| Top reported (levels.fyi) | — | **$288K** |
| Glassdoor ceiling | — | **$388K** |
| Managing Director / Partner | sparse | $400K+ base + equity-like |

### Comp Reality Check

| Comparison | Affirm | JPMC | Deloitte |
|---|---|---|---|
| Entry mgr median | $450K (M1) | $247K (VP) | **$190K (Mgr)** |
| Senior mgr median | $625K (M2) | $399K (ED) | **$239K (SM)** |
| Top tier | $880K | ~$600K (MD) | **~$388K** |

**Deloitte pays ~58% of JPMC and ~38% of Affirm at equivalent scope.** Cash-based, no public stock. MD/Partner track adds equity-like distributions.

## Business + Structure

**Service lines (where EMs live):**
- **Consulting** — strategy, ops, **Deloitte Digital** (tech/UX), Engineering & Cloud
- **Deloitte Engineering** (formerly Engineering, AI & Data) — tech delivery arm
- Audit & Assurance, Tax, Risk & Financial Advisory (non-EM)

**EM roles concentrate in:** Deloitte Consulting → Engineering & Cloud / Deloitte Digital. **NOT pure tech** — consulting hours, client-driven schedule, project-based.

## Career Ladder

- Consultant → Senior Consultant → **Manager** (5–7 yrs) → **Senior Manager** (8–12 yrs) → **Managing Director / Partner** (12+, equity track)
- Deloitte "Manager" ≈ industry "Senior IC + small team lead"
- Deloitte "Senior Manager" ≈ industry "Engineering Manager / Director"
- **Up-or-out at SM**: promo to MD/Partner in ~3 yrs or exit pressure

## Ratings + Culture

| Source | Rating |
|---|---|
| Glassdoor overall | ~4.0 / 5 (113K+ reviews) |
| Indeed | ~3.9 / 5 (5K+ reviews) |
| Blind WLB | **3.0** (lowest) |
| Blind Career Growth | 3.7 (highest) |
| Glassdoor WLB | 3.2 |
| Glassdoor Culture/Values | 3.7 |
| Career opportunities | 4.0 |

### Themes
- **Career growth strong** — Big 4 brand opens doors.
- **WLB poor** — client-driven, immovable deadlines. Audit/Tax busy seasons brutal; Consulting milestones bring weekend work.
- **Travel** — historically heavy Mon-Thu client site, reduced post-COVID but real. Varies by practice.
- **Hybrid flexibility** offered but undermined by client demands.
- **Recent benefit cuts:** Parental leave 16 → 8 weeks. PTO cut 5–10 days by tenure. Margin pressure signal.
- **Recent layoffs:** US Consulting hit in 2024 + 2025, targeted by practice.
- **Up-or-out pressure** at SM/MD level — sustainability concern for mid/late career.

## Risks

- **Consulting != product engineering.** "Engineering Manager" often = delivery lead managing consultants on client project. Different skill: timeline/scope/billing, not tech architecture.
- **Comp ceiling low:** SM tops ~$300K cash. No equity. Big gap vs Affirm/Big Tech.
- **WLB volatile by team/client.** Some Consulting roles fine, others 60+ hr peaks.
- **Benefit cuts trending wrong way** — signal of margin pressure.
- **Promotion path:** Up-or-out at SM means decline can force exit even with strong perf.
- **Travel risk:** Some practices still expect heavy client-site travel.

## Fit for Drew (21+ yrs EM)

### Fits
- Title pattern (Manager / Senior Manager) maps to tracker keywords.
- Brand on resume.
- Volume of openings high.
- Deloitte Engineering AI/Cloud roles meaningful tech transformation.

### Doesn't Fit
- **Comp ~60% below JPMC, 40% below Affirm.** Below floor for 21+ yrs experience.
- **Client-services model** — billable hours, timesheets, utilization targets.
- **Up-or-out at SM** — exit pressure mid-50s/60s.
- **Travel** — Mon-Thu client site possible.
- **Benefit erosion** — parental leave / PTO cuts signal margin tightening.

## Scraper Decision (Deferred 2026-05-19)

### Why Deferred
- **Avature has no public REST** — HTML scraping only. Brittle (server-rendered, layout-dependent).
- **Build cost:** ~45 min for new `src/scrapers/avature.py` (BeautifulSoup/selectolax HTML parser). Maintenance risk higher than Greenhouse/Oracle.
- **Single-company ROI low.** Comp ceiling (~$388K SM) lower than Affirm M1 floor ($315K). High-effort scraper for likely-non-fit company.

### When to Revisit
Build Avature scraper if/when:
- Drew targets another Avature shop with better fit: **HSBC, Siemens, Continental, Heineken, L'Oréal** (all Avature)
- Deloitte posts specific senior tech roles ($300K+ band) worth automated tracking
- Pivot to consulting-style EM tolerable (likely never, given current preferences)

### Manual Workaround
For specific interesting Deloitte roles: paste URL into tracker manually. Single-job tracking via `--track` flag works without scraper.

### Build Approach (if revisited)
- HTML parse listing page at `apply.deloitte.com/en_US/careers/SearchJobs?listFilterMode=1&jobOffset=N`
- Extract job links: `/en_US/careers/JobDetail/{slug}/{id}`
- Fetch detail pages, extract description from server-rendered HTML
- Filter: title regex + US location (no country JSON field — must parse text)
- Pagination: increment `jobOffset` until empty result
- Watch for: rate limiting, session cookie requirements, redesigns
- Test fixture: save 1–2 real list + detail HTMLs to `tests/fixtures/avature_*.html`

## Tracker Integration

**Not added.** No config change. Manual URL tracking only via `uv run jobtracker --track <url>` for specific interesting roles.

## Sources

- [Levels.fyi — Deloitte SEM](https://www.levels.fyi/companies/deloitte/salaries/software-engineering-manager)
- [Levels.fyi — Deloitte SM](https://www.levels.fyi/companies/deloitte/salaries/software-engineering-manager/levels/senior-manager)
- [Glassdoor — Deloitte Senior Manager](https://www.glassdoor.com/Salary/Deloitte-Senior-Manager-Salaries-E2763_D_KO9,23.htm)
- [Glassdoor — Deloitte reviews](https://www.glassdoor.com/Reviews/Deloitte-Reviews-E2763.htm)
- [Glassdoor — culture reviews](https://www.glassdoor.com/Reviews/Deloitte-culture-Reviews-EI_IE2763.0,8_KH9,16.htm)
- [Blind — Deloitte reviews](https://www.teamblind.com/company/Deloitte/reviews)
- [HRDigest — Deloitte benefit cuts](https://www.thehrdigest.com/backtracking-on-benefits-deloitte-cuts-key-support-for-some-employees/)
- [BuiltIn — Deloitte WLB](https://builtin.com/company/deloitte/faq/work-life-balance-wellbeing)
- [Deloitte careers](https://apply.deloitte.com/en_US/careers/SearchJobs)
