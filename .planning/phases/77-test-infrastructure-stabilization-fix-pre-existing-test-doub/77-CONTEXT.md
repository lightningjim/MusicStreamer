# Phase 77: Test infrastructure stabilization — fix pre-existing test-double drift & teardown crashes - Context

**Gathered:** 2026-05-16
**Status:** Ready for planning (discussion skipped — see §Discussion Disposition)

<domain>
## Phase Boundary

Phase 77 cleans up the standing inventory of **pre-existing test failures** that have been carried in `deferred-items.md` files across at least 10 prior phases (51, 54, 55, 60.4, 61, 65, 66, 68, 71, 72, 72.1, 73). The goal is a **clean full-suite `pytest tests/` run** so future phases stop re-logging the same noise as deferred items.

The failures fall into **six discrete clusters**, every one verified pre-existing on each surfacing phase's base commit (multiple `git stash` bisects on record). Each cluster has a well-understood root cause; none requires user-vision input.

**In scope (six clusters):**

1. **FakePlayer test-double drift (Phase 62 carry-over).** `musicstreamer/ui_qt/main_window.py:391` connects to `self._player.underrun_recovery_started` (added in Phase 62 commit `b60e86c`), but **10 of the 12** `_FakePlayer` / `FakePlayer` stubs across `tests/` never grew the corresponding `Signal()` — only `tests/test_main_window_integration.py` (line 41) and `tests/test_main_window_gbs.py` (line 33) have it. Construction of any `MainWindow` in tests using one of the stale stubs raises `AttributeError: '_FakePlayer' object has no attribute 'underrun_recovery_started'`. Affected (per phase 65 + 71 + 73 deferred-items audits): `tests/test_ui_qt_scaffold.py`, `tests/test_main_window_media_keys.py`, `tests/test_main_window_soma.py`, `tests/test_now_playing_panel.py`, `tests/test_phase72_now_playing_panel.py`, `tests/test_phase72_1_stream_picker_reflow.py`, `tests/ui_qt/test_main_window_node_indicator.py`, `tests/test_station_list_panel.py` (indirect — via MainWindow construction in the two named tests), plus the 7 mpris2 tests (cluster 2 below).

2. **MPRIS2 DBus name-collision in unit tests.** All 7 tests in `tests/test_media_keys_mpris2.py` fail with `RuntimeError: registerService('org.mpris.MediaPlayer2.musicstreamer') failed: name already taken or bus error`. Cause: `SERVICE_NAME = "org.mpris.MediaPlayer2.musicstreamer"` is a module-level constant in `musicstreamer/media_keys/mpris2.py:56`, the session bus is shared across the test process and any running MusicStreamer instance (and across parallel test workers), and there is no per-test suffix mechanism. The `# TODO: support unique-suffix for multi-instance` at `mpris2.py:256` documents the gap.

3. **Qt teardown aborts triggered by specific test-file orderings.** Three documented reproducers:
   - `tests/test_main_window_integration.py → tests/test_now_playing_panel.py` (Plan 72-04 deferred)
   - `tests/test_phase72_now_playing_panel.py → tests/test_phase72_assumptions.py` (Plan 72-03 deferred)
   - `tests/test_import_dialog_qt.py::test_yt_scan_passes_through` mid-suite (Plan 65-01/02 deferred)
   - `tests/test_main_window_underrun.py::test_first_call_shows_toast` (Phase 71 deferred — real `urllib.urlretrieve` on a worker thread races widget GC during EditStationDialog logo fetch)

   All four sites pass **in isolation**; the crash surfaces only when prior pytest-qt fixtures leave residual widget/thread state that interacts badly with the next test's setup. Stack trace consistently lands inside `QObjectPrivate::deleteChildren` / `_ZN7QWidgetD1Ev`.

4. **`_aa_quality` orphan AttributeError (Phase 56 carry-over).** `tests/test_import_dialog_qt.py::test_audioaddict_tab_widgets` (line 143) and `::test_audioaddict_quality_combo` (line 153) assert `dialog._aa_quality is not None`. Phase 56 commit `414e236` (`chore(aa-import): remove dead Quality dropdown`) deleted the widget but missed these two test assertions. Production code in `musicstreamer/ui_qt/import_dialog.py` has no `_aa_quality` attribute, no quality combo, no `--quality` arg threading — confirmed via grep at scout time. This is unambiguous test→impl drift (impl already shipped; tests are orphaned).

