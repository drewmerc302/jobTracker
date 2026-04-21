# Performance Review Reference: Andrew Mercurio (Drew)
*Compiled from Audible performance reviews 2016–2024. Use this document for resume tailoring, interview prep, cover letters, and accomplishment framing.*

---

## Career Timeline at Audible (Amazon)

| Period | Title | Org / Manager |
|--------|-------|---------------|
| 2016 | Sr. Software Dev Engineer II | Tech_Dev-Bidisha_Das / Chiranjiv Jouhal |
| 2018 | Sr. Mgr, Software Development (Team Leader) | Tech_Dev-Bidisha_Das / Bidisha Das |
| 2019 | Sr Manager, Software Dev | Tech_Dev-Bidisha_Das / Bidisha Das |
| 2020 | Director, Software Dev | Tech_Dev-Bidisha_Das / Bidisha Das |
| 2021–2024 | Director, Software Dev | Tech_Dev-Leonid_Geller / Leonid Geller |

**Location:** EWR1 / EWR11 — Newark, NJ (Audible HQ)

### Teams Led Over Time

| Year | Teams | Direct Reports |
|------|-------|----------------|
| 2018 | ATMOS / PRIMO | ~5–8 SDEs |
| 2019 | PRIMO | ~10 SDEs |
| 2020 | PRIMO → APEX (transition) | ~14 SDEs |
| 2021 | APEX + COFFEE (simultaneously) | 15–17 engineers |
| 2022 | APEX + ACORN (simultaneously) + coverage for COFFEE | ~15 engineers |
| 2023 | PERU org (ALPACA + COFFEE) — *Leader of Leaders* | 4 L6 reports (2 SDMs, 2 SDE3s) |
| 2024 | PERU org (ALPACA + PACMAN) — *Leader of Leaders* | 2 SDMs + SDE3s |

---

## Overall Performance Ratings

| Year | Manager Rating | Employee Self-Rating |
|------|---------------|---------------------|
| 2016 | Solid Performer | — |
| 2018 | Solid Performer | High Performer |
| 2019 | Valued Contribution | Valued Contribution |
| 2020 | Valued Contribution | Valued Contribution |
| 2021 | **Outstanding Contribution** | **Outstanding Contribution** |
| 2022 | Valued Contribution | Valued Contribution |
| 2023 | Valued Contribution | **Outstanding Contribution** |
| 2024 | Valued Contribution | Valued Contribution |

---

## Major Projects & Accomplishments by Year

### 2016
- **Rating:** Solid Performer
- Details limited in surviving documentation.

---

### 2018 — Transition from SDE to SDM; delivered the biggest project in Audible's history
**Rating:** Manager: Solid Performer | Employee: High Performer

#### Rolling Stone: Oracle → PostgreSQL Database Migration
The marquee achievement of Drew's tenure as technical lead / new SDM. Led full migration of 9 Audible services from Oracle to PostgreSQL with zero customer-facing downtime.

- **Scale:** ~20 contractors, SDEs, TPMs, scrum masters, QA engineers, DBAs across 9 services
- **Services migrated:** AudibleCancelOfferService, AudibleMembershipCatalogService, AudibleRedemptionService, AudibleCartService, AudiblePriceAggregatorService, AudibleCustomerSegmentationService, AudibleCustomerInformationService, AudibleMembershipManagementService, AudibleMembershipInformationService
- **Key technical achievement:** Designed and implemented zero-downtime dual-read/write solution for cart and membership flows — initially deemed unachievable; Drew drove the team to find the path
- **Business impact:** Saved Audible ~$300,000 in prevented lost sales and customer confidence from a zero-impact transition
- **Delivery:** On schedule across nearly 100 milestones; minimal customer impact
- **Personal role:** Technical lead, project planning coordination, TPM liaison, go/no-go decision authority, architecture review board interface, DBA coordination, senior management communications, blocker resolution

#### PRIMO Team SDM Transition
Formally transitioned from SDE to SDM mid-year while simultaneously leading Rolling Stone.
- Delivered: Extra Credits improvements, BOGO enhancements, numerous Promotion optimizations and fixes, ANVIL risk closures, gift-a-title support, membership promotion launches in all global marketplaces, daily deal enhancements
- Dramatic reduction in OE (one of the most significant across Consumer Domains)

