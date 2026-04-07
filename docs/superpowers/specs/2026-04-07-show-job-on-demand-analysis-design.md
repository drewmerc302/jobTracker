# Show-Job On-Demand Analysis

## Problem

`--show-job` only displays `suggested_edits` and `keyword_gaps` after `--tailor-job` has been run, because the Sonnet resume analysis lives inside `run_tailor_for_job`. This forces a wasteful workflow: run `--tailor-job` to populate suggestions, run `--show-job` to read them, then run `--tailor-job` again with `--adopt` to apply edits.

## Goal

`--show-job` should display the full analysis (including suggested edits and keyword gaps) on first invocation by running the Sonnet analysis on-demand and caching the result. Subsequent calls reuse the cache. The automated 12-hour pipeline is unaffected.

## Design

### New helper: `ensure_analysis` in `tailor.py`

```python
def ensure_analysis(job: dict, db: Database, config: Config, force: bool = False) -> dict:
```

**Behavior:**
1. Read existing suggestions from `db.get_match(job["id"])`
2. If `suggested_edits` is already populated and `force=False`: return cached suggestions dict (no LLM call)
3. If `job["description"]` is empty/None: skip LLM call, return existing cached suggestions as-is
4. Otherwise: load resume YAML via `get_active_resume_yaml(config)`, call `llm_resume_analysis()`, merge and write to DB, return full result

**Merge logic:** When writing Sonnet results to DB, fall back to existing Haiku-generated values:
- `key_requirements`: use Sonnet result, fall back to existing if Sonnet returns empty
- `interview_talking_points`: same fallback behavior
- `suggested_edits`, `keyword_gaps`: always from Sonnet (these don't exist in the Haiku output)

This preserves the merge behavior currently in `run_tailor_for_job` lines 344-353.

**Return value:** The full `llm_resume_analysis` response dict (including `reordered_bullets`, `suggested_edits`, `keyword_gaps`, `key_requirements`, `interview_talking_points`). The DB cache only stores the display-facing fields (no `reordered_bullets`), but the return value includes everything so `--tailor-job` can use `reordered_bullets` for PDF generation.

When returning from cache (no LLM call), `reordered_bullets` will not be present — the return value will have `reordered_bullets` set to `{}`. Both paths return the same shape dict to simplify downstream code. `--tailor-job` always calls with `force=True` since it needs fresh reorder data.

**Error handling:** If `llm_resume_analysis` raises an exception, catch it, log a warning, and return existing cached suggestions (or empty dict). `--show-job` degrades gracefully to showing partial suggestions.

**Note:** `get_active_resume_yaml` is cheap file I/O, so the double-load in `--tailor-job` (once here, once for PDF generation) is acceptable.

### Changes to `--show-job` handler (pipeline.py)

- After fetching the match, call `ensure_analysis(job, db, config, force=args.fresh)`
- `ensure_analysis` writes to DB if new analysis was generated
- Re-read suggestions from the return value and patch into the match dict in memory (no redundant DB fetch)
- Pass patched match to `_format_job_detail`

### Changes to `--tailor-job` handler (pipeline.py)

- Always call `ensure_analysis(job, db, config, force=True)` — tailor always needs `reordered_bullets` for PDF generation, and that's only available from a fresh LLM call (not stored in DB cache)
- Pass the returned analysis dict into `run_tailor_for_job`

### Changes to `run_tailor_for_job` (tailor.py)

- New parameter: `analysis: dict` replaces the internal `llm_resume_analysis()` call
- Drops its own `llm_resume_analysis()` call
- Drops its own `db.update_match_suggestions()` write
- Only responsible for: reordering bullets, applying adopted edits, generating PDFs

### New `--fresh` flag (argparse)

- Boolean flag, works with both `--show-job` and `--tailor-job`
- Forces `ensure_analysis` to re-run the Sonnet analysis even if cached suggestions exist
- Use case: resume YAML has changed since last analysis

### Unchanged

- `--show-all-jobs`: reads DB as-is, no on-demand analysis (avoids burning tokens on many jobs)
- Automated 12-hour pipeline: filter step still uses cheap Haiku, no Sonnet calls added
- `_format_job_detail`: no changes needed, already renders `suggested_edits` and `keyword_gaps` when present

## Token Budget Impact

- `--show-job` now triggers one Sonnet call per job (only on first view, cached after)
- `--tailor-job` reuses the cached analysis by default (saves one Sonnet call vs current behavior)
- `--tailor-job --fresh` or `--show-job --fresh` forces a re-analysis
- Net effect: same or fewer Sonnet calls for the typical workflow