5. **`test_filter_strip_hidden_in_favorites_mode` + `test_refresh_recent_updates_list` mismatches** (`tests/test_station_list_panel.py:318` + `:504`):
   - `test_refresh_recent_updates_list` asserts `panel.recent_view.model().rowCount() == 3`, but `musicstreamer/ui_qt/station_list_panel.py:492` calls `self._repo.list_recently_played(5)`. The fake repo's `list_recently_played(n=3)` default plus the test's expectation (3 rows) vs the production limit (5) is the cause. Plan 68-04 deferred-items.md documents both directions of the fix.
   - `test_filter_strip_hidden_in_favorites_mode` (line 318) asserts `isVisibleTo(panel)` semantics across `QStackedWidget` page switches under `QT_QPA_PLATFORM=offscreen`. Page-0/page-1 visibility behavior on the offscreen platform may require an explicit `show()` after the `setCurrentIndex()` switch.

6. **`test_play_twitch_sets_plugin_option_when_token_present` (`tests/test_twitch_auth.py:68`).** Test asserts `session.set_plugin_option("twitch", "api-header", [...])`, but production at `musicstreamer/player.py:1156` calls `session.set_option("twitch-api-header", [...])`. This is test↔impl drift across the streamlink API rename — production code uses the **older** `set_option("twitch-api-header", ...)` form; test was authored against the **newer** plugin-scoped `set_plugin_option("twitch", "api-header", ...)` form. The Phase 31 docstring at `tests/test_twitch_auth.py:1-9` explicitly mentions "the new code calls `session.set_plugin_option('twitch', 'api-header', ...)` — scoped to the twitch plugin only (Pitfall 6)" — so the original intent was the scoped form, but production never converted. **Direction = impl follows test** is consistent with the documented intent.

**Out of scope:**

- **Refactoring `MainWindow.__init__` to take a Player protocol** — would shrink the FakePlayer surface but is unrelated to the bug fix; a future architecture phase.
- **Switching MPRIS2 to a different DBus binding** — `dbus-python` vs `QtDBus` etc. Phase 49 already chose `QtDBus`; this phase only patches the test-time collision, not the bus binding.
- **Re-introducing the AudioAddict quality dropdown UX** — Phase 56 deliberately removed it. Phase 77 deletes the orphan test assertions; if the UX is wanted back, file a new phase.
- **`pytest --forked` / `pytest-xdist` parallelism** — Phase 77 fixes test-state isolation defects in-place; whether parallelism is enabled later is a CI/devloop decision.
- **Backfilling tests for already-shipped Phase 62 / Phase 71 features** — Phase 77 only restores test-double parity with what already shipped; it does not add new assertions about Player behavior.
- **`PyGIDeprecationWarning: GLib.unix_signal_add_full`** (Phase 72 deferred-items.md). System-Python PyGI warning, not a MusicStreamer issue. Out of scope; logged in Phase 72 deferred-items.md already.
- **A new BUG / TEST / INFRA requirement ID in `.planning/REQUIREMENTS.md`** is a planner concern — planner adds an `INFRA-01` (or similar) row when scope-locking. The phase 77 roadmap entry has `**Requirements**: TBD`.

</domain>

<decisions>
## Implementation Decisions

### Discussion Disposition

- **D-00 [informational]:** **`/gsd-discuss-phase 77 --chain` invoked discussion was skipped by mutual agreement.** Rationale: Phase 77 is technical-cleanup heavy and light on user-vision. The "gray areas" identified during analyze_phase (FakePlayer canonicalization shape; MPRIS2 collision fix mechanism; Qt-teardown strategy; test vs impl drift direction per case) are exactly the kind of decisions the planner + researcher can resolve from full context, not user vision. User confirmed: "If discuss isn't recommended, we can move onto the planning phase." This CONTEXT.md is grounded in the prior-phase deferred-items.md audits (10+ phases) and direct codebase scout — every claim below is verifiable from the cited file paths.

### Failure-cluster scope (locked)

