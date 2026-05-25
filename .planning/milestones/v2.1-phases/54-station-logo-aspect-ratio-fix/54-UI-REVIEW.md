# Phase 54 — UI Review

**Audited:** 2026-04-30
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md for this phase)
**Screenshots:** Not captured via automated tooling — UAT screenshots in phase directory used for visual evidence. No dev server detected on localhost:3000/5173/8080.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | No user-facing strings introduced; internal comments are precise and attributable |
| 2. Visuals | 3/4 | Portrait pillarbox now renders correctly; star icon area lacks tooltip; recently-played list has no delegate enforcement |
| 3. Color | 4/4 | Transparent pillarbox bars correct per D-04; no hardcoded color values introduced in production code |
| 4. Typography | 4/4 | No typography changes; existing provider-header font contract undisturbed |
| 5. Spacing | 3/4 | Row height correctly floored at 32px; `_PROVIDER_TREE_MIN_ROW_HEIGHT` is a magic constant decoupled from STATION_ICON_SIZE without lint guard |
| 6. Experience Design | 3/4 | Fallback, loading, and error paths are all handled; cache-key non-canonicalization (WR-03) is a latent misfire edge case; recently-played portrait cropping is unverified in-scope |

**Overall: 21/24**

---

## Top 3 Priority Fixes

1. **Recently-played list has no portrait-fix coverage** — A user whose most-recently-played station has a portrait logo will see a cropped icon in the Recently Played strip because `recent_view` is a plain `QListView` with no delegate override and `StationStarDelegate` is only wired to `self.tree`. `_populate_recent` calls `load_station_icon` (so the canvas is square) but the list-view will still constrain display to its own `iconSize` rect, which, on this Qt/platform, can exhibit the same landscape-shaped decoration rect bug that necessitated Plan 04. Concrete fix: install a lightweight `AspectIconDelegate` on `recent_view` that mirrors the `decorationSize`/`decorationAlignment` enforcement from `StationStarDelegate.paint`, or confirm via UAT that `QListView` on this platform honors the 32x32 canvas without coercion.

2. **Cache key not canonicalized — `./assets/1/logo.png` vs `assets/1/logo.png` can produce two cache entries for the same file** — `_art_paths.py:58-63` documents this explicitly (WR-03) but leaves it unresolved. If any call site passes a non-canonical relative form (e.g. starting with `./`), the canvas is re-rendered and re-cached under a second key, doubling memory for that station's icon. The fix is a one-liner: apply `os.path.normpath` to `abs_path` before constructing `key`, and add a test asserting that `./assets/1/logo.png` and `assets/1/logo.png` resolve to the same cache entry.

3. **Star icon area has no tooltip** — The 20x20 star in every station row is an interaction target (click to toggle favorite) but carries no `setToolTip` and no accessible description. Users unfamiliar with the convention will not know it is interactive. No `setToolTip` call appears in `StationStarDelegate` or its construction site in `station_list_panel.py:291`. Concrete fix: override `helpEvent` in `StationStarDelegate` to return a tooltip string ("Add to Favorites" / "Remove from Favorites") when the mouse is over `_star_rect(option.rect)`.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

No user-facing strings were introduced in this phase. The two modified production files (`_art_paths.py` and `station_star_delegate.py`) contain only internal comments and docstrings. All existing station names, provider names, and UI labels are unchanged.

Internal comment quality is high: every non-obvious decision is attributed to a context decision (D-04, D-05, D-09, D-11) or a code-review warning marker (WR-01 through WR-07), making the rationale traceable without opening the planning documents.

No generic labels, placeholder copy, or ambiguous error strings were found in the phase-modified files.

### Pillar 2: Visuals (3/4)

**What is correct:**

UAT screenshots confirm the core fix works on the deployment target (Linux X11 DPR=1.0):
- `uat-landscape-after-b2.png`: Cafe BGM / Living Coffee row renders a letterboxed landscape thumbnail with consistent 32px row heights across Drone Zone and SomaFM Groove Salad. The row heights are now uniform and visually aligned.
- `Screenshot From 2026-04-30 12-57-37.png`: ClassicalRadio / 20th Century row renders the 1000x1000 logo edge-to-edge in a 32x32 cell correctly.
- `uat-portrait-after.png` (pre-B2, showing the broken state): confirms the Plan 03 failure was visible. The B2 summary records user-approved UAT.

