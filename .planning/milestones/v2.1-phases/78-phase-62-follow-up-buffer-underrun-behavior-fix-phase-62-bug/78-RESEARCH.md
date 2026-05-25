# Phase 78: Phase 62 follow-up — Buffer underrun behavior fix (Commit A) - Research

**Researched:** 2026-05-17
**Domain:** Python stdlib logging (file sink) + Qt Signal wiring (UI counter) — Commit A scope only
**Confidence:** HIGH (entire scope is in-process stdlib + Qt patterns already proven in this codebase)

## Summary

This is a **two-stage phase** and this research pass covers **Commit A only** (harvest infrastructure: file sink + cycle-count UI row). Commit B (the actual buffer-tuning fix) is deferred to a second planning pass that runs ~1 week later, once enough real-world `buffer_underrun ...` log lines have accumulated to drive a data-informed decision. Per CONTEXT.md D-01, Commit B is explicitly out of scope here; only its research dependencies are named at the end.

The Commit A surface is small and entirely composed of patterns this codebase already uses:

1. **File sink** — a `logging.handlers.RotatingFileHandler(maxBytes=1_048_576, backupCount=3)` attached to the existing `musicstreamer.player` logger. The exact same handler shape is already in production at `musicstreamer/oauth_log.py:55-71` (just with different rotation parameters). Default `logger.propagate = True` means the same INFO record reaches BOTH the new file handler AND the root-logger stderr stream from `basicConfig` — grep parity is automatic.
2. **`buffer_events_log_path()` helper** in `musicstreamer/paths.py` — three lines mirroring `cookies_path()` / `gbs_cookies_path()`.
3. **`_underrun_event_count: int` + new `underrun_count_changed = Signal(int)`** on Player — increment inside the existing main-thread slot `_on_underrun_cycle_closed` at `player.py:918`. No threading hazards because the increment + emit happens on the main thread (the cross-thread marshalling already occurred via the queued `_underrun_cycle_closed` Signal at `player.py:409-411`).
4. **`Underruns: {N}` row** in `now_playing_panel.py` `_build_stats_widget` at line 2451, added via one extra `form.addRow(...)` call before `wrapper.setVisible(False)` at line 2481.
5. **Drift-guard updates** — Phase 77 INFRA-01 added a source-grep parity drift-guard (`tests/test_fake_player_signal_parity.py`) that fails the build the moment a new Signal lands on Player without a parity entry on `tests/_fake_player.py`. The planner MUST plan a parity edit to `_fake_player.py` in the same wave that adds `underrun_count_changed` to Player.

**Primary recommendation:** Wire the file handler at startup in `_run_gui` AFTER `migration.run_migration()` (line 177) where DATA_DIR is guaranteed to exist; the per-logger `setLevel(INFO)` already on line 235 in `main()` stays unchanged. Increment + emit in the existing main-thread cycle-closed slot. Add one `form.addRow` line. Update `_fake_player.py`. Done.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Buffer-event file sink (`RotatingFileHandler` attached to logger) | App boot (`__main__.py`) | Path helper (`paths.py`) | The handler is a startup-time singleton attachment, just like `logging.basicConfig`; the path string is supplied by the existing data-paths module. |
| Cycle-count state (`_underrun_event_count`) | Player (`player.py`) | — | Counter is a runtime property of the player's underrun lifecycle — same QObject that owns the cycle tracker. |
| Cycle-count Signal emission (`underrun_count_changed`) | Player → MainWindow → NowPlayingPanel | — | One-way data flow; same shape as the existing `buffer_percent` → `set_buffer_percent` chain at `main_window.py:381` + `now_playing_panel.py:946`. |
| UI row rendering (`Underruns: {N}` label) | NowPlayingPanel (`now_playing_panel.py`) | — | Lives inside `_build_stats_widget` exactly where `Buffer` progressbar row lives today; same `QFormLayout` (Phase 47.1 extensible design). |
| Counter reset on app launch | Player `__init__` | — | `self._underrun_event_count: int = 0` is set in `__init__`; no persistence (per Discretion). |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `logging` (stdlib) | Python 3.13 (in-repo runtime) | Module logger + INFO emission for `buffer_underrun` line | Already imported at `player.py:36`; `_log = logging.getLogger(__name__)` declared at `player.py:81`; no new import on player side. `[VERIFIED: source grep]` |
| `logging.handlers.RotatingFileHandler` (stdlib) | Python 3.13 | Size-rotated file sink (1MB × 3 backups, total disk cap ≤ 4MB) | Already used in this codebase at `musicstreamer/oauth_log.py:12,63` with the same API. Project-canonical pattern. `[VERIFIED: source grep]` |
| `PySide6.QtCore.Signal` | PySide6 6.x (pinned in `pyproject.toml`) | New `underrun_count_changed = Signal(int)` on Player; cross-stage forwarding to NowPlayingPanel | Same primitive as existing 18 Signals on Player (`player.py:241-282`). `[VERIFIED: source grep]` |
| `musicstreamer.paths` | (project internal) | New `buffer_events_log_path()` helper returning `~/.local/share/musicstreamer/buffer-events.log` | Existing module with 9 sibling helpers (`cookies_path`, `db_path`, etc. at `paths.py:38-95`). `[VERIFIED: source grep]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `platformdirs` | already pinned | Underlies `paths.data_dir()` → `user_data_dir("musicstreamer")` → `~/.local/share/musicstreamer` on Linux | Indirect — used via `paths._root()`. No new direct usage. `[VERIFIED: source grep]` |
| `pytest` + `qtbot` | already in test infra | Unit + UI tests for handler attachment, counter increment, row presence | Existing project test stack. `[VERIFIED: source grep]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `RotatingFileHandler(maxBytes=1MB, backupCount=3)` | `TimedRotatingFileHandler(when='D', backupCount=7)` | Rejected by CONTEXT.md D-02 — size-based gives a predictable disk cap (≤4MB total); time-based gives unpredictable disk usage if dropouts cluster. `start_ts` in each line already supports date-range analysis. |
| Bare `FileHandler(path)` (no rotation) | — | Rejected by CONTEXT.md D-02 — diagnostic file could grow unbounded over a multi-week harvest. |
| New typed Signal `underrun_count_changed = Signal(int)` | Extend existing `underrun_recovery_started` to carry count payload | Rejected by CONTEXT.md D-08 + Discretion bias — clearer to add a typed signal than overload an existing void signal. Two consumers (count UI + toast) want different gating. `[VERIFIED: CONTEXT.md]` |
| Persist `_underrun_event_count` to SQLite | Counter resets per launch | CONTEXT.md Discretion locks "resets per launch — no persistence". File sink is the persistent record. `[VERIFIED: CONTEXT.md]` |
| Wider `musicstreamer.*` capture in the file sink | Sink scoped to `musicstreamer.player` only | Rejected by CONTEXT.md D-02 — yt_import / soma_import / aa_import lines would dilute the diagnostic signal. `[VERIFIED: CONTEXT.md]` |

### Installation

No new packages. `logging.handlers.RotatingFileHandler` is stdlib; PySide6 + platformdirs are already pinned.

