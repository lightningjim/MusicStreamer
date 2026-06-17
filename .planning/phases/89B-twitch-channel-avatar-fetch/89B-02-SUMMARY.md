---
phase: 89B-twitch-channel-avatar-fetch
plan: "02"
subsystem: edit-station-dialog-twitch-wiring
tags: [twitch, avatar, registry-dispatch, provider-derivation, tdd]
dependency_graph:
  requires:
    - musicstreamer/twitch_helix.py (Plan 01 — fetch_channel_avatar + _parse_login)
    - musicstreamer/yt_import.py (get_avatar_fetcher registry)
    - musicstreamer/ui_qt/edit_station_dialog.py (_AvatarFetchWorker, _on_url_text_changed, _on_url_timer_timeout, _on_save)
  provides:
    - twitch.tv URL enables Refresh-avatar button (D-08)
    - _AvatarFetchWorker dispatches via registry to twitch fetcher (D-08)
    - blank-provider Twitch stations get "Twitch: <login>" provider on save (D-02/D-04)
  affects:
    - musicstreamer/ui_qt/edit_station_dialog.py
    - tests/test_edit_station_dialog_avatar.py
    - tests/test_twitch_provider_assign.py
tech_stack:
  added: []
  patterns:
    - URL-sniff registry dispatch (get_avatar_fetcher keyed by "twitch" or "youtube")
    - Single provider_id-None guard for combined YouTube+Twitch avatar URL gate (Pitfall 7)
    - Blank-provider guard before Twitch provider derivation (D-04 / Pitfall 3)
    - Late import of twitch_helix in _on_save (avoids module-level import; mirrors Plan 01 pattern)
key_files:
  created:
    - tests/test_edit_station_dialog_avatar.py
    - tests/test_twitch_provider_assign.py
  modified:
    - musicstreamer/ui_qt/edit_station_dialog.py
decisions:
  - "registry dispatch by URL sniff in run(): 'twitch.tv' in lower -> 'twitch', else 'youtube'"
  - "node_runtime passed only when provider_key == 'youtube' (Pitfall 1 compliance)"
  - "is_avatar_url gate in _on_url_timer_timeout: single combined boolean for YouTube+Twitch; single provider_id-None guard (Pitfall 7)"
  - "source-grep drift-guard uses f-string form 'f\"Twitch: ' to avoid matching comments"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-17"
  tasks_completed: 3
  files_created: 2
  files_modified: 1
---

# Phase 89B Plan 02: Twitch Dialog Wiring Summary

**One-liner:** Wired Twitch URL detection + registry dispatch into EditStationDialog: twitch.tv enables Refresh, `_AvatarFetchWorker` dispatches to the Twitch fetcher, and blank-provider stations get a `"Twitch: <login>"` provider on save.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wave 0 RED tests for dispatch + provider derivation | be48e1fb | tests/test_edit_station_dialog_avatar.py, tests/test_twitch_provider_assign.py |
| 2 | Twitch URL detection + registry dispatch in _AvatarFetchWorker | 580292fe | musicstreamer/ui_qt/edit_station_dialog.py |
| 3 | Login→provider derivation on save (blank-only) | d6fb0d14 | musicstreamer/ui_qt/edit_station_dialog.py, tests/test_twitch_provider_assign.py |

## What Was Built

### musicstreamer/ui_qt/edit_station_dialog.py (modified, 3 sites)

**Site 1 — `_on_url_text_changed` (~L1274):**
- Added `is_twitch = "twitch.tv" in lower`
- Changed `setEnabled(is_yt)` to `setEnabled(is_yt or is_twitch)` (Pitfall 2 / D-08)

**Site 2 — `_on_url_timer_timeout` (~L1304):**
- Replaced the YouTube-only `if "youtube.com" in lower or "youtu.be" in lower:` gate with `is_avatar_url = ("youtube.com" in lower or "youtu.be" in lower or "twitch.tv" in lower)` and `if is_avatar_url:`
- The provider_id-None guard (Pitfall 7 / CR-01) and reuse-on-open skip (D-07) now apply once for both YouTube and Twitch — not duplicated
- Worker launch unchanged (it already passes url/token/station_id/provider_id/node_runtime)

