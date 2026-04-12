---
phase: 38
slug: filter-strip-favorites
status: draft
shadcn_initialized: false
preset: none
created: 2026-04-12
---

# Phase 38 — UI Design Contract

> Visual and interaction contract for filter strip, favorites view, and star button additions. All design tokens inherited from Phase 37 — this document extends, not replaces, the Phase 37 contract.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (desktop Qt app — shadcn N/A) |
| Preset | not applicable |
| Component library | PySide6 widgets; new: FlowLayout (custom), QButtonGroup-backed segmented control |
| Icon library | Adwaita symbolic SVGs via `:/icons/` resource — new icons listed under Assets |
| Font | Qt application default (inherited from Phase 37 — no family override) |
| Style direction | Qt-native flat, identical to Phase 37. Targeted QSS only for chip selected state and segmented control button pressed state. |

---

## Spacing Scale

Inherited from Phase 37. No new tokens added.

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Chip-to-chip horizontal gap in FlowLayout; icon-to-label gap in favorite rows |
| sm | 8px | Chip inner horizontal padding (each side); search box vertical margin within filter strip; FlowLayout row-to-row vertical gap |
| md | 16px | Filter strip outer left/right margin (matches now-playing panel margin); segmented control bottom margin |
| lg | 24px | Vertical gap between segmented control and search box (intentional breathing room) |
| xl | 32px | Not used this phase |

**Chip inner padding:** 8px horizontal × 4px vertical (sm × xs — tighter pill aesthetic, non-scale mix permitted for chip specifically).

**Segmented control height:** 32px (matches provider group header height for visual consistency).

**Star button size:** 28 × 28px (`setIconSize(QSize(20, 20))`) — smaller than play/pause (36×36) since it is a secondary action.

**Search box:** system default height (`QLineEdit` default); no fixed height override. 16px left/right margin matches filter strip outer margin.

---

## Typography

Inherited from Phase 37. Roles reused in Phase 38 widgets:

| Role | Size | Weight | Line Height | Phase 38 Usage |
|------|------|--------|-------------|----------------|
| Body | 10pt | 400 (Normal) | default | Chip label text; search box placeholder and input text; favorite track row text |
| Label | 9pt | 400 (Normal) | default | Favorites section sub-headers ("Favorite Stations", "Favorite Tracks") |
| Heading | 13pt | 600 (DemiBold) | default | Not used in new widgets this phase |
| Display | 16pt | 600 (DemiBold) | default | Favorites empty state heading only |

**Chip text:** 10pt Normal. Chips are small pill elements; DemiBold would be visually heavy.

**Segmented control button text:** 10pt Normal. Pressing adds no weight change — only background changes (see Interaction States).

---

## Color

Palette inherited from Phase 37 (QPalette roles; no hardcoded hex except toast and the two new additions below).

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `QPalette.Window` | Filter strip background; favorites view background |
| Secondary (30%) | `QPalette.Base` | Search box (`QLineEdit`) background; chip unselected background |
| Accent (10%) | `QPalette.Highlight` | **Newly reserved for:** (5) selected chip fill, (6) active segmented control button fill, (7) star button filled-star icon tint. Existing reservations 1–4 from Phase 37 unchanged. |
| Destructive | not used this phase | Trash icon in favorites uses `QPalette.Text` (neutral) — no destructive color since removal has no permanent consequence (favorites can be re-added) |

**Accent reserved for (cumulative, Phase 37 + 38):**
1. Selected station row in the tree view (`QPalette.Highlight`)
2. `QSlider` filled groove (volume)
3. Play/pause `QToolButton` pressed/checked visual
4. Keyboard focus indicators (Qt default)
5. Selected chip fill color (new — Phase 38)
6. Active segmented control button fill (new — Phase 38)
7. Filled star icon tint when favorited (new — Phase 38)

**Chip QSS (unselected):**
```css
QPushButton[chipState="unselected"] {
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 12px;
    padding: 4px 8px;
}
```

**Chip QSS (selected):**
```css
QPushButton[chipState="selected"] {
    background-color: palette(highlight);
    color: palette(highlighted-text);
    border: 1px solid palette(highlight);
    border-radius: 12px;
    padding: 4px 8px;
}
```

