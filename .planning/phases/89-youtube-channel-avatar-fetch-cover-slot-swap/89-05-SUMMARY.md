---
phase: 89-youtube-channel-avatar-fetch-cover-slot-swap
plan: "05"
subsystem: ui-dialog
tags: [avatar-fetch, edit-station-dialog, qthread, debounce, stale-token, tdd, ART-AVATAR-05]
dependency_graph:
  requires: [89-01, 89-02]
  provides: [_AvatarFetchWorker, avatar-preview-row, debounce-auto-fetch, manual-refresh, stale-token-discard, non-blocking-failure]
  affects: [musicstreamer/ui_qt/edit_station_dialog.py, tests/test_edit_station_dialog.py]
tech_stack:
  added: []
  patterns: [QThread-worker-queued-signal, stale-token-monotonic, atomic-persist-main-thread, non-blocking-failure-inline-message]
key_files:
  created: []
  modified:
    - musicstreamer/ui_qt/edit_station_dialog.py
    - tests/test_edit_station_dialog.py
decisions:
  - "_AvatarFetchWorker.run() never touches widgets and never calls QTimer.singleShot (spike landmine); result marshalled exclusively via queued finished Signal"
  - "Avatar fetch token is separate from logo fetch token (_avatar_fetch_token vs _logo_fetch_token) so stale logo and stale avatar discards don't collide"
  - "Inline YT check ('youtube.com' in lower or 'youtu.be' in lower) used for Refresh button gating (D-10) — same pattern as existing _on_logo_fetched at L1288"
  - "repo.update_channel_avatar_path called on the main thread in _on_avatar_fetched slot (D-12) — SQLite write off-main-thread is unsafe"
  - "_on_refresh_avatar_clicked delegates to _on_url_timer_timeout (D-11: Refresh reuses identical async path)"
  - "Failure shows non-blocking inline message; column stays unwritten; Save always enabled (D-03/D-11)"
metrics:
  duration: "~22 min"
  completed: "2026-06-16"
  tasks_completed: 2
  files_changed: 2
---

# Phase 89 Plan 05: EditStationDialog Avatar Fetch Wiring Summary

**One-liner:** Avatar preview row + `_AvatarFetchWorker` QThread wired to the 500ms URL debounce and manual Refresh button, with stale-token discard, atomic persist on the main thread, and non-blocking failure handling — satisfying ART-AVATAR-05 (D-01/D-02/D-03/D-10/D-11/D-12).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests: avatar widgets + worker shape + shutdown | ecd96615 | tests/test_edit_station_dialog.py (+168 lines, 8 tests) |
| 1 (GREEN) | Avatar preview row, _AvatarFetchWorker, YT-gated Refresh | 5cf6ead8 | musicstreamer/ui_qt/edit_station_dialog.py (+133 lines) |
| 2 (RED) | Failing tests: debounce launch + stale-token + failure + Refresh path | 9a92b252 | tests/test_edit_station_dialog.py (+136 lines, 6 tests) |
| 2 (GREEN) | Wire debounce auto-fetch + _on_avatar_fetched with stale-token | 0762702e | musicstreamer/ui_qt/edit_station_dialog.py (+56 lines) |

## What Was Built

### Task 1: Avatar UI row + _AvatarFetchWorker + YT gating

**`_AvatarFetchWorker(QThread)`** added immediately before `_PlaylistFetchWorker`:
- `finished = Signal(str, int)` — emits `(rel_path_or_empty, token)`
- `run()`: calls `yt_import.fetch_channel_avatar(url)` → `assets.write_channel_avatar(station_id, data)` → emits `(rel_path, token)` on success; emits `("", token)` on any exception (WR-04: never re-raises; never touches widgets; no `QTimer.singleShot`)

**Avatar UI row** inserted after `cover_art_source_combo` in `_build_ui()`:
- `self._avatar_preview`: `QLabel`, fixed 64×64, `AlignCenter`
- `self._avatar_status`: `QLabel("")`
- `self._refresh_avatar_btn`: `QPushButton("Refresh avatar")`, initially disabled (D-10)
- Laid out in `QHBoxLayout` inside a `QWidget` container, added via `form.addRow("Channel avatar:", ...)`

**State variables** alongside existing logo/pls tokens:
- `self._avatar_fetch_worker: Optional[_AvatarFetchWorker] = None`
- `self._avatar_fetch_token: int = 0`

**YouTube URL gating** in `_on_url_text_changed`:
- Inline check: `"youtube.com" in lower or "youtu.be" in lower`
- `_refresh_avatar_btn.setEnabled(is_yt)` on every URL change

