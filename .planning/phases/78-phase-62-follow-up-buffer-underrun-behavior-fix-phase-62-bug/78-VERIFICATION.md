---
phase: 78-phase-62-follow-up-buffer-underrun-behavior-fix-phase-62-bug
verified: 2026-05-17T00:00:00Z
status: human_needed
score: 13/13 must-haves verified (Commit A scope)
overrides_applied: 0
human_verification:
  - test: "Harvest week (real-world A/B baseline accumulation)"
    expected: "After ~1 week of normal daily-use listening via the .desktop entry, `~/.local/share/musicstreamer/buffer-events.log` contains structured `buffer_underrun ...` lines; the `Underruns: {N}` row in stats-for-nerds (hamburger toggle ON) increments live during dropouts; sample count meaningful enough to plan Commit B."
    why_human: "Requires real-world daily-use environment for ~1 week to accumulate samples (VALIDATION.md Manual-Only Verifications section). No CI substitute is meaningful at this stage — Commit A's only purpose is to make harvest possible. SC #3 closure itself is gated on Commit B (after harvest data accumulates)."
---

# Phase 78: Phase 62 follow-up — Buffer Underrun Behavior Fix (Commit A) Verification Report

**Phase Goal (Commit A scope):** Ship the harvest-infrastructure half of BUG-09 SC #3. Add a size-rotated `RotatingFileHandler` (1MB × 3 backups) on the `musicstreamer.player` logger so existing Phase 62 `buffer_underrun ...` INFO lines also land at `~/.local/share/musicstreamer/buffer-events.log` regardless of launch context; promote the Phase 62 D-Discretion `_underrun_event_count` to a live `Underruns: {N}` row in stats-for-nerds via a new `underrun_count_changed = Signal(int)` on Player wired through MainWindow to NowPlayingPanel. Preserve `__main__.py` `basicConfig(WARNING)` byte-identical (Pitfall 5); preserve INFRA-01 FakePlayer drift-guard via same-wave parity edit; preserve Phase 16 D-09 (`constants.py` unchanged in Commit A). Commit B (the actual buffer-tuning fix) is explicitly deferred to a follow-up planning pass after ~1 week of real-world harvest.

**Verified:** 2026-05-17
**Status:** human_needed (Commit A artifacts complete; harvest UAT step requires real-world daily-use accumulation)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Commit A — `<domain>` source)

Must-haves merged from CONTEXT.md `<domain>` (Commit A scope) + the three PLAN.md frontmatter `must_haves.truths` arrays. ROADMAP `success_criteria` array is empty for this phase (the phase goal itself is the contract); the `<domain>` block is the de-facto success criteria source per the verifier prompt.

