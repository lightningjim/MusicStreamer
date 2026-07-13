---
phase: 94-optimize-sidebar-logo-loading-with-pre-scaled-thumbnails-for
verified: 2026-06-15T00:00:00Z
status: passed
human_verification_result: passed 2026-06-15 — Test 1 (first-scroll smoothness) PASS ("fluid movement instead of slow molasses", fallback barely visible before the real logo lands); Test 2 (logo sharpness) PASS at 1x — no HiDPI hardware available to exercise WR-02, which remains a documented non-blocking follow-up.
score: 6/6 must-haves verified
overrides_applied: 0
human_verification:
  - test: "On a HiDPI display (Wayland fractional 1.5x/2x or macOS Retina 2x), import a large multi-station list (e.g. DI.fm via AudioAddict import), then fast-scroll the sidebar top-to-bottom before thumbnails have been generated. Confirm no multi-row stall and that logos progressively fill in from the fallback (audio-x-generic-symbolic) placeholder to real station logos within a few seconds."
    expected: "First scroll is smooth with no perceptible per-row stall; logos appear progressively as daemon workers complete. Subsequent scrolls show all logos instantly from the QPixmapCache. No torn or partial thumbnail images are visible."
    why_human: "Paint-path smoothness and event-loop jank are perceptual. The async repaint pipeline is verified structurally and by the dataChanged test, but true first-scroll smoothness on a large DI.fm-scale list (80+ stations) under real GPU compositing cannot be asserted deterministically."
  - test: "On a HiDPI display (2x or fractional), verify that sidebar station logos are acceptably sharp after thumbnails have been generated. Compare against the prior behavior (if a pre-phase-94 snapshot is available) or judge by eye."
    expected: "Logos are visually crisp at the cell size. Given WR-02: the 96px thumb is rendered into a 32px logical cell; on a 2x display the cell is 64 physical pixels but the thumb is 96px physical, so no upscale occurs. Sharpness is at least as good as the pre-phase legacy path (which also decoded a large source and scaled to 32px)."
    why_human: "Visual sharpness on fractional/Retina scaling is perceptual. WR-02 documents that the thumb DPR=1.0 limitation means DPR is not propagated, but the 96px source is large enough to cover 2x without upscaling — a human on real hardware is the authoritative judge."
---

# Phase 94: Sidebar Logo Thumbnail Optimization — Verification Report

**Phase Goal:** Speed up station-sidebar scrolling on large lists by loading lazily-generated, off-UI-thread 96px logo thumbnails in the sidebar (mtime-invalidated) instead of synchronously decoding full-res PNGs on the paint path, while leaving the Now Playing full-res path untouched.
**Verified:** 2026-06-15T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D-01: now_playing_panel._load_scaled_pixmap exists and contains no reference to station_art.thumb; phase-94 commits do not touch the file | VERIFIED | `grep -n "_load_scaled_pixmap\|station_art.thumb" now_playing_panel.py` → `_load_scaled_pixmap` at line 204, no thumb reference. `git log -- now_playing_panel.py` shows last change was phase 87 (commit `9b7a82fd`); no phase-94 commit. Drift-guard test `test_now_playing_panel_does_not_use_thumb` PASSES. |
| 2 | D-02: load_station_icon generates thumbnails lazily (no migration), writes via daemon thread, on_thumb_needed fires on miss | VERIFIED | `_generate_thumb` at `_art_paths.py:76–130` spawns `threading.Thread(target=_worker, daemon=True).start()`. No migration code anywhere. `test_generate_thumb_writes_png` and `test_thumb_missing_returns_fallback` both PASS (22/22 suite). |
| 3 | D-03 (CENTRAL): on thumb miss with on_thumb_needed provided, load_station_icon returns QPixmap(FALLBACK_ICON) immediately — no full-res decode — and enqueues async generation; row repaints via dataChanged when thumb lands | VERIFIED | Code at `_art_paths.py:187–197`: `elif on_thumb_needed is not None: src = QPixmap(FALLBACK_ICON); on_thumb_needed(station.id, abs_path, thumb_path)`. No `QPixmap(load_path)` or `QPixmap(abs_path)` on this branch. `test_thumb_landing_emits_datachanged` confirms exactly one `dataChanged` emission with `Qt.DecorationRole` after the worker lands. `test_in_flight_dedup` confirms dedup guard fires and `_in_flight_thumbs` is cleared. |
| 4 | D-03 threading: QImage off-thread, QPixmap main-thread only; cross-thread via SimpleQueue+QTimer bridge; timer is lifecycle-managed (not always-on) | VERIFIED | `_generate_thumb` worker body (lines 94–128) uses only `QImage`. No `QPixmap` call inside `_generate_thumb`. Signal is `_thumb_landing = Signal(int, str, str)`. Daemon callback calls `pending.put(...)` only; `_poll_pending_landings` QTimer slot (10ms, NOT started in `__init__`) drains the queue and emits `_thumb_landing` from the main thread. `Qt.QueuedConnection` on `_on_thumb_landing`. Timer `start()` called only inside `_request_thumb` on first enqueue; `stop()` called in `_poll_pending_landings` when queue empty and `_in_flight_thumbs` empty. |
| 5 | D-04: generated thumbnail is 96px on the longest axis | VERIFIED | `_art_paths.py:102`: `scaled = img.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)`. `test_thumb_is_96px` uses a 200×100 source and asserts `max(img.width(), img.height()) <= 96` with aspect-ratio check. PASSES. |
| 6 | D-05/D-06: thumbnail at assets/{id}/station_art.thumb.png written atomically (mkstemp+os.replace); staleness via mtime check | VERIFIED | `THUMB_FILENAME = "station_art.thumb.png"` at line 39. `_thumb_path_for` returns `os.path.join(os.path.dirname(abs_source_path), THUMB_FILENAME)`. Atomic write: `mkstemp(dir=thumb_dir, suffix=".thumb.tmp.png")` + `os.replace(tmp, thumb_path)`. `_is_thumb_fresh` checks `os.stat(thumb_path).st_mtime >= os.stat(source_path).st_mtime`, returns `False` on any `OSError`. Tests `test_thumb_path_derivation` and `test_thumb_freshness_check` PASS. |

