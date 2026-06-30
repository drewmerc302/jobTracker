# Companies needing a manual scraper

Companies surfaced by `jobtracker-update-from-linkedin` that run an ATS jobTracker
doesn't support (or otherwise can't be auto-added). Each would need a hand-built
scraper or a scraper enhancement. Reviewed manually before any work.

| Date | Company | ATS | Board URL | Note |
|------|---------|-----|-----------|------|
| 2026-06-30 | American Express | Eightfold AI (+ legacy Taleo) | https://aexp.eightfold.ai/careers | No Workday/GH/Lever/Oracle tenant. Eightfold scraper would be new. |
| 2026-06-30 | Paramount | SAP SuccessFactors | https://careers.paramount.com/ | SuccessFactors + Beamery. No supported board. |
| 2026-06-30 | OneStream Software | UltiPro / UKG Pro | https://recruiting.ultipro.com/ONE1018ONSO/JobBoard/ | Stale `onestreamsoftware` Greenhouse slug returns empty. |
| 2026-06-30 | BUILD, Inc. | Ashby | https://jobs.ashbyhq.com/build | Live Ashby board (10 jobs). jobTracker has no Ashby scraper. |
| 2026-06-30 | PrintMail Solutions | custom / none | https://www.printmailsolutions.com/careers/ | Careers page redirects to LinkedIn; no API board. ~175-person co, Newtown PA. |
| 2026-06-30 | AllTrails | Lever (empty) | https://jobs.lever.co/alltrails | Correct ATS is Lever `alltrails`, but 0 live postings right now. Re-check later — addable as `lever_companies["alltrails"]` when they repost. |

## Scraper-enhancement opportunities

- **Oracle (the company)** — runs Oracle Recruiting Cloud at
  `eeho.fa.us2.oraclecloud.com` (site `CX_1`, ~915 manager-keyword reqs). The
  current `OracleScraper` hardcodes `https://{tenant}.fa.oraclecloud.com` with **no
  datacenter/region segment**, so it can't reach the `.us2.` host. Teaching the
  scraper to accept a full host/region (tenant=`eeho`, region=`us2`, site=`CX_1`)
  would unblock Oracle. Worth doing — Oracle posts many EM/Director roles.