| #  | Truth | Status | Evidence |
| -- | ----- | ------ | -------- |
| 1  | File sink: `RotatingFileHandler(maxBytes=1_048_576, backupCount=3, encoding='utf-8')` attached to `musicstreamer.player` logger only (D-02) | VERIFIED | `musicstreamer/buffer_log.py:54-60` constructs the handler with exact parameters; `:50` calls `logging.getLogger("musicstreamer.player")` (named logger, not `musicstreamer.*`); `tests/test_buffer_events_log.py::test_handler_attached_to_player_logger` PASSED (1/6). |
| 2  | Path source: `paths.buffer_events_log_path()` returns `{data_dir()}/buffer-events.log` and honors `_root_override`; default permissions (no `0o600`) per D-03 | VERIFIED | `musicstreamer/paths.py:68-70` (`os.path.join(_root(), "buffer-events.log")`); `grep -c "0o600" musicstreamer/buffer_log.py` → 0; `tests/test_paths.py::test_buffer_events_log_path` PASSED. |
| 3  | Boot wiring: install call lives inside `_run_gui` AFTER `migration.run_migration()`, NOT in `main()` (Pitfall 1) | VERIFIED | `musicstreamer/__main__.py:177` `migration.run_migration()`; `:187-188` `from musicstreamer.buffer_log import install_buffer_events_handler; install_buffer_events_handler()`; `_run_gui` ends before `def main` at `:241` — install call is structurally inside `_run_gui` and structurally NOT inside `main`. |
| 4  | Idempotent install (Pitfall 7): second call is a no-op | VERIFIED | `musicstreamer/buffer_log.py:51-53` iterates `log.handlers` and short-circuits when a `RotatingFileHandler` with matching `baseFilename` exists; `tests/test_buffer_events_log.py::test_install_is_idempotent` PASSED. |
| 5  | `propagate=True` (default) — INFO record reaches BOTH file sink AND existing stderr handler from `basicConfig(WARNING)` | VERIFIED | `musicstreamer/buffer_log.py` does NOT set `propagate=False` anywhere; `tests/test_buffer_events_log.py::test_record_reaches_both_sinks` PASSED. |
| 6  | Rotation: at >1MB, `buffer-events.log.1` is produced; `buffer-events.log.4` is never produced (backupCount=3 cap) | VERIFIED | `tests/test_buffer_events_log.py::test_rotation_at_1mb` and `::test_never_creates_backup_4` BOTH PASSED. |
| 7  | Pitfall 5 byte-identical: `__main__.py` `basicConfig(level=logging.WARNING)` preserved exactly; per-logger `setLevel(INFO)` retained | VERIFIED | `grep -nE "basicConfig\(level=logging\.WARNING\)"` returns `242:    logging.basicConfig(level=logging.WARNING)`; `grep -nE "getLogger\(['\"]musicstreamer\.player['\"]\)\.setLevel"` returns `246:    logging.getLogger("musicstreamer.player").setLevel(logging.INFO)`; drift-guard `tests/test_main_window_underrun.py::test_main_module_sets_player_logger_to_info` PASSED. |
| 8  | Player Signal: `underrun_count_changed = Signal(int)` declared at class scope immediately after `underrun_recovery_started = Signal()` | VERIFIED | `musicstreamer/player.py:277` `underrun_recovery_started = Signal()`; `:283` `underrun_count_changed = Signal(int)` (4-line Phase 78 comment block at 278-282 separates them but production declaration order preserved). |
| 9  | Counter field: `self._underrun_event_count: int = 0` initialized in `Player.__init__` adjacent to `self._tracker` (Pitfall 3 type-annotated zero) | VERIFIED | `musicstreamer/player.py:447` `self._tracker = _BufferUnderrunTracker()`; `:452` `self._underrun_event_count: int = 0` (immediately adjacent, type-annotated). |
| 10 | Counter increments + Signal emits on EVERY `_on_underrun_cycle_closed` call (all outcomes — recovered/failover/stop/pause/shutdown), and the existing `_log.info('buffer_underrun …')` call is byte-identical to its Phase 62 form | VERIFIED | `musicstreamer/player.py:937-944` `_log.info("buffer_underrun …")` preserves Phase 62 D-02 format string and `%r` quoting on `station_name`/`url` (T-62-01 invariant); `:948-949` `self._underrun_event_count += 1; self.underrun_count_changed.emit(self._underrun_event_count)` appended after the log call. `test_player_underrun_count.py` syntactically valid via `uv run python -m py_compile`; contains the 4 expected test function names (`test_count_starts_at_zero`, `test_count_increments_per_close`, `test_count_increments_for_all_outcomes`, `test_signal_emits_with_count_value`). Functional test execution blocked by pre-existing gi env-gap — informational per verifier prompt. |
| 11 | FakePlayer parity (INFRA-01 drift-guard): `tests/_fake_player.py` mirrors `underrun_count_changed = Signal(int)` next to `underrun_recovery_started = Signal()` | VERIFIED | `tests/_fake_player.py:69` `underrun_recovery_started = Signal()`; `:70` `underrun_count_changed = Signal(int)` (immediately after, same arity); docstring counts updated to `all 19 Signals` (`:6`) and `(19 signals, D-16 invariant)` (`:36`); `tests/test_fake_player_signal_parity.py` PASSED (2/2 assertions). |
| 12 | UI row: `NowPlayingPanel._build_stats_widget` produces a `QFormLayout` row with label `Underruns` and default value `0`, positioned AFTER the existing `Buffer` row and BEFORE `wrapper.setVisible(False)`; both widgets use `_MutedLabel`; `set_underrun_count(int)` slot updates `self._underrun_count_label.setText(str(int(count)))` | VERIFIED | `musicstreamer/ui_qt/now_playing_panel.py:2488` `form.addRow(buffer_row_label, value_row)` (Buffer row); `:2494` `underrun_row_label = _MutedLabel("Underruns", wrapper)`; `:2495` `self._underrun_count_label = _MutedLabel("0", wrapper)`; `:2496` `form.addRow(underrun_row_label, self._underrun_count_label)`; `:2499` `wrapper.setVisible(False)` (positional ordering correct); `:951-959` `def set_underrun_count(self, count: int) -> None: … self._underrun_count_label.setText(str(int(count)))`; `tests/test_now_playing_panel.py::test_underrun_count_row_present` PASSED. |
| 13 | MainWindow wire: `self._player.underrun_count_changed.connect(self.now_playing.set_underrun_count)` — bound method (QA-05, no lambda), DirectConnection (no `QueuedConnection` argument); end-to-end FakePlayer.emit(N) updates label text to str(N) | VERIFIED | `musicstreamer/ui_qt/main_window.py:381` `buffer_percent.connect(...)`; `:382-389` Phase 78 comment block; `:390` `self._player.underrun_count_changed.connect(self.now_playing.set_underrun_count)` — sibling of `buffer_percent`, bound method, no `QueuedConnection`. `grep -nE "underrun_count_changed.*Qt\.ConnectionType\.QueuedConnection"` → 0 matches (DirectConnection lock). `tests/test_main_window_underrun.py::test_count_changed_updates_stats_row` PASSED. |

