# Show-Job On-Demand Analysis Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `--show-job` display suggested resume edits on first invocation by extracting LLM analysis into a shared `ensure_analysis` helper, eliminating the need to run `--tailor-job` first.

**Architecture:** Extract `llm_resume_analysis` + DB write logic from `run_tailor_for_job` into `ensure_analysis()` in `tailor.py`. Both `--show-job` and `--tailor-job` call `ensure_analysis`. Add `--fresh` flag to force re-analysis.

**Tech Stack:** Python, anthropic SDK, SQLite, pytest

**Spec:** `docs/superpowers/specs/2026-04-07-show-job-on-demand-analysis-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/steps/tailor.py` | Modify (lines 314-365) | Add `ensure_analysis`, slim down `run_tailor_for_job` |
| `src/pipeline.py` | Modify (lines 14, 52-56, 531-548, 595-637, 727-754) | Wire up `ensure_analysis`, add `--fresh` flag, update `--step tailor` |
| `tests/test_tailor.py` | Modify | Add tests for `ensure_analysis` |
| `tests/test_pipeline.py` | Modify | Add test for `--fresh` arg parsing |

---

### Task 1: Add `ensure_analysis` to `tailor.py`

**Files:**
- Modify: `src/steps/tailor.py` (add function after line 188, before `generate_resume_pdf`)
- Test: `tests/test_tailor.py`

- [ ] **Step 1: Write failing test for `ensure_analysis` — cache hit path**

Add to `tests/test_tailor.py`:

```python
from src.steps.tailor import ensure_analysis


def test_ensure_analysis_returns_cached_when_edits_exist():
    """When suggested_edits already exist in DB, return them without LLM call."""
    from unittest.mock import MagicMock, patch

    db = MagicMock()
    config = MagicMock()
    job = {"id": "Stripe:123", "description": "Build stuff"}

    cached_suggestions = {
        "suggested_edits": [{"original": "a", "suggested": "b", "reason": "kw"}],
        "keyword_gaps": ["agile"],
        "key_requirements": ["Python"],
        "interview_talking_points": ["Led teams"],
    }
    db.get_match.return_value = {"suggestions": json.dumps(cached_suggestions)}

    with patch("src.steps.tailor.llm_resume_analysis") as mock_llm:
        result = ensure_analysis(job, db, config)

    assert result["suggested_edits"] == cached_suggestions["suggested_edits"]
    assert result.get("reordered_bullets") == {}
    mock_llm.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_tailor.py::test_ensure_analysis_returns_cached_when_edits_exist -v`
Expected: FAIL with `ImportError: cannot import name 'ensure_analysis'`

- [ ] **Step 3: Write failing test for `ensure_analysis` — cache miss path (LLM call)**

Add to `tests/test_tailor.py`:

```python
@patch("src.steps.tailor.llm_resume_analysis")
@patch("src.steps.tailor.get_active_resume_yaml")
def test_ensure_analysis_calls_llm_when_no_edits_cached(mock_get_yaml, mock_llm):
    """When no suggested_edits in DB, call LLM and write results."""
    from unittest.mock import MagicMock

    db = MagicMock()
    config = MagicMock()
    job = {"id": "Stripe:123", "description": "Build stuff"}

    # DB has Haiku suggestions (no suggested_edits)
    haiku_suggestions = {
        "key_requirements": ["Python"],
        "interview_talking_points": ["Led teams"],
    }
    db.get_match.return_value = {"suggestions": json.dumps(haiku_suggestions)}

    # LLM returns full analysis
    mock_get_yaml.return_value = (Path("/fake/resume.yaml"), {"name": "Drew"})
    mock_llm.return_value = {
        "reordered_bullets": {"Acme - EM": ["c", "a"]},
        "suggested_edits": [{"original": "a", "suggested": "b", "reason": "kw"}],
        "keyword_gaps": ["agile"],
        "key_requirements": ["React"],
        "interview_talking_points": [],
    }

    result = ensure_analysis(job, db, config)

    # Should have called LLM
    mock_llm.assert_called_once()
    # Should have written merged suggestions to DB
    db.update_match_suggestions.assert_called_once()
    written = json.loads(db.update_match_suggestions.call_args[0][1])
    assert written["suggested_edits"] == [{"original": "a", "suggested": "b", "reason": "kw"}]
    assert written["keyword_gaps"] == ["agile"]
    # Sonnet returned empty talking points, should fall back to Haiku
    assert written["interview_talking_points"] == ["Led teams"]
    # key_requirements: Sonnet had a value, use it
    assert written["key_requirements"] == ["React"]
    # Return includes reordered_bullets for tailor-job
    assert result["reordered_bullets"] == {"Acme - EM": ["c", "a"]}
```

