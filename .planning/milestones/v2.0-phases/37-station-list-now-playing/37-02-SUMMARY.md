---
phase: 37
plan: 02
subsystem: ui_qt
tags: [qt, widget, now-playing, cover-art, volume, ui-14]
requires:
  - musicstreamer.player.Player.title_changed
  - musicstreamer.player.Player.elapsed_updated
  - musicstreamer.player.Player.set_volume
  - musicstreamer.player.Player.stop
  - musicstreamer.player.Player.pause
  - musicstreamer.player.Player.play
  - musicstreamer.cover_art.fetch_cover_art
  - musicstreamer.cover_art.is_junk_title
  - musicstreamer.repo.Repo.get_setting
  - musicstreamer.repo.Repo.set_setting
  - musicstreamer.models.Station
provides:
  - musicstreamer.ui_qt.now_playing_panel.NowPlayingPanel
  - musicstreamer.ui_qt.now_playing_panel.NowPlayingPanel.cover_art_ready
  - musicstreamer.ui_qt.now_playing_panel.NowPlayingPanel.on_title_changed
  - musicstreamer.ui_qt.now_playing_panel.NowPlayingPanel.on_elapsed_updated
  - musicstreamer.ui_qt.now_playing_panel.NowPlayingPanel.on_playing_state_changed
  - musicstreamer.ui_qt.now_playing_panel.NowPlayingPanel.bind_station
  - ":/icons/media-playback-start-symbolic.svg"
  - ":/icons/media-playback-pause-symbolic.svg"
  - ":/icons/media-playback-stop-symbolic.svg"
affects:
  - musicstreamer/ui_qt/icons.qrc
  - musicstreamer/ui_qt/icons_rc.py
  - musicstreamer/ui_qt/icons/NOTICE.md
tech-stack:
  added: []
  patterns:
    - QHBoxLayout three-column now-playing (180 logo | stretch center | 160 cover)
    - Cover-art worker thread → Qt Signal + Qt.ConnectionType.QueuedConnection adapter
    - QSlider valueChanged (live) / sliderReleased (persist) split for volume
    - QPixmap.scaled KeepAspectRatio letterbox inside fixed QLabel slot (UI-14)
    - Qt.PlainText lockdown on untrusted ICY metadata labels
    - Bound-method signal slots (no self-capturing lambdas — QA-05)
key-files:
  created:
    - musicstreamer/ui_qt/now_playing_panel.py
    - musicstreamer/ui_qt/icons/media-playback-start-symbolic.svg
    - musicstreamer/ui_qt/icons/media-playback-pause-symbolic.svg
    - musicstreamer/ui_qt/icons/media-playback-stop-symbolic.svg
    - tests/test_now_playing_panel.py
  modified:
    - musicstreamer/ui_qt/icons.qrc
    - musicstreamer/ui_qt/icons_rc.py
    - musicstreamer/ui_qt/icons/NOTICE.md
decisions:
  - "Volume persistence fires on sliderReleased only — live valueChanged updates player volume + tooltip but does not write to repo (avoids SQLite spam during drag). Keyboard-only adjustments persist on the next release; acceptable per RESEARCH §6."
  - "Cover-art worker callback captures a bound reference to self.cover_art_ready.emit (not self) so the nested _cb closure never captures the panel widget — satisfies QA-05 without blocking the adapter pattern."
  - "Station logo fallback uses :/icons/audio-x-generic-symbolic.svg (Plan 37-01 asset) when station.station_art_path is None or fails to load — applied uniformly to both the 180x180 logo slot and the 160x160 cover slot."
metrics:
  completed: 2026-04-11
  duration: ~12min
  tasks: 2
  files_created: 5
  files_modified: 3
  tests_added: 19
  tests_total: 303
requirements: [UI-02, UI-14]
---

# Phase 37 Plan 02: Now Playing Panel Summary

Built the right-panel `NowPlayingPanel(QWidget)` for the Qt main window: three-column horizontal layout, ICY + elapsed labels + play/pause/stop/volume control row, 160×160 cover-art slot with YouTube 16:9 letterbox handling (UI-14), volume persistence round-tripped through `Repo.get_setting` / `set_setting`, and the cover-art worker-thread → Qt signal adapter using `Qt.ConnectionType.QueuedConnection`. Ships the three Adwaita `media-playback-*-symbolic` icons via `icons.qrc`. Neither `player.py` nor `cover_art.py` were modified — both consumed as-is.

