---
phase: 89-youtube-channel-avatar-fetch-cover-slot-swap
plan: "02"
subsystem: yt_import
tags: [avatar-fetch, yt-dlp, registry, ART-AVATAR-03, D-04]
dependency_graph:
  requires: []
  provides: [fetch_channel_avatar, register_avatar_fetcher, get_avatar_fetcher, _AVATAR_FETCHERS]
  affects: [musicstreamer/yt_import.py, tests/test_yt_import_library.py]
tech_stack:
  added: [urllib.request (module-level import)]
  patterns: [cookie_utils.temp_cookies_copy, yt_dlp.YoutubeDL, two-step channel resolution, provider registry]
key_files:
  created: []
  modified:
    - musicstreamer/yt_import.py
    - tests/test_yt_import_library.py
decisions:
  - "Only avatar_uncropped has a stable named id in current yt-dlp (2026.3.17); avatar fallback branch is belt-and-suspenders for future versions"
  - "Null-safe square guard: reject only when BOTH width and height are present and unequal (None != None == False)"
  - "Two-step resolution: video URL extracts channel_url from info dict then re-fetches avatar from the channel"
  - "Provider registry lives in yt_import.py alongside fetch_channel_avatar; YouTube pre-registered at module load"
  - "Registry cleanup in test uses .copy()/.clear()/.update() to avoid test cross-contamination"
metrics:
  duration: 2m
  completed: "2026-06-16"
  tasks_completed: 2
  files_changed: 2
---

# Phase 89 Plan 02: fetch_channel_avatar + Per-Provider Registry Summary

One-liner: YouTube channel avatar fetch via yt-dlp avatar_uncropped filter with null-safe square guard, video-to-channel two-step resolution, and per-provider registry pre-registering YouTube (D-04).

## What Was Built

**Task 1: `fetch_channel_avatar(channel_url) -> bytes`** added to `musicstreamer/yt_import.py`:
- Builds yt-dlp opts identical to `scan_playlist` but WITHOUT `extract_flat` (Pitfall 3: extract_flat suppresses channel thumbnails)
- Wraps `yt_dlp.YoutubeDL` in `cookie_utils.temp_cookies_copy()` (T-89-05: prevents canonical cookies.txt mutation)
- Two-step resolution: if no `avatar_uncropped`/`avatar` thumbnail in first info dict, reads `channel_url` (fallback `uploader_url`) and re-extracts
- Thumbnail filter: `next(...id == 'avatar_uncropped'...)` preferred, `next(...id == 'avatar'...)` fallback
- Square guard: `if w is not None and h is not None and w != h: raise ValueError(...)` — null-safe (Pitfall 2)
- Downloads via `urllib.request.urlopen(url, timeout=10)` (T-89-06: 10s timeout bounds the download)

**Task 2: Per-provider registry (D-04)** added to `musicstreamer/yt_import.py`:
- `_AVATAR_FETCHERS: dict[str, Callable[[str], bytes]] = {}`
- `register_avatar_fetcher(provider, fetcher) -> None`
- `get_avatar_fetcher(provider) -> Optional[Callable[[str], bytes]]`
- YouTube pre-registered at module load: `register_avatar_fetcher("youtube", fetch_channel_avatar)`

## TDD Gate Compliance

- RED commit: `b4453d29` — 6 failing avatar field-filter tests
- GREEN commit: `7668fa16` — implementation; all 6 tests pass
- Task 2 tests added to same test file; registry was already implemented with Task 1 code (no separate RED needed — registry was intrinsically tested in Task 1's implementation commit)
- Final registry tests commit: `0ce4537f` — 10 total avatar tests passing

## Tests Added

Added to `tests/test_yt_import_library.py` under `-k avatar`:

| Test | ART-AVATAR | Covers |
|------|-----------|--------|
| `test_avatar_prefers_avatar_uncropped` | 03 | avatar_uncropped selected over numeric-id entries |
| `test_avatar_raises_when_no_avatar_entry` | 03 | ValueError on no avatar entry |
| `test_avatar_rejects_non_square_entry` | 03 | ValueError when width != height (both present) |
| `test_avatar_allows_none_dimensions` | 03 | None dims must NOT reject (Pitfall 2) |
| `test_avatar_opts_do_not_contain_extract_flat` | 03 | extract_flat guard (Pitfall 3) |
| `test_avatar_video_url_two_step_resolution` | 03 | video URL -> channel_url re-resolve |
| `test_avatar_registry_youtube_registered` | D-04 | youtube fetcher registered at import |
| `test_avatar_registry_twitch_absent_by_default` | D-04 | twitch slot empty this phase |
| `test_avatar_registry_register_and_retrieve` | D-04 | runtime register+retrieve (89b-ready) |
| `test_avatar_registry_unknown_provider_returns_none` | D-04 | unknown provider returns None |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Model Coverage

| Threat | Mitigation | Status |
|--------|------------|--------|
| T-89-04 (malformed avatar bytes) | Square-dimension filter rejects mismatched entries; QPixmap.isNull() validation deferred to Plan 04/05 render boundary | Partial (per plan) |
| T-89-05 (cookies file mutation) | `cookie_utils.temp_cookies_copy()` wrapper applied | Mitigated |
| T-89-06 (network hang) | `urllib.request.urlopen(url, timeout=10)` | Mitigated |

## Known Stubs

None — `fetch_channel_avatar` returns real bytes; registry is fully functional.

## Threat Flags

None — no new network endpoints or auth paths introduced beyond what the plan's threat model covers.

## Self-Check: PASSED

- `musicstreamer/yt_import.py` exists and contains `def fetch_channel_avatar`
- `musicstreamer/yt_import.py` contains `avatar_uncropped` and `register_avatar_fetcher("youtube"`
- `musicstreamer/yt_import.py` does NOT contain `extract_flat` in the avatar opts (only in scan_playlist)
- `tests/test_yt_import_library.py` contains 10 avatar tests, all passing
- Commits b4453d29, 7668fa16, 0ce4537f all exist in git log