**Score:** 6/6 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/ui_qt/_art_paths.py` | THUMB_FILENAME, _thumb_path_for, _is_thumb_fresh, _generate_thumb, load_station_icon with on_thumb_needed param | VERIFIED | All 4 helpers present and substantive. File is 229 lines (well above min_lines: 130). QPixmap absent from _generate_thumb body. |
| `musicstreamer/ui_qt/station_tree_model.py` | _thumb_landing Signal, _in_flight_thumbs, _request_thumb, _on_thumb_landing, index_for_station_id; data() wired | VERIFIED | All 5 symbols present. `data()` line 295: `return load_station_icon(node.station, on_thumb_needed=self._request_thumb)`. Cache eviction at `_on_thumb_landing` line 200: `QPixmapCache.remove(f"station-logo:{source_path}")`. |
| `tests/test_art_paths.py` | 5 new phase-94 tests (D-02/D-04/D-05/D-06) | VERIFIED | 14 total tests (9 pre-existing + 5 new). All 5 names from VALIDATION.md present. All PASS. |
| `tests/test_station_thumb_async.py` | 4 tests (D-01/D-03); file created new | VERIFIED | 4 tests present. All PASS. Includes `qtbot.waitSignal` (upgraded from WR-03 fixed 500ms timeout). |
| `musicstreamer/ui_qt/now_playing_panel.py` | UNTOUCHED — no phase-94 commits | VERIFIED | Last commit `9b7a82fd` (phase 87). No reference to `station_art.thumb` in source. `_load_scaled_pixmap` at line 204. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `station_tree_model.data()` | `load_station_icon(on_thumb_needed=self._request_thumb)` | DecorationRole branch, line 295 | WIRED | Exact pattern `on_thumb_needed=self._request_thumb` present. Count: 1. |
| `_request_thumb` | `_art_paths_mod._generate_thumb` | Module-attribute reference for monkeypatching | WIRED | `_art_paths_mod._generate_thumb(...)` at line 147. |
| daemon thread callback | `_pending_landings` (SimpleQueue) | `pending.put((sid, src, path or ""))` in `_callback` closure | WIRED | Callback at line 143–145. |
| `_poll_pending_landings` (QTimer slot) | `_thumb_landing.emit(sid, src, path)` | Main-thread emission from timer | WIRED | Line 167. |
| `_on_thumb_landing` | `QPixmapCache.remove + dataChanged.emit` | Source-path keyed eviction + index re-derivation | WIRED | Lines 200–203. Cache key `f"station-logo:{source_path}"` matches `load_station_icon` insert key and `edit_station_dialog._invalidate_cache_for`. |
| `load_station_icon` miss branch | `QPixmap(FALLBACK_ICON)` (not `QPixmap(load_path)`) | `elif on_thumb_needed is not None:` branch | WIRED | Lines 187–197. The full-res decode `QPixmap(load_path)` is reached ONLY in the legacy `else` branch (no `on_thumb_needed` provided). Paint path with on_thumb_needed is zero-cost. |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `station_tree_model.data()` DecorationRole | `QIcon` returned | `load_station_icon` → QPixmapCache → thumb PNG on disk | Yes — disk PNG generated by daemon worker via QImage decode+scale | FLOWING |
| `_generate_thumb` worker | `scaled` (QImage) | `QImage(source_path).scaled(96,96,...)` | Yes — reads real on-disk source PNG | FLOWING |
| `_on_thumb_landing` | `dataChanged` emission | `index_for_station_id(station_id)` two-level walk | Yes — live model node walk | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| D-05: THUMB_FILENAME constant value | `grep 'THUMB_FILENAME = ' _art_paths.py` | `THUMB_FILENAME = "station_art.thumb.png"` | PASS |
| D-03: on_thumb_needed miss uses FALLBACK not load_path | Code read lines 187–197 | `src = QPixmap(FALLBACK_ICON)` in elif branch; `QPixmap(load_path)` only in else (legacy) | PASS |
| D-03: QPixmap absent from _generate_thumb body | `grep QPixmap` inside lines 76–130 | Only `# CR-01: the worker uses QImage only` comment; no `QPixmap(` call | PASS |
| D-03: timer not started in __init__ | `grep '\.start()' __init__ range` | Only comment `# Do NOT call .start() here`; `start()` called only in `_request_thumb` | PASS |
| D-01: no phase-94 commits to now_playing_panel.py | `git log --since=2026-06-10 -- now_playing_panel.py` | No commits | PASS |
| Phase quick suite | `.venv/bin/python -m pytest tests/test_art_paths.py tests/test_station_icon_integration.py tests/test_station_thumb_async.py -q` | `22 passed, 1 warning in 0.89s` | PASS |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `musicstreamer/ui_qt/_art_paths.py` | 89 | `CR-01:` used as inline comment prefix (IN-02: naming nit) | Info | Cosmetic ambiguity between code-review IDs and implementation notes. Non-blocking per review assessment. |
| `tests/test_station_thumb_async.py` | 181 | `QTest.qWait(200)` hard timeout in `test_in_flight_dedup` | Warning | WR-03 was fixed for `test_thumb_landing_emits_datachanged` (now uses `qtbot.waitSignal`). The dedup test still uses a fixed 200ms wait. In this test the spy replaces the real worker (callback fires synchronously), so the 200ms wait is draining a QueuedConnection, not a real disk write — materially less flaky than the original 500ms real-worker wait. Acceptable for current coverage. |