```bash
# No-op — entire Commit A scope is in-repo edits.
```

**Version verification:** Not applicable (no new dependencies). The Python runtime is 3.13.13 on the development machine (verified `python3 --version`); `logging.handlers.RotatingFileHandler.__init__` signature confirmed via `help()` at the same runtime — matches the project usage at `oauth_log.py:63-68`.

## Package Legitimacy Audit

Commit A installs no external packages. Audit is **not required** for this commit.

If Commit B's planning later wants to add (e.g.) a benchmarking dep or a synthetic-network fixture, run the slopcheck protocol then. For Commit A there is nothing to verify.

## Architecture Patterns

### System Architecture Diagram

```
+------------------------------+
|  Player (main thread)        |
|                              |
|  _on_underrun_cycle_closed   |   <- already runs on main thread
|  (player.py:918)             |      (queued Signal at lines 409-411
|     |                        |       has marshalled bus-loop -> main)
|     |  [NEW: increment +     |
|     |   emit]                |
|     v                        |
|  _log.info("buffer_underrun" |   <- existing emit at player.py:927-934
|     ...)                     |
|     |                        |
|     +-- propagate=True --+   |
|     |                    |   |
|  underrun_count_changed  |   |
|  .emit(N)  [NEW Signal]  |   |
+----------|---------------|---+
           |               |
           |               v
           |     +---------------------+
           |     |  logging machinery  |
           |     |                     |
           |     |  musicstreamer.player
           |     |  logger (INFO)      |
           |     |     |               |
           |     |     +-> RotatingFileHandler [NEW]
           |     |     |     -> ~/.local/share/musicstreamer/
           |     |     |        buffer-events.log
           |     |     |     -> rotates at 1MB, keeps 3 backups
           |     |     |
           |     |     +-> root logger (basicConfig WARN)
           |     |           -> stderr StreamHandler
           |     |             (unchanged from Phase 62)
           |     +---------------------+
           v
+------------------------------+
|  MainWindow (main thread)    |
|  [NEW: bound-method connect  |
|   to _on_underrun_count_     |
|   changed at __init__ next   |
|   to existing buffer_percent |
|   connection on line 381]    |
+----------|-------------------+
           v
+------------------------------+
|  NowPlayingPanel             |
|  [NEW: set_underrun_count(N) |
|   slot updates _underrun_pct |
|   _label.setText(f"{N}")]    |
|                              |
|  Renders inside              |
|  _build_stats_widget         |
|  via form.addRow(            |
|    _MutedLabel("Underruns"), |
|    underrun_value_label)     |
|  [NEW row, sits beside the   |
|  existing Buffer progress bar|
|  row at line 2478]           |
+------------------------------+
```

### Recommended Project Structure

No new files. All edits land in existing modules:

```
musicstreamer/
├── __main__.py              # +1 RotatingFileHandler attach block (~6 lines)
├── paths.py                 # +1 buffer_events_log_path() helper (~3 lines)
├── player.py                # +1 instance field, +1 Signal, +2 lines in slot
└── ui_qt/
    ├── main_window.py       # +1 .connect(...) line beside buffer_percent
    └── now_playing_panel.py # +1 set_underrun_count slot, +1 form.addRow

tests/
├── _fake_player.py                # +1 Signal mirror (drift-guard requires it)
├── test_buffer_events_log.py      # NEW — handler attachment + path tests
├── test_player_underrun_count.py  # NEW — counter increment + signal tests
└── test_main_window_underrun.py   # +1 test for new stats row presence/text
```

### Pattern 1: `RotatingFileHandler` attached to a named logger with `propagate=True`

**What:** Add a `RotatingFileHandler` to a specific named logger; default `propagate=True` means records ALSO reach the root logger's `basicConfig` stderr handler. Both sinks receive every record without explicit duplication. `[VERIFIED: live Python repl, this session]`

**When to use:** Diagnostic file sink that must coexist with existing stderr output.

**Example (mirrors `musicstreamer/oauth_log.py:55-71`):**

```python
# In __main__.py inside _run_gui, AFTER migration.run_migration() so DATA_DIR exists.
# Source: musicstreamer/oauth_log.py:55-71 (project-canonical pattern).
from logging.handlers import RotatingFileHandler
import logging
from musicstreamer import paths

_player_log = logging.getLogger("musicstreamer.player")
# Per-logger INFO already set in main() at __main__.py:235 (Pitfall 5 — DO NOT
# touch the global basicConfig WARNING level at line 231).
_buffer_handler = RotatingFileHandler(
    paths.buffer_events_log_path(),
    maxBytes=1_048_576,    # 1 MB per CONTEXT.md D-02
    backupCount=3,         # 3 backups per CONTEXT.md D-02 (total ≤4MB)
    encoding="utf-8",
)
_buffer_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
_player_log.addHandler(_buffer_handler)
```

**Note on formatter choice:** The existing stderr line is `INFO:musicstreamer.player:buffer_underrun ...` (basicConfig default fmt). The file line will be `<asctime> buffer_underrun ...` if you set the formatter as above, or just `buffer_underrun ...` if you omit the formatter (default `Formatter()` writes `%(message)s` alone). CONTEXT.md `<specifics>` says "byte-for-byte the same as the existing stderr line ... Grep parity with stderr captures is the goal" — but stderr already prepends `INFO:musicstreamer.player:`. The structured payload `buffer_underrun start_ts=... end_ts=... ...` is identical in both sinks regardless of formatter; only the prefix differs. **Recommendation:** include `%(asctime)s` in the file formatter so each line is independently date-stampable for the harvest analysis (the in-line `start_ts=%.3f` is also there, redundantly, which is fine). Planner-locked choice.

### Pattern 2: New typed `Signal(int)` on Player, main-thread → main-thread

**What:** Add a `Signal(int)` at class scope on Player; emit it from `_on_underrun_cycle_closed` which already runs on the main thread (the cross-thread queued connection at `player.py:409-411` brought the call into the main thread). The receiver slot in `NowPlayingPanel` runs on the main thread too, so `DirectConnection` is the correct default — no `Qt.ConnectionType.QueuedConnection` argument needed. `[VERIFIED: source inspection]`

**Why not queued:** Queued connections add a tick of latency through the event loop. Both ends are already on the main thread; direct is faster and semantically correct.

**Example:**

```python
# musicstreamer/player.py — class-scope, near line 277 next to underrun_recovery_started:
class Player(QObject):
    # ...existing 18 signals...
    underrun_recovery_started = Signal()
    # Phase 78 / BUG-09 Commit A: cycle counter for stats-for-nerds row.
    # Emitted from _on_underrun_cycle_closed (main-thread slot — direct connect OK).
    underrun_count_changed = Signal(int)

    def __init__(self, ...):
        # ...existing fields...
        self._underrun_event_count: int = 0   # Resets per app launch (CONTEXT Discretion)

    def _on_underrun_cycle_closed(self, record) -> None:
        # ...existing _log.info(...) emission at lines 927-934...
        self._underrun_event_count += 1
        self.underrun_count_changed.emit(self._underrun_event_count)
```