**Segmented control QSS — active button:**
```css
QPushButton[segState="active"] {
    background-color: palette(highlight);
    color: palette(highlighted-text);
    border-radius: 4px;
}
```

**Segmented control QSS — inactive button:**
```css
QPushButton[segState="inactive"] {
    background-color: transparent;
    color: palette(button-text);
    border-radius: 4px;
}
```

Use `setProperty("chipState", "selected")` + `style().unpolish(widget)` + `style().polish(widget)` to trigger QSS re-evaluation on toggle.

---

## Copywriting Contract

### Filter Strip

| Element | Copy |
|---------|------|
| Search box placeholder | `Search stations…` |
| Search box clear button tooltip | `Clear search` |
| "Clear all" filters button tooltip | `Clear all filters` |
| Provider chip label | `{provider_name}` — exact value from DB, no truncation in chip label |
| Tag chip label | `{tag}` — exact value from DB |
| Filter strip — no chips available (no stations in DB) | strip is hidden; empty state handled at station list level |

### Segmented Control

| Element | Copy |
|---------|------|
| Stations tab | `Stations` |
| Favorites tab | `Favorites` |

### Favorites View

| Element | Copy |
|---------|------|
| Favorite stations section header | `Favorite Stations` |
| Favorite tracks section header | `Favorite Tracks` |
| Favorites empty state heading (no starred stations or tracks) | `No favorites yet` |
| Favorites empty state body | `Star a station or track to save it here.` |
| Favorite stations section — no starred stations (but tracks exist) | `No favorite stations.` (inline, label role) |
| Favorite tracks section — no starred tracks (but stations exist) | `No favorite tracks.` (inline, label role) |
| Favorite track row format | `{track_title} — {station_name}` |
| Trash button tooltip (remove favorite track) | `Remove from favorites` |
| Station star in tree — unstarred tooltip | `Add to favorites` |
| Station star in tree — starred tooltip | `Remove from favorites` |

### Toast — Star Actions

| Trigger | Copy |
|---------|------|
| Track starred | `Saved to favorites` |
| Track unstarred | `Removed from favorites` |
| Station starred | `Station added to favorites` |
| Station unstarred | `Station removed from favorites` |

### Star Button (Now-Playing Panel)

| State | Tooltip |
|-------|---------|
| No station playing | button disabled; no tooltip |
| Station playing, no ICY title | button disabled; tooltip `No track to favorite` |
| ICY title available, not favorited | `Save track to favorites` |
| ICY title available, already favorited | `Remove track from favorites` |

**Copywriting rules (inherited from Phase 37):**
- U+2026 `…` not three dots.
- Sentence case. No title case. No UPPERCASE. No emoji.
- Em dash `—` in favorite track row format (`{title} — {station}`).

---

## Component Inventory (Phase 38 additions)

