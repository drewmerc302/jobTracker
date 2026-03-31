---
name: interview-research
description: Generate a comprehensive interview prep document for a specific company and role. Researches interview process, questions, culture, compensation, and company details from current web sources. Use when the user asks to prep for an interview, research a company, or generate an interview guide.
---

# Interview Research & Prep Guide Generator

Produces a thorough, single-document interview preparation guide. The output is practical reference material the user can study before their interview — sourced from live web data, not training data.

## Inputs

Collect these before starting. Ask if any are missing:

| Input | Required | Notes |
|-------|----------|-------|
| Company name | Yes | — |
| Target role | Yes | Full title if known |
| Job description | Preferred | Paste or URL — used to tailor question categories |
| Interview stage | No | e.g. "just got the recruiter screen", "Loop next week" |
| Inside contact or referral | No | Tailor networking section if yes |

Drew's background (pre-loaded): mid-to-senior Engineering Manager, 21+ years experience, active job search. Tailor all talking points, behavioral questions, and negotiation strategy to this profile unless the user specifies otherwise.

## Research Phase

Search aggressively — 15-25 searches is expected for a thorough guide. Do not rely on training data for anything time-sensitive.

### Required searches (run all of these):

**Company fundamentals**
- `[company] annual revenue 2024 2025`
- `[company] investor relations earnings`
- `[company] products roadmap 2025`
- `[company] layoffs headcount 2024 2025`
- `[company] CEO leadership team site:linkedin.com`

**Culture & reviews**
- `[company] glassdoor reviews engineering manager`
- `[company] blind forum culture work life balance`
- `[company] comparably culture`
- `[company] engineering blog values`

**Interview process**
- `[company] engineering manager interview process site:glassdoor.com`
- `[company] EM interview process site:reddit.com`
- `[company] interview questions engineering manager site:blind.com`
- `[company] interview process timeline loop rounds`
- `[company] interview igotanoffer OR prepfully OR interviewing.io`
- `[role] [company] interview questions behavioral`

**Compensation**
- `[company] engineering manager salary site:levels.fyi`
- `[company] EM compensation equity RSU 2024 2025`
- `[company] offer negotiation tips`

**Recent news (last 6 months)**
- `[company] news site:techcrunch.com OR site:bloomberg.com 2025`
- `[company] product launch announcement 2025`
- `[company] strategic priorities 2025`

Mark any section where data wasn't found with: `⚠️ Data not found — check [suggested source]`. Never fabricate numbers or names.

## Output

Save the document to:
`/Users/drewmerc/workspace/jobTracker/outputs/interview-prep/[Company]-[Role-slug]-prep.md`

Create the `outputs/interview-prep/` directory if it doesn't exist.

Also write the note to Obsidian at:
`Topics/Job Applications/Interview Prep/[Company] - [Role].md`
Use `mcp__obsidian__write_note` for this.

---

## Document Template

Write the full document using this structure. Every section is required. If data is unavailable, say so explicitly.

