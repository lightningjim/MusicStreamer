# Phase 41 — UI Review

**Audited:** 2026-04-15
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md for this phase)
**Screenshots:** Not captured (no dev server detected)
**Scope note:** Phase 41 is a backend/infrastructure phase. Only UI-touching files audited: `main_window.py` and `now_playing_panel.py`. Audit focuses on observable UI impacts from MPRIS2 wiring, not the backend code itself.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | Toast and tooltip copy is specific, contextual, and uses ellipsis correctly |
| 2. Visuals | 4/4 | Icon-only buttons all have tooltips; play/pause icon swaps contextually |
| 3. Color | 4/4 | No hardcoded colors introduced; no new color surface added by Phase 41 |
| 4. Typography | 4/4 | Three-tier type scale (9/10/13pt) is intentional and consistent with UI-SPEC |
| 5. Spacing | 4/4 | All spacing is pixel-explicit (16/24/8) with no arbitrary or inconsistent values |
| 6. Experience Design | 3/4 | play/pause state not mirrored to backend on `_on_stop_clicked` path from panel |

**Overall: 23/24**

---

## Top 3 Priority Fixes

1. **Stop via panel button does not call `backend.set_playback_state("stopped")`** — OS media overlay stays "Playing" after user clicks the in-panel Stop button directly — `_on_stop_clicked` calls `self._player.stop()` and updates `_is_playing` locally, but the media keys backend is only informed in `_on_media_key_stop` (from OS) and `_on_station_deleted` (from deletion). A user stopping via the in-panel button leaves the GNOME overlay in a stale state. Fix: connect `now_playing.stop_btn.clicked` (or the existing `_on_stop_clicked` call) to emit `set_playback_state("stopped")` in MainWindow. The cleanest path is adding a `stopped_by_user` signal on `NowPlayingPanel` and wiring it in MainWindow alongside the existing `track_starred` pattern.

2. **`star_btn` tooltip goes blank on no-station state** (`now_playing_panel.py:387` — `setToolTip("")`) — When no station is bound, hovering the star button gives an invisible tooltip with no affordance. Low-severity, but tooltip emptiness looks like a bug to screen-reader users. Fix: change the empty branch to `setToolTip("No station selected")`.

3. **`_on_media_key_play_pause` reads `now_playing._is_playing` directly** (`main_window.py:297`) — this accesses a private attribute of a sibling widget. If `NowPlayingPanel` is ever refactored, this will silently break. Fix: expose a `is_playing` property (read-only) on `NowPlayingPanel` and use that. One-line change to the panel; one-line change to MainWindow.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

All user-visible strings introduced or touched in Phase 41 are specific and well-formed.

- `main_window.py:223` — `"Connecting\u2026"` uses the Unicode ellipsis character (U+2026) per UI-SPEC copywriting contract.
- `main_window.py:231` — `"Stream exhausted"` is specific; not "Error" or "Something went wrong".
- `main_window.py:235` — `"Stream failed, trying next\u2026"` is informative during failover.
- `main_window.py:239` — `"Channel offline"` is concise and correct for Twitch offline state.
- `main_window.py:246` — `f"Playback error: {truncated}"` surfaces the actual error message (truncated at 80 chars + ellipsis), which is more actionable than a generic error toast.
- `now_playing_panel.py:166,180` — "Play" / "Pause" / "Stop" tooltip labels are correct and swap contextually.
- `now_playing_panel.py:134` — Default ICY label `"No station playing"` is a clear empty state, not "No data" or "Nothing".

No generic CTAs ("OK", "Submit", "Click Here") found. No "went wrong / try again" patterns found.

### Pillar 2: Visuals (4/4)

All interactive controls introduced or touched in Phase 41 have proper visual affordances.

- `play_pause_btn`, `stop_btn`, `edit_btn`, `star_btn` — all `QToolButton` with `ToolButtonIconOnly` style; all have explicit `setToolTip()` calls (lines 166, 180, 191, 306).
- `play_pause_btn` icon swaps between `media-playback-start-symbolic` and `media-playback-pause-symbolic` based on state (`on_playing_state_changed`, lines 331–344) — correct contextual icon behavior.
- Phase 41 introduces no new visual elements; it only adds backend wiring. The existing three-column layout (180px logo | center stretch | 160px cover) is not disturbed.
- `edit_btn.setEnabled(False)` when no station is bound (line 192, enforced in `on_playing_state_changed` line 345) — correct disabled affordance.
- `star_btn.setEnabled(False)` until station + ICY title available (line 208, `_update_star_enabled`) — correct gating.