| Widget | Size | Notes |
|--------|------|-------|
| Segmented control container | full panel width × 32px | `QHBoxLayout` wrapping two `QPushButton`s in a `QButtonGroup(exclusive=True)`; 16px left/right margin |
| Each segmented button | 50% of container width | `setSizePolicy(QExpanding, QFixed)` |
| Search box (`QLineEdit`) | full panel width − 32px margins | System default height; clear action via `setClearButtonEnabled(True)` (Qt built-in) |
| FlowLayout container | full panel width − 32px margins | Wraps chip rows; top-level `QWidget` with `FlowLayout` set as its layout |
| Chip (`QPushButton`) | min 48px wide, fit-to-label + 16px (2×8px padding) | `setCheckable(True)` driven by `QButtonGroup(exclusive=False)` per dimension |
| Chip height | 24px | Fixed: `setFixedHeight(24)` |
| Provider chip row | auto-wrapped by FlowLayout | One `QButtonGroup(exclusive=False)` for provider dimension |
| Tag chip row | auto-wrapped by FlowLayout | One `QButtonGroup(exclusive=False)` for tag dimension |
| "Clear all" button | fit-to-label | `QPushButton`, icon: `edit-clear-all-symbolic` or plain text `✕ Clear`; placed at trailing end of filter strip below chips |
| Star button (now-playing) | 28 × 28px | `QToolButton`, `setIconSize(QSize(20, 20))`, `setCheckable(True)`, inserted at `# Plan 38: insert star button here` in `now_playing_panel.py` |
| Station star button (tree row) | 20 × 20px | Rendered via custom item delegate — visible always (not hover-only); right-aligned in row, after station name elision; `QStyleOptionButton` painted in delegate |
| Favorites view container | fills station list panel below segmented control | `QStackedWidget` slot; shown when Favorites tab active |
| Favorite stations list | full width, rows 40px | `QListWidget` with no provider grouping (flat list); same logo+name layout as station tree rows |
| Favorite tracks list | full width, rows 40px | `QListWidget`; each row: text left-aligned (`{title} — {station}`), trash `QToolButton` right-aligned via item widget |
| Favorites section separator | 1px `QFrame.HLine` | Between Favorite Stations list and Favorite Tracks list; same style as Phase 37 recently-played separator |
| Favorites section sub-header | full width, 24px tall | `QLabel` at 9pt, 8px left padding, `QPalette.Text` color |

---

## Layout Contracts

### Updated StationListPanel (Phase 38)

```
StationListPanel (QWidget)
├── QVBoxLayout (0px margins, 0px spacing)
│   ├── Segmented control row (QHBoxLayout, 16px L/R margins, 8px top, 8px bottom)
│   │   ├── "Stations" QPushButton [50%]
│   │   └── "Favorites" QPushButton [50%]
│   │
│   ├── [STATIONS MODE — QStackedWidget page 0]
│   │   ├── Search QLineEdit (16px L/R margins, 4px top, 4px bottom)
│   │   ├── FlowLayout container (16px L/R margins, 4px top, 8px bottom)
│   │   │   ├── Provider chips (QButtonGroup, OR-within)
│   │   │   └── Tag chips (QButtonGroup, OR-within)
│   │   ├── "Clear all" QPushButton (right-aligned, 16px right margin, 4px bottom)
│   │   ├── RecentlyPlayedSection [max 160px]
│   │   ├── QFrame.HLine (separator)
│   │   └── QTreeView (QSortFilterProxyModel over StationTreeModel) [stretch]
│   │
│   └── [FAVORITES MODE — QStackedWidget page 1]
│       ├── "Favorite Stations" QLabel [9pt, 8px top/left]
│       ├── QListWidget — starred stations [40px rows, stretch]
│       ├── QFrame.HLine (separator)
│       ├── "Favorite Tracks" QLabel [9pt, 8px top/left]
│       └── QListWidget — track favorites [40px rows, stretch]
```

**Filter strip visibility:** The search box, FlowLayout container, and "Clear all" button are on QStackedWidget page 0 (Stations mode). Switching to Favorites hides them entirely via the stack — no `setVisible()` calls needed.

**Chip ordering within rows:** Alphabetical by label text. Consistent and predictable; no dynamic reordering by usage count.

### Now-Playing Panel Control Row (updated)

```
Control row QHBoxLayout (8px spacing)
├── Play/pause QToolButton [36×36]
├── Stop QToolButton [36×36]
├── Volume QSlider [120×24]
└── Star (track) QToolButton [28×28]    ← NEW, right of volume
```

### Station Tree Row (updated delegate)

```
[32×32 logo][4px gap][station name, elided][stretch][20×20 star button]
```

Star is right-aligned in the row, always visible (not hover-only). This matches v1.5 behavior and avoids interaction discoverability issues on desktop.

---

## Interaction States

### Segmented Control

| State | Visual |
|-------|--------|
| Stations active | Stations button: `segState="active"` (highlight fill, highlighted-text color); Favorites button: `segState="inactive"` (transparent) |
| Favorites active | Reverse of above |
| Button press | Immediate — no animation |

### Chips

