# Design: `--gripes` Feature

**Date:** 2026-04-06  
**Status:** Approved

## Overview

Add a `--gripes` flag to `jobtracker` that, when used with `--show-job`, fetches and displays the most common employee pain points for the target company. Results are cached per-company in the database with a 30-day TTL to avoid redundant web searches.

## Requirements

- `uv run jobtracker --show-job "Stripe:7609424" --gripes` fetches and displays employee gripes for Stripe
- Output includes: a TL;DR list (5 bullets) + 3–5 expanded themes with name, one-line summary, and 2–3 sentence detail
- Results cached in DB per company; re-fetched if cache is older than 30 days
- Works in both plain text and markdown output modes (`--markdown`)
- No separate `--refresh-gripes` flag in this iteration

## Architecture

### 1. Database Layer (`src/db.py`)

New table — add to the `executescript` block inside `_create_tables()` in `db.py` (no separate migration needed; `CREATE TABLE IF NOT EXISTS` handles existing installs):
```sql
CREATE TABLE IF NOT EXISTS company_gripes (
    company     TEXT PRIMARY KEY,
    gripes_json TEXT NOT NULL,
    fetched_at  TEXT NOT NULL
)
```

New methods on `Database`:
- `get_company_gripes(company: str) -> dict | None` — returns parsed `gripes_json` or `None` if not cached
- `upsert_company_gripes(company: str, gripes: dict)` — stores with current UTC timestamp

### 2. Gripes Module (`src/steps/gripes.py`)

**Web search**: 3 queries per company using direct HTTP requests (similar to `_web_research` in `interview_prep.py`, but targeting review-focused URLs). Each query is a DuckDuckGo or similar search URL fetched via `urllib.request.urlopen`:
1. `"{company}" employee reviews site:glassdoor.com`
2. `"{company}" employees complaints reddit OR blind`
3. `"{company}" work culture problems`

Search results concatenated and capped at ~4000 chars.

**LLM**: Claude Haiku (`config.llm_filter_model`) with `tool_use` forced choice. Tool schema:

```python
GRIPES_TOOL = {
    "name": "company_gripes",
    "description": "Analyze employee reviews and summarize common complaints for a company",
    "input_schema": {
        "type": "object",
        "properties": {
            "tldr": {
                "type": "array",
                "items": {"type": "string"},
                "description": "5 one-line bullets summarizing the most common employee complaints"
            },
            "themes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name":    {"type": "string"},
                        "summary": {"type": "string"},
                        "detail":  {"type": "string"}
                    },
                    "required": ["name", "summary", "detail"]
                },
                "description": "3-5 recurring complaint themes with expanded detail"
            }
        },
        "required": ["tldr", "themes"]
    }
}
```

**Public function**:
```python
def get_gripes(db: Database, company: str, config: Config) -> dict | None
```

Logic:
1. Check DB cache; return cached result if `fetched_at >= datetime.now(utc) - timedelta(days=30)`
2. Run 3 web searches, concatenate results
3. Call LLM with search results
4. Upsert to DB, return result

Retry: `tenacity` with 3 attempts, exponential backoff, `anthropic.APIError`.

### 3. CLI (`src/pipeline.py`)

New argument:
```python
parser.add_argument(
    "--gripes",
    action="store_true",
    help="Show common employee pain points for the company (use with --show-job)",
)
```

In the `args.show_job` handler, after printing `_format_job_detail(...)`:
```python
if args.gripes:
    gripes = get_gripes(db, job["company"], config)
    if gripes:
        print(_format_gripes(gripes, job["company"], markdown=args.markdown))
    else:
        print(f"Could not fetch gripes for {job['company']}")
```

### 4. Output Formatting

`_format_gripes(gripes: dict, company: str, markdown: bool) -> str` in `pipeline.py`.

**Plain text:**
```
Employee Gripes (Stripe):
  TL;DR:
  - Slow promotion cycles with unclear criteria
  - On-call burden is high for ICs and EMs
  ...

  Work-life balance
  One-line summary.
  2-3 sentence detail expanding on the theme with specifics from reviews.
```

**Markdown:**
```markdown
## Employee Gripes

**TL;DR**
- Slow promotion cycles with unclear criteria
- On-call burden is high for ICs and EMs

### Work-life balance
*One-line summary.*

2-3 sentence detail expanding on the theme.
```

## Data Flow

```
--show-job + --gripes
    → pipeline.py: show_job handler
    → get_gripes(db, company, config)
        → db.get_company_gripes(company)  [cache hit? return]
        → _web_search(company)            [3 queries via urllib.request.urlopen]
        → _call_llm(search_results)       [Haiku + GRIPES_TOOL]
        → db.upsert_company_gripes(company, result)
    → _format_gripes(gripes, company, markdown)
    → print()
```

## Error Handling

- Web search failures: log warning, continue with partial results (empty string if all fail)
- LLM failure: log error, return `None`; pipeline prints "Could not fetch gripes for {company}" and continues
- Empty search results: LLM still called with minimal context; Haiku will synthesize from training knowledge

## Testing

- `tests/test_gripes.py`: unit tests with mocked web search and LLM responses
- Test cache hit (no web search called), cache miss (web search + LLM called), cache expiry (30-day check)
- Test `_format_gripes()` for both plain and markdown output

## Files Changed

| File | Change |
|------|--------|
| `src/db.py` | Add `company_gripes` table + 2 methods |
| `src/steps/gripes.py` | New module |
| `src/pipeline.py` | Add `--gripes` flag, call `get_gripes`, call `_format_gripes` |
| `tests/test_gripes.py` | New test module |

## Out of Scope

- `force` / `--refresh-gripes` flag (can add later; `force` param omitted until then)
- Gripes integrated into Obsidian notes
- Gripes shown without `--show-job`
