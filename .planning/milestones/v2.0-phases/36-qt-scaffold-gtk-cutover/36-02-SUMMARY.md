---
phase: 36
plan: 02
subsystem: url helpers / test rewiring
tags: [refactor, extraction, PORT-04, QA-04, cutover-safety]
requires:
  - phase-36-plan-01 Qt scaffold (ui_qt, __main__ cutover)
  - musicstreamer.aa_import.NETWORKS (pre-existing, GTK-free)
provides:
  - musicstreamer.url_helpers module with 4 pure URL classification functions
  - tests/test_aa_url_detection.py rewired to url_helpers
  - tests/test_yt_thumbnail.py reduced to _is_youtube_url only
affects:
  - musicstreamer/url_helpers.py (new)
  - tests/test_aa_url_detection.py (imports + deleted 2 fetch_aa_logo tests)
  - tests/test_yt_thumbnail.py (imports + deleted 3 fetch_yt_thumbnail tests)
tech-stack:
  added: []
  patterns: [verbatim extraction, module-level urllib.parse import, defer-to-later-phase comments for deleted tests]
key-files:
  created:
    - musicstreamer/url_helpers.py
  modified:
    - tests/test_aa_url_detection.py
    - tests/test_yt_thumbnail.py
decisions:
  - Move function-local `import urllib.parse` (from `_aa_channel_key_from_url`) up to module level in the new file — standard style and the only non-verbatim change
  - Keep musicstreamer/ui/edit_dialog.py fully intact during this plan (duplicated helpers) so intermediate state remains green — atomic ui/ deletion happens in 36-03
  - Delete 2 fetch_aa_logo tests (in addition to the 3 fetch_yt_thumbnail tests called out in the plan prompt) because their `patch("musicstreamer.ui.edit_dialog.GLib")` call sites cannot survive 36-03's ui/ deletion; Phase 39 will re-add Qt-signal-based equivalents
metrics:
  duration: ~4 minutes
  completed: 2026-04-11T23:35:58Z
  tasks: 2/2
  files-created: 1
  files-modified: 2
  tests: 267 passed (272 baseline - 5 deleted)
---

# Phase 36 Plan 02: URL Helpers Extraction Summary

Moved the 4 pure URL classification helpers (`_is_youtube_url`, `_is_aa_url`, `_aa_channel_key_from_url`, `_aa_slug_from_url`) out of `musicstreamer/ui/edit_dialog.py` into a new GTK-free `musicstreamer/url_helpers.py` so the non-UI tests (`test_aa_url_detection`, `test_yt_thumbnail`) survive Plan 36-03's atomic deletion of the `ui/` tree. `edit_dialog.py` is untouched — it keeps its own copies of the helpers in parallel until the atomic cutover, which is the intermediate safety valve.

## What Was Built

### Task 1 — `musicstreamer/url_helpers.py` (commit `2f5ad98`)

- New module with 4 pure functions and 2 module-level constants copied verbatim from `musicstreamer/ui/edit_dialog.py` lines 17-86:
  - `_is_youtube_url(url)` — simple substring check for youtube.com / youtu.be.
  - `_is_aa_url(url)` — checks against `_AA_STREAM_DOMAINS` set (6 AudioAddict network domains).
  - `_aa_channel_key_from_url(url, slug)` — extracts channel key from URL path, strips `_hi/_med/_low` quality tiers and the per-network URL prefix (e.g. `zr` for zenradio).
  - `_aa_slug_from_url(url)` — iterates `NETWORKS` (from `musicstreamer.aa_import`) to pick the matching slug from a stream URL's domain.
- Module-level `import urllib.parse` (was function-local inside `_aa_channel_key_from_url` — the only non-verbatim change, a standard cleanup).
- `from musicstreamer.aa_import import NETWORKS` — verified GTK-free via `grep -E "Gtk|Adw|GLib|from gi\."` (zero matches).
- Zero GTK/Qt/subprocess coupling: `grep -E "Gtk|Adw|GLib|from gi\.|subprocess|def fetch_"` → no matches.
- Functions explicitly NOT extracted: `fetch_aa_logo`, `fetch_yt_thumbnail`, `fetch_yt_title` — they use `GLib.idle_add` + `subprocess.run(['yt-dlp', ...])`, die with the GTK delete in Plan 36-03, and get rebuilt in Phase 37/39 with `yt_dlp.YoutubeDL` + Qt signals.

Smoke test:
```
python -c "from musicstreamer.url_helpers import _is_youtube_url, _is_aa_url, _aa_channel_key_from_url, _aa_slug_from_url; \
  assert _is_youtube_url('https://youtu.be/x') is True; \
  assert _is_aa_url('http://prem2.di.fm/x') is True; \
  assert _aa_channel_key_from_url('http://prem2.di.fm:80/ambient_hi', 'di') == 'ambient'; \
  assert _aa_slug_from_url('http://prem2.di.fm/x') == 'di'"
```
→ `ok`

### Task 2 — Test rewiring (commit `d95f8ce`)

