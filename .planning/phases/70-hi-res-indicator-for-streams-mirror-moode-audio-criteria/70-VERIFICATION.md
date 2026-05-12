---
phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria
verified: 2026-05-12T00:00:00Z
status: passed
score: 22/22 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open the app with a station bound that has a cached FLAC hi-res stream. Observe the now-playing panel."
    expected: "A 'HI-RES' pill badge appears immediately left of the LIVE badge in the icy_row. Badge uses palette(highlight) background, palette(highlighted-text) text, border-radius 8px, bold weight. Badge is hidden for an MP3-only station."
    why_human: "QSS rendering, layout order, and theme-contrast correctness cannot be asserted without a visual pixel inspection."
  - test: "While a hi-res stream is playing, observe the stream picker combo box items in the now-playing panel."
    expected: "Each hi-res stream item shows a label such as 'FLAC 1411 — HI-RES' (em-dash separator, all-caps tier suffix). Lossless CD stream shows 'FLAC 1411 — LOSSLESS'. MP3 stream shows no suffix."
    why_human: "Combo box rendering and em-dash character in the label requires visual confirmation."
  - test: "Open the station tree (StationListPanel). Observe tree rows for a known hi-res station versus an MP3-only station."
    expected: "Hi-res station row shows a 'HI-RES' pill before the star icon. CD-FLAC station shows 'LOSSLESS' pill. MP3-only station shows no pill. Provider rows show no pill. When a hi-res row is selected (highlighted), the pill fill and text colors swap (Highlight/HighlightedText) so the pill remains visible."
    why_human: "QPainter paint() output requires visual pixel verification; selection-state color swap correctness cannot be unit-tested reliably."
  - test: "Open EditStationDialog for a station with a FLAC 96/24 stream (already played once so caps are cached). Inspect the streams table."
    expected: "A 6th column 'Audio quality' (Sentence case) appears, 90 px wide, Fixed mode. The cell for the hi-res stream reads 'Hi-Res' (title-case prose). Cell is read-only (cannot be edited). Header tooltip reads 'Auto-detected from playback. Hi-Res ≥ 48 kHz or ≥ 24-bit on a lossless codec.'"
    why_human: "Read-only cell rendering and tooltip display require interactive testing."
  - test: "In StationListPanel, play a hi-res stream to completion so caps are cached. Observe the 'Hi-Res only' chip."
    expected: "The 'Hi-Res only' chip becomes visible. Clicking it filters the station list to only stations with at least one cached hi-res stream. Unclicking restores all stations. Chip has tooltip 'Show only stations with at least one Hi-Res stream'."
    why_human: "Filter chip visibility gate (F-02), filter behavior, and tooltip require interactive end-to-end testing."
  - test: "Play a hi-res stream; observe whether the badge updates live after GStreamer caps are negotiated (runtime detection)."
    expected: "Initially the badge shows 'LOSSLESS' (FLAC cold-start D-03 default). After GStreamer reports the actual caps (96 kHz / 24-bit), the badge text switches to 'HI-RES' and the tooltip updates to 'Hi-Res — 96 kHz / 24-bit'."
    why_human: "Real GStreamer caps negotiation on a live stream cannot be simulated in unit tests; the end-to-end caps flow requires a real playback session."
---

# Phase 70: Hi-Res Indicator for Streams Verification Report

**Phase Goal:** Surface a two-tier audio-quality badge ("LOSSLESS" / "HI-RES") across the now-playing panel, station-tree rows, stream-picker entries, and EditStationDialog rows, plus a 'Hi-Res only' filter chip and a hi-res-preferring tiebreak in stream failover ordering. Detection is runtime-driven from negotiated GStreamer caps; the rate/depth are persisted per stream so the badge appears on tree rows after the first replay. Mirrors moOde Audio's Hi-Res convention.

