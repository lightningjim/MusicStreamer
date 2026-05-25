# Phase 65: Show current version in app - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Surface the running app's current version (e.g. `v2.1.63`) in the UI as a **disabled informational entry at the bottom of the hamburger menu**. The version string is read at runtime via `importlib.metadata.version("musicstreamer")` so it auto-stays-in-sync with `pyproject.toml`'s `[project].version` (which Phase 63 made the canonical source via the auto-bump hook). The currently-stale `musicstreamer/__version__.py` mirror is deleted in lockstep — single source of truth from now on.

The phase also calls `app.setApplicationVersion(...)` in `__main__.py` so Qt's own slot is populated and `QCoreApplication.applicationVersion()` is available everywhere without re-importing metadata, and updates the Windows PyInstaller spec to ship the package's `dist-info` (`copy_metadata("musicstreamer")`) so the bundled exe reads the same version that dev / `uv run` reads.

**In scope:**
- New disabled `QAction` at the bottom of `self._menu` in `MainWindow.__init__` (`musicstreamer/ui_qt/main_window.py:163-229`), separator above it, label format `v{version}`.
- Read mechanism: `importlib.metadata.version("musicstreamer")` at the read site.
- `app.setApplicationVersion(...)` added next to the existing `setApplicationName` / `setApplicationDisplayName` / `setDesktopFileName` block (`musicstreamer/__main__.py:184-187`).
- Delete `musicstreamer/__version__.py` (stale `2.0.0` literal; build.ps1 already reads from `pyproject.toml` directly).
- `packaging/windows/MusicStreamer.spec` updated to include `copy_metadata("musicstreamer")` in `datas` so `importlib.metadata` resolves inside the PyInstaller bundle.
- A small smoke test that the bundled exe sees the package metadata (or equivalent assertion) so the next bundle build catches regressions.
- Tests covering: read site returns a non-empty SemVer-shape string; menu construction places the version action at the footer with the expected label; `__version__.py` deletion does not break any importer (codebase grep confirms no remaining references).

**Out of scope:**
- About dialog (license, repo URL, Qt version, copyright). Click is disabled in this phase; an About dialog is a follow-up if/when wanted.
- Click-to-copy clipboard, click-to-open-GitHub-release. Disabled QAction has no click target.
- Showing milestone codename or build SHA / commit date alongside the version. Compact `v2.1.63` is the chosen surface.
- Menubar right-corner label (`menuBar().setCornerWidget(...)`). Discussed and explicitly declined in favor of the menu-footer placement.
- Auto-rewriting `__version__.py` on every phase. The file is being deleted, not maintained.
- Adding a CLI `--version` flag to `__main__.py`. The build.ps1 smoke section currently logs `BUILD_INFO smoke_skipped=ui_app` — adding the flag is a separate concern and not requested.
- Changes to `pyproject.toml`'s version field, the auto-bump hook (`tools/bump_version.py`), or the Phase 63 versioning policy. This phase only consumes the version that Phase 63 produces.
- Touching MPRIS / SMTC metadata to expose version (these surfaces show track / station info, not app version).

</domain>

<decisions>
## Implementation Decisions

### Placement (Area 1)
- **D-01:** The version is rendered as a **disabled `QAction` at the bottom of the hamburger menu** (`self._menu` in `main_window.py:163-229`). Position: after the existing Group 3 "Export Settings / Import Settings" actions (`main_window.py:211-214`) and after the optional Phase 44 D-13 Node-missing indicator (`main_window.py:220-229`) — so the version is the literal last entry in the menu regardless of whether the Node-missing entry is present.
- **D-02:** A `self._menu.addSeparator()` precedes the new action, mirroring the existing inter-group separator pattern (`main_window.py:184, 197, 206`).
- **D-03:** The action is constructed via `self._menu.addAction(label).setEnabled(False)` (or `act.setEnabled(False)` after capture). Disabled QAction renders greyed and is non-clickable — this is the entire click-behavior contract for Phase 65 (D-08).
- **D-04:** Menubar right-corner widget (`menuBar().setCornerWidget(...)`) was considered and **declined**. Single discoverable surface (the hamburger) is preferred over an always-visible label that competes for header real estate.

