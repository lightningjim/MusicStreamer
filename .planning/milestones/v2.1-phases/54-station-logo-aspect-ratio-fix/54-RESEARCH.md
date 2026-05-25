# Phase 54: Station Logo Aspect Ratio Fix - Research

**Researched:** 2026-04-29
**Domain:** PySide6 / Qt 6.11 model-view rendering — QIcon decoration in QTreeView rows
**Confidence:** HIGH on diagnosis (verified by hands-on Qt probing); MEDIUM on the right plan-shape (depends on UAT-driven validation that the user is observing what they think they are observing)

## Summary

Phase 54 was filed as "portrait logos lose top+bottom in tree rows; pillarbox them at 16w × 32h." Hands-on probing of the existing code with PySide6 6.11.0 (project pin: `PySide6>=6.11`) shows that **the existing pipeline already pillarboxes / letterboxes non-square logos correctly in the provider tree** — there is no observable cropping bug in the in-scope surface today.

Two observations made during research force a re-shape of the plan:

1. **The live DB has zero portrait-shaped station logos.** Of 172 stations with `station_art_path` populated: 142 are square (1000×1000 AudioAddict), 30 are 16:9 landscape (1280×720, mostly YouTube), 0 are taller-than-wide. There is no portrait-shaped repro available locally.
2. **The in-scope rendering path already handles non-square pixmaps correctly.** A QIcon constructed from a `Qt.KeepAspectRatio`-scaled pixmap, painted into a 32×32 QTreeView row cell with `tree.setIconSize(QSize(32, 32))` and the existing `StationStarDelegate`, renders pillarboxed portraits at 16w × 32h and letterboxed landscapes at 32w × 16h. Verified at the pixel level — see Root Cause Analysis.

This means the phase has two valid landings, and the plan must choose between them with a quick clarification step:

- **Path A — preserve-via-test (preferred).** Lock the current correct behavior in `tests/test_art_paths.py` per D-10 (synthetic-portrait-pixmap regression test), add a parallel landscape test, ship those two tests, and run live UAT against the Cafe BGM 1280×720 YouTube logo (concrete repro from the live DB) and a synthetic portrait fixture installed temporarily for the test session. If UAT shows row icons render aspect-correctly today, **this phase ships only as a regression-lock** — no production code change. This is the smallest-diff outcome and is consistent with D-09.
- **Path B — diff-on-platform-mismatch.** If live UAT on the user's machine actually shows cropped portrait logos (i.e. my probe disagrees with the user's eyes — possible on Windows due to a platform-style difference, or possible because the user is looking at a surface I haven't considered), the fix lands in `_art_paths.py:48–80` as documented in §3 below.

**Primary recommendation:** Plan Wave 1 as the regression test pair (D-10) + a UAT step that installs a synthetic portrait logo on a test station, captures a screenshot, and gates Path-A vs Path-B with explicit user confirmation. Do not ship a delegate (D-09 fallback) — there is no evidence it is needed.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Aspect-preserving image scale | Loader (`_art_paths.load_station_icon`) | — | Already does `pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)` (line 78); single chokepoint per Phase 45 contract |
| Icon delivery to view | Model (`StationTreeModel.data` DecorationRole) | — | Returns the QIcon from the loader; no transformation applied (line 146) |
| Cell size + iconSize hint | View (`QTreeView` in `station_list_panel.py:280`) | — | `setIconSize(QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))` = (32, 32); fixed cell footprint per D-03 |
| Row paint (icon + star) | Delegate (`StationStarDelegate.paint`) | Qt style | `super().paint(...)` invokes default item-view paint, which uses `option.icon.paint(...)` to render decoration; star painted on top |
| Pillarbox transparency | Qt's QIcon::paint built-in behavior | — | Empty area in non-square pixmap rendered as transparent — D-04 satisfied automatically |