**Verified:** 2026-05-12
**Status:** passed (escalated from `human_needed` after live UAT closure 2026-05-12T17:30:00Z — see "UAT Closure" section at file end)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | hi_res.py exports classify_tier, bit_depth_from_format, best_tier_for_station, TIER_LABEL_BADGE, TIER_LABEL_PROSE | VERIFIED | File exists at 156 lines; all five symbols confirmed importable via spot-check: `classify_tier("FLAC", 96000, 24) == "hires"`, `classify_tier("FLAC", 0, 0) == "lossless"`, `classify_tier("AAC", 96000, 24) == ""`, constants match contract |
| 2 | classify_tier honors D-01 through D-04 — two tiers, FLAC/ALAC thresholds, D-03 fallback, D-04 lossy returns "" | VERIFIED | Spot-checks pass; 69/69 test_hi_res.py tests pass including parametrized truth-table |
| 3 | StationStream.sample_rate_hz and .bit_depth fields exist after bitrate_kbps | VERIFIED | `models.py` lines 22-23: `sample_rate_hz: int = 0`, `bit_depth: int = 0` in correct position |
| 4 | station_streams table schema + two idempotent ALTER blocks in db_init | VERIFIED | `repo.py` lines 61-62 show CREATE TABLE columns; lines 94-100 show two independent try/except ALTER blocks. Spot-check: `db_init()` twice on `:memory:` — both succeed, columns present |
| 5 | Repo.insert_stream + update_stream accept sample_rate_hz + bit_depth kwargs; list_streams hydrates them | VERIFIED | `repo.py` lines 204/215: kwargs present with default 0; line 198: hydration in list_streams; round-trip confirmed via test_repo.py (87/87 pass) |
| 6 | order_streams sort key includes -sample_rate_hz and -bit_depth between -bitrate_kbps and position | VERIFIED | `stream_ordering.py` lines 70-71 verified. Spot-check: FLAC-96/24 sorts before FLAC-44/16; AAC-96/24 still loses to CD-FLAC (S-02 preserved). 69/69 test_stream_ordering.py tests pass |
| 7 | Player.audio_caps_detected = Signal(int, int, int) declared at class scope; _on_caps_negotiated handler + _arm_caps_watch_for_current_stream + dual-path wiring | VERIFIED | `player.py` line 279: Signal declared. Line 738: `_arm_caps_watch_for_current_stream`. Line 770: `_on_caps_negotiated`. Lines 865 + 984: dual-path calls from `_on_playbin_state_changed` and `_set_uri`. Pitfall 2 honored: no QTimer.singleShot, no setVisible/setText/set_property in handler body. Pitfall 6 honored: `_caps_armed_for_stream_id = 0` in handler body. All 6 test_player_caps.py tests pass |
| 8 | MainWindow connects Player.audio_caps_detected with QueuedConnection; declares quality_map_changed Signal + _last_quality_payload cache; _on_audio_caps_detected follows DB-write-first ordering (Phase 50 D-04) then fan-out | VERIFIED | `main_window.py` lines 138, 362, 366-367, 471+. DB write at line 519 precedes _refresh_quality_badge at 544 and quality_map_changed.emit at 550. Idempotency cache at line 533. Stream-deleted race handled (lines 505-507, 515-517). 6 new tests in test_main_window_integration.py pass (66/66 total) |
| 9 | NowPlayingPanel._quality_badge QLabel: PlainText lock, Phase 68 LIVE QSS verbatim, placed LEFT of _live_badge in icy_row, initially hidden | VERIFIED | `now_playing_panel.py` lines 387-413. `setTextFormat(Qt.PlainText)` at 388. QSS character-for-character identical to _live_badge (both confirmed by grep). `addWidget(_quality_badge)` at 411 precedes `addWidget(_live_badge)` at 412. T-40-04 baseline bumped 4→5 |
| 10 | NowPlayingPanel._refresh_quality_badge slot: slot-never-raise idiom, correct tier/badge/tooltip/accessibleName logic; called from bind_station and stream-picker selection change | VERIFIED | `now_playing_panel.py` line 1518. Called at lines 780 (bind_station) and 1077 (stream selection). 3 non-comment occurrences verified. All 134/134 test_now_playing_panel.py tests pass |
| 11 | Stream picker formatter appends em-dash tier suffix when tier is non-empty | VERIFIED | `now_playing_panel.py` lines 1060-1062: `classify_tier` called, `TIER_LABEL_BADGE.get` used, `—` (em-dash) separator confirmed |
| 12 | station_star_delegate.paint() renders tier pill BEFORE star for station rows; QPainter primitives only (no QSS); selection-state color swap; _PILL_* geometry constants; sizeHint grows | VERIFIED | `station_star_delegate.py` lines 27-34: all four geometry constants. Line 99: `best_tier_for_station`. Lines 113-124: selection-swap + antialiasing + drawRoundedRect + drawText. `setStyleSheet` count == 0 (grep confirmed). sizeHint at line 154 grows by `_PILL_WIDTH_WORST_CASE + _PILL_TO_STAR_GAP`. All 5 Wave 0 delegate tests pass (117/117 total excluding pre-existing flaky tests) |
| 13 | EditStationDialog._COL_AUDIO_QUALITY = 5; 6-column streams_table; "Audio quality" header (Sentence case); 90 px Fixed width; UI-SPEC OD-8 tooltip verbatim; per-row read-only TIER_LABEL_PROSE cell | VERIFIED | `edit_station_dialog.py` line 215: constant defined. Line 400: `QTableWidget(0, 6)`. Line 402: header label list with "Audio quality". Lines 412/417: Fixed mode + 90px. Lines 428-429: tooltip verbatim. Lines 717-720: classify_tier → TIER_LABEL_PROSE → read-only flag. All Phase 70 dialog tests pass |
| 14 | StationFilterProxyModel._hi_res_only + _hi_res_station_ids + set_quality_map (Pitfall 7 invalidate-guard) + set_hi_res_only (always invalidates) + clear_all + has_active_filter + filterAcceptsRow branch | VERIFIED | `station_filter_proxy.py` lines 45-46: fields. Line 88: `set_quality_map` with guard at line 102. Line 105: `set_hi_res_only`. Line 126: `clear_all` resets. Line 138: `has_active_filter`. Line 162: filterAcceptsRow branch. All 24/24 test_station_filter_proxy.py tests pass |
| 15 | StationListPanel._hi_res_chip: "Hi-Res only" text, checkable, _CHIP_QSS reuse, initial hidden, bound-method toggled connection; update_quality_map + set_hi_res_chip_visible public methods | VERIFIED | `station_list_panel.py` lines 301-313: chip construction verified. Line 313: `toggled.connect(self._on_hi_res_chip_toggled)` — bound method, no lambda (confirmed by grep). Lines 604/614/630: three methods. MainWindow hasattr guard now matches |
| 16 | settings_export._station_to_dict emits sample_rate_hz + bit_depth; _insert_station + _replace_station SQL extended with two columns + Phase 47.3 forward-compat idiom | VERIFIED | `settings_export.py` lines 127-128: dict keys. Lines 410/421-422: INSERT SQL + value tuple. Lines 468/479-480: _replace_station mirrors. `int(stream.get("sample_rate_hz", 0) or 0)` idiom confirmed. All 87/87 test_settings_export.py tests pass |
| 17 | REQUIREMENTS.md HRES-01 row in Features section + Traceability row + coverage counts 20→21 + Last-updated stamp | VERIFIED | 3 occurrences of HRES-01 in REQUIREMENTS.md. Coverage footer: "v2.1 requirements: 21 total", "Mapped to phases: 21". Traceability: `| HRES-01 | Phase 70 | Complete |`. Last-updated stamped 2026-05-12 |
| 18 | ROADMAP.md Phase 70 Goal text finalized; Requirements: HRES-01; 12/12 plans complete with checklist | VERIFIED | Line 577: full goal text. Line 578: `Requirements: HRES-01`. Line 580: `12/12 plans complete`. Lines 583-594: all 12 plans with `[x]` checkboxes |
| 19 | hi_res.py module is pure: zero GStreamer/Qt imports | VERIFIED | `grep -c "import gi\|import Gst\|import Qt\|import PySide6"` returns 0 |
| 20 | No PRAGMA user_version in repo.py | VERIFIED | grep returns empty — invariant preserved |
| 21 | Pitfall 2 invariant: _on_caps_negotiated does not call setVisible/setText/setStyleSheet/set_property/set_state/QTimer.singleShot | VERIFIED | grep over handler body returns 0 for all prohibited patterns |
| 22 | Pre-existing flaky tests are the only failures in the full suite (2 failing: test_filter_strip_hidden_in_favorites_mode, test_refresh_recent_updates_list) | VERIFIED | Both failures reproduce without Phase 70 files in scope; test_filter_strip_hidden_in_favorites_mode fails at a QListView assertion unrelated to Phase 70 (recent_view); test_refresh_recent_updates_list similarly pre-existing. All 28 Phase 70-introduced tests are GREEN |