### Version source at runtime (Area 2)
- **D-05:** Runtime read uses `importlib.metadata.version("musicstreamer")`. Single source of truth = `pyproject.toml`'s `[project].version` (Phase 63 auto-bump). No literal mirror, no parser, no second mutation per phase.
- **D-06:** `musicstreamer/__version__.py` is **deleted** in this phase. The file currently holds a stale `__version__ = "2.0.0"` literal and a comment explicitly forecasting this exact phase ("Future About dialog / hamburger menu footer (runtime read)"). Codebase grep confirms `build.ps1` reads version from `pyproject.toml` directly via regex (`packaging/windows/build.ps1:141-148`), not from `__version__.py`, so deletion is safe.
  - **D-06a:** A repo grep gate runs as part of the plan's validation: `git grep -l "from musicstreamer.__version__\|musicstreamer/__version__\|__version__\.py"` must return zero matches before the deletion is committed. If any consumer is found, fix the consumer first or pivot to D-05's "wrapper" alternative — not silently leave the import broken.
- **D-07:** `app.setApplicationVersion(importlib.metadata.version("musicstreamer"))` is added in `__main__.py::_run_gui` immediately after `app.setApplicationDisplayName("MusicStreamer")` (`__main__.py:186`) and before `app.setDesktopFileName(constants.APP_ID)` (`__main__.py:187`). Idiomatic Qt setup; lets `QCoreApplication.applicationVersion()` serve as the in-app read site (the menu builder uses it instead of re-calling `importlib.metadata`). Cheap, narrow, no second metadata access path.
- **D-08:** `packaging/windows/MusicStreamer.spec` is updated to include the package's `dist-info` so `importlib.metadata.version("musicstreamer")` resolves inside the PyInstaller bundle. Mechanism: `from PyInstaller.utils.hooks import copy_metadata` and concatenate `copy_metadata("musicstreamer")` into the `datas` list (the spec already uses `collect_all` for `charset_normalizer` / `streamlink` / `yt_dlp` and concatenates their datas at line 100-103 — same pattern). **No `try/except` fallback to a placeholder string** — Phase 65's whole point is showing the real version on Kyle's Win11 rig, so a silent `"0.0.0-dev"` fallback would defeat the feature where it's most needed.
- **D-09:** A bundle-aware test guards regression: either (a) a unit test that calls `importlib.metadata.version("musicstreamer")` and asserts non-empty SemVer-shape, OR (b) a Windows-build smoke check that runs `MusicStreamer.exe --print-version` (would require adding the flag — out of scope per domain) OR (c) post-build inspection of the staged bundle's `<bundle>/_internal/musicstreamer-*.dist-info/` directory existence. **Planner picks**; (a) is the simplest CI-friendly option and is the recommended default.