```python
# musicstreamer/ui_qt/main_window.py — beside existing buffer_percent wiring at line 381:
self._player.buffer_percent.connect(self.now_playing.set_buffer_percent)
self._player.underrun_count_changed.connect(self.now_playing.set_underrun_count)
# QA-05: bound method, no lambda. No QueuedConnection — both sides on main thread.
```

```python
# musicstreamer/ui_qt/now_playing_panel.py — beside existing set_buffer_percent at line 946:
def set_underrun_count(self, count: int) -> None:
    """Phase 78 Commit A: update the Underruns: {N} stats row."""
    self._underrun_count_label.setText(str(int(count)))
```

### Pattern 3: Extensible `QFormLayout` row addition in `_build_stats_widget`

**What:** Phase 47.1 D-08/D-09 designed `_build_stats_widget` at `now_playing_panel.py:2451` to be extensible via additional `form.addRow(...)` calls. The whole wrapper inherits the hamburger-toggle visibility via `set_stats_visible(bool)` at line 951. `[VERIFIED: CONTEXT.md ref + source inspection]`

**Where to add:** Inside `_build_stats_widget`, AFTER `form.addRow(buffer_row_label, value_row)` at line 2478, BEFORE `wrapper.setVisible(False)` at line 2481.

**Example:**

```python
# musicstreamer/ui_qt/now_playing_panel.py:2478 (after existing Buffer row, before setVisible(False)):
form.addRow(buffer_row_label, value_row)
# Phase 78 / BUG-09 Commit A: live underrun cycle count. Same _MutedLabel pattern
# as the Buffer row above (Phase 47.1 D-10 theme-flip safety).
underrun_label = _MutedLabel("Underruns", wrapper)
self._underrun_count_label = _MutedLabel("0", wrapper)
form.addRow(underrun_label, self._underrun_count_label)
wrapper.setVisible(False)
```

### Anti-Patterns to Avoid

- **Mutating `logging.basicConfig` to add the file handler.** Pitfall 5 from Phase 62 explicitly forbids touching the root logger's level/handlers. `basicConfig(level=WARNING)` at `__main__.py:231` must stay byte-for-byte. The new handler attaches to the **module logger** (`musicstreamer.player`) only. The `tests/test_main_window_underrun.py::test_main_module_sets_player_logger_to_info` source-grep gate at lines 109-133 enforces this — it will fail if `basicConfig(level=logging.INFO)` shows up. Always verify by running this drift-guard test BEFORE committing.
- **Installing the handler before `migration.run_migration()` runs.** DATA_DIR is created by `assets.ensure_dirs()` / `migration.run_migration()` at `__main__.py:177`. The current per-logger `setLevel(INFO)` lives at line 235 in `main()` — which runs BEFORE `_run_gui` reaches the migration step. Installing the `RotatingFileHandler` at the same site as the `setLevel` would attempt to open a file inside a not-yet-existing directory and raise `FileNotFoundError`. **Two safe options:**
  - **(A) [preferred]** Install the handler inside `_run_gui`, after `migration.run_migration()` (line 177). This is one logical "boot section" later than the `setLevel(INFO)` in `main()`, but the per-logger level escalation has no dependency on the handler — they can land in different functions.
  - **(B)** Pass `delay=True` to `RotatingFileHandler(...)`. With `delay=True` the file is not opened at handler construction; it's opened lazily on first emit, which always happens after MainWindow is constructed (and thus after migration). **Caveat:** the directory still must exist at first emit; if a buffer_underrun happens before migration runs, this is the same problem. Since the player can only emit after MainWindow is up (and thus after migration), this is safe — but option (A) is cleaner.
  - **(C)** Defensive `os.makedirs(paths.data_dir(), exist_ok=True)` immediately before constructing the handler. Belt-and-suspenders.
  - **Recommendation:** Option (A) is the project-idiomatic choice. The `setLevel(INFO)` stays at `__main__.py:235` (it's a logger config that doesn't touch the filesystem); the file-handler attach moves to `_run_gui` next to `migration.run_migration()`.
- **Adding `underrun_count_changed` as a queued connection.** The receiver and emitter are both on the main thread. Queued adds latency. The existing pattern at `main_window.py:381` (`buffer_percent.connect(...)` with no connection-type argument) is correct — match it.
- **Forgetting to mirror the new Signal on `tests/_fake_player.py`.** The Phase 77 INFRA-01 drift-guards at `tests/test_fake_player_signal_parity.py` (name + arity parity) and `tests/test_fake_player_no_inline.py` (no inline FakePlayer redefinitions) will fail immediately. Add `underrun_count_changed = Signal(int)` to `_fake_player.py` in the same wave that adds it to Player.
- **Using a lambda for the new `.connect(...)` wire.** QA-05 convention is bound-method connect throughout the project. The existing `_player.buffer_percent.connect(self.now_playing.set_buffer_percent)` is the template.
- **Persisting the counter to SQLite / settings.** CONTEXT.md Discretion locks "counter resets per launch — no persistence". The file sink is the persistent record.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Size-rotated file sink | A custom file writer with manual size checking and rename logic | `logging.handlers.RotatingFileHandler` | Stdlib handles concurrent-write safety, atomic rename across rotations, and edge cases (e.g., write that pushes file just over `maxBytes` mid-emit). Already used in this codebase (`oauth_log.py`). |
| File handle lifecycle | Manual `open`/`close` around each emission | The handler's internal stream management | The handler opens once, holds the file descriptor, and rolls over correctly. Manual lifecycle invites race conditions and lost writes. |
| Cross-thread signal marshalling for the new counter | Manual `QMetaObject.invokeMethod` or thread-affinity checks | Default `Signal.emit()` semantics — both ends already on main thread | Both emitter and receiver are on the main thread; PySide6's default DirectConnection works correctly. No need for `QueuedConnection`. |
| Counter de-dup logic | Manually track previous count to avoid redundant Signal emits | Just emit on every cycle_close | Each cycle_close is a distinct event; the UI is happy to re-render `Underruns: 5` over `Underruns: 5` (no-op for `QLabel.setText`). De-dup adds code with zero behavioural value. |
| File-creation-on-first-emit gating | A custom predicate that checks if the path exists | `RotatingFileHandler(..., delay=True)` OR install handler post-migration | The stdlib handler handles this directly — either via `delay` or by relying on directory existing at install time. |

**Key insight:** Every piece of Commit A has either a stdlib primitive or an existing in-project pattern. There is no place this phase should write custom code beyond ~30 net lines of glue.

## Runtime State Inventory

> Not applicable. Commit A is a **pure additive code change** (file sink + new Signal + new UI row + counter). It does not rename, refactor, migrate, or rebrand any existing surface.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — counter explicitly resets per launch (CONTEXT.md Discretion); no SQLite or settings persistence. | None |
| Live service config | None — entirely in-process. | None |
| OS-registered state | None — no Task Scheduler, systemd, pm2, or launchd entries touched. | None |
| Secrets / env vars | None — no secrets involved. | None |
| Build artifacts | None — no package metadata renames; `pyproject.toml` version field bumps automatically via the existing VER-01 hook at phase close. | None |

