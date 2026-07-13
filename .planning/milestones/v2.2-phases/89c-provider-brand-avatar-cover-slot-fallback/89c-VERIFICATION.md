---
phase: 89c-provider-brand-avatar-cover-slot-fallback
verified: 2026-06-17T00:00:00Z
status: passed
score: 11/11 must-haves verified
overrides_applied: 0
human_uat_resolution: "All 4 human-verification items confirmed PASS via 89C-HUMAN-UAT.md (live render across all providers, picker, Pitfall-7 guard, tier-replay). One additional minor gap surfaced during UAT (dialog avatar preview empty on reopen) was diagnosed and fixed by gap-closure plan 89c-03 (_populate now calls _refresh_avatar_preview; drift-guard test_populate_refreshes_avatar_preview). Two cosmetic notes (status-label truncation at small window sizes) logged, not blocking."
human_verification:
  - test: "Play a SomaFM or AudioAddict station in the running app and wait for a track whose art resolution exhausts (cover slot shows placeholder or logo)"
    expected: "After cover resolution exhausts, cover slot shows the provider brand avatar (circular crop) rather than duplicating the station logo shown in the left logo slot — but only if a brand PNG has been supplied by the user. Without a PNG, the cover slot shows the station logo (current behavior, D-04 missing-asset path)."
    why_human: "Requires a real GStreamer playback session + ICY metadata triggering _on_cover_art_ready with an empty path. Cannot simulate Qt signal dispatch or QPixmap render in a headless spot-check."
  - test: "Open EditStationDialog for any station that has a provider_id set and click 'Choose brand image…'. Pick a PNG file."
    expected: "The avatar preview in the dialog updates to the picked image, the providers.avatar_path DB column is updated, and on the next cover-miss the cover slot renders the user-supplied image (circular crop) instead of the bundled brand mark."
    why_human: "Requires Qt display context to exercise QFileDialog.getOpenFileName + UI preview refresh. Cannot automate the file-picker dialog in CI."
  - test: "Open EditStationDialog for a NEW station (never saved) and click 'Choose brand image…'"
    expected: "Status label shows 'Save station first to set a brand image'. No file is written. No DB UPDATE runs."
    why_human: "Requires Qt display context for the dialog interaction (Pitfall-7 guard test)."
  - test: "While a SomaFM brand avatar is showing in the cover slot, resize the window so a compact/full tier-change triggers _apply_art_tier"
    expected: "Brand avatar re-renders at the new tier size with correct circular crop. No station logo flash or cover-art re-load occurs."
    why_human: "Requires live Qt window resize event to trigger _apply_art_tier — cannot drive Qt's resizeEvent from a headless test."
---

# Phase 89c: Provider Brand Avatar Cover-Slot Fallback — Verification Report

