# Phase 39: Core Dialogs - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-13
**Phase:** 39-core-dialogs
**Areas discussed:** EditStation dialog, Discovery dialog, Import dialog, Stream picker

---

## EditStation Dialog

### Dialog Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Single dialog | One QDialog with all fields: name, URL, provider picker, tag chips, ICY toggle, stream management table, delete button. Matches v1.5's single-window approach but flattened. | ✓ |
| Main + sub-dialog | EditStationDialog for basic fields. Separate ManageStreamsDialog for multi-stream CRUD. Mirrors v1.5's two-dialog pattern. | |

**User's choice:** Single dialog
**Notes:** Simplifies the flow vs. v1.5's two-dialog approach.

### Multi-Stream Management

| Option | Description | Selected |
|--------|-------------|----------|
| Table + buttons | QTableWidget rows showing URL, quality, codec, position. Add/Remove/Move Up/Move Down buttons. Quality presets via QComboBox per row. | ✓ |
| Inline list with drag | QListWidget with drag-to-reorder. Custom widget per row. More compact but drag reorder is fiddly in Qt. | |

**User's choice:** Table + buttons
**Notes:** None

### Provider Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Editable combo | QComboBox with setEditable(True). Shows existing providers, user can type new. Typed value takes precedence. | ✓ |
| Combo + separate field | Read-only QComboBox + separate QLineEdit for new provider. Clearer separation but more UI surface. | |

**User's choice:** Editable combo
**Notes:** None

### Tag Editor

| Option | Description | Selected |
|--------|-------------|----------|
| FlowLayout chips | Reuse Phase 38's FlowLayout. Toggleable chips for existing tags. QLineEdit + Add for new tags. | ✓ |
| Comma text field | Simple QLineEdit with comma-separated tags. Minimal but loses visual feedback. | |

**User's choice:** FlowLayout chips
**Notes:** None

---

## Discovery Dialog

### Dialog Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Search bar + table | Top: search field + tag/country combos + Search button. Bottom: QTableView with results. Per-row Preview and Save buttons. | ✓ |
| Split pane | Left: filter panel. Right: scrollable result cards. More visual but heavier. | |

**User's choice:** Search bar + table
**Notes:** None

### Preview Playback

| Option | Description | Selected |
|--------|-------------|----------|
| Inline play button | Per-row play/stop toggle in results table. Uses main Player. Stops any currently-playing station. | ✓ |
| Separate mini-player | Small preview bar at dialog bottom. Needs second Player instance. | |

**User's choice:** Inline play button
**Notes:** None

---

## Import Dialog

### Tab Structure

| Option | Description | Selected |
|--------|-------------|----------|
| QTabWidget | Standard QTabWidget with YouTube and AudioAddict tabs. Each tab has its own layout. | ✓ |
| Stacked pages | Initial chooser leading to full-page flows. Wizard-like but adds navigation complexity. | |

**User's choice:** QTabWidget
**Notes:** None

### Progress Feedback

| Option | Description | Selected |
|--------|-------------|----------|
| Inline progress bar | QProgressBar + status label within each tab. Determinate for import, indeterminate for fetch. | ✓ |
| Toast-only feedback | No in-dialog progress. Toast on completion. Simpler but no visibility during long imports. | |

**User's choice:** Inline progress bar
**Notes:** None

### YouTube Scan Results

| Option | Description | Selected |
|--------|-------------|----------|
| Checklist | Checkable list of live streams found. User picks which to import. Matches v1.5 and ROADMAP. | ✓ |
| Auto-import all | Scan and immediately import all. Simpler but less control. | |

**User's choice:** Checklist
**Notes:** None

---

## Stream Picker

### Widget Choice

| Option | Description | Selected |
|--------|-------------|----------|
| QComboBox | Standard QComboBox showing current stream label/quality. Dropdown lists all streams. Hidden for single-stream stations. | ✓ |
| Icon button + popup | Small icon button with popup menu. More compact but less discoverable. | |

**User's choice:** QComboBox
**Notes:** None

### Failover Sync

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, sync selection | Combo box auto-updates on failover signal. Uses blockSignals to avoid re-triggering play. | ✓ |
| No, manual only | Picker only changes on user action. May show stale selection after failover. | |

**User's choice:** Yes, sync selection
**Notes:** None

---

## Claude's Discretion

- Dialog dimensions, table column widths, field ordering
- Loading indicator style, stream table styling
- Whether to show station art preview in edit dialog

## Deferred Ideas

None — discussion stayed within phase scope.
