# Phase 14: YouTube Playlist Import - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** 14-youtube-playlist-import
**Areas discussed:** Entry point, Provider assignment, Progress UX, Station naming

---

## Entry Point

| Option | Description | Selected |
|--------|-------------|----------|
| Separate header button | Add 'Import' next to 'Discover' in header bar | ✓ |
| From Discover dialog | Add import option inside existing Discovery dialog | |
| Header bar menu | Hamburger/overflow menu with both Discover and Import | |

**User's choice:** Separate header button
**Notes:** Consistent with Discover pattern, always accessible.

---

## Provider Assignment

| Option | Description | Selected |
|--------|-------------|----------|
| Channel name from yt-dlp | Use YouTube channel name from playlist metadata | ✓ |
| Always 'YouTube' | Single 'YouTube' provider for all imports | |
| User sets it | Ask user to type provider name before import | |

**User's choice:** Channel name from yt-dlp
**Notes:** Natural grouping by channel in station list.

---

## Progress UX

| Option | Description | Selected |
|--------|-------------|----------|
| Real-time count + spinner | Live "X imported, Y skipped" label while processing | ✓ |
| Spinner only, summary at end | Show spinner, then final count when done | |
| Progress bar + count | Progress bar with percentage (requires total count upfront) | |

**User's choice:** Real-time count + spinner
**Notes:** Matches IMPORT-01 ROADMAP spec exactly.

---

## Station Naming

| Option | Description | Selected |
|--------|-------------|----------|
| Video title, no review | Import immediately after URL paste, no review step | |
| Video title, with review step | Checklist of found live streams before committing | ✓ |
| Channel name as station name | Use channel name instead of video title | |

**User's choice:** Video title with review step

### Follow-up: Review step detail

| Option | Description | Selected |
|--------|-------------|----------|
| Checkboxes only | Select/deselect streams, no renaming | ✓ |
| Checkboxes + rename | Editable name per row | |
| Checkboxes + thumbnail preview | Thumbnail per item for visual ID | |

**User's choice:** Checkboxes only
**Notes:** Simpler to build; video title used as-is for station name.

---

## Claude's Discretion

- Exact yt-dlp invocation / `is_live` field validation (researcher task)
- Dialog widget hierarchy and sizing
- Scan error handling (invalid URL, private playlist)
- Button states during scan/import

## Deferred Ideas

None.