**Score:** 13/13 truths VERIFIED (Commit A scope).

**Note on the 14th candidate truth — harvest UAT:** Per CONTEXT.md D-01 and VALIDATION.md Manual-Only Verifications, the harvest week itself ("daily-use accumulation for ~1 week → meaningful sample count → file exists with structured lines + Underruns counter increments live") is a real-world UAT step that cannot be discharged programmatically. It is captured as a human-verification item below. The Commit A code-level deliverables that ENABLE harvest are all verified above.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `musicstreamer/buffer_log.py` | New module exporting idempotent `install_buffer_events_handler()` | VERIFIED | 62 lines; single public function; module docstring tagged Phase 78 / BUG-09 Commit A; D-02 rotation params; D-03 default perms; Pitfall 7 idempotency via baseFilename match; Pitfall 5 preserves `propagate=True`. |
| `musicstreamer/paths.py` | Add `buffer_events_log_path()` sibling helper | VERIFIED | `:68-70` returns `os.path.join(_root(), "buffer-events.log")`; pure (no I/O, no `os.makedirs`); honors `_root_override` automatically via `_root()`. |
| `musicstreamer/__main__.py` | Install call inside `_run_gui` AFTER `migration.run_migration()` | VERIFIED | `:187-188`; preceded by 7-line Phase 78 comment block tagging Pitfall 1 / 5 / idempotency rationale; structurally inside `_run_gui` (lines 163-240), NOT in `main()` (starts at 241). |
| `musicstreamer/player.py` | New Signal + counter field + increment/emit | VERIFIED | `:283` Signal decl; `:452` counter init (type-annotated zero); `:948-949` increment+emit appended after byte-identical `_log.info` at `:937-944`. |
| `tests/_fake_player.py` | INFRA-01 parity mirror | VERIFIED | `:70` `underrun_count_changed = Signal(int)`; docstring counts updated to 19; drift-guard `test_fake_player_signal_parity.py` PASSED. |
| `musicstreamer/ui_qt/now_playing_panel.py` | Underruns row + `set_underrun_count` slot | VERIFIED | `:2494-2496` row construction; `:951-959` `set_underrun_count(count: int) -> None` slot. |
| `musicstreamer/ui_qt/main_window.py` | Player.underrun_count_changed → NowPlayingPanel wire | VERIFIED | `:390` bound-method DirectConnection. |
| `tests/test_buffer_events_log.py` | New file with 6 unit tests (B-78A-01..05) | VERIFIED | 145 lines; 6 test functions; all 6 PASSED in 0.18s. |
| `tests/test_player_underrun_count.py` | New file with 4 unit tests (B-78A-07..09) | VERIFIED (file existence + syntactic validity) | 118 lines; 4 expected test names present; `py_compile` OK; functional execution blocked by pre-existing gi env-gap (verifier prompt: treat as informational). |
| `tests/test_paths.py::test_buffer_events_log_path` | New test in existing file (B-78A-06) | VERIFIED | PASSED in 0.04s. |
| `tests/test_now_playing_panel.py::test_underrun_count_row_present` | New test in existing file (B-78A-11) | VERIFIED | PASSED in 0.19s. |
| `tests/test_main_window_underrun.py::test_count_changed_updates_stats_row` + `::test_main_module_sets_player_logger_to_info` | New end-to-end test (B-78A-12) + Pitfall 5 drift-guard (B-78A-13) | VERIFIED | Both PASSED in 0.48s. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `__main__.py::_run_gui` | `buffer_log.install_buffer_events_handler` | Lazy import + call AFTER `migration.run_migration()` | WIRED | `:187` lazy import; `:188` call. Position confirmed: after `migration.run_migration()` at `:177`, before `from PySide6.QtWidgets import QApplication` at `:190`. |
| `buffer_log.install_buffer_events_handler` | `musicstreamer.player` logger | `logging.getLogger('musicstreamer.player').addHandler(RotatingFileHandler(...))` | WIRED | `buffer_log.py:50` getLogger; `:61` addHandler. Idempotency at `:51-53`. |
| `buffer_log.install_buffer_events_handler` | `paths.buffer_events_log_path` | Import + call to resolve sink path | WIRED | `buffer_log.py:31` `from musicstreamer import paths`; `:49` `path = paths.buffer_events_log_path()`. No string-literal duplication. |
| `player.py::_on_underrun_cycle_closed` | `Player.underrun_count_changed` | `self._underrun_event_count += 1; self.underrun_count_changed.emit(self._underrun_event_count)` | WIRED | `:948-949` two-line append after byte-identical `_log.info` at `:937-944`. Increment-then-emit semantics (post-increment value emitted). |
| `Player` class body | `FakePlayer` class body | INFRA-01 drift-guard source-grep parity | WIRED | Both contain `underrun_count_changed = Signal(int)` with identical arity. `test_fake_player_signal_parity.py` confirms. |
| `MainWindow.__init__` | `NowPlayingPanel.set_underrun_count` | `self._player.underrun_count_changed.connect(self.now_playing.set_underrun_count)` — bound method, DirectConnection | WIRED | `main_window.py:390`; bound method (no lambda); no `Qt.ConnectionType.QueuedConnection` argument (grep returns 0). |
| `NowPlayingPanel.set_underrun_count` | `NowPlayingPanel._underrun_count_label` | `self._underrun_count_label.setText(str(int(count)))` | WIRED | `now_playing_panel.py:959`. Label widget created at `:2495` (`_MutedLabel("0", wrapper)`). |