No icon-only buttons without tooltips. No new unlabeled controls introduced.

### Pillar 3: Color (4/4)

Phase 41 introduces zero new color surface. No hardcoded hex values or `rgb()` calls appear in either file. Accent color palette is applied at startup via the existing `apply_accent_palette` path (line 112–113) — no change from pre-Phase-41.

Registry audit: shadcn not initialized — skipped.

### Pillar 4: Typography (4/4)

Three intentional type sizes in `now_playing_panel.py`:

| Role | Size | Weight | Location |
|------|------|--------|----------|
| Name/Provider label | 9pt | Normal | line 127–128 |
| ICY title (heading) | 13pt | DemiBold | line 136–137 |
| Elapsed timer | 10pt | Normal (TypeWriter) | line 146–148 |

This is a deliberate three-level hierarchy matching the UI-SPEC comment annotations in the source (`# UI-SPEC Heading role 13pt DemiBold`, `# UI-SPEC Label role 9pt Normal`, `# UI-SPEC Body role 10pt`). Three font sizes and two weights — within the abstract standard (≤4 sizes, ≤2 weights). Phase 41 introduces no new typography.

### Pillar 5: Spacing (5/4 — note: capped at 4/4)

All spacing values are explicit pixel constants, not arbitrary or inconsistent:

| Value | Usage | Location |
|-------|-------|----------|
| 16px | outer layout margins (all 4 sides) | line 105 |
| 24px | outer layout spacing (between columns) | line 106 |
| 8px | center column spacing, control row spacing | lines 121, 154 |
| 180/160px | logo/cover fixed sizes | lines 112, 230 |
| 36/28px | button fixed sizes | lines 159, 173, 187, 206 |
| 120px | volume slider fixed width | line 217 |
| 140px | stream combo minimum width | line 198 |

No arbitrary `[N px]` Tailwind-style values (this is a Qt/Python project — spacing is set via method calls). No inconsistent patterns introduced by Phase 41. The 16/24/8 rhythm is a consistent 2:3:1 scale.

### Pillar 6: Experience Design (3/4)

**What's good:**
- Full loading state: `"Connecting…"` toast on station activate (line 223).
- Error state: `_on_playback_error` surfaces actual error message in a toast (line 246), truncated to 80 chars.
- Empty state: `"No station playing"` is the default ICY label (line 134); panel controls start disabled.
- Offline state: `_on_offline` shows `"Channel offline"` and calls `set_playback_state("stopped")` (lines 239–241).
- Failover state: both `None` (stream exhausted) and non-None (trying next) cases handled (lines 230–235).
- Belt-and-braces factory fallback: `try/except` around `media_keys.create()` with `NoOpMediaKeysBackend` fallback (lines 181–185) — startup never blocks on media keys failure.
- `closeEvent` calls `backend.shutdown()` before `super()` (lines 209–215) — clean OS deregistration.
- Next/Previous no-ops are wired but intentionally empty with D-03 comments (lines 307–313) — correct.

**Finding that costs 1 point:**

`_on_stop_clicked` in `now_playing_panel.py` (lines 363–376) stops playback and updates all local state but does NOT notify `main_window.py` — and therefore the `_media_keys` backend is never told `set_playback_state("stopped")` when the user presses the panel's own Stop button. The backend only learns about stops via:
- `_on_media_key_stop` (OS request path — line 305)
- `_on_station_deleted` (station deletion path — line 273)
- `_on_offline` / `_on_failover(None)` (player events — lines 233, 241)

The direct panel Stop button click path is missing. A user who manually clicks Stop will leave the GNOME media overlay showing the station as "Playing" until the next ICY update or app restart. This is an observable UI regression introduced by Phase 41's wiring.

**Not flagged (intentional):**
- `_on_media_key_next` / `_on_media_key_previous` are explicit no-ops per D-03 — correct behavior, not a defect.

---

## Files Audited

- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/main_window.py`
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/now_playing_panel.py`
- `.planning/phases/41-platform-media-keys/41-01-SUMMARY.md` (context)
- `.planning/phases/41-platform-media-keys/41-02-SUMMARY.md` (context)
- `.planning/phases/41-platform-media-keys/41-03-SUMMARY.md` (context)
- `.planning/phases/41-platform-media-keys/41-01-PLAN.md` (context)
- `.planning/phases/41-platform-media-keys/41-CONTEXT.md` (context)