## What Shipped

### NowPlayingPanel (`musicstreamer/ui_qt/now_playing_panel.py`)

Layout per UI-SPEC Layout Contracts:

```
QHBoxLayout (margins 16, spacing 24)
├── logo_label (QLabel 180x180 fixed)
├── center QVBoxLayout (spacing 8, AlignVCenter)
│   ├── name_provider_label (QLabel, 9pt Normal, PlainText)
│   ├── icy_label (QLabel, 13pt DemiBold, PlainText — locked against rich-text injection)
│   ├── elapsed_label (QLabel, 10pt Normal, TypeWriter style hint for tabular digits)
│   └── control row QHBoxLayout (spacing 8)
│       ├── play_pause_btn (QToolButton 36x36, 24px icon, tooltip "Play"/"Pause")
│       ├── stop_btn (QToolButton 36x36 — clicks call player.stop directly)
│       ├── volume_slider (QSlider horizontal 120px wide, range 0-100)
│       └── addStretch(1)
└── cover_label (QLabel 160x160 fixed)
```

Plan-38 star button and Plan-39 edit button + stream picker slots are marked with inline comments only — no placeholder widgets per D-07.

### Public API (slots wired by Plan 37-04)

| Method | Source Signal / Trigger |
|--------|--------------------------|
| `bind_station(Station)` | MainWindow when user activates a station |
| `on_title_changed(str)` | `Player.title_changed` |
| `on_elapsed_updated(int)` | `Player.elapsed_updated` |
| `on_playing_state_changed(bool)` | MainWindow after play/pause/stop |
| `cover_art_ready = Signal(str)` | Self-emitted from cover_art worker thread |

### Volume Persistence (RESEARCH §6, D-08)

- Initial value: `int(repo.get_setting("volume", "80"))` wrapped in `try/except (TypeError, ValueError)` → defaults to 80 on bad/missing values.
- `valueChanged` → `_on_volume_changed_live` → `player.set_volume(value/100.0)` + tooltip update.
- `sliderReleased` → `_on_volume_released` → `repo.set_setting("volume", str(value))`.

### Cover Art Adapter (RESEARCH §5, D-19)

Nested closure in `_fetch_cover_art_async` captures **only** `self.cover_art_ready.emit` (the bound `Signal.emit`), never `self` — passes QA-05 lifetime check while still letting the cover_art worker thread marshal results onto the main thread via a queued connection. `is_junk_title` guard + `_last_cover_icy` dedup ports v1.5 behavior.

### UI-14 Letterbox Proof

`_set_cover_pixmap` scales via `QPixmap.scaled(QSize(160,160), Qt.KeepAspectRatio, Qt.SmoothTransformation)`. For a 16:9 source (320×180) the returned pixmap is 160×90 **and** `cover_label.size()` stays exactly 160×160 — both asserted in `test_youtube_thumbnail_letterbox`.

### Assets

Three verbatim Adwaita symbolic icons added to `musicstreamer/ui_qt/icons/`:

- `media-playback-start-symbolic.svg`
- `media-playback-pause-symbolic.svg`
- `media-playback-stop-symbolic.svg`

`icons.qrc` updated with matching `<file alias=...>` entries, `icons_rc.py` regenerated via `pyside6-rcc`, `NOTICE.md` attribution table extended.

### Tests (`tests/test_now_playing_panel.py` — 19 tests)

Uses `FakePlayer(QObject)` mirroring `Player`'s Signal surface (no GStreamer), and a `FakeRepo` dict. Covers:

1. `test_panel_construction` — minimumWidth 560, all widget fixed sizes
2. `test_icy_label_plaintext_format` — security lock-down
3. `test_volume_slider_initial_from_repo` — "65" → 65 + player.set_volume(0.65)
4. `test_volume_slider_default_when_unset` — no "volume" key → 80
5. `test_volume_slider_default_on_bad_value` — "abc" → 80 (try/except guard)
6. `test_volume_slider_persist_on_release` — sliderReleased writes to repo
7. `test_volume_slider_live_updates_player` — valueChanged drives set_volume + tooltip
8. `test_icy_title_update` — on_title_changed → icy_label.text()
9. `test_elapsed_format_mm_ss` — 125 → "2:05"
10. `test_elapsed_format_zero_pads_seconds` — 7 → "0:07"
11. `test_elapsed_format_hh_mm_ss` — 3725 → "1:02:05"
12. `test_play_pause_icon_toggle` — tooltip toggles Play ↔ Pause
13. `test_stop_button_calls_player_stop` — via FakePlayer.stop_called
14. `test_name_provider_separator_u00b7` — "Drone Zone · SomaFM" with U+00B7
15. `test_bind_station_no_provider` — provider=None → just the name
16. `test_cover_art_signal_adapter` — real file → pixmap loaded
17. `test_cover_art_ready_signal_missing_path_falls_back` — empty path → no crash, slot size unchanged
18. `test_youtube_thumbnail_letterbox` — **UI-14 proof**: 320×180 → `pixmap == 160×90` AND `label.size() == 160×160`
19. `test_new_icons_load` — three `:/icons/media-playback-*-symbolic.svg` resolve

