---
phase: 37
slug: station-list-now-playing
status: draft
shadcn_initialized: false
preset: none
created: 2026-04-11
---

# Phase 37 — UI Design Contract

> Visual and interaction contract for the first visual-content phase of v2.0. Ports v1.5 core playback UI (station list + now-playing + toast) to Qt/PySide6. Faithful-to-v1.5 intent, Qt-native execution.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (desktop Qt app — shadcn N/A) |
| Preset | not applicable |
| Component library | PySide6 widgets (QTreeView, QSplitter, QToolButton, QSlider, QLabel) |
| Icon library | Adwaita symbolic SVGs bundled via `:/icons/` resource + `QIcon.fromTheme(name, fallback)` (Linux theme wins, Windows uses bundled) |
| Font | Qt application default (Fusion default on Windows; system default on Linux via adwaita-qt — typically Cantarell or Noto Sans) |
| Style direction | **Qt-native flat** — no global QSS override. Targeted QSS only for (a) toast background, (b) recently-played section separator. Rationale: Fusion dark palette already set on Windows (Phase 36 PORT-07); adwaita-qt handles Linux; bespoke QSS is a Windows regression risk and `Claude's Discretion` D-23 allows this call. |

---

## Spacing Scale

Declared values (multiples of 4):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px  | Icon-to-label gap in station rows; control row inter-button gap |
| sm | 8px  | Inner padding on now-playing labels; tree-view row vertical padding |
| md | 16px | Now-playing panel outer margins; main splitter handle visual breathing room; toast inner padding |
| lg | 24px | Now-playing three-column gaps (logo ↔ center ↔ cover art) |
| xl | 32px | Reserved — not used this phase |

**Station list tree-view row height:** 40px (32px logo + 4px top + 4px bottom).
**Now-playing panel outer margins:** `QHBoxLayout.setContentsMargins(16, 16, 16, 16)`.
**Now-playing center-column vertical spacing:** 8px between Name·Provider label, ICY title, elapsed timer, and control row.
**Control row inter-widget spacing:** 8px between play/pause, stop, volume slider.
**Toast inner padding:** 12px horizontal, 8px vertical (non-scale exception — tight toast aesthetic).

Exceptions: 12px toast padding (tighter than 16px for visual weight).

---

## Typography

Qt on Linux/Windows inherits the OS default font family. Sizes declared in **points (pt)** because Qt widgets scale by point size, not pixels.

| Role | Size | Weight | Line Height | Usage |
|------|------|--------|-------------|-------|
| Body | 10pt | 400 (Normal) | default | Station list row names; volume slider tooltip; toast body; elapsed timer label |
| Label | 9pt  | 400 (Normal) | default | `Name · Provider` subtitle; provider group count suffix `(N)` |
| Heading | 13pt | 600 (DemiBold) | default | ICY track title in now-playing center column; provider group headers in station tree |
| Display | 16pt | 600 (DemiBold) | default | Reserved for empty-state headline only |

**Font count:** 4 roles, 2 weights (Normal 400 + DemiBold 600). No italics. No third weight.

**Implementation:**
- Use `QFont` with `QFont.setPointSize(N)` + `QFont.setWeight(QFont.Normal | QFont.DemiBold)`.
- Do NOT hardcode a family — let Qt/adwaita-qt/Fusion pick the system default.
- Elapsed timer uses `QFont.setStyleHint(QFont.TypeWriter)` for tabular digits so seconds don't jitter width as they tick. This is the one family override allowed.

**Elapsed timer format:** `M:SS` below 1 hour (e.g. `3:42`), `H:MM:SS` at or above 1 hour (e.g. `1:02:17`). No leading zero on the first field. Updates on every `player.elapsed_updated[int]` tick (1Hz).

---

## Color

No custom palette — inherits Fusion (Windows) / adwaita-qt (Linux) system palette. 60/30/10 framing uses `QPalette` roles:

| Role | Value (Fusion dark) | Usage |
|------|------|-------|
| Dominant (60%) | `QPalette.Window` — `#353535` on dark, system default on light | Central widget background; both panels' base surface |
| Secondary (30%) | `QPalette.Base` — `#191919` on dark | `QTreeView` viewport background; provider group header row (slightly lighter via `QPalette.AlternateBase` `#353535`) |
| Accent (10%) | `QPalette.Highlight` — `#2A82DA` on dark Fusion; system accent on Linux | **Reserved exclusively for:** (1) selected station row in `QTreeView`, (2) volume slider groove fill, (3) play/pause button pressed state, (4) focus ring on keyboard-focused widgets |
| Destructive | not used this phase | — |