- **D-01 [informational]:** **All six clusters are in scope for this phase.** The roadmap goal — "clean full-suite `pytest tests/` run" — implies no failure left behind from the named list. Splitting into multiple phases would defeat the goal.

- **D-02 [informational]:** **Bar = `pytest tests/` exits 0 with no `xfail` / `skip` masking** for the six named clusters. If a fix genuinely cannot land in Phase 77 (e.g., needs a CI sandbox change), `<discretion>` allows the planner to scope-defer that one item with explicit `<deferred>` entry — but the default is "fix in this phase."

- **D-03 [informational]:** **Pre-existing failures NOT in the six-cluster list stay deferred.** If the planner discovers a 7th failure cluster during scope-lock, it goes into `<deferred>` for a follow-up phase. Don't silently expand scope.

### Test↔impl drift direction (locked per case)

For each of the three test↔impl drift items, the direction is locked here so the planner doesn't need to re-litigate:

- **D-04:** **`_aa_quality` cluster (cluster 4): test follows impl.** Phase 56 intentionally removed the quality dropdown (`chore(aa-import): remove dead Quality dropdown`, commit `414e236`). The two orphan assertions in `tests/test_import_dialog_qt.py` at lines 143 and 153 are deleted, plus any `_aa_quality`-typed references in nearby helpers. If the AudioAddict quality dropdown is wanted back, file a new feature phase — Phase 77 does not restore it.

- **D-05 (REVISED 2026-05-17 per 77-RESEARCH.md §Summary item 1):** **`set_plugin_option` cluster (cluster 6): test follows impl.** Streamlink removed `Streamlink.set_plugin_option()` entirely in **streamlink 6.0.0** (PR #5033, 2023-07-20). Project pins `streamlink>=8.3` and the installed copy is `8.3.0` — confirmed by direct CPython probe (`hasattr(Streamlink(), 'set_plugin_option')` → `False`). Production at `musicstreamer/player.py:1156` already uses the correct migrated API: `session.set_option("twitch-api-header", ...)`. The Phase 31 docstring at `tests/test_twitch_auth.py:1-9` is **stale 2-year-old documentation referring to a deleted API**. Fix: delete/rewrite the `set_plugin_option` assertion in `test_play_twitch_sets_plugin_option_when_token_present` (and the two sibling tests if they reference it), and update the stale module docstring. NO production-code change. Original CONTEXT.md text (committed before the streamlink probe) inverted the direction; this revision corrects it.

- **D-06:** **`recent_3_vs_5` cluster (cluster 5a): test follows impl.** `musicstreamer/ui_qt/station_list_panel.py:492` deliberately calls `list_recently_played(5)` — the production UX shows 5 recent rows (matches the "Recently Played" panel BROWSE-04 requirement in PROJECT.md). The test's expectation of 3 rows is incorrect. Update the test assertion to `== 5` (or to a count that doesn't hard-code the limit — planner picks).

### FakePlayer drift fix (shape locked, location partially open)

- **D-07:** **Canonicalize FakePlayer via a shared `tests/_fake_player.py` module + drift-guard test.** Per the recurring-drift evidence (10+ phases logged this same failure since Phase 62 shipped in 2026-05), one-off in-place patches keep failing — every new test file rolls its own stub and forgets a signal. A shared module with a single import line per test file solves the next round of drift. Mirrors the existing `tests/conftest.py` `_FakeRepo` / `_FakeStation` shared-double pattern (lines 102–207).

- **D-08 (REVISED 2026-05-17 per 77-RESEARCH.md §Summary item 2):** **Canonical signal set = every `Signal(...)` declared on `musicstreamer.player.Player`, checked by BOTH name AND argument arity.** Drift-guard imports both `musicstreamer.player.Player` and the shared `_FakePlayer`, walks `Player.__dict__` (NOT `dir(Player)` — `__dict__` excludes inherited `QObject` signals `destroyed`/`objectNameChanged` automatically; live probe: `dir()` returns 20, `__dict__` returns 18), filters by `isinstance(v, Signal)`, and asserts every entry is present on `_FakePlayer` with **matching argument arity**. Name-only comparison would silently allow the existing `audio_caps_detected` arity drift (production = `Signal(int, int, int)` at `player.py:282`; `tests/test_main_window_gbs.py:34` and `tests/test_main_window_soma.py:42` declare `Signal(object)`). Mirrors the project's established source-introspection drift-guard convention (Phase 79 Plan 04 `tests/test_yt_dlp_opts_drift.py`; Phase 69 Plan 05 `tests/test_packaging_spec.py`). Implementation note: PySide6 `Signal` arity is read via `Signal.__init__`-time stored tuple; planner picks the introspection mechanism (source-parse of `_fake_player.py` text vs PySide6 metadata) — research recommends source-parse with `ast.parse` for robustness.

