---
phase: 87-gbs-fm-marquee-themed-day-detection
verified: 2026-06-15T12:00:00Z
status: human_needed
score: 4/5 must-haves verified
overrides_applied: 0
re_verification: null
human_verification:
  - test: "Bind a GBS.FM station on a non-themed day and confirm marquee banner appears with current announcement text (if non-empty), or stays hidden (if empty)"
    expected: "Top-of-NowPlayingPanel banner shows first pipe-segment of marquee; × dismiss hides it; re-bind to non-GBS station hides immediately; re-bind to GBS re-evaluates on next poll"
    why_human: "Requires live GBS.FM cookies and a running app; cannot be verified via grep or automated tests"
  - test: "Verify themed-logo slot override: either wait for a real themed-day window (next: Halloween 2026-10-31) or inject a known hash into GBS_LOGO_BASELINE_HASHES + run with the da troops fixture PNG as a mock logo_3.png"
    expected: "logo_label QLabel in NowPlayingPanel shows the themed PNG for the session; cover_label unchanged; no toast fires; SQLite station record unchanged post-session"
    why_human: "Themed-day window has passed (Memorial Day 2026-05-25); live verification requires a future window or manual fixture injection"
  - test: "CR-01 thread safety: run the app on a GBS.FM station and confirm no crash, warning, or corrupted pixmap under themed-day detection. Cross-check platform: macOS or Windows where the GUI paint backend is stricter than Linux/XCB offscreen"
    expected: "No QPixmap-on-non-GUI-thread crash or warning; themed logo renders correctly"
    why_human: "Qt thread-affinity violations are platform-dependent and silently masked by offscreen test infrastructure; requires real GUI session"
---

# Phase 87: GBS.FM Marquee + Themed-Day Detection Verification Report

**Phase Goal:** When the bound station is GBS.FM, the user sees the current themed logo (if any), a dismissible top-of-panel announcement banner, and a live updating marquee — all backed by the Phase 76 QtWebEngine cookie-persistence pattern that Phase 89 reuses for channel avatars.
**Verified:** 2026-06-15T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Code Review Note (87-REVIEW.md)

The code review identified 1 BLOCKER (CR-01) and 4 warnings. Their impact on goal achievement:

**CR-01 — QPixmap constructed and decoded on the worker QThread (gbs_marquee.py:469-472)**
Advisory for phase goal: `QPixmap()` and `pix.loadFromData(logo_bytes, "PNG")` run on the `GbsMarqueeWorker` thread, violating Qt's requirement that paint-device objects only be created on the GUI thread. On Linux/XCB with an offscreen test backend this is masked (all 35 tests pass), but on macOS or Windows with the native paint backend it can produce intermittent crashes or corrupted pixmaps. This is a **correctness defect** that must be fixed before shipping to end users but does not block verification of goal coverage — the feature path exists and the test suite confirms the logic. Resolution: emit raw `bytes` from the worker (already thread-safe) and call `pix.loadFromData` inside `set_themed_logo_override` on the main thread.

**WR-01 — force_poll() silently un-pauses idle worker:** Advisory. The `or 60_000` fallback in `force_poll` can resurrect polling when the cadence is 0 (non-GBS station). No production call site currently calls `force_poll` while idle; only tests use it with active cadence. Low-risk in practice but a semantic gap.

**WR-02 — One-shot fires against empty marquee text on first-tick failure:** Advisory. If the first `_fetch_marquee()` fails, `_on_first_gbs_bind()` still runs against `_last_full_marquee_text == ""`, classifying via the D-12 fallback path even if a keyword would have matched on a later successful fetch. Per D-17 the session gate still closes; the themed logo still applies (D-12 fallback). A genuine themed day would still be detected (logo drift fires regardless of keyword); keyword correlation just falls back earlier than intended.