**Accent reserved for:**
1. Selected station row in the tree view (`QPalette.Highlight`)
2. `QSlider` filled groove (volume)
3. Play/pause `QToolButton` pressed/checked visual
4. Keyboard focus indicators (Qt default — do not disable)

Explicitly **not** accent-colored: ICY title text, station names, provider headers, elapsed timer, cover art borders, toast background.

**Toast background:** Semi-transparent dark — `rgba(40, 40, 40, 220)` with 8px border-radius and white text. This is the ONE hardcoded color in the QSS surface and must work on both dark and light Fusion because the toast is an overlay with its own visual weight.

**Toast QSS (the only stylesheet in this phase):**
```css
QLabel#ToastLabel {
    background-color: rgba(40, 40, 40, 220);
    color: white;
    border-radius: 8px;
    padding: 8px 12px;
}
```

**Recently-played separator:** 1px horizontal line via `QFrame.HLine` + `QFrame.Sunken`. No custom color — inherits `QPalette.Mid`.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA (play/pause tooltip) | `Play` when paused/stopped; `Pause` when playing |
| Stop button tooltip | `Stop` |
| Volume slider tooltip | `Volume: {N}%` (dynamic) |
| Station list empty heading | `No stations yet` |
| Station list empty body | `Use the Import or Discover dialog to add stations.` (Phase 37 note: dialogs ship in Phase 39 — this copy points forward; acceptable per user's "port faithfully" instinct) |
| Recently played section header | `Recently Played` |
| Provider group header format | `{provider_name} ({station_count})` — e.g. `SomaFM (12)` |
| Now-playing idle state (no station selected) | Station name label: empty; ICY title label: `No station playing`; elapsed: `0:00`; cover art: app-icon placeholder |
| Toast — connecting | `Connecting…` (U+2026 ellipsis, not `...`) |
| Toast — failover to next stream | `Stream failed, trying next…` |
| Toast — all streams exhausted | `Stream exhausted` |
| Toast — Twitch channel offline | `Channel offline` |
| Toast — generic playback error | `Playback error: {message}` (message from `player.playback_error[str]`, truncated to 80 chars with `…` suffix if longer) |
| Destructive confirmation | none — Phase 37 has no destructive actions (delete is Phase 39) |

**Copywriting rules:**
- Use U+2026 `…` not three dots.
- Use U+00B7 `·` (middle dot) as separator in `Name · Provider` — matches v1.5.
- Sentence case for buttons and labels. Not title case. Not UPPERCASE.
- No emoji in UI copy (per user's global directive).

---

## Component Inventory (Phase 37)

Fixed-size widgets and their exact pixel contracts:

| Widget | Size | Notes |
|--------|------|-------|
| `QSplitter` main layout | 30% left / 70% right initial | `QSplitter(Qt.Horizontal)`, not persisted (D-06) |
| `MainWindow` default size | 1200 × 800 | Inherited from Phase 36 scaffold |
| Station list panel min width | 280px | Prevents collapse below readable width |
| Now-playing panel min width | 560px | Keeps 3-column layout viable |
| Station row logo | 32 × 32 px | `QIcon` at `setIconSize(QSize(32, 32))` |
| Station row height | 40px | `QTreeView.setUniformRowHeights(True)` |
| Provider group header height | 32px | Standard tree row |
| Recently-played section max height | 160px | Caps at ~4 rows; scrolls if more (Phase 37 only ever shows top-3 per D-02) |
| Now-playing logo column | 180 × 180 px fixed | `QLabel.setFixedSize(180, 180)`, `setScaledContents(False)`, scale via `QPixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)` |
| Now-playing cover art slot | 160 × 160 px fixed | `QLabel.setFixedSize(160, 160)`, YouTube letterboxed per D-16 |
| Play/pause `QToolButton` | 36 × 36 px | `setIconSize(QSize(24, 24))`, `setToolButtonStyle(Qt.ToolButtonIconOnly)` |
| Stop `QToolButton` | 36 × 36 px | Same as play/pause |
| Volume `QSlider` | 120 × 24 px | `QSlider(Qt.Horizontal)`, fixed width, `setTickPosition(QSlider.NoTicks)` (D-08) |
| Toast overlay width | min 240px, max 480px, clamp to `min(centralWidget.width() - 64, 480)` | Bottom-center anchored |
| Toast overlay Y offset | 32px from bottom of central widget | Above status bar baseline |
| Toast overlay height | fit-to-content, ~36–52px typical | Depends on text wrap |

---

## Layout Contracts

### Main Window (centralWidget)
```
QSplitter (Qt.Horizontal)
├── StationListPanel (QWidget)           [30%, min 280px]
│   ├── RecentlyPlayedSection (QListView or QWidget stack)   [max 160px tall]
│   ├── QFrame.HLine (sunken, 1px)       [separator]
│   └── QTreeView (stations by provider)  [stretch]
└── NowPlayingPanel (QWidget)             [70%, min 560px]
    └── QHBoxLayout (16px margin, 24px spacing)
        ├── Station logo QLabel           [180×180 fixed]
        ├── Center QVBoxLayout (stretch, 8px spacing)
        │   ├── "Name · Provider" QLabel  [9pt, label role]
        │   ├── ICY title QLabel          [13pt DemiBold, heading role]
        │   ├── Elapsed timer QLabel      [10pt TypeWriter, body role]
        │   └── Control row QHBoxLayout (8px spacing)
        │       ├── Play/pause QToolButton [36×36]
        │       ├── Stop QToolButton       [36×36]
        │       └── Volume QSlider         [120×24]
        └── Cover art QLabel               [160×160 fixed]
```

### Station Row Layout (inside `QTreeView` via custom delegate or default rendering)
```
[32×32 logo][4px gap][station name, elided at right if > available width]
```
Elision: `Qt.ElideRight` via `QFontMetrics.elidedText()` if names overflow the available width. Provider group header adds `(N)` count suffix in the same label text, not a separate column.

### Recently-Played Section
```
QLabel "Recently Played"  [9pt label role, 8px top padding, 16px left padding]
QListView (or 3-row QWidget stack)  [row height 40px, same logo+name layout as station rows]
QFrame.HLine (1px sunken separator)  [8px vertical margin]
```

### Toast Overlay
- Parented to `MainWindow.centralWidget()` (not to status bar).
- Frameless `QLabel` with `objectName = "ToastLabel"` for QSS hook.
- Positioned via `move()` on `show()` and on `centralWidget.resizeEvent` re-anchor.
- Animation: fade-in 150ms, hold 3000ms, fade-out 300ms via `QPropertyAnimation(self, b"windowOpacity")`.
- `setAttribute(Qt.WA_TransparentForMouseEvents, True)` — clicks pass through.
- `setAttribute(Qt.WA_ShowWithoutActivating, True)` — does not steal focus.

---

## Interaction States

| Widget | State | Visual |
|--------|-------|--------|
| Station row | default | Normal palette |
| Station row | hover | `QPalette.AlternateBase` tint (Qt default) |
| Station row | selected | `QPalette.Highlight` bg + `QPalette.HighlightedText` fg |
| Station row | selected + playing | Same as selected (no extra indicator this phase — playing state is visible in the now-playing panel) |
| Play/pause button | paused/stopped | `media-playback-start-symbolic` icon |
| Play/pause button | playing | `media-playback-pause-symbolic` icon |
| Play/pause button | hover/pressed | Qt default (Fusion frame highlight) |
| Stop button | any | `media-playback-stop-symbolic` icon; disabled state when nothing is playing (`setEnabled(False)` — Qt default dims) |
| Volume slider | dragging | Live `player.set_volume()` + tooltip update |
| Cover art slot | no ICY title / junk title | Shows station logo scaled into slot (v1.5 fallback behavior) |
| Cover art slot | fetched cover | Shows iTunes result scaled to 160×160 |
| Cover art slot | YouTube station | Letterboxed 160×90 in 160×160 slot |

---

## Copy Localization

English-only (en-US) this phase. No i18n framework (`Qt.tr()`) introduced — v2.0 scope is port-only, and i18n was not in v1.5. All copy strings are plain Python literals in `musicstreamer/ui_qt/*.py`.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none — not applicable to desktop Qt | not required |
| third-party | none | not required |

This is a PySide6 desktop application. No component registry ecosystem exists. All widgets are first-party Qt classes or custom subclasses authored in this repository.

---

## Assets to Add This Phase

New files in `musicstreamer/ui_qt/icons/` (per D-15), all verbatim from Adwaita symbolic set + `icons.qrc` regeneration:

- `media-playback-start-symbolic.svg`
- `media-playback-pause-symbolic.svg`
- `media-playback-stop-symbolic.svg`
- `audio-x-generic-symbolic.svg` (station list fallback per D-04)

After adding: rerun `pyside6-rcc musicstreamer/ui_qt/icons.qrc -o musicstreamer/ui_qt/icons_rc.py` and commit the regenerated `icons_rc.py`.

---

## Out of Scope (Design Contract)

Explicitly NOT specified in this document — these are Phase 38+ concerns:

- Search box / filter chip styling
- Favorites segmented toggle
- Star button visual
- Edit icon visual
- Stream picker dropdown
- Any dialog layouts (EditStation, Discovery, Import, Accounts)
- Accent color picker presets
- Hamburger menu action layout

If the executor encounters any of these while implementing Phase 37, it is out-of-scope creep and must be rejected.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS (N/A — no registries)

**Approval:** pending
