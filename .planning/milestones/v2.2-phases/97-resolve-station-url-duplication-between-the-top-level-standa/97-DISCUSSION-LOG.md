# Phase 97: Resolve station URL duplication - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-23
**Phase:** 97-resolve-station-url-duplication-between-the-top-level-standa
**Areas discussed:** Source of truth, Multi-stream mapping, Metadata = playback?

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Source of truth | Which UI surface owns stream #1's URL | ✓ |
| Multi-stream mapping | How the primary URL binds when several streams exist | ✓ |
| Metadata = playback? | Whether fetch/metadata URL and playback URL are one concept | ✓ |
| New-station entry | How a brand-new station's first URL is entered | |

---

## Source of truth

### Q1 — Which UI surface owns stream #1's URL?
| Option | Description | Selected |
|--------|-------------|----------|
| Top field is canonical | Keep prominent 'URL:' field; table manages #2+; least rewiring | |
| Streams table owns it | Remove top field; table row is sole editor; rewire all metadata reads | ✓ |
| Keep both, live-bind | Both visible, synced; duplication hidden not removed | |

**User's choice:** Streams table owns it.

### Q2 — Where should metadata operations read from after the top field is removed?
| Option | Description | Selected |
|--------|-------------|----------|
| Live from the table cell | Read primary row's unsaved cell text; preserves interactive behavior | ✓ |
| From the saved stream | Use persisted URL; only refreshes after Save (behavior change) | |

**User's choice:** Live from the table cell.

### Q3 — How should the table behave for the common single-stream case?
| Option | Description | Selected |
|--------|-------------|----------|
| Auto-create first row | Always ensure one editable primary row; type the URL directly | ✓ |
| Explicit Add button | User clicks 'Add stream' first; uniform but one extra click | |
| You decide | Leave ergonomics to planning | |

**User's choice:** Auto-create first row.

---

## Multi-stream mapping

### Q1 — Which stream is "primary" when several exist?
| Option | Description | Selected |
|--------|-------------|----------|
| First by position | Top row / streams[0]; matches today's behavior | ✓ |
| Phase-82 preferred stream | Use preferred_stream_id, fall back to position 1 | |

**User's choice:** First by position.

### Q2 — Should reordering change which stream is primary?
| Option | Description | Selected |
|--------|-------------|----------|
| Top row = primary | Promoting a row to top makes it canonical; follows position | |
| Separate primary marker | Distinct flag independent of ordering | ✓ |

**User's choice:** Separate primary marker.

### Q3 — Reconciling "first by position" with "separate marker"; relation to preferred_stream_id?
| Option | Description | Selected |
|--------|-------------|----------|
| New marker, defaults to first | Distinct pinned flag; auto-set to first on create; separate from preferred_stream_id | ✓ |
| Reuse preferred_stream_id | Treat playback choice as canonical anchor too | |
| Marker drives metadata only | Fully independent of playback and order | |

**User's choice:** New marker, defaults to first.
**Notes:** Initial answers appeared to conflict (first-by-position vs separate marker); reconciled to: a new pinned canonical marker that defaults to the first stream on creation, stays pinned through reordering, and is distinct from Phase-82 preferred_stream_id (which still controls playback).

---

## Metadata = playback?

### Q1 — How should canonical (metadata) vs preferred (playback) divergence be treated?
| Option | Description | Selected |
|--------|-------------|----------|
| Allowed, no warning | Power users may diverge silently; coincide for single-stream | ✓ |
| Allowed, subtle hint | Permit divergence but show a quiet cue | |
| Keep them together | Force canonical == played (contradicts separate marker) | |

**User's choice:** Allowed, no warning.

### Q2 — Should all metadata consumers use the canonical stream, or is AA sibling matching special?
| Option | Description | Selected |
|--------|-------------|----------|
| All use canonical | Every consumer reads the canonical stream URL uniformly | ✓ |
| Siblings match any stream | AA sibling detection compares all stream URLs | |
| You decide | Default all-canonical, planning may broaden siblings | |

**User's choice:** All use canonical.

---

## Claude's Discretion

- Exact widget/control + placement for the canonical marker.
- DB representation of the canonical marker (FK on station vs boolean on stream) and the defaulting migration.
- Wiring mechanism for live canonical-cell reads.

## Deferred Ideas

- New-station entry flow (area not selected; D-03 covers the core ergonomic).
- Divergence warning UI (D-06 chose silent; revisit if users report confusion).
