# Phase 37 — UI Review

**Audited:** 2026-04-12
**Baseline:** 37-UI-SPEC.md (approved design contract)
**Screenshots:** Not captured — no dev server detected (desktop Qt app, no web server)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | All spec strings present; "No stations yet" empty state missing from station list |
| 2. Visuals | 3/4 | Three-column layout and icon sizes match spec; no stop button disabled state |
| 3. Color | 4/4 | Only spec-approved hardcoded color is the toast QSS rgba; all other colors inherit palette |
| 4. Typography | 3/4 | Provider group header uses `setBold(True)` (700 weight) instead of specified DemiBold (600) |
| 5. Spacing | 4/4 | All margin, padding, and gap values match the declared spacing scale exactly |
| 6. Experience Design | 3/4 | Toast covers error/failover/offline well; stop button lacks disabled state; empty station list has no visual fallback |

**Overall: 20/24**

---

## Top 3 Priority Fixes

1. **Provider group font weight is Bold (700) not DemiBold (600)** — Visually heavier than specified, potentially creates unintended contrast hierarchy against station row names — change `f.setBold(True)` to `f.setWeight(QFont.DemiBold)` in `station_tree_model.py:167`

2. **Stop button always enabled regardless of playback state** — Allows a no-op click when nothing is playing; spec explicitly requires `setEnabled(False)` when idle — add `self.stop_btn.setEnabled(False)` in `__init__`, then toggle it in `on_playing_state_changed()`

3. **Station list has no empty-state UI** — Spec declares: heading "No stations yet", body "Use the Import or Discover dialog to add stations." — when `repo.list_stations()` returns an empty list, `StationListPanel` silently shows an empty tree with no feedback; add a `QLabel` empty-state overlay in `StationListPanel` that shows when `StationTreeModel.rowCount(QModelIndex()) == 0`

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**Passing:**
- "Connecting…" uses U+2026 (`main_window.py:124`) — correct
- "Stream failed, trying next…" uses U+2026 (`main_window.py:132`) — correct
- "Stream exhausted" exact match (`main_window.py:129`) — correct
- "Channel offline" exact match (`main_window.py:136`) — correct
- `"Playback error: {truncated}"` with 80-char truncation + U+2026 (`main_window.py:141-142`) — correct
- `"No station playing"` idle ICY label (`now_playing_panel.py:122,293`) — correct
- `"Recently Played"` section header (`station_list_panel.py:74`) — correct
- `"Play"` / `"Pause"` tooltip toggle (`now_playing_panel.py:154,266,274`) — correct
- `"Stop"` tooltip (`now_playing_panel.py:168`) — correct
- `"Volume: {N}%"` tooltip (`now_playing_panel.py:203,301`) — correct
- `Name · Provider` separator uses U+00B7 (`now_playing_panel.py:224`) — correct
- Provider group `{name} ({N})` format (`station_tree_model.py:87`) — correct
- Elapsed idle state `"0:00"` (`now_playing_panel.py:132`) — correct

**Missing:**
- Empty state copy for station list: spec requires heading `"No stations yet"` and body `"Use the Import or Discover dialog to add stations."` — neither string exists in any `ui_qt/*.py` file. The tree simply renders empty with no user feedback.

**Not applicable this phase:** Destructive confirmation (none required), i18n.

---

### Pillar 2: Visuals (3/4)

**Passing:**
- Three-column now-playing layout (180px logo | stretch center | 160px cover) implemented per spec (`now_playing_panel.py:93-191`)
- Station logo `setScaledContents(False)` with `QPixmap.scaled(..., Qt.KeepAspectRatio)` — correct
- Cover art letterbox via `Qt.KeepAspectRatio` (UI-14 verified by test `test_youtube_thumbnail_letterbox`)
- `QTreeView.setHeaderHidden(True)`, `setRootIsDecorated(False)`, `expandAll()` — correct
- `QFrame.HLine + QFrame.Sunken` separator — matches spec
- Toast positioned bottom-center, 32px above bottom edge — correct
- `WA_TransparentForMouseEvents` + `WA_ShowWithoutActivating` — correct
- Icon-only buttons (`Qt.ToolButtonIconOnly`) — correct
- `QIcon.fromTheme(name, fallback)` pattern throughout — correct
- Adwaita symbolic icons for play/pause/stop/fallback — all four bundled