- [ ] **Step 4: Write failing test for `ensure_analysis` — force re-analysis**

Add to `tests/test_tailor.py`:

```python
@patch("src.steps.tailor.llm_resume_analysis")
@patch("src.steps.tailor.get_active_resume_yaml")
def test_ensure_analysis_force_reruns_even_with_cache(mock_get_yaml, mock_llm):
    """force=True should call LLM even when cached edits exist."""
    from unittest.mock import MagicMock

    db = MagicMock()
    config = MagicMock()
    job = {"id": "Stripe:123", "description": "Build stuff"}

    cached = {
        "suggested_edits": [{"original": "old", "suggested": "old+", "reason": "old"}],
        "key_requirements": ["Python"],
        "interview_talking_points": ["Led teams"],
    }
    db.get_match.return_value = {"suggestions": json.dumps(cached)}

    mock_get_yaml.return_value = (Path("/fake/resume.yaml"), {"name": "Drew"})
    mock_llm.return_value = {
        "reordered_bullets": {},
        "suggested_edits": [{"original": "new", "suggested": "new+", "reason": "new"}],
        "keyword_gaps": [],
        "key_requirements": ["Go"],
        "interview_talking_points": ["Scaled systems"],
    }

    result = ensure_analysis(job, db, config, force=True)

    mock_llm.assert_called_once()
    assert result["suggested_edits"] == [{"original": "new", "suggested": "new+", "reason": "new"}]
```

- [ ] **Step 5: Write failing test for `ensure_analysis` — empty description skips LLM**

Add to `tests/test_tailor.py`:

```python
def test_ensure_analysis_skips_llm_when_no_description():
    """Jobs with empty description should not trigger LLM call."""
    from unittest.mock import MagicMock

    db = MagicMock()
    config = MagicMock()
    job = {"id": "Stripe:123", "description": ""}

    haiku = {"key_requirements": ["Python"], "interview_talking_points": ["Led teams"]}
    db.get_match.return_value = {"suggestions": json.dumps(haiku)}

    result = ensure_analysis(job, db, config)

    assert result["key_requirements"] == ["Python"]
    assert result.get("reordered_bullets") == {}
```

- [ ] **Step 6: Write failing test for `ensure_analysis` — LLM error degrades gracefully**

Add to `tests/test_tailor.py`:

```python
@patch("src.steps.tailor.llm_resume_analysis")
@patch("src.steps.tailor.get_active_resume_yaml")
def test_ensure_analysis_catches_llm_error(mock_get_yaml, mock_llm):
    """LLM errors should be caught, returning cached suggestions."""
    from unittest.mock import MagicMock
    import anthropic

    db = MagicMock()
    config = MagicMock()
    job = {"id": "Stripe:123", "description": "Build stuff"}

    haiku = {"key_requirements": ["Python"], "interview_talking_points": ["Led teams"]}
    db.get_match.return_value = {"suggestions": json.dumps(haiku)}

    mock_get_yaml.return_value = (Path("/fake/resume.yaml"), {"name": "Drew"})
    mock_llm.side_effect = Exception("API timeout")

    result = ensure_analysis(job, db, config)

    assert result["key_requirements"] == ["Python"]
    db.update_match_suggestions.assert_not_called()
```

- [ ] **Step 7: Implement `ensure_analysis`**

Add to `src/steps/tailor.py` after `llm_resume_analysis` (after line 188):

