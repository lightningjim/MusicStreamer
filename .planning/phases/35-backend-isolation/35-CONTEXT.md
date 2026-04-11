# Phase 35: Backend Isolation - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Port `musicstreamer/player.py` to a `QObject` with typed Qt signals, swap the GStreamer bus→UI bridge from `GLib.idle_add` to a `GLib.MainLoop` daemon thread + queued Qt signals, move data paths to `platformdirs`, port `yt_import.py` and `player._play_twitch()` from subprocess calls to the `yt-dlp` / `streamlink` Python library APIs, and run a spike to decide whether mpv can be dropped. Qt event loop runs headless (no window) this phase; UI scaffold is Phase 36.

Out of scope for Phase 35: `QMainWindow`, GTK UI deletion, icon bundling, Fusion style, full MPRIS rewrite — all belong to later phases.

</domain>

<decisions>
## Implementation Decisions

### Phase Scope — Option A (Qt-first backend)
- **D-01:** Phase 35 performs the full `Player` → `QObject` conversion. `player.py` ends the phase with zero `GLib.idle_add`, `GLib.timeout_add`, `GLib.source_remove`, and `dbus-python` imports. This matches PORT-01 and the roadmap success criteria as written.
- **D-02:** `QCoreApplication` (headless, no widgets) is instantiated in Phase 35 so queued Qt signals and `QTimer` callbacks dispatch correctly. The Qt event loop is present even though no `QMainWindow` exists yet.
- **D-03:** Phase 36 then only adds the visible `QMainWindow`, deletes GTK UI, bundles icons, and enforces Fusion on Windows — it does NOT re-touch `player.py` internals.

### Task Ordering
- **D-04:** The mpv-drop spike runs FIRST, before the yt-dlp library-API port. Rationale: the spike decides whether mpv code paths remain, which changes the surface area of the library-API port task. Planner should sequence: (1) spike → (2) decision recorded → (3) yt-dlp/streamlink library port → (4) player QObject conversion → (5) platformdirs paths + migration helper → (6) pytest-qt port → (7) mpris stub.

### Headless Qt Entry Point
- **D-05:** Create `musicstreamer/__main__.py` that instantiates `QCoreApplication`, constructs `Player`, and exposes a tiny script/REPL harness capable of playing a single ShoutCast URL so success criterion #1 ("App launches and GStreamer plays a stream with ICY title updating in terminal/log") can be verified by a live manual run, not only by tests.
- **D-06:** The existing GTK `main.py` entry point stays on disk but is NOT invoked during Phase 35 verification — it will be deleted in Phase 36 as part of PORT-04.

### GStreamer Bus Bridge (already locked by PORT-02)
- **D-07:** GStreamer bus routes to the Qt main thread via a `GLib.MainLoop` running on a daemon thread with `bus.enable_sync_message_emission()`. Bus messages are re-emitted as queued Qt signals via `Qt.ConnectionType.QueuedConnection`. No `QTimer` polling of the bus. This is a REQUIREMENTS-level decision — planner should treat it as fixed.
- **D-08:** Player timers currently using `GLib.timeout_add` (failover countdown, yt-dlp poll loop, cookie-retry one-shot) convert to `QTimer` with `singleShot` where appropriate. `GLib.source_remove` calls become `QTimer.stop()` / `deleteLater()`.

### mpris.py Disposition
- **D-09:** `mpris.py` is replaced with a no-op stub class exposing the same public interface (`MprisService`, its constructor, and any methods `main_window` calls on it). The stub accepts the same arguments and silently does nothing. No `dbus-python`, no `GLib`, no real D-Bus service registration during Phase 35–40. The real QtDBus rewrite is Phase 41 (MEDIA-02) and will replace this stub.
- **D-10:** `main_window.py` (GTK) callers of `MprisService` keep working against the stub interface so the GTK app still launches during the transition. When Phase 36 deletes GTK UI, the stub's callers are gone but the stub itself stays on disk, ready for Phase 41 to rewrite.
- **D-11:** Media keys are explicitly NOT functional after Phase 35 and will not be functional again until Phase 41. The stub logs a one-line debug warning on construction so this is discoverable.

### Data Paths — platformdirs (PORT-05)
- **D-12:** All hard-coded `~/.local/share/musicstreamer` literals are replaced with a single helper (e.g., `musicstreamer/paths.py`) that returns paths rooted at `platformdirs.user_data_dir("musicstreamer")`. Cover-art cache, SQLite DB, cookies file, Twitch token path, and accent CSS cache all route through this helper.
- **D-13:** The helper is pure (no I/O on import) so tests can monkeypatch the root directory cleanly.

