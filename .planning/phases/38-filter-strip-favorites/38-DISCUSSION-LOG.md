# Phase 38: Filter Strip + Favorites - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-12
**Phase:** 38-filter-strip-favorites
**Areas discussed:** Search + filter interaction, Stations/Favorites toggle, Star button behavior, Filter strip layout

---

## Search + Filter Interaction

| Option | Description | Selected |
|--------|-------------|----------|
| AND composition | Search text filters within chip selection | ✓ |
| Independent filters | Search and chips operate separately | |
| OR composition | Either match shows results | |

**User's choice:** AND composition
**Notes:** Matches v1.5 behavior

---

| Option | Description | Selected |
|--------|-------------|----------|
| Auto from data | Chips auto-generate from station DB | ✓ |
| Fixed preset list | Hardcoded chip set | |
| User-managed chips | User creates/deletes custom chips | |

**User's choice:** Auto from data

---

| Option | Description | Selected |
|--------|-------------|----------|
| OR within, AND between | Multi-select within dimension is OR, between dimensions is AND | ✓ |
| Single-select per row | One chip active per row | |
| OR everywhere | All chips OR together | |

**User's choice:** OR within, AND between (matches ROADMAP spec)

---

## Stations/Favorites Toggle

| Option | Description | Selected |
|--------|-------------|----------|
| Segmented control | Two-button [Stations / Favorites] at top of panel | ✓ |
| Tab bar | QTabWidget with tabs | |
| Toggle button | Single star/heart button | |

**User's choice:** Segmented control

---

| Option | Description | Selected |
|--------|-------------|----------|
| Flat list by recency | Newest first, "Track Title — Station Name" per row, trash icon | ✓ |
| Grouped by station | Station headers with nested tracks | |
| Grouped by genre | Genre headers with tracks underneath | |

**User's choice:** Flat list by recency

---

## Star Button Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| ICY title + station context | Saves track title, station name, provider, genre | ✓ |
| Station only | Favorites the station, not the track | |
| ICY title only | Just the track string, no station context | |

**User's choice:** ICY title + station context

---

| Option | Description | Selected |
|--------|-------------|----------|
| Icon toggle + toast | Star fills/unfills + brief toast notification | ✓ |
| Icon toggle only | Star changes, no toast | |
| Icon toggle + animation | Star with scale/pulse animation | |

**User's choice:** Icon toggle + toast

---

## Filter Strip Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Above tree, below toggle | Search + chips between segmented control and tree | ✓ |
| Collapsible panel | Filter strip expands/collapses | |
| Integrated in header | Search in header, chips as horizontal scroll | |

**User's choice:** Above tree, below toggle

---

| Option | Description | Selected |
|--------|-------------|----------|
| Flow/wrap layout | Chips wrap to new lines on narrow windows | ✓ |
| Horizontal scroll | Single row with scroll | |
| Overflow menu | Show N chips then "+3 more" button | |

**User's choice:** Flow/wrap layout (matches ROADMAP spec)

---

## Additional User Input

User requested **station favorites** (in addition to track favorites): starred stations appear at top of station list under a "Favorites" heading, using the same star icon pattern. Folded into Phase 38 scope as D-06/D-07/D-09.

## Claude's Discretion

- Chip styling, search box clear button, chip ordering
- Segmented control implementation approach
- Empty state text for favorites
- Whether station favorite uses a new DB column or separate table

## Deferred Ideas

None — discussion stayed within phase scope.