```python
def ensure_analysis(job: dict, db: Database, config: Config, force: bool = False) -> dict:
    """Run Sonnet resume analysis on-demand, caching results in DB.

    Returns the full analysis dict including reordered_bullets.
    When served from cache, reordered_bullets is {}.
    """
    match = db.get_match(job["id"])
    existing = json.loads(match.get("suggestions") or "{}") if match else {}

    # Cache hit: suggested_edits already populated and not forcing refresh
    if existing.get("suggested_edits") and not force:
        existing.setdefault("reordered_bullets", {})
        return existing

    # No description: skip LLM, return what we have
    if not job.get("description"):
        existing.setdefault("reordered_bullets", {})
        return existing

    # Cache miss or force: run Sonnet analysis
    try:
        resume_yaml_path, resume_data = get_active_resume_yaml(config)
        resume_yaml_str = yaml.dump(resume_data, default_flow_style=False)
        analysis = llm_resume_analysis(resume_yaml_str, job["description"], config)
    except Exception:
        logger.warning(f"LLM analysis failed for {job['id']}, using cached suggestions")
        existing.setdefault("reordered_bullets", {})
        return existing

    # Merge: Sonnet results with Haiku fallbacks
    merged = {
        "suggested_edits": analysis.get("suggested_edits", []),
        "keyword_gaps": analysis.get("keyword_gaps", []),
        "key_requirements": analysis.get("key_requirements", [])
        or existing.get("key_requirements", []),
        "interview_talking_points": analysis.get("interview_talking_points", [])
        or existing.get("interview_talking_points", []),
    }
    db.update_match_suggestions(job["id"], json.dumps(merged))

    # Return full analysis (including reordered_bullets for tailor-job)
    result = {**merged, "reordered_bullets": analysis.get("reordered_bullets", {})}
    return result
```

- [ ] **Step 8: Run all new tests to verify they pass**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_tailor.py -v -k "ensure_analysis"`
Expected: All 5 new tests PASS

- [ ] **Step 9: Run full test suite to check for regressions**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_tailor.py -v`
Expected: All tests PASS

- [ ] **Step 10: Commit**

```bash
cd /Users/drewmerc/workspace/jobTracker
git add src/steps/tailor.py tests/test_tailor.py
git commit -F /tmp/msg.txt
# msg: "feat: add ensure_analysis helper for on-demand resume analysis"
```

---

### Task 2: Slim down `run_tailor_for_job` to use passed-in analysis

**Files:**
- Modify: `src/steps/tailor.py:314-365`
- Test: `tests/test_tailor.py`

- [ ] **Step 1: Write failing test for new `run_tailor_for_job` signature**

Add to `tests/test_tailor.py`:

```python
@patch("src.steps.tailor.generate_cover_letter_pdf")
@patch("src.steps.tailor.generate_resume_pdf")
@patch("src.steps.tailor.apply_suggested_edits")
@patch("src.steps.tailor.reorder_resume_yaml")
def test_run_tailor_uses_passed_analysis(mock_reorder, mock_apply, mock_resume, mock_cover):
    """run_tailor_for_job should use the analysis dict passed to it, not call LLM."""
    from unittest.mock import MagicMock
    from src.steps.tailor import run_tailor_for_job

    db = MagicMock()
    config = MagicMock()
    job = {"id": "Stripe:123", "company": "Stripe", "description": "Build stuff", "title": "EM"}
    analysis = {
        "reordered_bullets": {"Acme - EM": ["c", "a"]},
        "suggested_edits": [{"original": "a", "suggested": "b", "reason": "kw"}],
    }

    mock_reorder.return_value = {"experience": []}
    mock_resume.return_value = Path("/out/resume.pdf")
    mock_cover.return_value = Path("/out/cover.pdf")

    result = run_tailor_for_job(
        job=job,
        analysis=analysis,
        resume_yaml_path=Path("/fake/resume.yaml"),
        resume_data={"name": "Drew"},
        output_dir=Path("/tmp/out"),
        config=config,
    )

    mock_reorder.assert_called_once_with({"name": "Drew"}, {"Acme - EM": ["c", "a"]})
    assert result["resume_pdf"] == Path("/out/resume.pdf")
    # Should NOT have written suggestions to DB
    db.update_match_suggestions.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_tailor.py::test_run_tailor_uses_passed_analysis -v`
Expected: FAIL (signature mismatch — `analysis` is not a parameter yet)

- [ ] **Step 3: Modify `run_tailor_for_job` signature and body**

Replace `run_tailor_for_job` in `src/steps/tailor.py:314-365` with:

```python
def run_tailor_for_job(
    job: dict,
    analysis: dict,
    resume_yaml_path: Path,
    resume_data: dict,
    output_dir: Path,
    config: Config,
    adopt_edits: set[int] | None = None,
) -> dict:
    job_dir = output_dir / f"{job['company']}_{job['id'].replace(':', '_')}"
    tailored = reorder_resume_yaml(resume_data, analysis.get("reordered_bullets", {}))

    if adopt_edits:
        edits = analysis.get("suggested_edits", [])
        tailored = apply_suggested_edits(tailored, edits, adopt_edits)
        logger.info(f"Applied {len(adopt_edits)} suggested edits to resume")

    resume_pdf = generate_resume_pdf(tailored, job_dir, config)
    cover_letter_pdf = generate_cover_letter_pdf(
        resume_yaml_path,
        job.get("description", ""),
        job["company"],
        job["title"],
        job_dir,
        config,
    )
    return {
        "job_id": job["id"],
        "resume_pdf": resume_pdf,
        "cover_letter_pdf": cover_letter_pdf,
        "analysis": analysis,
    }
```

Key changes: removed `evaluation` and `db` params, added `analysis` param, removed `llm_resume_analysis` call, removed `db.update_match_suggestions` and `db.update_match_paths` calls.

- [ ] **Step 4: Run new test to verify it passes**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_tailor.py::test_run_tailor_uses_passed_analysis -v`
Expected: PASS

- [ ] **Step 5: Run full tailor tests**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_tailor.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/drewmerc/workspace/jobTracker
git add src/steps/tailor.py tests/test_tailor.py
git commit -F /tmp/msg.txt
# msg: "refactor: slim run_tailor_for_job to accept pre-computed analysis"
```

---

### Task 3: Add `--fresh` flag and wire up pipeline handlers

**Files:**
- Modify: `src/pipeline.py:14,52-56,531-548,595-637`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test for `--fresh` arg parsing**

Add to `tests/test_pipeline.py`:

```python
def test_parse_args_fresh():
    args = parse_args(["--show-job", "Stripe:123", "--fresh"])
    assert args.fresh is True


def test_parse_args_fresh_default():
    args = parse_args(["--show-job", "Stripe:123"])
    assert args.fresh is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_pipeline.py::test_parse_args_fresh -v`
Expected: FAIL with `AttributeError: Namespace has no attribute 'fresh'`

- [ ] **Step 3: Add `--fresh` flag to argparse**

In `src/pipeline.py`, after the `--gripes` argument (after line 131), add:

```python
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Force re-analysis even if cached (use with --show-job or --tailor-job)",
    )
```

- [ ] **Step 4: Run arg parsing tests**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/test_pipeline.py -v -k "fresh"`
Expected: Both PASS

- [ ] **Step 5: Update import in `pipeline.py`**

Change line 14 of `src/pipeline.py` from:

```python
from src.steps.tailor import get_active_resume_yaml, run_tailor_for_job
```

to:

```python
from src.steps.tailor import get_active_resume_yaml, run_tailor_for_job, ensure_analysis
```

- [ ] **Step 6: Wire up `--show-job` handler**

Replace the `if args.show_job:` block (lines 531-548) with:

```python
    if args.show_job:
        job_id = args.show_job
        job = db.get_job(job_id)
        if not job:
            print(f"Job not found: {job_id}")
            return
        match = db.get_match(job_id)
        if not match:
            print(f"No match record for {job_id}")
            return
        analysis = ensure_analysis(dict(job), db, config, force=args.fresh)
        # Patch match with updated suggestions for display
        match = dict(match)
        match["suggestions"] = json.dumps({
            k: v for k, v in analysis.items() if k != "reordered_bullets"
        })
        print(_format_job_detail(job, match, db, markdown=args.markdown))
        if args.gripes:
            gripes = get_gripes(db, job["company"], config)
            if gripes:
                print(_format_gripes(gripes, job["company"], markdown=args.markdown))
            else:
                print(f"Could not fetch gripes for {job['company']}")
        return