### Data Migration Helper (PORT-06)
- **D-14:** A migration helper runs on first launch. On Linux, `platformdirs.user_data_dir("musicstreamer")` resolves to `~/.local/share/musicstreamer` — the same path as v1.5 — so the helper is effectively a no-op on Linux. The real cross-path migration logic is deferred until Windows install exists (Phase 44 UAT, or first actual Windows user).
- **D-15:** The helper still runs unconditionally and writes a marker file (`.platformdirs-migrated`) after a successful check so re-invocations short-circuit cheaply. This keeps the code path exercised during Phase 35 tests instead of sitting dead until Phase 44.
- **D-16:** The helper is NOT a destructive move. It copies if paths differ, then leaves the old location alone (non-destructive per PORT-06). On Linux (same path), it just writes the marker and returns.

### yt-dlp + streamlink Library API Port (PORT-09)
- **D-17:** `yt_import.py`'s playlist scan and single-video resolution move from `subprocess.Popen(['yt-dlp', ...])` to `yt_dlp.YoutubeDL({...}).extract_info(url, download=False)`. Flat-playlist extraction flags map to `{'extract_flat': 'in_playlist'}` options.
- **D-18:** `player._play_twitch()`'s `subprocess.run(['streamlink', '--stream-url', ...])` call moves to `streamlink.Streamlink().streams(url)` — picking the best available quality from the returned dict.
- **D-19:** `player._play_youtube()` currently launches mpv as a subprocess. Its fate is decided by the spike (D-20). If the spike succeeds, this path is deleted entirely and `playbin3` gets the yt-dlp-resolved URL directly. If the spike fails on any edge case, mpv stays as a fallback and a centralized `_popen()` helper (PKG-03) is introduced during Phase 35 for the remaining subprocess launches, pre-staged for Windows.

### mpv Spike (the deciding task)
- **D-20:** The spike verifies GStreamer `playbin3` can play yt-dlp library-resolved URLs across these cases: (a) normal YouTube live stream, (b) HLS manifest, (c) cookie-protected / age-gated stream using `cookies.txt`, (d) stream requiring a specific format selection (e.g., 720p live HLS). Each case is either PASS or FAIL with a one-line note.
- **D-21:** If ALL cases pass: mpv is removed entirely from `player.py`, `PKG-05` is retired in REQUIREMENTS.md, and no mpv subprocess launcher work ships in Phase 35.
- **D-22:** If ANY case fails: mpv stays as the YouTube fallback, the failing case(s) are documented as the retention reason, and PKG-05 remains active for Phase 44.
- **D-23:** Spike result is written to `.planning/phases/35-backend-isolation/35-SPIKE-MPV.md` and committed as the first artifact of the phase.