- **D-09 (REVISED 2026-05-17 per 77-RESEARCH.md §Summary item 2):** **All 11 distinct fake-player sites switch to the shared import.** Original CONTEXT.md listed 12 entries but double-counted (`tests/test_phase72_now_playing_panel.py` and `tests/test_now_playing_panel.py` are distinct files but were tallied once each — actual grep re-run confirms 11 separate sites, all distinct). Live-verified enumeration: `tests/test_stream_picker.py:32`, `tests/test_discovery_dialog.py:39`, `tests/test_ui_qt_scaffold.py:16`, `tests/test_main_window_integration.py:31`, `tests/test_equalizer_dialog.py:40`, `tests/test_main_window_media_keys.py:54`, `tests/test_now_playing_panel.py:29`, `tests/test_main_window_soma.py:33`, `tests/test_phase72_now_playing_panel.py:34`, `tests/test_main_window_gbs.py:25`, `tests/test_phase72_1_stream_picker_reflow.py:79`, `tests/ui_qt/test_main_window_node_indicator.py:35`. (`test_equalizer_dialog.py` declares `class FakePlayer:` without `(QObject)` — planner decides whether to migrate it; if the equalizer dialog never connects Qt signals on the player it may stay non-QObject.) Each site loses its local class definition; tests import `from tests._fake_player import FakePlayer` (or planner-picked module name per `<discretion>`). **Two additional sites need an arity correction during migration**: `tests/test_main_window_gbs.py:34` and `tests/test_main_window_soma.py:42` both declare `audio_caps_detected = Signal(object)` — the shared `_fake_player.py` declaration uses the correct `Signal(int, int, int)` arity from production `player.py:282`, so swapping to the shared import auto-fixes the drift.

### MPRIS2 DBus name-collision fix

- **D-10:** **Per-test unique bus-name suffix via fixture-scoped monkeypatch of `SERVICE_NAME`.** Each `LinuxMprisBackend` test patches `musicstreamer.media_keys.mpris2.SERVICE_NAME` to `f"org.mpris.MediaPlayer2.musicstreamer.test_{os.getpid()}_{uuid4().hex[:8]}"` before constructing the backend. Teardown unregisters the unique name. This is the lowest-blast-radius fix: no production-code change, no env-var contract, no new constructor kwarg. Future planner can revisit if multi-instance support genuinely needs an env-var path (the existing TODO at `mpris2.py:256` can stay for that future work).

- **D-11:** **Teardown unregisters explicitly on test exit.** Even with a unique suffix, leaking name binds across a pytest run is wasteful. Fixture pattern: `yield backend; backend.shutdown(); bus.unregisterService(SERVICE_NAME)` (with a try/except guard for collisions during shutdown).

### Qt teardown crash strategy

- **D-12 (REVISED 2026-05-17 per 77-RESEARCH.md §Summary item 5):** **Block real network calls in tests via per-test `monkeypatch.setattr` (option a, locked).** Live investigation showed the daemon thread that races widget GC is `cover_art._itunes_attempt`'s `threading.Thread(daemon=True)`, NOT just `urllib.urlretrieve`. **The monkeypatch must cover BOTH `urllib.request.urlretrieve` AND `urllib.request.urlopen`** (the cover-art path uses `urlopen` for the iTunes Search API call; the logo-fetch path uses `urlretrieve`). Patch surface per test:
  - `monkeypatch.setattr("urllib.request.urlretrieve", lambda *a, **kw: None)` — return-nothing stub
  - `monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: io.BytesIO(b""))` — empty-response stub (or a `MagicMock` if the consumer needs `.read()` / `.status`)

  pytest-socket (option b) is researched and rejected: legitimate package (11.3M downloads/month) but introduces a project-wide gate that integration tests under `tests/integration/` would have to opt out of, plus a new dev dependency. Per-test monkeypatch is the surgical fix consistent with `tests/test_cookies.py`'s `paths._root_override` pattern.