Verified by: no rename / move / delete operations are part of the Commit A scope per CONTEXT.md.

## Common Pitfalls

### Pitfall 1: File handler installed before DATA_DIR exists

**What goes wrong:** `RotatingFileHandler("/home/user/.local/share/musicstreamer/buffer-events.log", ...)` raises `FileNotFoundError: [Errno 2] No such file or directory` if the parent dir doesn't exist yet at handler construction time.

**Why it happens:** The handler default is `delay=False` — the file is opened immediately. `__main__.main()` sets up logging at line 231-239 BEFORE `_run_gui()` calls `migration.run_migration()` (line 177 of `_run_gui`). If you naively put the handler attach right next to the `setLevel(INFO)` at line 235, the order is: basicConfig → setLevel → addHandler [BOOM] → … → migration creates DATA_DIR.

**How to avoid:** Install the handler inside `_run_gui` AFTER `migration.run_migration()`. The `setLevel(INFO)` can stay where it is — they don't have to be co-located. Alternative: `delay=True` defers the open until first emit (which is after MainWindow is constructed → after migration).

**Warning signs:** A red squiggle from the first launch on a clean test home directory. Catch in a test that uses `tmp_path` and a custom `_root_override`.

### Pitfall 2: Pitfall 5 regression — bumping `basicConfig` to INFO

**What goes wrong:** Tempted to "simplify" by changing `logging.basicConfig(level=logging.WARNING)` at `__main__.py:231` to `logging.basicConfig(level=logging.INFO)` so the file handler's lazy-open behavior is "more convenient". This would also surface INFO chatter from `aa_import`, `gbs_api`, `mpris2`, etc., to stderr — flooding the user's terminal during normal use.

**Why it happens:** This was a real concern in Phase 62 and is documented as Pitfall 5 in CONTEXT.md `<canonical_refs>` and the qt-glib-bus-threading.md skill. The Phase 62 verifier prompt explicitly bound this invariant.

**How to avoid:** Two protections already in place:
  1. `tests/test_main_window_underrun.py::test_main_module_sets_player_logger_to_info` (lines 109-133) is a source-grep drift-guard that asserts BOTH `getLogger("musicstreamer.player").setLevel(logging.INFO)` AND `basicConfig(level=logging.WARNING)` are present. Run it before committing Plan 03 / Plan 04.
  2. Pattern 1 above only attaches the handler to `_player_log = logging.getLogger("musicstreamer.player")` — not to root. The `propagate=True` default is sufficient to keep stderr working without changing the root level.

**Warning signs:** Stderr after a normal session shows lots of `INFO:musicstreamer.aa_import:...` or `INFO:musicstreamer.gbs_api:...` lines that weren't there in Phase 62. Drift-guard test fails.

### Pitfall 3: `_underrun_event_count` not added to Player's `__init__`

**What goes wrong:** Forgetting to initialize `self._underrun_event_count: int = 0` in Player's `__init__` means the first `_on_underrun_cycle_closed` call raises `AttributeError`. The phase test suite catches this immediately, but on a release path it would only surface on the first real underrun.

**Why it happens:** It's tempting to mutate `self._underrun_event_count` only in the slot without a typed initialization, relying on Python's "set on first write" semantics.

**How to avoid:** Add `self._underrun_event_count: int = 0` in `Player.__init__` adjacent to the existing `self._tracker = _BufferUnderrunTracker()` at `player.py:441-442`. Same physical block as the cycle-tracker fields — they're conceptually paired.

**Warning signs:** `pytest tests/test_player_underrun_count.py` (new test file) fails with AttributeError, OR drift-guard `test_fake_player_signal_parity.py` flags missing Signal mirror.

### Pitfall 4: `_fake_player.py` not updated → INFRA-01 drift-guard fails

**What goes wrong:** Phase 77 INFRA-01 added `tests/test_fake_player_signal_parity.py` which source-greps both `musicstreamer/player.py` and `tests/_fake_player.py` and asserts every `<name> = Signal(<args>)` declaration appears in BOTH with identical arity. Adding `underrun_count_changed = Signal(int)` to Player without mirroring on `_fake_player.py` fails this test immediately.

**Why it happens:** The mirror is non-obvious — `_fake_player.py` is in `tests/`, not `musicstreamer/`, and it's easy to forget the parity edit when focused on production code.

**How to avoid:** Plan the `_fake_player.py` edit explicitly in the same wave that adds the Signal to Player. The two edits are intentionally coupled — that's the whole point of the INFRA-01 drift-guard. Verify by running `pytest tests/test_fake_player_signal_parity.py -v` before commit.

**Warning signs:** `FakePlayer missing Player signal(s): ['underrun_count_changed']` in CI output.

### Pitfall 5: Toast for the new count change

**What goes wrong:** Tempting to also fire a toast on every count change ("Buffer underrun #5"). This would compete with the existing `Buffering…` toast and break Phase 62's silent-recovery philosophy (D-07, D-08).

**Why it happens:** It's intuitive to mirror a count change with a notification.

**How to avoid:** CONTEXT.md D-07 explicitly forbids any new toast paths. The count is a stats-for-nerds row — silent. The existing `Buffering…` toast (cooldown-gated) remains the only user-visible signal during recovery.

**Warning signs:** UI test fails because `_toast.label.text()` contains "Underrun #N" or similar.

### Pitfall 6: Directly testing the file's bytes-on-disk instead of the handler shape

**What goes wrong:** A test that writes to a real `~/.local/share/musicstreamer/buffer-events.log` would pollute the developer's data directory and race against other test runs. It also couples the test to real wall-clock timestamps in the line.

**Why it happens:** "I'll just trigger an underrun and `open()` the file" is the obvious first approach.

**How to avoid:** Use the `paths._root_override` pattern (see `paths.py:22-31`) — monkeypatch it to a `tmp_path` and the helper redirects every accessor. Verify the handler's existence and `baseFilename` attribute directly: `RotatingFileHandler.baseFilename` is a documented attribute. Example:

```python
def test_buffer_handler_attached_to_player_logger(tmp_path, monkeypatch):
    monkeypatch.setattr("musicstreamer.paths._root_override", str(tmp_path))
    # Trigger the install path (call the install function the planner extracts —
    # OR mimic _run_gui's relevant subset; see Pattern below).
    from musicstreamer.buffer_log import install_buffer_events_handler
    install_buffer_events_handler()
    import logging
    log = logging.getLogger("musicstreamer.player")
    rotating_handlers = [
        h for h in log.handlers
        if h.__class__.__name__ == "RotatingFileHandler"
    ]
    assert len(rotating_handlers) == 1
    h = rotating_handlers[0]
    assert h.baseFilename == str(tmp_path / "buffer-events.log")
    assert h.maxBytes == 1_048_576
    assert h.backupCount == 3
```

**Warning signs:** Test pollutes developer's actual `~/.local/share/musicstreamer/` directory; flaky CI.

### Pitfall 7: Forgetting to install the handler exactly once (handler duplication on test reruns)

**What goes wrong:** If a test calls the install function twice, the handler attaches twice — every emit writes two lines to the file. In production this isn't an issue (install runs once at startup), but in test code that exercises `_run_gui` multiple times, handlers accumulate.