**Issues:**
- **Stop button disabled state absent.** Spec states: `Stop button | any | media-playback-stop-symbolic icon; disabled state when nothing is playing (setEnabled(False))`. The button is always enabled. Clicking stop when nothing is playing calls `player.stop()` unnecessarily and resets the panel to idle state even when it's already idle.
- **Toast parent is `MainWindow` not `centralWidget()`:** `ToastOverlay(self)` (`main_window.py:84`) passes `MainWindow` as parent, not `self._splitter` (the centralWidget). The 37-04 SUMMARY says it was parented to `self._splitter`, but the code passes `self`. `_reposition()` uses `parent.width()/height()` — with `MainWindow` as parent this includes menubar and statusbar in the height calculation, positioning the toast slightly higher than the 32px spec offset. Visual impact is small (status bar is ~22px) but is a spec deviation. The `eventFilter` also watches `MainWindow.resizeEvent` rather than the splitter's, which is actually fine.

---

### Pillar 3: Color (4/4)

**Passing:**
- No custom palette — all widget colors inherit Fusion/adwaita-qt system palette
- Only one hardcoded color block: toast QSS `rgba(40, 40, 40, 220)` with `color: white` (`toast.py:47-48`) — exactly what the spec allows and specifies
- No hardcoded colors in `station_list_panel.py`, `station_tree_model.py`, `now_playing_panel.py`, or `main_window.py`
- Colors in `icons_rc.py` (SVG fill values `#2e3436`, `#4a90d9`) are embedded in bundled icon data, not applied via code — acceptable
- Accent (`QPalette.Highlight`) reserved for: tree selection (Qt default), volume slider (Qt default Fusion), play/pause pressed state (Qt default) — no unauthorized accent usage found
- Toast `border-radius: 8px` — matches spec
- `QFrame.HLine + Sunken` separator inherits `QPalette.Mid` — matches spec

---

### Pillar 4: Typography (3/4)

**Passing:**
- "Recently Played" label: 9pt Normal (`station_list_panel.py:78-79`) — matches Label role
- `name_provider_label`: 9pt Normal (`now_playing_panel.py:115-116`) — matches Label role
- `icy_label`: 13pt DemiBold (`now_playing_panel.py:124-125`) — matches Heading role
- `elapsed_label`: 10pt Normal + TypeWriter style hint (`now_playing_panel.py:134-136`) — matches Body role with tabular digit requirement
- No family override (no `setFamily()` calls) — system font inherited per spec
- No italics, no third weight in now-playing panel or station list panel

**Issue:**
- **Provider group header uses `setBold(True)` (weight 700) instead of `setWeight(QFont.DemiBold)` (weight 600)** (`station_tree_model.py:167`). The spec says "13pt DemiBold" (weight 600). `setBold(True)` sets weight to `QFont.Bold` = 700, which is heavier than specified. The comment on line 165 even says "13pt DemiBold" but the implementation uses `setBold`. On Linux with Cantarell or Noto Sans this will render visibly heavier than intended — provider headers will outcompete the ICY title in visual weight.

  Fix: replace `f.setBold(True)` with `f.setWeight(QFont.DemiBold)` (keep `f.setPointSize(13)`).

- No `Display` (16pt DemiBold) usage this phase — reserved for empty-state headline not yet implemented. Not a defect; it's intentionally unused.

**Font count audit:** 3 roles in active use (Label 9pt, Body 10pt, Heading 13pt) — within the 4-role declared max. 2 weights in use (Normal 400, DemiBold 600 as intended — though the implementation delivers 700 for provider headers).

---

### Pillar 5: Spacing (4/4)

**Passing (all values match declared spacing scale):**