**Score:** 22/22 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/hi_res.py` | Pure classifier helpers + tier label constants | VERIFIED | 156 lines, all 5 public symbols present, zero GStreamer/Qt imports |
| `musicstreamer/models.py` | StationStream with sample_rate_hz + bit_depth after bitrate_kbps | VERIFIED | Lines 22-23, correct position |
| `musicstreamer/repo.py` | Schema migration + CRUD kwargs + list_streams hydration | VERIFIED | CREATE TABLE + 2 ALTER blocks + insert/update/list confirmed |
| `musicstreamer/stream_ordering.py` | order_streams with -sample_rate_hz, -bit_depth tiebreak | VERIFIED | Lines 70-71 in sort key lambda |
| `musicstreamer/player.py` | audio_caps_detected Signal + _on_caps_negotiated + _arm_caps_watch | VERIFIED | Signal at line 279, both methods, dual-path wiring confirmed |
| `musicstreamer/ui_qt/main_window.py` | quality_map_changed + _on_audio_caps_detected + audio_caps_detected.connect | VERIFIED | Lines 138, 366, 471+ |
| `musicstreamer/ui_qt/now_playing_panel.py` | _quality_badge + _refresh_quality_badge + picker tier suffix | VERIFIED | Lines 387, 1518, 1060-1062 |
| `musicstreamer/ui_qt/station_star_delegate.py` | paint() tier pill + sizeHint extension + geometry constants | VERIFIED | Lines 27-34, 78+, 138+ |
| `musicstreamer/ui_qt/edit_station_dialog.py` | _COL_AUDIO_QUALITY = 5 + 6-column table + read-only cell | VERIFIED | Lines 215, 400, 718-720 |
| `musicstreamer/ui_qt/station_filter_proxy.py` | set_quality_map + set_hi_res_only + Pitfall 7 guard + filterAcceptsRow | VERIFIED | Lines 41-46, 88, 105, 162 |
| `musicstreamer/ui_qt/station_list_panel.py` | _hi_res_chip + update_quality_map + set_hi_res_chip_visible | VERIFIED | Lines 301-313, 604, 614, 630 |
| `musicstreamer/settings_export.py` | sample_rate_hz + bit_depth round-trip + forward-compat idiom | VERIFIED | Lines 127-128, 410, 421-422, 468, 479-480 |
| `tests/test_hi_res.py` | 8 test functions covering truth-table + bit_depth + best_tier + label constants | VERIFIED | 184 lines, 8 test functions confirmed |
| `tests/test_player_caps.py` | 6 test functions: rate/depth, queued signal, disarm, ignore-unknown, ignore-zero, no-double-emit | VERIFIED | 166 lines, 6 test functions, all GREEN |
| `.planning/REQUIREMENTS.md` | HRES-01 row + traceability entry + coverage counts updated | VERIFIED | 3 occurrences, counts 21/21 |
| `.planning/ROADMAP.md` | Phase 70 goal finalized, requirements + 12-plan checklist | VERIFIED | All 12 plans marked [x] |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| tests/test_hi_res.py | musicstreamer/hi_res.py | `from musicstreamer.hi_res import classify_tier, ...` | WIRED | Import confirmed; 69/69 tests GREEN |
| musicstreamer/stream_ordering.py | models.StationStream.sample_rate_hz / .bit_depth | `-(s.sample_rate_hz or 0), -(s.bit_depth or 0)` in sort key | WIRED | Lines 70-71 confirmed |
| musicstreamer/repo.py db_init | models.StationStream | `StationStream(..., sample_rate_hz=r["sample_rate_hz"], bit_depth=r["bit_depth"])` | WIRED | Line 198 confirmed |
| Player._on_caps_negotiated | Player.audio_caps_detected | `self.audio_caps_detected.emit(sid, rate, depth)` only — Pitfall 2 honored | WIRED | Line 819 confirmed, no prohibited patterns |
| Player.audio_caps_detected | MainWindow._on_audio_caps_detected | `audio_caps_detected.connect(self._on_audio_caps_detected, Qt.ConnectionType.QueuedConnection)` | WIRED | Lines 366-367 confirmed |
| MainWindow._on_audio_caps_detected | repo.update_stream THEN fan-out | DB write at line 519 precedes _refresh_quality_badge at 544 and quality_map_changed.emit at 550 | WIRED | Phase 50 D-04 ordering preserved |
| MainWindow._on_audio_caps_detected | now_playing._refresh_quality_badge | hasattr guard now matches; call at line 544 | WIRED | Method exists on NowPlayingPanel |
| MainWindow._on_audio_caps_detected | station_panel.update_quality_map | hasattr guard now matches; call at line 547 | WIRED | Method exists on StationListPanel |
| station_list_panel.update_quality_map | proxy.set_quality_map + set_hi_res_chip_visible | Lines 614-626 | WIRED | Confirmed |
| _hi_res_chip.toggled | proxy.set_hi_res_only | `toggled.connect(self._on_hi_res_chip_toggled)` — bound method | WIRED | Line 313, QA-05 pattern |
| now_playing_panel._refresh_quality_badge | hi_res.classify_tier + TIER_LABEL_BADGE + TIER_LABEL_PROSE | `from musicstreamer.hi_res import classify_tier, TIER_LABEL_BADGE, TIER_LABEL_PROSE` | WIRED | Lines 62, 1565-1566 |
| station_star_delegate.paint | hi_res.best_tier_for_station + TIER_LABEL_BADGE | `from musicstreamer.hi_res import best_tier_for_station, TIER_LABEL_BADGE` | WIRED | Line 22, lines 99-101 |
| edit_station_dialog._add_stream_row | hi_res.classify_tier + TIER_LABEL_PROSE | `from musicstreamer.hi_res import classify_tier, TIER_LABEL_PROSE` | WIRED | Line 48, lines 717-718 |
| settings_export._station_to_dict | _insert_station / _replace_station SQL | round-trip dict → ZIP → SQL preserves sample_rate_hz / bit_depth | WIRED | Lines 127-128, 410, 468 confirmed |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| now_playing_panel._refresh_quality_badge | `s.codec, s.sample_rate_hz, s.bit_depth` from current stream | `self._streams` populated by `_populate_stream_picker` which reads repo-hydrated StationStream objects | Yes — repo.list_streams returns DB values; defaults to 0/0 (D-03 fallback triggers lossless for FLAC) | FLOWING |
| station_star_delegate.paint | `station.streams` iterable | Station from `index.data(Qt.UserRole)` — model reads from repo.list_stations | Yes — DB-backed; sample_rate_hz/bit_depth hydrated from row | FLOWING |
| MainWindow._on_audio_caps_detected quality_map | `self._repo.list_stations()` | DB read after repo.update_stream write | Yes — freshly written caps values | FLOWING |
| StationFilterProxyModel._hi_res_station_ids | quality_map dict from MainWindow fan-out | Rebuilt from repo.list_stations after every caps update | Yes — driven from real cap detection events | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| classify_tier FLAC/ALAC rules | Python import + calls in test env | All D-01..D-04 cases correct | PASS |
| classify_tier AAC hi-res still returns "" | `classify_tier("AAC", 96000, 24) == ""` | True | PASS |
| order_streams FLAC-96/24 outranks FLAC-44/16 | Python spot-check | FLAC-96/24 first in result | PASS |
| order_streams cross-codec: AAC doesn't outrank FLAC | Python spot-check | FLAC first regardless of AAC rate/depth | PASS |
| db_init idempotent | sqlite3 in-memory + db_init twice | No exception, columns present | PASS |
| settings_export forward-compat idiom present | inspect.getsource on _station_to_dict and _insert_station | Keys and `int(stream.get(...))` idiom confirmed | PASS |
| _on_caps_negotiated no Qt-object access | grep over handler body | 0 prohibited patterns | PASS |
| test_hi_res.py | `uv run pytest tests/test_hi_res.py` | 69 passed | PASS |
| test_player_caps.py | `uv run pytest tests/test_player_caps.py` | 6 passed | PASS |
| test_repo.py (inc. Phase 70 stubs) | `uv run pytest tests/test_repo.py` | 87 passed | PASS |
| test_stream_ordering.py | `uv run pytest tests/test_stream_ordering.py` | 69 passed | PASS |
| test_settings_export.py | `uv run pytest tests/test_settings_export.py` | 87 passed | PASS |
| test_station_filter_proxy.py | `uv run pytest tests/test_station_filter_proxy.py` | 24 passed | PASS |
| test_station_star_delegate.py | `uv run pytest tests/test_station_star_delegate.py` | included in 117-pass run | PASS |
| test_edit_station_dialog.py | `uv run pytest tests/test_edit_station_dialog.py` | included in 117-pass run | PASS |
| test_station_list_panel.py (Phase 70 tests) | `uv run pytest tests/test_station_list_panel.py` | 117 passed, 2 pre-existing failures excluded | PASS |
| test_now_playing_panel.py | `uv run pytest tests/test_now_playing_panel.py` | 134 passed | PASS |
| test_main_window_integration.py | `uv run pytest tests/test_main_window_integration.py` | 66 passed | PASS |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` files found; phase is a feature addition, not a migration phase.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| HRES-01 | Plans 70-00 through 70-11 | Two-tier badge (LOSSLESS/HI-RES) across 4 UI surfaces + filter chip + ordering tiebreak + runtime caps + persistence | SATISFIED | All 12 plans implemented; REQUIREMENTS.md updated; 28 Phase 70 tests GREEN |