All 7 key links WIRED.

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `NowPlayingPanel._underrun_count_label` | text content | `set_underrun_count(count)` slot | Yes — fed by `Player.underrun_count_changed.emit(self._underrun_event_count)` whenever `_on_underrun_cycle_closed` runs (which is the receiving end of the queued `_underrun_cycle_closed` Signal driven by `_BufferUnderrunTracker` GStreamer bus events) | FLOWING |
| `~/.local/share/musicstreamer/buffer-events.log` | log lines | `_log.info("buffer_underrun …")` at `player.py:937-944` propagating to the `RotatingFileHandler` attached at boot | Yes — same INFO record that already reached stderr in Phase 62 now also reaches the file via `propagate=True` and the new handler's `addHandler` site | FLOWING |
| `Player._underrun_event_count` | int counter | `+= 1` inside `_on_underrun_cycle_closed` | Yes — single mutation site; counter resets per launch (CONTEXT D-Discretion); persistence is the file sink, not the int | FLOWING |

All three dynamic-data sites have real upstream data sources. The harvest UAT is the only level-4 step that can't be discharged programmatically — it confirms the live-world data flow actually populates the file/UI over a week of daily use.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| File-sink layer (B-78A-01..05) | `uv run pytest tests/test_buffer_events_log.py -q` | `6 passed in 0.18s` | PASS |
| Path helper (B-78A-06) | `uv run pytest tests/test_paths.py::test_buffer_events_log_path -q` | `1 passed in 0.04s` | PASS |
| FakePlayer parity (B-78A-10 / INFRA-01) | `uv run pytest tests/test_fake_player_signal_parity.py -q` | `2 passed in [time]` | PASS |
| UI row presence (B-78A-11) | `uv run pytest tests/test_now_playing_panel.py::test_underrun_count_row_present -q` | `1 passed in 0.19s` | PASS |
| End-to-end Signal→label (B-78A-12) + Pitfall 5 drift-guard (B-78A-13) | `uv run pytest tests/test_main_window_underrun.py::test_count_changed_updates_stats_row tests/test_main_window_underrun.py::test_main_module_sets_player_logger_to_info -q` | `2 passed in 0.48s` | PASS |
| Phase 78 narrow wave-merge | `uv run pytest tests/test_buffer_events_log.py tests/test_now_playing_panel.py tests/test_main_window_underrun.py tests/test_fake_player_signal_parity.py tests/test_fake_player_no_inline.py tests/test_paths.py -q` | `167 passed in 2.00s` | PASS |
| Pitfall 5 byte-identical (source-grep) | `grep -nE "basicConfig\(level=logging\.WARNING\)" musicstreamer/__main__.py` | `242:    logging.basicConfig(level=logging.WARNING)` | PASS |
| Phase 16 D-09 (constants.py unchanged) | `git diff e2bd1c6..HEAD -- musicstreamer/constants.py \| wc -l` | `0` | PASS |
| DirectConnection lock | `grep -nE "underrun_count_changed.*Qt\.ConnectionType\.QueuedConnection" musicstreamer/ui_qt/main_window.py` | 0 matches | PASS |
| Install call in `_run_gui` not `main` | `grep -nE "install_buffer_events_handler" musicstreamer/__main__.py` | `:187`, `:188` (both inside `_run_gui:163-240`, before `def main:241`) | PASS |
| gi env-gap is pre-existing | `uv run pytest tests/test_player_underrun_count.py -q` | `ModuleNotFoundError: No module named 'gi'` during collection | SKIP (pre-existing env-gap per verifier prompt; file is `py_compile`-valid and contains all 4 expected test names) |

