# Phase 54: Station Logo Aspect Ratio Fix - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-29
**Phase:** 54-station-logo-aspect-ratio-fix
**Areas discussed:** Surface scope, Bar treatment, Repro examples, YouTube special-casing

---

## Surface scope

### Q1 — Where is the bug visible?

| Option | Description | Selected |
|--------|-------------|----------|
| Now-playing logo (180×180) | Left-column big logo in the right panel — most prominent surface | |
| Cover slot fallback (160×160) | Right-column cover-art slot when no ICY title | |
| Station list rows (32px) | Per-station icon next to the name in the left tree | ✓ |
| EditStationDialog preview (64×64) | Logo preview row at top of edit dialog | |

**User's choice:** Station list rows (32px) only.
**Notes:** Narrows the fix scope significantly — other surfaces already render correctly.

### Q2 — Symptom shape?

| Option | Description | Selected |
|--------|-------------|----------|
| Sides cut off | Wide/landscape logos get left+right edges chopped | |
| Top+bottom cut off | Tall/portrait logos get top+bottom chopped | ✓ |
| Both, depending on logo | Crops on whichever axis exceeds 1:1 | |
| Logo is squished/distorted | Aspect ratio broken — logo stretched, not cropped | |

**User's choice:** Top+bottom cut off (portrait logos).
**Notes:** Confirms center-crop-to-square is happening to portrait sources despite the loader's `Qt.KeepAspectRatio` call.

### Q3 — Provider tree, Recently Played, or both?

| Option | Description | Selected |
|--------|-------------|----------|
| Both surfaces | Provider tree AND Recently Played both show bug | |
| Provider tree only | Only main grouped tree rows affected | ✓ |
| Recently Played only | Only top section affected | |
| Not sure / haven't compared | Researcher to confirm | |

**User's choice:** Provider tree only.
**Notes:** Notable signal — the QStandardItem.setIcon path used by Recently Played may render differently than the model data() DecorationRole path used by the tree. Useful for root-cause hypothesis.

### Q4a — Landscape logos in the same surface?

| Option | Description | Selected |
|--------|-------------|----------|
| Landscape rows fine | Wide logos render correctly today | |
| Landscape also off | Wide logos also broken | |
| Not sure | Researcher should audit both axes | ✓ |

**User's choice:** Not sure.
**Notes:** Researcher will audit both portrait + landscape in scope.

### Q4b — Target portrait render shape?

| Option | Description | Selected |
|--------|-------------|----------|
| Pillarbox (16w × 32h, centered) | Logo shrinks to height=32, width follows aspect; bars left+right; matches SC #3 | ✓ |
| Cap by width (32w × 64h, row grows) | Width=32, height grows to 64; row taller for portrait | |
| Center-crop to square (current, broken) | Keep current — known wrong | |

**User's choice:** Pillarbox 16w × 32h, centered.
**Notes:** Fixed row height preserved; aligns with SC #4.

---

## Bar treatment

### Q1 — Bar fill color?

| Option | Description | Selected |
|--------|-------------|----------|
| Transparent (Recommended) | Row's normal/hover/selection bg shows through | ✓ |
| Match row bg explicitly | Paint solid theme bg into bars | |
| Solid black | Always-black pillarbox bars | |
| Image-derived edge color | Sample logo edges for seamless extension | |

**User's choice:** Transparent.
**Notes:** Cheapest, blends with theme tokens automatically.

### Q2 — Cell footprint?

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed 32×32 footprint (Recommended) | Every row reserves same icon-column width — names align | ✓ |
| Shrink to actual logo width | Portrait stations get narrower cell — names shift | |

**User's choice:** Fixed 32×32 footprint.
**Notes:** Direct match to SC #4 (viewport size/position does not shift between stations).

### Q3 — Inset/border?

| Option | Description | Selected |
|--------|-------------|----------|
| Fill cell (Recommended) | Logo's longer side = 32px; max visual size | ✓ |
| 1–2px inset | Tiny breathing room around logo | |
| Rounded-rect clip (4px radius) | Round logo corners; matches Phase 11 panel rounding | |

**User's choice:** Fill cell edge-to-edge.
**Notes:** Phase 11 panel rounding was for full-panel surfaces, not row icons.

### Q4 — Hover/selection treatment?