Plan 04 summary confirms user sign-off with "approved" after the B2 fix, portrait renders 16w x 32h pillarboxed as designed.

**WARNING findings:**

- **Star icon area — no tooltip or accessible hint** (`station_star_delegate.py:74-79`): the star is drawn via `icon.paint(painter, rect, ...)` with no companion `QToolTip` or `helpEvent` override. Users not already trained on the star convention get no affordance hint. On mouse-hover, the cursor does not change (no `setCursor` call), making the target invisible to new users.

- **Recently-played QListView — no delegate enforcement** (`station_list_panel.py:171-180`, `station_list_panel.py:374`): `recent_view` uses the Qt default item delegate with `setIconSize(QSize(32, 32))`. While `load_station_icon` produces a 32x32 transparent canvas (Plan 03 fix), the platform's default `QListView` item delegate may exhibit the same landscape-shaped decoration rect behavior on Linux X11/Wayland that Plan 04 corrects for `QTreeView`. The UAT evidence (`uat-evidence.png`) shows "Recently Played" had an oversized red bar pre-Plan 03, and Plan 02 noted "Renders correctly in Recently Played" for the landscape repro, but post-B2 portrait behavior in the recently-played strip was not explicitly re-verified.

- **`uat-portrait-after-b2.png` was never captured** (54-04-SUMMARY.md lines 66-69): the UAT sign-off is verbal ("approved" resume signal) with no screenshot. The summary notes this explicitly and says "recommend capturing the screenshot at convenience, but not blocking phase closure on it." For a bugfix phase where the primary deliverable is correct visual rendering, the absence of a definitive post-fix portrait screenshot is a gap in the visual record. This is a process finding, not a code bug.

### Pillar 3: Color (4/4)

No hardcoded color values were introduced in production files. The canvas fill uses `Qt.transparent` (a semantic constant, not a hex literal), fully honoring D-04.

The `Qt.red` constant is used only in test fixtures (`_write_logo` in `test_art_paths.py` and `_write_portrait_logo` in `test_station_star_delegate.py`). This is correct — test fixtures should produce high-contrast, easily verifiable colors.

The star icon (`starred-symbolic`, `non-starred-symbolic`) uses `QIcon.fromTheme` with an SVG fallback, inheriting the user's system icon theme colors rather than hardcoding any values. This is correct behavior for a system-themed application.

No accent overuse issues found in the modified files.

### Pillar 4: Typography (4/4)

No typography changes were introduced in this phase. The provider group header font (`13pt Bold`, set in `station_tree_model.py:149-152`) is untouched. No new `QFont` usage, no new size classes, no weight changes.

The `_PROVIDER_TREE_MIN_ROW_HEIGHT = 32` constant governs row height, not typography, and is distinct from any font-size concern.

### Pillar 5: Spacing (3/4)

**What is correct:**

Row height is now reliably floored at 32px for both station and provider rows (`station_star_delegate.py:95-99`). The `setUniformRowHeights(True)` edge case (first-row probe is a provider) is specifically handled by the separate `_PROVIDER_TREE_MIN_ROW_HEIGHT` constant. The star margin (`_STAR_MARGIN = 4`) and size (`_STAR_SIZE = 20`) constants are named and consistent.

**WARNING findings:**

- **`_PROVIDER_TREE_MIN_ROW_HEIGHT = 32` is a magic constant without a lint-enforced relationship to `STATION_ICON_SIZE`** (`station_star_delegate.py:25-32`): the code comment explains the decoupling rationale (a future STATION_ICON_SIZE increase should not silently inflate provider rows), but there is no assertion or test that `_PROVIDER_TREE_MIN_ROW_HEIGHT >= STATION_ICON_SIZE`. If STATION_ICON_SIZE is ever raised above 32 (e.g. for HiDPI), `_PROVIDER_TREE_MIN_ROW_HEIGHT` can become the binding constraint without any warning. Concrete fix: add `assert _PROVIDER_TREE_MIN_ROW_HEIGHT >= STATION_ICON_SIZE` at module load time, or unify with a comment explicitly listing the expected value.

