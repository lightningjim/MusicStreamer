# Phase 37: Station List + Now Playing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-11
**Phase:** 37-station-list-now-playing
**Areas discussed:** Station list widget, Now-playing layout, Toast overlay, Phase 37 control scope, YouTube 16:9 thumbnail
**User response:** "defaults" across the board

---

## Gray Areas

### 1. Station list widget strategy

| Option | Description | Selected |
|--------|-------------|----------|
| (a) QTreeView + QAbstractItemModel | Native Qt MVC; provider groups top-level, stations children; scales cleanly; filter-friendly via QSortFilterProxyModel (recommended default) | ✓ |
| (b) QTreeWidget | Simpler non-MVC cousin; less upfront code, harder to extend | |
| (c) Custom ExpanderSection widget | Closest match to v1.5 Adwaita aesthetic but more code and worse selection/keyboard nav | |

**User's choice:** defaults → (a)

### 2. Now-playing panel layout

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Match v1.5 three-column exactly | QHBoxLayout [logo | info+controls | cover art] — familiar mental model (recommended default) | ✓ |
| (b) Vertical stack | Simpler for narrow windows but bigger visual change | |
| (c) Responsive | Horizontal on wide, vertical on narrow — overkill | |

**User's choice:** defaults → (a)

### 3. Toast overlay implementation

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Custom ToastOverlay widget | Frameless QWidget with QPropertyAnimation + QTimer; reusable for Phases 38–40 (recommended default) | ✓ |
| (b) QStatusBar.showMessage | Built-in but ugly; looks like status bar not toast | |
| (c) Third-party library | Adds a dep | |

**User's choice:** defaults → (a)

### 4. Phase 37 control-row scope

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Port only 37-ready controls | Play/pause, stop, volume slider only; star/edit/stream-picker deferred to later phases (recommended default) | ✓ |
| (b) All buttons as stubs | All visible, non-37 buttons show "coming soon" toast on click | |
| (c) Ship all functional | Pull forward favorites/edit/stream-picker from later phases — bigger scope | |

**User's choice:** defaults → (a)

### 5. YouTube 16:9 thumbnail handling (UI-14)

| Option | Description | Selected |
|--------|-------------|----------|
| (a) QPixmap.scaled + KeepAspectRatio in 160×160 slot | Matches v1.5 ContentFit.CONTAIN semantics; letterboxes cleanly (recommended default) | ✓ |
| (b) Separate 160×90 slot for YouTube | Dynamic layout logic required | |

**User's choice:** defaults → (a)

---

## Claude's Discretion

- Splitter initial ratio (30/70 left/right is a starting suggestion)
- QTreeView QSS styling — rounded corners or flat
- Elapsed timer label format (`0:00` vs `00:00`)
- Toast animation timing (150/3000/300 ms fade-in/hold/fade-out is reasonable)
- Station row height
- Keyboard shortcuts (defer)

## Deferred Ideas

- Search box + filter chips → Phase 38 (UI-03)
- Favorites view + star button → Phase 38 (UI-04)
- EditStationDialog + edit icon → Phase 39 (UI-05)
- Stream picker dropdown → Phase 39 (UI-13)
- DiscoveryDialog, ImportDialog → Phase 39 (UI-06, UI-07)
- Auth dialogs + accent + hamburger → Phase 40 (UI-08..UI-11)
- Window geometry persistence → future QoL phase
- Keyboard shortcuts → deferred
- Drag-to-reorder / right-click context menu → future enhancement (not v2.0)
</content>
</invoke>