**Helper methods added**:
- `_refresh_avatar_preview()`: loads `station.channel_avatar_path` PNG into 64×64 label (main thread only; square preview — no circular crop needed in dialog)
- `_on_refresh_avatar_clicked()`: stops `_url_timer`, calls `_on_url_timer_timeout()` (D-11 same path)
- `_shutdown_avatar_fetch_worker()`: disconnects + `wait(2000)`; called from `accept()`, `closeEvent()`, and `reject()`

### Task 2: Debounce auto-fetch + _on_avatar_fetched + stale-token

**`_on_url_timer_timeout` extended** (after existing logo fetch launch):
- YouTube inline check gates avatar branch
- Increments `_avatar_fetch_token`, sets `_avatar_status` to `"Fetching avatar…"`
- Creates and starts `_AvatarFetchWorker(url, token, station_id, self)` connected to `_on_avatar_fetched`

**`_on_avatar_fetched(rel_path, token)`** slot:
- Stale-token guard: `if token != self._avatar_fetch_token: return` (T-89-14)
- Failure branch (`rel_path == ""`): sets `_avatar_status` to D-03 non-blocking message; no DB write; Save stays enabled
- Success branch: `self._station.channel_avatar_path = rel_path` (in-memory update) → `_refresh_avatar_preview()` → `_avatar_status.setText("Avatar found")` → `self._repo.update_channel_avatar_path(station_id, rel_path)` on the main thread (SQLite thread safety / D-12)
- WR-04: `try/except Exception` wraps the success branch; never raises out of slot

## Verification

```
tests/test_edit_station_dialog.py -k avatar
  12 passed, 83 deselected
  
  Task 1 tests (8): widgets present, token init, refresh button gated by URL (non-YT,
  youtube.com, youtu.be), worker emit shape (success path), worker failure emits empty,
  shutdown no crash

  Task 2 tests (6): debounce launches worker on YT URL, non-YT skips avatar launch,
  success updates preview + persists, failure non-blocking (no persist + Save enabled),
  stale token discarded, Refresh reuses same path
```

## TDD Gate Compliance

Task 1:
- RED commit: `ecd96615` — 8 failing avatar tests
- GREEN commit: `5cf6ead8` — all 8 pass

Task 2:
- RED commit: `9a92b252` — 6 failing debounce/stale-token tests (8 Task 1 still green)
- GREEN commit: `0762702e` — all 12 pass

Both tasks satisfy RED→GREEN gate sequence.

## Deviations from Plan

None — plan executed exactly as written. The `_AvatarFetchWorker` imports `yt_import` and `assets` inside `run()` (lazy import) to match the codebase style and to avoid pulling those modules into the worker's constructor context. The `_on_avatar_fetched` slot wraps the success body in `try/except Exception` (WR-04 contract per plan's STRIDE register T-89-13).

## Threat Model Coverage

| Threat | Mitigation | Status |
|--------|------------|--------|
| T-89-13 (DoS: worker raising/touching widgets off-thread) | run() never re-raises; never touches widgets; no QTimer.singleShot; result via queued Signal only | Mitigated |
| T-89-14 (Tampering: stale avatar from superseded fast-typing) | _on_avatar_fetched: token != _avatar_fetch_token → immediate return | Mitigated |
| T-89-15 (DoS: fetch failure blocking edit flow) | Empty rel_path → non-blocking status message only; column unwritten; Save always enabled | Mitigated |

## Known Stubs

None — the avatar fetch is fully wired end-to-end:
- Worker calls `yt_import.fetch_channel_avatar` (real implementation from Plan 02)
- Persists via `assets.write_channel_avatar` (real atomic writer from Plan 01)
- DB write via `repo.update_channel_avatar_path` (real method from Plan 01)
- Preview loads from real PNG path via `_refresh_avatar_preview`

## Threat Flags

None — no new network endpoints or auth paths beyond what the plan's threat model covers. The avatar fetch uses the same `yt_import.fetch_channel_avatar` network path already assessed in Plan 02.

## Self-Check

Files modified:
- musicstreamer/ui_qt/edit_station_dialog.py — FOUND
- tests/test_edit_station_dialog.py — FOUND

Commits:
- ecd96615 — test(89-05): add failing avatar tests for widget/worker/shutdown (RED)
- 5cf6ead8 — feat(89-05): add avatar preview row, _AvatarFetchWorker, YT-gated Refresh (GREEN)
- 9a92b252 — test(89-05): add failing tests for debounce auto-fetch + stale-token + failure (RED)
- 0762702e — feat(89-05): wire debounce auto-fetch + _on_avatar_fetched with stale-token (GREEN)

## Self-Check: PASSED
