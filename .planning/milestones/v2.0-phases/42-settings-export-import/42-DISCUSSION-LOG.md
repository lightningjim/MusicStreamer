# Phase 42: Settings Export/Import - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-16
**Phase:** 42-settings-export-import
**Areas discussed:** Export content & structure, Import merge behavior, Summary dialog UX, File picker & defaults

---

## Export Content & Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Full DB dump | All stations, streams, favorites, providers, settings table | ✓ |
| Curated subset | Only user-configured data, skip internal state | |
| You decide | Claude picks completeness level | |

**User's choice:** Full DB dump
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| logos/\<station_name\>.\<ext\> | Human-readable, sanitized names | ✓ |
| logos/\<station_id\>.\<ext\> | Mirrors current assets layout, IDs meaningless cross-machine | |
| logos/\<hash\>.\<ext\> with manifest | Content-addressed, harder to inspect | |

**User's choice:** logos/\<station_name\>.\<ext\>
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Include timestamps | Full fidelity round-trip | ✓ |
| Reset on import | Recently played starts fresh | |

**User's choice:** Include timestamps
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, export both | Station stars + ICY track favorites | ✓ |
| Track favorites only | Only favorites table, station stars reset | |

**User's choice:** Yes, export both
**Notes:** None

---

## Import Merge Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Stream URL | Match by URL in station_streams | ✓ |
| Station name + provider | Match by name+provider combo | |
| Both (URL first, name fallback) | URL match then name+provider fallback | |

**User's choice:** Stream URL
**Notes:** Aligns with existing `station_exists_by_url()` in Repo

| Option | Description | Selected |
|--------|-------------|----------|
| Toggle in import dialog | Radio/segmented: Merge vs Replace All, default Merge | ✓ |
| Always merge, no replace | Simpler but can't do clean restore | |
| You decide | Claude picks | |

**User's choice:** Toggle in import dialog
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Everything | Replace name, provider, tags, streams, logo, ICY flag, star | ✓ |
| Only missing fields | Fill blanks, don't overwrite | |
| Metadata only, keep streams | Update name/tags/provider but keep stream table | |

**User's choice:** Everything
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Union — add missing | INSERT OR IGNORE by station_name+track_title | ✓ |
| Replace all favorites | Replace entire favorites table from import | |
| You decide | Claude picks | |

**User's choice:** Union — add missing
**Notes:** None

---

## Summary Dialog UX

| Option | Description | Selected |
|--------|-------------|----------|
| Counts only | "12 added, 3 replaced, 1 skipped, 0 errors" simple dialog | |
| Counts + expandable list | Summary counts + expandable per-station detail | ✓ |
| Full diff view | Side-by-side conflict comparison | |

**User's choice:** Counts + expandable list
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| All-or-nothing | Summary + OK/Cancel, no per-station selection | ✓ |
| Checklist per station | Checkboxes per station to deselect entries | |

**User's choice:** All-or-nothing
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Toast + abort | Toast error, no partial import | ✓ |
| Error dialog with details | Modal dialog explaining the error | |
| You decide | Claude picks | |

**User's choice:** Toast + abort
**Notes:** Consistent with existing ToastOverlay pattern

---

## File Picker & Defaults

| Option | Description | Selected |
|--------|-------------|----------|
| .zip | Standard ZIP, descriptive default filename | ✓ |
| .msbackup | Custom extension (ZIP internally) | |
| You decide | Claude picks | |

**User's choice:** .zip
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| User's home/Documents | QStandardPaths::DocumentsLocation | ✓ |
| Desktop | Desktop for immediate visibility | |
| Last used directory | Remember last export/import dir | |

**User's choice:** User's home/Documents
**Notes:** None

---

## Claude's Discretion

- JSON schema design within settings.json
- Station name sanitization strategy for logo filenames
- Exact import summary dialog widget layout
- Whether Replace All prompts an extra confirmation

## Deferred Ideas

None
