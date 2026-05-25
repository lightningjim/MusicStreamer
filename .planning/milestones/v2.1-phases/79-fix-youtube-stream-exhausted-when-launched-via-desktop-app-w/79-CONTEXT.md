# Phase 79: Fix YouTube 'stream exhausted' when launched via desktop app (works via pipx/dev script) - Context

**Gathered:** 2026-05-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 79 fixes a single root cause: when MusicStreamer is launched via the GNOME `.desktop` entry (`Exec=musicstreamer`), the systemd-session-inherited PATH does NOT include version-manager shims (fnm / nvm / volta / asdf). `runtime_check.check_node()` already falls back to `$HOME`-rooted layouts (commit `a06549f`, 2026-04-25) — so the "Install Node.js" warning correctly stays silent — but `Player._youtube_resolve_worker` passes `js_runtimes={"node": {"path": None}}` to `yt_dlp.YoutubeDL`. With `path=None`, yt-dlp does its OWN PATH lookup, which fails under the .desktop launch context. JS-requiring YouTube streams then return "No video formats found!" → `_try_next_stream()` drains the failover queue → emits `failover(None)` → user sees "Stream exhausted." Pipx-from-terminal works because the terminal-inherited PATH carries the version-manager shims.

The fix threads the resolved Node executable path from `runtime_check.NodeRuntime` into both yt-dlp call sites (`Player._youtube_resolve_worker` and `yt_import.scan_playlist`) via dependency injection. A new tiny module `musicstreamer/yt_dlp_opts.py` owns the `js_runtimes` opts builder so both sites share a single source of truth. No PATH augmentation, no behavioral change for installations where Node really is on PATH (pipx-from-terminal, dev `uv run`).

**In scope:**