**Why it happens:** `logger.addHandler(...)` is unconditional; it doesn't dedup.

**How to avoid:** Make the install function idempotent — scan `_player_log.handlers` for an existing `RotatingFileHandler` whose `baseFilename` matches the expected path, and skip the addHandler call if found. Example:

```python
def install_buffer_events_handler() -> None:
    path = paths.buffer_events_log_path()
    log = logging.getLogger("musicstreamer.player")
    for h in log.handlers:
        if isinstance(h, RotatingFileHandler) and h.baseFilename == path:
            return  # already installed
    handler = RotatingFileHandler(path, maxBytes=1_048_576, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log.addHandler(handler)
```

**Warning signs:** Test asserts `len(rotating_handlers) == 1` fails with `2` or more.

## Code Examples

Verified patterns from existing project sources. All references are to lines in this repository.

### Example 1: Existing RotatingFileHandler shape (oauth_log.py)

```python
# Source: musicstreamer/oauth_log.py:55-71 (project-canonical)
class OAuthLogger:
    def __init__(self, log_path: str) -> None:
        self._log_path = log_path
        self._logger = logging.getLogger(f"musicstreamer.oauth.{id(self)}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False  # OAuth logger detaches from root for privacy
        handler = RotatingFileHandler(
            log_path,
            maxBytes=64 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)
```

**For Phase 78:** Use the SAME shape but keep `propagate=True` (default — do NOT set `propagate=False`). We want INFO records to reach BOTH the file sink AND the existing stderr handler from `basicConfig`. We also use `maxBytes=1_048_576, backupCount=3` per CONTEXT.md D-02.

### Example 2: Existing test pattern for a RotatingFileHandler (test_oauth_log.py)

```python
# Source: tests/test_oauth_log.py:178-203
def test_log_rotation_at_64kb(tmp_path):
    """After enough writes to exceed 64KB, oauth.log.1 exists."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    payload = "a" * 150
    for i in range(500):
        logger.log_event(
            {"ts": float(i), "category": "X", "detail": payload, "provider": "twitch"}
        )
    assert os.path.exists(log_path + ".1"), "rotation should have produced oauth.log.1"

def test_log_never_creates_backup_3(tmp_path):
    """backupCount=2 means oauth.log.3 never exists."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    payload = "a" * 150
    for i in range(2000):
        logger.log_event(
            {"ts": float(i), "category": "X", "detail": payload, "provider": "twitch"}
        )
    assert not os.path.exists(log_path + ".3"), "backupCount=2 must cap at .2"
```

**For Phase 78:** Mirror this pattern for the new file (use `tmp_path` + `paths._root_override` monkeypatch). Test that `buffer-events.log.1` rotates at 1MB and `buffer-events.log.4` is never created (because backupCount=3 caps at .3).

### Example 3: Existing main-thread Signal wiring (main_window.py + now_playing_panel.py)

```python
# Source: musicstreamer/ui_qt/main_window.py:381
self._player.buffer_percent.connect(self.now_playing.set_buffer_percent)
```

```python
# Source: musicstreamer/ui_qt/now_playing_panel.py:946-949
def set_buffer_percent(self, percent: int) -> None:
    """Update the buffer indicator bar + {N}% label atomically (D-11). Phase 47.1."""
    self.buffer_bar.setValue(int(percent))
    self.buffer_pct_label.setText(f"{int(percent)}%")
```

**For Phase 78:** Add `self._player.underrun_count_changed.connect(self.now_playing.set_underrun_count)` immediately after the buffer_percent connect line. Add `set_underrun_count(int)` to NowPlayingPanel in the same style.

### Example 4: Existing main-thread cycle-closed slot (player.py:918-934)

```python
# Source: musicstreamer/player.py:918-934
def _on_underrun_cycle_closed(self, record) -> None:
    """Main-thread slot (Phase 62 / D-02). Cancels in-flight dwell timer
    (silent recovery, D-07) and writes the structured log line at INFO.
    """
    self._underrun_dwell_timer.stop()    # idempotent
    _log.info(
        "buffer_underrun "
        "start_ts=%.3f end_ts=%.3f duration_ms=%d min_percent=%d "
        "station_id=%d station_name=%r url=%r outcome=%s cause_hint=%s",
        record.start_ts, record.end_ts, record.duration_ms, record.min_percent,
        record.station_id, record.station_name, record.url,
        record.outcome, record.cause_hint,
    )
```

**For Phase 78:** Add two lines after the `_log.info(...)` call:

```python
    self._underrun_event_count += 1
    self.underrun_count_changed.emit(self._underrun_event_count)
```

Counter increments on EVERY cycle_close regardless of outcome (recovered / failover / stop / pause / shutdown) — same semantics as the log emission, per CONTEXT.md `<specifics>`.

### Example 5: Existing extensible stats widget (now_playing_panel.py:2451-2482)

```python
# Source: musicstreamer/ui_qt/now_playing_panel.py:2451-2482
def _build_stats_widget(self) -> QWidget:
    """Construct the stats-for-nerds wrapper (D-07/D-08/D-09). Phase 47.1."""
    wrapper = QWidget(self)
    form = QFormLayout(wrapper)
    form.setContentsMargins(0, 0, 0, 0)

    buffer_row_label = _MutedLabel("Buffer", wrapper)

    value_row = QWidget(wrapper)
    value_layout = QHBoxLayout(value_row)
    value_layout.setContentsMargins(0, 0, 0, 0)
    value_layout.setSpacing(6)
    self.buffer_bar = QProgressBar(value_row)
    self.buffer_bar.setRange(0, 100)
    self.buffer_bar.setTextVisible(False)
    self.buffer_bar.setFixedWidth(120)
    self.buffer_pct_label = _MutedLabel("0%", value_row)
    value_layout.addWidget(self.buffer_bar)
    value_layout.addWidget(self.buffer_pct_label)
    value_layout.addStretch(1)

    form.addRow(buffer_row_label, value_row)
    # [PHASE 78 INSERTION POINT — exactly here, before setVisible]
    wrapper.setVisible(False)
    return wrapper
```

**For Phase 78:** Insert at the marked point — single `form.addRow(_MutedLabel("Underruns", wrapper), self._underrun_count_label)` line. Use `_MutedLabel` for theme-flip safety per Phase 47.1 D-10. The widget inherits the existing hamburger-toggle visibility from the wrapper.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Phase 62: instrumentation via stderr only | Phase 78 Commit A: stderr + size-rotated file sink | This phase | `.desktop` launches no longer lose the diagnostic stream; week-long harvest becomes possible. |
| Phase 62: `_underrun_event_count` listed as optional Discretion item, not implemented | Phase 78 Commit A: counter is required, surfaced live in stats-for-nerds | This phase | Live observability of cycle count without grepping the log file. |
| Phase 62: instrumentation considered the ship line for BUG-09 | Phase 78 closes SC #3 (behavior fix) — instrumentation was the deferred half | This phase + Commit B | BUG-09 fully closes after Commit B ships post-harvest. |