| Location | Spec | Implemented |
|----------|------|-------------|
| Now-playing outer margins | `16, 16, 16, 16` | `setContentsMargins(16, 16, 16, 16)` (`now_playing_panel.py:93`) |
| Now-playing outer column spacing | `lg = 24px` | `setSpacing(24)` (`now_playing_panel.py:94`) |
| Center column spacing | `sm = 8px` | `setSpacing(8)` (`now_playing_panel.py:109`) |
| Control row inter-widget spacing | `sm = 8px` | `setSpacing(8)` (`now_playing_panel.py:142`) |
| Station logo size | `180x180px` | `setFixedSize(180, 180)` (`now_playing_panel.py:100`) |
| Cover art slot | `160x160px` | `setFixedSize(160, 160)` (`now_playing_panel.py:189`) |
| Play/pause button | `36x36px` | `setFixedSize(36, 36)` (`now_playing_panel.py:147`) |
| Stop button | `36x36px` | `setFixedSize(36, 36)` (`now_playing_panel.py:161`) |
| Volume slider width | `120px` | `setFixedWidth(120)` (`now_playing_panel.py:176`) |
| Recently Played max height | `160px` | `setMaximumHeight(160)` (`station_list_panel.py:87`) |
| Station list min width | `280px` | `setMinimumWidth(280)` (`station_list_panel.py:65`) |
| Now-playing min width | `560px` | `setMinimumWidth(560)` (`now_playing_panel.py:87`) |
| Toast inner padding | `8px 12px` | `padding: 8px 12px` (`toast.py:50`) |
| Toast min/max width | `240px / 480px` | `_MIN_WIDTH=240, _MAX_WIDTH=480` (`toast.py:20-21`) |
| Toast Y offset | `32px` | `_BOTTOM_OFFSET=32` (`toast.py:23`) |
| Splitter 30/70 initial | `360/840` at 1200px | `setSizes([360, 840])` (`main_window.py:76`) |
| Recently Played label left padding | `16px` | `setContentsMargins(16, 0, 16, 4)` (`station_list_panel.py:75`) |

No arbitrary pixel values outside the spacing scale (4/8/16/24px tokens). No CSS `px` literals in Python code beyond spec-declared exceptions.

---

### Pillar 6: Experience Design (3/4)

**Passing:**
- Connecting toast shown on station activation — provides immediate feedback (`main_window.py:124`)
- Failover handling: "Stream failed, trying next…" and "Stream exhausted" distinguish between partial and total failure (`main_window.py:128-132`)
- Offline state: "Channel offline" toast with playing state cleared (`main_window.py:135-137`)
- Playback error: truncated at 80 chars to prevent UI overflow (`main_window.py:141`)
- Stale cover art responses discarded via token comparison (`now_playing_panel.py:323-326`)
- Junk ICY title guard (`is_junk_title`) prevents garbage from triggering cover fetches
- Volume persisted on `sliderReleased` (not `valueChanged` — avoids SQLite write spam)
- Volume restores from repo on construction (`now_playing_panel.py:196-202`)
- ICY label uses `Qt.PlainText` — prevents rich-text injection from malicious stream metadata
- Toast reuse: existing instance re-shows cleanly during fade-out without flicker
- Click-through toast (`WA_TransparentForMouseEvents`) — does not block interaction
- `WA_ShowWithoutActivating` — toast never steals keyboard focus
- Provider group rows non-selectable (D-03) — prevents meaningless selections

**Issues:**
- **Stop button always enabled** (`now_playing_panel.py:158-170`). Spec Interaction States table: `Stop button | any | disabled state when nothing is playing (setEnabled(False))`. Currently the button is always enabled. A user with no station playing can click Stop, which calls `player.stop()` and clears the now-playing panel — including `self._station = None` and clearing labels — even when there was nothing to stop.

- **No station list empty state** (`station_list_panel.py`). If `repo.list_stations()` returns `[]`, the tree is silently empty — no heading, no body copy, no visual affordance. Spec requires this state to be covered. Without it, a new user sees a blank panel with no guidance.

- **No "No stations yet" empty state for recently played section either.** If `repo.list_recently_played(3)` returns `[]`, `recent_view` renders as an empty list widget. This is a minor secondary issue — the primary recently-played UI still shows the tree which dominates.

---

## Registry Safety

Not applicable — PySide6 desktop application with no component registry. `components.json` does not exist. No third-party registries used.

---

## Files Audited

- `musicstreamer/ui_qt/main_window.py`
- `musicstreamer/ui_qt/now_playing_panel.py`
- `musicstreamer/ui_qt/station_list_panel.py`
- `musicstreamer/ui_qt/station_tree_model.py`
- `musicstreamer/ui_qt/toast.py`
- `.planning/phases/37-station-list-now-playing/37-UI-SPEC.md`
- `.planning/phases/37-station-list-now-playing/37-CONTEXT.md`
- `.planning/phases/37-station-list-now-playing/37-01-SUMMARY.md`
- `.planning/phases/37-station-list-now-playing/37-02-SUMMARY.md`
- `.planning/phases/37-station-list-now-playing/37-03-SUMMARY.md`
- `.planning/phases/37-station-list-now-playing/37-04-SUMMARY.md`
