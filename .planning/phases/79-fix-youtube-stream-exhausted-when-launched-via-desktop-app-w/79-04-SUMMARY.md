---
phase: 79-fix-youtube-stream-exhausted-when-launched-via-desktop-app-w
plan: "04"
subsystem: testing
tags: [youtube, yt-dlp, drift-guard, source-grep, bug-fix, regression-lock]

# Dependency graph
requires:
  - phase: 79-fix-youtube-stream-exhausted-when-launched-via-desktop-app-w
    plan: "01"
    provides: musicstreamer.yt_dlp_opts.build_js_runtimes (the token the drift-guard counts)
provides:
  - Positive-form drift-guard: tests/test_yt_dlp_opts_drift.py with two source-grep assertions (B-79-DG-1)
affects:
  - Plans 79-02 and 79-03 (their call sites must contain exactly 1 build_js_runtimes( each for tests to turn GREEN)
  - Any future contributor modifying player.py or yt_import.py js_runtimes opts

# Tech tracking
tech-stack:
  added: []
  patterns:
    - positive-form source-grep drift-guard (count == 1 assertion, not negative grep)
    - pathlib.Path.read_text() for source-as-text test inspection
    - mirrors tests/test_packaging_spec.py:201-208 substrate-grep pattern

key-files:
  created:
    - tests/test_yt_dlp_opts_drift.py
  modified: []

key-decisions:
  - "Positive form (count == 1) over negative grep ('path': None absent) — avoids Pitfall 8: yt_dlp_opts.py itself contains 'path': None legitimately, so negative grep would always false-positive"
  - "Wave 2 parallel positioning — drift-guard is intentionally RED until 79-02 + 79-03 land; turns GREEN automatically on merge"
  - "Rule 1 auto-fix: escaped {{}} literal braces in .format() rationale string to prevent KeyError on Python's str.format() treating {'node': ...} as format placeholders"

patterns-established:
  - "Drift-guard pattern: pathlib.Path.read_text() + src.count('token') == N with multi-line rationale citing bug ID + regression scenario"

requirements-completed:
  - BUG-11

# Metrics
duration: ~1min
completed: "2026-05-16"
---

# Phase 79 Plan 04: Drift-guard test for build_js_runtimes call sites Summary

**Source-grep drift-guard asserting both player.py and yt_import.py contain exactly one `build_js_runtimes(` call each — positive-form lock against re-introducing the inline `{"node": {"path": None}}` literal that is the BUG-11 root cause.**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-05-16T17:50:55Z
- **Completed:** 2026-05-16T17:52:04Z
- **Tasks:** 1
- **Files created:** 1

## Accomplishments

- Created `tests/test_yt_dlp_opts_drift.py` with two POSITIVE-form drift-guard assertions (B-79-DG-1)
- `test_player_uses_build_js_runtimes`: reads `musicstreamer/player.py` as text; asserts `src.count("build_js_runtimes(") == 1` with multi-line rationale citing BUG-11, commit `a06549f`, and Plan 79-02
- `test_yt_import_uses_build_js_runtimes`: reads `musicstreamer/yt_import.py` as text; asserts `src.count("build_js_runtimes(") == 1` with rationale citing D-10 single-source-of-truth invariant and Pitfall 2 (insertion, not substitution)
- Tests correctly FAIL with "Current count: 0" in this worktree (Wave 2 parallel contract — turn GREEN once 79-02 + 79-03 land)

## Task Commits

1. **Task 1: Create tests/test_yt_dlp_opts_drift.py** - `6ded01c` (test)

## Files Created/Modified

- `tests/test_yt_dlp_opts_drift.py` — Two positive-form source-grep drift-guard assertions for BUG-11 regression lock

## Decisions Made

- Positive form `build_js_runtimes(` count assertion over negative `"path": None` grep — follows RESEARCH.md OQ 3 recommendation and avoids Pitfall 8 (the helper module `yt_dlp_opts.py` legitimately contains `"path": None`, so a negative grep would permanently false-positive)
- Wave 2 parallel positioning accepted — drift-guard RED until call sites land, GREEN automatically after merge
- No pytest fixtures, no parametrize, no additional imports beyond `pathlib.Path` — pure source-text inspection per plan spec

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Escaped literal curly braces in `.format()` rationale string**
- **Found during:** Task 1 (test execution verification)
- **Issue:** The rationale string in `test_player_uses_build_js_runtimes` contained `{'node': {'path': None}}` as an unescaped Python `.format()` string. Python's `str.format()` treated `{'node'}` as a format placeholder, raising `KeyError: "'node'"` when the assertion fired.
- **Fix:** Doubled the literal curly braces in the rationale string: `{'node': {'path': None}}` → `{{'node': {{'path': None}}}}` so they render correctly as `{'node': {'path': None}}` in the error output.
- **Files modified:** `tests/test_yt_dlp_opts_drift.py`
- **Verification:** Re-ran `uv run --with pytest pytest tests/test_yt_dlp_opts_drift.py -x -v`; now fails with `AssertionError: ... Current count: 0` (correct failure message, no KeyError)
- **Committed in:** `6ded01c` (included in task commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in format string)
**Impact on plan:** Necessary correctness fix — the rationale message in the assertion was broken without it. No scope creep.

## Issues Encountered

None beyond the Rule 1 auto-fix documented above.

## Known Stubs

None. The test file is pure source-text inspection with no placeholder text, no UI rendering, no hardcoded empty values.

## Threat Flags

None. Per the plan's threat model: zero runtime attack surface — the tests read two source files as text and assert a substring count. No new attack vectors.

## Wave 2 Contract Note

Both drift-guard tests are intentionally RED in this worktree (count == 0 because Plans 79-02 and 79-03 haven't landed yet). Per the plan objective: "The drift-guard tests will FAIL with `count == 0` until Plans 79-02 and 79-03 land; that's the intended Wave 2 contract — once 79-02 + 79-03 land, the drift-guard turns green automatically."

## Self-Check

### Files exist

- FOUND: tests/test_yt_dlp_opts_drift.py

### Commits exist

- FOUND: 6ded01c

## Self-Check: PASSED