**Deprecated / outdated:** None for this commit. All Phase 62 surfaces (cycle tracker, dwell timer, cooldown gate) are KEPT verbatim.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `delay=True` works as documented in Python 3.13's `RotatingFileHandler` (file not opened until first emit). | Pitfall 1 Option (B) | If wrong, the recommended Option (A) (install handler after migration) is unaffected — A is the project-idiomatic choice anyway. Risk: LOW. `[ASSUMED]` — not verified in a unit test this session, but matches stdlib docs and Python's `FileHandler.__init__` source behavior. |
| A2 | A `RotatingFileHandler` added to `musicstreamer.player` with default `propagate=True` DOES allow the same INFO record to also reach the root logger's stderr handler from `basicConfig(WARNING)`. | Pattern 1, Summary | **VERIFIED in this session via live Python repl.** `[VERIFIED: live Python repl 2026-05-17]` — captured stderr buffer contained `INFO:musicstreamer.player:test_info_line` even though root level was WARNING (because per-logger level INFO ≥ message level INFO, and root's handler has no level filter). |
| A3 | The new `underrun_count_changed = Signal(int)` connection between Player and NowPlayingPanel can safely use the default (Direct) connection — both ends are on the main thread. | Pattern 2 | If both ends are NOT on the main thread, Direct from non-Qt thread is unsafe (Phase 43.1 Pitfall 2). `[VERIFIED: source inspection]` — emit is from `_on_underrun_cycle_closed` which is a slot connected to `_underrun_cycle_closed` via `Qt.ConnectionType.QueuedConnection` at `player.py:409-411`, so the slot is already running on the main thread; receiver `NowPlayingPanel.set_underrun_count` runs on the main thread by Qt convention (NowPlayingPanel is a widget). |
| A4 | The existing `block_real_network` fixture at `tests/conftest.py:74-98` is the appropriate fixture for tests that construct MainWindow (to prevent daemon-thread urlopen leaks). | Pattern (test) | The fixture exists and is the Phase 77-blessed convention. `[VERIFIED: source inspection]` |
| A5 | The Phase 77 INFRA-01 drift-guards `tests/test_fake_player_signal_parity.py` and `tests/test_fake_player_no_inline.py` are currently green and will fire if the planner adds `underrun_count_changed` to Player without mirroring on `_fake_player.py`. | Pitfall 4 | Drift-guards inspected; logic confirmed. `[VERIFIED: source inspection]` |
| A6 | The Phase 77-introduced `block_real_network` fixture's `urlopen` MagicMock side-effect (`OSError`) is safe for `test_first_call_shows_toast` and similar — no cascading errors during MainWindow construction. | Validation Architecture | Phase 77 already shipped this pattern across `tests/test_main_window_underrun.py` (line 32 in current source). `[VERIFIED: source inspection]` |

## Open Questions (RESOLVED)

All four open questions were resolved during planning. Each entry's resolution and the implementing plan/task is cited inline.

1. **Formatter prefix in the file line — `%(asctime)s` or bare `%(message)s`?**
   - What we know: CONTEXT.md `<specifics>` says "byte-for-byte the same as the existing stderr line" but the existing stderr line is prefixed with `INFO:musicstreamer.player:` (basicConfig default). The structured `buffer_underrun ...` payload is what grep actually targets — and it's identical in both sinks regardless of formatter choice.
   - What's unclear: whether the planner should add `%(asctime)s` to the file formatter (gives each line an independent ISO datestamp on top of the in-line `start_ts=%.3f`) or leave it bare.
   - Recommendation: include `%(asctime)s` so the file is self-stamping for the harvest analysis. The Discretion permits either; mention the choice in PLANS but don't block the user.
   - **— RESOLVED:** include `%(asctime)s %(message)s` formatter on the file handler. Locked in Plan 78-01 Task 2 action.

2. **Underrun count row label text — "Underruns: {N}" or just "Underruns" with value column "{N}"?**
   - What we know: CONTEXT.md `<domain>` writes "expose `Underruns: {N}` row" but the existing Buffer row uses two-column layout: label "Buffer" on left, value (`buffer_bar` + `buffer_pct_label`) on right. Using the same shape gives a clean `Underruns | 0` two-column read.
   - What's unclear: whether the user prefers the colon-formatted single-cell shape or the existing two-column shape.
   - Recommendation: match the existing Buffer row's two-column shape (label "Underruns" on left, integer string on right). Consistent with Phase 47.1 D-10's _MutedLabel pattern and the existing `QFormLayout` semantics. Visually it reads identical to "Underruns: N" if both are on the same form row.
   - **— RESOLVED:** match the existing Buffer row's two-column `QFormLayout` shape (label "Underruns" / value `_MutedLabel("0")`). Locked in Plan 78-03 Task 1 action.

3. **Should Commit A also pre-touch (create) the empty `buffer-events.log` file at install time?**
   - What we know: CONTEXT.md `<decisions>` Claude's Discretion says "No need to `touch` it at install time" — explicit not-do.
   - Recommendation: don't pre-touch. Handler opens lazily on first emit (or eagerly with `delay=False`, but only after migration ran — so DATA_DIR exists). No issue.
   - **— RESOLVED:** no pre-touch. Honors CONTEXT.md Claude's Discretion explicit not-do. Locked in Plan 78-01 Task 2 (handler created lazily on first emit).

4. **Where exactly should the `install_buffer_events_handler()` function live?**
   - What we know: `__main__.py` is the existing install site for logger config. CONTEXT.md `<code_context>` Integration Points #1 says "`musicstreamer/__main__.py:222–226` (near the existing `setLevel(INFO)` call)". But Pitfall 1 above shows the handler attach must happen AFTER `migration.run_migration()`, which is in `_run_gui` not in `main`.
   - What's unclear: whether the planner should (a) move the install call to `_run_gui` post-migration but keep the `setLevel(INFO)` in `main()`, OR (b) extract a small helper module `musicstreamer/buffer_log.py` and call it from `_run_gui`.
   - Recommendation: option (b) — extract a tiny `musicstreamer/buffer_log.py` with a single `install_buffer_events_handler()` function. This makes the test surface clean (Pitfall 6 test pattern works against the module directly) and matches the project's preference for narrow, testable helpers (cf. `cookie_utils.py`, `yt_dlp_opts.py`, `desktop_install.py`).
   - **— RESOLVED:** option (b) — extract `musicstreamer/buffer_log.py` with `install_buffer_events_handler()` called from `_run_gui` AFTER `migration.run_migration()`. Locked in Plan 78-01 Tasks 2 (helper module + tests) and 3 (call site).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python `logging.handlers.RotatingFileHandler` (stdlib) | File sink | ✓ | Python 3.13.13 | — |