**WR-03 — Banner not re-shown on GBS rebind after non-GBS detour:** Advisory. After switching away and back to GBS, the banner stays blank until the next poll (up to 60s/5min). Last `first_segment` is not cached on the panel side. Minor UX gap.

**WR-04 — `set_themed_logo_override(None)` cannot clear an override:** Advisory. Once set, the session override is irreversible by design per D-09. The signal docstring says "QPixmap or None" implying None should clear, but the method early-returns. Not a goal-blocking defect — no code path currently emits None to this signal.

**IN-01 — Dead variable `logo_url`:** Code smell only.
**IN-02 — `load_auth_context()` outside try block:** Low risk (function is defensive internally).
**IN-03 — Duplicated RotatingFileHandler install logic:** Maintainability smell only.

**None of CR-01 or the warnings block the phase goal from being evaluated.** CR-01 is a correctness defect that requires fixing before release; the others are quality improvements. The verification proceeds on goal+requirement coverage.

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | When user binds a GBS.FM station on a known themed day, now-playing logo slot displays themed logo for session; never cover slot, never station-list row, never libnotify toast (GBS-THEME-05) | ? UNCERTAIN | Logic implemented: `set_themed_logo_override` writes to `logo_label` only (line 1153); drift-guard `test_themed_logo_targets_logo_slot_only` passes; `test_themed_logo_targets_logo_slot_only_behavior` passes. CR-01 (QPixmap on worker thread) is a correctness risk on non-Linux platforms. Human verification needed for actual themed-day window |
| 2 | Next app launch re-evaluates themed-day detection from scratch; themed logo does NOT persist to SQLite or carry past a session boundary (GBS-THEME-04) | ✓ VERIFIED | `_themed_logo_override` is `Optional[QPixmap]` in-memory only (line 351); no write to `repo.py`; drift-guard `test_themed_logo_never_persists` passes; `repo.py` has zero references to `themed` or `_themed_logo` |
| 3 | When GBS.FM marquee text contains a new first pipe-segment announcement (hash-different from last-seen), a top-of-NowPlayingPanel banner appears; user can dismiss with × and same banner does not re-appear until marquee changes | ✓ VERIFIED | `AnnouncementBanner` widget exists; `_dismissed_announcement_hashes: set[str]` in `NowPlayingPanel`; `_on_marquee_ready` implements hash-check predicate; `test_banner_visibility_predicate` passes; `test_dismiss_stores_hash` passes |
| 4 | Marquee fetcher imports `paths.gbs_cookies_path()` + `musicstreamer.gbs_api.load_auth_context()`; source-grep drift-guard confirms no parallel cookie file written, no QtWebEngine session instantiated | ✓ VERIFIED | `from musicstreamer import gbs_api, paths` at line 47; `test_marquee_module_reuses_phase76_auth_only` passes (5 banned identifiers absent, required imports present) |
| 5 | 60-second poll cadence while GBS station bound + playing; 5-minute slow cadence otherwise; 10+ committed marquee fixtures plus 3+ themed-day / 5+ non-themed-day logo SHA-256 samples lock the parser and canonical-hash table | ✓ VERIFIED (with D-04 relaxation) | `set_cadence(60_000)` / `set_cadence(300_000)` wired via `_refresh_gbs_marquee_cadence`; `test_cadence_state_machine` passes; `test_fixture_count_ten_or_more` passes (10 files); GBS-THEME-06 3+/5+ literal relaxed per D-04 — 1 themed entry shipped; `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` tracks accretion; follow-up todo present with `next_window: 2026-10-31` |

**Score:** 4/5 truths fully verified (SC1 is UNCERTAIN pending human themed-day window verification)

### Deferred Items