#### Subs-DOX Migration
- Pivotal work on multi-month membership promotions that enabled successful market launches for this initiative

---

### 2019 Mid-Year — Growing SDM; owning full product and project responsibility
**Rating:** N/A (mid-year check-in)

- **Vendisto Migration:** Both Membership and Coupon use cases delivered on time by PI-9
- **Centralized Pricing:** AudibleCatalogPublishingService changes + new Datapath for static and dynamic prices; coordinated with CBO/ABOS teams
- **CloudAuth:** All migrations completed ahead of schedule by PI-9 end; only one non-essential service remaining
- **Operational Excellence:** Consistently low TT and policy engine violation count; sev-2s down; on-call quality of life improved
- **PrimeDay:** Zero incidents on all PRIMO-owned services
- **CSC Replacement:** Facilitated PingHub and new CSC-lite platform implementation
- **People:** Career guidance across both inexperienced new hires and seasoned veterans

*Peer quotes:* "He is the first or second person to chime in on a Primo Sev2." / "Drew does a great job of moving projects forward even when it means filling in gaps left in other roles." / "He is an advocate for his team, ensuring they get interesting work and recognizing when he needs to get them assigned to certain projects for their career development."

---

### 2019 Year-End — First full year as SDM
**Rating:** Manager: Valued Contribution | Employee: Valued Contribution

- **Flexible Promotions:** Mission-critical marketing initiative delivered on time; complex away-team dependencies navigated
- **PAS Deprecation:** Delivered ahead of planned schedule with **zero defects** caught by QA on first round of testing
- **MFA BOGO:** Delivered on time despite wildly changing requirements and away-team dependencies across Consumer Domains and Player/Library
- **PI Commitments:** All delivered on time; no Red epics carrying over unexpectedly
- **People:** Akanksha promoted from L8 → L9; began coaching her on SDM transition path
- **OE leadership:** PRIMO recognized as a leader across the domain; championed team ideas to lower ticket counts and raise quality

---

### 2020 Mid-Year — Assumed APEX leadership; managing 14+ engineers
**Rating:** N/A (mid-year check-in)

- Took over APEX team from departing SDM (Vishal); assimilated quickly, respected immediately by the engineering team
- **APEX scope:** Cart, AMPAS, ABOS, and related critical purchase services
- **Minerva:** Led team through delivery of major Audible product initiative — rescoped, found paths to green, mitigated risks on tight timelines; demonstrated customer obsession in thinking through scenarios
- **Groomed Akanksha** (PRIMO) to be an independent SDM so Drew could fully commit to APEX
- **OE progress:** TT count reached low 20s at best point; sustained focus despite Minerva workload
- **People development:** Alex Fu became SME on BuyBox; Nayana became SME in Promotions
- **Proposed Shopping Reorg:** Advocated for breaking the oversized APEX team into 2-pizza-sized teams

---

### 2020 Year-End — Major delivery year; led Shopping Domain reorg
**Rating:** Manager: Valued Contribution | Employee: Valued Contribution

- **ABOS launch:** Production readiness, client onboarding, and GameDay scaling
- **Podcasts at Scale:** Delivered
- **Wakanda:** CEO-driven initiatives with extremely tight timelines; managed complex, poorly-understood emergent asks while meeting all deliverables
- **Shopping Domain Reorg:** Co-designed the restructuring that split the domain into **APEX, COFFEE, and PRIMO** — three focused, appropriately-sized teams; oversaw CTI/oncall transitions
- **SDM Standup:** Proposed and initiated the Shopping SDMs sync meeting — adopted by Bidisha for ongoing use
- **OE:** APEX became the **leader in OE metrics for the Shopping Domain** after historically being the noisiest team
- **Groomed Puneet** (Coffee team lead) toward SDM transition
- **People:** Provided constructive feedback, opportunity, and career advocacy for all direct reports

*Peer quotes:* "Drew took over a large team when Vishal left — I was very impressed with how easily he was able to get into the weeds and how effective he was. It's clear they respect him as a top notch engineering leader." / "The amount of time he spends in triaging our massive TT queue to help make the lives of SDEs easier. CRAZY!"

---

### 2021 Mid-Year — Managing 15+ engineers across two teams; exceptional breadth
**Rating:** N/A (mid-year check-in)

