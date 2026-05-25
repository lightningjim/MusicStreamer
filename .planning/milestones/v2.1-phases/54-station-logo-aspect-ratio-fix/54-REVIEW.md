---
phase: 54-station-logo-aspect-ratio-fix
depth: standard
status: issues_found
files_reviewed: 4
diff_base: 3952864^
findings:
  critical: 1
  warning: 7
  info: 5
  total: 13
files:
  - musicstreamer/ui_qt/_art_paths.py
  - musicstreamer/ui_qt/station_star_delegate.py
  - tests/test_art_paths.py
  - tests/test_station_star_delegate.py
generated: 2026-04-30
---

# Code Review — Phase 54 Station Logo Aspect Ratio Fix

**Depth:** standard
**Files reviewed:** 4
**Status:** issues_found

## Summary

The Phase 54 implementation correctly addresses BUG-05 with a defensible two-part fix: the canvas-paint patch in `_art_paths.py::load_station_icon` produces a deterministic 32×32 transparent square pixmap, and `StationStarDelegate` overrides force a square decoration rect on station rows while flooring uniform row height for all rows. The invariants spelled out in the phase brief (D-01, D-04, D-05, D-07, D-09, D-11) are honored.

However, the review surfaced one **CRITICAL** (incorrect Plan-04 paint contract on HiDPI displays — the icon scaling is broken at devicePixelRatio > 1), several **WARNINGs** (a redundant `initStyleOption` re-call that overwrites Qt's own style-derived state, a stale docstring, a brittle test path, an O(n²) per-pixel scan in tests, an undocumented coupling between provider sizeHint and provider rendering, a tautological provider-row test, and a leaked QObject in test setup), and a few **INFO** items.

Findings counts: **1 critical, 7 warning, 5 info, 13 total**.

---

## CRITICAL Findings

### CR-01: HiDPI device-pixel-ratio dropped on canvas — logos render blurry on Retina/HiDPI

**File:** `musicstreamer/ui_qt/_art_paths.py:86-92`
**Severity:** critical

**Issue:** The aspect-correct canvas patch creates the 32×32 destination pixmap with `QPixmap(size, size)` and never sets `setDevicePixelRatio()`. On HiDPI displays (Wayland fractional scaling, macOS Retina, Windows 1.5x/2x), Qt source-pixmaps loaded via `QPixmap(load_path)` and FALLBACK_ICON (an SVG resource) carry the device pixel ratio of the screen they were last rasterized for, but the new 32×32 canvas does not. When QIcon paints this pixmap into a higher-DPR row, Qt nearest-neighbor up-scales it, producing blurry station logos.

The pre-Phase-54 code returned `pix.scaled(...)` directly, which preserved DPR via `QPixmap.scaled`. The new code drops it.

**Fix (smallest diff):**
```python
pix = QPixmap(size, size)
pix.setDevicePixelRatio(scaled.devicePixelRatio())  # carry DPR through
pix.fill(Qt.transparent)
```

Better long-term: allocate at the device size — `QPixmap(int(size * dpr), int(size * dpr))`, set DPR, then paint at logical coordinates.

**Verification suggestion:** Reproduce on a HiDPI test rig before shipping. If `devicePixelRatio == 1.0` on the project's target Linux X11 deployment, this could be downgraded to WARNING and deferred to a future HiDPI phase — but the one-line fix is worth applying defensively now. Confirm whether `pytest tests/test_art_paths.py` runs in a 1.0-DPR offscreen Qt platform plugin (likely yes — that's why the existing tests don't catch this).

---

## WARNING Findings

### WR-01: Redundant `initStyleOption` re-call in delegate paint may overwrite Qt-supplied state

**File:** `musicstreamer/ui_qt/station_star_delegate.py:56`
**Severity:** warning

**Issue:** Inside `paint()` for station rows the code calls `self.initStyleOption(option, index)` even though Qt has already populated `option` before invoking `paint()`. `QStyledItemDelegate` itself calls `initStyleOption` inside `paint`, so calling it again from a subclass before delegating to `super().paint(...)` causes Qt to do the work twice and overwrites any state the calling view may have placed on `option` (selected/hover state, focus rect, `option.widget` style sheets bound to it). With `super().paint(...)` immediately after, `super().paint` will call `initStyleOption` a third time. In practice this works on the styles tested, but it's a fragile contract: any state mutation the calling QTreeView applies to `option` before calling `paint` (and that `initStyleOption` does not re-derive from the model) will be lost.

The safe pattern is to skip the explicit `initStyleOption` call and just mutate `option` after Qt has populated it:

**Fix:**
```python
station = index.data(Qt.UserRole)
if isinstance(station, Station):
    # Qt has already called initStyleOption on `option` before paint() was
    # invoked. Mutate the option in place; do NOT re-init or we will
    # overwrite view-supplied state.
    option.decorationSize = QSize(STATION_ICON_SIZE, STATION_ICON_SIZE)
    option.decorationAlignment = Qt.AlignVCenter | Qt.AlignLeft
super().paint(painter, option, index)
```

If a defensive re-init is genuinely required for Qt 6.11 (e.g., the platform style mutates `decorationSize` between the public `paint` entry and the internal `CE_ItemViewItem` read), document that explicitly with a citation. The current inline comment ("MUST happen BEFORE super().paint() so Qt's CE_ItemViewItem path reads the overridden values") only justifies the *ordering*, not the re-init.

### WR-02: Provider-row floor at 32 px couples unrelated concerns to STATION_ICON_SIZE

**File:** `musicstreamer/ui_qt/station_star_delegate.py:74-87`
**Severity:** warning

**Issue:** The fix correctly observes that `tree.setUniformRowHeights(True)` probes the first row (a provider) so a station-only floor is bypassed, and floors **all** rows at 32 px. This is a deliberate behavior change to provider rows — they will now be taller than they previously were if Qt's natural sizeHint for the provider label was, say, 22 px. Provider-row width is preserved (no star reservation), so the D-01 width invariant holds. But provider-row *height* is now driven by station-icon size, coupling two unrelated concerns. If `STATION_ICON_SIZE` were ever increased (e.g., to 48 for a future HiDPI option), provider rows in the unrelated provider-tree header would also grow — silently.

**Fix:** Either (a) introduce `_PROVIDER_TREE_MIN_ROW_HEIGHT = 32` and floor providers at that, decoupled from `STATION_ICON_SIZE`, with a comment explaining the dependency on `setUniformRowHeights`; or (b) document at the top of `StationStarDelegate` that station-icon size is the source of truth for provider-row height in this delegate.

### WR-03: Stale docstring overstates cache-key dedup guarantee for relative paths

**File:** `musicstreamer/ui_qt/_art_paths.py:56-58`
**Severity:** warning

**Issue:** The docstring claims the cache key is `f"station-logo:{abs_path or FALLBACK_ICON}"` and that the "(D-03)" tag means "the same logo referenced as relative vs. absolute hits the same cache entry." That deduplication only works if a relative path resolves to the same absolute string the next time around. Relative paths are normalized via `os.path.join`, which does **not** call `os.path.realpath` or `os.path.normpath`. Two different string forms of the same logical path (e.g., `assets/1/logo.png` vs `./assets/1/logo.png`) would hit different cache keys.

**Fix:** Either add `os.path.normpath(...)` to `abs_art_path` to canonicalize, or weaken the docstring to "the same `station_art_path` string referenced as relative-then-absolute across calls hits the same cache entry."

Also: the actual code (lines 70-71) computes `load_path = abs_path or FALLBACK_ICON` and uses `f"station-logo:{load_path}"` — functionally identical to the docstring claim, but the variable name divergence (`abs_path` in docstring vs `load_path` in code) is a minor nit.

### WR-04: Brittle equality test on QImage — comparison defeats its own purpose post-Plan-03

**File:** `tests/test_art_paths.py:111-114, 142-146`
**Severity:** warning

**Issue:** `loaded_pix.toImage() != fallback_pix.scaled(...).toImage()` compares full QImage byte content of the loaded logo vs. the fallback. The intent is "verify we got a real logo, not the fallback."

With the canvas patch, `loaded_pix` is now a 32×32 pixmap with transparent margins around a 16×32 portrait. The `fallback_pix.scaled(32, 32, KeepAspectRatio, Smooth)` is **not** painted onto a transparent canvas — it's the raw scaled pixmap. So the comparison is between two pixmaps with different structure that happen to be the same logical size. This would always be `!=` regardless of which logo is shown, defeating the purpose of the assertion in the affected tests.

**Fix:** Replace with a more direct check — assert the loaded pixmap contains the fixture's red color at the expected location:
```python
img = loaded_pix.toImage()
center = img.pixelColor(img.width() // 2, img.height() // 2)
assert center.red() > 200 and center.green() < 50, (
    "expected red fixture logo at center, got fallback or wrong pixel"
)
```

### WR-05: O(n²) per-pixel scan in test helper without bounds check or null guard

**File:** `tests/test_art_paths.py:72-87`
**Severity:** warning

**Issue:** `_non_transparent_bbox` iterates every pixel via `pixelColor(x, y)`. Each call involves a Python-to-C++ roundtrip and format conversion. For the test's 32×32 pixmap that's 1024 calls — fine. But there is no upper bound: a future test passing a 256×256 pixmap becomes 65k roundtrips per test. Also: no guard against `pix.isNull()` — calling it on a null pixmap returns `(width, height, -1, -1)` which would silently pass downstream assertions on `region_w == max_x - min_x + 1` if both endpoints are -1 and width=0.

**Fix:** Add at the top of the helper:
```python
assert not pix.isNull(), "_non_transparent_bbox requires a non-null pixmap"
assert pix.width() <= 64 and pix.height() <= 64, (
    "_non_transparent_bbox is O(n^2); not for large pixmaps"
)
```

### WR-06: Test instantiates `StationStarDelegate.__bases__[0]()` — fragile and leaks QObject

**File:** `tests/test_station_star_delegate.py:216`
**Severity:** warning

**Issue:** `StationStarDelegate.__bases__[0]()` directly constructs a fresh `QStyledItemDelegate` to call `sizeHint` for comparison purposes. Two issues:

1. This QObject has no parent and is leaked for the test's lifetime. Pytest-qt does not GC it.
2. Using `__bases__[0]` is fragile — implicitly couples the test to the inheritance order of `StationStarDelegate`. If a future refactor inserts a mixin class as the first base, this test silently calls the wrong base class.

**Fix:**
```python
from PySide6.QtWidgets import QStyledItemDelegate
super_delegate = QStyledItemDelegate(parent=delegate)
super_hint = super_delegate.sizeHint(option, provider_idx)
```
Or call `QStyledItemDelegate.sizeHint(delegate, option, provider_idx)` directly (no instance allocation needed).

### WR-07: `test_paint_provider_row_does_not_force_decoration_size` is tautological

**File:** `tests/test_station_star_delegate.py:268, 281-284`
**Severity:** warning

**Issue:** The test snapshots `pre_paint_dec_size = QSize(option.decorationSize)` and asserts equality after paint, intending to detect a regression where the delegate forces 32×32 on provider rows. But: `super().paint(painter, option, index)` *also* calls `initStyleOption(option, index)` internally on `QStyledItemDelegate`. `initStyleOption` re-derives `decorationSize` from `Qt.SizeHintRole`/`Qt.DecorationRole` data — for a provider row with no decoration, that resets to default. So the post-paint equality holds because `initStyleOption` re-set it, **not** because the delegate didn't touch it. The test is tautological for any implementation that calls `super().paint(...)`.

**Fix:** Capture the value the delegate sets *before* calling super.paint (e.g., by stubbing `super().paint` to capture `option.decorationSize` at the moment of entry), or remove the test as redundant — `test_paint_forces_square_decoration_rect` already covers the station-row positive case, and the provider-row negative case is enforced structurally by the `if isinstance(station, Station)` guard in source.

---

## INFO Findings

### IN-01: Unused import `QStyle` in delegate

**File:** `musicstreamer/ui_qt/station_star_delegate.py:16`
**Severity:** info

`QStyle` is imported but never used. Pre-existing (not introduced by Phase 54), but visible during this review.

**Fix:**
```python
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
```

### IN-02: Magic numbers `_STAR_SIZE = 20` and `_STAR_MARGIN` not centralized

**File:** `musicstreamer/ui_qt/station_star_delegate.py:23-24`
**Severity:** info

`_STAR_SIZE` and `_STAR_MARGIN` are module-private constants while `STATION_ICON_SIZE` is centralized in `_theme.py`. For consistency, the star size should also live in `_theme.py` or be derived from `STATION_ICON_SIZE`.

### IN-03: `_isolate_pixmap_cache` and `tmp_data_dir` fixtures duplicated across two test files

**File:** `tests/test_art_paths.py:57-62`, `tests/test_station_star_delegate.py:33-37`
**Severity:** info

Identical `_isolate_pixmap_cache` autouse fixture and `tmp_data_dir` fixture are defined in both test modules. Promote to `tests/conftest.py` to reduce drift risk.

### IN-04: Comment cites "D-03" but the tag isn't defined in the phase brief

**File:** `musicstreamer/ui_qt/_art_paths.py:58`
**Severity:** info

Inline comment references decision tag "D-03". The phase brief lists D-01, D-04, D-05, D-07, D-09, D-11. A maintainer reading just this file has no way to resolve the tag. Either inline a one-line restatement of D-03 or replace the tag with the meaning ("absolute-path-keyed cache").

### IN-05: `_make_station` helper diverges across the two test files

**File:** `tests/test_art_paths.py:27-35`, `tests/test_station_star_delegate.py:60-69`
**Severity:** info

`test_art_paths.py::_make_station` sets `provider_name=None`; `test_station_star_delegate.py::_make_station` sets `provider_name="TestProvider"`. Each is internally consistent but the divergence increases cognitive load. Standardize on one default; promote helper to `tests/conftest.py` once consolidated.

---

## Next Steps

1. **CR-01 (BLOCKER):** Apply the one-line `setDevicePixelRatio` fix in `_art_paths.py` before considering Phase 54 fully closed. If HiDPI is out of scope for the current milestone, file as a follow-up phase and document the deferral in REQUIREMENTS.md.
2. **WR-01, WR-04, WR-07:** Highest-leverage warnings — small fixes that materially improve the durability of the Plan-04 contract and the integrity of the test suite.
3. **WR-02, WR-03, WR-05, WR-06:** Cleanup work; bundle into a single follow-up commit.
4. **INFO items:** Consider as part of routine cleanup or alongside the WR fixes.

Auto-fix candidates (suitable for `/gsd-code-review-fix 54`): WR-01, WR-04, WR-05, WR-06, WR-07, IN-01, IN-03, IN-05.
Manual review recommended: CR-01 (verify HiDPI behavior on target hardware), WR-02 (design call), WR-03 (docstring vs code change), IN-02 (theme centralization), IN-04 (decision-tag resolution).