```markdown
# [Company] — [Role] Interview Prep
*Generated: [date] | Source: live web research*

---

## 1. Company Snapshot

| Field | Detail |
|-------|--------|
| Founded | |
| HQ | |
| Employees | |
| Revenue (latest) | |
| Revenue growth YoY | |
| Profitable? | |
| Business model | |
| Public / Private | |
| Key competitors | |
| Recent headlines | |

---

## 2. What They Do

2-3 paragraphs: core product/service, target customers, revenue mix, market position.
Be specific — what does the company actually sell and to whom?

### Strategic Priorities (2025)
- Bullet list of stated or reported strategic initiatives

### Recent Developments (last 6 months)
- Product launches, partnerships, exec changes, M&A, layoffs, pivots

---

## 3. Leadership Team

| Name | Title | Background | Tenure |
|------|-------|------------|--------|
| | CEO | | |
| | CTO / CPO | | |
| | VP Eng / SVP Eng | | |
| | Hiring manager (if known) | | |

Note: verify on LinkedIn — titles change frequently.

---

## 4. Financial Health & Competitive Position

### Key Metrics
- Revenue trajectory (include 2-3 years if available)
- Profitability / burn rate
- Customer count, ARR, or other KPI
- Funding stage or market cap

### Competitive Landscape
- Top 2-3 competitors and how [company] differentiates
- Market tailwinds/headwinds

### Stability Signals
- Layoffs or hiring freezes? Recent funding? Any red flags?

---

## 5. Culture & Work Environment

### Stated Values
List the company's official values and what they actually mean in practice (per reviews).

### Employee Sentiment
- Glassdoor rating: X/5 ([N] reviews)
- Blind sentiment: [summary]
- Common praise themes
- Common complaint themes
- What EMs specifically say about the role

### Work Style
- Remote / hybrid / in-office policy
- Eng culture (move fast vs. process-heavy, data-driven, etc.)
- On-call expectations
- How PMs and EMs interact

### What They Screen For
Based on reviews and reported questions, list the 3-5 traits/behaviors they consistently probe for in interviews.

---

## 6. Compensation Benchmarks

### Engineering Manager Ranges (verify on levels.fyi)

| Level | Base | Bonus | Equity (annual) | Total |
|-------|------|-------|-----------------|-------|
| EM (mid) | | | | |
| EM (senior) | | | | |
| Sr. EM / Group EM | | | | |

### Equity Structure
- Type: RSU / options / phantom
- Vesting: cliff and schedule
- Refresh grants?
- 409A / strike price (private) or current stock price (public)

### Benefits Worth Noting
List standout benefits (401k match, parental leave, learning budget, etc.)

### Negotiation Notes
- Is this company known to negotiate? (per Blind/Glassdoor)
- What to anchor on
- Competing offer leverage — what's the market rate they'd be competing against?

---

## 7. Interview Process

### Pipeline Overview
List each stage in order:

1. **Recruiter screen** (~30 min) — what they cover
2. **Hiring manager screen** (~45-60 min) — focus areas
3. **Take-home / written exercise** (if any) — what it involves
4. **Loop / onsite** — list each panel with interviewer role and focus
5. **Executive / final round** (if applicable)

### Timeline
- Typical time recruiter → offer: X weeks
- How quickly do they move? (per Glassdoor interview reviews)
- When to follow up

### Evaluation Criteria
What are they actually assessing at each stage? What do interviewers report looking for?

### Red Flags to Watch For
- Questions that signal misalignment
- Signs of process disorganization or scope confusion
- Anything in recent reviews suggesting a problematic loop

---

## 8. Interview Questions — Reported & Likely

Organize by category. For each question include a brief note on what they're really assessing.

### Behavioral / Leadership
*EM-focused: hiring, performance management, conflict, prioritization, org design*

- [Question] *(probing for: X)*
- [Question] *(probing for: X)*
- ... (10-15 questions minimum)

### Situation-Specific / Role-Play
*Scenarios reported at this company specifically*

- [Question or scenario]
- ...

### Strategy / Org Design
*Typical for senior EM / group EM roles*

- [Question]
- ...

### Company-Specific
*Questions that require knowing this company's products, model, or context*

- [Question]
- ...

### Technical / System Design (if applicable)
*Scope varies by company — some EM loops include a light technical round*

- [Question or design topic]
- ...

### Questions Candidates Report Being Asked (verbatim)
Quotes from Glassdoor/Blind/Reddit where available. Cite source.

> "Tell me about a time you had to let someone go." — Glassdoor 2024
> "How would you build the engineering team for [product]?" — Blind thread

---

## 9. Questions to Ask Your Interviewers

Grouped by interview stage. Use these to signal strategic thinking and genuine interest.

### For the Recruiter Screen
1. ...
2. ...
3. ...

### For the Hiring Manager
1. ...
2. ...
3. ...
4. ...
5. ...

### For Engineering ICs on the Loop
1. ...
2. ...
3. ...

### For the Executive Round
1. ...
2. ...
3. ...

*(15-20 questions total — all company-specific, not generic)*

---

## 10. Strategic Talking Points

8-12 specific recent developments you can weave into answers or discussion. For each:
- **What**: The development (launch, initiative, metric, etc.)
- **Why it matters**: Business context
- **How to use it**: Which type of question or conversation it fits

Example format:
> **[Company] launched [product] in Q4 2024**
> Why it matters: First move into [market], competing with [X]
> Use in: "Why [company]?" answers, questions about the role's scope

---

## 11. STAR Story Bank

For Drew's background, pre-draft 6-8 STAR stories mapped to common EM question categories.
Each story should be 4-6 bullet points (Situation → Task → Action → Result).

| Category | Story Title | Situation | Key Action | Result |
|----------|-------------|-----------|------------|--------|
| Hiring & team building | | | | |
| Performance management | | | | |
| Cross-functional conflict | | | | |
| Prioritization under pressure | | | | |
| Technical direction / architecture | | | | |
| Org change / reorg | | | | |
| Stakeholder management | | | | |
| Failure / learning | | | | |

*Note: Fill in the Story Title and details based on Drew's actual experience if provided; otherwise leave as prompts.*

---

## 12. Pre-Interview Checklist

### 1 Week Before
- [ ] Read the company's last earnings call transcript or latest investor letter
- [ ] Follow company on LinkedIn; note any recent posts from the hiring manager
- [ ] Review the job description line by line; map each requirement to a STAR story
- [ ] Set up a levels.fyi alert for this company if negotiation is coming
- [ ] Look up each interviewer on LinkedIn; note their background and tenure

### 2-3 Days Before
- [ ] Read the last 5 engineering blog posts (if they have one)
- [ ] Run through your STAR stories out loud
- [ ] Prepare your 2-minute "walk me through your background" tailored to this role
- [ ] Review the compensation section of this doc; decide your target number
- [ ] Draft 2-3 specific questions for each interviewer based on their LinkedIn

### Day Before
- [ ] Confirm logistics (Zoom link, address, interviewer names)
- [ ] Review the Company Snapshot table cold
- [ ] Sleep

### Day Of
- [ ] Reread the "What They Screen For" section
- [ ] Have your questions list open during the call
- [ ] Send a thank-you note within 2 hours of each conversation

---

## 13. Insider Intel Template

Fill this in from any informational interviews, referrals, or LinkedIn outreach.

**Source**: [Name, title, how you know them]
**Date**:

- What's the real reason this role is open?
- What does success look like in the first 90 days?
- Who is the hardest interviewer and what do they care about?
- Is the hiring manager new or established?
- What's the team's current state? (size, tenure, morale)
- Is there internal competition for this role?
- What's the offer process like? Room to negotiate?

---

*End of prep guide. Good luck.*
```

---

## Post-Generation Steps

1. Save file to `outputs/interview-prep/` path above
2. Write to Obsidian vault using `mcp__obsidian__write_note`
3. Tell the user:
   - Where the file was saved
   - Which sections have the most time-sensitive data (leadership, financials, comp)
   - Which searches returned thin results
   - Offer to go deeper on: additional practice questions, system design walkthroughs, or comp negotiation strategy