### Display format (Area 3)
- **D-10:** Label format is **`v{version}`** — e.g. `v2.1.63`. The single `v` prefix + raw version, nothing else. No "Version " word, no app-name repetition (the surface is already inside MusicStreamer's own menu), no milestone codename in parentheses, no build SHA.
- **D-11:** The version string is read via `QCoreApplication.applicationVersion()` (D-07) at the menu construction site, formatted via `f"v{version}"`. If the call returns an empty string (e.g. an unexpected dev path), the action is constructed with `v(unknown)` so the menu does not silently break — defensive but not a feature.

### Click behavior (Area 4)
- **D-12:** The action is **disabled** (`act.setEnabled(False)`) — purely informational footer, no click target, no toast, no dialog, no clipboard copy, no URL navigation. The simplest read of "show the version" gets the simplest implementation.
- **D-13:** No tooltip beyond Qt's default. (No "Click to copy" hint because there is no click action.)

### Claude's Discretion
- Exact name of the action variable (`self._act_version` is the recommended default; planner may pick a different name as long as it follows the existing `self._act_*` convention for retained references — see `self._act_stats`, `self._act_export`, `self._act_import_settings`, `self._act_node_missing`).
- Whether the menu read site goes through `QCoreApplication.applicationVersion()` (D-11 default) or calls `importlib.metadata.version("musicstreamer")` directly. The Qt slot is the recommended path (single setup site in `__main__.py`); planner may inline the metadata call if a cleaner test surface emerges.
- Whether to write a tiny helper (e.g., `musicstreamer/version.py` with `def get_version() -> str: ...`) or read inline at both `__main__.py` and `main_window.py`. A helper makes mocking in tests trivial; inline is fine if the test surface uses Qt's `applicationVersion` directly. Planner picks.
- Test placement: extend `tests/test_main_window.py` (likely exists for menu-construction tests) for the new menu entry, and either add a new `tests/test_version.py` for the read mechanism or fold into an existing module. Planner picks.
- Whether the `copy_metadata("musicstreamer")` call lives in the `.spec` body next to the existing `collect_all` block, or wraps into the existing `_cn_datas + _sl_datas + _yt_datas` concatenation at line 103 (same shape). Either reads cleanly.
- Whether the disabled `QAction` uses `addAction(label)` + `setEnabled(False)` or `addSection(label)` (which renders as a non-clickable header). `addAction(...).setEnabled(False)` is the recommended default — looks like a regular menu item, just greyed.
- Whether to include the `v(unknown)` defensive-fallback (D-11). Not required by spec; planner may drop it if metadata is asserted at startup with a hard fail instead.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 65: Show current version in app" — currently `**Goal:** [To be planned]` / `**Requirements**: TBD`. The planner should backfill the goal sentence and (optionally) add a stub `## Canonical refs:` block to ROADMAP that points back to this CONTEXT.md, mirroring the convention used for earlier phases.
- `.planning/REQUIREMENTS.md` — there is currently **no UI-visible-version requirement**. Phase 63's `VER-01` covers the auto-bump (closed); Phase 65 surfaces what `VER-01` produces. Planner adds a new requirement (e.g. `VER-02` or `UI-XX`) at planning time, or notes "no new requirement, this is a polish enhancement" — Kyle's call. Recommended: add a single-line `VER-02` so traceability matches Phase 63's shape.
- `.planning/PROJECT.md` `## Current Milestone: v2.1 Fixes and Tweaks` — milestone heading. **Source of `{major}.{minor}`** for Phase 63's bump, and (transitively) the version Phase 65 displays.

### Phase 63 precedent (the upstream that produces the version)
- `.planning/phases/63-auto-bump-pyproject-toml-version-on-phase-completion-using-m/63-CONTEXT.md` — D-01..D-12 for the auto-bump mechanism. Phase 65 consumes the result; do not re-litigate any decision in 63's CONTEXT.
- `pyproject.toml:7` — `version = "2.1.63"` is the canonical source. Phase 65 reads this transitively via `importlib.metadata`.

### Phase 61 precedent (the most recent main_window/__main__ Qt-API touch)
- `.planning/phases/61-linux-app-display-name-in-wm-dialogs-force-quit-and-other-wm/61-CONTEXT.md` — D-06/D-07/D-08 added `setApplicationDisplayName` / `setApplicationName` / `setDesktopFileName` next to each other in `_run_gui`. Phase 65 follows the same group: `setApplicationVersion(...)` slots into the same block per D-07.

### Source files this phase touches
- `musicstreamer/__main__.py:184-187` — Qt application setup block (`setApplicationName`, `setApplicationDisplayName`, `setDesktopFileName`). New `app.setApplicationVersion(importlib.metadata.version("musicstreamer"))` slots in here per D-07.
- `musicstreamer/ui_qt/main_window.py:162-229` — hamburger menu construction. New version action + separator land at the bottom of this block per D-01/D-02. Reference patterns:
  - `main_window.py:184, 197, 206` — existing inter-group `addSeparator()` calls.
  - `main_window.py:200-205` — `self._act_stats` retained-reference convention for `self._act_*`.
  - `main_window.py:220-229` — Phase 44 D-13 conditional Node-missing action; precedent for "an action that exists for informational purposes only" and for keeping menu order stable (the version footer should land *after* this block when present).
- `musicstreamer/__version__.py` — deleted in this phase per D-06. Current contents: stale `__version__ = "2.0.0"` literal; comments explicitly forecast this phase.
- `packaging/windows/MusicStreamer.spec:24-103` — PyInstaller spec. New `copy_metadata("musicstreamer")` import + datas concatenation per D-08; same concatenation pattern as the existing `_cn_datas + _sl_datas + _yt_datas`.
- `packaging/windows/build.ps1:141-148` — reference only; build.ps1 reads `version` from `pyproject.toml` directly via regex. Phase 65 does **not** modify build.ps1 (and confirms `__version__.py` deletion is safe because build.ps1 never read from it).

### Project conventions (apply during planning)
- **Bound-method signal connections, no self-capturing lambdas (QA-05)** — the new action's `triggered.connect(...)` is N/A because the action is disabled, but if the planner introduces any signals around the version display, this rule applies.
- **`self._act_*` retention pattern** — actions kept for later state changes (enable/disable/recheck) are stored on `self`. The version action is static and disabled — retention is optional, but `self._act_version` is recommended for test introspection.
- **`importlib.metadata` usage** — Python 3.10+ stdlib; no new dependency. Tests already use `tomllib` (Python 3.11+ stdlib) for read-only pyproject inspection (`tests/test_media_keys_smtc.py:9, 148`); `importlib.metadata` is the same shape (stdlib, zero install cost).
- **PyInstaller spec convention** — `collect_all(...)` for third-party packages whose datas/binaries are non-trivial. `copy_metadata(...)` is the lighter-weight import (single call, returns a `datas` list); use it for `musicstreamer` itself rather than `collect_all` because we're explicit about *only* needing dist-info, not binaries / submodules.
- **Linux Wayland deployment, DPR=1.0** (per project memory) — N/A for Phase 65 (no rendering / DPR concerns).
- snake_case + type hints throughout, no formatter (per `.planning/codebase/CONVENTIONS.md`).

### No external specs
No ADRs or external design docs apply. Standard Qt API, standard `importlib.metadata`, standard PyInstaller `copy_metadata` hook — all covered by their first-party docs (the researcher should consult Qt6 `QCoreApplication::setApplicationVersion`, Python `importlib.metadata`, and PyInstaller `copy_metadata` hook docs as needed).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`self._menu = menubar.addMenu("≡")`** at `main_window.py:164` — the hamburger menu instance. Phase 65 appends one separator + one disabled action to it; no menu reorganisation.
- **`self._act_*` retention pattern** — `self._act_stats` (`main_window.py:200`), `self._act_export` / `self._act_import_settings` (`main_window.py:211-213`), `self._act_node_missing` (`main_window.py:226`). New `self._act_version` follows the same shape.
- **`addSeparator()` between menu groups** — `main_window.py:184, 197, 206`. New separator before the version footer mirrors this.
- **Qt application setup block** — `__main__.py:184-187`. Phase 61 D-06/D-07/D-08 added three lines here; Phase 65 adds one more (`setApplicationVersion`).
- **PyInstaller `collect_all` concatenation pattern** — `packaging/windows/MusicStreamer.spec:24-33, 100-103`. New `copy_metadata("musicstreamer")` slots into the same `datas=[...] + _cn_datas + _sl_datas + _yt_datas` shape.
- **`tomllib` test usage** — `tests/test_media_keys_smtc.py:9, 148` reads `pyproject.toml` for read-only assertions. Phase 65's tests for the version-read site can reference the same module if the planner wants a "the displayed version equals the pyproject version" assertion.

### Established Patterns
- **Single source of truth for app-level constants** — `constants.APP_ID` (Phase 61 D-02) consolidated the app ID. Phase 65 follows the same discipline: `pyproject.toml`'s `[project].version` is the *only* literal; everything else reads.
- **Disabled-but-visible menu action** — Phase 44 D-13's `self._act_node_missing` is conditionally added (`if node_runtime is not None and not node_runtime.available`) and is *enabled-but-with-warning-glyph*. Phase 65's version action is *unconditional* and *disabled-with-no-glyph* — different shape, but same "informational menu entry" idiom.
- **One-line Qt setup additions in `_run_gui`** — Phase 61 D-06/D-08 added single-line setters next to existing ones; Phase 65 D-07 follows the same pattern.

### Integration Points
- **New menu action** — appended to `self._menu` after the Phase 44 Node-missing block (`main_window.py:229`), with a `self._menu.addSeparator()` immediately before. Reads `QCoreApplication.applicationVersion()` (D-07/D-11) and constructs label via `f"v{version}"`.
- **New `setApplicationVersion` call** — added at `__main__.py:187` (between `setApplicationDisplayName` and `setDesktopFileName`, or just after `setDesktopFileName` — planner picks; both order-preserving). Reads `importlib.metadata.version("musicstreamer")`.
- **PyInstaller spec edit** — `from PyInstaller.utils.hooks import copy_metadata` near the other hook imports; concatenate `copy_metadata("musicstreamer")` into the existing `datas` list at line 100-103.
- **`__version__.py` deletion** — `git rm musicstreamer/__version__.py`. Pre-deletion grep gate (D-06a) validates zero remaining importers.
- **Tests** — extend `tests/test_main_window.py` (or sibling) for menu-construction assertions; add a small standalone test for the read mechanism (`importlib.metadata.version("musicstreamer")` returns non-empty + matches `pyproject.toml`'s `[project].version`).

</code_context>

<specifics>
## Specific Ideas

- The user-visible promise: **"When I open the hamburger menu, the very last entry is a greyed-out `v2.1.63` (or whatever the running build's version is). I never have to look at pyproject.toml or run a CLI command to know which build I'm running."** That's the entirety of Phase 65's UX surface.
- The internal promise: **a single literal in `pyproject.toml`, read everywhere via `importlib.metadata`.** Phase 63 made `pyproject.toml` the canonical write site (auto-bump); Phase 65 makes it the canonical read site (importlib.metadata). The `__version__.py` mirror is retired in lockstep — no second source can drift.
- The bundle promise: **what dev sees and what the Windows installer sees match.** `--copy-metadata musicstreamer` (via the spec's `copy_metadata` hook) is the structural mechanism; a smoke test guards the regression.
- This phase pairs naturally with a future "About MusicStreamer…" dialog, but that's deliberately deferred — Phase 65 ships the simplest "show the version" surface and stops there.

</specifics>

<deferred>
## Deferred Ideas

- **About MusicStreamer… dialog** — version + repo URL + Qt/PySide6 version + license blurb + (optional) build SHA. Click-target for the version entry would shift from `setEnabled(False)` (D-12) to `triggered.connect(self._open_about_dialog)`. Future polish phase if/when wanted.
- **Click-to-copy clipboard** — copy the version string when the entry is clicked, with a "Version copied" toast. Useful for bug reports. Mutually exclusive with D-12 (disabled action). Future phase if the workflow turns out to need it.
- **Click-to-open GitHub release page** — `QDesktopServices.openUrl(...)` to `github.com/.../releases/tag/v2.1.63`. Requires that release tags actually exist for each phase, which they don't today (Phase 63's auto-bump rewrites `pyproject.toml` but doesn't tag).
- **Menubar right-corner label** — `menuBar().setCornerWidget(QLabel("v2.1.63"), Qt.TopRightCorner)` for an always-visible read. Discussed and declined in favor of the menu-footer placement; revisit if the version becomes important enough to warrant always-visible UI real estate.
- **Milestone codename in the label** — e.g. `v2.1.63 (v2.1 Fixes & Tweaks)`. Discussed and declined for compactness; revisit if Kyle ever wants the milestone surfaced in-app.
- **CLI `--version` flag** — `python -m musicstreamer --version` → `MusicStreamer 2.1.63`. The Windows build.ps1 smoke section currently logs `BUILD_INFO smoke_skipped=ui_app reason='UAT covers functional verification'`; adding a `--version` flag would let the smoke step actually launch-and-exit without UI. Out of scope for Phase 65 but a low-cost follow-up if smoke harness work resumes.
- **Build-SHA / dirty-flag in the version string** — e.g. `v2.1.63+abc1234` or `v2.1.63-dirty`. Out of scope; Phase 65's version surface is the SemVer triple from pyproject only.
- **Self-healing `__version__.py`** — auto-rewriting on every phase via Phase 63's bump hook. Rejected during discussion: the file is being deleted, not maintained.
- **Auto-tagging git releases on phase completion** — Phase 63's deferred-ideas list already carries this; Phase 65 inherits the same deferral.

</deferred>

---

*Phase: 65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb*
*Context gathered: 2026-05-08*
