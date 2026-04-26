# Phase 36: Qt Scaffold + GTK Cutover - Research

**Researched:** 2026-04-11
**Domain:** PySide6 QApplication/QMainWindow scaffolding, Qt resource system, pytest-qt, GTK cutover mechanics
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Bare-Window Scope (D-01..D-03)**
- D-01: `QMainWindow` with structural containers wired but empty: `QMenuBar` placeholder (no actions — UI-10 is Phase 40), central `QWidget` with empty `QVBoxLayout` (Phase 37 populates), `QStatusBar` (empty — Phase 37 adds toast overlay via UI-12).
- D-02: Window title `"MusicStreamer"`. Window icon = app icon (D-10). Default geometry 1200×800. Geometry persistence via `QSettings` is **deferred** — do NOT wire this phase.
- D-03: Hamburger menu actions NOT wired. May add a single placeholder `QMenu` off menubar with zero `QAction` children.

**Entry Point Strategy (D-04..D-06)**
- D-04: `musicstreamer/__main__.py` rewritten — default invocation `python -m musicstreamer` launches `QApplication` + `MainWindow`.
- D-05: Phase 35 headless smoke harness preserved behind `--smoke <url>` CLI flag. `python -m musicstreamer --smoke <url>` runs exact Phase 35 behavior (`QCoreApplication` + Player + ICY title log to stdout, NO widgets).
- D-06: CLI parsing uses `argparse` (stdlib only). Surface is just `[--smoke URL]`.

**GTK Deletion (D-07..D-09)**
- D-07: `musicstreamer/ui/` deleted in full (9 files) in a single atomic commit.
- D-08: All `from musicstreamer.ui import ...` references in `musicstreamer/` and `tests/` removed before/in the deletion commit.
- D-09: `musicstreamer/main.py` (if exists) removed. Only entry point post-Phase 36 is `python -m musicstreamer`.

**Icon Sourcing + Scope (D-10..D-13)**
- D-10: Icons from GNOME Adwaita symbolic theme (`/usr/share/icons/Adwaita/symbolic/`). License CC-BY-SA 3.0 with attribution via `NOTICE.md` / `icons/LICENSE`. Enables `QIcon.fromTheme("name", QIcon(":/icons/name.svg"))` pattern on both Linux (system theme) and Windows (bundled).
- D-11: Ship MINIMAL icon set — only what Phase 36 actually needs. Estimate 1–2 SVGs: (a) app icon (placeholder rectangle OK), (b) `open-menu-symbolic` for hamburger placeholder if menubar included.
- D-12: Resource layout: `musicstreamer/ui_qt/icons/` holds SVGs + `icons.qrc`. Compile via `pyside6-rcc icons.qrc -o icons_rc.py`. Import `icons_rc` as side-effect in `__main__.py`.
- D-13: Exact filenames Claude's discretion.

**Windows Fusion Style + Dark Mode (D-14..D-16)**
- D-14: `QApplication.setStyle("Fusion")` on Windows ONLY (`sys.platform == "win32"`), BEFORE widget construction. Linux keeps system style.
- D-15: Dark-mode detection via `QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark` (PySide6 6.5+). On dark, apply standard dark `QPalette` recipe.
- D-16: Accent color (ACCENT-01 / UI-11) deferred to Phase 40.

**pytest-qt Compatibility (D-17..D-19)**
- D-17: Phase 35 wired `conftest.py` with `QT_QPA_PLATFORM=offscreen`. Phase 36 must NOT regress.
- D-18: All 272 tests must still pass. Any GTK-import ripple test gets fixed in the same commit.
- D-19: New smoke test: instantiate `MainWindow`, `show()`, `qtbot.waitExposed(window)`, assert `windowTitle()`, assert central widget + menubar + status bar exist. This is the QA-01 evidence.

