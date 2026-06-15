# Phase 94: Sidebar Logo Thumbnail Optimization - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Speed up station-sidebar scrolling on large lists (e.g. DI.fm) by loading
pre-scaled small logo variants in the sidebar instead of decoding + smooth-scaling
the full-resolution logo PNG at paint time. The full-res `station_art` is
preserved unchanged for the Now Playing panel.

**In scope:** the sidebar logo load path only — thumbnail generation, storage,
sizing, warming, and invalidation.

**Out of scope (own phases / not this work):** tree virtualization, lazy-loading
the tree model itself, cover-art changes, the Now Playing art pipeline, and any
change to how/where the full-res logo is downloaded or stored.

**Root cause (confirmed in code):** `load_station_icon()` in
`musicstreamer/ui_qt/_art_paths.py` decodes the full-res PNG (`QPixmap(path)`)
and `SmoothTransformation`-scales it to 32px **synchronously inside the tree
model's `DecorationRole`** (`station_tree_model.py:163-164`) during paint. On a
fast scroll through a large list, each uncached row decodes a full-size image on
the UI thread → jank. QPixmapCache stores the scaled result keyed by path, so
later scrolls are fast; the cost is the first decode of each row.
</domain>

<decisions>
## Implementation Decisions

### Sidebar variant vs full-res (locked by phase goal)
- **D-01:** The sidebar renders a small pre-scaled thumbnail. The full-res
  `station_art` is preserved and continues to feed the Now Playing panel
  (`now_playing_panel.py::_load_scaled_pixmap`, 180px). Only the sidebar load
  path (`load_station_icon`) switches to the thumbnail.

### Generation strategy & timing
- **D-02:** Generate thumbnails **lazily on cache/file miss**, then write the
  result to disk. No eager import-time generation and **no migration** — the
  scheme is self-healing and automatically covers every import source
  (aa_import, soma_import, gbs_api) and manual edits, because they all land a
  full-res logo that the sidebar will thumbnail on demand.