Tier ownership note: every decision the plan needs to make lives at the **loader** tier. The model and view are already correct.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Surface scope**
- **D-01:** Only the **provider-tree rows** in `station_list_panel.py` / `station_tree_model.py` are in scope. Recently Played items, the now-playing 180×180 logo, the cover-art 160×160 fallback, and the EditStationDialog 64×64 preview are NOT touched in this phase. Researcher should still confirm Recently Played reproduces or not, but the user reports "provider tree only".
- **D-02:** Symptom is **portrait logos** (taller than wide) losing their **top+bottom**. Landscape logo behavior in the same surface is unconfirmed — researcher must audit both axes; if landscape is also broken, the fix should address both. If only portrait, target portrait only.
- **D-03:** Target render for a 1:2 portrait logo in the 32px row cell = **16w × 32h pillarboxed, centered**. Row icon-column footprint stays a fixed **32×32** per row so station names remain vertically aligned (SC #4).

**Bar treatment**
- **D-04:** Pillarbox bars are **transparent** — the row's normal/hover/selection background paints behind them. No solid color, no theme-bg explicit fill, no image-derived edge color, no rounded-rect frame.
- **D-05:** Logo fills the cell **edge-to-edge** on its longer axis (no inset, no rounded corners, no border). Phase 11 panel rounding does NOT apply at row-icon scale.
- **D-06:** No special hover/selection treatment — logo paints over the row's selection-accent background as today.

**YouTube special-casing**
- **D-07:** **Keep the loader uniform.** No YouTube branch, no wider cell for 16:9 thumbs, no square-crop fallback. `load_station_icon` already treats every station identically with `Qt.KeepAspectRatio` — that contract is preserved. YouTube thumbs at 16:9 will render naturally as 32w × 18h letterboxed in the row, just as portrait logos pillarbox to 16w × 32h.
- **D-08:** Phase 18's ContentFit.CONTAIN special-case was for the GTK-era now-playing 180×180 slot only. It's not relevant to row-icon rendering and is not being reintroduced.

**Approach + tests**
- **D-09:** **Smallest-diff fix** preferred over a custom QStyledItemDelegate. Custom delegate is acceptable only if a single-call-site fix can't restore aspect-correct rendering.
- **D-10:** Regression test = **synthetic-pixmap unit test on `load_station_icon`** in `tests/test_art_paths.py`.
- **D-11:** **No QPixmapCache key bump.** Cache key stays `f"station-logo:{abs_path}"` (Phase 45 contract).

**Repro**
- **D-12:** Affected stations are AudioAddict channels + manually-added stations.
- **D-13:** Researcher digs SQLite DB for a non-square portrait repro.

### Claude's Discretion
- Exact synthetic-pixmap dimensions in the test (D-10 says "e.g. 50×100" — researcher chooses).
- Whether to add a parallel landscape test even though D-02 only confirmed portrait.
- The exact assertion shape for "aspect preserved" (toImage equality, dimension comparison, pixel-corner sampling, or a mix).

### Deferred Ideas (OUT OF SCOPE)
- Now-playing 180×180 portrait audit — separate phase if a parallel-latent bug surfaces.
- Custom QStyledItemDelegate for station-tree row icons — escalation path only (D-09).
- Wider row cell for 16:9 YouTube thumbs — explicitly rejected (D-07).
- Image-derived edge-color pillarbox bars — explicitly rejected (D-04).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUG-05 | Rectangular brand logos display fully in the radio logo view (no square-only crop that cuts off content) | §1 confirms current pipeline already preserves aspect for both portrait and landscape in the in-scope surface; §4 specifies the regression-lock test that ensures a future change cannot reintroduce cropping; §5 names a concrete repro station for live UAT |

### Phase 54 Success Criteria → Verification Map

| SC | Criterion | Verification |
|----|-----------|--------------|
| SC #1 | Square logo displays fully (no edge cropping) | Existing test `test_relative_station_art_path_resolves_via_abs_art_path` already covers a 64×64 square; live UAT against AudioAddict 1000×1000 station id=10 "20th Century" |
| SC #2 | Landscape logo displays fully (letterboxed) | NEW test `test_load_station_icon_preserves_landscape_aspect` (synthetic 100×50 → 32×16 assertion); live UAT against YouTube 1280×720 station id=2 "Living Coffee: Smooth Jazz Radio" |
| SC #3 | Portrait logo displays fully (pillarboxed) | NEW test `test_load_station_icon_preserves_portrait_aspect` (synthetic 50×100 → 16×32 assertion); live UAT requires installing a synthetic portrait file on a test station (no portrait exists in DB) |
| SC #4 | Logo viewport size/position does not shift between stations | Verified by inspection of `tree.setIconSize(QSize(32, 32))` + `setUniformRowHeights(True)` + `StationStarDelegate.sizeHint` returning fixed `base.height()` — no per-row variation possible |
</phase_requirements>

## 1. Root Cause Analysis

**Headline finding: the existing rendering pipeline does NOT crop non-square logos in the provider tree.** The bug as filed is not reproducible against the current codebase on PySide6/Qt 6.11.0 (Linux, offscreen Qt platform).

### Pipeline trace (file:line)

The data flow for a station logo from disk to a tree row pixel:

1. `_art_paths.py:73–79` — `load_station_icon(station, size=32)` calls `QPixmap(load_path)`, then `pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)`. For a 50×100 portrait input, this returns a **16×32** pixmap. For a 1280×720 landscape input, this returns a **32×18** pixmap. Verified by hands-on probe.
2. `_art_paths.py:80` — wraps the (possibly non-square) pixmap with `QIcon(pix)`. The QIcon stores the pixmap at its actual aspect ratio.
3. `station_tree_model.py:145–146` — `data(index, Qt.DecorationRole)` returns the QIcon as-is. No re-scaling. No transformation.
4. `station_list_panel.py:280` — `tree.setIconSize(QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))` = (32, 32). Cell footprint hint.
5. `station_list_panel.py:292` — `tree.setItemDelegate(self._star_delegate)` installs `StationStarDelegate`, whose `paint()` (in `station_star_delegate.py:46–47`) calls `super().paint(painter, option, index)` first. The super-class (`QStyledItemDelegate`) calls `QApplication.style().drawControl(CE_ItemViewItem, option, painter, ...)`, which in turn invokes `option.icon.paint(painter, option.decorationRect, option.decorationAlignment, ...)`.
6. `QIcon::paint(painter, rect, alignment, mode, state)` — when alignment is centered (the default for item views), Qt calls `pixmap(rect.size())` to retrieve a pixmap, then draws it centered in `rect`. **Per Qt 6.11 docs (`QIcon::pixmap` contract): "the pixmap might be smaller than requested, but never larger" [CITED: doc.qt.io/qt-6/qicon.html#pixmap]**. Asking the QIcon for a 32×32 pixmap when the source is 16×32 returns a 16×32 pixmap unchanged. Qt then center-paints that 16×32 pixmap inside the 32×32 `decorationRect` — producing 8px transparent pillarbox bars on each side, with the row's row background visible behind them.

### Hands-on probe (2026-04-29, PySide6 6.11.0, Qt 6.11.0)

`QT_QPA_PLATFORM=offscreen python3` script ran the full stack: real `StationTreeModel` populated from a real `Station` (YouTube provider, `station_art_path` = absolute path to a 1280×720 JPEG from the live DB), real `StationStarDelegate`, real `tree.setIconSize(QSize(32, 32))`, real `setUniformRowHeights(True)`. Rendered the viewport to a PNG and pixel-scanned the result.

Result (at `/tmp/tree_with_delegate.png`):

- The 1280×720 logo scales to 32w × 18h.
- In the 32px-tall row, the icon is centered vertically at y ≈ 7..25 (offscreen platform), with empty top + bottom strips that **show through to the row's selection background** (transparent).
- The star is correctly painted at the right edge.
- No cropping. No stretching. Aspect preserved.

A synthetic 50×100 portrait QPixmap (filled with red, no PIL/file-IO required) ran through the same path produces a centered 16×32 pillarboxed icon in the 32×32 cell. Verified at the pixel level — pixel `(8, 16)` is red (logo content), pixel `(0, 0)` and `(24, 16)` are transparent (pillarbox bars).

### Why the four hypotheses from CONTEXT.md `<code_context>` did not pan out

| # | Hypothesis | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | `_art_paths.py:78` `Qt.KeepAspectRatio` should produce a 16×32 cached pixmap; **why does the row paint cropped?** | Loader output is 16×32 as expected. Tree row also paints 16×32 pillarboxed. **No cropping at any stage.** | Probe at every stage |
| 2 | QIcon's internal scaling crops to fill when view requests square pixmap from non-square source | False. `QIcon(pix_16x32).pixmap(QSize(32, 32))` returns a 16×32 pixmap unchanged. Qt docs confirm: "smaller than requested, but never larger" | `icon.pixmap(QSize(32, 32))` returned `16x32` in probe; QIcon docs |
| 3 | Tree's `iconSize` mismatch with `STATION_ICON_SIZE` causes on-the-fly rescale | False. `station_list_panel.py:280` sets `tree.setIconSize(QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))` = (32, 32) — exact match with the loader's default. No mismatch anywhere | grep `setIconSize` confirms three call sites all use `STATION_ICON_SIZE` |
| 4 | Path divergence — model `data()` (tree) renders differently than `QStandardItem.setIcon()` (Recently Played) | Both paths produce identical aspect-correct output for non-square icons. Recently Played uses `QListView.setIconSize(QSize(32, 32))` at `station_list_panel.py:174` — exact same hint as tree | Probe rendered both styles; both pillarbox correctly |

### So why does the user perceive a bug?

I cannot fully resolve this from research alone. Plausible explanations the planner should weigh:

- **Misperception of letterboxing as cropping.** The 16:9 YouTube logos and ~1000×1000 AudioAddict logos in the live DB are square or landscape. The user may be looking at the 32×18 letterboxed YouTube logos in the tree and reading the empty top + bottom strips as "the logo is cropped." That is the opposite — the empty strips ARE the aspect preservation.
- **Platform-specific style.** The probe ran on Linux/offscreen. It's conceivable that on a different `QStyle` (e.g. Windows native, or KDE with `Adwaita-Qt` style) the default item-view decoration alignment differs and could produce visible artifacts. **Researcher could not test this from a Linux box; this is a known gap.**
- **Cached pixmap from a previous build.** `QPixmapCache` is process-scoped, so this is unlikely across runs, but worth ruling out by clearing the cache or restarting.
- **Looking at a surface the user thinks is in-scope but isn't.** Possible but D-01 explicitly locks scope to provider-tree rows, so this is a discussion-time issue, not a research issue.

The plan must include a **UAT screenshot step** that confirms whether the current build actually renders cropped portrait logos on the user's machine, **before** writing any production code change.

## 2. Landscape Audit Result

**Landscape: aspect-preserved correctly today. Not broken.**

Evidence: a 1280×720 YouTube logo (station id=2, "Living Coffee: Smooth Jazz Radio") scaled by `load_station_icon` produces a 32×18 pixmap. Rendering through the real `StationTreeModel` + `StationStarDelegate` pipeline produces a centered 32w × 16h-equivalent letterboxed image in the 32×32 cell. See `/tmp/tree_with_delegate.png` from the probe (image attached visually during research).

The ratio is preserved end-to-end. No top/bottom cropping; the empty strips above and below the logo are transparent and show the row's selection background.

**This means D-02's caveat ("if landscape is also broken, fix should address both") collapses to: nothing to fix on the landscape axis.** The plan can scope the test pair to portrait + landscape regardless, since the existing behavior is symmetric.

## 3. Smallest-Diff Fix Proposal

### Path A — preserve-via-test (PREFERRED)

**Production code change: NONE.** `load_station_icon` is already aspect-correct.

The phase ships:

1. New test `test_load_station_icon_preserves_portrait_aspect` in `tests/test_art_paths.py` (D-10).
2. New test `test_load_station_icon_preserves_landscape_aspect` in `tests/test_art_paths.py` (parallel coverage).
3. Live UAT step that visually confirms current behavior on the user's machine — gates whether to escalate to Path B.

This satisfies BUG-05 by **locking the existing correct behavior against future regression**. SC #1, #2, #3, #4 are already TRUE today; the tests prove they remain TRUE.

**Why this is the smallest diff per D-09:** Zero production lines changed. The cache key is unchanged (D-11). The loader contract is unchanged (D-07). No delegate is introduced (D-09 fallback path not taken).

### Path B — escalation IF UAT shows real cropping on the user's machine

**Trigger condition:** Live UAT on the user's machine demonstrably shows a portrait or landscape logo in the provider tree being center-cropped (i.e. the pixel data my probe produced does not match what the user sees in the running app).

If this triggers, the fix shape depends on where the divergence actually lives. Three escalation options ordered by diff size:

#### B-1: Render-to-square-canvas in `load_station_icon` (smallest escalation diff)

Modify `_art_paths.py:73–80` to paint the aspect-scaled pixmap onto a transparent square canvas of `(size, size)` before wrapping in QIcon. This eliminates any platform-style ambiguity about how a non-square pixmap is centered in a square decoration rect.

```python
# musicstreamer/ui_qt/_art_paths.py — replace lines 73–80
from PySide6.QtCore import QPoint
from PySide6.QtGui import QPainter

pix = QPixmap()
if not QPixmapCache.find(key, pix):
    src = QPixmap(load_path)
    if src.isNull():
        src = QPixmap(FALLBACK_ICON)
    scaled = src.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    # Paint onto a transparent square canvas so QIcon stores a perfectly
    # square pixmap with the logo centered and pillarbox/letterbox transparent.
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    x = (size - scaled.width()) // 2
    y = (size - scaled.height()) // 2
    painter.drawPixmap(QPoint(x, y), scaled)
    painter.end()
    QPixmapCache.insert(key, pix)
return QIcon(pix)
```

**Diff scope:** ~10 lines changed in one function in one file. No callers affected. Cache key unchanged (D-11). Fallback path preserved (`src.isNull()` check kept). Loader contract unchanged externally — still returns a `QIcon` for any station.

**Why this fixes a hypothetical cropping bug:** the QIcon now wraps a perfectly square pixmap, so any platform-style code path that was previously confused by a non-square icon-source pixmap can no longer crop. The transparent bars satisfy D-04. The aspect of the original logo is preserved on the longer axis (D-03 — 16w × 32h for 1:2 portrait). D-05 (edge-to-edge on longer axis) is automatic from the centering math.

**Tradeoff:** ~6× memory per cached icon (storing a 32×32 RGBA pixmap instead of a 16×32 one for portrait) — negligible at 172 stations × 4KB = ~700KB. SmoothTransformation already runs once at scale time; no additional CPU.

#### B-2: Custom `QStyledItemDelegate` for the icon column (D-09 fallback)

Reject this unless B-1 fails to fix the visible bug. The current tree is already wearing `StationStarDelegate` (set via `tree.setItemDelegate`, NOT `setItemDelegateForColumn`), which means **a second `setItemDelegateForColumn` would conflict** with the star delegate. Path B-2 would require either:

- Folding pillarbox-paint into `StationStarDelegate.paint()` (paint icon ourselves with `QPainter.drawPixmap(option.rect, scaled_pixmap, ...)`, skip super decoration), then super-paint star — adds ~15 lines to `station_star_delegate.py`; **changes a delegate already in production** for a hypothetical paint problem.
- Creating a separate StationLogoDelegate, but tree only supports one item delegate per column. Composition would require reworking how the star delegate is attached. Significantly more diff.

Neither is appealing. Path B-1 is strictly better than B-2.

### Recommendation

Plan Wave 1 ships Path A (tests + UAT screenshot gate). Wave 2 ships Path B-1 conditionally, only if the UAT screenshot shows actual cropping. Path B-2 stays in `<deferred>` per D-09.

## 4. Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9 + pytest-qt 4 [VERIFIED: pyproject.toml] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_art_paths.py -x` |
| Full suite command | `pytest` (per `testpaths = ["tests"]`) |
| Existing fixtures | `qtbot` (auto from pytest-qt), `tmp_data_dir` (in `test_art_paths.py:55`), `_isolate_pixmap_cache` (autouse, in `test_art_paths.py:46`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUG-05 / SC #3 | Portrait 1:2 logo scales to 16w × 32h with aspect preserved | unit | `pytest tests/test_art_paths.py::test_load_station_icon_preserves_portrait_aspect -x` | New test — Wave 0 |
| BUG-05 / SC #2 | Landscape 2:1 logo scales to 32w × 16h with aspect preserved | unit | `pytest tests/test_art_paths.py::test_load_station_icon_preserves_landscape_aspect -x` | New test — Wave 0 |
| BUG-05 / SC #1 | Square logo unchanged | unit | `pytest tests/test_art_paths.py::test_default_size_is_32px -x` (existing) | ✅ Exists |
| BUG-05 / SC #4 | Row footprint stays 32×32 | manual | UAT screenshot (no automated row-height test in current suite) | UAT only |

### Test Specification

**Test 1: portrait aspect preserved (D-10 specifies 50×100 example).**

```python
def test_load_station_icon_preserves_portrait_aspect(qtbot):
    """A portrait source pixmap (50w × 100h, 1:2) is loaded as a 16w × 32h
    pixmap inside the returned QIcon — aspect ratio preserved, no center crop.
    Regression lock for BUG-05 / SC #3.
    """
    # Synthetic source — no filesystem I/O. Covers Path A regression-lock and
    # would also fail under a hypothetical future change that reintroduced
    # crop-to-square scaling.
    src = QPixmap(50, 100)
    src.fill(Qt.red)
    # Construct a station whose station_art_path is a real on-disk file so the
    # loader takes the QPixmap(load_path) branch. We must materialize the
    # synthetic pixmap to disk because load_station_icon resolves via path.
    import os
    art_path = os.path.join(_isolate_path_for_test, "synthetic_portrait.png")
    assert src.save(art_path, "PNG"), "test fixture save failed"

    station = _make_station(art_path)
    icon = load_station_icon(station)

    # Ask the icon for a 32x32 pixmap — the row's iconSize hint.
    pix = icon.pixmap(QSize(32, 32))

    # Aspect-preserving 50x100 -> 32-bound -> 16x32.
    assert pix.width() == 16, f"expected pillarboxed 16w, got {pix.width()}w"
    assert pix.height() == 32, f"expected full-height 32h, got {pix.height()}h"
    # Sanity: ratio is 1:2 (within rounding).
    assert abs(pix.height() / pix.width() - 2.0) < 0.01
```

**Test 2: landscape aspect preserved (parallel coverage for SC #2).**

```python
def test_load_station_icon_preserves_landscape_aspect(qtbot):
    """A landscape source pixmap (100w × 50h, 2:1) is loaded as a 32w × 16h
    pixmap — aspect ratio preserved, no center crop. Covers SC #2.
    """
    src = QPixmap(100, 50)
    src.fill(Qt.blue)
    art_path = os.path.join(_isolate_path_for_test, "synthetic_landscape.png")
    assert src.save(art_path, "PNG")

    station = _make_station(art_path)
    icon = load_station_icon(station)
    pix = icon.pixmap(QSize(32, 32))

    assert pix.width() == 32, f"expected full-width 32w, got {pix.width()}w"
    assert pix.height() == 16, f"expected letterboxed 16h, got {pix.height()}h"
    assert abs(pix.width() / pix.height() - 2.0) < 0.01
```

**Fixture choice — why save to disk instead of pure in-memory:**

`load_station_icon` accepts a `station` object and resolves `station.station_art_path` through `abs_art_path` and `QPixmap(load_path)`. There is no in-memory pixmap entry point. Mocking the file lookup is more invasive than just writing a 50×100 PNG to a temp file via `tmp_data_dir` — the existing test pattern (`_write_logo` helper at `tests/test_art_paths.py:38`). I recommend extending `_write_logo` to take optional `width` / `height`:

```python
def _write_logo(path: str, size: int = 64, width: int | None = None, height: int | None = None) -> None:
    """Write a real PNG file at the given (width, height) or square size."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    w = width if width is not None else size
    h = height if height is not None else size
    pix = QPixmap(w, h)
    pix.fill(Qt.red)
    assert pix.save(path, "PNG"), f"failed to write fixture logo at {path}"
```

This preserves all 7 existing test call sites (they pass only `path` and optional `size`) while unlocking the new `width=50, height=100` and `width=100, height=50` calls.

### Sampling Rate

- **Per task commit:** `pytest tests/test_art_paths.py -x` (~2s, runs all 9 tests after the 2 additions).
- **Per wave merge:** `pytest -x` (full suite, ~30–60s).
- **Phase gate:** Full suite green + Live UAT visual confirmation (per Path A vs Path B branch).

### Wave 0 Gaps

- [x] `tests/test_art_paths.py` already exists with shared `_make_station`, `_write_logo`, `tmp_data_dir`, `_isolate_pixmap_cache` fixtures.
- [ ] Extend `_write_logo` to accept `width` / `height` kwargs (Wave 1 task — backwards compatible).
- [ ] No new framework install or conftest change required.

**Verdict:** Test infrastructure is ready. Wave 0 gap is just the `_write_logo` signature extension, which can fold into the same Wave 1 commit as the two new tests.

### Live UAT Steps

UAT runs in a single session and gates Path A vs Path B:

1. **Existing landscape repro (in DB):** Launch the app. Navigate to the "Cafe BGM" provider in the tree. Visually inspect the row icon for "Living Coffee: Smooth Jazz Radio - Relaxing Jazz & Sweet Bossa Nova for Calm at Home" (station id=2). Expected: 32w × 16h-equivalent letterboxed YouTube thumbnail with the row's selection-accent background visible above and below the logo. Capture screenshot.
2. **Square baseline (in DB):** Inspect any "ClassicalRadio" station row (e.g. id=10 "20th Century"). Expected: 32×32 logo filling the cell. Capture screenshot.
3. **Synthetic portrait (NOT in DB — must be installed):** Use the EditStationDialog to upload a synthetic 50×100 portrait PNG (created with `python3 -c "from PySide6.QtGui import QPixmap; from PySide6.QtCore import Qt; from PySide6.QtWidgets import QApplication; import sys; app=QApplication(sys.argv); p=QPixmap(50,100); p.fill(Qt.red); p.save('/tmp/portrait.png','PNG')"`) onto any test station, then inspect the tree row. Expected: 16w × 32h pillarboxed red rectangle, transparent strips on left + right.
4. **Decision gate:**
    - If steps 1, 2, 3 all match expectations → **Path A.** Tests pass, no production change needed, ship.
    - If step 1 or 3 shows actual cropping (top + bottom missing on portrait, or left + right missing on landscape) → **Path B-1.** Apply the `_art_paths.py` patch from §3 above; rerun all UAT steps.

Acceptance criteria are grep-verifiable in `tests/test_art_paths.py`:
```
def test_load_station_icon_preserves_portrait_aspect
def test_load_station_icon_preserves_landscape_aspect
```

## 5. Repro Station(s) from Live DB

Audit of `/home/kcreasey/.local/share/musicstreamer/musicstreamer.sqlite3` (172 stations with `station_art_path` set, all assets present on disk):

| Aspect class | Count | Example station for UAT |
|--------------|-------|--------------------------|
| Square (≥0.95–1.05 ratio) | 142 | id=10 "20th Century" (ClassicalRadio), 1000×1000, art at `assets/10/station_art.jpg` |
| Landscape (w > h × 1.05) | 30 | **id=2 "Living Coffee: Smooth Jazz Radio"** (Cafe BGM), 1280×720, art at `assets/2/station_art.jpg` |
| Portrait (h > w × 1.05) | **0** | **None exist in the live DB.** |

**Concrete UAT recommendations:**

- **Landscape repro (in-DB, ready to use):** "Living Coffee: Smooth Jazz Radio" — Cafe BGM provider, station id=2. Asset: `~/.local/share/musicstreamer/assets/2/station_art.jpg` (1280×720 JPEG). Verified to exist; verified to load via `QPixmap` without isNull. This is the exact AudioAddict + YouTube class of station the bug report calls out.
- **Square baseline:** Any ClassicalRadio station, e.g. id=10 "20th Century" (1000×1000).
- **Portrait repro:** **Must be synthesized** — no portrait logos exist in the user's library. Recommended approach: write a 50×100 red PNG to `/tmp/portrait.png`, then use EditStationDialog → "Choose Logo…" on a throw-away test station (or temporarily on any existing station — note its old `station_art_path` to restore afterward). The synthetic test handles the regression-lock case automatically; live UAT for portrait requires this manual fixture install because the user's data does not contain the case.

**Why no portrait stations exist:** AudioAddict serves square (1000×1000) art. YouTube serves 16:9 (1280×720) thumbs. PLS / manually-uploaded stations could be any aspect, but the user has none currently. The bug-report mention of "AudioAddict + manually-added" being broken is the strongest signal that the user is observing **landscape behavior misread as cropping** (item 1 in the §1 "why does the user perceive a bug" list).

## 6. Threat Model

UI rendering change to a single helper. Scope is narrow.

| Surface | Risk | Mitigation |
|---------|------|------------|
| `pix.isNull()` fallback path | Path B-1 must not break the FALLBACK_ICON branch | The `isNull` check stays at lines 76–77 unchanged in Path B-1; the canvas-paint runs uniformly on either real-or-fallback `src` |
| File-IO surface | Could a malicious station_art_path inject a path-traversal attack via `abs_art_path`? | `abs_art_path` is unchanged. It joins `paths.data_dir()` + relative path with `os.path.join`, which on its own does NOT prevent traversal (`../`) — but the real attack surface is the asset-import flow (`assets.copy_asset_for_station`), not the loader. The loader only loads what's already been written. **No new file-IO surface introduced** by either Path A or Path B-1. |
| QPainter resource leak (Path B-1 only) | `QPainter(pix)` must `painter.end()` before the QPixmap is read | Path B-1 patch ends the painter explicitly before `QPixmapCache.insert`. Standard pattern; mirrors `now_playing_panel.py:576` etc. |
| Cache eviction during paint | If the cached pixmap is evicted between `QPixmapCache.find()` and `QIcon(pix)`, the icon could become null | Existing risk; unchanged. `QPixmapCache.find` returns `False` if evicted, the loader rebuilds; the QIcon wraps the local `pix` reference, not a cache pointer. |
| FALLBACK_ICON aspect | Phase 54 must not alter the fallback's appearance for stations with no `station_art_path` | FALLBACK_ICON (`audio-x-generic-symbolic.svg`) is square at the bundled SVG level. Path A leaves it untouched. Path B-1 paints it onto a 32×32 transparent canvas centered — same visual result as today (square SVG centered in square cell). No regression. |

**ASVS V5 Input Validation:** the function takes a `station` object whose `station_art_path` came from the DB, which came from either AA API (`aa_import.copy_asset_for_station`) or the user's file-picker (`edit_station_dialog._on_choose_logo`). Both paths copy the file into `paths.assets_dir()` before storing the relative path. The loader is downstream of all input validation.

**Verdict:** No new threat surface. Both Path A and Path B-1 preserve the existing fallback flow.

## Common Pitfalls (for the planner)

### Pitfall 1: shipping a delegate when no fix is needed

**What goes wrong:** Planner reads "Phase 54: Station Logo Aspect Ratio Fix" and assumes a code change is required, drafts a custom `QStyledItemDelegate`, lands hundreds of lines for a non-bug.
**Why it happens:** Phase title implies "fix" — but research shows the existing pipeline is already correct on Linux/Qt 6.11.0.
**How to avoid:** Plan Wave 1 = test + UAT gate. Path B is conditional on UAT screenshot showing real cropping.
**Warning signs:** Plan introduces `setItemDelegateForColumn` or modifies `station_star_delegate.py` — these would conflict with the existing single-item-delegate setup.

### Pitfall 2: extending `_write_logo` and breaking 7 existing call sites

**What goes wrong:** Adding `width`/`height` kwargs without defaults; or making them required.
**Why it happens:** Test refactor reflex.
**How to avoid:** New kwargs default to `None`; preserve `size` semantics.

### Pitfall 3: assuming the synthetic pixmap can be passed in-memory

**What goes wrong:** Planner assumes `load_station_icon` accepts a `QPixmap` directly and writes a test that does not match the loader's signature.
**Why it happens:** Loader takes a `Station` object whose `station_art_path` is a string path, not a pixmap.
**How to avoid:** Tests must save the synthetic pixmap to a real on-disk file path inside `tmp_data_dir`, then construct `Station(station_art_path=<rel_path>)`.

### Pitfall 4: bumping the QPixmapCache key in Path B-1

**What goes wrong:** Plan changes the cache key string to invalidate old entries.
**Why it happens:** Reflex when changing what the cache stores.
**How to avoid:** D-11 explicitly forbids this. Existing test `test_cache_hit_on_second_call` will fail if the key changes. Path B-1 changes only the **pixel content** stored under the same key; that's cache-coherent for a fresh process.

### Pitfall 5: reading "portrait" success criteria literally without realizing no DB has portrait logos

**What goes wrong:** Planner gates UAT on finding a portrait logo in the DB, can't, blocks the phase.
**Why it happens:** D-13 says "researcher digs the DB for a portrait repro" — but the answer is "none exists."
**How to avoid:** Plan installs a synthetic portrait via the EditStationDialog logo-upload flow as a UAT setup step. §4 step 3 above documents this.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Aspect-preserving image scale | Custom math | `QPixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)` | Already in use; battle-tested; subpixel-accurate |
| Centering a smaller pixmap inside a square canvas | Custom math + per-pixel loop | `QPainter.drawPixmap(QPoint(x, y), scaled)` with `(size - scaled.width()) // 2` for x | Standard Qt idiom; matches `now_playing_panel.py:91` style |
| Synthetic test pixmaps | PIL `Image.new` + `Image.save` | `QPixmap(w, h).fill(color); pix.save(path, "PNG")` | Already used in `tests/test_art_paths.py:_write_logo`; no PIL dependency added |
| Item-view icon rendering | Custom `paint()` override | `QStyledItemDelegate` super().paint() — Qt handles decoration alignment, hover, selection automatically | Phase 38-02's `StationStarDelegate` already pattern-leads with this approach |

## Sources

### Primary (HIGH confidence — verified by hands-on probe)

- **PySide6 / Qt installed version:** PySide6 6.11.0, Qt 6.11.0 — verified by `python3 -c "import PySide6; print(PySide6.__version__)"` [VERIFIED]
- **`_art_paths.py:48–80` `load_station_icon`** — read directly [VERIFIED]
- **`station_tree_model.py:23, 145–146`** — DecorationRole returns the QIcon as-is [VERIFIED]
- **`station_list_panel.py:174, 280, 292`** — `setIconSize(QSize(STATION_ICON_SIZE, STATION_ICON_SIZE))` and `setItemDelegate(StationStarDelegate)` [VERIFIED]
- **`station_star_delegate.py:46–47`** — `super().paint()` invokes default item-view decoration paint [VERIFIED]
- **Hands-on probes** — saved screenshots at `/tmp/tree_with_delegate.png`, `/tmp/tree_real_logos.png`, `/tmp/tree_default_iconsize.png`, `/tmp/tree_with_iconsize_32.png` show portrait + landscape rendering aspect-correctly [VERIFIED]
- **Live SQLite audit** — 172 stations, 0 portrait, 30 landscape, 142 square — `/home/kcreasey/.local/share/musicstreamer/musicstreamer.sqlite3` [VERIFIED 2026-04-29]

### Secondary (MEDIUM confidence — official docs)

- **QIcon::pixmap contract:** "the pixmap might be smaller than requested, but never larger" [CITED: doc.qt.io/qt-6/qicon.html#pixmap]
- **QStyledItemDelegate paint behavior:** invokes `QStyle::drawControl(CE_ItemViewItem, ...)` which renders decoration via `option.icon.paint(...)` [CITED: doc.qt.io/qt-6/qstyleditemdelegate.html]

### Tertiary (LOW confidence — unverified, not relied upon)

- Web searches for "QStyledItemDelegate non-square QIcon decoration crops aspect ratio" returned no specific known-bug entries for Qt 6.x. Absence of evidence is not evidence of absence; the platform-style explanation in §1 remains a possibility for the user's environment specifically.

## Open Questions

1. **Does the user actually see cropping on their build?**
   - What we know: probe on Linux/Qt 6.11.0/offscreen platform shows correct aspect-preserved rendering.
   - What's unclear: whether the user's actual running build (Linux, X11/Wayland Qt platform with their desktop's QStyle) matches the offscreen probe.
   - Recommendation: Path A's UAT step 1 (visually confirm "Living Coffee" YouTube logo letterboxes correctly in the tree) gates the entire phase. If UAT shows correct rendering, phase ships as test-only. If UAT shows actual cropping, escalate to Path B-1.

2. **Could the user be observing a different surface than the in-scope provider tree?**
   - What we know: D-01 is locked to provider-tree rows.
   - What's unclear: whether the user's mental model of "logo viewport" maps to the provider tree or to the now-playing 180×180 logo (which is excluded by D-01).
   - Recommendation: UAT step 1 explicitly photographs the provider tree row. If the row looks fine but the user is unhappy, the issue is elsewhere — file as a follow-up phase per D-09's escalation rules. Don't rescope this phase.

3. **Why does the user perceive AudioAddict square logos as cropped?**
   - What we know: AudioAddict art is 1000×1000 square; renders as 32×32 filling the cell. No cropping mathematically possible.
   - What's unclear: whether the user is responding to AudioAddict's *internal* logo design (logo glyph on a square background with internal padding), which can read as "the logo is small / there's empty space." That is not a code-level bug.
   - Recommendation: UAT step 2 confirms square cells render edge-to-edge. If the user objects to AA's internal padding, that's a different ticket (image-source quality, not rendering).

## Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| User UAT confirms my probe (no actual cropping) → phase ships test-only | High (~70%) | Phase trivializes; user may feel "you didn't fix anything" | Plan describes the UAT-driven decision tree clearly; user signs off on test-only outcome before merge |
| User UAT shows actual cropping → Path B-1 needed | Moderate (~25%) | Need to ship a real code change; small diff, low risk | Path B-1 is well-scoped (~10 line diff, single file). Cache contract preserved (D-11). |
| Path B-1 fails to fix actual cropping | Low (~5%) | Need delegate refactor (Path B-2 / D-09 escalation) | Path B-2 is the documented fallback. Plan should not commit to it upfront — only if B-1 fails. |
| `_write_logo` extension breaks an existing test | Very low | Wave 1 fails to merge | Default kwarg values preserve all 7 existing call signatures; verified by inspection |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The user's running app is on Linux Qt 6.11.0 like the probe environment | §1, §3 | Probe results may not apply to a Windows or older-Qt build. Phase 54 has no Windows attribution in CONTEXT.md, but this should be confirmed. **MEDIUM RISK — should be confirmed at plan-discuss time.** |
| A2 | The user's mental model of "logo viewport" maps to the provider-tree row icons (per D-01) | §1, §5 | If the user is mis-locating the bug, scope discussion needs to widen. D-01 is locked, so this is on the user. |
| A3 | The synthetic 50×100 / 100×50 dimensions are sufficient for the regression test | §4 | Larger or smaller dimensions would also work but D-10 explicitly says "e.g. 50×100" so the canonical form should match. **LOW RISK — researcher's discretion per CONTEXT.md.** |

**Note:** A1 is the most consequential assumption. The plan should call it out explicitly in plan-checker review and re-confirm during UAT step 0 ("which OS are you running this on?"). If the user is on Windows and reports cropping, that is a stronger signal Path B-1 is actually needed and the platform-style hypothesis is right.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | runtime + tests | ✓ | 3.x (project) | — |
| pytest | test runner | ✓ | 9.x [pyproject.toml] | — |
| pytest-qt | qtbot fixture | ✓ | 4.x [pyproject.toml] | — |
| PySide6 | Qt bindings | ✓ | 6.11.0 [VERIFIED] | — |
| Pillow (PIL) | Stations DB audit (research-only) | ✓ | n/a (used only during research) | Not required for test or production |
| SQLite3 | research-only DB inspection | ✓ | stdlib | — |

All test, build, and runtime dependencies are present. Pillow is only used by the research script that audited the DB; it is not a runtime dependency for the phase.

## Validation Architecture

(Section heading provided so VALIDATION.md generation can find it. See §4 above for the full content. Summary below for clarity.)

**Test framework:** pytest 9 + pytest-qt 4. Runs out of `pyproject.toml` `[tool.pytest.ini_options]`.

**Phase tests to add:**

- `tests/test_art_paths.py::test_load_station_icon_preserves_portrait_aspect` — synthetic 50×100 → asserts `icon.pixmap(QSize(32, 32))` is 16×32 (D-10).
- `tests/test_art_paths.py::test_load_station_icon_preserves_landscape_aspect` — synthetic 100×50 → asserts `icon.pixmap(QSize(32, 32))` is 32×16 (parallel coverage for SC #2).

**Phase tests already covering criteria:**

- `tests/test_art_paths.py::test_default_size_is_32px` (existing, line 120) covers SC #1 baseline ("max dimension ≤ 32 for a 128×128 source").
- `tests/test_art_paths.py::test_cache_hit_on_second_call` (existing, line 144) ensures D-11's no-key-bump constraint stays observable.

**Helper extension:**

- `tests/test_art_paths.py::_write_logo` (line 38) extended with optional `width`/`height` kwargs — keeps all 7 existing call signatures stable.

**Sampling:**

- Per task commit: `pytest tests/test_art_paths.py -x`
- Per wave merge: `pytest -x`
- Phase gate: full suite green + UAT screenshot pair (landscape from DB + synthetic portrait fixture).

**Wave 0 readiness:** existing `_isolate_pixmap_cache` autouse + `tmp_data_dir` + `_make_station` + `_write_logo` infrastructure is sufficient. No new fixtures, no conftest edits, no framework install. Wave 0 is effectively a no-op for this phase.

**Acceptance grep gates:**

```bash
grep -q "def test_load_station_icon_preserves_portrait_aspect" tests/test_art_paths.py
grep -q "def test_load_station_icon_preserves_landscape_aspect" tests/test_art_paths.py
```

## Security Domain

> Per `.planning/config.json`, `security_enforcement` is not explicitly set to `false`; this section is included for completeness. Phase 54 makes minimal changes (test-only in Path A, ~10 lines of pure-Qt rendering in Path B-1) so the threat surface is small.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase touches only the icon loader; no auth surface |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a |
| V5 Input Validation | tangentially | The loader receives `station.station_art_path` from the DB, which is populated by validated import flows (`assets.copy_asset_for_station`, `EditStationDialog._on_choose_logo`). No new validation surface. |
| V6 Cryptography | no | n/a |

### Known Threat Patterns for PySide6 Qt rendering

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `station_art_path` | Tampering | `abs_art_path` joins under `paths.data_dir()`. Upstream `assets.copy_asset_for_station` controls the write surface; the loader is read-only. |
| Decompression-bomb image (e.g. malicious PNG with insane dimensions) | DoS | `QPixmap()` will return null on most malformed inputs and trigger the FALLBACK_ICON branch. A hostile-but-valid PNG sized 1B×1B pixels would cause memory exhaustion at scale time, but the asset-import flow is user-controlled — not network-fetched. Existing risk; unchanged. |
| Pixmap cache poisoning | Tampering | `QPixmapCache` is process-scoped and keyed by absolute path. Two stations with the same `station_art_path` correctly share a cache entry. No cross-process attack surface. |

**Verdict:** No new ASVS-relevant surface. Phase 54 changes are below the threat-modeling threshold.

## Metadata

**Confidence breakdown:**

- Diagnosis (existing pipeline already correct): **HIGH** — verified by hands-on probe with the real model + real delegate + real iconSize hint, on the project's pinned PySide6 6.11.0.
- Path A test design: **HIGH** — synthetic pixmap dimensions are mathematically deterministic; existing test infrastructure is well-understood.
- Path B-1 fix shape (if escalation needed): **MEDIUM** — the patch is small and follows established `now_playing_panel.py` patterns, but has not been validated against an actual cropping repro because none exists locally.
- Path B-2 rejection: **HIGH** — `tree.setItemDelegate` (not `setItemDelegateForColumn`) is already in use, making a second column delegate architecturally awkward.
- Repro station selection: **HIGH** — verified file existence + image dimensions in the live DB.

**Research date:** 2026-04-29
**Valid until:** 2026-05-29 (30 days; PySide6 / Qt are stable, but the user's local environment can drift)
