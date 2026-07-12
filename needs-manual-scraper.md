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
| 2026-07-12 | Citi (Citigroup) | Eightfold AI (+ Radancy) | https://jobs.citi.com/ | Public careers is Eightfold "Match Me" + Radancy. A bare citi.wd5 Workday host reference 404s on every site path — no live public Workday board. |
| 2026-07-12 | ParshipMeet Group | Personio | https://www.parshipmeet.com/en/careers/jobs/ | Apply flow uses Personio (teamlove.jobs.personio.de). Also EU-only — the live "Lead Engineering" role is Hamburg/Dresden/Berlin, not US. Skip regardless of ATS. |

## Scraper-enhancement opportunities

- **Oracle (the company)** — runs Oracle Recruiting Cloud at
  `eeho.fa.us2.oraclecloud.com` (site `CX_1`, ~915 manager-keyword reqs). The
  current `OracleScraper` hardcodes `https://{tenant}.fa.oraclecloud.com` with **no
  datacenter/region segment**, so it can't reach the `.us2.` host. Teaching the
  scraper to accept a full host/region (tenant=`eeho`, region=`us2`, site=`CX_1`)
  would unblock Oracle. Worth doing — Oracle posts many EM/Director roles.
