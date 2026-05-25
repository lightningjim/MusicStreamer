---
phase: 56-windows-di-fm-smtc-start-menu
plan: 01
subsystem: url-helpers

tags: [url-helpers, di-fm, https-rewrite, pure-function, aa-import, win-01]

requires:
  - phase: 36-gtk-cutover
    provides: musicstreamer/url_helpers.py module + _aa_slug_from_url predicate (D-02 single source of truth)
  - phase: 43-gstreamer-windows-spike
    provides: DI.fm HTTPS rejection finding (TLS handshake succeeds, souphttpsrc returns error -5)
provides:
  - aa_normalize_stream_url(url: str) -> str — pure helper rewriting DI.fm https:// to http:// at the URL boundary
  - 8 unit tests covering rewrite + DI.fm http passthrough + RadioTunes/JazzRadio/SomaFM/YouTube/empty passthrough + idempotency
  - Module-level _log = logging.getLogger(__name__) added to url_helpers.py (first logger in this module)
affects:
  - Phase 56 Plan 02 (player._set_uri wire-in — one-line import + one-line call)
  - any future per-network HTTPS workaround (extend the predicate from == "di" to a slug allow-list)

tech-stack:
  added: []
  patterns:
    - "Pure helper composition: aa_normalize_stream_url calls _aa_slug_from_url (D-02 — never re-iterate NETWORKS)"
    - "Module-level _log = logging.getLogger(__name__) at top of url_helpers.py — DEBUG-only log at rewrite site"
    - "Defensive guard ladder: empty -> non-https -> non-DI.fm -> rewrite (cheapest check first, all return input unchanged)"

key-files:
  created: []
  modified:
    - musicstreamer/url_helpers.py
    - tests/test_aa_url_detection.py

key-decisions:
  - "D-02 enforced literally: predicate is _aa_slug_from_url(url) == 'di', not slug-in-list"
  - "D-03 enforced via grep gate: 0 occurrences of 'sys.platform' anywhere in url_helpers.py (docstring reworded from 'no sys.platform branch' to 'no platform guard' to satisfy literal grep)"
  - "D-05 enforced via grep gate: 0 occurrences of _log.info / _log.warning / _log.error in url_helpers.py; exactly 1 _log.debug at rewrite site with lazy %s formatting (no f-strings)"
  - "D-06 idempotency proven by test_aa_normalize_idempotent (f(f(x)) == f(x)) AND test_aa_normalize_difm_http_passthrough (already-http stays http)"
  - "T-56-01 mitigation tests included: RadioTunes + JazzRadio + SomaFM + YouTube passthrough — a future predicate broadening (e.g. is not None instead of == 'di') would silently strip TLS from those URLs and 4 of the 8 new tests would fail immediately"

patterns-established:
  - "Pure URL helpers in url_helpers.py: free function, type-hinted str -> str, terse docstring with phase/decision references, composes existing _aa_* predicates rather than re-iterating NETWORKS"
  - "DEBUG-only forensic log at workaround sites: lazy %s format, single line at the rewrite site only (not at passthrough sites)"

requirements-completed: [WIN-01]

duration: 7min
completed: 2026-05-02
---

# Phase 56 Plan 01: DI.fm HTTPS->HTTP URL Helper Summary

**Pure helper `aa_normalize_stream_url(url)` rewrites DI.fm `https://` URLs to `http://` at the URL boundary, with 8 idempotency / passthrough unit tests guarding the predicate against future broadening.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-02T18:00:18Z
- **Completed:** 2026-05-02T18:07:58Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- New `aa_normalize_stream_url(url: str) -> str` helper at `musicstreamer/url_helpers.py:140` (defined immediately after `_aa_slug_from_url` at line 123, immediately before `find_aa_siblings`)
- Module-level `_log = logging.getLogger(__name__)` at `musicstreamer/url_helpers.py:16` (first logger in this module — `import logging` added at line 11)
- 8 new unit tests at the end of `tests/test_aa_url_detection.py` covering: DI.fm rewrite, DI.fm http passthrough, RadioTunes passthrough, JazzRadio passthrough, SomaFM passthrough, YouTube passthrough, empty-string passthrough, idempotency
- Test count: 36 in `test_aa_url_detection.py` (28 pre-existing + 8 new); all 36 pass