**Dead-Code Cleanup (D-20..D-22)**
- D-20: `musicstreamer/mpris.py` **deleted** in Phase 36.
- D-21: `dbus-python` **removed** from `pyproject.toml` (note: it's NOT currently listed in [project.dependencies] — see Runtime State Inventory).
- D-22: `tests/test_mpris.py` **deleted**.

**Module Layout (D-23, D-24)**
- D-23: `musicstreamer/ui_qt/` layout: `__init__.py` (empty), `main_window.py` (`MainWindow(QMainWindow)`), `icons/` directory, `icons.qrc`, `icons_rc.py` (generated, COMMITTED to avoid build step on every checkout).
- D-24: `__main__.py` imports `MainWindow` from `musicstreamer.ui_qt.main_window` + imports `icons_rc` as side-effect. `--smoke` path does NOT import `ui_qt`.

### Claude's Discretion
- `QVBoxLayout` spacing/margins.
- `QMainWindow` subclass vs direct (recommend subclass).
- Menubar placeholder — empty `QMenu("≡")` vs `menuBar()` with no children.
- `argparse` formatter class.
- Whether `icons_rc.py` is `.gitignore`d vs committed (D-23 says committed).
- Exact list of Adwaita SVGs to pull (minimal set).

### Deferred Ideas (OUT OF SCOPE)
- Window geometry persistence via `QSettings` — future phase.
- Accent color palette (UI-11 / ACCENT-01) — Phase 40.
- Hamburger menu actions wired (UI-10) — Phase 40.
- Station list UI (UI-01), now-playing panel (UI-02), toast overlay (UI-12), YouTube 16:9 thumbnail (UI-14) — Phase 37.
- Filter strip + favorites (UI-03/04) — Phase 38.
- Core dialogs (UI-05/06/07/13) — Phase 39.
- MPRIS2 via QtDBus (MEDIA-02) — Phase 41.
- Windows packaging — Phase 44.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PORT-03 | Qt scaffold (`QApplication` + `QMainWindow`) replaces GTK widgets; app launches with empty window | Minimal QApplication + MainWindow pattern in "Standard Stack" + "Code Examples" |
| PORT-04 | `musicstreamer/ui/` deleted; `musicstreamer/ui_qt/` is the only UI package (hard cutover) | Runtime State Inventory enumerates deletion targets + import ripples |
| PORT-07 | Qt Fusion style forced on Windows with explicit dark-mode detection | `QApplication.setStyle("Fusion")` + `Qt.ColorScheme` + dark `QPalette` recipe |
| PORT-08 | Bundled SVG icon set via `.qrc`; `QIcon.fromTheme("name", QIcon(":/icons/name.svg"))` fallback pattern | pyside6-rcc workflow + Adwaita symbolic source + fromTheme fallback semantics |
| QA-01 | pytest-qt offscreen replaces GTK fake-display infrastructure; all tests ported | Phase 35 already delivered pytest-qt + offscreen; Phase 36 adds widget construction smoke test |
| QA-04 | Per-phase "no new behavior" gate enforced at plan approval | Scope discipline noted — bare window only, zero Phase 37+ feature leakage |
</phase_requirements>

## Summary

Phase 36 is a mechanical cutover. The hard work — Player refactor to QObject + Qt signals + bus bridge — shipped in Phase 35. Phase 36 upgrades the headless `QCoreApplication` smoke harness to a full `QApplication` + `QMainWindow` and deletes ~4030 LOC of GTK code in a single atomic commit. The PySide6 APIs involved are small, stable, and well-documented. The real risk surface is the GTK-import ripple in 3 test files (`test_mpris.py`, `test_aa_url_detection.py`, `test_yt_thumbnail.py`) and the discovery that `dbus-python` is NOT actually listed in `pyproject.toml` [project.dependencies] — it's a system apt package, so D-21 "remove from pyproject.toml" is a no-op that should be verified and documented.

PySide6 6.11.0 and `pyside6-rcc` 6.11.0 are both present in the venv and ready. Adwaita symbolic icons are installed at `/usr/share/icons/Adwaita/symbolic/actions/` (`open-menu-symbolic.svg`, `media-playback-*-symbolic.svg` all confirmed present). `Qt.ColorScheme` attribute exists on PySide6 6.11.0 (verified via live import).

**Primary recommendation:** Structure the phase as 3–4 plans: (1) scaffold `ui_qt/` + icons + `__main__.py` rewrite, (2) atomic GTK delete + test ripple fix, (3) Windows Fusion/dark-mode palette + tests, (4) verification + post-cutover audit. Keep each plan reviewable in isolation.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.11.0 [VERIFIED: venv import] | Qt 6 Python bindings | Already installed (Phase 35), pinned in pyproject.toml as `PySide6>=6.11` |
| pyside6-rcc | 6.11.0 [VERIFIED: `pyside6-rcc --version`] | Qt resource compiler for .qrc files | Ships with PySide6; compiles SVGs into a Python module |
| pytest-qt | >=4 [VERIFIED: pyproject optional-dep] | Qt-aware test fixtures (qtbot, qapp) | Phase 35 already wired `conftest.py` with offscreen platform |

### Supporting (already in stack, Phase 35)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| argparse | stdlib | CLI arg parsing for `--smoke` | No new dep — D-06 mandates stdlib |
| adwaita-icon-theme | 47.0 (Debian) [VERIFIED: `ls /usr/share/icons/Adwaita/symbolic/`] | Source of SVG icons | System package, already installed on dev machine |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pyside6-rcc` generated Python | `QResource.registerResource()` with `.rcc` binary file | Binary file must be loaded at runtime; Python module approach is simpler and git-friendly |
| argparse | click / typer | Stdlib is D-06 locked; click would add a dep for zero gain |
| QMainWindow subclass | QMainWindow composed with `setCentralWidget()` at call site | Subclass recommended (D-23, also Claude's discretion note) — cleaner extensibility for Phase 37+ |
| Adwaita icons | Lucide / Feather / Tabler | Adwaita preserves v1.5 icon name continuity so `QIcon.fromTheme()` fallback lookup works on Linux with zero additional mapping |

**Installation:** Already installed. No new `uv add` / `pip install` required this phase.

**Version verification:** `PySide6==6.11.0` verified via `python -c "import PySide6; print(PySide6.__version__)"` on 2026-04-11. Registry check [CITED: pypi.org/project/PySide6] — 6.11 series is the current stable LTS line of Qt 6.

## Architecture Patterns

### Recommended Project Structure

```
musicstreamer/
├── __main__.py           # REWRITTEN — argparse → GUI path (default) or --smoke (legacy)
├── player.py             # UNCHANGED (Phase 35 QObject + Gst signals)
├── gst_bus_bridge.py     # UNCHANGED
├── migration.py          # UNCHANGED (run_migration() called from __main__)
├── paths.py              # UNCHANGED
├── ui/                   # DELETED — 9 files, ~4030 LOC
├── mpris.py              # DELETED (D-20)
└── ui_qt/                # NEW
    ├── __init__.py       # empty
    ├── main_window.py    # MainWindow(QMainWindow) — structural containers only
    ├── icons/
    │   ├── app-icon.svg         # placeholder rectangle or Adwaita source
    │   ├── open-menu-symbolic.svg
    │   └── LICENSE              # CC-BY-SA 3.0 attribution
    ├── icons.qrc         # Qt resource descriptor
    └── icons_rc.py       # GENERATED by pyside6-rcc, committed (D-23)
```

### Pattern 1: Minimal QApplication + QMainWindow Scaffold

**What:** Application bootstrap that sets style BEFORE widget construction.
**When to use:** Entry point for any PySide6 app.
**Example:** [CITED: doc.qt.io/qtforpython-6/PySide6/QtWidgets/QMainWindow.html]

```python
# musicstreamer/__main__.py (GUI path)
import sys
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst
from PySide6.QtWidgets import QApplication

from musicstreamer import migration
from musicstreamer.ui_qt import icons_rc  # noqa: F401 — side-effect import registers :/icons/
from musicstreamer.ui_qt.main_window import MainWindow

def _run_gui() -> int:
    Gst.init(None)
    migration.run_migration()

    app = QApplication(sys.argv)
    if sys.platform == "win32":
        app.setStyle("Fusion")
        _apply_windows_palette(app)   # dark-mode aware palette

    window = MainWindow()
    window.show()
    return app.exec()
```

### Pattern 2: MainWindow Subclass with Structural Containers

```python
# musicstreamer/ui_qt/main_window.py
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QMainWindow, QMenuBar, QStatusBar, QWidget, QVBoxLayout,
)

