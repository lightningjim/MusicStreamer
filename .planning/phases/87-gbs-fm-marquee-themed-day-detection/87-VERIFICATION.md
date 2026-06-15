---
phase: 87-gbs-fm-marquee-themed-day-detection
verified: 2026-06-15T14:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 4/5
  gaps_closed:
    - "SC1 UNCERTAIN resolved: themed-day correlator now hashes the dynamic #leftmenulogo CSS URL (extract_leftmenulogo_url), not the static logo_3.png that never drifted; test_pride_logo_drifts_from_baseline confirms the Pride fixture URL resolves and drifts (is_themed=True)"
    - "CR-01 CLEARED: QPixmap import removed from gbs_marquee.py; worker emits raw bytes via themed_logo_ready; set_themed_logo_override decodes bytes on the main thread; test_worker_emits_raw_bytes_not_qpixmap asserts payload is bytes not QPixmap"
    - "WR-01 FIXED (87-REVIEW-gap): themed-day one-shot now gates on homepage-fetch success (html is not None), not marquee-text-parse success; test_themed_day_fires_when_marquee_empty regression passes"
    - "WR-02 FIXED (87-REVIEW-gap): _fetch_logo_bytes rejects non-http(s) URL schemes via urlsplit scheme guard; test_fetch_logo_bytes_rejects_non_http_scheme passes"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Live end-to-end themed-logo swap: bind a GBS.FM station during an active themed-day window (next expected: Halloween 2026-10-31, or any future themed window) and confirm the logo_label slot shows the themed PNG for the session"
    expected: "logo_label in NowPlayingPanel displays the themed PNG. cover_label unchanged. No libnotify toast. SQLite station record unchanged after session. Next app launch re-evaluates from scratch (no persisted override)."
    why_human: "Automated tests (test_pride_logo_drifts_from_baseline, test_worker_emits_raw_bytes_not_qpixmap) confirm the resolver, drift detection, and raw-bytes emission paths are correct, but they do not run a live network fetch against gbs.fm nor exercise the actual Qt GUI paint path end-to-end. The Pride themed-day window was confirmed as the root cause of the original UAT failure; UAT Test 2 was not re-run live after the 87-07 fix. This item closes once the feature is successfully exercised on a live themed-day window with the corrected code."
  - test: "CR-01 thread-safety on macOS or Windows (cross-platform confirmation): bind a GBS.FM station during a live or mocked themed day and confirm no crash, Qt warning, or corrupted pixmap"
    expected: "No QPixmap-on-non-GUI-thread crash or warning. Themed logo renders correctly. UAT Test 3 from 87-HUMAN-UAT is now unblocked since the logo swap path (UAT Test 2) is closed at the code level."
    why_human: "Qt thread-affinity violations are silently masked by Linux XCB/offscreen backends. CR-01 is cleared in code (QPixmap import absent from gbs_marquee.py; worker emits bytes; slot decodes on main thread), but the original UAT Test 3 was blocked because Test 2 never fired the swap path on Windows. Now that Test 2 is closed at the code level, a live re-run on macOS or Windows during a themed-day window can confirm the fix end-to-end."
---

# Phase 87: GBS.FM Marquee + Themed-Day Detection Verification Report

**Phase Goal:** When the bound station is GBS.FM, the user sees the current themed logo (if any), a dismissible top-of-panel announcement banner, and a live updating marquee — all backed by the Phase 76 QtWebEngine cookie-persistence pattern that Phase 89 reuses for channel avatars.
**Verified:** 2026-06-15T14:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (plan 87-07 + 87-REVIEW-gap fixes)

## Re-verification Summary

This is a re-verification following closure of the gaps identified in the initial 87-VERIFICATION.md (status: human_needed, score: 4/5) and confirmed by 87-HUMAN-UAT.md.

Items closed at the code/automated level since initial verification:

**SC1 (UNCERTAIN → VERIFIED at code level):** The original themed-day correlator hashed a hardcoded static `logo_3.png` URL that never changes for themed days. Plan 87-07 introduced `extract_leftmenulogo_url(html)` which parses the `#leftmenulogo {background-image:url('...')}` CSS rule from the homepage HTML already fetched for the marquee (single fetch, no second round-trip). The resolver handles both the imgur form (`https://i.imgur.com/l27hhaY.png`) and the img.gbs.fm/raw form (`https://img.gbs.fm/NIgE8/yucEqesu87.png/raw`). `test_pride_logo_drifts_from_baseline` (the UAT Test 2 regression) confirms: the Pride fixture URL is resolved correctly AND bytes whose hash is not in `GBS_LOGO_BASELINE_HASHES` yield `is_themed=True` per D-12.