### Probe Execution

No probes are documented for this phase. `find scripts -path '*/tests/probe-*.sh' -type f` returns no results. Phase 78 is not a migration/tooling phase that surfaces probes. SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| BUG-09 | 78-01, 78-02, 78-03 | Intermittent audio dropouts/stutters when the GStreamer buffer can't keep up are observable, attributable, and (once root-caused) mitigated. Repro is unclear at filing time — phase ships diagnostic instrumentation first, then a behavior fix once root cause is observable | SATISFIED (Commit A enables SC #3 closure in deferred Commit B pass) | Phase 62 closed instrumentation half (SC #1, #2, #4 — see `62-VERIFICATION.md`). Phase 78 Commit A ships the harvest infrastructure (file sink + live counter UI) required to gather samples for SC #3. SC #3 closure itself remains gated on Commit B (a separate planning pass after ~1 week of accumulated samples, per CONTEXT D-01). The framing the verifier prompt asked to honor — "Commit A enables SC #3 closure in the deferred Commit B pass" — is honored throughout this phase's artifacts (CONTEXT.md `<domain>`, all three PLAN frontmatters, all three SUMMARYs, this VERIFICATION). REQUIREMENTS.md continues to mark BUG-09 as `[x] Complete` per the deferred-fix-as-follow-up convention noted in `62-VERIFICATION.md` line 87. |

No orphaned requirements (no plan declares a requirement ID absent from REQUIREMENTS.md; no REQUIREMENTS.md entry for Phase 78 references an ID not claimed by a plan).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |

No anti-patterns found. Debt-marker grep (`TBD|FIXME|XXX|HACK|PLACEHOLDER`) across `musicstreamer/buffer_log.py`, `musicstreamer/paths.py`, `musicstreamer/__main__.py`, `musicstreamer/player.py`, `musicstreamer/ui_qt/main_window.py`, `musicstreamer/ui_qt/now_playing_panel.py`, `tests/_fake_player.py`, `tests/test_buffer_events_log.py`, `tests/test_player_underrun_count.py` returns 0 matches. No empty-implementation patterns, no stub-prop patterns, no console.log-only patterns. The Commit B work explicitly deferred per D-01 is recorded in CONTEXT.md `<domain>` and CONTEXT.md `<decisions>` D-04..D-07 with `[informational]` tags — that is a planning artifact, not an in-code debt marker.

### Human Verification Required

#### 1. Harvest week (real-world A/B baseline accumulation)