Full suite: **303 passed** (284 baseline from 37-01 + 19 new), ignoring `tests/test_toast_overlay.py` which belongs to the parallel in-progress Plan 37-03 (Wave 2, not yet green).

## Commits

| Task | Message | Commit |
|------|---------|--------|
| 1 | feat(37-02): add media-playback Adwaita icons | `1b99d85` |
| 2 | feat(37-02): add NowPlayingPanel with 3-column layout, volume persistence, and cover art adapter | `68f9b00` |

## Deviations from Plan

None. Plan executed exactly as written. No auto-fixes, no auth gates, no scope changes, no skipped tasks.

One narrow interpretation note for QA-05: the nested `_cb` closure inside `_fetch_cover_art_async` captures `self.cover_art_ready.emit` (a bound `Signal.emit` method), not `self` directly, so there is no self-capturing closure. The plan's `grep 'lambda.*self'` gate is satisfied (no lambdas in the module at all).

## Deferred Issues

None.

## Threat Flags

None — this plan adds only read-only consumption of existing `Player` signals and `cover_art.fetch_cover_art` (pure Python). The one new network surface is `cover_art.fetch_cover_art` itself, which is **already** in use from the v1.5 GTK UI and is only re-wired here; no new endpoints introduced. Explicit `Qt.PlainText` lockdown on `icy_label` adds a defensive boundary against hostile ICY metadata strings being interpreted as rich text.

## Known Stubs

None. The panel is functionally complete for the Plan 37-04 integration — every widget, slot, and signal is live. `main_window.py` wiring is out of scope for 37-02 by design (D-18, 37-04 owns it).

## Integration Notes for Downstream Plans

- **Plan 37-04 (MainWindow integration):** Construct `NowPlayingPanel(player, repo, parent=self)`, then connect:
  - `player.title_changed` → `panel.on_title_changed`
  - `player.elapsed_updated` → `panel.on_elapsed_updated`
  - `station_panel.station_activated` → `MainWindow._on_station_activated` → `panel.bind_station(station)` + `player.play(station)` + `panel.on_playing_state_changed(True)`
  - Stop / pause transitions → `panel.on_playing_state_changed(False)`
- **Plan 37-03 (Toast overlay — parallel Wave 2):** Zero file overlap with this plan. Can merge independently.
- **Plan 38 (favorites / star button):** Insert a `QToolButton` immediately before the `volume_slider.addWidget` call — comment marker `# Plan 38: insert star button here` is in place.
- **Plan 39 (edit dialog + stream picker):** Insert widgets immediately after the `stop_btn` — comment marker `# Plan 39: insert edit button + stream picker here` is in place.

## Self-Check: PASSED

Verified:
- `musicstreamer/ui_qt/now_playing_panel.py` exists
- `musicstreamer/ui_qt/icons/media-playback-start-symbolic.svg` exists
- `musicstreamer/ui_qt/icons/media-playback-pause-symbolic.svg` exists
- `musicstreamer/ui_qt/icons/media-playback-stop-symbolic.svg` exists
- `tests/test_now_playing_panel.py` exists
- `musicstreamer/ui_qt/icons.qrc` contains all three `media-playback-*-symbolic.svg` entries
- `musicstreamer/ui_qt/icons/NOTICE.md` lists all three icons
- Commit `1b99d85` exists (Task 1 — icons)
- Commit `68f9b00` exists (Task 2 — panel + tests)
- `musicstreamer/player.py` untouched
- `musicstreamer/cover_art.py` untouched
- `musicstreamer/ui_qt/main_window.py` untouched
- Plan-02 suite (`tests/test_now_playing_panel.py`): 19/19 passed
- Full suite (ignoring in-progress 37-03 `test_toast_overlay.py`): 303 passed
