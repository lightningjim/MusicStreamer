---
phase: 60-gbs-fm-integration
plan: "08"
subsystem: gbs_api
tags: [phase60, gap-closure, urllib, redirect-handler, django-messages, idempotent-import, tdd]
requires: [60-02]
provides:
  - "fixed _NoRedirect override (http_error_302 returns fp, not raises)"
  - "import_station field-level dirty-check"
affects: [gbs_search_dialog, main_window]
requirements-completed: [GBS-01a, GBS-01e]
tech-stack-added: []
tech-stack-patterns:
  - "urllib.request.HTTPRedirectHandler.http_error_302 override (not redirect_request)"
  - "field-level tuple comparison before counting repo writes as updated"
key-files-created: []
key-files-modified:
  - musicstreamer/gbs_api.py
  - tests/test_gbs_api.py
decisions:
  - "Override http_error_302 (not redirect_request) per CPython urllib internals — redirect_request->None falls through to http_error_default which raises unconditionally"
  - "Alias http_error_301/303/307 to http_error_302 for belt-and-braces resilience"
  - "repo.update_stream called unconditionally in dirty-check path (SQLite WAL consistency); only return tuple changes"
  - "Compare (url, quality, position, codec, bitrate_kbps) — label/stream_type excluded as user-editable fields"
duration: "6 minutes"
completed: "2026-05-04"
tasks: 3
files: 2
---

# Phase 60 Plan 08: Fix 302 Messages + Import Dirty-Check Summary

**One-liner:** Override urllib's http_error_302 to return raw response (not raise) + add field-level dirty-check to import_station for correct (0,0)/(0,1) semantics.

## Accomplishments

- Closed UAT issue **T13** ("Submit Failed: HTTP Error 302: Found"): `_NoRedirect` now overrides `http_error_302` to return `fp` (the raw response file-object) directly, stopping the CPython urllib chain before `http_error_default` can raise. `submit()` now successfully reads `Location` and `Set-Cookie: messages` headers.
- Closed UAT issue **T6** (idempotent re-import always toasts "GBS.FM streams updated"): `import_station` now compares `(url, quality, position, codec, bitrate_kbps)` for each stream before counting the update path as changed. Returns `(0, 0)` when zero fields differ, `(0, 1)` when any field changed. The `else` branch in `_on_gbs_import_finished` (the "no changes" toast) is now reachable.
- Added 6 new regression tests and updated 1 existing test (24 total in `tests/test_gbs_api.py`).
- All 144 tests across `test_gbs_api.py`, `test_stream_ordering.py`, `test_now_playing_panel.py`, and `test_gbs_search_dialog.py` pass.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 + 1.5 | TDD-RED: failing regression tests + update test_import_idempotent | b20e911 | tests/test_gbs_api.py |
| 2a | TDD-GREEN: fix _NoRedirect http_error_302 override (T13) | 0a6aba9 | musicstreamer/gbs_api.py |
| 2b | TDD-GREEN: import_station field-level dirty-check (T6) | 9354fda | musicstreamer/gbs_api.py |

## Files Modified

| File | Change |
|------|--------|
| `musicstreamer/gbs_api.py` | `_NoRedirect` class: replaced `redirect_request` returning None with `http_error_302` returning `fp`; added 301/303/307 aliases. `import_station`: added `any_field_changed` dirty flag with field-tuple comparison before counting update as `updated=1`. |
| `tests/test_gbs_api.py` | Added imports (`http.client`, `os`, `urllib.request`); added `_make_fake_302_response` helper; added 6 new test functions; updated `test_import_idempotent` assertion from `(0, 1)` to `(0, 0)`. |

## Decisions Made

1. **http_error_302 not redirect_request**: CPython's `HTTPRedirectHandler.http_error_302` calls `self.redirect_request(...)` and if that returns `None`, returns `None` to `OpenerDirector.error`, which falls through to `HTTPDefaultErrorHandler.http_error_default` — the unconditional `raise HTTPError(code, ...)`. Overriding `redirect_request` cannot prevent this raise; overriding `http_error_302` can because it intercepts before the raise path.

2. **Alias 301/303/307**: Per diagnosis §6 Open Question 1, if gbs.fm ever sends a 301/303/307 instead of 302 for `/add/` responses, the override continues to work. Cost: none. Added as `http_error_301 = http_error_307 = http_error_303 = http_error_302`.

3. **repo.update_stream unconditional**: The dirty flag only changes the return tuple. `repo.update_stream` is still called for every existing stream to preserve SQLite WAL consistency. This matches T-60-08-04 threat mitigation in the plan.

4. **Label/stream_type excluded from dirty-check**: These fields may carry user edits or default values not tracked in the canonical tier list. Only the 5 canonical fields (`url`, `quality`, `position`, `codec`, `bitrate_kbps`) are compared.

## TDD Gate Compliance

- RED gate: commit `b20e911` — `test(60-08): add failing regression tests...` (5 tests failing, 19 passing)
- GREEN gate 1: commit `0a6aba9` — `fix(60-08): override http_error_302...` (T13 fix, 22 passing)
- GREEN gate 2: commit `9354fda` — `fix(60-08): import_station returns (0,0)...` (T6 fix, 24 passing)

## Deviations from Plan

### Notes on plan iteration

- Task 1.5 (update `test_import_idempotent` assertion `(0,1)` → `(0,0)`) was combined into the Task 1 RED commit as directed by revision 2 plan instructions. Both changes appear in commit `b20e911`.
- The test `test_submit_auth_expired_still_raises` was listed as "must-not-regress (currently passes)" in the plan, but it actually FAILED in the RED phase — the real `_open_no_redirect` path causes `HTTPError(302)` to be raised even for auth-expired locations because `http_error_default` fires before `submit()` can inspect `Location`. This is expected: the RED commit correctly captured that this test also needed the GREEN fix to pass. After the GREEN commit (`0a6aba9`), all 3 auth-related tests pass.

### Auto-fixed Issues

None. Plan executed exactly as written.

## Known Stubs

None. Both fixed behaviors (302 response capture and dirty-check return value) are fully wired. No placeholder data or TODO paths remain.

## Threat Flags

No new trust boundaries introduced. The `_NoRedirect.http_error_302` fix returns the same `fp` object that urllib would have passed to `http_error_default`; no new network endpoints or auth paths created.

## Self-Check

### Files exist:
- [x] `musicstreamer/gbs_api.py` — contains `http_error_302` and `any_field_changed`
- [x] `tests/test_gbs_api.py` — contains `_make_fake_302_response` and 6 new tests

### Commits exist:
- [x] b20e911 — RED commit
- [x] 0a6aba9 — GREEN commit 1 (T13)
- [x] 9354fda — GREEN commit 2 (T6)

### Test count: 24 tests in test_gbs_api.py (18 original → 17 untouched + 1 updated + 6 new)

## Self-Check: PASSED
