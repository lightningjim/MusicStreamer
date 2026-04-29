# Phase 54: Station Logo Aspect Ratio Fix - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the **provider-tree station list rows (32px icon column)** so portrait/non-square station logos render with their full content visible (pillarboxed within the fixed cell), instead of being center-cropped top+bottom. The fix is strictly station-list rows — the now-playing 180×180 viewport, cover-art slot, EditStationDialog 64×64 preview, and Recently Played items are all out of scope (no bug observed there today).

</domain>

<decisions>
## Implementation Decisions

### Surface scope
- **D-01:** Only the **provider-tree rows** in `station_list_panel.py` / `station_tree_model.py` are in scope. Recently Played items, the now-playing 180×180 logo, the cover-art 160×160 fallback, and the EditStationDialog 64×64 preview are NOT touched in this phase. Researcher should still confirm Recently Played reproduces or not, but the user reports "provider tree only".
- **D-02:** Symptom is **portrait logos** (taller than wide) losing their **top+bottom**. Landscape logo behavior in the same surface is unconfirmed — researcher must audit both axes; if landscape is also broken, the fix should address both. If only portrait, target portrait only.
- **D-03:** Target render for a 1:2 portrait logo in the 32px row cell = **16w × 32h pillarboxed, centered**. Row icon-column footprint stays a fixed **32×32** per row so station names remain vertically aligned (SC #4).

### Bar treatment
- **D-04:** Pillarbox bars are **transparent** — the row's normal/hover/selection background paints behind them. No solid color, no theme-bg explicit fill, no image-derived edge color, no rounded-rect frame.
- **D-05:** Logo fills the cell **edge-to-edge** on its longer axis (no inset, no rounded corners, no border). Phase 11 panel rounding does NOT apply at row-icon scale.
- **D-06:** No special hover/selection treatment — logo paints over the row's selection-accent background as today.

### YouTube special-casing
- **D-07:** **Keep the loader uniform.** No YouTube branch, no wider cell for 16:9 thumbs, no square-crop fallback. `load_station_icon` already treats every station identically with `Qt.KeepAspectRatio` — that contract is preserved. YouTube thumbs at 16:9 will render naturally as 32w × 18h letterboxed in the row, just as portrait logos pillarbox to 16w × 32h.
- **D-08:** Phase 18's ContentFit.CONTAIN special-case was for the GTK-era now-playing 180×180 slot only. It's not relevant to row-icon rendering and is not being reintroduced.

### Approach + tests
- **D-09:** **Smallest-diff fix** preferred over a custom QStyledItemDelegate. Researcher diagnoses why the cached aspect-preserving pixmap appears cropped at row-render time despite `_art_paths.py:78` already calling `pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)`. Likely candidates: QIcon's internal pixmap-scaling behavior when the view requests a square pixmap from a non-square source, or the tree's iconSize hint mismatch. Custom delegate is acceptable only if a single-call-site fix can't restore aspect-correct rendering.
- **D-10:** Regression test = **synthetic-pixmap unit test on `load_station_icon`** in `tests/test_art_paths.py`. Test feeds a portrait-shaped synthetic QPixmap (e.g. 50×100), invokes `load_station_icon` at 32px target, asserts the returned QIcon's 32-target pixmap preserves aspect (no top/bottom rows of fallback/transparent appearing where logo content should be). Live UAT also gated on a real broken station after researcher identifies one.
- **D-11:** **No QPixmapCache key bump.** Cache key stays `f"station-logo:{abs_path}"` (Phase 45 contract). Existing `tests/test_art_paths.py` cache-hit assertions stay green.

### Repro
- **D-12:** Affected stations are **AudioAddict channels** + **manually-added stations** (file-picker uploads can be any aspect). YouTube live thumbs are 16:9 landscape — listed as not-the-portrait-case, but researcher should still verify their row rendering during the audit.
- **D-13:** **Researcher digs the SQLite DB** (`musicstreamer.sqlite3`) for non-square station_art assets to find a concrete portrait repro for UAT. User did not pin a specific station name.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap + requirements
- `.planning/ROADMAP.md` §"Phase 54: Station Logo Aspect Ratio Fix" — goal + 4 success criteria (square fully visible, landscape letterboxed, portrait pillarboxed, viewport size/position fixed)
- `.planning/REQUIREMENTS.md` §"BUG-05" — "Rectangular brand logos display fully in the radio logo view (no square-only crop that cuts off content)"
- `.planning/PROJECT.md` §"Current State" — Phase 45 unified-loader context (`load_station_icon`)

### Code that already implements aspect-preserving load
- `musicstreamer/ui_qt/_art_paths.py:48–80` — `load_station_icon(station, size=STATION_ICON_SIZE)` — QPixmapCache-backed QIcon factory; uses `Qt.KeepAspectRatio` already
- `musicstreamer/ui_qt/_theme.py` — `STATION_ICON_SIZE` constant (Phase 46 theme tokens)

### Call sites (the surfaces this phase scopes / does NOT scope)
- `musicstreamer/ui_qt/station_tree_model.py:23, 146` — provider-tree row icons (IN SCOPE)
- `musicstreamer/ui_qt/station_list_panel.py:41, 374` — Recently Played items (out of scope unless researcher proves repro)
- `musicstreamer/ui_qt/now_playing_panel.py:79–91, 141–145, 602–608` — now-playing 180×180 + cover slot fallback (out of scope)
- `musicstreamer/ui_qt/edit_station_dialog.py:254–256, 753–762` — 64×64 logo preview (out of scope)

### Test surface
- `tests/test_art_paths.py` — destination for the synthetic-portrait-pixmap regression test (D-10)

### Prior decisions to respect
- Phase 18 (`.planning/milestones/v1.4-ROADMAP.md`) — ART-03 ContentFit.CONTAIN was for the now-playing slot, not row icons; not being reintroduced (D-08)
- Phase 45 (`.planning/milestones/v2.0-ROADMAP.md`) — unified `load_station_icon` contract (D-07, D-11)
- Phase 46 — theme token usage in `_theme.py` (cell footprint, icon size)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `musicstreamer/ui_qt/_art_paths.py` — `load_station_icon()` is the single chokepoint for every station icon render across the app. Fix lives here or directly in the consuming view.
- `musicstreamer/ui_qt/_theme.py` — `STATION_ICON_SIZE` already drives the 32-target. Reusable for cell footprint sizing.
- `tests/test_art_paths.py` — established test module with cache-hit / fallback / abs-path-resolution coverage. New aspect-ratio test sits next to existing patterns.

### Established Patterns
- **Aspect-preserving scale via `Qt.KeepAspectRatio`** — used in three places (`_art_paths.py:78`, `now_playing_panel.py:91`, `edit_station_dialog.py:759`). Two work; one row-icon path apparently does not.
- **QPixmapCache keyed on absolute path** (`_art_paths.py:71`) — Phase 45 contract; D-11 keeps it intact.
- **Fallback to `:/icons/audio-x-generic-symbolic.svg`** when source pixmap is null. Fix must not break this fallback.

### Integration Points
- The provider tree calls `load_station_icon` via `station_tree_model.data(index, DecorationRole)` — that's where the QIcon meets Qt's view rendering. If the fix needs a custom delegate (D-09 fallback path), it attaches to the tree at `station_list_panel.py:374` area / wherever the QTreeView is constructed.
- `setItemDelegateForColumn` precedent exists at `edit_station_dialog.py` (`_BitrateDelegate` from Phase 47-03) — reusable pattern if D-09 escalates.

### Suspected root-cause hypotheses for the researcher
- `QIcon(pix)` constructed from a non-square cached pixmap: when Qt asks the QIcon for a square pixmap (matching the view's `iconSize()`), it may scale the cached pixmap with crop-to-fill semantics rather than fit-with-bars.
- The tree's `iconSize` may default to a different hint than `STATION_ICON_SIZE`, causing on-the-fly re-scaling that loses aspect.
- The QStandardItem `setIcon()` path in `station_list_panel.py:374` (Recently Played) may render differently than the model `data()` path in `station_tree_model.py:146` — the fact that the user only reports the tree, not Recently Played, is a useful signal.

</code_context>

<specifics>
## Specific Ideas

- "Top+bottom cut off" for portrait logos is a literal symptom — the rendered pixel result loses the top and bottom of the source image. That's center-crop-to-square behavior, despite the loader cache being shaped 16w×32h.
- AudioAddict + manually-uploaded logos are the known-broken cases. AA logos come from the AA API (post-Phase 17 / Phase 999.7 logo path). Manually-added go through `_on_choose_logo` in EditStationDialog.
- User wants a small, focused fix — not a delegate refactor unless researcher proves the loader-only fix can't work.

</specifics>

<deferred>
## Deferred Ideas

- **Now-playing 180×180 portrait audit** — user did not report a bug there, but researcher offered to audit it as a parallel-latent check. Not in this phase. If researcher discovers a parallel bug, file as a follow-up phase, not scope creep.
- **Custom QStyledItemDelegate for station-tree row icons** — escalation path only if loader-only fix can't restore aspect-correct rendering (D-09). Not the default approach.
- **Wider row cell for 16:9 YouTube thumbs** — explicitly rejected (D-07). If a future phase wants to surface YouTube thumbs more prominently in the tree, that's a separate UX phase.
- **Image-derived edge-color pillarbox bars** — explicitly rejected (D-04). Considered only as a stylistic upgrade in some future visual-polish phase, not this fix.

</deferred>

---

*Phase: 54-Station Logo Aspect Ratio Fix*
*Context gathered: 2026-04-29*
