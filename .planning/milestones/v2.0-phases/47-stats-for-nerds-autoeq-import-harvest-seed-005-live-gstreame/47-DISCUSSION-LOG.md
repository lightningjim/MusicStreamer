# Phase 47: Stream bitrate quality ordering - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-04-17
**Phase:** 47-stream-bitrate-quality-ordering
**Areas discussed:** Scope shape, `quality` vs `bitrate_kbps` relationship, mixed-bitrate failover, Edit Station UX

---

## Scope shape (original Phase 47 bundled 3 features)

| Option | Description | Selected |
|--------|-------------|----------|
| Split into 3 phases: 47=bitrate, 48=buffer, 49=AutoEQ | Renumber to 47/48/49, most granular | |
| Split into 3 via decimals: 47=bitrate, 47.1=buffer, 47.2=AutoEQ | Keeps existing Phase 48 (AudioAddict listen key) in place. Decimals cluster related seed-harvest work. | ✓ |
| Split into 2: 47=bitrate+buffer, 48=AutoEQ | Middle ground | |
| Keep as-is — one Phase 47 | Bundled; contradicts user's scope-creep-frustration preference | |

**User's choice:** 3-way split. Roadmap restructured: Phase 47 = bitrate only; NEW Phase 47.1 = SEED-005 buffer indicator; NEW Phase 47.2 = SEED-007 AutoEQ.
**Notes:** Each phase has independent UAT, clear goal, reasonable size. Bitrate sequenced first because failover reorder is most foundational.

---

## `quality` vs `bitrate_kbps` relationship

| Option | Description | Selected |
|--------|-------------|----------|
| Keep both — `quality` is human label, `bitrate_kbps` is sort key | Lowest disruption, preserves custom tags | ✓ |
| Deprecate `quality`, migrate to bitrate_kbps | Cleaner long-term, more invasive | |
| Keep both, derive `quality` from bitrate_kbps | Computed field, loses custom tags | |

**User's choice:** Keep both.
**Notes:** `quality` stays as-is; `bitrate_kbps` is the new sort key. AA import sets both ("hi" + 320). No migration of existing `quality` values.

---

## Mixed-bitrate failover ordering

| Option | Description | Selected |
|--------|-------------|----------|
| Unknowns sort last | Known-bitrate streams first, unknowns fall to bottom in position order | ✓ |
| Any unknown → fall back to pure position order | Literal reading of roadmap wording; brittle on partial data | |

**User's choice:** Unknowns sort last.
**Notes:** Partial-data-safe; fresh imports with known bitrates always win. Unknowns keep their relative position order among themselves at the bottom of the failover queue.

---

## Edit Station bitrate UX

| Option | Description | Selected |
|--------|-------------|----------|
| Numeric QLineEdit + QIntValidator | Free typing, flexible, matches existing table fields | ✓ |
| QComboBox dropdown of common values | Discoverable, but adds widget type and special cases | |
| QSpinBox with range 0-9999 | Arrows + numeric, clunky typing | |

**User's choice:** QLineEdit with validator.
**Notes:** Column order URL | Quality | Codec | Bitrate | Position. Empty cell ↔ 0 (unknown).

---

## Claude's Discretion

- Module placement for the pure ordering function (`musicstreamer/stream_ordering.py` recommended)
- Test file name (`tests/test_stream_ordering.py`)
- Whether to show an inline "computed failover order" preview column (lean: no — keep UI simple)
- Whether AA bitrate-tier map is a constants table or inline (lean: inline, colocated with existing tier logic)

## Deferred Ideas

- SEED-005 buffer indicator → Phase 47.1
- SEED-007 AutoEQ import → Phase 47.2
- Per-stream live bitrate measurement from ICY metadata
- Auto-detect bitrate on stream add (probe URL during import)
- Mobile-data "prefer lower bitrate" toggle
- `quality` field deprecation (if it becomes redundant after a future phase)
