# Phase 71: Sister station expansion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-12
**Phase:** 71-sister-station-expansion-1-add-ability-to-link-sister-statio
**Areas discussed:** Concept boundary, Storage model, SomaFM interpretation, Edit-dialog UX

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Concept boundary | Unified vs separate 'Related stations' label semantics | ✓ |
| Storage model | Symmetric join table vs group_id column vs directional FK | ✓ |
| SomaFM interpretation | Independent stations vs multi-stream-on-one-station shape | ✓ |
| Edit-dialog UX | Picker affordance, default state, link management | ✓ |

**User's choice:** All four areas

---

## Concept boundary

### Q1 — Unified vs separate

| Option | Description | Selected |
|--------|-------------|----------|
| Unified 'Related stations' | One label everywhere aggregating AA-auto + manual + SomaFM | |
| Keep AA 'Also on:' separate from manual sisters | Two labeled rows: 'Also on:' (AA auto) + 'Sister stations:' (manual) | |
| You decide | Pick based on codebase conventions | |

**User's response:** "Would definitely NOT be cross provider between the stations in question, just that we would allow other providers to have their own sister stations beyond all AA network providers"

**Notes:** The initial framing was wrong. The user clarified after Q2 (see clarification block below) that the new manual mechanism must handle BOTH cross-provider AA name-mismatch overrides (e.g., DI.fm "Classical Relaxation" ↔ RadioTunes "Relaxing Classical") AND same-provider variants (SomaFM Drone Zone ↔ Drone Zone 2). The mechanism augments — does not replace — AA URL-derived auto-detection.

### Q2 — Display surfaces

| Option | Description | Selected |
|--------|-------------|----------|
| NowPlaying line + Edit dialog | Mirror Phase 64 — inline 'Sister stations:' label under station name | ✓ |
| Edit dialog only | No NowPlaying surfacing — sisters as management concept only | |
| NowPlaying + Edit + station-tree chain-link icon | All three surfaces | |
| You decide | Use codebase conventions to pick | |

**User's choice:** NowPlaying line + Edit dialog

### Clarification (post-Q2)

User reset the framing: the new mechanism is ONE manual link tool handling both cases (AA name-mismatch + same-provider variants). I re-presented the surfacing question with the corrected framing.

### Q3 — Merge vs separate with corrected framing

| Option | Description | Selected |
|--------|-------------|----------|
| Merge into existing 'Also on:' line | Manual links + AA auto in one row, no auto/manual distinction in display | ✓ |
| Separate 'Also on:' + 'Related:' | Two stacked labels for auto vs manual | |
| Merge + allow manual entries to override AA auto-detection | Same merge but with suppression of wrong AA auto-matches | |

**User's choice:** Merge into existing 'Also on:' line

### Q4 — Continue or move on

| Option | Description | Selected |
|--------|-------------|----------|
| Move to Storage model | Concept settled | ✓ |
| More concept questions | Drill into vocabulary, dedupe, ordering | |

**User's choice:** Move to Storage model

---

## Storage model

### Q1 — Schema shape

| Option | Description | Selected |
|--------|-------------|----------|
| Symmetric join table `station_siblings(a_id, b_id)` | UNIQUE(a_id, b_id), CHECK(a_id < b_id), ON DELETE CASCADE | ✓ |
| Group ID column on stations: `sibling_group_id INTEGER` | Each station in at most one group | |
| Directional FK: `sister_of_id INTEGER` on stations | Hierarchical with a canonical primary | |

**User's choice:** Symmetric join table `station_siblings(a_id, b_id)`

### Q2 — ZIP export shape

| Option | Description | Selected |
|--------|-------------|----------|
| Per-station list of partner station NAMES | `siblings: ["Other Station Name", ...]` resolved by name on import | ✓ |
| Top-level `sibling_links` array in settings.json | (station_a_name, station_b_name) pairs at top level | |
| No ZIP integration | Links stay local-only | |

**User's choice:** Yes — export per-station as a list of partner station NAMES

### Q3 — Delete cascade

| Option | Description | Selected |
|--------|-------------|----------|
| ON DELETE CASCADE — link rows auto-delete | Matches existing station_streams pattern | ✓ |
| Soft delete with prompt | Block delete or auto-unlink with toast | |

**User's choice:** ON DELETE CASCADE — link rows auto-delete

### Q4 — Continue or move on

| Option | Description | Selected |
|--------|-------------|----------|
| Move to SomaFM interpretation | Storage locked | ✓ |
| More storage questions | Drill into transitive closures, indexing | |

**User's choice:** Move to SomaFM interpretation

---

## SomaFM interpretation

### Q1 — Variant shape

| Option | Description | Selected |
|--------|-------------|----------|
| Different content — separate stations | Each variant is its own Station row, linked via new mechanism | ✓ |
| Same content, different bitrates/codecs — one station, multiple streams | Existing multi-stream/failover model handles it | |
| Mixed — both shapes coexist, user decides per pair | Mechanism supports both | |