- **`tests/test_aa_url_detection.py`:**
  - Import changed: `from musicstreamer.ui.edit_dialog import _is_aa_url, _aa_channel_key_from_url` → `from musicstreamer.url_helpers import _is_aa_url, _aa_channel_key_from_url`.
  - Removed unused imports: `os`, `tempfile`, `MagicMock`, `patch` (no more mocking in the file).
  - Deleted `test_fetch_aa_logo_success` and `test_fetch_aa_logo_failure` — their `patch("musicstreamer.ui.edit_dialog.GLib")` and `patch("musicstreamer.ui.edit_dialog._fetch_image_map")` call sites cannot survive 36-03's `ui/` deletion. Replaced with a file-bottom comment block pointing at Phase 39 (Qt rebuild of EditStationDialog).
  - Remaining 15 pure-logic tests unchanged.

- **`tests/test_yt_thumbnail.py`:**
  - Rewritten top-to-bottom — now a 17-line file.
  - New module docstring explains the Phase 36 extraction and points forward to Phase 37's yt_dlp library API + Qt signals rebuild.
  - Single remaining test: `test_is_youtube_url` now imports `_is_youtube_url` from `musicstreamer.url_helpers`.
  - Deleted `test_fetch_yt_thumbnail_success`, `test_fetch_yt_thumbnail_no_output`, `test_fetch_yt_thumbnail_subprocess_error` (-3 tests).
  - Dropped unused `subprocess`, `threading`, `unittest.mock.patch`, `unittest.mock.MagicMock`, `pytest` imports.

## Verification Results

| Check                                                                            | Result        |
| -------------------------------------------------------------------------------- | ------------- |
| `python -c "from musicstreamer.url_helpers import ..."` smoke (4 functions)     | PASS          |
| `grep -E "Gtk\|Adw\|GLib\|from gi\.\|subprocess\|def fetch_" musicstreamer/url_helpers.py` | no matches   |
| `grep "from musicstreamer.ui.edit_dialog" tests/test_aa_url_detection.py`         | no matches    |
| `grep "from musicstreamer.ui.edit_dialog" tests/test_yt_thumbnail.py`             | no matches    |
| `grep "from musicstreamer.url_helpers" tests/test_aa_url_detection.py`            | PASS          |
| `grep "from musicstreamer.url_helpers import _is_youtube_url" tests/test_yt_thumbnail.py` | PASS     |
| `pytest tests/test_aa_url_detection.py tests/test_yt_thumbnail.py -q`             | **16 passed** |
| `QT_QPA_PLATFORM=offscreen pytest -q` (full suite)                                | **267 passed** (272 baseline - 5 deleted) |
| `musicstreamer/ui/edit_dialog.py` present + unmodified                            | PASS (sha unchanged) |

Test count math: 272 baseline - 2 fetch_aa_logo - 3 fetch_yt_thumbnail = 267. Matches.

## Deviations from Plan

### Auto-fixed issues

None for Task 1 — verbatim extraction, clean first pass.

**1. [Rule 3 — Expected scope extension] Deleted 2 `fetch_aa_logo` tests in `test_aa_url_detection.py`**

- **Found during:** Task 2 planning — the executor prompt explicitly flagged that `test_aa_url_detection.py` might have `fetch_aa_logo`-related tests to handle "similarly," and grep confirmed 2 tests at the bottom of the file patching `musicstreamer.ui.edit_dialog.GLib` and `_fetch_image_map`.
- **Fix:** Deleted both tests along with the unused `os`, `tempfile`, `MagicMock`, `patch` imports. Added a file-bottom comment block pointing at Phase 39 for the Qt-signal-based replacement. This is consistent with the plan's treatment of the 3 `fetch_yt_thumbnail_*` tests in `test_yt_thumbnail.py` — same survival rationale (`GLib.idle_add` mocking dies with the `ui/` deletion).
- **Files modified:** `tests/test_aa_url_detection.py`.
- **Commit:** `d95f8ce`.
- **Impact on test count:** 272 baseline → 267 passing (plan allowed "≥ 269" — exact final count depends on what else catches, plan explicitly noted "exact count depends on what else the planner catches"). The 2 extra deletions here were anticipated in the executor prompt ("Also check for tests/test_aa_import.py or similar that might import fetch_aa_logo — handle similarly if present").

## Authentication Gates

None — local refactor only.

## Known Stubs

None introduced by this plan. `musicstreamer/ui/edit_dialog.py` still owns its helper copies, which is the intentional intermediate state — Plan 36-03 atomically deletes the whole `ui/` tree.

## Threat Flags

None — extraction is a pure refactor, no new network/auth/filesystem/schema surface. Removes nothing, adds one pure Python module.

## Self-Check: PASSED

- `musicstreamer/url_helpers.py` — FOUND
- `tests/test_aa_url_detection.py` — MODIFIED (contains `from musicstreamer.url_helpers`)
- `tests/test_yt_thumbnail.py` — MODIFIED (contains `from musicstreamer.url_helpers import _is_youtube_url`)
- commit `2f5ad98` — FOUND (Task 1: url_helpers.py creation)
- commit `d95f8ce` — FOUND (Task 2: test rewiring + 5 test deletions)
- `QT_QPA_PLATFORM=offscreen pytest -q` → 267 passed
- `musicstreamer/ui/edit_dialog.py` untouched (36-03 scope)