| `PySide6.QtCore.Signal` | New count Signal | ✓ | PySide6 pinned in `pyproject.toml` | — |
| `platformdirs` | Indirect via `paths._root()` | ✓ | already pinned | — |
| `pytest` + `pytest-qt` (qtbot) | Unit + UI tests | ✓ | already in dev deps | — |
| `~/.local/share/musicstreamer/` writable | File sink at runtime | ✓ | — | — (parent dir already exists; created by `migration.run_migration()` at boot) |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` (+ `pytest-qt` for Qt tests) — pinned in dev deps |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_buffer_events_log.py tests/test_player_underrun_count.py tests/test_main_window_underrun.py -q` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| BUG-09 SC#3 (Commit A — file sink) | `RotatingFileHandler` is attached to `musicstreamer.player`, points at `paths.buffer_events_log_path()`, has `maxBytes=1_048_576` and `backupCount=3` | unit | `uv run pytest tests/test_buffer_events_log.py::test_handler_attached_to_player_logger -x` | ❌ Wave 0 |
| BUG-09 SC#3 (Commit A — file sink) | Calling `_log.info(...)` writes the `buffer_underrun ...` line to the file (single emit → single line in file) | unit | `uv run pytest tests/test_buffer_events_log.py::test_emit_writes_line_to_file -x` | ❌ Wave 0 |
| BUG-09 SC#3 (Commit A — file sink) | Rotation: at >1MB, `buffer-events.log.1` exists; `buffer-events.log.4` never created | unit | `uv run pytest tests/test_buffer_events_log.py::test_rotation_at_1mb tests/test_buffer_events_log.py::test_never_creates_backup_4 -x` | ❌ Wave 0 |
| BUG-09 SC#3 (Commit A — file sink) | Idempotent install: calling install twice does NOT double the handler count | unit | `uv run pytest tests/test_buffer_events_log.py::test_install_is_idempotent -x` | ❌ Wave 0 |
| BUG-09 SC#3 (Commit A — file sink) | Both stderr AND file receive the same record (propagate=True path verification) | unit | `uv run pytest tests/test_buffer_events_log.py::test_record_reaches_both_sinks -x` | ❌ Wave 0 |
| BUG-09 SC#3 (Commit A — path helper) | `buffer_events_log_path()` returns `{data_dir}/buffer-events.log`; respects `_root_override` monkeypatch | unit | `uv run pytest tests/test_paths.py::test_buffer_events_log_path -x` | ❌ Wave 0 (file exists; new test inside it) |
| BUG-09 SC#3 (Commit A — counter) | `Player._underrun_event_count` initialized to 0 in `__init__`; counter increments by 1 per `_on_underrun_cycle_closed` call; resets to 0 on Player instantiation | unit | `uv run pytest tests/test_player_underrun_count.py::test_count_starts_at_zero tests/test_player_underrun_count.py::test_count_increments_per_close -x` | ❌ Wave 0 |
| BUG-09 SC#3 (Commit A — counter) | Counter increments on EVERY outcome (recovered / failover / stop / pause / shutdown) | unit | `uv run pytest tests/test_player_underrun_count.py::test_count_increments_for_all_outcomes -x` | ❌ Wave 0 |
| BUG-09 SC#3 (Commit A — Signal) | `underrun_count_changed = Signal(int)` declared at class scope; emit fires from `_on_underrun_cycle_closed` with the new count value | unit | `uv run pytest tests/test_player_underrun_count.py::test_signal_emits_with_count_value -x` | ❌ Wave 0 |
| BUG-09 SC#3 (Commit A — FakePlayer parity) | `tests/_fake_player.py` mirrors `underrun_count_changed = Signal(int)` (INFRA-01 drift-guard passes) | drift-guard | `uv run pytest tests/test_fake_player_signal_parity.py -x` | ✅ exists (test passes once parity is added) |
| BUG-09 SC#3 (Commit A — UI row) | `NowPlayingPanel._build_stats_widget` produces a `QFormLayout` with a second row whose label text is "Underruns"; default value text is "0" | unit | `uv run pytest tests/test_now_playing_panel.py::test_underrun_count_row_present -x` | ❌ Wave 0 (file exists; new test inside) |
| BUG-09 SC#3 (Commit A — UI wiring) | `MainWindow.__init__` connects `Player.underrun_count_changed` to `NowPlayingPanel.set_underrun_count`; emitting the signal updates the label text | integration | `uv run pytest tests/test_main_window_underrun.py::test_count_changed_updates_stats_row -x` | ❌ Wave 0 (file exists; new test inside) |
| BUG-09 SC#3 (Commit A — Pitfall 5) | `__main__.py` still has `basicConfig(level=logging.WARNING)`; per-logger INFO still set | source-grep (regression lock) | `uv run pytest tests/test_main_window_underrun.py::test_main_module_sets_player_logger_to_info -x` | ✅ exists (already covers Pitfall 5) |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_buffer_events_log.py tests/test_player_underrun_count.py tests/test_main_window_underrun.py tests/test_fake_player_signal_parity.py -q` (fast — ≤2s)
- **Per wave merge:** `uv run pytest tests/test_player_underrun.py tests/test_player_underrun_tracker.py tests/test_main_window_integration.py tests/test_now_playing_panel.py tests/_buffer_events_log.py tests/test_player_underrun_count.py tests/test_main_window_underrun.py -q` (Phase 62 regression + Phase 78 new tests)
- **Phase gate:** Full suite green via `uv run pytest tests/ -q` before `/gsd:verify-work` runs. Existing project gate.

### Wave 0 Gaps

- [ ] `tests/test_buffer_events_log.py` — covers BUG-09 SC#3 file-sink layer (handler attachment, path, rotation, idempotency, propagate sanity check)
- [ ] `tests/test_player_underrun_count.py` — covers counter init / increment-per-outcome / Signal emission
- [ ] New test cases inside `tests/test_paths.py`, `tests/test_now_playing_panel.py`, `tests/test_main_window_underrun.py` for the path helper, UI row presence, and end-to-end Signal → label wiring (one test per file; no new file)
- [ ] `_fake_player.py` parity edit: add `underrun_count_changed = Signal(int)` next to existing `underrun_recovery_started = Signal()` at line 69

*Framework install: not needed — `pytest` + `pytest-qt` already in dev deps.*

## Security Domain

This phase has minimal security surface — diagnostic file written to user's own data dir, no external network, no secrets. ASVS categories listed for completeness; only V7 (Error Handling & Logging) materially applies.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a |
| V5 Input Validation | partial | Existing `%r`-quoting of `station_name` and `url` in the `_log.info(...)` line at `player.py:927-934` already neutralizes log-injection (T-62-01 mitigation, locked Phase 62). No new untrusted input touches the log path. |
| V6 Cryptography | no | n/a |
| V7 Error Handling & Logging | yes | Use stdlib `logging.handlers.RotatingFileHandler` — never hand-roll size rotation. CONTEXT.md D-03 explicitly does NOT 0o600 the file (rationale: diagnostic data, not credentials; user wants easy `cat`/`grep`). This is a deliberate departure from `oauth_log.py` (which DOES 0o600). |
| V8 Data Protection | partial | The file contains station URLs and station names — same data already on stderr from Phase 62. Not credentials. Default perms (typically 0644 on Linux) are appropriate per D-03. |