**User's choice:** Different content — separate stations

### Q2 — Auto-detection

| Option | Description | Selected |
|--------|-------------|----------|
| Fully manual — no SomaFM auto-detect | Tighter scope, manual table covers everything | ✓ |
| Add SomaFM URL-pattern auto-detector parallel to find_aa_siblings | New helper, merged into 'Also on:' | |
| Both — auto-detect + manual override | Largest scope, full AA parity | |

**User's choice:** Fully manual — ship the linking mechanism, no SomaFM auto-detect

### Q3 — Continue or move on

| Option | Description | Selected |
|--------|-------------|----------|
| Move to Edit-dialog UX | SomaFM scope is clear | |
| More SomaFM questions | Drill into bulk-link, transitive closures | |

**User's response:** "To confirm, any Auto connection can be deferred to phase 74"

**Notes:** User confirmed Phase 74 (SomaFM full station catalog) as the natural home for any URL-pattern auto-detection. Captured in CONTEXT.md Deferred Ideas.

---

## Edit-dialog UX

### Q1 — Picker affordance

| Option | Description | Selected |
|--------|-------------|----------|
| '+ Add sibling' button → modal with library station search | Discoverable, reuses list-search pattern | ✓ |
| Inline combobox with type-ahead search | Compact, less screen real-estate | |
| Multi-select chip-style picker | All stations as toggleable chips | |
| You decide | Pick based on codebase conventions | |

**User's choice:** '+ Add sibling' button → modal with library station search

### Q2 — Picker scope

| Option | Description | Selected |
|--------|-------------|----------|
| All stations, search-driven | Single flat list with search box | |
| Default to same-provider, toggle to show all | Filtered by default with expand option | |
| Show all + group by provider | Collapsible provider headers | |

**User's response:** "Select provider, unlocks another selection for stations under the provider"

**Notes:** User specified a two-step picker not present in my options: pick provider FIRST, which then unlocks the station list filtered to that provider. Captured as D-12 in CONTEXT.md.

### Q3 — Picker default and multi-add

| Option | Description | Selected |
|--------|-------------|----------|
| Provider defaults to current; one sibling per modal open | Click station → link → close. Reopen modal to add another | ✓ |
| Provider defaults to current; multi-select with Confirm/Cancel | Pick multiple stations at once and Confirm | |
| Provider starts empty; user always picks both | No default, explicit selection required | |

**User's choice:** Provider defaults to current station's provider; one sibling per modal open

### Q4 — Manage existing links

| Option | Description | Selected |
|--------|-------------|----------|
| Per-sibling 'x' next to each name in 'Also on:' display | Chip row, click 'x' to unlink with toast | ✓ |
| Right-click context menu → Unlink | Keep read-only label, add right-click handler | |
| Single 'Manage siblings' button opens picker in 'manage' mode | Modal doubles as manager | |

**User's choice:** Per-sibling 'x' next to each name in the 'Also on:' display

### Q5 — Auto vs manual visual distinction

| Option | Description | Selected |
|--------|-------------|----------|
| Only manually-linked siblings show 'x'; AA auto plain text | Visual: 'x' means 'I can remove this' | ✓ |
| All chips show 'x', AA auto-removal stored as 'hidden' flag | Persistent suppression of wrong AA auto-matches | |
| Visual marker (icon/color) on auto vs manual chips | Show shape without 'x' on auto | |

**User's choice:** Only manually-linked siblings show 'x'; AA auto-siblings show plain text

---

## Wrap-up

### Q — More gray areas or ready for CONTEXT.md

| Option | Description | Selected |
|--------|-------------|----------|
| Ready for CONTEXT.md | Decisions captured, write the file | ✓ |
| Explore more gray areas | Drill into transitive closures, bulk-link, vocabulary | |

**User's choice:** Ready for CONTEXT.md

---

## Claude's Discretion

The user did not explicitly say "you decide" on any question, but the following implementation choices were left open in CONTEXT.md for the planner:
- Helper module placement for `find_manual_siblings` (default: extend `url_helpers.py`)
- Chip-row widget implementation (FlowLayout vs custom button row)
- Provider QComboBox vs alternative widget in the picker
- Station list widget shape (QListView with proxy vs QListWidget)
- Sort order of manually-linked siblings in the merged display
- Whether the merge helper does a one-hop transitive walk (default: strict direct-link)
- Tooltip on chips (default: none, with provider-name option for cross-provider links)

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section. Headline items:
- SomaFM URL-pattern auto-detection → Phase 74
- Auto-detection for other networks beyond AA and SomaFM
- AA auto-detection override / suppression
- Transitive closure auto-expansion
- Multi-select picker
- Station-tree chain-link icon
- Vocabulary change to "sister" in UI
- Right-click context menu on chips
- 'Manage siblings' bulk dialog
- Cross-station bulk-link command