### Anti-Patterns Found

No TBD, FIXME, XXX, or PLACEHOLDER markers found in any Phase 70 modified file. No stub implementations detected. No hardcoded empty data flowing to rendering surfaces.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | — |

### Human Verification Required

Six items require interactive testing with a running application and real GStreamer streams:

**1. NowPlayingPanel _quality_badge visual rendering**

**Test:** Bind a station with a FLAC 96/24 stream (caps already detected). Observe the icy_row in the now-playing panel.
**Expected:** "HI-RES" pill appears immediately left of the LIVE badge. Badge uses palette(highlight) background, palette(highlighted-text) text, border-radius 8px, bold font. Badge is absent for MP3-only stations.
**Why human:** QSS rendering correctness and layout order cannot be asserted from unit tests.

**2. Stream picker tier suffix**

**Test:** Open the stream switcher in the now-playing panel for a multi-stream station with at least one FLAC hi-res stream and one MP3 stream.
**Expected:** Hi-res stream item reads like "FLAC 1411 — HI-RES" (em-dash U+2014, all-caps badge). CD FLAC reads "FLAC 1411 — LOSSLESS". MP3 item has no suffix.
**Why human:** QComboBox rendering with embedded special character requires interactive inspection.

**3. Station tree tier pill**

**Test:** Browse the station tree. Find a station with a known hi-res FLAC stream (caps previously detected). Compare against an MP3-only station and a provider row.
**Expected:** Hi-res station row shows "HI-RES" pill before the star. CD-FLAC shows "LOSSLESS". MP3 shows no pill. Provider rows show no pill. When the hi-res row is selected (blue highlight), the pill inverts colors and remains legible.
**Why human:** QPainter output and selection-state color swap require visual verification.