### Test Infrastructure — Big-bang pytest-qt Port (QA-02)
- **D-24:** Single plan task installs `pytest-qt` + `QT_QPA_PLATFORM=offscreen`, ports all 265 existing tests to pytest-qt conventions in one batch, and updates `conftest.py` to provide a `qapp` fixture.
- **D-25:** Tests that exercised GTK widgets directly (if any exist — scout during planning) either get rewritten against the headless Qt harness or get deferred to Phase 36–37 with a skip marker noting the deferral.
- **D-26:** Zero GTK imports are permitted in the test suite at end of Phase 35 (this enforces QA-02's "zero GTK imports" gate early — Phase 36 only has to delete GTK from production code).

### Claude's Discretion
- Specific QObject signal signatures (`Signal(str)` vs `Signal(object)` etc.) for title, failover, offline, and elapsed-timer events — pick whatever types give the clearest interface; planner + researcher decide.
- Exact module layout for `paths.py` (top-level `musicstreamer/paths.py` vs nested).
- Whether the `__main__.py` harness accepts a URL as a CLI arg or has a single hard-coded known-good URL for the smoke test.
- Whether the spike runs in CI or is a manual/local-only task.

### Folded Todos
None — no pending todos matched this phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap + Requirements
- `.planning/ROADMAP.md` §"Phase 35: Backend Isolation" — goal, depends-on, requirements list, success criteria
- `.planning/REQUIREMENTS.md` §"PORT — Backend isolation & Qt scaffold" — PORT-01, PORT-02, PORT-05, PORT-06, PORT-09 full text
- `.planning/REQUIREMENTS.md` §"QA — Port quality gates" — QA-02 text
- `.planning/PROJECT.md` — "Current Milestone: v2.0 OS Agnostic" section and "Key context" bullets (keep Python + GStreamer backend, retire GTK entirely)

### Existing code to touch
- `musicstreamer/player.py` — 355 lines; GLib.idle_add, GLib.timeout_add, subprocess.Popen for yt-dlp/mpv, subprocess.run for streamlink. Full rewrite target.
- `musicstreamer/yt_import.py` — 106 lines; subprocess-based yt-dlp flat-playlist extraction. Port to library API.
- `musicstreamer/mpris.py` — 170 lines; dbus-python + DBusGMainLoop. Replace with no-op stub.
- `musicstreamer/constants.py` — hard-coded data dir path literals. Route through new paths helper.

### Codebase maps (pre-existing, read for context)
- `.planning/codebase/STACK.md` — current stack (Python + GTK4/Libadwaita + GStreamer + SQLite + yt-dlp + streamlink + dbus-python)
- `.planning/codebase/ARCHITECTURE.md` — module boundaries and signal flow
- `.planning/codebase/CONVENTIONS.md` — thread-local DB connections, GLib.idle_add cross-thread pattern (both changing in this phase)
- `.planning/codebase/INTEGRATIONS.md` — external services (iTunes, Radio-Browser, AudioAddict, yt-dlp, streamlink)
- `.planning/research/STACK.md` — project research on the stack (check for Qt/PySide6 notes)

### External specs (researcher should consult)
- PySide6 / Qt signals and slots docs (`Signal`, `Slot`, `QObject`, `QCoreApplication`, `QTimer`, `Qt.ConnectionType.QueuedConnection`)
- `yt-dlp` Python API (`yt_dlp.YoutubeDL`, `extract_info`, `extract_flat`)
- `streamlink` Python API (`streamlink.Streamlink().streams()`)
- `platformdirs` docs (`user_data_dir`)
- GStreamer Python bindings — bus sync message emission, thread safety with non-GLib main loops

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Player class structure:** Existing `_on_title`, `_on_failover`, `_on_twitch_resolved` handler method names can stay — just change the dispatch mechanism from `GLib.idle_add(self._on_title, title)` to `self.titleChanged.emit(title)`.
- **Constants file:** `musicstreamer/constants.py` already centralizes paths — adding a `paths.py` helper follows the same pattern.
- **Daemon thread pattern:** `player.py` already uses daemon threads for Twitch streamlink resolution — same pattern applies to the new `GLib.MainLoop` bus bridge.

### Established Patterns
- **Thread-local DB connections** (`db_connect()`): Keep as-is; Qt signals don't change SQLite thread affinity. Future phases may revisit.
- **Module-level caches** (`_last_cover_icy`, `last_itunes_result`): Unaffected — these live outside the threading conversion.
- **GLib.idle_add as cross-thread UI update:** This is the pattern being REPLACED this phase. Every call site needs conversion to a Qt signal.

### Integration Points
- `main.py` (current entry point) → will NOT be the Phase 35 entry. Phase 35 entry is `musicstreamer/__main__.py`.
- `main_window.py` → still alive as a GTK widget during Phase 35 (deleted in Phase 36). Its `MprisService` construction needs to keep working against the new stub.
- `mpris.py` stub must match the existing public interface exactly so no changes ripple into `main_window.py` or other callers.

### Constraints
- No `QApplication` (GUI) this phase — only `QCoreApplication` (headless). Any code path that accidentally requires widgets will fail verification.
- `pytest-qt` needs the offscreen platform so CI and headless runs work: `QT_QPA_PLATFORM=offscreen`.
- `PySide6.QtDBus` is available but NOT used this phase — it's reserved for Phase 41.

</code_context>

<specifics>
## Specific Ideas

- User explicitly wants Option A (Qt-first backend), meaning QObject conversion happens in Phase 35 even though the visible Qt UI is Phase 36.
- User accepts that media keys are non-functional between end of Phase 35 and Phase 41 — mpris stub is fine.
- Spike runs first so its outcome informs the rest of the phase's task list.

</specifics>

<deferred>
## Deferred Ideas

- **QtDBus MPRIS2 rewrite** → Phase 41 (MEDIA-02), already scoped
- **Qt UI scaffold + GTK delete + icon bundling** → Phase 36 (PORT-03, PORT-04, PORT-07, PORT-08)
- **Real Windows platformdirs migration path (source != destination)** → validated in Phase 44 Windows packaging when a Windows user actually exists
- **`_popen()` CREATE_NO_WINDOW helper (PKG-03)** → Phase 44, unless the mpv spike fails in which case Phase 35 introduces a minimal version for mpv only

</deferred>

---

*Phase: 35-backend-isolation*
*Context gathered: 2026-04-11*
</content>
</invoke>