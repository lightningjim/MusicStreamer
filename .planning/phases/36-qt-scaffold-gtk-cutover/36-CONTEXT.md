# Phase 36: Qt Scaffold + GTK Cutover - Context

**Gathered:** 2026-04-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the GTK4/Libadwaita application shell with a Qt/PySide6 one. Delete `musicstreamer/ui/` entirely (9 modules, ~4030 LOC). Create `musicstreamer/ui_qt/` with a `QMainWindow` that includes structural containers (menubar, central widget, status bar) but NO user-visible content beyond the window chrome — all actual UI content (station list, now-playing panel, filter bar, dialogs) lands in Phase 37+. Bundle a minimal SVG icon set via a `.qrc` Qt resource. Force Fusion style on Windows so dark mode renders correctly. Swap the headless Phase 35 `__main__.py` smoke harness behind a CLI flag so the default invocation opens the Qt window.

Out of scope for Phase 36: station list UI, now-playing panel UI, filter bar, favorites toggle, any dialog, accent color picker, media keys integration, full icon inventory. All deferred to Phase 37+.

</domain>

<decisions>
## Implementation Decisions

### Bare-Window Scope (Gray Area 1 → option b)
- **D-01:** Phase 36 creates `QMainWindow` with the **structural containers wired but empty**: a `QMenuBar` placeholder (no actions yet — Phase 40 populates via UI-10), a central `QWidget` (empty `QVBoxLayout` — Phase 37 populates), and a `QStatusBar` (empty — Phase 37 adds the toast overlay via UI-12). Phase 37 can populate these slots directly without creating the scaffolding.
- **D-02:** Window title: `"MusicStreamer"`. Window icon: the app icon (see D-10). Default window geometry: 1200×800 (Claude's discretion — sized for station list + now-playing panel per Phase 37 layout). Geometry persistence across launches is **deferred** — planner should not wire `QSettings.setValue("geometry", ...)` this phase.
- **D-03:** The hamburger menu actions (Discover, Import, Accent Color, YouTube Cookies, Accounts, Export/Import Settings) are NOT wired in Phase 36. UI-10 belongs to Phase 40. Phase 36 may add a single `QMenu` off the menubar as a placeholder, but with no `QAction` children.

### Entry Point Strategy (Gray Area 2 → option b)
- **D-04:** `musicstreamer/__main__.py` is rewritten to launch the full Qt application by default. Invocation: `python -m musicstreamer` → instantiates `QApplication`, constructs `MainWindow`, calls `show()`, enters `app.exec()`.
- **D-05:** The Phase 35 headless smoke harness (`QCoreApplication` + `Player` + direct URL playback) is preserved via a `--smoke` CLI flag: `python -m musicstreamer --smoke <url>` runs the exact Phase 35 behavior (no widgets, just Player + ICY title log to stdout). This keeps the backend smoke-test capability available for regression checks during later UI development without forcing the user to remember a separate module path.
- **D-06:** CLI arg parsing uses `argparse` (stdlib, no extra dep). The absence of `--smoke` is the default GUI path. Any other positional argument handling is deferred — the CLI surface is just `python -m musicstreamer [--smoke URL]`.

### GTK Deletion (required by PORT-04 — no gray area)
- **D-07:** `musicstreamer/ui/` is deleted in full, including `__init__.py`, `main_window.py` (1193 lines), `accent_dialog.py`, `accounts_dialog.py`, `discovery_dialog.py`, `edit_dialog.py`, `import_dialog.py`, `station_row.py`, `streams_dialog.py`. The deletion is atomic — a single commit removes all 9 files.
- **D-08:** Any `from musicstreamer.ui import ...` references anywhere in `musicstreamer/` or `tests/` must be removed before the deletion commit. Planner should grep for them during the cutover task and include them in the same commit.
- **D-09:** `from musicstreamer import main` or legacy GTK entry-point invocations (if any exist) get removed. The only entry point after Phase 36 is `python -m musicstreamer` (i.e., `musicstreamer/__main__.py`).

### Icon Sourcing + Scope (Gray Areas 3 + 4 → options a + a)
- **D-10:** Icons come from the **GNOME Adwaita icon theme** (`adwaita-icon-theme` package on Linux, available at `/usr/share/icons/Adwaita/symbolic/`). License: CC-BY-SA 3.0 with attribution. A `NOTICE.md` or `icons/LICENSE` file in the resource directory credits GNOME Project. This choice preserves the icon name continuity from v1.5 (all names are GNOME symbolic names like `media-playback-start-symbolic`) and enables the PORT-08 fallback pattern `QIcon.fromTheme("name", QIcon(":/icons/name.svg"))` to succeed on Linux via the system theme AND on Windows via the bundled SVG.
- **D-11:** Phase 36 ships a **minimal icon set** — only the icons the Phase 36 bare window actually needs. Best estimate: (a) app icon (can be a placeholder rectangle SVG this phase; Phase 37 or later can drop in proper branding), (b) `open-menu-symbolic` for the hamburger placeholder if the menubar is included. That is 1–2 SVGs, no more. Later phases (37, 39, 40) ship additional icons as they become needed for the features they introduce.
- **D-12:** Icon resource layout: `musicstreamer/ui_qt/icons/` directory holds the SVG files, plus an `icons.qrc` Qt resource descriptor. The resource is compiled at build time via `pyside6-rcc icons.qrc -o icons_rc.py` (or similar) and imported once at app startup so resources are registered before any `QIcon(":/icons/...")` lookup. Planner should document the build step in the plan's action field (e.g., "run `pyside6-rcc` as part of the Phase 36 deps/build task").
- **D-13:** The exact icon filenames Phase 36 ships are Claude's discretion — planner picks whatever minimal set makes the bare window work without "missing icon" errors.

### Windows Fusion Style + Dark Mode (PORT-07)
- **D-14:** `QApplication.setStyle("Fusion")` is called on Windows ONLY (`sys.platform == "win32"`), BEFORE any widget construction. On Linux, the system style wins — GNOME users get `adwaita-qt` if it's installed, otherwise default Fusion. The rationale is: GNOME users on Linux expect native-looking apps; Windows users get the default style which has the dark-mode regression, so Fusion is the fix there.
- **D-15:** Windows dark-mode detection uses `QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark` (PySide6 6.5+). On dark mode, apply a dark Fusion palette via `QPalette` (standard Qt recipe — planner can fill in the color values). No custom styling beyond what Fusion + dark palette produce.
- **D-16:** Accent-color application (ACCENT-01, UI-11) is **deferred to Phase 40**. Phase 36's palette is plain Fusion light or dark — no custom accent overlay yet.

### pytest-qt Compatibility (QA-01, QA-04)
- **D-17:** Phase 35 already installed `pytest-qt` and wired `conftest.py` with `QT_QPA_PLATFORM=offscreen`. Phase 36 must NOT regress this. The existing `qapp` fixture from pytest-qt is a `QApplication` subclass — Phase 35 tests that don't construct widgets will continue to work against it. Phase 35 tests that mock the `Gst.ElementFactory.make` factory will also continue to work.
- **D-18:** All 272 currently-passing tests must still pass at end of Phase 36. The regression gate is `QT_QPA_PLATFORM=offscreen pytest -q` → 272 passed. If any test fails because of the GTK-delete, the planner must update that test in the same commit (likely GTK-import ripples in tests that haven't been touched since Plan 35-05).
- **D-19:** A new minimal smoke test verifies the Qt scaffold: instantiate `MainWindow`, call `show()`, `qtbot.waitExposed(window)`, assert `window.windowTitle() == "MusicStreamer"` and the central widget + menubar + status bar exist. This is the QA-01 evidence that the Qt harness actually renders.

### Dead-Code Cleanup (Gray Area 5 → option b)
- **D-20:** `musicstreamer/mpris.py` is **deleted** in Phase 36 alongside the GTK UI cutover. Its only callers live in `main_window.py` which disappears in the same commit. Phase 41 (MEDIA-02) will re-create `mpris.py` from scratch as a `PySide6.QtDBus` implementation — no continuity is needed between the old no-op stub and the future real implementation.
- **D-21:** `dbus-python` is **removed from `pyproject.toml`** runtime dependencies during Phase 36. It has no callers after `main_window.py` and `mpris.py` are deleted. Phase 41 adds `PySide6.QtDBus` calls (which are part of PySide6 already — no new dep). If `dbus-python` somehow has a lingering test or import site, the planner catches it via the `grep -r "import dbus"` sweep that goes into the cutover task.
- **D-22:** `tests/test_mpris.py` — Plan 35-05 rewrote this against the no-op stub. Phase 36 **deletes** this test file since the stub is gone. A new test arrives in Phase 41 when the QtDBus adaptor lands.

### Module Layout for `musicstreamer/ui_qt/` (Claude's Discretion, but capture for planner)
- **D-23:** Initial `musicstreamer/ui_qt/` layout:
  - `__init__.py` — empty
  - `main_window.py` — `MainWindow(QMainWindow)` class with structural containers only
  - `icons/` — directory holding SVG files
  - `icons.qrc` — Qt resource descriptor
  - `icons_rc.py` — generated resource module (committed to avoid a build step on every checkout; regenerate when SVGs change)
- **D-24:** `musicstreamer/__main__.py` imports `MainWindow` from `musicstreamer.ui_qt.main_window` and also imports `icons_rc` (as a side-effect import for resource registration). `--smoke` path does NOT import `ui_qt` at all.

### Claude's Discretion
- Specific `QVBoxLayout` spacing/margins for the empty central widget.
- Whether to use `QMainWindow` directly or subclass it (recommend subclass for future extensibility).
- Exact menubar placeholder implementation — empty `QMenu("≡")` vs. just `menuBar()` with no children.
- `argparse` formatter class for the CLI.
- Whether `icons_rc.py` gets `.gitignore`d and regenerated on install, or committed. Planner picks.
- The exact list of GNOME Adwaita SVGs pulled (planner picks the minimal set).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap + Requirements
- `.planning/ROADMAP.md` § "Phase 36: Qt Scaffold + GTK Cutover" — goal, depends-on, requirements list, success criteria
- `.planning/REQUIREMENTS.md` § "PORT — Backend isolation & Qt scaffold" — PORT-03, PORT-04, PORT-07, PORT-08 full text
- `.planning/REQUIREMENTS.md` § "QA — Port quality gates" — QA-01, QA-04 full text
- `.planning/PROJECT.md` — "Current Milestone: v2.0 OS Agnostic" section; Key Decisions table already notes Qt cutover is hard-cutover

### Phase 35 output to build on
- `.planning/phases/35-backend-isolation/35-06-drop-mpv-yt-dlp-ejs-SUMMARY.md` — final player state, no subprocess launches, clean backend ready for Qt
- `.planning/phases/35-backend-isolation/35-CONTEXT.md` — D-05 (existing `__main__.py` headless smoke pattern), D-09..D-11 (mpris stub disposition)
- `musicstreamer/__main__.py` — current headless Phase 35 entry that Phase 36 rewrites
- `musicstreamer/player.py` — QObject + typed Qt signals, ready for main-thread widget integration
- `musicstreamer/mpris.py` — no-op stub slated for deletion in D-20

### GTK UI files being deleted
- `musicstreamer/ui/__init__.py`
- `musicstreamer/ui/main_window.py` (1193 lines — primary deletion target)
- `musicstreamer/ui/accent_dialog.py`
- `musicstreamer/ui/accounts_dialog.py`
- `musicstreamer/ui/discovery_dialog.py`
- `musicstreamer/ui/edit_dialog.py`
- `musicstreamer/ui/import_dialog.py`
- `musicstreamer/ui/station_row.py`
- `musicstreamer/ui/streams_dialog.py`

### Codebase maps (pre-existing)
- `.planning/codebase/STACK.md` — pre-port stack; will need a post-cutover note after Phase 36
- `.planning/codebase/ARCHITECTURE.md` — pre-port architecture
- `.planning/codebase/CONVENTIONS.md` — still largely valid (thread-local DB, Qt signals from Phase 35)

### External specs (researcher should consult)
- PySide6 `QMainWindow`, `QMenuBar`, `QStatusBar`, `QApplication`, `QStyle`, `QPalette`, `Qt.ColorScheme` docs
- PySide6 resource system: `pyside6-rcc` CLI, `.qrc` format, runtime resource import side effect
- GNOME Adwaita icon theme license (CC-BY-SA 3.0) and symbolic icon naming convention (`freedesktop.org` icon-theme spec)
- `QIcon.fromTheme("name", fallback)` behavior on Windows (no system theme) vs. Linux (XDG system theme lookup)
- `adwaita-qt` package — does the user's dev environment have it? (affects Linux styling consistency but is system-level, not bundled)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`musicstreamer/player.py`** — already a QObject with typed Signals. `MainWindow.__init__` constructs one `Player()` instance and wires slots to `title_changed`, `playback_error`, `failover`, `offline` signals (even though Phase 36 doesn't yet display them — wiring them to logging slots or empty handlers is fine).
- **`musicstreamer/paths.py`** — already centralizes data paths. `MainWindow` uses `paths.data_dir()` if it needs any path (unlikely this phase).
- **`musicstreamer/migration.py`** — already runs on first launch. The new `__main__.py` should call `migration.run_migration()` before widget construction, same as the Phase 35 headless entry does.

### Established Patterns
- **Qt signals + queued connections** — already set up in Phase 35. Widget slots in Phase 36+ connect to Player signals with `Qt.ConnectionType.AutoConnection` (default) which resolves to queued when sender and receiver are on different threads.
- **`musicstreamer/constants.py` PEP 562 __getattr__ shim** — lazy resolution through `paths.py`. This pattern stays untouched.
- **`__main__.py` structure** — Phase 35 shows the pattern: `Gst.init(None)` → `migration.run_migration()` → construct app → construct Player → wire signals → enter event loop. Phase 36 extends this with widget construction in the GUI path.

### Integration Points
- **New entry point** — `musicstreamer/__main__.py` rewrite is the single seam where GUI branch vs smoke branch divide.
- **Icon resource registration** — one-time side-effect import of `musicstreamer.ui_qt.icons_rc` in `__main__.py` (GUI path only). Tests that use `qtbot`/`qapp` don't construct `MainWindow`, so they don't need resources — but any test that does construct `MainWindow` must import `icons_rc` first.
- **Pipeline → main thread** — `Player` emits signals from the `GstBusLoopThread`; they're auto-queued to whichever thread owns the slot. In Phase 36 that thread is the Qt main thread (where `QApplication` lives).

### Constraints
- NO feature-parity UI porting in Phase 36 — that's Phase 37+ work. Any pressure to "just add the station list while you're at it" gets redirected as scope creep per QA-04 ("no new behavior" gate).
- Icons must not fail silently. Planner must include a smoke test that constructs `QIcon.fromTheme("some-expected-name")` via the fallback path and asserts `icon.isNull() == False`.
- `adwaita-qt` on the user's Linux dev machine is system-level — if it's not installed, Fusion will be the Linux style too. This is acceptable; the phase goal is "window launches and looks sane", not "looks pixel-perfect native."

</code_context>

<specifics>
## Specific Ideas

- User chose "structural containers now" (D-01) because it smooths the Phase 37 work — no refactoring of the window shell needed when actual content arrives.
- User explicitly chose to preserve the headless smoke harness via `--smoke` (D-05) — backend regression testing remains cheap.
- Icon sourcing from Adwaita (D-10) is the continuity-preserving choice: v1.5 used the same icon names, so `QIcon.fromTheme()` fallback works across platforms with minimal effort.
- `mpris.py` deletion (D-20) is aggressive cleanup — user accepts that media keys stay non-functional until Phase 41, as already decided in Phase 35 D-11.

</specifics>

<deferred>
## Deferred Ideas

- **Window geometry persistence** (`QSettings.setValue("geometry", ...)`) — noted in D-02 as deferred. Future quality-of-life phase or Phase 40 (hamburger menu + settings).
- **Accent color palette integration** (UI-11 / ACCENT-01 port) — Phase 40.
- **Hamburger menu actions wired** (UI-10) — Phase 40.
- **Station list UI** (UI-01) — Phase 37.
- **Now-playing panel UI** (UI-02) — Phase 37.
- **Toast overlay widget** (UI-12) — Phase 37 populates the status bar placeholder from D-01.
- **Full icon inventory** — Phase 37+ add icons as their features need them.
- **Real MPRIS2 implementation via QtDBus** (MEDIA-02) — Phase 41.
- **Windows packaging + installer** — Phase 44.

</deferred>

---

*Phase: 36-qt-scaffold-gtk-cutover*
*Context gathered: 2026-04-11*
</content>
</invoke>