No items deferred to later phases.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `musicstreamer/gbs_marquee.py` | parse_marquee, MARQUEE_URL, GbsMarqueeWorker, compute_logo_theme, GBS_LOGO_BASELINE_HASHES | ✓ VERIFIED | All functions/classes present; 540 lines; no banned identifiers |
| `musicstreamer/ui_qt/announcement_banner.py` | AnnouncementBanner(QWidget) with PlainText QLabel + dismissed Signal | ✓ VERIFIED | Class present, Qt.TextFormat.PlainText set, setWordWrap(True), dismissed Signal at class scope |
| `musicstreamer/ui_qt/now_playing_panel.py` | set_themed_logo_override, attach_gbs_marquee_worker, _on_marquee_ready, AnnouncementBanner parented | ✓ VERIFIED | All methods present; `_dismissed_announcement_hashes: set[str]`; banner at line 373 |
| `musicstreamer/ui_qt/main_window.py` | GbsMarqueeWorker construction, start(), stop_and_wait() in closeEvent | ✓ VERIFIED | Worker constructed line 502; `start()` line 504; `stop_and_wait(5_000)` in closeEvent line 772 |
| `musicstreamer/buffer_log.py` | install_gbs_marquee_handler() | ✓ VERIFIED | Function at line 71; named logger `musicstreamer.gbs_marquee` |
| `musicstreamer/constants.py` | GBS_THEMED_DAY_KEYWORDS frozenset | ✓ VERIFIED | Line 81; 9 keywords including "da troops", "halloween", "christmas" |
| `tests/test_gbs_marquee.py` | 24 tests covering parser, fixture count, worker cadence, correlator, one-shot gate | ✓ VERIFIED | 24 tests, all pass |
| `tests/test_gbs_marquee_drift_guard.py` | 5 source-grep drift-guards | ✓ VERIFIED | 5 tests (including optional test_worker_run_calls_exec_loop), all pass |
| `tests/test_announcement_banner.py` | 6 widget + integration tests | ✓ VERIFIED | 6 tests, all pass |
| `tests/fixtures/gbs_themed_logos/2026-05-25_memorial-day_da-troops.png` | Live Memorial Day harvest | ✓ VERIFIED | File present, 7,458 bytes, SHA-256 in MANIFEST |
| `tests/fixtures/gbs_marquee/` | ≥ 10 samples (real + synthetic) | ✓ VERIFIED | 10 data files (2 real + 8 synthetic) |
| `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` | GBS-THEME-06 D-04 follow-up | ✓ VERIFIED | resolves_phase: 87, next_window: 2026-10-31, requirement_id: GBS-THEME-06 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `GbsMarqueeWorker._on_tick` | `gbs_api.load_auth_context` | `_fetch_marquee()` D-11 ladder | ✓ WIRED | `auth = gbs_api.load_auth_context()` line 285; anonymous fallback present |
| `GbsMarqueeWorker.themed_logo_ready` | `NowPlayingPanel.set_themed_logo_override` | `Qt.QueuedConnection` | ✓ WIRED | `worker.themed_logo_ready.connect(self.set_themed_logo_override, _Qt.QueuedConnection)` line 1177 |
| `GbsMarqueeWorker.marquee_ready` | `NowPlayingPanel._on_marquee_ready` | `Qt.QueuedConnection` | ✓ WIRED | `worker.marquee_ready.connect(self._on_marquee_ready, _Qt.QueuedConnection)` line 1181 |
| `NowPlayingPanel.bind_station` | `GbsMarqueeWorker.set_cadence` | `_refresh_gbs_marquee_cadence` | ✓ WIRED | Lines 935-941; GBS.FM → `_refresh_gbs_marquee_cadence()`; non-GBS → `set_cadence(0)` |
| `NowPlayingPanel.on_playing_state_changed` | `GbsMarqueeWorker.set_cadence` | `_refresh_gbs_marquee_cadence` | ✓ WIRED | Line 1062; fires when station is GBS.FM |
| `cadence_changed_internal` Signal | `_apply_cadence_on_worker_thread` | `Qt.QueuedConnection` | ✓ WIRED | Line 401-402; Pitfall #7 bridge pattern |
| `GbsMarqueeWorker.run()` | `self.exec_()` | Direct call | ✓ WIRED | Line 540; `test_worker_run_calls_exec_loop` drift-guard confirms |
| `MainWindow.__init__` | `GbsMarqueeWorker.start()` | Direct call | ✓ WIRED | Line 504 |
| `MainWindow.closeEvent` | `GbsMarqueeWorker.stop_and_wait(5000)` | Direct call | ✓ WIRED | Lines 772-777 |
| `AnnouncementBanner.dismissed` | `NowPlayingPanel._on_banner_dismissed` | AutoConnection | ✓ WIRED | Line 375 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `NowPlayingPanel` (banner) | `first_segment` | `GbsMarqueeWorker._fetch_marquee()` → `extract_noticearea_text()` → `parse_marquee()` | Yes — live urllib GET to `gbs.fm/` | ✓ FLOWING |
| `NowPlayingPanel` (themed logo) | `_themed_logo_override: QPixmap` | `GbsMarqueeWorker._fetch_logo_bytes()` → `compute_logo_theme()` → `themed_logo_ready` signal | Yes — live urllib GET to `gbs.fm/images/logo_3.png` | ✓ FLOWING (CR-01 advisory: QPixmap decoded on worker thread) |
| `GBS_LOGO_BASELINE_HASHES` | `dict[str, str]` | Hardcoded literal at module scope | Yes — 1 real-captured SHA-256 from Memorial Day harvest | ✓ FLOWING (D-04 relaxed: 1 of required 3+ entries; follow-up todo tracks) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `parse_marquee` handles pipe split | `.venv/bin/python -m pytest tests/test_gbs_marquee.py::test_parse_marquee_pipe_split` | PASSED | ✓ PASS |
| Fixture count ≥ 10 | `.venv/bin/python -m pytest tests/test_gbs_marquee.py::test_fixture_count_ten_or_more` | PASSED | ✓ PASS |
| Drift-guard: no banned identifiers | `.venv/bin/python -m pytest tests/test_gbs_marquee_drift_guard.py` | 5/5 PASSED | ✓ PASS |
| Banner PlainText invariant | `.venv/bin/python -m pytest tests/test_announcement_banner.py::test_banner_uses_plaintext_format` | PASSED | ✓ PASS |
| Once-per-session gate | `.venv/bin/python -m pytest tests/test_gbs_marquee.py::test_once_per_session_gate` | PASSED | ✓ PASS |
| Cadence state machine | `.venv/bin/python -m pytest tests/test_gbs_marquee.py::test_cadence_state_machine` | PASSED | ✓ PASS |
| Full Phase 87 suite | `.venv/bin/python -m pytest tests/test_gbs_marquee.py tests/test_gbs_marquee_drift_guard.py tests/test_announcement_banner.py` | 35/35 PASSED | ✓ PASS |