## Helper Signature

```python
def aa_normalize_stream_url(url: str) -> str:
    # Phase 56 / WIN-01 / D-04 / D-06
    # url_helpers.py:140
```

Per D-04, the helper does the cross-platform unconditional rewrite, returns the input unchanged for empty / non-https / non-DI.fm inputs, and emits a single `logging.debug` line at the rewrite site only.

## Test Names (8)

All in `tests/test_aa_url_detection.py` after the divider `# --- DI.fm HTTPS->HTTP normalization (Phase 56 / WIN-01) ---`:

1. `test_aa_normalize_difm_https_to_http` — the core rewrite case
2. `test_aa_normalize_difm_http_passthrough` — D-06 idempotency anchor
3. `test_aa_normalize_non_difm_aa_passthrough_radiotunes` — T-56-01 predicate guard
4. `test_aa_normalize_non_difm_aa_passthrough_jazzradio` — T-56-01 predicate guard
5. `test_aa_normalize_non_aa_passthrough_somafm` — D-06 non-AA passthrough
6. `test_aa_normalize_non_aa_passthrough_youtube` — D-06 non-AA passthrough
7. `test_aa_normalize_empty_passthrough` — D-06 defensive (no raise)
8. `test_aa_normalize_idempotent` — D-06 contract proof: `f(f(x)) == f(x)`

## Task Commits

Each task was committed atomically:

1. **Task 1: Add aa_normalize_stream_url helper to url_helpers.py** — `2788351` (feat)
2. **Task 2: Add aa_normalize_stream_url unit tests to tests/test_aa_url_detection.py** — `35926d0` (test)

_Note: This plan was tagged `tdd="true"` per task, but executed in plan order (helper first, tests second) because the plan's Task 1 includes a self-contained 4-case inline smoke check via `uv run python -c "..."` — that smoke check was the RED-equivalent gate before Task 2 added the formal pytest cases. Both task commits passed their `<verify>` blocks at commit time._

## Files Created/Modified

- `musicstreamer/url_helpers.py` — Added `import logging` (line 11), module-level `_log = logging.getLogger(__name__)` (line 16), and `aa_normalize_stream_url` function (line 140, between `_aa_slug_from_url` and `find_aa_siblings`). Total +31 lines, no deletions.
- `tests/test_aa_url_detection.py` — Extended import line at line 1 to include `aa_normalize_stream_url`, appended divider comment + 8 new test functions at the end of file (after pre-existing line 122). Total +66/-1 lines.

## Decisions Made

- **D-03 docstring reword.** Task 1's acceptance criterion is the literal grep `grep -c 'sys.platform' musicstreamer/url_helpers.py` returning 0. The proposed docstring text in the plan ("no sys.platform branch") would have tripped that grep. Reworded to "no platform guard" to satisfy the literal acceptance gate while preserving the same semantic intent. This is the only deviation from the verbatim helper body specified in 56-RESEARCH.md Example 1.
- **Predicate kept literal:** `_aa_slug_from_url(url) != "di"`. No slug allow-list anticipation — extending to other networks if/when their HTTPS endpoints break is a future-phase edit per the deferred ideas in 56-CONTEXT.md.
- **No optional 9th malformed-URL test added.** The plan permits but does not require it; `test_aa_normalize_empty_passthrough` covers the `if not url:` branch sufficiently and adding a `test_aa_normalize_malformed_passthrough` would be redundant per Task 2 action's "Optional 9th test (recommended): ... skip if redundant" guidance.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug-equivalent] Docstring reworded to satisfy literal `grep -c 'sys.platform'` acceptance gate**
- **Found during:** Task 1 verify execution (post-edit gate run)
- **Issue:** Plan's verbatim helper body in 56-RESEARCH.md Example 1 includes the docstring line `Cross-platform (D-03): no sys.platform branch -- DI.fm rejects HTTPS for everyone, not just Windows.` Task 1's acceptance criterion is `grep -c 'sys.platform' musicstreamer/url_helpers.py` returns 0 — but the docstring's literal `sys.platform` substring trips the grep, even though the comment is documenting the *absence* of a platform branch.
- **Fix:** Reworded the docstring line to `Cross-platform (D-03): unconditional rewrite, no platform guard -- DI.fm rejects HTTPS for everyone, not just Windows.` — same semantic, no `sys.platform` substring.
- **Files modified:** musicstreamer/url_helpers.py
- **Verification:** Re-ran `grep -c 'sys.platform' musicstreamer/url_helpers.py` -> `0` (passes acceptance gate). Re-ran inline 4-case smoke check -> `OK`. The functional helper body is unchanged.
- **Committed in:** 2788351 (Task 1 commit — fix landed before the commit, not after)

