---
phase: 74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-
fixed_at: 2026-05-14T00:00:00Z
review_path: .planning/phases/74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-/74-REVIEW.md
iteration: 1
findings_in_scope: 17
fixed: 15
skipped: 2
status: partial
---

# Phase 74: Code Review Fix Report

**Fixed at:** 2026-05-14
**Source review:** `.planning/phases/74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-/74-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 17 (5 Critical, 7 Warning, 5 Info — `fix_scope=all`)
- Fixed: 15
- Skipped: 2 (both Info-tier; explicit out-of-scope per REVIEW.md)

## Fixed Issues

### CR-01: `_resolve_pls` silently corrupts the import by returning the input PLS URL as if it were a stream URL

**Files modified:** `musicstreamer/soma_import.py`
**Commit:** `0cdb767`
**Applied fix:** Replaced `return [pls_url]` on fetch/parse failure with `return []`. Added a `_log.warning` so the failure is diagnosable. The caller (`fetch_channels`) already drops channels with zero recognisable tiers via `if not streams: continue`, so the empty-list return produces the correct behaviour (channel dropped from import, no broken `.pls` URL persisted as a stream row).

### CR-02: SSRF / local-file-read via `urllib.request.urlopen` — no scheme allow-list on any of the three call sites

**Files modified:** `musicstreamer/soma_import.py`
**Commit:** `004b4f4`
**Applied fix:** Added `_safe_urlopen_request(url)` helper that validates `urlparse(url).scheme in {"https", "http"}` and that `netloc` is non-empty before building the Request. Replaced all three call sites (`fetch_channels`, `_resolve_pls`, `_download_logo`) to route through the helper. `file://`, `ftp://`, `jar://`, and empty-netloc URLs now raise `ValueError` before any network/filesystem touch.

### CR-03: SQLite connection leak in `_download_logos` — one connection per logo, never closed

**Files modified:** `musicstreamer/soma_import.py`
**Commit:** `42b9256`
**Applied fix:** Wrapped `db_connect()` inside `_download_logo` in `try/finally` so the connection closes deterministically rather than relying on refcount GC under `ThreadPoolExecutor`. Eliminates the dozens-of-WAL-locked-connections accumulation pattern flagged in MEMORY.md `reference_musicstreamer_db_schema.md`.

### CR-04: `import_stations` per-channel try/except allows half-imported stations to persist permanently

**Files modified:** `musicstreamer/soma_import.py`
**Commit:** `bf063e1`
**Applied fix:** Track `inserted_station_id: int | None` per channel. Set it after `repo.insert_station(...)` succeeds; clear it (set to `None`) after the per-stream loop completes successfully. In the per-channel `except Exception` handler, call `repo.delete_station(inserted_station_id)` if the sentinel is still set — `delete_station` relies on the `ON DELETE CASCADE` FK between `station_streams.station_id` and `stations.id` (repo.py:72) plus `PRAGMA foreign_keys = ON` in `db_connect` (repo.py:20), so the partial stream rows are cleaned up atomically with the station row. The next re-import can then repair the channel.

**Note:** This finding involves stateful logic (rollback sentinel handling). The fix passes Tier 1 (re-read) and Tier 2 (syntax check), but the actual rollback semantics under failure should be confirmed by a UAT round-trip that forces an `insert_stream` failure mid-loop and verifies (a) station row gone, (b) all stream rows gone, (c) skipped counter incremented, (d) re-import succeeds.

### CR-05: `_on_soma_import_error` skips `_refresh_station_list()` — UI silently stale after partial-import failure

**Files modified:** `musicstreamer/ui_qt/main_window.py`
**Commit:** `76f727d`
**Applied fix:** Added `self._refresh_station_list()` to `_on_soma_import_error` so the StationListPanel reflects whatever rows `import_stations` managed to commit before the failure propagated. Mirrors the success-path handler (`_on_soma_import_done`, line 1516).

### WR-01: `_download_logos` silently swallows ALL exceptions with no log line

**Files modified:** `musicstreamer/soma_import.py`
**Commit:** `bf08bf6`
**Applied fix:** Replaced the bare `except Exception: pass` with `_log.warning("SomaFM logo download failed for station %s (%s): %s", station_id, image_url, exc)` so future "half my stations have no art" reports are diagnosable.

### WR-02: Double-clicking "Import SomaFM" spawns parallel workers — no in-flight guard

**Files modified:** `musicstreamer/ui_qt/main_window.py`
**Commit:** `cd53c49`
**Applied fix:** Added `if self._soma_import_worker is not None: show_toast("…already in progress"); return` guard at the top of `_on_soma_import_clicked`. Applied the same guard to `_on_gbs_add_clicked` since the REVIEW explicitly flagged the GBS analog as having the identical defect.

### WR-03: `_bitrate_from_url` accepts arbitrary-length digit runs; no upper bound on parsed bitrate

**Files modified:** `musicstreamer/soma_import.py`
**Commit:** `d32b48f`
**Applied fix:** Capped the digit run at `\d{1,5}` in `_BITRATE_FROM_URL_RE` (no realistic ICE bitrate exceeds 5 digits) and added `if 8 <= value <= 9999: return value` so out-of-range values fall through to the table default. Closes both the quadratic-`int()` DoS surface and the silent-1e12-bitrate UI corruption surface.

### WR-04: `test_re_import_emits_no_changes_toast_via_real_thread` calls real `db_connect()` from a worker thread