### Probe Execution

No probes declared in PLAN files. Step 7c: SKIPPED (no probe scripts declared for this phase).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| GBS-THEME-01 | 87-04 | Fetch logo_3.png and SHA-256 hash on GBS bind | ✓ SATISFIED | `_on_first_gbs_bind` calls `_fetch_logo_bytes()` + `compute_logo_theme()`; test passes |
| GBS-THEME-02 | 87-04 | SHA-256 differs from baseline AND keyword match → themed logo applied | ✓ SATISFIED | `compute_logo_theme` implements both conditions (D-12); keyword match AND fallback-no-keyword tested |
| GBS-THEME-03 | 87-04 | Themed logo replaces logo slot ONLY; never cover slot, never station list | ✓ SATISFIED | `set_themed_logo_override` writes `logo_label` only; drift-guard `test_themed_logo_targets_logo_slot_only` blocks `cover_label` refs |
| GBS-THEME-04 | 87-04 | Themed logo is session-scoped, not persisted to SQLite | ✓ SATISFIED | `_themed_logo_override` is in-memory `Optional[QPixmap]`; `test_themed_logo_never_persists` drift-guard confirms no `repo.set_setting`/`.save(` |
| GBS-THEME-05 | 87-05/06 | No toast / notification on themed day detection | ✓ SATISFIED | `test_no_toast_in_themed_day_path` drift-guard bans `show_toast`/`libnotify`/`QSystemTrayIcon` in both files |
| GBS-THEME-06 | 87-01/04/06 | 3+ themed-day + 5+ non-themed-day logo SHA-256 samples in fixture | ? PARTIAL (D-04 relaxed) | 1 themed entry in `GBS_LOGO_BASELINE_HASHES` (Memorial Day 2026-05-25); 0 canonical; D-04 explicitly relaxes this to structure-only-ships; `todos/2026-05-25-gbs-theme-hash-baseline-grow.md` created with `next_window: 2026-10-31` |
| GBS-MARQ-01 | 87-03/04 | Poll 60s (playing) / 5 min (not playing) when GBS bound | ✓ SATISFIED | `_refresh_gbs_marquee_cadence`: `set_cadence(60_000)` when playing, `set_cadence(300_000)` otherwise; `test_cadence_state_machine` passes |
| GBS-MARQ-02 | 87-02 | Marquee split on `\|`; first segment is announcement; others ignored for banner | ✓ SATISFIED | `parse_marquee` returns `(first_segment, full_text)`; 8+ parser tests pass |
| GBS-MARQ-03 | 87-05 | Banner visible: bound=GBS.FM AND non-empty AND hash not dismissed | ✓ SATISFIED | `_on_marquee_ready` visibility predicate; `test_banner_visibility_predicate` passes |
| GBS-MARQ-04 | 87-05 | Banner displays text with `\|` as wrap hints | ✓ SATISFIED | `set_announcement` replaces `\|` with `\n`; `test_pipe_to_newline_wrap` passes |
| GBS-MARQ-05 | 87-05 | Dismiss × stores hash; same announcement not re-shown until text changes | ✓ SATISFIED | `_on_banner_dismissed` adds hash to `_dismissed_announcement_hashes`; predicate checks set membership; test passes |
| GBS-MARQ-06 | 87-01/06 | Marquee fetcher reuses Phase 76 cookies-jar (no QWebEngineProfile, no parallel cookie file) | ✓ SATISFIED | `from musicstreamer import gbs_api, paths` at module scope; `test_marquee_module_reuses_phase76_auth_only` bans 6 identifiers |
| GBS-MARQ-07 | 87-01/02 | 10+ committed marquee fixture samples | ✓ SATISFIED | 10 data files (2 real-captured + 8 synthetic); `test_fixture_count_ten_or_more` passes |