- **`x = (size - scaled.width()) // 2` centering arithmetic uses integer truncation** (`_art_paths.py:100-101`): for odd-width scaled pixmaps the off-by-half-pixel is cosmetically negligible at 32px but is not visually tested. This is informational — the rounding direction is conventional (round-down) and the 50x100 and 100x50 test fixtures happen to produce even-dimension scaled results (16x32 and 32x16). A future source dimension that yields an odd scaled.width() would produce a 0.5px off-center logo with no test to catch it.

### Pillar 6: Experience Design (3/4)

**What is correct:**

- Fallback path: `src.isNull()` check retained; FALLBACK_ICON painted onto the transparent canvas like any other source (`_art_paths.py:81-82`). Missing-file and None-path cases are covered by existing tests.
- Cache hit: the `QPixmapCache.find` guard prevents redundant re-renders. `test_cache_hit_on_second_call` remains green.
- `QPainter.end()` is explicitly called before `QPixmapCache.insert` (`_art_paths.py:103`), preventing the resource-leak risk documented as T-54-07.
- `pix.setDevicePixelRatio(scaled.devicePixelRatio())` carries source DPR onto the canvas (`_art_paths.py:97`), a CR-01 fix added during code review — correct for future HiDPI compatibility even though the deployment target is DPR=1.0.

**WARNING findings:**

- **Cache key non-canonicalization (WR-03)** (`_art_paths.py:56-63`): explicitly documented but unresolved. If any call site reaches `load_station_icon` with a non-canonical relative path (e.g. beginning with `./`), the cache miss fires, an extra 32x32 canvas is allocated, and a second key is inserted. The current call sites (`station_tree_model.py:146`, `station_list_panel.py:374`) both pass the raw `station.station_art_path` through `abs_art_path`, which uses `os.path.join` without normalization. Whether any station in the live DB has a `./`-prefixed relative path is unknown (it would depend on how `EditStationDialog` stores the path). The risk is latent, not confirmed broken, but it is documented and left open.

- **Recently-played portrait rendering unverified post-B2**: see Pillar 2 visual finding above. From an experience-design perspective: if a portrait logo is cropped in the recently-played strip, the user perceives a partially-working fix even though the tree is correct.

- **Star target hit zone is small and undiscoverable**: the 20x20 star occupies the rightmost 24px of a row. There is no hover cursor change (`setCursor` is not called in `editorEvent` on hover), no tooltip, and no keyboard navigation support for the toggle. For users navigating by keyboard, the star is completely inaccessible. This is a pre-existing gap not introduced in Phase 54, but the delegate rewrite in Plan 04 was an appropriate moment to address it.

---

## Files Audited

Production files:
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/_art_paths.py`
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/station_star_delegate.py`
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/station_list_panel.py` (call-site review)
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/station_tree_model.py` (call-site review)
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui_qt/_theme.py` (token values)

Test files:
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/tests/test_art_paths.py`
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/tests/test_station_star_delegate.py`

Phase planning documents:
- `54-CONTEXT.md`, `54-01-PLAN.md`, `54-01-SUMMARY.md`
- `54-02-PLAN.md`, `54-02-SUMMARY.md`
- `54-03-PLAN.md`, `54-03-SUMMARY.md`
- `54-04-PLAN.md`, `54-04-SUMMARY.md`

UAT screenshots examined:
- `uat-evidence.png` (Plan 02 pre-patch)
- `uat-portrait-after.png` (Plan 03 post-B1, still broken)
- `uat-landscape-after.png` (Plan 03 landscape — correct)
- `uat-landscape-after-b2.png` (Plan 04 post-B2 — confirmed correct)
- `Screenshot From 2026-04-30 12-57-37.png` (ClassicalRadio square baseline)
