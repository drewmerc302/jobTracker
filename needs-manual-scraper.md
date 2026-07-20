# Companies needing a manual scraper

Companies surfaced by `jobtracker-update-from-linkedin` that run an ATS jobTracker
doesn't support (or otherwise can't be auto-added). Each would need a hand-built
scraper or a scraper enhancement. Reviewed manually before any work.

| Date | Company | ATS | Board URL | Note |
|------|---------|-----|-----------|------|
| ~~2026-06-30~~ | ~~American Express~~ | ~~Eightfold AI (+ legacy Taleo)~~ | ~~https://aexp.eightfold.ai/careers~~ | RESOLVED 2026-07-12: Eightfold is only a front-end; the real backend is Oracle Recruiting Cloud (`egug.fa.us2.oraclecloud.com`, CX_1, 290 reqs, verified live). Added as `oracle_companies["amex"]`. |
| 2026-06-30 | Paramount | SAP SuccessFactors | https://careers.paramount.com/ | SuccessFactors + Beamery. No supported board. |
| 2026-06-30 | OneStream Software | UltiPro / UKG Pro | https://recruiting.ultipro.com/ONE1018ONSO/JobBoard/ | Stale `onestreamsoftware` Greenhouse slug returns empty. |
| 2026-06-30 | BUILD, Inc. | Ashby | https://jobs.ashbyhq.com/build | Live Ashby board (10 jobs). jobTracker has no Ashby scraper. |
| 2026-06-30 | PrintMail Solutions | custom / none | https://www.printmailsolutions.com/careers/ | Careers page redirects to LinkedIn; no API board. ~175-person co, Newtown PA. |
| 2026-06-30 | AllTrails | Lever (empty) | https://jobs.lever.co/alltrails | Correct ATS is Lever `alltrails`, but 0 live postings right now. Re-check later — addable as `lever_companies["alltrails"]` when they repost. |
| 2026-07-06 | AllTrails | Ashby | https://jobs.ashbyhq.com/alltrails | Moved off Lever (slug now 0 postings) to a live Ashby board. Supersedes the 2026-06-30 Lever entry — no longer worth re-checking Lever. |
| 2026-07-06 | Avalara | iCIMS | https://careersind-avalara.icims.com/ | careers.avalara.com is a CareerPuck front-end over iCIMS. |
| 2026-07-06 | Genoa Ventures | Getro/Consider aggregator | https://careers.genoavc.com/jobs | VC portfolio-company job board; the "AI Engineering Lead" alert is an unnamed portfolio company, not the fund. |
| 2026-07-06 | Optum (UnitedHealth Group) | Oracle Taleo | https://careers.unitedhealthgroup.com/search-jobs | TalentBrew recruitment-marketing front-end; apply flow submits to uhg.taleo.net. |
| 2026-07-06 | Tyndale Company, Inc. | iCIMS | https://careers-tyndaleusa.icims.com/ | FR-clothing supplier, Pipersville PA (not Tyndale House publishers). |
| ~~2026-07-06~~ | ~~Yum! Brands~~ | ~~custom (Laravel/React)~~ | ~~https://jobs.yum.com/~~ | RESOLVED 2026-07-12: jobs.yum.com is only a front-end; the real backend is Oracle Recruiting Cloud (`eczd.fa.us2.oraclecloud.com`, CX_1, 170 reqs, verified live). Added as `oracle_companies["yum"]`. |
| ~~2026-07-12~~ | ~~Citi (Citigroup)~~ | ~~Eightfold AI (+ Radancy)~~ | ~~https://jobs.citi.com/~~ | RESOLVED 2026-07-20: the earlier "no live public Workday board" call was wrong. Site ID is the literal string `2` — `citi.wd5.myworkdayjobs.com/wday/cxs/citi/2/jobs` returns live postings (verified). Added as `workday_companies["citi"]`. |
| 2026-07-12 | ParshipMeet Group | Personio | https://www.parshipmeet.com/en/careers/jobs/ | Apply flow uses Personio (teamlove.jobs.personio.de). Also EU-only — the live "Lead Engineering" role is Hamburg/Dresden/Berlin, not US. Skip regardless of ATS. |
| 2026-07-20 | Charles Schwab | iCIMS (`career-schwab.icims.com`) | https://www.schwabjobs.com/ | schwabjobs.com is a Radancy/Phenom front-end. Probed `schwab.wd5`: every site ID returns HTTP 401, no public Workday board. EM roles are Austin/Denver — outside the location filter anyway. |
| 2026-07-20 | FinThrive | Ceridian Dayforce HCM | https://us231.dayforcehcm.com/CandidatePortal/en-US/finthrive | 16 jobs, JS-rendered. **Director of Software Engineering (Hands-On), Virtual US, posted 2026-07-20 — strong fit, apply manually.** Tracker structurally cannot see it. |
| 2026-07-20 | Blackboard (fka Anthology) | Jobvite | https://careers.blackboard.com/ | Rebrand went the opposite direction from assumption — anthology.com now 301s to blackboard.com. 9 open roles total, zero engineering leadership. Low value even with a scraper. |
| 2026-07-20 | Snapdocs | Ashby | https://jobs.ashbyhq.com/snapdocs | 6 jobs, all GTM/implementation. No engineering roles at all. |
| 2026-07-20 | BUILD, Inc. | Ashby | https://jobs.ashbyhq.com/build | Re-confirms the 2026-06-30 entry. Seed-stage agentic AI for institutional real estate (Index Ventures). The Head of Engineering role from the alert was a Jack & Jill anonymized listing, now closed. Live adjacent: Tech Lead Core Infrastructure, VP Digital Infrastructure NA. |
| 2026-07-20 | Ladders | aggregator — PERMANENT SKIP | https://www.linkedin.com/company/ladders | Anonymized "for our client" postings. LinkedIn's own company entity *is* Ladders; no employer name is ever published. Do not retry resolution on these. |

## Scraper-enhancement opportunities

- **Oracle (the company)** — runs Oracle Recruiting Cloud at
  `eeho.fa.us2.oraclecloud.com` (site `CX_1`, ~915 manager-keyword reqs). The
  current `OracleScraper` hardcodes `https://{tenant}.fa.oraclecloud.com` with **no
  datacenter/region segment**, so it can't reach the `.us2.` host. Teaching the
  scraper to accept a full host/region (tenant=`eeho`, region=`us2`, site=`CX_1`)
  would unblock Oracle. Worth doing — Oracle posts many EM/Director roles.

- **Ashby is now the biggest coverage gap** (2026-07-20: 2 of 5 companies in a single
  batch, plus AllTrails, Snapdocs, and BUILD from earlier runs). Clean public endpoint:
  `POST https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams` with body
  `{"organizationHostedJobsPageName": "<slug>"}` returns titles, locations, and comp
  tiers in one call. ~100 LOC on the existing `BaseScraper` pattern. Highest-leverage
  next scraper — unlocks the seed/Series-A startup market the tracker can't see today.

- **`probe_board.py` has two confirmed false-negative modes** (found 2026-07-20):
  1. It stops at the first ATS that answers, even when that board is stale. It marked
     ServiceTitan `smartrecruiters`/8 postings when the live board is Workday/94.
  2. It only tries the bare company name as a slug. It missed Bevi, whose Greenhouse
     slug is `bevicareers`. Add a `{name}careers` fallback variant.
  Any company a past run labeled `smartrecruiters` or `ashby` deserves a re-check.