**Site 3 — `_AvatarFetchWorker.run()` (~L169):**
- Replaced hard-coded `yt_import.fetch_channel_avatar(self._url, node_runtime=...)` with registry dispatch
- URL sniff: `"twitch.tv" in lower` → `provider_key = "twitch"`, else `"youtube"`
- `fetcher = yt_import.get_avatar_fetcher(provider_key)` — raises ValueError if None
- `node_runtime` passed only on the YouTube path (Pitfall 1 / D-08)
- WR-04 `except Exception: self.finished.emit("", token)` backstop preserved

**Site 4 — `_on_save` (~L1693):**
- Before `ensure_provider(provider_name)`, added blank-provider + twitch.tv gate
- `if not provider_name:` → `if "twitch.tv" in url.lower():` → `twitch_helix._parse_login(url)` → `provider_name = f"Twitch: {_login}"` when login is non-empty
- D-04 / Pitfall 3 compliance: `not provider_name` gate ensures manual providers are never overwritten
- Reuses `twitch_helix._parse_login` — no duplicated parse logic
- `ensure_provider(provider_name)` and `update_station(..., provider_id, ...)` unchanged

### tests/test_edit_station_dialog_avatar.py (new, 3 tests)

- `test_twitch_url_enables_refresh_btn` — verifies twitch.tv enables Refresh; YouTube also enables; unrelated URL disables
- `test_avatar_worker_dispatches_twitch` — source-grep drift-guard asserts `get_avatar_fetcher` in `run()` source and `fetch_channel_avatar(self._url` NOT present; behavioral spy asserts `get_avatar_fetcher("twitch")` called, YouTube fetcher not called
- `test_youtube_dispatch_passes_node_runtime` — regression guard for Pitfall 1: YouTube path still forwards node_runtime

### tests/test_twitch_provider_assign.py (new, 4 tests)

- `test_save_source_has_twitch_derivation` — source-grep: f-string `f"Twitch: ` present; `not provider_name` guard appears before it in file
- `test_save_derives_provider_for_blank_twitch` — blank combo + twitch.tv/twitchdev → ensure_provider("Twitch: twitchdev")
- `test_save_preserves_manual_provider_for_twitch` — "Live Sports" + twitch.tv → ensure_provider("Live Sports"), NOT "Twitch: twitchdev"
- `test_save_non_twitch_url_unchanged` — blank combo + somafm URL → no Twitch derivation

## Verification

```
.venv/bin/python -m pytest tests/test_edit_station_dialog_avatar.py tests/test_twitch_provider_assign.py -q
→ 7 passed

.venv/bin/python -m pytest tests/test_twitch_helix.py tests/test_edit_station_dialog_avatar.py tests/test_twitch_provider_assign.py -q
→ 15 passed

git diff musicstreamer/cover_art.py musicstreamer/ui_qt/now_playing_panel.py
→ (no output — files unmodified, D-11 honored)
```

Pre-existing failure: `test_avatar_fetch_worker_emit_shape` makes a live YouTube network call to @KEXP (not currently live); fails identically on the prior commit — out of scope and pre-existing per MEMORY.md.

## Security Compliance

| Threat | Status |
|--------|--------|
| T-89b-02 (Tampering — login→provider derivation) | MITIGATED — `_parse_login` strips `?`/`#`/path segments; derived login used only to build the `"Twitch: <login>"` provider NAME, never as filesystem path; file key is integer `provider_id` |
| T-89b-03 (Elevation / DoS — Qt-threading) | MITIGATED — `run()` touches no widgets and calls no QTimer; all results marshalled via queued `finished` Signal; WR-04 `except Exception` backstop preserved |
| T-89b-04 (Spoofing — D-04 provider-overwrite) | MITIGATED — `not provider_name` gate prevents Twitch derivation when field has content |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Source-grep drift-guard found comment before f-string**
- **Found during:** Task 3 GREEN verification
- **Issue:** `test_save_source_has_twitch_derivation` searched for `"Twitch: "` and found the comment `"Twitch: <login>" provider` at index 76987, BEFORE `not provider_name` at 77224; test failed even though code was correct
- **Fix:** Changed drift-guard to search for the f-string form `f"Twitch: ` (which only matches code, not comments)
- **Files modified:** tests/test_twitch_provider_assign.py
- **Commit:** d6fb0d14

## Known Stubs

None — all dispatch and derivation logic is fully wired; the test suite covers all acceptance criteria paths.

## Threat Flags

No new security-relevant surface beyond the plan's threat model.

## Self-Check: PASSED