- **D-13 [informational]** (scope-deferred per `<discretion>` 2026-05-17)**:** **Cover-art worker thread teardown.** The `test_main_window_integration.py → test_now_playing_panel.py` and `test_phase72_now_playing_panel.py → test_phase72_assumptions.py` crashes share a common signature with the Plan 72-02 "cover-art worker thread, signal-source-deleted race" diagnosis. **Original direction:** fix at the production-code layer (cover-art worker awaits `wait()` before parent-widget destructor, or unparents itself in `finished`); mirrors Phase 68's existing cover-art worker pattern (`closeEvent` calls `worker.wait(16000)`). **2026-05-17 planner disposition:** scope-deferred to a follow-up phase per `<discretion>` clause below — Phase 77 fixes only the network-call leak (D-12) and the worker-teardown race (D-14) test-side. The cross-file Qt-teardown production refactor moves to a future "test infrastructure follow-up" phase. Plan 77-05 `<objective>` documents the deferral and its justification.

- **D-14:** **`test_yt_scan_passes_through` Qt teardown abort.** Fixture cleanup ordering across the ~40+ pytest-qt files that run before `tests/test_import_dialog_qt.py` is the trigger. Planner investigates the `_YtScanWorker` cleanup in `tests/test_import_dialog_qt.py:234` — ensure `worker.deleteLater()` is called, or `qtbot.waitSignal(worker.finished)` is followed by an explicit join. If the leak is structural in `_YtScanWorker` itself, fix it in production code (mirror Plan 72-02's cover-art worker fix).

- **D-15 (REVISED 2026-05-17 per 77-RESEARCH.md §Summary item 3):** **`isVisibleTo()` failure is NOT an offscreen-platform quirk** — live probe confirmed `isVisibleTo()` works correctly under `QT_QPA_PLATFORM=offscreen`. Root cause: the test never calls `panel.show()` (only `qtbot.addWidget(panel)`), and `isVisibleTo()` returns False on any widget whose top-level was never shown — regardless of platform. **Fix locked: option (b)** — replace `assert panel._search_box.isVisibleTo(panel)` with the semantic equivalent `assert panel._stack.currentIndex() == 0` (page 0 contains the search box; page-active state IS effective visibility). No `panel.show()` / `qtbot.waitExposed()` needed; the test stays event-loop-free. Single-line diff per assertion at `tests/test_station_list_panel.py:326` and `:332`.

### Drift-guard regression test (locks the recurrence shape)

- **D-16 (REVISED 2026-05-17 per 77-RESEARCH.md §Summary item 2):** **Drift-guard pytest in `tests/test_fake_player_signal_parity.py` — checks name AND argument arity.** Imports `musicstreamer.player.Player`, walks `Player.__dict__` filtering by `isinstance(v, Signal)`, then imports `tests._fake_player.FakePlayer` and asserts every Player signal is present on FakePlayer as a `Signal`-typed attribute **with matching argument arity** (source-parse the FakePlayer module text via `ast.parse` to read the arg-list of each `Signal(...)` call; cross-check against the production `Signal(...)` declaration via the same source-parse on `musicstreamer/player.py`). The arity check catches the existing `audio_caps_detected` arity drift (`Signal(int, int, int)` in production vs `Signal(object)` at gbs/soma sites) plus any future arity changes. Name-only comparison was the original D-16 shape but research showed it silently misses real drift; the source-parse form is the locked shape.

- **D-17:** **Source-grep drift-guard pytest in `tests/test_fake_player_no_inline.py`.** Walks `tests/test_*.py` and `tests/ui_qt/test_*.py`, greps each for `class\s+_?FakePlayer\s*\(QObject\)` patterns; allows ONLY `tests/_fake_player.py` to define one. Any new inline FakePlayer class fails the test immediately. Pattern matches the existing `tests/test_yt_dlp_opts_drift.py` (Phase 79 Plan 04) and Phase 69 `tests/test_packaging_spec.py` shape.

- **D-18:** **MPRIS2 SERVICE_NAME-monkeypatch helper.** Lives next to other shared test helpers (planner picks `tests/_fake_player.py` or a new `tests/_mpris_helpers.py`). Single fixture `unique_mpris_service_name(monkeypatch)` that yields the suffixed string; tests use it via `@pytest.fixture` injection.

### Claude's Discretion

- **Shared-module filename** — `tests/_fake_player.py` is the working name. Planner may prefer `tests/_test_doubles.py` (grouped with future Fake* doubles), `tests/_player_double.py`, or extension of `tests/conftest.py` (with `@pytest.fixture` instead of a class import). Recommendation: `tests/_fake_player.py` — focused, easy to grep-ban inline copies (D-17).
- **MPRIS2 name suffix format** — `test_{pid}_{uuid8}` is the working form. Planner may pick a shorter form or rely on `uuid4().hex` alone if pid info isn't needed for debugging. Single-format consistency is all that matters.
- **`pytest-socket` adoption** (D-12 option b) — judgment call between dependency cost and global safety. If planner picks (b), update `pyproject.toml` `dependencies` and `[tool.pytest.ini_options]`, plus an allowlist for the integration tests under `tests/integration/`.
- **Whether `LinuxMprisBackend` shutdown gets a behavior change** — D-11 fixture-side unregister is the default. If planner discovers the production `shutdown()` already does this and the fixture-side call is redundant, drop the fixture-side call.
- **Cover-art worker fix scope** (D-13) — if the fix is non-trivial and the planner judges Phase 77 shouldn't carry a production-code refactor of `cover_art_worker` (or whatever owns the worker), the planner may scope-defer the cross-file Qt-teardown crashes to a new "test infrastructure follow-up" phase, fixing only the network-call leak (D-12) in Phase 77. Decision lives with the planner after they read the worker code.
- **Plan ordering** — natural grouping is `[FakePlayer shared module + drift-guards] → [MPRIS2 monkeypatch] → [test↔impl drift fixes] → [Qt-teardown / network-block]`, ending with a `tests/ -x` full-suite green verification plan. Planner finalizes the wave structure and dependencies.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements

- `.planning/ROADMAP.md` line 828 — Phase 77 entry with the seven named failure sites. The recurring-cluster phase list (51, 54, 55, 60.4, 61, 65, 66, 68, 71, 72, 72.1, 73) lives in the goal sentence.
- `.planning/REQUIREMENTS.md` — no Phase 77 entry yet. Planner adds a row (e.g., `INFRA-01` or `BUG-12`) when scope-locking.
- `.planning/PROJECT.md` line 53 — `Tests: 399 passing, 1 pre-existing failure` (the `_aa_quality` orphan, now widely-known to be undercounted — true number is 35+ failures + 18+ setup errors per Phase 71 audit). Planner updates this line at phase close.

### Pre-existing-failure audit trail (READ FIRST — Phase 77 closes these)

- `.planning/phases/71-sister-station-expansion-1-add-ability-to-link-sister-statio/deferred-items.md` — **canonical inventory**. Plan 71-08 Task 4 audited the full pytest run on the Phase 71 base commit and produced a complete breakdown by cluster (A: FakePlayer drift, B: DBus collision, C: `_aa_quality`, D: `test_main_window_underrun` real-network crash). Most actionable single source.
- `.planning/phases/65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb/deferred-items.md` — FakePlayer-drift list cross-checked; documents the `test_yt_scan_passes_through` Qt-teardown abort.
- `.planning/phases/68-add-feature-for-detecting-live-performance-streams-di-fm-and/deferred-items.md` — recent-3-vs-5 + QStackedWidget visibility specifics, with both directions of the fix proposed.
- `.planning/phases/72-fullscreen-mode-hide-left-column-for-compact-displays/deferred-items.md` — Qt teardown crash crossing `test_main_window_integration → test_now_playing_panel` (Plan 72-04) and `test_phase72_now_playing_panel → test_phase72_assumptions` (Plan 72-03). Plus the PyGIDeprecationWarning (out of scope per `<domain>`).
- `.planning/phases/73-musicbrainz-album-cover-lookup-complement-itunes-with-smart-/deferred-items.md` — `_aa_quality` + FakePlayer drift + hamburger-indicator failure; covers the `tests/ui_qt/test_main_window_node_indicator.py` sub-directory site.
- `.planning/phases/72.1-stream-selector-dropdown-overlap-persists-in-fullscreen-mode/deferred-items.md` — `tests/test_main_window_integration.py::test_hamburger_menu_actions` failure surfaced during Plan 72.1-02 Task 3.

### Production-code sites Phase 77 touches

- `musicstreamer/player.py:241-282` — canonical `Signal()` set on `Player`. Source of truth for the FakePlayer drift-guard (D-08). Includes `underrun_recovery_started = Signal()` at line 277.
- `musicstreamer/player.py:1156-1159` — `session.set_option("twitch-api-header", ...)` site. D-05 switches this to `session.set_plugin_option("twitch", "api-header", ...)`.
- `musicstreamer/ui_qt/main_window.py:391-392` — `self._player.underrun_recovery_started.connect(...)` — the line that makes FakePlayer drift fatal in test construction.
- `musicstreamer/ui_qt/station_list_panel.py:492` — `self._repo.list_recently_played(5)` site. D-06 says test follows impl; this line stays as-is.
- `musicstreamer/media_keys/mpris2.py:56` — `SERVICE_NAME = "org.mpris.MediaPlayer2.musicstreamer"` constant. D-10 monkeypatches this in tests.
- `musicstreamer/media_keys/mpris2.py:254-261` — `registerService(SERVICE_NAME)` call site + the existing `# TODO: support unique-suffix for multi-instance` comment that documents the gap.

### Tests Phase 77 modifies

- `tests/conftest.py` — shared-double pattern reference (`_FakeRepo`, `_FakeStation`, `_FakeStream` already live here, lines 102–207). Phase 77 adds either a new sibling module `tests/_fake_player.py` or extends conftest with `@pytest.fixture fake_player`.
- `tests/test_import_dialog_qt.py:141-154` — `_aa_quality` orphan assertions; D-04 deletes these.
- `tests/test_twitch_auth.py:1-9, 68-86` — docstring documents the original scoped-plugin-option intent; D-05 makes production match.
- `tests/test_station_list_panel.py:318-333, 504-520` — both QStackedWidget visibility + recent-3-vs-5 sites.
- `tests/test_media_keys_mpris2.py` — 7 tests + their fixtures get the unique-name patch (D-10).
- `tests/test_main_window_underrun.py::test_first_call_shows_toast` — D-12 network-call sandbox site.
- The 12 FakePlayer sites enumerated in D-09.

### Project conventions (apply during planning)

- **Source-grep / introspection drift-guards** are the established project pattern for protocol-required invariants. Precedents:
  - `tests/test_yt_dlp_opts_drift.py` (Phase 79 Plan 04) — single-call-site grep gate
  - `tests/test_packaging_spec.py` (Phase 69) — DLL/plugin presence assertions
  - Memory `feedback_gstreamer_mock_blind_spot.md` — protocol-required literals must be testable at source level
- **`tests/_*.py` underscore-prefix** for non-test helper modules. Confirmed in tree: `tests/__init__.py` exists, and `tests/conftest.py` uses underscore-prefixed classes; planner picks `tests/_fake_player.py` to match.
- **`QT_QPA_PLATFORM=offscreen`** is set in `tests/conftest.py:13` before any PySide6 import. All Qt-teardown investigations happen under this platform.
- **`uv run` is the test runner per `CLAUDE.md` constraints.** Planner's verification commands use `uv run pytest tests/` (NOT bare `pytest`, NOT system pip).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`tests/conftest.py` `_FakeRepo` / `_FakeStation` / `_FakeStream` pattern** (lines 102–207) — exact shape Phase 77 mirrors for the shared `FakePlayer`. Module-level class definitions with sensible defaults; opt-in via fixture or direct import.
- **`musicstreamer/player.py:241-282` Player Signal block** — already nicely grouped with comments. Easy target for `Player.__dict__` introspection in the drift-guard test.
- **`tests/test_main_window_integration.py:31-50` FakePlayer (lines 41 mentions `underrun_recovery_started`)** and **`tests/test_main_window_gbs.py:25-40`** — the two existing fakes that DO have the Phase 62 signal. Either serves as the seed for the shared module (Phase 77 picks the more complete of the two and uses it as `tests/_fake_player.py` base).
- **`tests/_fake_player.py` does not exist yet** — confirmed via `ls tests/_FakePlayer.py 2>/dev/null` returning empty. New file.

### Established Patterns

- **Shared test doubles live in `tests/conftest.py` as module-level classes**, exposed via `@pytest.fixture` for opt-in use OR by direct import. Phase 60 added the GBS-related fakes this way (`_FakeStation` at line 102, etc.). Phase 77 follows the same pattern.
- **Drift-guards as tests, not as CI scripts** — every project drift-guard is a `tests/test_*_drift.py` (or similar) that runs as part of `pytest tests/`. No separate CI step. Phase 77's two new drift-guard tests (D-16, D-17) follow this.
- **Source-introspection over fragile string matching** — D-08's "walk `Player.__dict__` for Signal-typed attributes" approach is more robust than regex-grepping `tests/_fake_player.py` for `= Signal(`. Mirrors the Phase 79 `build_js_runtimes` call-count drift-guard which uses AST parsing.
- **Monkeypatch over env-var contracts for test-time constant overrides** — D-10 uses `monkeypatch.setattr(mpris2, "SERVICE_NAME", ...)` not env-var indirection. Matches `tests/test_cookies.py`'s `paths._root_override` pattern.

### Integration Points

- **`MainWindow.__init__` constructor signature** is the consumer of every FakePlayer. D-09's import switch is a single-line change per test file: replace `class FakePlayer(QObject): ...` with `from tests._fake_player import FakePlayer`. Hot-path test files all instantiate via `MainWindow(player=FakePlayer(), repo=FakeRepo(), ...)`.
- **`LinuxMprisBackend.__init__`** is the consumer of `SERVICE_NAME`. The monkeypatch happens at the `musicstreamer.media_keys.mpris2` module level, so all callers within that test fixture see the unique name. The production `__main__.py` path is unaffected.
- **Cover-art worker (`musicstreamer/cover_art*.py`)** — needs read by the planner during D-13 investigation. The Phase 68 `_AaLiveWorker` `closeEvent` → `worker.wait(16000)` pattern is the analogue.
- **`_YtScanWorker` (`musicstreamer/ui_qt/import_dialog.py`)** — needs read by the planner during D-14 investigation. Same "worker leaks past widget GC" shape.

</code_context>

<specifics>
## Specific Ideas

- **"Fix it once, prevent it forever" priority.** Phase 71's deferred-items audit notes the same FakePlayer drift has been logged in ~10 phases since Phase 62 shipped. The drift-guard tests (D-16, D-17) are the actual user-facing value of Phase 77 — they're what stop the recurrence. The in-place fixes are merely the price of admission to install the guards.
- **Bias toward shared doubles**, mirroring `tests/conftest.py`'s existing `_FakeRepo` shape. The user has historically pushed for shared test fixtures (memory: `feedback_gstreamer_mock_blind_spot.md` — protocol-required literals must be testable at source level).

</specifics>

<deferred>
## Deferred Ideas

- **Refactoring `MainWindow.__init__` to accept a Player protocol** (vs concrete `Player` / `FakePlayer`) — shrinks the test-double surface; future architecture phase.
- **Switching to `pytest-xdist` parallel test runs** — would require deeper test-isolation work than Phase 77 needs; revisit when CI runtime becomes a pain.
- **Re-introducing AudioAddict quality dropdown UX** — Phase 56 removed it deliberately. If wanted back, file a new feature phase.
- **Multi-instance MPRIS2 support via env-var bus suffix** (the existing `mpris2.py:256` TODO) — Phase 77 only fixes test-time collision via monkeypatch. Production multi-instance remains a future feature.
- **Backfilling missing tests for Phase 62 underrun behavior** — Phase 77 only restores test-double parity with what already shipped; Phase 78 (BUG-09 behavior fix) is the right home for new underrun tests.
- **PyGIDeprecationWarning fix** — system-Python issue, not MusicStreamer. Out of scope; remains logged in Phase 72 deferred-items.md.

</deferred>

---

*Phase: 77-test-infrastructure-stabilization-fix-pre-existing-test-doub*
*Context gathered: 2026-05-16*