| Option | Description | Selected |
|--------|-------------|----------|
| Default — logo paints over hover/selection bg | Logo pixels stay original; bars show selection bg | ✓ |
| Tint logo on selection | Apply selection-accent overlay to logo pixmap | |

**User's choice:** Default behavior.
**Notes:** No painting work beyond aspect fix.

---

## Repro examples

### Q1 — Affected station sources?

| Option | Description | Selected |
|--------|-------------|----------|
| AudioAddict channel(s) | AA API logos — some portrait/non-square | ✓ |
| YouTube live stream(s) | YT thumbs are 16:9 landscape | |
| Radio-Browser station(s) | Discovery imports may have non-square logos | |
| Manually-added station(s) | User-uploaded via EditStationDialog file-picker | ✓ |

**User's choice:** AudioAddict + Manually-added.
**Notes:** Multi-select. Defines researcher's audit scope.

### Q2 — Test approach?

| Option | Description | Selected |
|--------|-------------|----------|
| Unit pixmap test on load_station_icon (Recommended) | Synthetic portrait pixmap, assert aspect preserved | ✓ |
| Live UAT only — visual check | No automated test | |
| Both — unit + UAT | Belt and suspenders | |

**User's choice:** Unit pixmap test (single approach).
**Notes:** Live UAT still implied — user gates phase complete on visual confirmation, but the regression-locking artifact is the unit test.

### Q3 — Specific station name?

| Option | Description | Selected |
|--------|-------------|----------|
| Researcher digs | phase-researcher queries SQLite for non-square logos | ✓ |
| I'll name one | User will type a known broken station | |

**User's choice:** Researcher digs.
**Notes:** Researcher should query `musicstreamer.sqlite3` for assets with non-square dimensions.

### Q4 — Test file location?

| Option | Description | Selected |
|--------|-------------|----------|
| tests/test_art_paths.py (Recommended) | Existing module for _art_paths.py | ✓ |
| New tests/test_station_logo_aspect.py | Phase-specific isolated module | |
| tests/test_station_tree_model.py | Integration path where QIcon actually renders | |

**User's choice:** tests/test_art_paths.py.
**Notes:** Co-located with existing cache-hit / fallback / abs-path tests.

---

## YouTube special-casing

### Q1 — Uniform vs YouTube-special?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep uniform (Recommended) | One aspect rule for everyone | ✓ |
| YouTube gets bigger row icon | Detect YT and reserve wider cell | |
| YouTube logos cropped to square (legacy) | Force 16:9 to square crop | |

**User's choice:** Keep uniform.
**Notes:** Phase 18's special-case was for the now-playing slot, not row icons.

### Q2 — Now-playing slot in scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Strictly station-list rows (Recommended) | Don't widen scope; user not seeing bug there | ✓ |
| Audit now-playing too | Researcher checks 180×180 portrait rendering | |

**User's choice:** Strictly station-list rows.
**Notes:** Now-playing 180×180 already uses KeepAspectRatio + AlignCenter and looks correct to user. Out of scope for this phase.

### Q3 — Approach: small fix vs delegate?

| Option | Description | Selected |
|--------|-------------|----------|
| Smallest-diff fix (Recommended) | Adjust loader/renderer at single call site | ✓ |
| Custom QStyledItemDelegate | Bulletproof but heavier | |

**User's choice:** Smallest-diff fix.
**Notes:** Custom delegate is a fallback if researcher can't fix at the loader level.

### Q4 — QPixmapCache key?

| Option | Description | Selected |
|--------|-------------|----------|
| Default — no cache concerns (Recommended) | Same key, same target size | ✓ |
| Bump cache key | Add v2 suffix to invalidate old entries | |
| Researcher decides | Defer to research | |

**User's choice:** Default — no cache concerns.
**Notes:** Cache shape unchanged; existing test_art_paths.py cache assertions stay green.

---

## Claude's Discretion

None — every gray area resolved with an explicit user selection.

## Deferred Ideas

- Now-playing 180×180 portrait audit (parallel-latent check) — out of scope; researcher may file follow-up phase if discovered
- Custom QStyledItemDelegate for tree row icons — escalation only, not default
- Wider row cell for YouTube 16:9 thumbs — rejected (D-07)
- Image-derived edge-color pillarbox bars — rejected (D-04); future visual-polish only