No `TBD`, `FIXME`, or `XXX` markers found in any phase-94-modified file.

---

### Review Findings Status

| Finding | Severity | Status |
|---------|----------|--------|
| CR-01: temp file leaked on `QImage.save()` returning False | Critical | FIXED — commit `18cf9326`. `else` branch now calls `os.unlink(tmp)` before `callback(..., None)`. Confirmed at `_art_paths.py:115–120`. |
| WR-01: duplicate comment block in `StationTreeModel.__init__` | Warning | FIXED — commit `9a530470`. Only one copy of the dedup-guard comment remains (line 50–51, naming `_poll_pending_landings` as the correct second access site). |
| WR-02: 96px thumb has DPR=1.0 → potential HiDPI softness | Warning | OPEN (intentional non-fix). The 96px source is larger than the 32px logical cell even at 2x (96px > 64px physical), so no upscale occurs on 2x displays. Qt will subsample rather than upscale. Visual sharpness is a human judgment — routed to human_verification section. This is explicitly not a regression vs the prior full-res-scaled-to-32px path. |
| WR-03: `test_thumb_landing_emits_datachanged` relied on 500ms hard timeout | Warning | FIXED — commit `0e3211b6`. Test now uses `qtbot.waitSignal(model.dataChanged, timeout=5000)`. Confirmed in `test_station_thumb_async.py:126–127`. |
| IN-01: no test for permanent-fallback-cache state after generation failure | Info | OPEN (enhancement). No test exercises the double-call path where `_generate_thumb` fails and the second `data()` call hits the cached fallback without re-calling `on_thumb_needed`. Non-blocking per review assessment. |
| IN-02: `CR-01:` comment prefix naming nit | Info | OPEN (cosmetic). Non-blocking. |