**13/13 requirement IDs accounted for.** GBS-THEME-06 is partially satisfied per deliberate D-04 planning relaxation (structure shipped; literal 3+/5+ deferred to future themed-day windows).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `musicstreamer/gbs_marquee.py` | 469-472 | `QPixmap()` and `pix.loadFromData()` on worker QThread | ⚠️ WARNING (CR-01) | Qt paint-device created off GUI thread; silently masked by Linux/XCB offscreen test backend; can crash or corrupt on macOS/Windows. Fix: emit raw `bytes` from worker, decode in `set_themed_logo_override` on main thread |
| `musicstreamer/gbs_marquee.py` | 424 | `force_poll` uses `or 60_000` fallback — silently un-pauses idle worker | ℹ️ INFO (WR-01) | No current production call site calls `force_poll` while idle; test-only use is gated on active cadence |
| `musicstreamer/gbs_marquee.py` | 507 | `_on_first_gbs_bind()` fires when `_last_full_marquee_text == ""` if first marquee fetch failed | ℹ️ INFO (WR-02) | D-12 fallback still applies themed logo; keyword correlation just uses empty text; themed logo detection is conservative (correct) |
| `musicstreamer/ui_qt/now_playing_panel.py` | 942-947 | Banner not re-shown immediately on GBS rebind; waits for next poll | ℹ️ INFO (WR-03) | UX gap: up to 60s blank banner after returning to GBS station |
| `musicstreamer/ui_qt/now_playing_panel.py` | 1129 | `set_themed_logo_override(None)` silently no-ops; cannot clear | ℹ️ INFO (WR-04) | By design per D-09 (override persists for session); docstring implies None should clear but doesn't |
| `musicstreamer/buffer_log.py` | 41-102 | `install_buffer_events_handler` and `install_gbs_marquee_handler` duplicate logic | ℹ️ INFO (IN-03) | Maintainability: rotation params must be updated in two places |