class MainWindow(QMainWindow):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("MusicStreamer")
        self.setWindowIcon(QIcon.fromTheme("application-x-executable",
                                           QIcon(":/icons/app-icon.svg")))
        self.resize(1200, 800)

        # Menubar placeholder — no actions yet (D-03, UI-10 is Phase 40)
        menubar: QMenuBar = self.menuBar()
        menubar.addMenu("≡")  # empty placeholder menu, no QActions

        # Central widget — empty layout, Phase 37 populates
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setCentralWidget(central)

        # Status bar — empty, Phase 37 adds toast overlay (UI-12)
        self.setStatusBar(QStatusBar(self))
```

### Pattern 3: Fusion + Dark Palette on Windows

```python
# musicstreamer/__main__.py (helper)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

def _apply_windows_palette(app: QApplication) -> None:
    hints = QGuiApplication.styleHints()
    if hints.colorScheme() != Qt.ColorScheme.Dark:
        return  # light Fusion is fine as-is
    p = QPalette()
    p.setColor(QPalette.Window, QColor(53, 53, 53))
    p.setColor(QPalette.WindowText, Qt.white)
    p.setColor(QPalette.Base, QColor(25, 25, 25))
    p.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    p.setColor(QPalette.ToolTipBase, Qt.white)
    p.setColor(QPalette.ToolTipText, Qt.white)
    p.setColor(QPalette.Text, Qt.white)
    p.setColor(QPalette.Button, QColor(53, 53, 53))
    p.setColor(QPalette.ButtonText, Qt.white)
    p.setColor(QPalette.BrightText, Qt.red)
    p.setColor(QPalette.Link, QColor(42, 130, 218))
    p.setColor(QPalette.Highlight, QColor(42, 130, 218))
    p.setColor(QPalette.HighlightedText, Qt.black)
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
    app.setPalette(p)
```

Source: This is the canonical "Fusion dark palette" recipe reproduced in dozens of PySide6/PyQt5 projects; the color values match the Qt example project. [CITED: doc.qt.io/qtforpython-6/PySide6/QtGui/QPalette.html] for `QPalette.ColorRole` enum semantics.

### Pattern 4: argparse + QApplication Argv Interaction

`QApplication(sys.argv)` consumes Qt-specific flags (`-platform`, `-style`, etc.) and removes them from the list. For app-level flags, parse BEFORE constructing `QApplication`:

```python
def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv)
    parser = argparse.ArgumentParser(
        prog="musicstreamer",
        description="Internet radio stream player",
    )
    parser.add_argument(
        "--smoke", metavar="URL", nargs="?", const="DEFAULT",
        help="Run headless backend smoke harness with given stream URL",
    )
    # parse_known_args: let Qt consume its own flags from argv[1:]
    args, qt_argv = parser.parse_known_args(argv[1:])
    remaining = [argv[0], *qt_argv]  # preserve argv[0] for QApplication

    if args.smoke is not None:
        url = args.smoke if args.smoke != "DEFAULT" else DEFAULT_SMOKE_URL
        return _run_smoke(remaining, url)
    return _run_gui(remaining)
```

`parse_known_args` is the correct pattern when forwarding unknown args downstream [CITED: docs.python.org/3/library/argparse.html#partial-parsing].

### Pattern 5: .qrc Resource File + pyside6-rcc

```xml
<!-- musicstreamer/ui_qt/icons.qrc -->
<!DOCTYPE RCC>
<RCC version="1.0">
  <qresource prefix="/icons">
    <file>icons/app-icon.svg</file>
    <file>icons/open-menu-symbolic.svg</file>
  </qresource>
