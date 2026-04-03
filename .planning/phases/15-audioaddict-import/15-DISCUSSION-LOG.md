# Phase 15: AudioAddict Import - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-03
**Phase:** 15-audioaddict-import
**Areas discussed:** Entry point, API key persistence, Network selection, Quality picker UI

---

## Entry Point

| Option | Description | Selected |
|--------|-------------|----------|
| Unified Import dialog | One 'Import' button opens a tabbed dialog: YouTube \| AudioAddict | ✓ |
| Separate button | New 'AudioAddict' button alongside 'Import' in header bar | |
| Import menu | Turn 'Import' into Gtk.MenuButton with sub-items per source | |

**User's choice:** Unified Import dialog — single button, tabbed dialog with YouTube and AudioAddict tabs.
**Notes:** Keeps the header bar clean; mirrors the existing ImportDialog structure.

---

## API Key Persistence

| Option | Description | Selected |
|--------|-------------|----------|
| Save in SQLite | Store in app DB alongside volume setting; pre-fills on reopen | ✓ |
| Enter each time | No persistence; user pastes key every session | |
| Save in config file | Write to ~/.config/musicstreamer/ plain text file | |

**User's choice:** Save in SQLite.
**Notes:** Consistent with how volume is persisted in the existing repo settings pattern.

---

## Network Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Import all networks | Single import action; no network picker step | ✓ |
| Checklist of networks | Show known networks with checkboxes before import | |
| You decide | Claude picks the approach | |

**User's choice:** Import all networks at once.
**Notes:** Minimal flow — users can delete unwanted stations after import.

---

## Quality Picker UI

| Option | Description | Selected |
|--------|-------------|----------|
| Adw.ToggleGroup | Hi \| Med \| Low toggle buttons; matches Stations/Favorites pattern | ✓ |
| Gtk.DropDown | Compact dropdown selector | |
| You decide | Claude picks based on existing patterns | |

**User's choice:** Adw.ToggleGroup.
**Notes:** Consistent with existing toggle group usage in the app.

---

## Claude's Discretion

- Exact AudioAddict API endpoint and network slug list (researcher must verify)
- Invalid/expired API key error handling (inline error label)
- Whether quality preference persists alongside API key
- Dialog widget hierarchy within tabbed structure
- How ImportDialog is refactored to accommodate tabs

## Deferred Ideas

None.