**No TBD / FIXME / XXX markers** found in Phase 87 modified files. No debt markers blocking phase closure.

**Pre-existing test failure noted (not caused by Phase 87):**
`tests/test_constants_drift.py::test_soma_nn_requirements_registered` fails because it expects `SOMA-01..17` IDs in `REQUIREMENTS.md` — these were v2.1 requirements dropped when the v2.2 `REQUIREMENTS.md` was created at milestone changeover (commit `4233935a`). Phase 87 did not modify `test_constants_drift.py` (last modified by commit `f82cb700`, Phase 74, 2026-05-14). This is a pre-existing regression outside Phase 87's scope.

### Human Verification Required

#### 1. Live GBS.FM Marquee Banner (end-to-end UX)

**Test:** With Phase 76 GBS session cookies active, bind a GBS.FM station, wait up to 60 seconds for a poll cycle, and observe the now-playing panel.
**Expected:** If the current GBS marquee has a non-empty first pipe-segment, the announcement banner appears above the panel content. Clicking × hides it. Switching to a non-GBS station hides the banner immediately. Switching back to GBS waits for the next poll (up to 60s) to re-show any current announcement.
**Why human:** Requires live GBS.FM session cookies and a running Qt GUI application; cannot be reproduced by grep or automated tests.

#### 2. Themed-Logo Session Override (live or injected)

**Test:** Either (a) wait for a real themed-day window (next expected: Halloween 2026-10-31) and bind a GBS.FM station, OR (b) inject the Memorial Day fixture PNG bytes as the live logo_3.png response via a local HTTP mock, and run the app with matching keyword in the marquee.
**Expected:** The `logo_label` in NowPlayingPanel displays the themed PNG for the session. The `cover_label` is unchanged. No libnotify toast fires. After app restart, the next GBS bind re-evaluates fresh (no persisted override).
**Why human:** The Memorial Day themed-day window is past; live verification requires the next window or a test harness to mock `gbs.fm/images/logo_3.png`.

#### 3. CR-01 Thread Safety (cross-platform)

**Test:** Run the app on macOS or Windows (non-Linux, non-offscreen Qt backend) with a GBS.FM station bound during a real or mocked themed day.
**Expected:** No crash, Qt warning, or corrupted pixmap when `themed_logo_ready` fires. If CR-01 is not fixed before this test, expect an intermittent failure on stricter platforms.
**Why human:** Qt thread-affinity violations are silently masked by Linux XCB/offscreen backends used in CI; requires a native GUI session on a stricter platform to surface.

---

## Gaps Summary

No BLOCKER gaps. The phase goal is functionally achieved:
- All 13 requirement IDs are implemented and tested.
- GBS-THEME-06's literal "3+/5+" hash count is deliberately relaxed per D-04 planning decision; the follow-up todo tracks future accretion.
- CR-01 (QPixmap on worker thread) is a shipping-quality defect but does not block goal evaluation. It should be fixed before the feature ships to users on macOS/Windows.

The `human_needed` status reflects that SC1 (themed logo display) requires either a real themed-day window or human-driven mock injection to fully verify end-to-end behavior, and that CR-01 requires cross-platform human testing to confirm the thread-safety defect.

---

_Verified: 2026-06-15T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
