---
phase: 87-gbs-fm-marquee-themed-day-detection
plan: "02"
subsystem: gbs-marquee
tags:
  - gbs.fm
  - marquee
  - parser
  - fixtures
dependency_graph:
  requires:
    - 87-01 (harvest — homepage HTML + MANIFEST.md with noticearea selector)
  provides:
    - musicstreamer.gbs_marquee (parse_marquee, MARQUEE_URL, extract_noticearea_text)
    - tests/fixtures/gbs_marquee/ corpus (10 data files: 2 real + 8 synthetic)
  affects:
    - 87-03 (GbsMarqueeWorker wires fetch path into this module)
    - 87-06 (drift-guard greps for gbs_api + paths imports in gbs_marquee.py)
tech_stack:
  added: []
  patterns:
    - TDD (RED commit f896d122 → GREEN commit 795e1015)
    - Pure function parser (no Qt, no I/O) following aa_live.py precedent
    - HTML extraction via stdlib re (no BeautifulSoup dependency)
key_files:
  created:
    - musicstreamer/gbs_marquee.py
    - tests/test_gbs_marquee.py
    - tests/fixtures/gbs_marquee/synthetic-001.txt
    - tests/fixtures/gbs_marquee/synthetic-002.txt
    - tests/fixtures/gbs_marquee/synthetic-003.txt
    - tests/fixtures/gbs_marquee/synthetic-004.txt
    - tests/fixtures/gbs_marquee/synthetic-005.txt
    - tests/fixtures/gbs_marquee/synthetic-006.txt
    - tests/fixtures/gbs_marquee/synthetic-007.txt
    - tests/fixtures/gbs_marquee/synthetic-008.txt
  modified:
    - tests/fixtures/gbs_marquee/MANIFEST.md
decisions:
  - "MARQUEE_URL locked to https://gbs.fm/ (homepage HTML) per Plan 87-01 critical finding — /ajax stream does NOT carry themed-day text"
  - "parse_marquee operates on plain text (not raw HTML); HTML stripping done by extract_noticearea_text helper"
  - "8 synthetic fixtures (not 7) created to satisfy the strict >=10 fixture count test"
  - "extract_noticearea_text uses stdlib re — no BeautifulSoup dependency added"
metrics:
  duration: "~3 minutes"
  completed: "2026-06-15"
  tasks: 2
  files: 11
---

# Phase 87 Plan 02: Marquee Parser + Fixture Corpus Summary

## What Was Built

**parse_marquee skeleton + GBS-MARQ-07 fixture corpus satisfying the ≥ 10 sample requirement.**

### Task 1 — gbs_marquee.py skeleton (TDD)

`musicstreamer/gbs_marquee.py` created with:

- `MARQUEE_URL: str = f"{gbs_api.GBS_BASE}/"` — locked to the homepage HTML endpoint, confirmed by Plan 87-01 harvest dissection.
- `MARQUEE_DELIMITER: str = "|"` — canonical separator constant.
- `extract_noticearea_text(html: str) -> str` — extracts and HTML-strips the `<p id="noticearea">` element via stdlib `re`, drops the `GBS-FM:` prefix, collapses whitespace.
- `parse_marquee(raw_text: str) -> tuple[str, str]` — pure text parser implementing Pitfall #6's per-segment `.strip()`.  Returns `(first_segment, full_text)`.
- `from musicstreamer import gbs_api, paths` imports at module scope — drift-guard pre-flight for Plan 87-06's source-grep assertions.
- `GbsMarqueeWorker` placeholder comment at module bottom — Plan 87-03 fills the worker class.

`tests/test_gbs_marquee.py` written with 12 tests:
- 8 `parse_marquee` behavioural tests (empty, single-segment, pipe-split, bare-pipe, whitespace-padded, leading-empty, unicode, real Memorial Day specimen)
- 1 fixture-count test (`test_fixture_count_ten_or_more`)
- 2 MARQUEE_URL smoke tests
- 1 no-Qt-import purity test

TDD gates:
- RED commit `f896d122` — all 12 tests fail (module not yet created)
- GREEN commit `795e1015` — 8 parser tests pass; fixture-count pending Task 2

### Task 2 — Synthetic fixtures + MANIFEST.md extension

8 synthetic marquee `.txt` files added to `tests/fixtures/gbs_marquee/`:

| File | Scenario |
|------|----------|
| `synthetic-001.txt` | Single segment, no pipes |
| `synthetic-002.txt` | Bare-pipe delimiter, 2 segments |
| `synthetic-003.txt` | Space-padded delimiter, 3 segments |
| `synthetic-004.txt` | Internal punctuation + multi-pipe perpetuals |
| `synthetic-005.txt` | Unicode emoji in announcement (🎄) |
| `synthetic-006.txt` | Leading empty segment (leading-pipe edge case) |
| `synthetic-007.txt` | Leading/trailing whitespace, mixed delimiter spacing |
| `synthetic-008.txt` | 4-segment multi-pipe with unicode emoji (🍀) |

`MANIFEST.md` extended with `## Synthetic Samples (Pitfall #8 — parser robustness)` section containing a SHA-256–verified table for all 8 files.

Final fixture count: **10 data files** (2 real-captured + 8 synthetic).
`test_fixture_count_ten_or_more` passes (GBS-MARQ-07 satisfied).

## MARQUEE_URL Choice and Rationale

**Chosen value:** `https://gbs.fm/` (the homepage)

