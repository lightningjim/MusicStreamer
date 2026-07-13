# Phase 89c: Provider Brand-Avatar Cover-Slot Fallback - Discussion Log

> **Audit trail only.** Not consumed by researcher/planner/executor — decisions live in 89C-CONTEXT.md.

**Date:** 2026-06-17
**Phase:** 89C-provider-brand-avatar-cover-slot-fallback
**Mode:** discuss (interactive)

## Gray Areas Selected

User selected all four offered areas plus volunteered a fifth (free-text):
- AudioAddict granularity
- Brand-mark visual fit
- Asset sourcing & bundling
- Render-state & re-trigger
- **(user-added)** Direct file-upload override — for overriding auto, or for providers not
  otherwise automated without further custom coding.

## Questions & Selections

### AudioAddict granularity
- Options: Per-network (6 assets) / One shared AudioAddict mark / DI.fm only.
- **Selected: Per-network (6 assets)** → 7 brand avatars total (SomaFM + 6 AA networks). → D-01, D-02.

### Brand-mark visual fit
- Options: Pre-composed circular PNGs / Runtime inset on circular tile / Reuse Phase 89 center-crop.
- **Selected: Pre-composed circular PNGs.** → D-03, D-06.

### Upload-override scope
- Options: Fold in via providers.avatar_path / Bundled-only now, leave the hook / Bundled-only, no hook.
- **Selected: Fold in via providers.avatar_path** (reuse the dormant 89.1 per-provider column;
  precedence override > bundled > logo; manual pick for any provider). → D-08, D-09, D-09a.

### Asset source
- Options: I'll provide the PNGs / Claude generates monogram placeholders / Claude sources official marks.
- **Selected: User provides the PNGs.** Phase ships plumbing + 7 filename slots; missing asset ===
  current behavior. → D-04.

### Re-trigger
- Options: Transient per-resolution / Sticky until station change.
- **Selected: Transient per-resolution** (real art always wins). → D-10.

### Upload UI placement
- Options: EditStationDialog any provider / Only providers without a bundled avatar / Central providers screen.
- **Selected: EditStationDialog, any provider** (overrides bundled; covers no-bundled-asset case). → D-09.

### Bundling mechanism
- Options: Loose package-data dir / Qt resource (.qrc).
- **Selected: Loose package-data dir** (`musicstreamer/ui_qt/brand-avatars/<key>.png` via
  importlib.resources; PyInstaller datas; no qrc recompile). → D-05.

### Wrap
- **Selected: Ready for context** — remaining mechanics (registry module shape, tier-replay tracked
  var, missing-asset fallthrough) locked as Claude's-discretion defaults grounded in Phase 89/89.1.

## Claude's Discretion Items
- Registry module shape (dedicated `brand_avatars.py` lookup vs inline), tracked-var naming,
  filename-key scheme, EditStationDialog picker layout. → see CONTEXT "Claude's Discretion".

## Deferred Ideas
- More ICY providers beyond SomaFM/AA; central providers-management screen; Claude auto-sourcing marks.