**Files modified:** `tests/test_main_window_soma.py`
**Commit:** `2bfcb94`
**Applied fix:** Monkeypatched `musicstreamer.ui_qt.main_window.db_connect` to `lambda: sqlite3.connect(":memory:")` and `musicstreamer.repo.Repo` to `lambda con: MagicMock()`. The `Repo` patch targets `musicstreamer.repo` (not `main_window`) because `_SomaImportWorker.run()` does `from musicstreamer.repo import Repo` lazily inside the worker thread — the symbol is not in `main_window`'s namespace at the time the worker imports it.

### WR-05: `test_no_self_capturing_lambda_in_soma_action` parses source with `open(...)` and never closes the file

**Files modified:** `tests/test_main_window_soma.py`, `tests/test_main_window_gbs.py`
**Commit:** `9891e4d`
**Applied fix:** Replaced `open(...).read()` with `Path("…").read_text(encoding="utf-8")` in both test files (the GBS sibling test had the same defect). Eliminates the FD leak / ResourceWarning trip surface.

### WR-06: Codec literal "AAC" stored for both LC-AAC and HE-AAC (aacp) streams — DB cannot distinguish

**Files modified:** `musicstreamer/soma_import.py`, `.planning/phases/74-somafm-full-station-catalog-art-pull-all-somafm-streams-and-/74-LEARNINGS.md`
**Commit:** `fb234b4`
**Applied fix:** Chose the "accept the precision loss and add a TODO" branch from the REVIEW.md fix recommendation. Flipping aacp tiers to `"HE-AAC"` requires a player-codec-routing tap (Phase 69 WIN-05) which is out of scope for review-fix. Added a `WR-06 TODO` comment block in `_TIER_BY_FORMAT_QUALITY` documenting the deferred follow-up + the player routing tap that must precede the literal change. Added a corresponding entry to `74-LEARNINGS.md` under "Lessons" so the follow-up has a discoverable home (and bumped `counts.lessons` from 6 to 7 in the frontmatter).

### WR-07: `urllib.error` imported but never used — betrays incomplete error-handling design

**Files modified:** `musicstreamer/soma_import.py`
**Commit:** `2a4f631`
**Applied fix:** Wrapped the `urllib.request.urlopen(_API_URL)` call in `fetch_channels` in a `try/except urllib.error.HTTPError` block. 5xx → `RuntimeError("SomaFM is temporarily unavailable — try again in a few minutes")`. Other 4xx → `RuntimeError(f"SomaFM API rejected the request (HTTP {code}) — please file a bug")`. The wrapped error propagates through the existing `_SomaImportWorker.error` signal to the toast handler, so a 503 now shows a recoverable-blip toast instead of an opaque "SomaFM import failed: HTTP Error 503".

### IN-01: `_SomaImportWorker.__init__` is a no-op forward — drop it

**Files modified:** `musicstreamer/ui_qt/main_window.py`
**Commit:** `e6c12b4`
**Applied fix:** Removed the no-op `__init__(self, parent=None): super().__init__(parent)` override on both `_GbsImportWorker` and `_SomaImportWorker`. PySide6 accepts `Worker(parent=self)` natively against the inherited `QThread.__init__`. Updated both class docstrings to note the deliberate removal.

### IN-02: `_bitrate_from_url` is dead-code-tested as a public API but underscore-prefixed

**Files modified:** `musicstreamer/soma_import.py`, `tests/test_soma_import.py`
**Commit:** `4f21512`
**Applied fix:** Renamed `_bitrate_from_url` → `bitrate_from_url` (public). Retained `_bitrate_from_url = bitrate_from_url` as a module-level alias for backward compatibility with any external grep / caller. Updated the in-module `fetch_channels` call site and the three `tests/test_soma_import.py` call sites to use the new public name.

### IN-05: `_log.warning` for swallowed channel exceptions includes only `ch.get("id")` — missing `title` for diagnostic correlation

**Files modified:** `musicstreamer/soma_import.py`
**Commit:** `11e70da`
**Applied fix:** Updated both `_log.warning` sites (one in `fetch_channels`, one in `import_stations`) to include `ch.get("title")` in addition to `ch.get("id")`. Users report failures by title, not slug — the new format `"SomaFM channel %r (%s) import skipped: %s"` carries both for correlation.

## Skipped Issues

### IN-03: Three near-identical worker classes

**File:** `musicstreamer/ui_qt/main_window.py:88-174`
**Reason:** REVIEW.md explicitly classifies this as a "future refactor; out of scope for Phase 74 closeout." Consolidating `_ExportWorker`, `_ImportPreviewWorker`, `_GbsImportWorker`, and `_SomaImportWorker` into a single parametrised `_BackgroundWorker(QThread)` base would be a cross-cutting refactor touching all four signal-shape contracts and their associated regression tests. Deferred per the review author's stated scope.
**Original issue:** All four QThread subclasses follow the same `<verb>_finished` + `error` + forward-`__init__` + try/except-`run()` shape. After the 74-06 rename the pattern is even more uniform — a candidate for a single parametrised base class.

### IN-04: `tests/test_constants_drift.py` regex-style baseline test inflates phase-completion risk

**File:** `tests/test_constants_drift.py:82-108`
**Reason:** REVIEW.md explicitly states "Out of scope for Phase 74 but worth noting since Phase 74 added two new drift tests in the same file." The brittleness predates Phase 74 (the test was RED for the entirety of Phase 71 per the docstring) and changing its semantics is a cross-phase concern. The reviewer flagged it for awareness, not for closure in this review-fix pass.
**Original issue:** `test_richtext_baseline_unchanged_by_phase_71` literally counts `setTextFormat(Qt.RichText)` occurrences and asserts equality. Any addition of a legitimate new RichText QLabel will RED-fail an unrelated test in an unrelated phase.

---

_Fixed: 2026-05-14_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