```

- [ ] **Step 7: Wire up `--tailor-job` handler**

Replace the `if args.tailor_job:` block (lines 595-637) with:

```python
    if args.tailor_job:
        job_id = args.tailor_job
        job = db.get_job(job_id)
        if not job:
            logger.error(
                f"Job not found: {job_id}. Use --list-matches to see available IDs."
            )
            return
        match = db.get_match(job_id)
        if not match:
            logger.error(f"No match record for {job_id}. Run the filter step first.")
            return

        # Always force=True: tailor needs reordered_bullets which aren't cached
        analysis = ensure_analysis(dict(job), db, config, force=True)

        resume_yaml_path, resume_data = get_active_resume_yaml(config)

        # Parse --adopt flag
        adopt_indices = set()
        if args.adopt:
            try:
                adopt_indices = {int(n.strip()) for n in args.adopt.split(",")}
            except ValueError:
                logger.error("--adopt must be comma-separated numbers (e.g. '1,3,5')")
                return

        run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        output_dir = config.output_dir / run_date
        result = run_tailor_for_job(
            job=dict(job),
            analysis=analysis,
            resume_yaml_path=resume_yaml_path,
            resume_data=resume_data,
            output_dir=output_dir,
            config=config,
            adopt_edits=adopt_indices,
        )

        # Update PDF paths in DB
        db.update_match_paths(
            job_id,
            resume_path=str(result["resume_pdf"]) if result.get("resume_pdf") else None,
            cover_letter_path=str(result["cover_letter_pdf"]) if result.get("cover_letter_pdf") else None,
        )

        if result.get("resume_pdf"):
            print(f"Resume PDF:       {result['resume_pdf']}")
        if result.get("cover_letter_pdf"):
            print(f"Cover letter PDF: {result['cover_letter_pdf']}")
        if not result.get("resume_pdf") and not result.get("cover_letter_pdf"):
            print("PDF generation failed. Check logs.")
        return
```

Note: `db.update_match_paths` moved here from `run_tailor_for_job` since `run_tailor_for_job` no longer has `db`.

- [ ] **Step 8: Update `--step tailor` handler**

The `--step tailor` handler (lines 727-754) also calls `run_tailor_for_job` with the old signature. Replace lines 730-754 with:

```python
            unnotified = db.get_unnotified_matches()
            tailor_matches = [dict(m) for m in unnotified if not m.get("resume_path")]
            logger.info(
                f"Tailor standalone: found {len(tailor_matches)} untailored matches"
            )
            for job in tailor_matches:
                try:
                    analysis = ensure_analysis(job, db, config, force=True)
                    result = run_tailor_for_job(
                        job=job,
                        analysis=analysis,
                        resume_yaml_path=resume_yaml_path,
                        resume_data=resume_data,
                        output_dir=output_dir,
                        config=config,
                    )
                    db.update_match_paths(
                        job["id"],
                        resume_path=str(result["resume_pdf"]) if result.get("resume_pdf") else None,
                        cover_letter_path=str(result["cover_letter_pdf"]) if result.get("cover_letter_pdf") else None,
                    )
                except Exception as e:
                    logger.error(f"Tailor failed for {job['id']}: {e}")
```

- [ ] **Step 9: Run full test suite**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 10: Commit**

```bash
cd /Users/drewmerc/workspace/jobTracker
git add src/pipeline.py tests/test_pipeline.py
git commit -F /tmp/msg.txt
# msg: "feat: wire --show-job to on-demand analysis, add --fresh flag"
```

---

### Task 4: Manual smoke test

**Files:** None (verification only)

- [ ] **Step 1: Verify `--show-job` triggers analysis for an un-analyzed job**

Pick a job that hasn't had `--tailor-job` run yet:

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run jobtracker --list-matches`

Find a job with status `new`, then:

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run jobtracker --show-job "COMPANY:ID"`

Expected: Output includes "Suggested Resume Edits" and "Keyword gaps" sections (previously empty without running tailor first).

- [ ] **Step 2: Verify cache hit — second `--show-job` is instant**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run jobtracker --show-job "COMPANY:ID"`

Expected: Same output, no LLM call (should be noticeably faster).

- [ ] **Step 3: Verify `--fresh` forces re-analysis**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run jobtracker --show-job "COMPANY:ID" --fresh`

Expected: Output refreshed (LLM called again, may have slightly different suggestions).

- [ ] **Step 4: Verify `--tailor-job --adopt` works end-to-end**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run jobtracker --tailor-job "COMPANY:ID" --adopt 1,2`

Expected: PDFs generated successfully.

- [ ] **Step 5: Verify `--show-all-jobs` does NOT trigger analysis**

Run: `cd /Users/drewmerc/workspace/jobTracker && uv run jobtracker --show-all-jobs`

Expected: Jobs without prior analysis still show no suggested edits (no LLM calls).