### Warming / first-pass smoothness
- **D-03:** Generation runs **asynchronously, off the UI thread** ("async
  generate-on-miss"). On a miss the row paints a fallback/placeholder icon
  immediately; a worker generates the thumbnail and the row repaints when it
  lands. So even the first scroll through a large existing library stays smooth.
  No startup scan / no blocking "optimizing logos…" dialog.
  - **Planner note:** `QPixmap` is not safe to create off the main thread. The
    worker must build a `QImage` (and/or write the PNG to disk), then hand it to
    the UI thread for `QPixmap` conversion + `QPixmapCache` insert, followed by a
    `dataChanged` emit (or equivalent) to trigger the row repaint.

### Thumbnail size & HiDPI
- **D-04:** Store a **single 96px** thumbnail per station. 96px keeps the 32px
  logical sidebar icon sharp from 1x through 3x (Wayland fractional, macOS
  Retina 2x, Windows 1.5/2x) in one tiny artifact. No per-DPR variants. The
  existing devicePixelRatio-aware canvas logic in `load_station_icon` (lines
  91-103) continues to handle final placement.

### Storage / naming
- **D-05:** Thumbnail lives **alongside the source logo** with a **fixed name**
  (e.g. `assets/{station_id}/station_art.thumb.png`), mirroring the
  `assets/{station_id}/station_art.png` layout produced by
  `assets.py::copy_asset_for_station`. Fixed name (not content-hash) so there are
  no orphan files to clean up.

### Staleness / invalidation
- **D-06:** Detect staleness via an **mtime check on load**: if the thumbnail is
  missing OR older than the source logo, (re)generate it. One cheap `stat()` per
  load, self-healing, no orphans, and robust even if a future art-change path
  forgets to invalidate. (Re-import and the edit-station dialog both overwrite
  `station_art.png`, which updates its mtime; the GBS themed-day override is
  in-memory only and does not affect the on-disk sidebar thumbnail.)

### Claude's Discretion
- Exact worker/threading mechanism (thread pool vs `QThread` vs reuse of an
  existing worker pattern), placeholder icon choice during the async gap, the
  precise QPixmapCache key scheme, and PNG encoding parameters.
</decisions>

<specifics>
## Specific Ideas

- The fix should make fast-scrolling a large list (DI.fm-scale) feel smooth on
  the first pass, not just on re-scroll — hence the off-UI-thread async
  generation rather than a simpler synchronous-write-on-first-paint.
- Keep the change surgical to the sidebar load path; do not perturb Now Playing
  or the download/storage of full-res logos.
</specifics>

<canonical_refs>
## Canonical References

No external specs, ADRs, or design docs govern this phase — requirements are
fully captured in the decisions above. Relevant in-repo code (for the
researcher/planner, not external specs):

### Sidebar logo load path (the change site)
- `musicstreamer/ui_qt/_art_paths.py` — `load_station_icon()` (full-res decode +
  scale + QPixmapCache); `abs_art_path()` resolver. Primary edit site.
- `musicstreamer/ui_qt/station_tree_model.py` §`data()` (lines ~163-164) —
  calls `load_station_icon` from `DecorationRole`; where async repaint
  (`dataChanged`) would be emitted.
- `musicstreamer/ui_qt/_theme.py` — `STATION_ICON_SIZE = 32` (sidebar logical size).

### Full-res consumer (must remain unchanged)
- `musicstreamer/ui_qt/now_playing_panel.py` — `_load_scaled_pixmap()` (180px
  full-res load). Preserve as-is.

### Storage & art-update paths (thumbnail location + invalidation triggers)
- `musicstreamer/assets.py` — `copy_asset_for_station()` (`assets/{id}/...` layout).
- `musicstreamer/repo.py` — `update_station_art()` (DB choke point for art changes).
- `musicstreamer/aa_import.py`, `musicstreamer/soma_import.py`,
  `musicstreamer/gbs_api.py` — logo download → `copy_asset_for_station`.
- `musicstreamer/ui_qt/edit_station_dialog.py` — manual station-art swap path.
- `musicstreamer/migration.py` — idempotent marker-file pattern (reference only;
  D-02 requires no migration).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `load_station_icon()` already centralizes sidebar icon loading + QPixmapCache +
  fallback + HiDPI canvas — the thumbnail path slots in here behind the same API.
- `abs_art_path()` resolves relative `assets/...` paths to absolute; reuse for
  the thumbnail path too.
- `copy_asset_for_station()` establishes the `assets/{station_id}/` layout the
  thumbnail should live in.

### Established Patterns
- Sidebar icons are produced through the single `load_station_icon` entry point
  (called only from `station_tree_model.data()`), so the optimization has one
  natural choke point.
- QPixmapCache is already the caching layer; keep using it for the in-memory hot
  path, with the on-disk 96px thumb as the cold-start accelerator.
- `FALLBACK_ICON` (`:/icons/audio-x-generic-symbolic.svg`) is the existing
  placeholder — natural choice for the async-gap placeholder.

### Integration Points
- Async repaint requires the tree model to emit `dataChanged` for a row once its
  thumbnail is ready (worker → UI-thread signal → cache insert → repaint).
- `QPixmap` must only be constructed on the UI thread; worker produces `QImage` /
  writes PNG.
</code_context>

<deferred>
## Deferred Ideas

- DPR-aware multi-size thumbnails (@1x/@2x/@3x) — rejected as overkill for a 32px
  icon; revisit only if 96px proves visibly soft on extreme fractional scaling.
- Eager import-time generation + startup backfill warmer — considered and not
  chosen (lazy async is self-healing and migration-free); revisit only if the
  async-gap placeholder flash is judged distracting in practice.

### Reviewed Todos (not folded)
- The 6 todos surfaced by `todo.match-phase 94` (host-env docker probe, several
  failing-test todos, PLS codec fallback) are **false positives** — they matched
  on the placeholder keywords "phase"/"tbd"/"requirements" from the unplanned
  ROADMAP stub, not on sidebar/logo/thumbnail domain relevance. None folded.
</deferred>

---

*Phase: 94-optimize-sidebar-logo-loading-with-pre-scaled-thumbnails-for*
*Context gathered: 2026-06-15*
