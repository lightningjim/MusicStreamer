# Phase 13: Radio-Browser Discovery - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-31
**Phase:** 13-radio-browser-discovery
**Areas discussed:** Discovery dialog layout, Search & filter behavior, Preview playback, Save-to-library flow

---

## Discovery Dialog Layout

### Q1: Discovery UI approach

| Option | Description | Selected |
|--------|-------------|----------|
| Modal dialog | Separate window like station editor, with search + results inside | ✓ |
| Sidebar/panel | Inline panel alongside the station list (split view) | |
| Full-window overlay | Takes over the main window content area temporarily | |

**User's choice:** Modal dialog
**Notes:** Consistent with existing EditStationDialog pattern.

### Q2: Result display format

| Option | Description | Selected |
|--------|-------------|----------|
| Simple list rows | Adw.ActionRow with station name + subtitle (country, tags, bitrate) | ✓ |
| Richer rows | Name, country flag/label, codec/bitrate badge, tag chips per row | |
| You decide | Pick whatever works cleanly | |

**User's choice:** Simple list rows

---

## Search & Filter Behavior

### Q1: Search mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Submit-button search | User types query, hits Search/Enter to fetch results | |
| Live search with debounce | Results update as user types (~500ms delay) | ✓ |
| You decide | | |

**User's choice:** Live search with debounce

### Q2: Tag and country filtering

| Option | Description | Selected |
|--------|-------------|----------|
| Dropdown selectors | ComboRow for country, ComboRow for tag, pre-populated from API | ✓ |
| Text fields | User types country/tag as part of search query (single box) | |
| Chips below search | After first search, show available tags/countries from results as filter chips | |
| You decide | | |

**User's choice:** Dropdown selectors

---

## Preview Playback

### Q1: Preview vs current playback

| Option | Description | Selected |
|--------|-------------|----------|
| Stop current, play preview | Current stops, preview plays. Closing dialog doesn't auto-resume. | |
| Replace temporarily | Preview takes over, closing dialog resumes original station | ✓ |
| Play in parallel | Preview plays alongside current | |
| You decide | | |

**User's choice:** Replace temporarily — auto-resume on dialog close

### Q2: Preview trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Play button per row | Small play icon on each result row | ✓ |
| Click/activate the row | Single click starts preview | |
| You decide | | |

**User's choice:** Play button per row

---

## Save-to-Library Flow

### Q1: Provider assignment

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-assign "Radio-Browser" | All saved stations get "Radio-Browser" as provider | |
| Use station's homepage/network | Extract provider from Radio-Browser metadata | ✓ |
| Prompt user | Open edit dialog pre-filled so user can pick/set provider | |
| You decide | | |

**User's choice:** Use station's homepage/network from Radio-Browser metadata

### Q2: Duplicate URL handling

| Option | Description | Selected |
|--------|-------------|----------|
| Silently skip | Don't add, maybe show brief toast | |
| Block with error | Dialog tells user it's a duplicate | ✓ |
| You decide | | |

**User's choice:** Block with error message

---

## Claude's Discretion

- Radio-Browser API endpoint selection and query parameter mapping
- Tag/country dropdown population strategy
- ActionRow subtitle format
- Dialog sizing and widget hierarchy
- Error/empty state handling
- Preview button icon state (play vs stop when active)
- Provider name extraction from Radio-Browser metadata

## Deferred Ideas

None — discussion stayed within phase scope.