| State | Visual |
|-------|--------|
| Unselected | `chipState="unselected"` — `QPalette.Base` fill, `QPalette.Mid` border |
| Selected | `chipState="selected"` — `QPalette.Highlight` fill, `QPalette.HighlightedText` text |
| Hover (unselected) | Qt default hover on `QPushButton` — slight lightening via Fusion; no custom QSS |
| Toggle | Immediate — no animation |

### Star Button (now-playing, track favorite)

| State | Visual |
|-------|--------|
| Disabled (no station / no ICY title) | `setEnabled(False)` — Qt dims icon automatically |
| Enabled, not favorited | `bookmark-new-symbolic` (outline star); `setChecked(False)` |
| Enabled, favorited | `starred-symbolic` (filled star); `setChecked(True)` |
| On click | Toggle immediately; fire toast; call `repo.add_favorite()` or `repo.remove_favorite()` |

### Station Star (tree row delegate)

| State | Visual |
|-------|--------|
| Station not favorited | `non-starred-symbolic` (outline); painted at 20×20 right-aligned in row |
| Station favorited | `starred-symbolic` (filled); same position |
| On click | Toggle immediately; fire toast; update DB; refresh favorites view if active |

### Search Box

| State | Visual |
|-------|--------|
| Empty | Shows placeholder `Search stations…` |
| Has text | Qt built-in clear (✕) button appears at trailing end (`setClearButtonEnabled(True)`) |
| On text change | `QSortFilterProxyModel.setFilterFixedString()` called immediately (no debounce — station counts are small, filtering is fast) |

### Favorites View — Trash Button

| State | Visual |
|-------|--------|
| Default | `user-trash-symbolic` icon, 24×24px `QToolButton`, right edge of row |
| On click | Remove immediately from DB via `repo.remove_favorite()`; remove row from `QListWidget`; no confirmation dialog (not destructive enough to warrant it — D-10 toast confirms) |
| Post-remove | Toast: `Removed from favorites` |

---

## Filter Composition Logic

| Condition | Behavior |
|-----------|----------|
| Search text only | Show stations where `station.name` contains text (case-insensitive) |
| Provider chips only | Show stations where `station.provider_name` is in selected providers |
| Tag chips only | Show stations where any tag in `station.tags.split(",")` is in selected tags |
| Search + provider chips | AND: both conditions must match |
| Search + tag chips | AND: both conditions must match |
| Multiple provider chips selected | OR within provider dimension |
| Multiple tag chips selected | OR within tag dimension |
| Provider + tag chips | AND between dimensions, OR within each |
| "Clear all" clicked | Reset `QLineEdit.clear()`; uncheck all `QButtonGroup` buttons; `QSortFilterProxyModel` reset |

`QSortFilterProxyModel` subclass (`StationFilterProxyModel`) overrides `filterAcceptsRow()` to implement multi-dimension logic. Search text + chip selections are stored as instance attributes on the proxy; all three inputs trigger `invalidateFilter()`.

---

## Assets to Add This Phase

New SVG icons required (Adwaita symbolic set). After adding, rerun `pyside6-rcc` and commit `icons_rc.py`.

| Icon name | Usage |
|-----------|-------|
| `starred-symbolic.svg` | Filled star — favorited state (track + station) |
| `non-starred-symbolic.svg` | Outline star — unfavorited state (track + station) |
| `user-trash-symbolic.svg` | Trash button in favorite tracks list |
| `edit-clear-all-symbolic.svg` | "Clear all" filters button (optional; may use plain text label if icon unavailable) |

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none — not applicable to desktop Qt | not required |
| third-party | none | not required |

FlowLayout is authored in-repo (based on the Qt examples FlowLayout pattern, not pulled from an external registry). No third-party component registries exist for PySide6.

---

## Out of Scope (Design Contract)

Explicitly NOT specified here — these are Phase 39+ concerns:

- Edit icon on now-playing panel
- EditStationDialog layout
- Stream picker dropdown
- DiscoveryDialog, ImportDialog
- Accent color picker (UI-11) — chip selected color uses system `QPalette.Highlight` this phase
- Hamburger menu
- Any MPRIS/SMTC integration

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS (N/A — no registries)

**Approval:** pending