**Rationale:** Plan 87-01's harvest (2026-05-25 Memorial Day window) conclusively showed the marquee text in `<p id="noticearea">` inside the homepage HTML response.  The `/ajax` cold stream (`2026-05-25_ajax_cold.json`) contained no themed-day keywords.  Pitfall #3's prior probability estimate (60% /ajax, 25% homepage) was inverted by the live evidence.

**HTML selector:** `<p id="noticearea">` — extracted via `_NOTICEAREA_RE` regex in `extract_noticearea_text()`.

**Post-extraction algorithm:**
1. Strip HTML tags (`<b>`, `<br>`, `<a>`, etc.)
2. Collapse whitespace from block elements
3. Drop `GBS-FM:` prefix (`_GBS_FM_PREFIX_RE`)
4. Pass plain text to `parse_marquee()`

## Observed Delimiter

**Space-padded ` | ` ** (observed in the live 2026-05-25 harvest):
```
da troops* | Tune in to A Queerdo's Storytime hosted by Venomous at 4pm BST/10am CDT/8am PDT FRIDAY! | RIP Rob Base & Dick Parry & Dennis Locorriere
```

Per Pitfall #6, both bare `|` and space-padded ` | ` are handled uniformly by the per-segment `.strip()` in `parse_marquee()`.  Plan 87-04's keyword-search on `full_text` does not need to normalise the delimiter — it searches the raw `full_text` string for keyword substrings (case-insensitive).

## Open Questions for Plan 87-03

1. **Runtime fallback:** If `extract_noticearea_text(html)` returns `""` (site redesign or unexpected DOM change), Plan 87-03's worker should log `gbs.marquee.parse_empty` and consider probing the `/ajax` endpoint as a secondary candidate.  A `# TODO(87-03)` comment is in `MARQUEE_URL`'s docstring.

2. **Authenticated vs anonymous fetch:** The homepage may serve different `noticearea` content for authenticated vs anonymous requests.  Plan 87-01 captured the authenticated state (Phase 76 dev cookies).  Plan 87-03 should attempt cookies-first and fall back to anonymous if `load_auth_context()` returns `None`.

3. **Rate limiting:** The marquee worker (Plan 87-03) polls at a configured interval.  Session-scoped single-fetch (at GBS launch) is the current spec — but the worker should honour `gbs_api._TIMEOUT_READ` (10s) and `_TIMEOUT_WRITE` (15s) per the reuse contract.

## Deviations from Plan

**1. [Rule 2 - Missing critical functionality] Added test_parse_marquee_real_day_specimen**
- **Found during:** Task 1 implementation
- **Issue:** The plan's 8-test behavior block covered synthetic edge cases but not the actual real-world marquee text from the harvest.
- **Fix:** Added `test_parse_marquee_real_day_specimen` using the Memorial Day specimen from Plan 87-01 SUMMARY (HTML-stripped version).
- **Files modified:** `tests/test_gbs_marquee.py`
- **Commit:** `f896d122` (RED commit)

**2. [Rule 2 - Missing functionality] 8 synthetic fixtures instead of 7**
- **Found during:** Task 2 implementation
- **Issue:** The plan's MANIFEST.md noted that 2 real + 7 synthetic = 9, and "if the literal 10+ is enforced strictly at verification time, Plan 87-02 commits an 8th synthetic." The test enforces `>= 10` strictly.
- **Fix:** Created `synthetic-008.txt` (4-segment line with 🍀 emoji, multi-pipe + unicode).
- **Files modified:** `tests/fixtures/gbs_marquee/synthetic-008.txt`, `MANIFEST.md`
- **Commit:** `76450b89`

**3. [Rule 2 - Missing functionality] Added extract_noticearea_text helper**
- **Found during:** Task 1 implementation
- **Issue:** The plan specified a pure `parse_marquee(raw_text)` function but the worker (Plan 87-03) needs the HTML-stripping logic to bridge from raw homepage bytes to plain text. Providing it here avoids Plan 87-03 needing to inline the regex.
- **Fix:** Added `extract_noticearea_text(html: str) -> str` using stdlib `re` (no new dependencies).
- **Files modified:** `musicstreamer/gbs_marquee.py`
- **Commit:** `795e1015`

## Known Stubs

None. `parse_marquee` is a fully implemented pure function. `MARQUEE_URL` is locked. `GbsMarqueeWorker` is intentionally deferred to Plan 87-03 (placeholder comment present).

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes were introduced. `musicstreamer/gbs_marquee.py` makes no I/O calls — all I/O is deferred to Plan 87-03's worker. T-87-02-04 (synthetic fixtures misidentified as real) mitigated by `provenance = synthetic` column in MANIFEST.md and `synthetic-` filename prefix.

## Self-Check: PASSED

- `test -f musicstreamer/gbs_marquee.py` — FOUND
- `test -f tests/test_gbs_marquee.py` — FOUND
- `ls tests/fixtures/gbs_marquee/synthetic-*.txt | wc -l` — 8
- `uv run --with pytest pytest tests/test_gbs_marquee.py -v` — 12/12 passed
- `grep "from musicstreamer import" musicstreamer/gbs_marquee.py` — includes `gbs_api` and `paths`
- `grep -E "QWebEngineProfile|GBS_WEB_PROFILE_NAME|..." musicstreamer/gbs_marquee.py` — 0 hits
- `grep -c "^MARQUEE_URL" musicstreamer/gbs_marquee.py` — 1
- RED commit `f896d122` — exists in git log
- GREEN commit `795e1015` — exists in git log
- Task 2 commit `76450b89` — exists in git log