Led APEX and COFFEE simultaneously (15+ engineers) during Bidisha's departure, integration into MPX domain, and transition to new manager Leonid Geller. Manager quote: "The list of most important contributions is too long to count."

**Key Accomplishments:**
- **Fleet Optimizer POC:** 70% reduction in cart hosts via CloudTune enablement
- **iOS Free Trial:** Implementation and launch support
- **Easy Exchanges:** Launch support and fast follows
- **ExternallyManagedPayments (EMP):** Research, POC, and implementation
- **Fraud Support for iOS:** Investigated and resolved external purchase/credit fraud
- **GDPR (Sandfire):** GDPR data deletion compliance in cart
- **A11Y:** All accessibility issues closed
- **Puma → PayStation migration:** For Audible touchpoints
- **AL2 Migration:** All hosts across both teams migrated from AL2012 → AL2
- **SAS risks:** Reduced from thousands → consistently zero in "recommended fixes" category
- **TT reduction:** Queue from 70 → consistently ~20
- **COEs:** Perfect COE score; all action items resolved within stipulated timeframes
- **PAPG Compliance:** India market implementation
- **CBCC card issue:** Successfully resolved ongoing issue blocking Puma→PayStation migration in US
- **Associates Integration:** D+D support
- **IMR improvements:** Multiple wins via FleetOptimizer, CloudTune
- **VISA fine follow-up:** Ongoing compliance focus
- **Yates promoted to SDE-III** (rare achievement at L6 SDM level)
- 4 Applaudible recognitions in H1 2021

---

### 2021 Year-End — **Outstanding Contribution** (highest rating)
**Rating:** Manager: Outstanding Contribution | Employee: Outstanding Contribution

This was the highest-rated review year. Despite exceptional adversity (4 headcount departures, new manager, domain reorg, competing priorities), delivered across all dimensions.

**Headline accomplishments:**
- Led teams to 2 L6 promotions: Yates (SDE-III) and Puneet (SDE → SDM)
- Onboarded 3 new SDEs; participated in 11 interview events
- Led two teams (APEX + COFFEE) with 17 people
- Stepped in as organizational leader during Bidisha's departure in March
- Integrated 2 former Shopping teams with Accounts and Membership organization

**Project deliverables across PI-16 through PI-19:**
- Google EMP (Subscription & Single Item Purchase) — in flight heading into Q1 2022
- iOS Extra Credits migration to ExternallyManagedPayments
- Cart Boomerang (away from ACDDS)
- GDPR Cart to AudibleCustomerDataDeletionService
- India PAPG changes in Cart/AMPAS
- GMA UK/IN, GMB IT launches
- Conditional Fulfillment launch support
- EMP ALC/ALOP support
- Checkout Rearchitecture
- Prime Day gamedays
- Host Migration in DUB datacenter (Project SandSwitch)
- IMR wins via FleetOptimizer for AudibleCartService
- Easy Exchanges launch
- AmazonAssociates support for 3-month Plus ASIN
- TOA 1.0 + 2.0 expansion support

*Manager quote:* "I have truly enjoyed Drew's partnership since we began working closely in 2021 and appreciate his insights, depth of domain knowledge, and desire to grow professionally."

*Peer quotes:* "Drew is the Shield of APEX. He's the Iron Dome." / "Drew is team dad. He is incredibly proactive at shielding and blocking his SDEs from difficult situations." / "The biggest impediment to Drew's continued success is managing two teams. If Drew performs this well while doing double-duty SDMing, I can only imagine how well he would function when able to focus on a single team." / "Drew has succeeded in managing one of the most chaotic teams in all of Audible."

---

### 2022 Mid-Year — Google Play Payments global launch; managing 15 reports
**Rating:** N/A (mid-year check-in)