**4. EditStationDialog Audio quality column**

**Test:** Open EditStationDialog for a station that has been played (caps cached). Inspect the streams table.
**Expected:** A 6th column "Audio quality" (Sentence case) is present, 90 px wide, Fixed mode. The cell for a hi-res FLAC stream reads "Hi-Res". Cell cannot be edited (read-only). Hovering the column header shows tooltip "Auto-detected from playback. Hi-Res ≥ 48 kHz or ≥ 24-bit on a lossless codec."
**Why human:** Table rendering, read-only enforcement, and tooltip visibility require interactive testing.

**5. Hi-Res only filter chip end-to-end**

**Test:** Play a hi-res stream until caps are detected. In StationListPanel, verify the "Hi-Res only" chip becomes visible. Click it. Observe the station list.
**Expected:** Chip becomes visible only when at least one station has a cached hi-res stream (F-02). Clicking filters list to hi-res stations only. Unclicking restores all. Chip tooltip is "Show only stations with at least one Hi-Res stream".
**Why human:** Chip visibility gate + filter behavior requires the full app lifecycle (caps detection → quality_map fan-out → chip visibility flip → proxy filter).

**6. Runtime caps detection live flow**

**Test:** Play a FLAC stream for the first time (no cached caps). Watch the badge in the now-playing panel.
**Expected:** Initially shows "LOSSLESS" (D-03 FLAC cold-start fallback). After GStreamer negotiates caps (typically within 1-2 seconds), badge updates to "HI-RES" if rate > 48 kHz or depth > 16-bit, or stays "LOSSLESS" for CD FLAC. Tooltip updates to reflect the actual rate/depth.
**Why human:** Live GStreamer caps negotiation (notify::caps Signal path) cannot be simulated in unit tests; requires real playback.