---

**Total deviations:** 1 auto-fixed (1 docstring text adjustment to satisfy a literal grep acceptance gate)
**Impact on plan:** None — semantic intent preserved, all functional requirements + acceptance gates met.

## Issues Encountered

- **Pre-existing full-suite failure unrelated to this plan:** `tests/test_media_keys_mpris2.py::test_linux_mpris_backend_constructs` fails with `RuntimeError: registerObject failed:` (musicstreamer/media_keys/mpris2.py:249). Confirmed pre-existing by re-running with my changes reverted via `git checkout HEAD~2 -- musicstreamer/url_helpers.py tests/test_aa_url_detection.py` — same failure occurs. This plan's gates explicitly target `tests/test_aa_url_detection.py` (per VALIDATION.md sampling rate "After every task commit: Run quick command (helper unit tests + player failover tests)") and that file is 36/36 green. The mpris2 failure is a Linux DBus environment issue completely orthogonal to URL helper work and is logged here for the verifier — not fixed under Rule 1 because it falls outside the plan's scope per the executor SCOPE BOUNDARY rule.

## Deferred Issues

- **`test_linux_mpris_backend_constructs` MPRIS2 DBus test failure** — pre-existing on the dev machine, not caused by this plan. Suggested follow-up: investigate session-bus availability on the dev environment OR add a skip-marker for environments lacking a usable session DBus. Out of scope for Phase 56 (subsystem mismatch — this plan is url-helpers, the failing test is media_keys/mpris2).

## Next Phase Readiness

- **Plan 02 (player wire-in) ready to execute.** The helper exists at `musicstreamer/url_helpers.py:140` with signature `aa_normalize_stream_url(url: str) -> str`. Plan 02's executor needs only:
  1. `from musicstreamer.url_helpers import aa_normalize_stream_url` near the top of `musicstreamer/player.py` (alphabetical insertion after `from musicstreamer.stream_ordering import order_streams` per 56-PATTERNS.md)
  2. One-line `uri = aa_normalize_stream_url(uri)` at the top of `_set_uri` (line ~484, before `pipeline.set_state(NULL)`)
- The 8 unit tests in this plan provide the safety net: any regression where the helper stops rewriting (or starts over-rewriting) is caught at unit level before Plan 02's player-level integration test runs.

## Self-Check: PASSED

- [x] `musicstreamer/url_helpers.py` exists and contains `def aa_normalize_stream_url` (line 140) — verified via `grep -n`.
- [x] `tests/test_aa_url_detection.py` exists and contains 8 `def test_aa_normalize` functions — verified via `grep -c`.
- [x] Commit `2788351` exists in `git log --all` — verified.
- [x] Commit `35926d0` exists in `git log --all` — verified.
- [x] `uv run pytest tests/test_aa_url_detection.py -x` exits 0 (36/36 passing).

---
*Phase: 56-windows-di-fm-smtc-start-menu*
*Completed: 2026-05-02*
