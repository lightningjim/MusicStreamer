# Phase 27: Add multiple streams per station - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-08
**Phase:** 27-add-multiple-streams-per-station-for-backup-round-robin-and
**Areas discussed:** Stream data model, Station editor UX, Quality tiers, Import behavior

---

## Stream Data Model

### Storage approach

| Option | Description | Selected |
|--------|-------------|----------|
| New `station_streams` table | Normalized: station_id, url, label, quality, position. Clean separation. | ✓ |
| JSON column on stations | `streams TEXT` JSON array. Simpler migration, harder to query. | |
| You decide | Claude picks best fit | |

**User's choice:** New `station_streams` table
**Notes:** None

### Stream fields

| Option | Description | Selected |
|--------|-------------|----------|
| Label (free text) | User-visible name like 'US Mirror', 'EU Server' | ✓ |
| Quality tier | e.g. hi/med/low | ✓ |
| Position/priority | Integer for ordering | ✓ |
| Stream type hint | e.g. 'shoutcast', 'youtube', 'hls' | ✓ |
| Codec type | MP3, AAC, OPUS, FLAC, etc (user-added) | ✓ |

**User's choice:** All five fields
**Notes:** Codec type was user-suggested via "Other"

### Migration strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Migrate to streams table | Remove stations.url, all URLs in station_streams | ✓ |
| Keep both | stations.url stays as legacy, station_streams additive | |

**User's choice:** Migrate to streams table
**Notes:** Clean single source of truth

---

## Station Editor UX

### Stream management approach

| Option | Description | Selected |
|--------|-------------|----------|
| Inline list in editor | Streams as ListBox inside existing edit dialog | |
| Separate streams dialog | "Manage Streams" button opens dedicated sub-dialog | ✓ |
| You decide | Claude picks best fit | |

**User's choice:** Separate streams dialog
**Notes:** None

### Reorder method

| Option | Description | Selected |
|--------|-------------|----------|
| Drag and drop | GTK4 DnD on list rows | |
| Up/down buttons | Arrow buttons per row | |
| You decide | Claude picks based on GTK4/Libadwaita patterns | ✓ |

**User's choice:** You decide
**Notes:** None

---

## Quality Tiers

### Tier definition

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed set (hi/med/low) | Predefined tiers, maps to AudioAddict | |
| Free-form text | User types anything | |
| Fixed + custom | Dropdown presets plus custom text option | ✓ |

**User's choice:** Fixed + custom
**Notes:** None

### Global preference vs position

| Option | Description | Selected |
|--------|-------------|----------|
| Global preferred quality | Settings option, player picks matching stream | |
| Position only | First stream plays first, manual ordering | |
| Both | Position is default, global quality can override | ✓ |

**User's choice:** Both
**Notes:** None

---

## Import Behavior

### AudioAddict import

| Option | Description | Selected |
|--------|-------------|----------|
| Import all qualities | One station, up to 3 streams (hi/med/low) | ✓ |
| Import selected quality only | Current behavior, single stream | |
| Import selected + store others | Preferred plays first, all stored as backup | |

**User's choice:** Import all qualities
**Notes:** None

### Radio-Browser import

| Option | Description | Selected |
|--------|-------------|----------|
| Single stream only | Just resolved direct URL | ✓ |
| Store both URLs | Resolved + original PLS/M3U as fallback | |
| You decide | Claude picks | |

**User's choice:** Single stream only
**Notes:** User later revisited to add attach-to-existing feature

### Radio-Browser attach-to-existing

| Option | Description | Selected |
|--------|-------------|----------|
| Save button offers both | User chooses new station or attach to existing | |
| Auto-detect duplicates | Prompt when similar name/provider found | |
| Both | Auto-detect suggests + manual pick any station | ✓ |

**User's choice:** Both (auto-detect + manual override)
**Notes:** User realized Radio-Browser lists multiple entries for same station (different mirrors/bitrates). Attach-to-existing addresses this real-world pattern.

---

## Claude's Discretion

- Stream reorder method (up/down buttons vs drag-and-drop)
- Streams sub-dialog layout
- Migration strategy details

## Deferred Ideas

None