---

### Requirements Coverage

| Decision | Description | Status | Evidence |
|----------|-------------|--------|----------|
| D-01 | Now Playing full-res 180px path untouched and drift-guarded | SATISFIED | `now_playing_panel.py` unchanged since phase 87; `_load_scaled_pixmap` exists; no thumb reference; drift-guard test PASSES |
| D-02 | Lazy generation on cache/file miss, daemon thread, disk write, no migration | SATISFIED | `_generate_thumb` daemon thread + callback; `test_generate_thumb_writes_png` PASSES; no migration code |
| D-03 | Async generate-on-miss: immediate fallback, off-thread worker, dataChanged repaint, dedup guard | SATISFIED | Full pipeline verified in code and by `test_thumb_landing_emits_datachanged` + `test_in_flight_dedup` PASSING |
| D-04 | Single 96px thumbnail (longest axis) | SATISFIED | `img.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)` at line 102; `test_thumb_is_96px` PASSES |
| D-05 | Thumbnail at assets/{id}/station_art.thumb.png, atomic write | SATISFIED | `THUMB_FILENAME = "station_art.thumb.png"`, `_thumb_path_for` sibling derivation, mkstemp+os.replace; `test_thumb_path_derivation` PASSES |
| D-06 | mtime staleness check on load | SATISFIED | `_is_thumb_fresh` with `os.stat` mtime comparison, `OSError` fallback; `test_thumb_freshness_check` PASSES |

---

### Human Verification Required

#### 1. First-scroll smoothness on a DI.fm-scale list

**Test:** Import a large AudioAddict network (e.g. DI.fm) using the existing import flow. Clear any pre-existing thumbnail cache by removing `assets/*/station_art.thumb.png` files. Launch the application and fast-scroll the station sidebar from top to bottom on the first pass before any thumbnails have been generated.

**Expected:** No per-row multi-frame stall during the first scroll. Logos appear as the audio-x-generic-symbolic fallback initially, then fill in with real 96px thumbnails progressively as daemon workers complete (within a few seconds of scrolling past each row). Re-scrolling is instant (all logos already cached in QPixmapCache). No torn or partially-written thumbnail files visible.

**Why human:** Perceptual smoothness and event-loop jank under real scroll event pressure, real disk I/O, and GPU compositing cannot be asserted deterministically in a headless test. The async pipeline is structurally correct and `test_thumb_landing_emits_datachanged` proves the repaint chain, but the subjective "smooth" quality on a 80+-station list requires direct observation.

#### 2. Logo sharpness at HiDPI on thumbnails

**Test:** On a HiDPI display (Wayland fractional 1.5x/2x, macOS Retina 2x, or Windows 1.5x/2x), after thumbnails have been generated, scroll the sidebar and inspect station logos at the native display resolution.

**Expected:** Logos are visually crisp. The 96px thumbnail at DPR=1.0 is 96 physical pixels; the 32px logical icon at 2x is 64 physical pixels — meaning the 96px source is downsampled (not upscaled) for display, so sharpness should be at least as good as the prior path (which also decoded a large source and scaled down). WR-02 notes the DPR metadata is not set on the thumb pixmap, which is an acknowledged limitation, but the source resolution is sufficient to avoid upscale artifacts on 2x.

**Why human:** Visual sharpness on fractional/Retina displays is perceptual and hardware-dependent. The implementation correctness is verified; sharpness quality is a human judgment.

---

## Gaps Summary

No blocking gaps. All 6 decisions (D-01 through D-06) are implemented, wired, and covered by passing tests. The two open review items (WR-02 HiDPI DPR metadata, IN-01 failure-path cache coverage) are acknowledged non-blocking enhancements that do not prevent the phase goal from being achieved. Status is `human_needed` because first-scroll smoothness and HiDPI sharpness are legitimately manual checks per `94-VALIDATION.md`'s Manual-Only Verifications table — not because any automated check failed.

---

_Verified: 2026-06-15T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