- **Google Play Payments (GPP) — Subscriptions & Extra Credits:** Global Android launch with hard delivery date (March 31), multiple Amazon downstream complexities. Ran daily scrum meetings, drove to successful launch.
- **Google Two-Phase Commit:** Designed and implemented two-phase commit process to fix customer billing edge cases
- **Project 7:** Complex multi-team mandate delivered on time; great growth opportunity for Angu and Yukang
- **Conditional Fulfillment Global:** Henry led; launched globally in CA and AU — major anti-fraud win preventing credit redemption before payment confirmation
- **Impact Winter Spikes / Free Tier:** Tight emergent deadline; enabled content redemption without credit card on file
- **Cerebro Revenue Split:** Delivered on time; complex exception handling resolved
- **DCQS migration:** Completed ahead of schedule
- **GMA DE (Germany) launch:** Supported
- **Apple purchase failure persistence layer:** New visibility into Apple billing workflow failures
- **ACORN:** Created new team from APEX; onboarded Sanjeev as new SDM
- **Rabi on path to SDE-III promotion**
- Applaudible metrics: 73 recognitions (109% increase); 15 direct; 57 boosts (128% increase)
- Managed intern (Mayank) alongside all other responsibilities

*Peer quotes:* "Drew was responsible for the 3PX components for the launch of Google Play Payments on Android, a global launch that had a hard delivery date, multiple complexities on Amazon downstream systems, and high visibility in the organization." / "Drew's greatest quality as a manager is that he is able to increase productivity by unblocking and resolving issues while never being a blocker or an impediment himself."

---

### 2022 Year-End — Transition to Leader of Leaders
**Rating:** Manager: Valued Contribution | Employee: Valued Contribution

