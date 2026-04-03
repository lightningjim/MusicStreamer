---
phase: 17-audioaddict-station-art
plan: "02"
subsystem: edit_dialog, aa_import
tags: [audioaddict, station-art, url-detection, api-key-popover, editor, tdd]
dependency_graph:
  requires: [17-01]
  provides: [ART-02-editor-aa-fetch]
  affects: [musicstreamer/ui/edit_dialog.py, tests/test_aa_url_detection.py]
tech_stack:
  added: [urllib.parse for path extraction]
  patterns: [daemon thread + GLib.idle_add for AA logo fetch, Gtk.Popover for API key entry]
key_files:
  created:
    - tests/test_aa_url_detection.py
  modified:
    - musicstreamer/ui/edit_dialog.py
decisions:
  - "_aa_channel_key_from_url uses urllib.parse.urlparse (not regex) to correctly reject domain-only URLs with no path"
  - "fetch_aa_logo reuses _on_thumbnail_fetched callback — identical copy/refresh flow as YouTube thumbnail"
  - "_aa_key_popover.unparent() on close-request avoids GTK reference warnings when dialog destroyed mid-state"
  - "_aa_channel_key_from_url strips network slug prefix (e.g. 'di_house' -> 'house') — stream URL paths are slug-prefixed but AA API keys images by bare channel name"
requirements-completed: [ART-02]
metrics:
  duration_seconds: 2100
  completed_date: "2026-04-03"
  tasks_completed: 2
  files_modified: 2
---

# Phase 17 Plan 02: AudioAddict URL Detection and Editor Logo Fetch Summary

**AA URL detection for all 6 network domains wired into station editor with daemon-thread logo fetch and API key popover; slug-prefix bug fixed during verification, 153 tests passing**

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Tests + AA URL helpers + fetch_aa_logo + editor wiring + API key popover | 436862a | musicstreamer/ui/edit_dialog.py, tests/test_aa_url_detection.py |
| fix | Strip slug prefix from channel key in _aa_channel_key_from_url | 84742f5 | musicstreamer/ui/edit_dialog.py |
| 2 | Visual verification of AA logo import and editor fetch | — | Checkpoint approved |

## What Was Built

**musicstreamer/ui/edit_dialog.py:**
- `_AA_STREAM_DOMAINS` — set of 6 AA base domain strings for fast membership check
- `_is_aa_url(url)` — returns True if any AA domain present in lowercased URL
- `_aa_channel_key_from_url(url)` — uses `urllib.parse.urlparse` to extract first path segment; returns None for domain-only URLs
- `_aa_slug_from_url(url)` — maps domain back to NETWORKS slug (e.g. `di.fm` → `"di"`)
- `fetch_aa_logo(slug, channel_key, callback)` — daemon thread: calls `_fetch_image_map`, downloads CDN image to tempfile, calls `callback(temp_path)` via `GLib.idle_add`; `callback(None)` on any failure
- `_on_url_focus_out` extended — AA branch checks stored `audioaddict_listen_key`, auto-fetches if present
- `_on_fetch_clicked` extended — AA branch triggers fetch or pops API key popover
- `_start_aa_logo_fetch(url)` — extracts slug+channel_key, shows spinner, calls `fetch_aa_logo` with shared `_on_thumbnail_fetched` callback
- `_on_aa_key_confirmed` — saves key to `repo.set_setting`, triggers fetch
- API key popover (`Gtk.Popover`) anchored to fetch_btn with heading, body text, entry, and confirm button
- `_on_close_request` extended — calls `_aa_key_popover.unparent()` to avoid GTK warnings

**tests/test_aa_url_detection.py:**
- 8 `test_is_aa_url_*` tests covering all 6 domains + 2 false cases
- 4 `test_channel_key_extraction_*` tests covering query param URL, no-query URL, domain-only, empty string
- `test_fetch_aa_logo_success` — mocks GLib/`_fetch_image_map`/urlopen, verifies temp_path callback
- `test_fetch_aa_logo_failure` — mocks empty image map, verifies None callback

## Test Coverage

14 new tests; full suite: 153 passing after slug-prefix bug fix (up from 138 after Plan 01).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed _aa_channel_key_from_url matching domain as path segment**
- **Found during:** Task 1 GREEN phase
- **Issue:** Initial regex `r'/([^/?]+)(?:\?|$)'` matched `di.fm` from `http://di.fm` (the `/` before the domain in `http://di.fm` triggered the pattern). Test `test_channel_key_extraction_no_path` expected `None`.
- **Fix:** Replaced regex with `urllib.parse.urlparse(url).path` — strips leading slash, returns None if path is empty after stripping.
- **Files modified:** musicstreamer/ui/edit_dialog.py
- **Commit:** 436862a (included in task commit)

**2. [Rule 1 - Bug] Fixed _aa_channel_key_from_url returning slug-prefixed key causing logo lookup failure**
- **Found during:** Task 2 visual verification
- **Issue:** Stream URLs at prem2.di.fm use paths like `/di_house` (network slug + channel name), but `_fetch_image_map` keys images by bare channel name `house`. Returned key `di_house` was not found in image map so no logos loaded.
- **Fix:** Added slug-stripping logic — detects network slug prefix in path segment and removes it before returning the key.
- **Files modified:** musicstreamer/ui/edit_dialog.py
- **Commit:** 84742f5

---

**Total deviations:** 2 auto-fixed (Rule 1 - bug x2)
**Impact on plan:** Both fixes essential for correctness. No scope creep.

## Known Stubs

None.

## Self-Check: PASSED

- musicstreamer/ui/edit_dialog.py contains `def _is_aa_url` — FOUND (line 29)
- musicstreamer/ui/edit_dialog.py contains `def _aa_channel_key_from_url` — FOUND (line 35)
- musicstreamer/ui/edit_dialog.py contains `def _aa_slug_from_url` — FOUND (line 53)
- musicstreamer/ui/edit_dialog.py contains `def fetch_aa_logo` — FOUND (line 67)
- musicstreamer/ui/edit_dialog.py contains `_aa_key_popover = Gtk.Popover()` — FOUND (line 262)
- musicstreamer/ui/edit_dialog.py contains `API Key Required` — FOUND (line 269)
- musicstreamer/ui/edit_dialog.py `_on_url_focus_out` contains `_is_aa_url` — FOUND (line 399)
- musicstreamer/ui/edit_dialog.py `_on_fetch_clicked` contains `_is_aa_url` — FOUND (line 409)
- musicstreamer/ui/edit_dialog.py contains `def _on_aa_key_confirmed` — FOUND (line 459)
- musicstreamer/ui/edit_dialog.py contains `audioaddict_listen_key` — FOUND (lines 401, 410, 463)
- tests/test_aa_url_detection.py contains `def test_is_aa_url` — FOUND
- tests/test_aa_url_detection.py contains `def test_channel_key_extraction` — FOUND
- tests/test_aa_url_detection.py contains `def test_fetch_aa_logo_success` — FOUND
- tests/test_aa_url_detection.py contains `def test_fetch_aa_logo_failure` — FOUND
- Commit 436862a — FOUND