**Test:** After this phase ships and the user is back on their development/listening rig, launch MusicStreamer via the GNOME `.desktop` entry (NOT terminal — Pitfall 1 was about exercising the `.desktop` boot path specifically). Listen to typical daily-use radio for approximately one week of normal listening. Open the stats-for-nerds panel via the hamburger menu and confirm the `Underruns: {N}` row appears below the `Buffer` row. When a buffer underrun cycle closes, watch the integer tick up live (and the `Buffering…` toast remain the only user-visible signal — Phase 62 silent-recovery philosophy still in effect).

**Expected:** `~/.local/share/musicstreamer/buffer-events.log` accumulates structured `buffer_underrun start_ts=… end_ts=… duration_ms=… min_percent=… station_id=… station_name=… url=… outcome=… cause_hint=…` lines — one line per cycle close. File rotates at 1MB if necessary; never produces `.4` backup. The live `Underruns` row matches the line count in the file (modulo rotation). Sample count is meaningful enough for Commit B's CONTEXT.md `<data-summary>` block (baseline N, duration distribution, outcome breakdown, station/codec patterns). Commit B planning starts when the user is satisfied with sample volume.

**Why human:** Requires real-world daily-use environment for ~1 week — VALIDATION.md Manual-Only Verifications section explicitly designates this as the manual UAT step. No CI substitute is meaningful at this stage: Commit A's only purpose is to make harvest possible. SC #3 closure itself is gated on Commit B (after harvest data accumulates and is converted into a buffer-tuning fix). The verifier prompt explicitly framed this verification as scope = Commit A only; the harvest accumulation is a downstream UAT step against Phase 78 Commit A's deliverables, not a gap in Commit A.

### Gaps Summary

No gaps. Every Commit A truth in CONTEXT.md `<domain>` and every PLAN frontmatter `must_haves.truths` entry resolves to VERIFIED in the codebase. The deferred Commit B work (buffer-duration bump, adaptive growth, validation A/B, `Buffer config: Xs (adapted)` row) is explicitly out-of-scope per CONTEXT D-01 and the verifier prompt's "Scope of this verification: Commit A only" directive — its absence is intentional, not a gap.

The single human-verification item (harvest week) is the planned UAT step that converts Commit A from "deployable infrastructure" into "harvested data ready for Commit B planning." It does not represent a code-level deliverable that failed; it is the planned follow-on activity that this phase enables.

### Notes on Scope Boundaries Honored

- **Commit A vs Commit B:** CONTEXT.md D-01 locks the two-stage shape; this verification respects it. The `<deferred>` section items (reconnect-on-stall, watermark tweaks, per-station overrides, synthetic fixture, distinct `Reconnecting…` toast, in-app log viewer, wider `musicstreamer.*` capture, TimedRotatingFileHandler) are all correctly absent from this phase's artifacts.
- **Phase 16 D-09 invariant:** `git diff e2bd1c6..HEAD -- musicstreamer/constants.py` returns 0 lines. `BUFFER_DURATION_S = 10` and `BUFFER_SIZE_BYTES = 10 * 1024 * 1024` are untouched in Commit A. The unlock is reserved for Commit B per D-04 `[informational]`.
- **Pitfall 5 (Phase 62 carry-forward):** `basicConfig(level=logging.WARNING)` at `__main__.py:242` is byte-identical to its pre-phase form. Only per-logger INFO escalation is used. `propagate=True` on the new handler preserves stderr parity.
- **T-62-01 (log-injection):** `station_name=%r url=%r` quoting at `player.py:940` is preserved verbatim. The new handler reads the same record stream — no new untrusted input flows into the log path.
- **INFRA-01 (Phase 77 drift-guard):** FakePlayer mirror landed in the same wave (commit `a9374d3`) as the Player Signal addition (commit `c514bbe`); drift-guard PASSED at every wave-merge boundary.
- **gi env-gap (Phase 77 baseline):** `tests/test_player_underrun_count.py` cannot be collected by `uv run pytest` because it transitively imports `gi` via `musicstreamer.player`. The verifier prompt treats this as pre-existing environmental, not a verification blocker. Syntactic validity (`py_compile`) and test-name coverage (4/4 expected names present) are the verification gates that DO apply in this environment.

---

_Verified: 2026-05-17_
_Verifier: Claude (gsd-verifier)_