- **Google Subscriptions & Extra Credits (GPP):** Launched in April — maintained compliance with Google's new digital transaction fee enforcement deadline
- **Google ALC/ALOP:** Launched in October — complex multi-stakeholder project; re-launched after reporting identified drop in membership signups
- **3PX Organizational Restructuring:** Hired, onboarded, and integrated **4 new SDMs** + new TPM; co-led leadership offsite to design org structure; became primary onboarding buddy for new SDMs
- **Hired JB Reefer** as new Apex SDM; began transition → first formal "leader of leaders" structure
- Coffee team (Puneet) + Alpaca (JB) now reporting through Drew
- Covered for departing SDM Albert mid-year (covered 3PX leadership during Leonid's absence for calibration)
- Drove Apex TT queue to **sustained ~10 TTs** (down from high 30s–50s historically)
- Achieved full CI/CD for AOEPS
- Onboarded 4 new SDEs
- Participated in 14 interview activities
- Accepted underperforming SDE from another team; supported through successful coaching plan

*Manager quote:* "In 2023 Drew will continue to lead 2 SDE-3s and 2 SDMs responsible for Alpaca and Coffee teams. The combined scope of ownership of these teams, the opportunity to champion broader CD-wide initiatives, and the strengths in his technical talent will enable Drew to grow his impact at Audible in 2023."

---

### 2023 Mid-Year — Leading PERU org; iOS ALC/ALOP delivered
**Rating:** N/A (mid-year check-in)

Leading "PERU" organization (ALPACA + COFFEE) with 4 L6 direct reports (2 SDMs + 2 SDE3s).

**Key Accomplishments:**
- **91 completed epics** across ALPACA and COFFEE in H1
- **Puneet (SDM) → L6 promotion success**; **Danisha (SDE) → L6 promotion success** — navigated 2 simultaneous L6 promotions
- **iOS ALC/ALOP (Apple Partner Billing) — Code Complete:** Led coordination across Matcha, Alpaca, DiCE, Docs, DEP, DMart, and others; delivered on time to Apple mandated date
- **mShop tiger team:** Negotiated and staffed; ensured Joey (highest-context engineer) was assigned; Alpaca's contribution was not a factor in any mShop delays
- **DA Workshop (DOT framework):** Hosted workshop with Amazon DA; surfaced Audible-specific requirements (credits, M+C bundling) that DOT didn't yet support; DA left aligned to prioritize Audible items in OP1
- **ABOS scaling process redesign:** Shifted burden from Coffee SDM/SDEs to TPMs requesting features — reduced Coffee capacity churn
- Mentor to Kimmy Dai (SDM transition candidate)
- Volunteered as safety warden for EWR11 cathedral; Franciscan Charities volunteer work in Newark
- 65 Applaudibles sent across PERU leadership in H1

---

### 2023 Year-End — $26M+ revenue impact; 168 epics delivered
**Rating:** Manager: Valued Contribution | Employee: Outstanding Contribution

**Highest-impact year from a revenue perspective.**

#### Project ALChemy (iOS ALC/ALOP via Apple Partner Billing)
- **$26,088,843 in additional revenue** since launch as of Dec 15, 2023
- **Opened a new revenue stream exceeding $100MM on annual basis**
- Multi-team coordination: Matcha, Alpaca, DiCE, Docs, DEP, DMart, Amazon DA
- Drew's role: coordinate teams, set expectations, brainstorm around blockers, represent 3PX to product/TPM, help Product understand scope/date tradeoffs to hit Apple mandated date

#### Unified Checkout Experience (UCX)
- Partnered with SDE3 Yates Monteith; led launch
- Enabled several Audible on mShop GPB milestones in 2023
- Supported Remix/Access experiment delivery
- Aligned Matcha, ECB, and BOGO as UCX clients

#### Other 2023 Highlights
- **168 total epics delivered** across Alpaca, Coffee, and Pacman (including Q4 Pacman)
- **DOT Summit:** Hosted Amazon DA engineers; resulted in DA prioritizing Audible P0 requirements in OP2 plan
- **JB Coaching Plan:** Mid-year coaching plan for underperforming SDM; JB made noticeable improvements in communication and technical ownership
- **Joey management (via JB):** Brought engineer back from brink of NI rating; achieved Valued rating at year end
- **Puneet → Pacman transition:** Guided Puneet's smooth takeover of Pacman team; coached him on listening to team and building trust through the change
- **Srini L5 promotion** via JB: Stepped in personally when JB's writing wasn't sufficient to close the promotion
- **Rabi internal mobility** to mShop (Fabio's org): Right decision for career goals; maintained strong relationship
- **Talent review coverage:** Represented 3PX at L7-level mid-year talent review while Leonid was on vacation; praised for quality of analysis vs other domains
- **L6 promotions:** 2 (Puneet SDM, Danisha SDE)
- **L5 SDE promotion** (Srini Kandari) + 1 successful SDM coaching plan

*Peer quotes:* "He is one of the best managers I have ever had." / "Drew is warm and tailors his communication to his audience well. He is deeply technically knowledgeable, flexible with scheduling, punctual, inclusive, funny, and easy to work with. He celebrates our victories. He knows exactly what's going on, when it's due, and who's on it." / "Drew is one of the most technically strong managers which I really appreciate. He's still relatively close to the technicals, which I cannot say about all other managers."

---

### 2024 Mid-Year — IAP S-Team goals; performance management; product partnership
**Rating:** N/A (mid-year check-in)

Leading PACMAN (Payments) and ALPACA (Purchase experience) organizations.

**Key Accomplishments:**
- **IAP S-Team Goals:** Delivered on multiple key apps and payments deliverables — DxGy, IAP S-team goal projects, Amazon Gift Cards, Product Vouchers, Google Alternative Billing, User Choice Billing
- **Product roadmap partnership:** Regular 1:1s with Kitty (product); collaborated with Dana Morgan, Michael Lewis, Michael Rutledge on iOS Promos, In App BOGO, Gift Cards, Product Vouchers, UCB, EEA, Mshop, Plan Switching
- **Max Perel (performance management):** Discovered and managed out IC who was gaming code commit counts. Ran full HR process; created best practices document distributed to other SDMs on how to identify code commit fraud
- **JB Reefer (SDM performance management):** Worked through coaching, micromanagement, solicited 360 feedback; initiated PIP/Pivot process per HR guidance
- **AOPS migration:** MMS → GPE; identified AOPS as last client on KTLO MMS, migrated during Q2 gap week
- **AMPAS CI/CD:** Identified gap in CD MX testing; drove path to green in Gamma/Devo; enabled CI/CD
- **Montana (proactive risk doc):** Created early considerations document before formal project details were shared — demonstrated proactive domain expertise
- **Action Codes:** Contributed to OP1 proposal to migrate from Audible action codes to Amazon standard ref_markers
- **Rabi transfer to mShop:** Facilitated permanent transfer to Fabio's org; right career decision despite short-term pain

*Peer quotes:* "Drew knows everything about the problem domain and the history of the org." / "Drew's leadership is characterized by a commitment to transparency and open communication." / "Drew's inclusive approach has fostered a sense of belonging and value within the team."

---

### 2024 Year-End — Performance management year; S-Team delivery
**Rating:** Manager: Valued Contribution | Employee: Valued Contribution

- **IAP S-Team goal:** Successfully delivered all S-Team deliverables as defined by KingPin goal — improved customer experience for IAP and grew collaboration with DEP and DA counterparts
- **Montana borrow experience:** Enabled implementation through AMPAS flows
- **43% of organization achieved Outstanding performance ratings**
- **Max Perel and JB Reefer managed out:** Handled both performance management cases professionally; full HR partnership; transparent communication
- **Danisha's growth:** Tech lead on Standard features across Consumer Domains all year — delivered full roadmap plus all emergent requests
- **Puneet SDM growth:** Coaching on ownership boundaries, when to let go, and how to grow brand and influence; significant improvement in how Puneet navigates SDM-level decisions
- **Promotion support:** Attempted (ultimately delayed due to competing priorities) for Jessie Guo, Ryan Mao, and Kristan
- All year Epics delivered as committed

*Manager quote:* "His talent development work resulted in 43% of his organization achieving Outstanding performance ratings."

*Peer quotes:* "Drew provides an environment that perfectly balances constructive feedback without being overly prescriptive." / "Drew has a very deep pool of technical and tribal knowledge... this depth of knowledge enables Drew to be a much more effective façade between the team and the various non-technical teams that we support." / "Drew never puts downward pressure on the team and instead uses his abilities to provide support to unlock the capabilities of the team. This creates an environment where the team always feels like it has a direction but never stressed or overwhelmed."

---

## Quantifiable Metrics & Results

| Metric | Value | Year |
|--------|-------|------|
| Revenue impact (iOS ALC/ALOP) | $26M+ in ~6 months; $100M+ annually | 2023 |
| Oracle→Postgres migration cost avoidance | ~$300K in prevented lost sales | 2018 |
| Cart host reduction (Fleet Optimizer POC) | 70% reduction | 2021 |
| APEX TT queue reduction | 70 → ~20 (H1 2021), then sustained ~10 (2022) | 2021–2022 |
| SAS risks reduced | Thousands → zero in "recommended fixes" category | 2021 |
| Total epics delivered (single year) | 168 across 3 teams | 2023 |
| Epics delivered in H1 alone | 91 | 2023 H1 |
| L6 promotions facilitated in one year | 2 (Puneet SDM + Danisha SDE) | 2023 |
| Org achieving Outstanding ratings | 43% | 2024 |
| Applaudible recognitions given (6 months) | 73 (109% increase) | 2022 H1 |
| Headcount managed (peak, simultaneously) | 17 across 2 teams | 2021 |
| Interview activities in a single year | 14 | 2022 |
| Rolling Stone migration milestones | ~100 milestones across 9 services | 2018 |
| Promotions/career advancements facilitated | 10+ across career (SDEs, SDMs, SDE3s) | 2019–2024 |

---

## People Development Record

| Person | Transition | Drew's Role |
|--------|-----------|-------------|
| Akanksha | L8 → L9, then → SDM | Coached, mentored, advocated |
| Puneet Wishwas | SDE II → SDM → L6 SDM | Transition mentor, coaching, doc editing, org navigation |
| Yates (Yates Monteith) | SDE II → SDE III | Promotion doc, growth opportunity assignment |
| Danisha Vayaland | SDE → L6 SDE | Coaching, doc support |
| Rabi Gupta | SDE II → SDE III | Doc support, growth opportunity, internal mobility facilitation |
| Srini Kandari | L4 → L5 SDE | Doc support (stepped in when JB couldn't close it) |
| Yasin | → L5 | Via Puneet; Drew edited and finalized the document |
| Barath N | SDE I → SDE II | Direct coaching |
| Nayana | Promotions SME development | Targeted opportunity assignment |
| Kimmy Dai | Mentee → SDM path | Formal mentorship program |
| JB Reefer | SDM (coaching plan) | Mid-year coaching plan; managed out when insufficient improvement |
| Joey Vinegard | NI risk → Valued | Managed through JB with Drew's direct coaching |

---

## Domain & Technical Expertise

Drew's deep technical expertise spans Audible's most critical e-commerce and payments infrastructure:

### Purchase / Cart Systems
- AudibleCartService (owned directly for years)
- AMPAS (AudibleMembershipPaymentAuthorizationService)
- AOEPS (checkout/order placement)
- Easy Exchanges
- Unified Checkout Experience (UCX)

### Payments / ExternallyManagedPayments (EMP)
- Google Play Payments (GPP) — Subscriptions, Extra Credits, ALC/ALOP, Alt Billing, UCB
- Apple In-App Purchase — ALC/ALOP via Apple Partner Billing
- Puma → PayStation migration
- Amazon Gift Cards, Product Vouchers
- ExternallyManagedPayments (EMP) framework
- VISA compliance, PAPG (payment compliance)
- Fraud detection and prevention (iOS, GDPR, external credit fraud)

### Promotions / Pricing
- AudiblePriceAggregatorService
- AudibleCustomerSegmentationService
- Centralized Pricing
- Flexible Promotions
- BOGO, Extra Credits, Daily Deals, MFA promotions
- Coupon systems (Amazon standard)

### Membership / Subscriptions
- AudibleMembershipManagementService
- AudibleMembershipInformationService
- AudibleMembershipCatalogService
- AudibleRedemptionService
- ABOS (Audible Buying Options Service)

### Platform / Infrastructure
- Oracle → PostgreSQL migrations
- AL2012 → AL2 host migrations
- CI/CD pipeline implementation
- Fleet Optimizer, CloudTune, IMR
- SAS risk remediation, Anvil recertifications
- COE management

---

## Consistent Strengths (cited repeatedly by managers and peers across years)

### Technical Knowledge & Domain Expertise
Universally cited. Drew's institutional knowledge of Audible's purchase/payment systems is described across years as unique, invaluable, and enabling faster decisions, better LOE estimates, and fewer production surprises.
> "Drew knows *everything* about the problem domain and the history of the org." (2024)
> "There's likely no one in the company who knows those flows as well as he does." (2023)
> "Drew is still relatively close to the technicals, which I cannot say about all other managers." (2023)

### Cross-functional Communication & Influence
Consistent strength in translating technical complexity for product, TPM, and executive stakeholders. Enables faster alignment, better prioritization, and fewer last-minute surprises.
> "My ability to communicate technically complex things to non-tech people." (self, 2023)
> "His strong network at Audible, which he strategically leverages to get things done." (2021)

### Customer Obsession
Recurring manager theme — Drew consistently thinks about customer impact first, including reading r/Audible to understand customer sentiment, and flagging product requests that would harm the customer experience.
> "Drew thinks about our software development and operations in the context of risk to the customer, not risk to our ticketing scores or metrics." (2021)

### Activate Caring / Team Culture
Repeatedly cited for building inclusive, high-trust teams; shielding engineers from interruptions; recognizing contributions; responding to personal needs proactively.
> "Drew never puts downward pressure on the team... This creates an environment where the team always feels like it has a direction but never stressed or overwhelmed." (2024)
> "He is the Iron Dome. He makes space when his engineers make space." (2021)

### Escalation & Stakeholder Management
Known for knowing who to call, when to escalate, and how to drive resolution. Described as the primary escalation point for the domain — "once escalated to Drew, he will see the problem through or find the correct owner" (2021).

### Operational Excellence Culture
Built OE-focused team cultures in every team he led. APEX went from historically the noisiest team to the OE leader in Shopping Domain under his leadership. Personally dove into TT queues, drove SAS risk reduction, COE perfection.

---

## Areas of Growth (noted by managers over the years)

These provide useful framing for "areas for improvement" questions in interviews:

- **Delegation:** Consistent theme through 2018–2022 — Drew had a tendency to go too deep himself rather than delegating to senior engineers. Actively worked on this; improved significantly by 2024.
- **Time management / prioritization:** Managing 2 teams simultaneously naturally created overextension; improved measurably by 2024.
- **Imagine & Invent:** Some feedback that Drew's deep knowledge occasionally created skepticism that came across as defeatist to stakeholders. Improved significantly by 2023 ("made improvements in his ability to consider what is possible").
- **Visibility / branding:** Early feedback (2018–2019) to socialize and present more; became much stronger by 2022–2023 as a recognized domain expert and 3PX representative.

---

## Key Quotes for Resume / Cover Letter Use

### On Leadership
> "He effectively leverages the strengths of various members of his team to get the right people in the room to solve whatever problem comes up." — Manager, 2020
> "Drew is a dependable leader who has demonstrated success in delivery of key strategic initiatives." — Manager, 2022
> "Drew demonstrated solid leadership and management capabilities throughout 2024, making contributions both as a manager of managers and as a scrum team leader." — Manager, 2024

### On Technical Credibility
> "As the owner of the Shopping domain I feel confident that I can route any issues I encounter to him and he will be able to handle it from there." — Peer, 2021
> "Drew's knowledge and insight of the services in Audible and Amazon gave confidence in our collective ability to understand the risk points and focus on areas of concern." — Peer, 2022
> "Drew is able to more often effectively and accurately answer questions/inquiries from our product partners, without proxying questions to devs on the team." — Direct report, 2024

### On People Management
> "Drew has emerged as a strong leader for the team and an SDM that the team can look up to." — Peer, 2019
> "In my experience Drew is pretty good at identifying differences in individuals' personalities and adapting to them appropriately, working with each person in a way that they respond best to." — Direct report, 2019
> "Drew is one of the best managers I have ever had." — Direct report, 2023

### On Delivery Under Pressure
> "What makes this different in Drew's case is that on top of all these challenging and exciting responsibilities, Drew had to lead a team of 15+ engineers, technically divided into 2 teams. Drew accomplished all of the above with flying colors." — Manager, 2021
> "This high intensity project was completed without attrition of any of the 3PX engineers working on the project." — Peer, 2022 (re: ALC/ALOP)

---

## Accomplishment Bullet Templates (Resume-ready)

These are pre-framed using impact → action → outcome structure:

- Led Oracle-to-PostgreSQL database migration of 9 Audible services (20+ engineers, contractors, DBAs); engineered zero-downtime dual-read/write solution previously deemed unachievable, preventing ~$300K in lost revenue.
- Launched iOS in-app purchases via Apple Partner Billing (Project ALChemy), opening a new revenue stream that generated $26M in incremental revenue within 6 months and exceeds $100M annually.
- Led global rollout of Google Play Payments across Android, managing daily scrum teams and resolving Amazon downstream complexities across a hard compliance deadline; delivered on time with zero blocking issues at launch.
- Reduced Audible Cart team's open ticket (TT) queue from 70 to a sustained ~10 by driving systematic root cause analysis and SAS risk remediation — reversed the team from worst to best OE performer in the Shopping Domain.
- Reduced cart infrastructure footprint by 70% through Fleet Optimizer POC, saving significant hosting costs.
- Transitioned an org from one over-sized team (14+ reports) to three focused 2-pizza teams (APEX, COFFEE, PRIMO) by co-designing a domain reorg adopted by Audible leadership.
- Led PERU organization (ALPACA + COFFEE) of 4 L6 direct reports through delivery of 168 epics in a single year; facilitated 2 simultaneous L6 promotions (SDM + SDE) and 1 L5 promotion.
- Drove 43% of direct organization to Outstanding performance ratings in 2024 while simultaneously managing two performance improvement cases to resolution.
- Managed multiple performance improvement processes including managing out both an IC and an SDM; created best practices documentation shared across the engineering management community.
- Coached 10+ engineers through promotion cycles across SDE and SDM tracks, including several off-cycle and challenging cases.
- Served as Consumer Domain technical POC to multiple Amazon partner teams (DA, DEP, Matcha/Player & Library), enabling faster feasibility decisions and reducing cross-team friction on critical payment initiatives.

---

## Context Notes for Future Use

- **Company:** Audible, Inc. (Amazon subsidiary) — Newark, NJ
- **Domain:** Consumer-facing e-commerce: purchase flow, payments, promotions, pricing, membership
- **Scale:** Systems process every Audible transaction globally; changes have immediate customer and revenue impact
- **Culture keywords:** OE (Operational Excellence), PI Planning (Program Increment), Sev-2s, TTs (trouble tickets), Epics, SDM (Software Development Manager), SDE (Software Development Engineer), TPM (Technical Program Manager)
- **Key internal projects referenced:** Rolling Stone, Minerva, Wakanda, Project 7, GPP (Google Play Payments), EMP/ExternallyManagedPayments, UCX (Unified Checkout Experience), ALC/ALOP (Apple's alt payment system), Montana, Thunderbird, DxGy, S-Team goals
- **Key partner orgs:** Matcha (Player & Library), DCCS/DEP/DICE/DA (Amazon Digital teams), mShop (Amazon mobile shopping), Matcha, Marketing Operations