**CR-01 (WARNING → CLEARED):** `from PySide6.QtGui import QPixmap` is absent from `gbs_marquee.py`. The worker emits raw `bytes` via `themed_logo_ready`. `set_themed_logo_override` accepts `bytes | bytearray | QPixmap` and decodes bytes on the main thread. `test_worker_emits_raw_bytes_not_qpixmap` asserts emission is `bytes`, not QPixmap. `test_set_themed_logo_override_accepts_bytes` confirms both payload types work correctly.

**WR-01 (87-REVIEW-gap, WARNING → FIXED):** The themed-day one-shot now gates on `html is not None` (homepage-fetch success), not `marquee_ok` (noticearea-text parse success). A themed day with an empty marquee still applies the D-12 logo override. `test_themed_day_fires_when_marquee_empty` regression passes: a fixture with a `#leftmenulogo` rule but no `<p id="noticearea">` element still triggers the logo fetch.

**WR-02 (87-REVIEW-gap, WARNING → FIXED):** `_fetch_logo_bytes` validates the scheme via `urllib.parse.urlsplit(url).scheme.lower() not in ("http", "https")` before calling `urlopen`. Non-http(s) URLs (file://, ftp://) are rejected with a WARN log and `None` return. `test_fetch_logo_bytes_rejects_non_http_scheme` confirms `file:///etc/passwd` and `ftp://example.com/logo.png` both return `None` without calling `urlopen`.

Items still requiring human verification: live end-to-end themed-logo swap on a running app (live network + Qt GUI), and CR-01 cross-platform confirmation on macOS/Windows with the swap path actually firing. These remain because automated tests cannot substitute for a live network session against gbs.fm or a native Qt paint backend on a stricter platform.

## Code Review Note

**87-REVIEW-gap.md (post-87-07) identified 2 warnings, both now FIXED:**

- **WR-01:** Themed-logo gate was coupled to marquee-text parse success (`marquee_ok`). Fixed: gate is now `html is not None` (homepage-fetch success). Verified at line 610 of `gbs_marquee.py`. Regression test: `test_themed_day_fires_when_marquee_empty` passes.
- **WR-02:** `_fetch_logo_bytes` accepted arbitrary URL schemes from page HTML. Fixed: scheme guard at line 406 of `gbs_marquee.py`. Regression test: `test_fetch_logo_bytes_rejects_non_http_scheme` passes.

**87-REVIEW-gap.md IN-01 (stale docstring — Signals: block says "Carries a QPixmap or None"):**
The `GbsMarqueeWorker` class docstring at line 463 still reads `Carries a \`\`QPixmap\`\` or None.` — a stale description from before CR-01. The inline comment on the `Signal(object)` declaration at line 468 is correct (`raw PNG bytes — CR-01: NO QPixmap off the GUI thread`), but the `Signals:` block docstring was not updated. This is a documentation smell only (behavior is correct and tested); it does not affect correctness. The initial 87-REVIEW.md noted this as IN-01 and it is still present.

**87-REVIEW-gap.md IN-02 (redundant is_drift clause):** `is_drift = (label_in_table is None) or (label_in_table != "canonical")` — correct per D-12 verbatim; redundant but not a bug. Not changed.

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | When user binds a GBS.FM station on a known themed day, now-playing logo slot displays themed logo for session; never cover slot, never station-list row, never libnotify toast (GBS-THEME-05) | ✓ VERIFIED (code-level) | `extract_leftmenulogo_url` resolves the dynamic CSS URL from reused homepage bytes; `_fetch_logo_bytes(url)` fetches the off-site host; `compute_logo_theme` drifts on any hash not in `GBS_LOGO_BASELINE_HASHES`; `set_themed_logo_override` writes `logo_label` only; `test_pride_logo_drifts_from_baseline` passes; `test_themed_logo_targets_logo_slot_only` drift-guard passes; `test_no_toast_in_themed_day_path` drift-guard passes. Live network + GUI path still needs human verification (see Human Verification Required). |
| 2 | Next app launch re-evaluates themed-day detection from scratch; themed logo does NOT persist to SQLite or carry past a session boundary (GBS-THEME-04) | ✓ VERIFIED | `_themed_logo_override` is `Optional[QPixmap]` in-memory only (NowPlayingPanel line 351); no write to `repo.py`; `test_themed_logo_never_persists` drift-guard passes; `repo.py` has zero references to `themed` or `_themed_logo` |
| 3 | When GBS.FM marquee text contains a new first pipe-segment announcement (hash-different from last-seen), a top-of-NowPlayingPanel banner appears; user can dismiss with × and same banner does not re-appear until marquee changes | ✓ VERIFIED | `AnnouncementBanner` widget exists; `_dismissed_announcement_hashes: set[str]` in `NowPlayingPanel`; `_on_marquee_ready` implements hash-check predicate; `test_banner_visibility_predicate` passes; `test_dismiss_stores_hash` passes |
| 4 | Marquee fetcher imports `paths.gbs_cookies_path()` + `musicstreamer.gbs_api.load_auth_context()`; source-grep drift-guard confirms no parallel cookie file written, no QtWebEngine session instantiated | ✓ VERIFIED | `from musicstreamer import gbs_api, paths` at line 47; `test_marquee_module_reuses_phase76_auth_only` passes (5 banned identifiers absent, required imports present) |
| 5 | 60-second poll cadence while GBS station bound + playing; 5-minute slow cadence otherwise; 10+ committed marquee fixtures plus 3+ themed-day / 5+ non-themed-day logo SHA-256 samples lock the parser and canonical-hash table | ✓ VERIFIED (with D-04 relaxation) | `set_cadence(60_000)` / `set_cadence(300_000)` wired via `_refresh_gbs_marquee_cadence`; `test_cadence_state_machine` passes; `test_fixture_count_ten_or_more` passes (10 data files + 2 additional fixtures = 12 total in directory; test counts ≥ 10 data files); GBS-THEME-06 3+/5+ literal relaxed per D-04; `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` with `next_window: 2026-10-31` |

**Score:** 5/5 truths verified at the automated/code level. 2 human verification items remain (live GUI session, cross-platform CR-01 confirmation).

### Deferred Items

No items deferred to later phases.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/gbs_marquee.py` | parse_marquee, MARQUEE_URL, GbsMarqueeWorker, compute_logo_theme, GBS_LOGO_BASELINE_HASHES, extract_leftmenulogo_url, _LEFTMENULOGO_RE | ✓ VERIFIED | All functions/classes present; QPixmap import ABSENT (CR-01 cleared); `_last_homepage_html` init at line 477; `extract_leftmenulogo_url` at line 249; scheme guard at line 406 |
| `musicstreamer/ui_qt/announcement_banner.py` | AnnouncementBanner(QWidget) with PlainText QLabel + dismissed Signal | ✓ VERIFIED | Class present, Qt.TextFormat.PlainText set, setWordWrap(True), dismissed Signal at class scope |
| `musicstreamer/ui_qt/now_playing_panel.py` | set_themed_logo_override(bytes\|QPixmap), attach_gbs_marquee_worker, _on_marquee_ready, AnnouncementBanner parented | ✓ VERIFIED | `set_themed_logo_override` at line 1129 accepts bytes/bytearray (decode main-thread) and QPixmap (D-09 re-apply); docstring updated for CR-01 |
| `musicstreamer/ui_qt/main_window.py` | GbsMarqueeWorker construction, start(), stop_and_wait() in closeEvent | ✓ VERIFIED | Worker constructed line 502; `start()` line 504; `stop_and_wait(5_000)` in closeEvent line 772 |
| `musicstreamer/buffer_log.py` | install_gbs_marquee_handler() | ✓ VERIFIED | Function at line 71; named logger `musicstreamer.gbs_marquee` |
| `musicstreamer/constants.py` | GBS_THEMED_DAY_KEYWORDS frozenset | ✓ VERIFIED | Line 81; 9 keywords |
| `tests/test_gbs_marquee.py` | 33 tests (24 original + 9 new from 87-07) | ✓ VERIFIED | 35 tests collected (2 from test file + 11 in test_announcement_banner.py accounts for 46 total across 3 files); all pass |
| `tests/test_gbs_marquee_drift_guard.py` | 5 source-grep drift-guards | ✓ VERIFIED | 5 tests, all pass |
| `tests/test_announcement_banner.py` | 6 widget + integration tests | ✓ VERIFIED | 6 tests, all pass |
| `tests/fixtures/gbs_marquee/2026-06-15_pride_homepage.html` | Pride fixture with img.gbs.fm/.../raw #leftmenulogo form | ✓ VERIFIED | File present, 35 lines; `#leftmenulogo {background-image:url('https://img.gbs.fm/NIgE8/yucEqesu87.png/raw');}` confirmed; sibling `#leftmenu`, `#bottomcont`, etc. rules present for selector-specificity test coverage |
| `tests/fixtures/gbs_themed_logos/2026-05-25_memorial-day_da-troops.png` | Live Memorial Day harvest | ✓ VERIFIED | File present, 7,458 bytes, SHA-256 in MANIFEST |
| `tests/fixtures/gbs_marquee/` | ≥ 10 samples (real + synthetic) | ✓ VERIFIED | 12 files total (3 HTML/JSON + MANIFEST + 8 synthetic .txt); 10 data files pass `test_fixture_count_ten_or_more` |
| `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` | GBS-THEME-06 D-04 follow-up | ✓ VERIFIED | resolves_phase: 87, next_window: 2026-10-31, requirement_id: GBS-THEME-06 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `GbsMarqueeWorker._on_tick` | `self._last_homepage_html` cache | `html or ""` assignment | ✓ WIRED | Line 592; cached before noticearea parse so `_on_first_gbs_bind` can reuse |
| `GbsMarqueeWorker._on_tick` | `_on_first_gbs_bind()` | `html is not None and not self._themed_day_detected_this_session` | ✓ WIRED | Line 610; gates on fetch success (not marquee-text parse) — WR-01 fix |
| `_on_first_gbs_bind` | `extract_leftmenulogo_url` | `self._last_homepage_html` | ✓ WIRED | Line 548; resolves dynamic URL from cached homepage bytes |
| `extract_leftmenulogo_url` | `_fetch_logo_bytes(logo_url)` | resolved URL parameter | ✓ WIRED | Line 553; passes off-site URL; scheme guard at line 406 |
| `_fetch_logo_bytes` | `urllib.request.urlopen` | `Request` with `User-Agent` header | ✓ WIRED | Line 413-414; scheme guard preceding the fetch |
| `GbsMarqueeWorker.themed_logo_ready` | `NowPlayingPanel.set_themed_logo_override` | `Qt.QueuedConnection` | ✓ WIRED | Line 1199; payload is raw `bytes` (CR-01 cleared) |
| `set_themed_logo_override` | `QPixmap().loadFromData(bytes(payload), "PNG")` | main-thread decode | ✓ WIRED | Lines 1158-1160; decode on GUI thread; decode failure returns early |
| `GbsMarqueeWorker._on_tick` | `gbs_api.load_auth_context` | `_fetch_marquee()` D-11 ladder | ✓ WIRED | `auth = gbs_api.load_auth_context()` line 338; anonymous fallback with User-Agent |
| `GbsMarqueeWorker.marquee_ready` | `NowPlayingPanel._on_marquee_ready` | `Qt.QueuedConnection` | ✓ WIRED | Line 1204 |
| `NowPlayingPanel.bind_station` | `GbsMarqueeWorker.set_cadence` | `_refresh_gbs_marquee_cadence` | ✓ WIRED | GBS.FM → `_refresh_gbs_marquee_cadence()`; non-GBS → `set_cadence(0)` |
| `AnnouncementBanner.dismissed` | `NowPlayingPanel._on_banner_dismissed` | AutoConnection | ✓ WIRED | Line 375 |
| `MainWindow.__init__` | `GbsMarqueeWorker.start()` | Direct call | ✓ WIRED | Line 504 |
| `MainWindow.closeEvent` | `GbsMarqueeWorker.stop_and_wait(5000)` | Direct call | ✓ WIRED | Lines 772-777 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `NowPlayingPanel` (banner) | `first_segment` | `GbsMarqueeWorker._fetch_marquee()` → `extract_noticearea_text()` → `parse_marquee()` | Yes — live urllib GET to `gbs.fm/` with Phase 76 auth or User-Agent anon | ✓ FLOWING |
| `NowPlayingPanel` (themed logo) | `_themed_logo_override: QPixmap` | `_on_tick` → `_last_homepage_html` → `extract_leftmenulogo_url()` → `_fetch_logo_bytes(dynamic_url)` → `compute_logo_theme()` → `themed_logo_ready.emit(logo_bytes)` → `set_themed_logo_override` (main thread) | Yes — live urllib GET to dynamic off-site logo URL (e.g. img.gbs.fm); CR-01 cleared | ✓ FLOWING (human live-window verification still needed) |
| `GBS_LOGO_BASELINE_HASHES` | `dict[str, str]` | Hardcoded literal at module scope | Yes — 1 real-captured SHA-256 from Memorial Day harvest (dynamic #leftmenulogo imgur URL); comment corrected in 87-07 | ✓ FLOWING (D-04 relaxed: 1 of required 3+ entries; follow-up todo tracks accretion) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full Phase 87 suite (46 tests) | `.venv/bin/python -m pytest tests/test_gbs_marquee.py tests/test_gbs_marquee_drift_guard.py tests/test_announcement_banner.py` | 46/46 PASSED (4.44s) | ✓ PASS |
| UAT Test 2 regression | `.venv/bin/python -m pytest tests/test_gbs_marquee.py::test_pride_logo_drifts_from_baseline` | PASSED | ✓ PASS |
| WR-01 regression (empty-marquee themed day) | `.venv/bin/python -m pytest tests/test_gbs_marquee.py::test_themed_day_fires_when_marquee_empty` | PASSED | ✓ PASS |
| WR-02 regression (non-http scheme guard) | `.venv/bin/python -m pytest tests/test_gbs_marquee.py::test_fetch_logo_bytes_rejects_non_http_scheme` | PASSED | ✓ PASS |
| CR-01 bytes emission | `.venv/bin/python -m pytest tests/test_gbs_marquee.py::test_worker_emits_raw_bytes_not_qpixmap` | PASSED | ✓ PASS |
| QPixmap decode on main thread | `.venv/bin/python -m pytest tests/test_gbs_marquee.py::test_set_themed_logo_override_accepts_bytes` | PASSED | ✓ PASS |
| Resolver — imgur form | `.venv/bin/python -m pytest tests/test_gbs_marquee.py::test_extract_leftmenulogo_url_imgur_form` | PASSED | ✓ PASS |
| Resolver — img.gbs.fm/raw form | `.venv/bin/python -m pytest tests/test_gbs_marquee.py::test_extract_leftmenulogo_url_imggbsfm_raw_form` | PASSED | ✓ PASS |
| Resolver — sibling selector specificity | `.venv/bin/python -m pytest tests/test_gbs_marquee.py::test_extract_leftmenulogo_url_selects_correct_rule` | PASSED | ✓ PASS |
| Drift-guards (5/5) | `.venv/bin/python -m pytest tests/test_gbs_marquee_drift_guard.py` | 5/5 PASSED | ✓ PASS |
| Banner visibility predicate | `.venv/bin/python -m pytest tests/test_announcement_banner.py::test_banner_visibility_predicate` | PASSED | ✓ PASS |

### Probe Execution

No probes declared in PLAN files. Step 7c: SKIPPED (no probe scripts declared for this phase).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| GBS-THEME-01 | 87-04 / 87-07 | Fetch the themed logo (dynamic #leftmenulogo URL, not logo_3.png) and SHA-256 hash on GBS bind | ✓ SATISFIED | `extract_leftmenulogo_url` resolves dynamic URL; `_fetch_logo_bytes(url)` fetches; `compute_logo_theme` hashes; `test_extract_leftmenulogo_url_imgur_form` + `test_extract_leftmenulogo_url_imggbsfm_raw_form` pass |
| GBS-THEME-02 | 87-04 / 87-07 | SHA-256 differs from baseline AND keyword match (or D-12 fallback) → themed logo applied | ✓ SATISFIED | `compute_logo_theme` implements D-12; keyword match AND fallback-no-keyword paths tested; `test_pride_logo_drifts_from_baseline` confirms Pride hash drifts |
| GBS-THEME-03 | 87-04 | Themed logo replaces logo slot ONLY; never cover slot, never station list | ✓ SATISFIED | `set_themed_logo_override` writes `logo_label` only; `test_themed_logo_targets_logo_slot_only` drift-guard blocks `cover_label` refs |
| GBS-THEME-04 | 87-04 | Themed logo is session-scoped, not persisted to SQLite | ✓ SATISFIED | `_themed_logo_override` is in-memory `Optional[QPixmap]`; `test_themed_logo_never_persists` drift-guard passes |
| GBS-THEME-05 | 87-05/06 | No toast / notification on themed day detection | ✓ SATISFIED | `test_no_toast_in_themed_day_path` drift-guard bans `show_toast`/`libnotify`/`QSystemTrayIcon` in both files |
| GBS-THEME-06 | 87-01/04/06 | 3+ themed-day + 5+ non-themed-day logo SHA-256 samples in fixture | ? PARTIAL (D-04 relaxed) | 1 themed entry in `GBS_LOGO_BASELINE_HASHES` (Memorial Day 2026-05-25, dynamic imgur URL); comment corrected in 87-07; no canonical entry yet; `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` tracks accretion |
| GBS-MARQ-01 | 87-03/04 | Poll 60s (playing) / 5 min (not playing) when GBS bound | ✓ SATISFIED | `_refresh_gbs_marquee_cadence`; `test_cadence_state_machine` passes |
| GBS-MARQ-02 | 87-02 | Marquee split on `\|`; first segment is announcement; others ignored for banner | ✓ SATISFIED | `parse_marquee` returns `(first_segment, full_text)`; 8+ parser tests pass |
| GBS-MARQ-03 | 87-05 | Banner visible: bound=GBS.FM AND non-empty AND hash not dismissed | ✓ SATISFIED | `_on_marquee_ready` visibility predicate; `test_banner_visibility_predicate` passes |
| GBS-MARQ-04 | 87-05 | Banner displays text with `\|` as wrap hints | ✓ SATISFIED | `set_announcement` replaces `\|` with `\n`; `test_pipe_to_newline_wrap` passes |
| GBS-MARQ-05 | 87-05 | Dismiss × stores hash; same announcement not re-shown until text changes | ✓ SATISFIED | `_on_banner_dismissed` adds hash to `_dismissed_announcement_hashes`; `test_dismiss_stores_hash` passes |
| GBS-MARQ-06 | 87-01/06 | Marquee fetcher reuses Phase 76 cookies-jar (no QWebEngineProfile, no parallel cookie file) | ✓ SATISFIED | `from musicstreamer import gbs_api, paths` at module scope; `test_marquee_module_reuses_phase76_auth_only` bans 6 identifiers; passes |
| GBS-MARQ-07 | 87-01/02 | 10+ committed marquee fixture samples | ✓ SATISFIED | 12 files in directory (10 data files pass `test_fixture_count_ten_or_more`) |

**13/13 requirement IDs accounted for.** GBS-THEME-06 is partially satisfied per deliberate D-04 planning relaxation.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `musicstreamer/gbs_marquee.py` | 463 | Class docstring `Signals:` block still reads `Carries a \`\`QPixmap\`\` or None.` — stale after CR-01 (IN-01 from 87-REVIEW-gap) | ℹ️ INFO | Documentation smell only; inline signal comment at line 468 is correct (`raw PNG bytes — CR-01: NO QPixmap off the GUI thread`); behavior is correct and tested |
| `musicstreamer/gbs_marquee.py` | 135 | `is_drift = (label_in_table is None) or (label_in_table != "canonical")` — first clause redundant (IN-02 from 87-REVIEW-gap) | ℹ️ INFO | Logically correct per D-12 verbatim; `None != "canonical"` makes the first clause dead. No behavioral impact |
| `musicstreamer/buffer_log.py` | 41-102 | `install_buffer_events_handler` and `install_gbs_marquee_handler` duplicate rotation-param logic | ℹ️ INFO (IN-03 from initial review) | Maintainability only; not introduced by 87-07 |
| `musicstreamer/ui_qt/now_playing_panel.py` | 942-947 | Banner not re-shown immediately on GBS rebind; waits for next poll | ℹ️ INFO (WR-03 from initial review; not changed) | UX gap: up to 60s blank banner after returning to GBS station |
| `musicstreamer/ui_qt/now_playing_panel.py` | 1129 | `set_themed_logo_override(None)` silently no-ops; cannot clear | ℹ️ INFO (WR-04 from initial review; by design per D-09) | No production call site emits None to this signal |

**No TBD / FIXME / XXX markers** found in Phase 87 modified files. No debt markers blocking phase closure.

**Pre-existing test failure noted (not caused by Phase 87, unchanged from initial verification):**
`tests/test_constants_drift.py::test_soma_nn_requirements_registered` fails because it expects `SOMA-01..17` IDs in `REQUIREMENTS.md` — these were v2.1 requirements dropped when the v2.2 `REQUIREMENTS.md` was created at milestone changeover. Phase 87 did not modify `test_constants_drift.py`.

### Human Verification Required

#### 1. Live Themed-Logo Session Override (end-to-end)

**Test:** Bind a GBS.FM station (with active Phase 76 session cookies) during an active themed-day window (next expected: Halloween 2026-10-31, or any future window that GBS serves a non-canonical `#leftmenulogo` URL). Wait for the first poll cycle (up to 60s). Observe the now-playing panel.
**Expected:** The `logo_label` in NowPlayingPanel displays the themed PNG for the session. The `cover_label` is unchanged. No libnotify toast fires. The SQLite station record is unchanged after the session. After app restart, the next GBS bind re-evaluates from scratch (no persisted override).
**Why human:** Automated tests confirm the URL resolver, drift detection, raw-bytes emission, and main-thread QPixmap decode paths all work correctly. However, they do not run a live network fetch against gbs.fm or exercise the actual Qt GUI paint path end-to-end. The Pride themed-day window (2026-06-15) was the live window where the original UAT Test 2 gap was diagnosed; UAT Test 2 was not re-run live with the corrected code before that window's expiry. The next opportunity is the next themed-day window where GBS serves a different `#leftmenulogo` URL.

#### 2. CR-01 Thread Safety on macOS or Windows

**Test:** On macOS or Windows (non-Linux, non-offscreen Qt backend), bind a GBS.FM station with a live or mocked themed day. Let the `themed_logo_ready` signal fire (with raw bytes) and `set_themed_logo_override` decode the pixmap on the main thread.
**Expected:** No crash, Qt warning, or corrupted pixmap. The themed logo renders correctly in `logo_label`.
**Why human:** Qt thread-affinity violations are silently masked by Linux XCB/offscreen backends. CR-01 is cleared in code (QPixmap import absent; worker emits bytes; slot decodes on main thread; `test_worker_emits_raw_bytes_not_qpixmap` passes). However, the original UAT Test 3 was blocked because UAT Test 2 never fired the logo-swap path on Windows. Now that the code-level fix is confirmed, a live or mocked themed-day session on macOS/Windows can complete UAT Test 3.

---

## Gaps Summary

No BLOCKER gaps. All 13 requirement IDs are implemented and tested. The phase goal is functionally achieved at the automated/code level:

- SC1 (themed logo display) is now VERIFIED at the code level. The root cause (static logo_3.png fetched instead of the dynamic CSS URL) is fixed and confirmed by the `test_pride_logo_drifts_from_baseline` regression test.
- CR-01 (QPixmap on worker thread) is CLEARED: the QPixmap import is absent from `gbs_marquee.py`; the worker emits raw bytes; the main-thread slot decodes; the test suite confirms.
- WR-01 and WR-02 (87-REVIEW-gap warnings) are FIXED with regression tests.
- The 46-test suite passes 46/46.

The `human_needed` status reflects 2 remaining items that cannot be verified programmatically: the live end-to-end logo swap on a future themed-day window, and CR-01 cross-platform confirmation on macOS/Windows. These are quality-assurance items for the next live themed-day window, not blockers to the phase goal assessment.

GBS-THEME-06's literal "3+/5+" hash count remains deliberately relaxed per D-04; the follow-up todo tracks accretion at the next themed-day window (Halloween 2026-10-31).

---

_Verified: 2026-06-15T14:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — after 87-07 gap-closure + 87-REVIEW-gap fixes_