- **`musicstreamer/yt_dlp_opts.py` (new module)** — single narrow helper that builds the `js_runtimes` opts dict from a `NodeRuntime`. Returns `{"node": {"path": node_runtime.path}}` when `node_runtime` is not None and has a resolved path; returns `{"node": {"path": None}}` when `node_runtime` is None or its path is None (preserves today's "yt-dlp does its own PATH lookup" behavior for non-Node-resolved cases). Strictly scoped to `js_runtimes` — does NOT own `format`, `remote_components`, `quiet`, `skip_download`, `cookiefile`, or the playlist-scan-specific `extract_flat` options.
- **`musicstreamer/player.py::Player.__init__`** — grows a `node_runtime: NodeRuntime | None = None` kwarg (mirror `MainWindow.__init__`'s existing pattern at `main_window.py:195-202`). Stored on `self._node_runtime`. Default None preserves backwards-compat for existing test call sites and the smoke harness (`__main__._run_smoke`) which doesn't need YouTube.
- **`musicstreamer/player.py::_youtube_resolve_worker`** — replaces the inline `"js_runtimes": {"node": {"path": None}}` literal with `yt_dlp_opts.build_js_runtimes(self._node_runtime)`. Adds one INFO log line per YT play: `_log.info("youtube resolve: node_path=%s", <abs_path_or_None>)`. Mirror Phase 62's `musicstreamer.player` INFO-level pattern (already configured in `__main__.main` at line 235).
- **`musicstreamer/__main__.py::_run_gui`** — passes `node_runtime=node_runtime` to `Player()` constructor (the existing `node_runtime` is detected at line 215, currently flows only to `MainWindow`).
- **`musicstreamer/yt_import.py::scan_playlist`** — grows a `node_runtime: NodeRuntime | None = None` kwarg. Internal `_build_opts()` uses `yt_dlp_opts.build_js_runtimes(node_runtime)` instead of the inline literal at `yt_import.py:73-ish`. Existing `cookies_path` kwarg stays unchanged.
- **`musicstreamer/ui_qt/import_dialog.py` (YouTube tab)** — the call site for `scan_playlist`. Threads `node_runtime` through from `MainWindow._node_runtime` (already stored) to `scan_playlist(..., node_runtime=self._main_window._node_runtime)` or via dialog constructor kwarg (planner picks the cleanest threading).
- **Unit tests** — `tests/test_player.py` gets a regression test: construct `Player(node_runtime=NodeRuntime(available=True, path="/fake/node"))`, monkeypatch `yt_dlp.YoutubeDL` to record opts, call `_youtube_resolve_worker("https://www.youtube.com/...")`, assert `recorded_opts["js_runtimes"]["node"]["path"] == "/fake/node"`. Mirror for `node_runtime=None` (asserts `path: None`) and `node_runtime=NodeRuntime(available=False, path=None)` (asserts `path: None`). `tests/test_yt_import_library.py` gets the same matrix for `scan_playlist`. New `tests/test_yt_dlp_opts.py` covers the helper directly: three inputs (None / available with path / unavailable with None path) → expected dicts.
- **Linux + Windows** — single code path. `runtime_check._which_node` already resolves `node.exe` on Windows and returns the absolute path; threading it through yt-dlp opts costs nothing extra and pre-empts a parallel Windows bug surface.

**Out of scope:**

- **`os.environ['PATH']` augmentation at startup** — explicitly rejected (D-01). The surgical `js_runtimes` change fully addresses the reported bug; a process-wide PATH mutation would change behavior for every other subprocess (streamlink, oauth_helper) without a demonstrated need. If a future phase surfaces a parallel bug for streamlink under .desktop, revisit.
- **Short-circuit when Node is absent** — explicitly rejected (D-02). Some YouTube streams resolve without invoking the JS runtime (live HLS manifests, unauthenticated paths). Pre-emptively failing them when `node_runtime.available=False` would regress those cases. Behavior on the absent branch stays as today (`path: None`, yt-dlp tries and may succeed or fail).
- **New toast category for the "Node found via fallback but yt-dlp rejected it" case** — rejected (D-09). After the fix, that case shouldn't happen by construction; defending against a hypothetical future regression isn't worth a new toast branch. Existing `MainWindow._on_playback_error` toast nudge (`main_window.py:809-815`) continues to cover the genuinely-absent case unchanged.
- **Owning `remote_components`, `format`, `cookiefile`, or any other yt-dlp opt** in the new module — rejected (D-07). `yt_dlp_opts.py` is narrowly scoped to `js_runtimes`. Player and yt_import use yt-dlp differently (single-video resolve vs `extract_flat` playlist scan); centralizing every opt would couple the two sites' needs unnecessarily.
- **Diagnostic-only / log-first phase** — root cause is confirmed by user observation (root-cause question), code inspection (`a06549f` commit message documents the .desktop PATH gap), and the smoking gun in `player.py:1063` (`path: None`). Skipping straight to the fix.
- **Re-probing for non-PATH env diffs between .desktop and pipx-from-terminal** — out of scope. The user confirmed root cause; if a parallel env diff surfaces later (LANG, XDG_RUNTIME_DIR, cookies path resolution under .desktop, etc.), file a new phase.
- **Changes to `runtime_check.check_node()` or `_which_node_version_manager_fallback`** — kept as-is. Both already work correctly; the bug is downstream of them (Player doesn't consume their result for yt-dlp).
- **Phase 78 dependency** — ROADMAP says Phase 79 depends on Phase 78. Phase 78 is "Buffer underrun behavior fix" (Phase 62 follow-up) — orthogonal to YouTube resolve. The dependency may be order-of-shipping only; planner confirms there's no actual code coupling. If Phase 78 isn't done at plan time, planner notes whether to wait or proceed.

</domain>

<decisions>
## Implementation Decisions

### Fix mechanism

- **D-01:** **Pass resolved node path into yt-dlp opts.** Replace the inline `{"node": {"path": None}}` literal at `player.py:1063` and the parallel literal in `yt_import.py` with a call to a shared helper that reads from `NodeRuntime.path`. Rejected: `os.environ['PATH']` augmentation (too broad), belt-and-braces both (unnecessary code surface).
- **D-02:** **When `node_runtime.path` is None (Node genuinely not installed), preserve today's `{"path": None}` behavior.** yt-dlp may still resolve JS-free streams (live HLS manifests, etc.); short-circuiting would regress those. The helper returns `{"node": {"path": None}}` for the `node_runtime=None` and `node_runtime.path=None` cases.
- **D-03:** **Single code path for Linux and Windows.** No `sys.platform` gate; `NodeRuntime.path` is already platform-aware (`_which_node` prefers `node.exe` on Windows). Threading the path through on both platforms pre-empts a future Windows-launcher bug at zero extra cost.
- **D-04:** **Regression-test bar = unit test asserting `opts["js_runtimes"]["node"]["path"] == <injected abs>`.** Monkeypatch `yt_dlp.YoutubeDL` to record opts; assert equality. No env-PATH integration test, no live UAT-only — unit test catches future regressions cheaply and the live UAT remains as the verification gate. Matrix covers three NodeRuntime inputs (None / available+path / unavailable+None).

### Plumbing route

- **D-05:** **`Player.__init__` grows `node_runtime: NodeRuntime | None = None` kwarg.** Mirrors the existing `MainWindow.__init__(node_runtime=None)` pattern at `main_window.py:195-202`. Dependency injection: testable, no hidden global state. Rejected: module-level cache in `runtime_check` (hidden state), Player calls `check_node()` itself (couples Player to runtime_check + risks redundant probes on every YT play).
- **D-06:** **`node_runtime=None` is the default.** Backwards-compat for `_run_smoke` (which constructs `Player()` directly and doesn't need YouTube) and any existing tests. `_youtube_resolve_worker` reads `self._node_runtime` and falls back to `{"path": None}` when None. Rejected: required kwarg (breaks tests + smoke harness for no benefit).
- **D-07:** **`__main__._run_gui` passes the existing `node_runtime` to `Player()`.** The detection at `__main__.py:215` (`node_runtime = runtime_check.check_node()`) already runs before MainWindow construction. Threading it to Player too is a single-line change at the `Player()` constructor call.
- **D-08:** **`yt_import.scan_playlist` grows a `node_runtime: NodeRuntime | None = None` kwarg.** Same dependency-injection shape as Player. The Import dialog (`ui_qt/import_dialog.py` YouTube tab) threads `node_runtime` from `MainWindow._node_runtime` through to the call site. Default None for parity with `Player`.

### yt_import parity

- **D-09:** **Fix BOTH yt-dlp call sites in this phase.** The playlist-import dialog (`ImportDialog` YouTube tab → `yt_import.scan_playlist`) has the same bug under `.desktop` launches. Leaving it for a follow-up would intentionally ship a known bug. Planner adds both sites to scope.
- **D-10:** **New module `musicstreamer/yt_dlp_opts.py` is the single source of truth for `js_runtimes`.** Public surface: `build_js_runtimes(node_runtime: NodeRuntime | None) -> dict`. Both `player.py` and `yt_import.py` import from it. Matches the project's pattern of focused tiny modules (`cookie_utils`, `url_helpers`, `runtime_check`, `subprocess_utils`).
- **D-11:** **Helper is strictly scoped to `js_runtimes`.** Does NOT own `format`, `remote_components`, `quiet`, `skip_download`, `cookiefile`, `extract_flat`. Those legitimately differ between the resolve path (single-video) and scan path (playlist with `extract_flat`). Centralizing them would couple unrelated decisions.

### Error visibility

- **D-12:** **Keep existing `_on_playback_error` toast machinery; no new branch.** The "Install Node.js for YouTube playback" toast (`main_window.py:809-815`) continues to cover the genuinely-absent case. After the fix, the "found via fallback but yt-dlp rejected it" case is structurally eliminated — defending against a hypothetical future regression isn't worth the maintenance.
- **D-13:** **Add ONE INFO log line per YT play in `_youtube_resolve_worker`** showing the resolved node path: `_log.info("youtube resolve: node_path=%s", <abs|None>)`. Mirrors Phase 62 BUG-09's INFO-level cycle_close pattern (`musicstreamer.player` is already at INFO via `__main__.main:235`). Lets future-Kyle grep the log on the live machine to verify what yt-dlp got. Same INFO line added to `yt_import.scan_playlist` for the import path.

### Claude's Discretion

- **Helper function name** — `build_js_runtimes(node_runtime)` is the working name. Planner may pick `js_runtimes_opts` or `build_node_js_runtimes` if it reads better. Single function; not a class.
- **Where the import dialog threads `node_runtime`** — via the dialog constructor (`ImportDialog(parent, repo, ..., node_runtime=...)`) vs accessing `parent._node_runtime` directly inside the YouTube tab handler. Recommendation: constructor kwarg for explicitness, but planner picks whichever is least invasive given existing dialog construction in `MainWindow`.
- **Test fixture for `NodeRuntime`** — direct `NodeRuntime(available=True, path="/fake/node")` literals vs a small `@pytest.fixture` helper. Recommendation: inline literals; the dataclass is trivial to construct.
- **Whether to add a drift-guard test** — a test that greps source for the literal `"path": None` inside `js_runtimes` dicts to prevent re-introducing the bug if someone copy-pastes from old code. Recommendation: YES if it's a one-liner via the existing `tests/test_packaging_spec.py` shape (project precedent for source-grep gates per memory `feedback_gstreamer_mock_blind_spot.md`). Planner decides.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements

- `.planning/ROADMAP.md` — Phase 79 entry. Note: `**Depends on:** Phase 78` is order-of-shipping only; no code coupling expected. Planner confirms.
- `.planning/REQUIREMENTS.md` — No Phase 79 requirement entry yet. Planner adds one (e.g. `BUG-11: YouTube playback works when MusicStreamer is launched via the GNOME .desktop entry`, parallel to BUG-07's framing).
- `.planning/PROJECT.md` §Key Decisions — existing YouTube/Node decisions: KEEP_MPV reversal (Plan 35-06), Phase 999.7 cookie temp-copy (`cookie_utils`), Phase 999.9 js_runtimes baseline.

### Closest existing patterns (READ FIRST — Phase 79 mirrors these)

- **`musicstreamer/runtime_check.py:36-116`** — `NodeRuntime` dataclass + `check_node()` + `_which_node` + `_which_node_version_manager_fallback`. Phase 79's threading consumes `NodeRuntime.path` directly; no changes to this module.
- **`musicstreamer/player.py:1005-1098` — `_play_youtube` + `_youtube_resolve_worker`** — the primary call site. Phase 79 touches the opts construction at line 1063 and adds the INFO log line.
- **`musicstreamer/yt_import.py:50-95` — `scan_playlist` (the yt_dlp library API call site)** — the parallel call site. Same opts construction pattern; same fix.
- **`musicstreamer/__main__.py:163-227` — `_run_gui`** — already detects `node_runtime = runtime_check.check_node()` at line 215 and passes it to MainWindow at line 222. Phase 79 adds a parallel pass to `Player()` (line 220).
- **`musicstreamer/ui_qt/main_window.py:195-202` — `MainWindow.__init__(node_runtime=None)`** — the kwarg + storage pattern Phase 79 mirrors on Player.
- **`musicstreamer/ui_qt/main_window.py:795-817` — `_on_playback_error`** — existing toast nudge for missing-Node case. Unchanged by Phase 79.

### Closest existing patterns — focused tiny modules

- **`musicstreamer/cookie_utils.py`** — focused module pattern. `temp_cookies_copy()` + `is_cookie_file_corrupted()`. Shape for the new `yt_dlp_opts.py`: single-purpose, narrow public surface, easy to unit-test in isolation.
- **`musicstreamer/url_helpers.py`** — same pattern (`is_youtube_url`, `is_aa_url`, etc.). Trivial helpers in a single-file module.
- **`musicstreamer/subprocess_utils.py`** — same pattern. Confirms the "tiny module per concern" project convention.

### Project conventions (apply during planning)

- **snake_case + type hints throughout, no formatter** — per `.planning/codebase/CONVENTIONS.md`.
- **No new dependencies** — `yt_dlp` and `runtime_check` are already imported; no new pyproject entries.
- **`musicstreamer.player` logger at INFO** — already configured (`__main__.main:235`). New INFO log line consumes the existing channel; no log-config change.
- **0o600 file mode for sensitive data** — N/A for this phase (no new files).
- **GStreamer mock blind spot (memory `feedback_gstreamer_mock_blind_spot.md`)** — source-grep gates are the established defense for legacy-API drift. Planner considers a similar grep for `"path": None` literals inside `js_runtimes` (Claude's Discretion).
- **"Mirror X" decisions must cite source (memory `feedback_mirror_decisions_cite_source.md`)** — N/A for this phase; no external project mirroring.

### Test pattern references

- **`tests/test_player.py`** — Player unit-test patterns. The new opts-recording test mirrors existing `_youtube_resolve_worker` tests if any (per Phase 999.9 commit message, `test_player_emits_expected_yt_failure_prefix` exists).
- **`tests/test_yt_import_library.py`** — yt_import library-API test patterns. Mirror for `scan_playlist(node_runtime=...)`.
- **`tests/test_packaging_spec.py`** — drift-guard test pattern (source-grep gates). Reference if planner adopts the drift-guard test in Claude's Discretion.

### Deployment surface

- **`packaging/linux/org.lightningjim.MusicStreamer.desktop`** — `Exec=musicstreamer`. Confirms the reproduction context: the .desktop launcher invokes the pipx-shimmed binary with a non-interactive PATH.
- **`scripts/install.sh`** — `pipx install -e . --system-site-packages --force`. Confirms install path that produces the `~/.local/bin/musicstreamer` shim and the pipx venv interpreter.
- **`~/.local/bin/musicstreamer` (generated by pipx)** — shim with `#!.../pipx/venvs/musicstreamer/bin/python` shebang. PATH lookup for the shim itself works; the shim's child Python process inherits the launcher's (stripped) PATH, which is what yt-dlp sees.
- **`musicstreamer/desktop_install.py`** — Phase 61 self-install of `.desktop` + icon at first launch. Confirms the deployed `.desktop` matches `packaging/linux/`; no second `.desktop` variant in play.

### Critical prior history

- **Commit `a06549f` (2026-04-25) — "fix: detect Node.js installed via fnm/nvm/volta/asdf"** — added the version-manager fallback in `_which_node_version_manager_fallback`. Commit message explicitly documents the .desktop PATH gap: "GUI launches via .desktop inherit a non-interactive PATH, so version-manager shims (fnm's per-shell `/run/user/$UID/fnm_multishells/...`, nvm's sourced shell function) are missing — `shutil.which("node")` returns None even when node is installed". Phase 79 is the second half of the same fix: now thread the resolved path THROUGH to yt-dlp.
- **Phase 999.9 — js_runtimes baseline** — per `player.py:1058-1063` comment: "yt-dlp's library API does NOT auto-discover JS runtimes the way the CLI does. Without an explicit js_runtimes entry the YouTube n-challenge solver cannot run." The `path: None` was the original Phase 999.9 default that worked at the time because shutil.which found node on the user's PATH (pre-version-manager-fallback world).
- **`.planning/debug/resolved/yt-stream-exhausted-cookies.md`** — UNRELATED debug case. Different root cause (yt-dlp 2026.03.17+ requiring `remote_components: {ejs:github}` on the authenticated/cookies path). Same "Stream exhausted" surface symptom. Phase 79 does not touch `remote_components`.

### Codebase maps

- `.planning/codebase/ARCHITECTURE.md` — overall module layout.
- `.planning/codebase/CONVENTIONS.md` — snake_case, type hints, no formatter, focused tiny modules.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`musicstreamer/runtime_check.NodeRuntime`** — dataclass `(available: bool, path: Optional[str])`. Already detected once at startup; Phase 79 just plumbs the existing instance to two more call sites.
- **`musicstreamer/runtime_check.check_node()`** — one-shot probe with fnm/nvm/volta/asdf fallback. Phase 79 does NOT call it more than once; the single startup detection in `_run_gui` is the source of truth.
- **`MainWindow.__init__(..., node_runtime=None)` pattern** — exact ctor-kwarg shape Phase 79 mirrors on `Player.__init__` and `scan_playlist`. Storage as `self._node_runtime` (Player) / closure capture (scan_playlist).
- **`musicstreamer.player` logger at INFO** (configured in `__main__.main:235`) — new INFO line consumes the existing channel; no log-config change.
- **`tests/test_player.py` monkeypatch-`yt_dlp.YoutubeDL` pattern** — existing tests already record yt-dlp opts (per Phase 999.9 / `test_player_emits_expected_yt_failure_prefix`). Phase 79's regression test extends this matrix.

### Established Patterns

- **Focused tiny modules** (`cookie_utils`, `url_helpers`, `runtime_check`, `subprocess_utils`) — `yt_dlp_opts.py` inherits this shape. Single public function, ~20 LOC, dedicated test file.
- **Dependency injection over hidden global state** — every recent phase that needed cross-module data threaded it via kwargs (MainWindow `node_runtime`, Player `clock=time.monotonic`, scan_playlist `cookies_path`). Phase 79 mirrors.
- **Default-None kwargs for backwards-compat** — both `MainWindow(node_runtime=None)` and Player(`clock=time.monotonic`) use this. Phase 79's `Player(node_runtime=None)` + `scan_playlist(node_runtime=None)` mirror.
- **INFO-level logging for runtime diagnostics** (Phase 62 cycle_close pattern) — `musicstreamer.player` already at INFO. New line uses the same channel.
- **Source-grep drift-guard tests** (per memory `feedback_gstreamer_mock_blind_spot.md`, established in `tests/test_packaging_spec.py`) — candidate for guarding against re-introduction of `"path": None` literals inside `js_runtimes` dicts.

### Integration Points

- **`musicstreamer/yt_dlp_opts.py` (new file)** — created next to `cookie_utils.py` and `url_helpers.py` in the package root.
- **`musicstreamer/player.py:131` (Player.__init__)** — add `node_runtime: NodeRuntime | None = None` kwarg; store on `self._node_runtime`. Import `NodeRuntime` from `musicstreamer.runtime_check` (forward import; no circular dependency since runtime_check doesn't import player).
- **`musicstreamer/player.py:1063`** — replace `"js_runtimes": {"node": {"path": None}},` with `"js_runtimes": yt_dlp_opts.build_js_runtimes(self._node_runtime),`.
- **`musicstreamer/player.py:_youtube_resolve_worker`** — add `_log.info("youtube resolve: node_path=%s", self._node_runtime.path if self._node_runtime else None)` near the top of the worker, after the cookies-corruption check, before opts construction. Mirror in `scan_playlist`.
- **`musicstreamer/yt_import.py:_build_opts` (or equivalent inline opts dict construction)** — replace the literal js_runtimes with `yt_dlp_opts.build_js_runtimes(node_runtime)`. Add the same INFO log line.
- **`musicstreamer/yt_import.py::scan_playlist`** — grow `node_runtime: NodeRuntime | None = None` kwarg.
- **`musicstreamer/__main__.py:220`** — change `player = Player()` to `player = Player(node_runtime=node_runtime)`.
- **`musicstreamer/ui_qt/import_dialog.py` (YouTube tab handler)** — thread `node_runtime` from MainWindow into the `scan_playlist` call. Either via dialog ctor kwarg or via `self._main_window._node_runtime` access (planner's discretion).
- **`tests/test_yt_dlp_opts.py` (new file)** — three test cases for `build_js_runtimes`: None input, `NodeRuntime(available=True, path="/fake/node")`, `NodeRuntime(available=False, path=None)`.
- **`tests/test_player.py`** — extend with regression test for `_youtube_resolve_worker` opts-recording with three NodeRuntime inputs.
- **`tests/test_yt_import_library.py`** — extend with regression test for `scan_playlist` opts-recording with three NodeRuntime inputs.
- **No DB schema changes, no new files in `paths.py`, no settings keys.**
- **No changes to `runtime_check.py`** — already correct.
- **No changes to `_on_playback_error` toast logic** — existing nudge for absent-Node case stays unchanged.

</code_context>

<specifics>
## Specific Ideas

- **Reproduction context** — user has confirmed: launching via the GNOME .desktop (`Exec=musicstreamer`) produces "Stream exhausted" on YT stations 100% of the time when fnm/nvm/volta is the Node source; launching the same shim from a terminal (`musicstreamer`) works because the terminal's PATH carries the version-manager shims.
- **"Works via pipx/dev script"** in the phase title refers to BOTH `~/.local/bin/musicstreamer` (the pipx shim, when run from a terminal) AND `uv run musicstreamer` from a dev checkout. Both inherit a healthy PATH; the bug is exclusively the .desktop launch path.
- **Commit `a06549f` is the prior half of the same fix** — the user wrote it 2026-04-25 to suppress the spurious "Install Node.js" warning. Phase 79 finishes the job by passing the path THROUGH to yt-dlp. The two halves together are: (1) detect Node even when PATH is stripped, (2) tell yt-dlp where it is.
- **No diagnostic / instrumentation phase needed** — root cause is direct code inspection. The smoking gun is `player.py:1063` literal `{"path": None}` not consuming `NodeRuntime.path`. Confirmed by both the user (root-cause question) and the commit-message archaeology on `a06549f`.
- **Cross-platform single code path** — Windows is in scope by default (D-03). `runtime_check._which_node` already prefers `node.exe` and returns the absolute path; threading it through costs nothing extra and forestalls a parallel Windows-launcher bug.
- **No new toast** — user explicitly preferred not adding a "Node resolved but yt-dlp rejected it" branch; the fix should make that case structurally impossible.
- **One INFO log per YT play** — user wants the resolved node path observable in normal-log mode (not DEBUG-only), so live debugging on the deployed machine works without re-deploying with elevated log level.
- **Two-sites parity, single source of truth** — user explicitly chose "share the opts builder" over "fix both inline" to prevent future drift between the resolve path and the playlist-scan path.

</specifics>

<deferred>
## Deferred Ideas

### Future phases (if needs surface)

- **`os.environ['PATH']` augmentation at startup** — if a future bug surfaces for streamlink (Twitch resolution) under .desktop, this becomes the next phase's question. Streamlink is bundled as a Python library and may not need it; verify if/when needed.
- **`yt_dlp_opts.py` expansion to own `remote_components`, `format`, `cookiefile`** — if a third or fourth yt-dlp call site appears, the centralization argument strengthens. For two sites today, narrow scope is the right call.
- **Drift-guard test for `"path": None` inside `js_runtimes` literals** — if Phase 79 ships without it and a future contributor re-introduces the bug, add the source-grep gate then. Planner may add it preemptively (Claude's Discretion).
- **Parallel env-diff investigation** — if other "works in pipx but not via .desktop" bugs surface (e.g. cookies path resolution, locale, XDG paths), file a generic "audit .desktop launch env" phase that compares the two contexts systematically.
- **PyInstaller / Windows installer changes** — the Windows installer (Phase 47) ships Node as part of the bundle. If the same bug ever surfaces on Windows under a non-default install layout, the fix is identical (NodeRuntime.path threads through) but the conditional may need a Windows-installer-aware probe path.

### Reviewed Todos (not folded)
None — discussion stayed within phase scope.

</deferred>

---

*Phase: 79-fix-youtube-stream-exhausted-when-launched-via-desktop-app-w*
*Context gathered: 2026-05-16*
