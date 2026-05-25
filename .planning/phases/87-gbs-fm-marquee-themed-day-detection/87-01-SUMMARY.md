---
phase: 87
plan: 01
status: complete
completed: 2026-05-25
requirements:
  - GBS-THEME-06
  - GBS-MARQ-06
  - GBS-MARQ-07
self_check: PASSED
---

# Plan 87-01 Summary — TIME-SENSITIVE Memorial Day Harvest + REQUIREMENTS/ROADMAP Edits

## What was built

### Task 1 — REQUIREMENTS.md + ROADMAP.md edits (D-07 / D-08)

- `.planning/REQUIREMENTS.md` GBS-MARQ-06 rewritten verbatim to cite `paths.gbs_cookies_path()` + `musicstreamer.gbs_api.load_auth_context()`; phantom `gbs_auth.py` / `QWebEngineProfile` framing removed.
- `.planning/ROADMAP.md` Phase 87 Success Criterion #4 rewritten to match the same cookies-jar reuse contract.
- Ban-list grep (`GBS_WEB_PROFILE_NAME|GBS_WEB_STORAGE_PATH|gbs_auth\.py`) returns empty across both files.
- Required-citation grep finds `paths.gbs_cookies_path` and `load_auth_context` in both files.

### Task 2 — Live fixture harvest (Memorial Day "da troops" window)

Captured three artifacts at 2026-05-25 ~13:45 local, with Phase 76 dev cookies (refreshed via `python -m musicstreamer.oauth_helper --mode gbs` immediately before harvest; `sessionid` valid through 2026-06-08, `csrftoken` through 2027-05-24).

| Artifact | Bytes | SHA-256 (full) | Source URL | Method |
|----------|-------|---------------|------------|--------|
| `tests/fixtures/gbs_themed_logos/2026-05-25_memorial-day_da-troops.png` | 7,458 | `bd2b83fbe2b4bfe9baf8237a8919494e10cc7cf42ad3c42b1fcd605942881be3` | https://gbs.fm/images/logo_3.png | cookies |
| `tests/fixtures/gbs_marquee/2026-05-25_homepage.html` | 41,300 | `f5f9c3fdaedf8b613b716d9a15629e771e073f99e39db82cf9aa27ec8ccd0d67` | https://gbs.fm/ | cookies |
| `tests/fixtures/gbs_marquee/2026-05-25_ajax_cold.json` | 6,949 | `71c3cbdba230f178f3d6eb5ab4e15defb58260cff34779eb5420107599e9d8e0` | https://gbs.fm/ajax?... | cookies |

Both `tests/fixtures/gbs_themed_logos/MANIFEST.md` and `tests/fixtures/gbs_marquee/MANIFEST.md` written per D-06 schema (filename, capture_date, sha256, theme_label/source_url, capture_method, provenance, notes).

## Critical research finding for Plan 87-02

**The marquee text lives in the homepage HTML, NOT in /ajax.** Pitfall #3's probability estimate (60% /ajax, 25% homepage) inverted on the live data. Plan 87-02 should:

1. Lock `MARQUEE_URL = "https://gbs.fm/"` (homepage HTML).
2. Use a `<p id="noticearea">` selector (BeautifulSoup `find(id="noticearea")` or regex).
3. Strip inner HTML (`<b>`, `<br>`, `<a>` tags) to plain text.
4. Drop the leading `GBS-FM: ` prefix.
5. Split on `|`, strip each segment, return first as the changeable announcement.

Today's first pipe-segment: `da troops*` (the trailing `*` correlates with `[*LATEST FAD]` marker further down the marquee — operator convention for "newest thing"; Phase 87 ignores the `*` semantically — the themed-day keyword set matches the substring `da troops`).

Today's full marquee text (extracted, HTML-stripped, first-pipe-segment-bolded):

> **da troops*** | Tune in to A Queerdo's Storytime hosted by Venomous at 4pm BST/10am CDT/8am PDT FRIDAY! | RIP Rob Base & Dick Parry & Dennis Locorriere | DO NOT UPLOAD AI GARBAGE LIKE THIS. WE WILL BAN IT AND NOT LIKE YOU. Please only upload human-created music, and also, please report any AI dongs you find. Hit us up on the Discord. [*LATEST FAD]

## Canonical-baseline coverage (D-04 status)

No `canonical-001.png` was harvested — the operator had no browser-cached non-themed `logo_3.png`, and the live URL today serves the themed asset. Plan 87-04's `GBS_LOGO_BASELINE_HASHES` ships with the themed entry only; canonical baseline accretes as the operator captures non-themed states post-Memorial-Day. Plan 87-06 creates the follow-up todo (`todos/2026-05-25-gbs-theme-hash-baseline-grow.md`) to track this.

## Decisions honored

- **D-01 (time-sensitive harvest)**: Captured today during the live Memorial Day window.
- **D-02 (inline-only, no spike split)**: Harvest executed as a Plan 87-01 task; no `/gsd:spike` ceremony.
- **D-04 (3+/5+ aspirational)**: Shipped with 1 themed entry; follow-up todo planned for Plan 87-06.
- **D-06 (fixture layout + MANIFEST schema)**: Both MANIFEST.md files match the schema.
- **D-07 / D-08 (REQUIREMENTS / ROADMAP rewrites)**: Done verbatim.
- **D-11 (anonymous fallback)**: Cookies were fresh; fallback path not exercised. Harvest script supports it for future re-runs.

## Self-Check: PASSED

- ban-list grep empty ✓
- required-citation grep present ✓
- 5 fixture files non-empty ✓
- SHA-256 reproducible from disk ✓
- MANIFEST schema present ✓
- Phase 76 dev cookies remain at 0o600, unchanged (harvest READS only) ✓

## Key files created

- `.planning/REQUIREMENTS.md` (edited)
- `.planning/ROADMAP.md` (edited)
- `tests/fixtures/gbs_themed_logos/2026-05-25_memorial-day_da-troops.png` (new)
- `tests/fixtures/gbs_themed_logos/MANIFEST.md` (new)
- `tests/fixtures/gbs_marquee/2026-05-25_homepage.html` (new)
- `tests/fixtures/gbs_marquee/2026-05-25_ajax_cold.json` (new)
- `tests/fixtures/gbs_marquee/MANIFEST.md` (new)

## Deviations from plan

None. Plan 87-01 executed as designed. The throwaway harvest script lived at `/tmp/87-01-harvest.py` and was not committed (per plan instructions).

## Hand-off for Plan 87-02

Parser-lock target is the homepage HTML, `<p id="noticearea">` element. See "Critical research finding" section above for the recommended `parse_marquee()` algorithm.