### Gaps Summary

None. All 22 automated must-haves are VERIFIED. The six items above are human verification needs for visual/interactive/runtime behaviors — not implementation gaps. The automated test suite confirms the structural wiring, logic correctness, DB persistence, and threading invariants that underpin those visual behaviors.

The 2 test failures (`test_filter_strip_hidden_in_favorites_mode` and `test_refresh_recent_updates_list`) are confirmed pre-existing flaky failures in `tests/test_station_list_panel.py` that reproduce on the main branch without Phase 70 changes. They are unrelated to Phase 70 scope.

---

_Verified: 2026-05-12_
_Verifier: Claude (gsd-verifier)_

---

## UAT Closure (2026-05-12T17:30:00Z)

All 6 human-verification items closed PASS by user after two post-UAT fixes:

1. **commit `e57051e`** — `fix(70-04): use audio-sink static pad for caps detection (playbin3 compat)` — restored app stability; the original Plan 70-04 used `playbin.emit("get-audio-pad", 0)`, a legacy `playbin` 1.x action signal absent on `GstPlayBin3`, raising TypeError on every station bind.

2. **commit `f53d4cb`** — `fix(70): revise D-04 — mirror moOde RADIO_BITRATE_THRESHOLD=128 for lossy` — corrected the moOde mirror; original D-04 ("no badge for lossy streams") contradicted the actual moOde playerlib.js logic (`RADIO_BITRATE_THRESHOLD = 128`, badge shown when `bitrate > 128`). Lossy codecs at bitrate_kbps > 128 now classify as "hires", matching moOde's documented threshold.

User report verbatim: "Yes, I see it on all the ones that I'd expect (also agree with moodeAudio's setup since just above 128 is usually 192 which is the common start for most 'indistinguishable' quality improvements start. I see no obvious regressions or other issues either."

Final test count: 517 passed in the Phase 70 surface (vs 497 before the D-04 mirror fix); 2 failures are pre-existing `test_station_list_panel.py` flaky tests unrelated to Phase 70.

**Verification status escalated: human_needed → passed.**