**Phase Goal:** When per-track cover-art resolution is exhausted for an ICY-metadata provider whose track art frequently misses (SomaFM, AudioAddict), the now-playing cover slot shows a distinct provider brand avatar (circular crop) instead of duplicating the station logo already shown in the left logo slot. Trigger is cover-resolution-exhausted — the `if not path:` fallback branch in now_playing_panel._on_cover_art_ready (NOT icy_disabled). GBS.FM excluded by intent; providers without a registered avatar keep current behavior; a source-grep drift-guard pins the lookup to the resolution-exhausted branch after iTunes/MB-CAA.
**Verified:** 2026-06-17
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | ART-AVATAR-11/D-01: brand_avatars.lookup() recognizes the 7 exact provider_name strings and returns None for GBS.FM | VERIFIED | `brand_avatars.py` `_REGISTRY` has exactly the 7 keys. `grep -c 'GBS' brand_avatars.py` = 0. Runtime spot-check: `ba.lookup('GBS.FM')` = None. |
| 2 | ART-AVATAR-11/D-04: registered provider whose PNG file is absent returns None (graceful missing-asset, no crash) | VERIFIED | `lookup()` has `os.path.isfile(abs_str)` guard before returning. Runtime spot-check: `ba.lookup('SomaFM')` = None (no PNG on disk yet). `test_lookup_missing_file_returns_none` PASSED. |
| 3 | ART-AVATAR-12/D-07: brand-avatar lookup fires ONLY from `_on_cover_art_ready` `if not path:` branch, never from fetch_cover_art dispatch nor bind_station icy_disabled path | VERIFIED | now_playing_panel.py L2188: `self._resolve_brand_avatar_fallback()` inside `if not path:` block. `cover_art.py` has zero `brand_avatars` references (confirmed by grep). `test_brand_lookup_only_in_cover_exhausted_branch` PASSED (asserts _resolve_brand_avatar_fallback NOT in bind_station body, NOT in cover_art.py). |
| 4 | ART-AVATAR-12/D-08: cover-resolution-exhausted resolves user-override (provider_avatar_path) -> bundled registry -> _show_station_logo_in_cover_slot, in that order | VERIFIED | `_resolve_brand_avatar_fallback` L2256-2273: step 1 checks `provider_avatar_path` + `isfile` guard → `_set_avatar_pixmap_from_path`; step 2 calls `brand_avatars.lookup(provider_name)` → `_set_brand_avatar_pixmap`; step 3 calls `_show_station_logo_in_cover_slot`. |
| 5 | ART-AVATAR-12/D-10: real cover art still wins — _set_cover_pixmap path unchanged; brand avatar is transient per cover-resolution | VERIFIED | `_on_cover_art_ready` L2189-2190: real path calls `_set_cover_pixmap(path)` unchanged. Brand path is set only in `_resolve_brand_avatar_fallback`. `_apply_art_tier` branch order: `_last_cover_path` first (L2129-2130). |
| 6 | D-11: _last_brand_avatar tier-replay var participates in _apply_art_tier (4th branch between _last_avatar_path and the logo else) and is reset in bind_station | VERIFIED | L2133-2134: `elif self._last_brand_avatar is not None: self._set_brand_avatar_pixmap(self._last_brand_avatar)` between `_last_avatar_path` branch and `else`. L938: reset in bind_station. `test_apply_art_tier_has_brand_avatar_branch` and `test_bind_station_resets_brand_avatar` both PASSED. |
| 7 | ART-AVATAR-12/D-04 (frozen build): brand-avatars dir is bundled via PyInstaller datas so importlib.resources resolves it in frozen builds | VERIFIED | `packaging/windows/MusicStreamer.spec` L124: `("../../musicstreamer/ui_qt/brand-avatars", "musicstreamer/ui_qt/brand-avatars")` with full namespace destination path (Pitfall 9 compliant). |
| 8 | D-02: registry ships per-network granularity — 7 distinct keys (SomaFM + DI.fm, RadioTunes, JazzRadio, RockRadio, ClassicalRadio, ZenRadio) | VERIFIED | `_REGISTRY` in brand_avatars.py has all 7 distinct keys. Spot-check: 7/7 keys present, `'GBS.FM' in ba._REGISTRY` = False. |
| 9 | D-06: _set_brand_avatar_pixmap reuses _make_circular_pixmap for antialiased, borderless circular render | VERIFIED | L2292-2294: `circ = _make_circular_pixmap(pix, n)` + `self.cover_label.setPixmap(circ)`. `_make_circular_pixmap` is the existing module-level function at L219. |
| 10 | D-12: source-grep drift-guard (test_brand_lookup_only_in_cover_exhausted_branch) pins brand lookup to resolution-exhausted branch only | VERIFIED | Test exists in `tests/test_cover_art_avatar.py` L164-203. PASSED in live test run (11/11 in test_cover_art_avatar.py GREEN). |
| 11 | D-09: EditStationDialog exposes a 'Choose brand image...' picker that writes the chosen image via write_provider_avatar + update_provider_avatar_path; Pitfall-7 guard no-ops on new stations; no _AvatarFetchWorker involvement | VERIFIED | `edit_station_dialog.py` L1402-1441: `_on_choose_brand_image` exists; contains `write_provider_avatar`, `update_provider_avatar_path`, `provider_id is None` guard, `try:/except` block; no `_AvatarFetchWorker` reference. `test_choose_brand_image_uses_provider_keyed_persist` + `test_choose_brand_image_never_raises` both PASSED. |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/brand_avatars.py` | Provider brand-avatar registry; lookup(provider_name) -> Optional[str] | VERIFIED | 52 lines. Contains `def lookup`, `_REGISTRY` with 7 keys, `os.path.isfile` guard. |
| `musicstreamer/ui_qt/brand-avatars/.gitkeep` | Git-tracked loose-PNG asset dir (D-05) | VERIFIED | `git ls-files` confirms tracked. No PNGs by design (D-04). |
| `tests/test_brand_avatars.py` | Registry unit tests + D-11 and D-09/D-09a source-grep drift-guards | VERIFIED | 10 tests; all PASSED. Includes WR-01 and WR-02 review-fix guards added after 89C-REVIEW.md. |
| `musicstreamer/ui_qt/now_playing_panel.py` | `_resolve_brand_avatar_fallback`, `_set_brand_avatar_pixmap`, `_last_brand_avatar`, `_apply_art_tier` 4th branch, bind_station reset | VERIFIED | All 5 items confirmed at specific line numbers. WR-01 fix (3-tracker reset) present at L2253-2255. |
| `packaging/windows/MusicStreamer.spec` | brand-avatars datas entry for frozen builds | VERIFIED | L124 contains `("../../musicstreamer/ui_qt/brand-avatars", "musicstreamer/ui_qt/brand-avatars")`. |
| `musicstreamer/ui_qt/edit_station_dialog.py` | `_on_choose_brand_image` handler + `_choose_brand_image_btn` in avatar row | VERIFIED | L519: button added to avatar_row. L1402: handler defined. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `now_playing_panel._on_cover_art_ready (if not path:)` | `_resolve_brand_avatar_fallback` | Direct call at L2188 replacing `_show_station_logo_in_cover_slot` | WIRED | L2187-2188 confirmed: `if not path:` → `self._resolve_brand_avatar_fallback()` |
| `now_playing_panel._resolve_brand_avatar_fallback` | `musicstreamer.brand_avatars.lookup` | Registry lookup on `station.provider_name` (D-08 step 2) at L2267-2268 | WIRED | `from musicstreamer import brand_avatars; abs_path = brand_avatars.lookup(self._station.provider_name or "")` |
| `brand_avatars.lookup` | `musicstreamer/ui_qt/brand-avatars/<key>.png` | `importlib.resources.files` + `os.path.isfile` guard | WIRED | L46-50: `_res.files("musicstreamer.ui_qt") / "brand-avatars" / filename` + `os.path.isfile(abs_str)` |
| `edit_station_dialog._on_choose_brand_image` | `musicstreamer.assets.write_provider_avatar` | Synchronous file read → provider-keyed atomic write | WIRED | L1431-1432 confirmed. |
| `edit_station_dialog._on_choose_brand_image` | `repo.update_provider_avatar_path` | Non-silent-reset single-column persist | WIRED | L1436 confirmed. |

### Code-Review Fix Verification (89C-REVIEW.md WR-01 / WR-02)

| Fix | Required | Status | Evidence |
|-----|----------|--------|---------|
| WR-01: `_resolve_brand_avatar_fallback` resets `_last_cover_path`, `_last_avatar_path`, `_last_brand_avatar` up front | Yes | VERIFIED | L2253-2255 in now_playing_panel.py. `test_resolve_brand_avatar_fallback_clears_stale_trackers` PASSED. |
| WR-02: `_on_choose_brand_image` wraps file-read/write/persist in try/except | Yes | VERIFIED | L1428-1438 in edit_station_dialog.py. `test_choose_brand_image_never_raises` PASSED. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `ba.lookup('GBS.FM')` returns None (D-01) | `.venv/bin/python -c "import musicstreamer.brand_avatars as ba; print(ba.lookup('GBS.FM'))"` | None | PASS |
| `ba.lookup('SomaFM')` returns None (no PNG on disk — D-04 missing-asset path) | `.venv/bin/python -c "import musicstreamer.brand_avatars as ba; print(ba.lookup('SomaFM'))"` | None | PASS |
| All 7 keys present in `_REGISTRY`, GBS.FM absent | `.venv/bin/python -c "..."` | 7 keys, GBS.FM not in dict | PASS |
| `tests/test_brand_avatars.py` — all registry + drift-guard tests | `.venv/bin/python -m pytest tests/test_brand_avatars.py -x -v` | 10/10 PASSED | PASS |
| `tests/test_cover_art_avatar.py` — all tests including new drift-guard | `.venv/bin/python -m pytest tests/test_cover_art_avatar.py -x -v` | 11/11 PASSED | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| ART-AVATAR-11 | 89c-01-PLAN.md, 89c-02-PLAN.md | 7-key brand-avatar registry; bundled assets; GBS.FM excluded | SATISFIED | `brand_avatars.py` + `brand-avatars/` dir; all 7 keys verified; GBS.FM absent. |
| ART-AVATAR-12 | 89c-01-PLAN.md | Resolution-exhausted `if not path:` branch renders brand avatar (circular crop); unregistered providers reach `_show_station_logo_in_cover_slot` | SATISFIED | `_resolve_brand_avatar_fallback` wired at the `if not path:` branch only; D-08 three-tier resolution; `_set_brand_avatar_pixmap` uses `_make_circular_pixmap`. |

Both requirement IDs declared in PLAN frontmatter are marked Complete in REQUIREMENTS.md traceability table. No orphaned requirements for this phase.

### Anti-Patterns Found

Scan of all phase-modified files (`brand_avatars.py`, `now_playing_panel.py`, `edit_station_dialog.py`, `test_brand_avatars.py`, `test_cover_art_avatar.py`, `MusicStreamer.spec`) for `TBD`, `FIXME`, `XXX`: **none found**.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | — |

### Human Verification Required

#### 1. Brand avatar renders on cover-resolution-exhausted (live playback)

**Test:** Play a SomaFM or AudioAddict station and wait for a track whose cover-art resolution exhausts (all three tiers — iTunes/MB-CAA — return nothing). A brand PNG must have been supplied by the user first (place e.g. `SomaFM.png` in `musicstreamer/ui_qt/brand-avatars/`).
**Expected:** Cover slot shows the provider brand avatar (circular crop) instead of duplicating the station logo in the left logo slot.
**Why human:** Requires a real GStreamer playback session + ICY metadata triggering `_on_cover_art_ready` with `path=None`. Cannot simulate Qt signal dispatch or QPixmap render in a headless spot-check.

#### 2. "Choose brand image..." picker saves and overrides cover slot

**Test:** Open EditStationDialog for any station with a `provider_id` set. Click "Choose brand image...". Pick a PNG file. Dismiss the dialog. Trigger a cover-miss for that station.
**Expected:** Avatar preview updates immediately in the dialog. On the next cover-miss, the cover slot shows the user-supplied image (circular crop, not the bundled brand mark, not the station logo).
**Why human:** Requires Qt display context to exercise `QFileDialog.getOpenFileName` + UI preview refresh.

#### 3. New-station guard ("Save station first")

**Test:** Open EditStationDialog for a brand-new station that has never been saved (provider_id is None). Click "Choose brand image...".
**Expected:** Status label shows "Save station first to set a brand image". No file written to disk. No DB UPDATE runs.
**Why human:** Requires Qt display context for the dialog interaction to confirm the Pitfall-7 guard surfaces correctly to the user.

#### 4. Brand avatar tier-replay on window resize

**Test:** With a SomaFM brand avatar showing in the cover slot (user has supplied PNG), resize the now-playing window or toggle compact mode (Ctrl+B) to trigger a tier change.
**Expected:** Brand avatar re-renders at the new tier size with correct circular crop. No flash back to station logo.
**Why human:** Requires live Qt resizeEvent to drive `_apply_art_tier`. Cannot automate Qt resize events in a headless test.

### Gaps Summary

No blocking gaps. All 11 must-haves are verified in the codebase. Both requirement IDs (ART-AVATAR-11, ART-AVATAR-12) are satisfied. No TBD/FIXME/XXX debt markers found. Code-review fixes WR-01 and WR-02 are confirmed present with their own drift-guard tests.

Status is `human_needed` because the end-to-end render path (live GStreamer playback → cover-resolution-exhausted → brand avatar displayed in Qt cover slot) requires a running display context and real ICY metadata stream. The automated tests cover every structural contract and the missing-asset fallback path; the live render behavior requires human UAT.

---

_Verified: 2026-06-17_
_Verifier: Claude (gsd-verifier)_