</RCC>
```

Compile step (manual, committed output):
```bash
pyside6-rcc musicstreamer/ui_qt/icons.qrc -o musicstreamer/ui_qt/icons_rc.py
```

Side-effect import at app start:
```python
from musicstreamer.ui_qt import icons_rc  # noqa: F401
```

After import, resources are accessible as `":/icons/open-menu-symbolic.svg"` via `QIcon(...)` or `QPixmap(...)`. [CITED: doc.qt.io/qtforpython-6/tutorials/basictutorial/qrcfiles.html]

### Pattern 6: QIcon.fromTheme with Bundled Fallback (PORT-08 core)

```python
icon = QIcon.fromTheme("open-menu-symbolic", QIcon(":/icons/open-menu-symbolic.svg"))
assert not icon.isNull()
```

**Semantics [CITED: doc.qt.io/qtforpython-6/PySide6/QtGui/QIcon.html#PySide6.QtGui.QIcon.fromTheme]:**
- On Linux with adwaita-icon-theme installed: `fromTheme("open-menu-symbolic")` returns the system theme icon (preferred — matches GNOME appearance).
- On Windows (no XDG theme): `fromTheme` returns a null icon, and Qt falls back to the bundled `QIcon(":/icons/...")`.
- On Linux without the theme: also falls back to bundled.
- Edge case: if the theme has a same-named icon but it's broken/missing, `fromTheme` still returns it. Mitigation — do not blindly trust `isNull()`; test with actual system theme present.

### Anti-Patterns to Avoid

- **Calling `setStyle("Fusion")` AFTER widget construction** — style changes after widgets exist force re-polish cascades. Always before.
- **Constructing `QApplication` inside a test** — pytest-qt's `qtbot`/`qapp` fixture already provides one. Constructing a second is a common `QApplication instance already exists` error.
- **Importing `icons_rc` at module top of `ui_qt/main_window.py`** — tests that construct `MainWindow` need resources registered first. Do the side-effect import in `__main__.py` (GUI path), and in any test fixture that constructs `MainWindow` (add to `conftest.py` as a session-scoped side effect).
- **Hard-coding `QIcon(":/icons/x.svg")` without `fromTheme()` fallback** — breaks PORT-08 fallback pattern and loses Linux native appearance.
- **Leaving `gi`/`Gtk`/`Adw` imports anywhere after the cutover** — grep must return zero for `Gtk\|Adw\|from gi.repository import.*\(Gtk\|Adw` outside of `player.py` and `gst_bus_bridge.py` (which legitimately import `Gst`/`GLib`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI arg parsing | Manual `sys.argv` slicing | `argparse` (stdlib) | Partial-parsing via `parse_known_args` handles Qt+app arg split correctly |
| Icon loading | Reading SVGs with `open()` | `QIcon.fromTheme` + `.qrc` | Qt caches, scales, and theme-integrates icons transparently |
| Dark mode detection | Registry reads / `darkdetect` pip package | `QGuiApplication.styleHints().colorScheme()` | Native Qt API, updates on theme change, no extra dep |
| Resource bundling | Ad-hoc SVG path lookup relative to `__file__` | `pyside6-rcc` → `.py` module → `:/` URIs | Works in PyInstaller bundles without `--add-data` acrobatics (critical for Phase 44) |
| Dark palette colors | Invent from scratch | Standard "Fusion dark" recipe (Pattern 3) | Proven values, matches GTK dark theme brightness, widely copied |
| Window geometry persistence | Pickle/JSON | `QSettings` (deferred per D-02) | Not this phase, but document the hook |

**Key insight:** Every aspect of this phase has a canonical Qt-provided answer. Resist the urge to invent anything — PySide6 is a mature binding for a mature framework.

## Runtime State Inventory

Phase 36 is a refactor/rename/deletion phase. Explicit audit per category:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | None — GTK UI stores no persistent state of its own; all data lives in SQLite + paths.py dirs which are untouched. Verified by reading `musicstreamer/ui/__init__.py` (empty) and noting Phase 35 already centralized paths. | None |
| **Live service config** | None — no external service holds `musicstreamer.ui` references. | None |
| **OS-registered state** | `.desktop` file (if any) may reference `musicstreamer` command — should be checked. `/usr/share/applications/musicstreamer.desktop` probably does NOT exist (dev-mode run). MPRIS2 `org.mpris.MediaPlayer2.musicstreamer` well-known name was claimed by the no-op stub — that name is released automatically on process exit. Phase 41 will reclaim via QtDBus. | None this phase |
| **Secrets/env vars** | `QT_QPA_PLATFORM=offscreen` is set in `tests/conftest.py` — stays. No env vars carry the string `ui` in a code-load-bearing way. | None |
| **Build artifacts / installed packages** | `build/lib/musicstreamer/ui/main_window.py` exists (stale setuptools build dir). After deleting `musicstreamer/ui/`, this build artifact becomes orphaned. Also `build/lib/musicstreamer/__main__.py` still imports `from musicstreamer.ui.main_window import MainWindow`. | Delete `build/` directory (or at minimum `build/lib/musicstreamer/ui/` and `build/lib/musicstreamer/__main__.py`). Regenerate with `pip install -e .` or `uv sync` if needed. |

**Import ripple in tests (the critical finding — this is what will break when `musicstreamer/ui/` is deleted):**

Verified via grep:
- `tests/test_mpris.py` — imports `from musicstreamer.mpris import MprisService` (2 sites). DELETE FILE per D-22.
- `tests/test_aa_url_detection.py` — imports `from musicstreamer.ui.edit_dialog import _is_aa_url, _aa_channel_key_from_url, fetch_aa_logo` (3 sites). **Action required:** these helpers are pure functions and should be MOVED out of `edit_dialog.py` into a non-UI module (e.g., `musicstreamer/aa_urls.py` or inlined into `musicstreamer/audioaddict.py` if that file exists) BEFORE the GTK delete. Alternatively, if Phase 37+ will re-create `edit_dialog.py` under `ui_qt/` soon, consider parking the tests with `pytest.skip` and restoring in Phase 39. Planner picks — recommendation: extract to `musicstreamer/aa_urls.py` now (small, ~20 LOC) since the functions are pure and have no GTK coupling.
- `tests/test_yt_thumbnail.py` — imports `from musicstreamer.ui.edit_dialog import _is_youtube_url, fetch_yt_thumbnail` (4 sites). Same treatment: extract to `musicstreamer/yt_thumbnail.py` or similar.

**Verify the extractable functions are GTK-free before extracting:** `grep -nE "Gtk|Adw|GLib" musicstreamer/ui/edit_dialog.py` — if the `_is_aa_url` / `fetch_aa_logo` / `_is_youtube_url` / `fetch_yt_thumbnail` functions reference Gtk types, the extraction is more surgery. Likely they don't (URL regex + requests calls), but planner must confirm.

**`tests/test_player_tag.py` legacy shim question (from additional_context):** Verified — the file tests `player._on_title_cb` shim at line 126. This is a test OF `player.py`, not a test that imports `main_window.py`. The shim exists inside `player.py` for backward-compat with the old GTK callback path. Phase 36 does NOT need to clean this up — it's a Player internal, and removing it would be a Phase 37 concern when the new Qt UI connects via Qt signals directly. Keep as-is.

**`dbus-python` in pyproject.toml (D-21):** Verified — `dbus-python` is NOT listed in `[project.dependencies]` in the current `pyproject.toml`. The line only has `PySide6>=6.11`, `yt-dlp`, `streamlink>=8.3`, `platformdirs>=4.3`. So D-21 is effectively a **no-op** — the dep is not there to remove. However:
- It IS installed on the system via apt (`python3-dbus` Debian package), which is how the old `import dbus` lines in `main_window.py` worked.
- The pyproject.toml comment block mentions PyGObject as "system package — installed via apt" — `dbus-python` has the same treatment implicitly.
- **Action:** Planner should (a) confirm dbus-python is not in pyproject.toml (already the case), (b) add a brief note in the cutover commit message / plan documenting the no-op, and (c) not worry about `uv.lock` since there's no `uv.lock` to update (the pyproject uses setuptools, not uv-managed lockfile — verified: `ls uv.lock 2>&1` returns no such file; this is a `pip install -e .` project).

## Common Pitfalls

### Pitfall 1: QApplication instance already exists in tests

**What goes wrong:** Smoke test instantiates `QApplication()` directly instead of using pytest-qt's `qapp`/`qtbot` fixture. `RuntimeError: Please don't create multiple QApplication instances`.
**Why it happens:** pytest-qt auto-creates a `QApplication` per session; manual instantiation collides.
**How to avoid:** Use the `qtbot` fixture, which implicitly provides the app. Only construct widgets, never `QApplication`.
**Warning signs:** Test fails on *second* run in a session but passes in isolation.

### Pitfall 2: icons_rc not imported before MainWindow construction in tests

**What goes wrong:** Test constructs `MainWindow()`; `QIcon(":/icons/app-icon.svg")` returns null; icon doesn't render; test assertion on icon shape fails or logs warning.
**Why it happens:** Resource side-effect import lives in `__main__.py` which tests don't execute.
**How to avoid:** Add `from musicstreamer.ui_qt import icons_rc  # noqa: F401` at the top of `tests/conftest.py` (or a session-scoped autouse fixture). Alternatively, import it at the top of `musicstreamer/ui_qt/main_window.py` so any consumer gets the registration — downside is slightly less clean but much harder to forget. **Recommended: import in `main_window.py` top-level.**
**Warning signs:** `QIcon` is null; "cannot open file ':/icons/x.svg'" in stderr.

### Pitfall 3: setStyle called after QMainWindow construction

**What goes wrong:** Widgets keep the pre-change style; some parts re-polish, others don't; visual artifacts.
**Why it happens:** `QApplication.setStyle()` needs to happen before any `QWidget.__init__`.
**How to avoid:** Set style as the FIRST thing after `QApplication(argv)` construction, before `MainWindow(...)`.
**Warning signs:** Dark mode looks half-applied on Windows.

### Pitfall 4: Deleting musicstreamer/ui/ without fixing test imports first

**What goes wrong:** `git rm -r musicstreamer/ui/` succeeds, `pytest` explodes with `ModuleNotFoundError: No module named 'musicstreamer.ui.edit_dialog'`.
**Why it happens:** 3 test files still import from the deleted module (enumerated in Runtime State Inventory).
**How to avoid:** Extract pure functions out of `edit_dialog.py` into non-UI modules FIRST, update test imports, then delete. Single commit is fine as long as ordering is right within the commit.
**Warning signs:** `pytest --collect-only` fails before any test runs.

### Pitfall 5: PyInstaller + .qrc resource loss

**What goes wrong:** Not this phase, but: in Phase 44, if `icons_rc.py` is `.gitignore`d, the packaging build might not regenerate it, and the bundle ships without icons.
**Why it happens:** Generated files skipped by source-based tools.
**How to avoid:** Commit `icons_rc.py` (D-23 already mandates this). Document the regenerate command in a README in `ui_qt/`.
**Warning signs:** Icons missing in built EXE but present in dev run.

### Pitfall 6: argparse consuming --help before QApplication

**What goes wrong:** `python -m musicstreamer --help` prints Qt's built-in help instead of the app's.
**Why it happens:** If you pass the full `sys.argv` to `QApplication` without parsing first, Qt grabs some flags.
**How to avoid:** Call `argparse` BEFORE `QApplication(...)`. Use `parse_known_args` and forward only `argv[0] + qt_argv` to `QApplication`.
**Warning signs:** `--help` output looks wrong or shows Qt flags.

### Pitfall 7: Stale build/ directory confusing import paths

**What goes wrong:** After deleting `musicstreamer/ui/`, `build/lib/musicstreamer/ui/` still exists. If `PYTHONPATH` or an editable install accidentally picks it up, `from musicstreamer.ui.main_window import MainWindow` silently succeeds and masks the cutover.
**Why it happens:** setuptools `build/` is a historic artifact.
**How to avoid:** `rm -rf build/ dist/ *.egg-info` as part of the cutover task. Add `build/` to `.gitignore` if not already.
**Warning signs:** `pytest` passes locally on dev machine but fails on CI (where `build/` doesn't exist).

## Code Examples

See "Architecture Patterns" section above for the full set: scaffold main, MainWindow subclass, Windows dark palette, argparse split, .qrc workflow, fromTheme fallback.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct `QIcon("path/to/file.svg")` with `sys.path` tricks | `.qrc` resource + `:/icons/` URI via `pyside6-rcc` | Qt 4.x onward | Works in PyInstaller bundles; required for Windows ship |
| `darkdetect` pip package | `QGuiApplication.styleHints().colorScheme()` | PySide6 6.5 [CITED: doc.qt.io/qt-6/qstylehints.html#colorScheme] | No extra dep; theme-change notifications via signal |
| Subprocess-invoked `rcc` tool | `pyside6-rcc` Python entry point | PySide6 included since 6.0 | Single venv provides both binding and compiler |
| `QPalette` raw RGB triples | Same (no modern alternative) | — | Still the canonical way; QSS is an alternative for UI-11 Phase 40 |

**Deprecated/outdated:**
- `QDesktopWidget` (replaced by `QScreen` via `QGuiApplication.primaryScreen()`) — not used this phase but worth knowing.
- `dbus-python` — D-21 removes from pyproject (no-op; was never there) and `mpris.py` stub deletion eliminates the last `import dbus` consumer in the codebase.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| PySide6 | All Phase 36 UI code | ✓ | 6.11.0 | — |
| pyside6-rcc | Icon compilation (D-12) | ✓ | 6.11.0 | Could hand-write `icons_rc.py` but not worth it |
| adwaita-icon-theme | Icon source files (D-10) | ✓ | (Debian pkg installed) | Download SVGs from gnome.org if absent |
| pytest-qt | QA-01 test harness | ✓ | >=4 (Phase 35) | — |
| Qt offscreen platform | Headless tests | ✓ | built into PySide6 | — |
| Node.js on PATH | Phase 35 YouTube resolver (NOT this phase) | ✓ | (system) | — |
| `uv` lockfile | D-21 dep removal | ✗ | N/A | Not applicable — this project uses setuptools + pip, no `uv.lock` exists. D-21 simplifies to "verify dbus-python not in pyproject.toml" which is already true. |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=9 + pytest-qt >=4 |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` + `tests/conftest.py` (sets `QT_QPA_PLATFORM=offscreen`) |
| Quick run command | `.venv/bin/pytest -q tests/test_qt_scaffold.py` (new file) |
| Full suite command | `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PORT-03 | `QApplication` + `MainWindow` instantiate; `show()` succeeds in offscreen; window has correct title | unit (pytest-qt) | `pytest tests/test_qt_scaffold.py::test_main_window_constructs -x` | ❌ Wave 0 |
| PORT-03 | Central widget exists with QVBoxLayout (empty); menubar exists; status bar exists | unit | `pytest tests/test_qt_scaffold.py::test_structural_containers_present -x` | ❌ Wave 0 |
| PORT-04 | `musicstreamer.ui` package does not exist; `musicstreamer.mpris` module does not exist | static | `pytest tests/test_qt_scaffold.py::test_gtk_ui_package_removed -x` (uses `importlib.util.find_spec`) | ❌ Wave 0 |
| PORT-04 | Zero `from gi.repository import Gtk/Adw` in `musicstreamer/` outside `player.py`/`gst_bus_bridge.py` | grep-based | `pytest tests/test_qt_scaffold.py::test_no_gtk_imports -x` (walks source tree) | ❌ Wave 0 |
| PORT-07 | On `sys.platform == "win32"`, Fusion style is applied before widget construction | unit (mocked platform) | `pytest tests/test_qt_scaffold.py::test_fusion_style_on_windows -x` (monkeypatch `sys.platform`) | ❌ Wave 0 |
| PORT-07 | Dark palette helper produces expected colors when `colorScheme() == Dark` | unit | `pytest tests/test_qt_scaffold.py::test_dark_palette_applied -x` | ❌ Wave 0 |
| PORT-08 | `QIcon.fromTheme("open-menu-symbolic", QIcon(":/icons/open-menu-symbolic.svg"))` returns non-null | unit (after `icons_rc` import) | `pytest tests/test_qt_scaffold.py::test_bundled_icon_loads -x` | ❌ Wave 0 |
| PORT-08 | `icons_rc` module imports without error; `:/icons/` prefix registered | unit | `pytest tests/test_qt_scaffold.py::test_icons_rc_registered -x` | ❌ Wave 0 |
| QA-01 | `qtbot.waitExposed(window)` after `show()` succeeds in offscreen platform | integration (pytest-qt) | included in `test_main_window_constructs` above | ❌ Wave 0 |
| QA-01 | All 272 Phase 35 tests still pass after cutover | regression | `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q` → expect ≥ 270 passing (three test files may adjust — see note below) | ✓ (full suite) |
| QA-04 | No new user-visible behavior added beyond bare window | manual + grep | Manual: run `python -m musicstreamer`, confirm window shows empty — no station list, no now-playing panel. Grep: `grep -r "QListView\|QListWidget\|station" musicstreamer/ui_qt/` returns empty. | ❌ Wave 0 |

**Test count delta:** Phase 35 ended at 272. Phase 36 removes `tests/test_mpris.py` (est. ~8 tests — TODO: count before plan) and adds the new `tests/test_qt_scaffold.py` (est. ~8–10 new tests). Net expected: 272 ± small delta, still comfortably above QA-02's ≥265 floor. Planner should count `test_mpris.py` tests during scoping.

**Test files with GTK ripple requiring adjustment:**
- `tests/test_aa_url_detection.py` — extract helpers to non-UI module, update imports.
- `tests/test_yt_thumbnail.py` — extract helpers to non-UI module, update imports.

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest -q tests/test_qt_scaffold.py` + any touched test file (fast feedback ~1–2s)
- **Per wave merge:** `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q` (full suite ~3s)
- **Phase gate:** Full suite green + manual `python -m musicstreamer` window launches on Linux before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `tests/test_qt_scaffold.py` — new file covering PORT-03/04/07/08 + QA-01 via the map above.
- [ ] `musicstreamer/aa_urls.py` (or similar) — extract `_is_aa_url`, `_aa_channel_key_from_url`, `fetch_aa_logo` from `ui/edit_dialog.py` so the test can still import them after GTK delete. **Pre-requirement:** confirm these functions are GTK-free.
- [ ] `musicstreamer/yt_thumbnail.py` (or similar) — extract `_is_youtube_url`, `fetch_yt_thumbnail` for the same reason.
- [ ] Add `from musicstreamer.ui_qt import icons_rc  # noqa: F401` to `tests/conftest.py` OR top of `ui_qt/main_window.py` — recommend main_window.py for robustness.
- [ ] No framework install needed — pytest-qt, PySide6, offscreen platform all delivered in Phase 35.

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | No auth in Phase 36 (Twitch OAuth is Phase 40) |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | partial | `argparse` validates `--smoke` argument; URL passed to GStreamer — no shell interpolation, safe. |
| V6 Cryptography | no | — |
| V14 Configuration | yes | Icon resource path `:/icons/` is internal; no user-controlled resource loads |

### Known Threat Patterns for PySide6 scaffold

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Arbitrary file load via user-supplied resource path | Tampering | All icons referenced via compiled `:/icons/` prefix — resources are hardcoded at build time, not runtime file paths |
| `--smoke URL` as attack vector | Tampering | URL passed to GStreamer `playbin3` via Python binding (no shell); malicious URLs at worst cause playback failure, not code exec |
| Malicious SVG exploiting Qt image handlers | Code exec | Only bundled curated Adwaita SVGs; no user-supplied SVG loading this phase |

No new security surface introduced in Phase 36. Phase 40 (OAuth) and Phase 42 (settings export) are where real security work lands.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `_is_aa_url`, `_aa_channel_key_from_url`, `fetch_aa_logo`, `_is_youtube_url`, `fetch_yt_thumbnail` functions in `ui/edit_dialog.py` are GTK-free pure Python (no `Gtk.*` or `Gdk.*` references) and can be mechanically extracted | Runtime State Inventory | If they reference Gtk types (e.g., return `GdkPixbuf.Pixbuf`), extraction becomes a refactor. Planner must `grep -nE "Gtk\|Gdk\|Adw" musicstreamer/ui/edit_dialog.py` at those function bodies before scoping. |
| A2 | `uv` is NOT used by this project (verified via absence of `uv.lock`); D-21 is effectively a no-op | Environment Availability + Runtime State Inventory | If the user later switches to `uv`, the no-op stays valid. Low risk. |
| A3 | The Windows Fusion dark palette recipe (Pattern 3) is canonical and produces an acceptable dark appearance | Architecture Patterns | Pattern 3 cannot be fully tested on Linux dev machine. Phase 44 Windows VM run is the first real test. Phase 36 validates it via unit test of the helper (not visual). |
| A4 | `build/lib/musicstreamer/ui/` is a stale setuptools artifact safely deleted | Runtime State Inventory | If CI depends on a pre-built `build/` dir this would break CI. Verify `.gitignore` covers `build/`. |
| A5 | pytest-qt offscreen platform supports `QMainWindow.show()` + `qtbot.waitExposed()` reliably in headless mode on Linux/Python 3.13 / PySide6 6.11 | Validation Architecture | Well-documented combination; pytest-qt 4 explicitly supports offscreen. LOW risk. |
| A6 | The number of tests in `tests/test_mpris.py` is roughly 5–10 | Validation Architecture | Exact count affects test-count delta. Planner should run `grep -c "^def test_" tests/test_mpris.py` during scoping. Trivial to verify. |

## Open Questions

1. **Should `icons_rc.py` import happen in `main_window.py` or `__main__.py`?**
   - What we know: Both work. D-24 says `__main__.py`; D-23 does not forbid `main_window.py`.
   - What's unclear: Tests will construct `MainWindow` without going through `__main__.py`. The cleanest fix is to import in `main_window.py` top-level.
   - Recommendation: Import in `ui_qt/main_window.py` top-level (or `ui_qt/__init__.py`). This satisfies D-24 functionally — `__main__.py` imports `MainWindow`, which transitively imports `icons_rc`.

2. **Extract helpers or skip tests?**
   - What we know: 2 test files import from `ui/edit_dialog.py`.
   - What's unclear: Whether to (a) extract to new modules now, or (b) `pytest.skip` and restore in Phase 39.
   - Recommendation: **Extract now.** The functions are pure (per assumption A1), extraction is ~20 LOC, and it avoids losing test coverage for multiple phases. Phase 39's `edit_dialog.py` in `ui_qt/` can re-import from the new modules.

3. **Commit `icons_rc.py` to git or regenerate on install?**
   - D-23 says commit. Good choice — avoids requiring `pyside6-rcc` at every checkout, simplifies PyInstaller build. Add a comment in `ui_qt/__init__.py` documenting the regenerate command.

4. **app-icon.svg source — Adwaita or custom placeholder?**
   - D-11 allows placeholder rectangle SVG. D-13 gives Claude discretion.
   - Recommendation: Use a simple rectangle SVG this phase (e.g., blue square with "MS" text). Phase 37+ can drop in real branding. Keeps license simple (MIT/public domain rather than adding CC-BY-SA obligation for an icon that'll be replaced anyway).

5. **Menubar: `menuBar()` with no children vs. a single empty `QMenu("≡")`?**
   - Claude's discretion per CONTEXT.md.
   - Recommendation: Add a single `QMenu("≡")` placeholder so the menubar is visibly present in the bare window (otherwise Qt hides empty menubars on some platforms, which would confuse the smoke test). Zero `QAction` children keeps UI-10 deferred.

## Sources

### Primary (HIGH confidence)
- PySide6 6.11.0 — verified via `python -c "import PySide6; print(PySide6.__version__)"` in `.venv`
- pyside6-rcc 6.11.0 — verified via `pyside6-rcc --version`
- `Qt.ColorScheme` attribute — verified via live import on PySide6 6.11.0
- `/usr/share/icons/Adwaita/symbolic/actions/open-menu-symbolic.svg` — verified via `ls`
- `/usr/share/doc/adwaita-icon-theme/copyright` — confirmed CC-BY-SA-3.0 or LGPL-3 dual license
- `musicstreamer/__main__.py`, `musicstreamer/mpris.py`, `tests/conftest.py`, `pyproject.toml` — read directly
- Phase 35 summaries (35-06) — read directly

### Secondary (MEDIUM confidence)
- [CITED: doc.qt.io/qtforpython-6/PySide6/QtWidgets/QMainWindow.html] — QMainWindow API
- [CITED: doc.qt.io/qtforpython-6/PySide6/QtGui/QPalette.html] — QPalette.ColorRole enum
- [CITED: doc.qt.io/qtforpython-6/PySide6/QtGui/QIcon.html#PySide6.QtGui.QIcon.fromTheme] — fromTheme fallback semantics
- [CITED: doc.qt.io/qt-6/qstylehints.html#colorScheme] — QStyleHints.colorScheme() added in Qt 6.5
- [CITED: doc.qt.io/qtforpython-6/tutorials/basictutorial/qrcfiles.html] — .qrc workflow
- [CITED: docs.python.org/3/library/argparse.html#partial-parsing] — parse_known_args

### Tertiary (LOW confidence)
- Fusion dark palette color values — widely copied recipe, exact RGB values from countless Qt examples. Not a single authoritative source, but convergent.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all deps already installed and verified in venv
- Architecture patterns: HIGH — canonical Qt/PySide6 idioms, thoroughly documented
- Pitfalls: HIGH — derived from direct codebase audit (grep of actual imports)
- Validation: HIGH — Phase 35 already delivered the test harness
- Runtime state inventory: HIGH — direct grep verification of import ripples
- Security: HIGH — minimal surface, phase is UI scaffolding

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (PySide6 is stable; 30 days before re-verifying versions)