### Known Threat Patterns for stdlib logging + file I/O

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Log injection via control chars in station_name/url | Tampering | Already mitigated — Phase 62 uses `%r` formatting at `player.py:927-934`; T-62-01 lock binds. No new mitigation needed. |
| Path traversal in log file path | Tampering | `paths.buffer_events_log_path()` constructs the path internally; no user input flows into the path string. Mitigated by design. |
| File-descriptor exhaustion via repeated install | DoS | Idempotent install (Pitfall 7) — install function refuses to add a second handler with the same `baseFilename`. Test-covered. |
| Disk-space exhaustion via unbounded log growth | DoS | `RotatingFileHandler(maxBytes=1MB, backupCount=3)` caps total disk usage at ~4MB. CONTEXT.md D-02 lock binds. |
| Cross-thread race writing to file | Tampering / Repudiation | `RotatingFileHandler.emit()` uses a stdlib `threading.RLock` (`logging.Handler.lock`). All emits are serialized. Mitigated by stdlib. |

## Project Constraints (from CLAUDE.md)

**CLAUDE.md content:** Project routing only — no actionable code conventions, no security requirements beyond the standard project patterns. The directive is "Spike findings for MusicStreamer (Windows packaging patterns, GStreamer+PyInstaller+conda-forge, PowerShell gotchas) → `Skill('spike-findings-musicstreamer')`".

For Phase 78 Commit A the relevant routing item is the qt-glib-bus-threading reference (Pitfall 2 + Pitfall 5). Both have been folded into Pitfalls 1 and 2 above. No additional CLAUDE.md directives apply to this commit.

---

## Commit B Research Dependencies (DO NOT RESEARCH NOW — for the planner's awareness only)

Per CONTEXT.md D-01, Commit B's planning happens in a separate pass ~1 week after Commit A ships. The questions below are noted here so the user knows what the post-harvest research pass will need to resolve. **Do not deep-research them in this commit.**

1. **Mid-session property write support in playbin3.** Does `self._pipeline.set_property("buffer-duration", new_value * Gst.SECOND)` and `set_property("buffer-size", new_bytes)` take effect mid-stream (i.e., without a `set_state(NULL)` → `set_state(PLAYING)` cycle)? Or do these properties only apply at the next URL bind? CONTEXT.md D-05's adaptive growth design depends on this. If mid-session writes are ignored, D-05 degrades gracefully to "new value applies at next `_try_next_stream`" — still adaptive, just at station-boundary granularity. **Planner should probe this with a GStreamer doc check + small live test against the actual `playbin3` element in this project's GStreamer 1.28.2 pin (Phase 43).**

2. **`queue2`'s `low-percent` / `high-percent` properties on playbin3.** Are these exposed via `playbin3.set_property("low-percent", N)` directly, or do we need to override `use-buffering` with a custom `queue2` element wrapped around the URI source? The Phase 62 RESEARCH document at `.planning/phases/62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt/62-RESEARCH.md` has background on the queue2 layering inside playbin3. CONTEXT.md `<deferred>` lists watermark tweaks as a follow-up to D-04's buffer bump; they're not first-line for Commit B but the question may surface.

3. **Best adaptive growth schedule shape (linear vs exponential).** CONTEXT.md D-05 sketches 10s → 20s → 40s → 80s → 120s. The actual curve gets picked from harvest data: if dropouts cluster around predictable durations (e.g., always 8-12s), a static bump to 15s may suffice and adaptive growth is over-engineered. If dropouts span widely (5-90s), exponential growth makes sense. **Planner's call once data exists.**

4. **Per-cycle counter reset semantics for the `Buffer config: Xs (adapted)` row.** Commit B's stats row only shows when `_current_buffer_duration_s != BUFFER_DURATION_S`. Does the live value reset on station change (mirroring D-05's reset)? The CONTEXT.md `<specifics>` says yes (reset to baseline on `_try_next_stream`), but the exact lifecycle for the UI row needs locking — does it flip back to hidden on the reset, or stay visible until the next underrun proves the reset stuck?

**None of these are blockers for Commit A. They are research items for the second pass.**

---

## Sources

### Primary (HIGH confidence)

- **`musicstreamer/oauth_log.py:1-90`** — Project-canonical `RotatingFileHandler` install pattern. Single source of truth for the file-sink shape.
- **`musicstreamer/paths.py:1-95`** — Path helper module shape; `_root_override` test-monkeypatch hook; `cookies_path` / `gbs_cookies_path` shape to mirror.
- **`musicstreamer/player.py:79-81, 271-282, 409-411, 909-940`** — Existing logger declaration, Signals declaration block, queued connections, and cycle-closed slot where increment+emit lands.
- **`musicstreamer/__main__.py:165-235`** — Boot ordering: `_run_gui` → migration → MainWindow construction; `main` → `basicConfig(WARNING)` → per-logger `setLevel(INFO)`.
- **`musicstreamer/ui_qt/now_playing_panel.py:2451-2482, 946-949`** — `_build_stats_widget` extensible form; existing `set_buffer_percent` slot template.
- **`musicstreamer/ui_qt/main_window.py:280-400`** — Player Signal wiring conventions; existing `buffer_percent.connect(...)` precedent.
- **`tests/test_oauth_log.py:1-221`** — Project-canonical RotatingFileHandler test pattern (tmp_path + handler attribute introspection + rotation assertions).
- **`tests/_fake_player.py:1-135`** — Phase 77 INFRA-01 shared FakePlayer; must mirror new Signal.
- **`tests/test_fake_player_signal_parity.py:1-87`** — INFRA-01 drift-guard source-grep logic.
- **`tests/test_main_window_underrun.py:1-134`** — Phase 62 MainWindow underrun test patterns; including `test_main_module_sets_player_logger_to_info` Pitfall 5 source-grep gate.
- **`.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md`** — Pitfall 2 (cross-thread Signal marshalling) and Rule-2 (`QTimer.singleShot` from non-Qt thread silently drops). Bound to this phase even though Commit A's new Signal is main-thread-only — the planner must document this explicitly.
- **`.planning/phases/62-audio-buffer-underrun-resilience-intermittent-dropouts-stutt/62-CONTEXT.md, 62-VERIFICATION.md`** — Phase 62 carry-forward; D-09 unlocked here; SC #3 closure path.

### Secondary (MEDIUM confidence)

- Live Python repl session 2026-05-17 — verified `propagate=True` behavior with `basicConfig(WARNING)` root + per-logger `setLevel(INFO)`. INFO record reached the basicConfig StreamHandler.
- Live `help(logging.handlers.RotatingFileHandler.__init__)` on the project Python 3.13.13 — confirmed signature `(filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=False, errors=None)`.

### Tertiary (LOW confidence)

None — every claim in this research is backed by direct source inspection or live Python verification in the session.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — every primitive is stdlib or already in this project; one project-canonical reference (`oauth_log.py`) covers the exact API.
- Architecture: HIGH — entirely composed of existing Phase 62, Phase 47.1, and Phase 77 patterns. No novel architecture.
- Pitfalls: HIGH — direct source inspection confirmed the boot-ordering issue (Pitfall 1), Pitfall 5 drift-guard test still exists, and `_fake_player.py` parity drift-guard still in place.

**Research date:** 2026-05-17
**Valid until:** 2026-06-17 (Commit A scope only; Commit B research happens in a separate pass after harvest week)

## RESEARCH COMPLETE
