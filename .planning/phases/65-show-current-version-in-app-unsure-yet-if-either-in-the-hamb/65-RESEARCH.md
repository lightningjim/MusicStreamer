# Phase 65: Show current version in app - Research

**Researched:** 2026-05-08
**Domain:** Qt6 QMenu wiring, `importlib.metadata`, PyInstaller `copy_metadata`
**Confidence:** HIGH

## Summary

Phase 65 is a small wiring phase: surface `pyproject.toml`'s `[project].version` (currently `2.1.63`) as a disabled `QAction` at the bottom of the hamburger menu, populate Qt's `applicationVersion` slot from the same source, delete the stale `__version__.py` mirror, and ensure the Windows PyInstaller bundle ships the package's `dist-info` so `importlib.metadata.version("musicstreamer")` resolves at runtime.

All open questions raised in the research scope are answerable with HIGH confidence from official Qt6, PyInstaller, and Python stdlib docs plus live verification against this repo's `.venv` (where `musicstreamer-2.1.63.dist-info` is already present and `importlib.metadata.version("musicstreamer")` already returns `"2.1.63"` under `uv run`). The deletion gate (D-06a) is verified clean: zero importers of `musicstreamer.__version__` exist outside the file itself.

**Primary recommendation:** Read `importlib.metadata.version("musicstreamer")` at exactly two sites — `__main__.py::_run_gui` (passed to `app.setApplicationVersion(...)`) and the menu construction site in `main_window.py` (use `QCoreApplication.applicationVersion()` if it returns non-empty, else fall back to a direct `importlib.metadata.version` call so the test surface works without `_run_gui` having executed). One unit test asserts the read site returns the same string as `tomllib.loads(pyproject.toml)["project"]["version"]`. One menu-construction test asserts the last non-separator action's text matches `r"^v\d+\.\d+\.\d+"`. No bundle-build smoke needed in this phase — the in-process unit test (D-09 option a) is sufficient.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Placement (Area 1)**
- **D-01:** Disabled `QAction` at the bottom of the hamburger menu (`self._menu` in `main_window.py:163-229`). After Group 3 (Export/Import Settings) and after the optional Phase 44 D-13 Node-missing indicator — version is the literal last entry whether or not Node-missing is present.
- **D-02:** `self._menu.addSeparator()` precedes the new action, mirroring existing inter-group separators (`main_window.py:184, 197, 206`).
- **D-03:** Action constructed via `self._menu.addAction(label).setEnabled(False)`. Disabled QAction renders greyed and is non-clickable — entire click-behaviour contract for the phase.
- **D-04:** Menubar right-corner widget (`menuBar().setCornerWidget(...)`) declined.

**Version source at runtime (Area 2)**
- **D-05:** Runtime read uses `importlib.metadata.version("musicstreamer")`. Single source of truth = `pyproject.toml`'s `[project].version` (Phase 63 auto-bump).
- **D-06:** Delete `musicstreamer/__version__.py` (currently stale `__version__ = "2.0.0"`).
- **D-06a:** Repo grep gate — `git grep -l "from musicstreamer\\.__version__\\|musicstreamer/__version__\\|__version__\\.py"` must return zero source-file matches before deletion is committed.
- **D-07:** Add `app.setApplicationVersion(importlib.metadata.version("musicstreamer"))` in `__main__.py::_run_gui` next to the existing `setApplicationName` / `setApplicationDisplayName` / `setDesktopFileName` block (`__main__.py:184-187`).
- **D-08:** Update `packaging/windows/MusicStreamer.spec` with `from PyInstaller.utils.hooks import copy_metadata` and concatenate `copy_metadata("musicstreamer")` into `datas`. **No `try/except`** fallback to a placeholder string.
- **D-09:** Bundle-aware regression test. Planner picks shape — option (a) in-process unit test recommended.

**Display format (Area 3)**
- **D-10:** Label format is `v{version}` — e.g. `v2.1.63`. Single `v` prefix + raw version, nothing else.
- **D-11:** Read via `QCoreApplication.applicationVersion()` at the menu site, formatted via `f"v{version}"`. Defensive `v(unknown)` fallback if the call returns empty (planner's choice whether to keep this).

**Click behaviour (Area 4)**
- **D-12:** Action is **disabled** — purely informational, no click target, no toast, no dialog, no clipboard, no URL.
- **D-13:** No tooltip beyond Qt's default.

### Claude's Discretion

- Action variable name (`self._act_version` recommended).
- Whether the menu read site uses `QCoreApplication.applicationVersion()` or calls `importlib.metadata.version("musicstreamer")` directly. **Research recommends a hybrid** — see §Implementation Approach.
- Whether to add a tiny helper module (e.g. `musicstreamer/version.py`) or inline both reads.
- Test placement: extend existing `tests/test_main_window_integration.py` for the menu entry vs. add a new `tests/test_version.py` for the read mechanism.
- Whether `copy_metadata("musicstreamer")` lives next to the existing `collect_all` block or wraps into the `_cn_datas + _sl_datas + _yt_datas` concatenation at line 103.
- `addAction(label).setEnabled(False)` vs. `addSection(label)`. **Research recommends `addAction(...) + setEnabled(False)`** — see Open Question #4.
- Whether to keep the `v(unknown)` defensive fallback (D-11). Research recommends **dropping it** in favour of a hard fail at `_run_gui` startup; see Open Question #2.

### Deferred Ideas (OUT OF SCOPE)

- About MusicStreamer dialog (license, repo URL, Qt version, copyright, build SHA).
- Click-to-copy clipboard, click-to-open-GitHub-release, or any click action.
- Milestone codename or build SHA / commit date in the label.
- Menubar right-corner label (`menuBar().setCornerWidget(...)`).
- Auto-rewriting `__version__.py` on every phase.
- CLI `--version` flag for `python -m musicstreamer`.
- Build-SHA / dirty-flag in version string.
- Auto-tagging git releases on phase completion.
- Touching MPRIS / SMTC metadata to expose version.
- Changes to `pyproject.toml`'s version field, `tools/bump_version.py`, or the Phase 63 versioning policy.

</user_constraints>

<phase_requirements>
## Phase Requirements

CONTEXT.md `<canonical_refs>` notes that **no `VER-02` (or equivalent UI-visible-version requirement) currently exists in `.planning/REQUIREMENTS.md`**. Phase 63's `VER-01` covers the auto-bump; Phase 65 surfaces what `VER-01` produces. The CONTEXT recommends the planner backfill a single-line `VER-02` requirement at planning time so traceability matches Phase 63's shape — Kyle's call.

| ID | Description (recommended wording) | Research Support |
|----|-----------------------------------|------------------|
| VER-02 *(proposed; not yet in REQUIREMENTS.md)* | The running app surfaces its current version (read from `pyproject.toml` via `importlib.metadata`) as a disabled informational entry at the bottom of the hamburger menu. The Windows PyInstaller bundle ships `musicstreamer.dist-info` so the bundled exe reads the same version dev sees. | §Standard Stack (importlib.metadata, Qt6 setApplicationVersion, PyInstaller copy_metadata), §Implementation Approach, §Validation Architecture |

If Kyle prefers no new requirement, the phase is justified as a polish enhancement under the existing `VER-01` umbrella — but having a stub `VER-02` makes the menu-entry assertion traceable and future-proofs the verifier's REQ→test map.

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Version literal write site | Source-of-truth file (`pyproject.toml`) | — | Phase 63 made this the canonical write site via auto-bump hook. |
| Version read at runtime | Python stdlib (`importlib.metadata`) | — | Reads dist-info installed by `pip install -e .` / `uv sync`; same source dev/CI/bundle. |
| In-process version slot | Qt application object (`QCoreApplication`) | — | `setApplicationVersion` populated once in `_run_gui`; available everywhere via `applicationVersion()`. |
| UI surface | Qt widget tier (`QMenu` / `QAction`) | — | Hamburger menu footer entry; greyed informational `QAction`. |
| Bundle metadata shipping | PyInstaller spec (`copy_metadata`) | — | Packages dist-info into the Windows bundle; resolves `importlib.metadata` lookups inside the frozen exe. |
| Test surface | pytest unit tests (in-process) | — | Source-text checks + Qt menu introspection; no bundle build needed in phase scope. |

**Tier-correctness check:** Every capability is in its idiomatic tier — no UI-tier code reads `pyproject.toml` directly, no Qt code parses TOML, no PyInstaller spec hardcodes a version. The single literal lives in `pyproject.toml`; everything else is a read or a transport.

## Phase 63 / Phase 61 Precedent

**Already verified upstream — do not re-research:**

- **Phase 63 (auto-bump mechanism):** `pyproject.toml:7` contains `version = "2.1.63"`. The auto-bump runs via a Claude-Code Stop hook (`.claude/settings.json`) calling `tools/bump_version.py --phase NN`. Phase 65 is a **pure consumer** of this output — does not modify `pyproject.toml`, `tools/bump_version.py`, or the hook. Live verification: `uv run python -c 'from importlib.metadata import version; print(version("musicstreamer"))'` → `2.1.63` (matches pyproject).

- **Phase 61 (Qt application setup block):** `__main__.py:184-187` contains the canonical block of `setApplicationName` / `setApplicationDisplayName` / `setDesktopFileName`. Phase 65 D-07 adds `setApplicationVersion(...)` as a fourth peer in this same block. The pattern is verbatim — single line, one Qt setter call, ordered with peers.

## Open Questions (Resolved)

### Q1: PyInstaller `copy_metadata("musicstreamer")` shape — does it slot into `datas` like `collect_all`?

**Answer (HIGH):** Yes. `copy_metadata` returns a `list[tuple[str, str]]` of `(source_path, destination_basename)` pairs, ready to concatenate directly into the `datas=[...]` list — same shape that `collect_all`'s `_datas` returns.

`[CITED: pyinstaller.org/en/stable/hooks.html#PyInstaller.utils.hooks.copy_metadata]` — "Copy distribution metadata for the given package, including any subpackage metadata. Returns a list to be assigned to the datas global variable."

`[CITED: github.com/pyinstaller/pyinstaller/issues/1706]` — confirms tuples follow the standard `(src, dst)` PyInstaller datas format.

**The `.spec` edit shape (per CONTEXT D-08, planner's discretion on inlining):**

```python
# At top of MusicStreamer.spec, alongside existing collect_all import:
from PyInstaller.utils.hooks import collect_all, copy_metadata

# Near the existing collect_all block (line 25-33):
_ms_datas = copy_metadata("musicstreamer")  # returns list[(src, dst)] — shape matches _cn_datas / _sl_datas / _yt_datas

# Concatenated into the existing datas list (line 100-103):
datas=[
    ("../../musicstreamer/ui_qt/icons", "musicstreamer/ui_qt/icons"),
    ("icons/MusicStreamer.ico", "icons"),
] + _cn_datas + _sl_datas + _yt_datas + _ms_datas,
```

**Editable-install caveat (LOW relevance, MEDIUM-confidence answer):** PEP 660 editable installs (which `pip install -e .` and `uv sync` produce for setuptools-backend projects like this one) **do** create a real `dist-info` directory in `site-packages`, which `importlib.metadata` and `copy_metadata` both find correctly. Live verification on this repo's `.venv`:

```
.venv/lib/python3.X/site-packages/musicstreamer-2.1.63.dist-info/
.venv/lib/python3.X/site-packages/__editable__.musicstreamer-2.1.63.pth
```

The `.dist-info` directory exists alongside the editable `.pth` file. `[VERIFIED: ls .venv/lib/python*/site-packages/ | grep musicstreamer]`.

**However:** this caveat is irrelevant for the Windows bundle path. `build.ps1` runs `pyinstaller MusicStreamer.spec` on the Windows VM where `musicstreamer` is installed via `pip install <wheel>` (or `uv pip install`) into a non-editable conda env per Phase 43/44 spike findings. `copy_metadata("musicstreamer")` resolves against that real install's `dist-info` and produces a list of files copied into the bundle. There is **no editable-install path through PyInstaller** in this project.

`[CITED: peps.python.org/pep-0660/]` — "The wheel file must contain a compliant .dist-info directory."

`[CITED: github.com/pyinstaller/pyinstaller/issues/1888]` — historical issues with `copy_metadata` are around `.egg-info` (legacy, deprecated post-pip-24.2); modern `.dist-info` from setuptools / pip / uv is well supported.

**Risk if wrong:** The bundle build fails noisily at `pyinstaller` time with `PackageNotFoundError`-style error (not silent). D-08's "no try/except fallback" stance is correct — failing loudly during the build is preferable to a silent placeholder in production.

---

### Q2: `importlib.metadata.version("musicstreamer")` test surface — does pytest see it under `uv run pytest`?

**Answer (HIGH):** Yes, verified live in this repo's `.venv`:

```bash
$ uv run python -c "from importlib.metadata import version; print(version('musicstreamer'))"
2.1.63
```

`[VERIFIED: live shell run in this session, 2026-05-08]`

**Why it works:** `uv sync` installs the project in editable mode via PEP 660, which writes a real `musicstreamer-2.1.63.dist-info/` to `.venv/lib/python*/site-packages/`. `importlib.metadata.distributions()` finds this `PathDistribution` via the standard `sys.path`-walking search.

**`PackageNotFoundError` cases to be aware of:**

1. Running pytest without first running `uv sync` / `pip install -e .` — `sys.path` includes the source tree but no `dist-info` exists. Mitigation: this repo's developer workflow uses `uv run pytest`, which auto-syncs before running. Documented assumption.
2. Running tests against a package by adding the source tree to `sys.path` directly (e.g. via `conftest.py` `sys.path.insert(0, ...)`) without installing the package. **Not the case in this repo** — `tests/conftest.py` does no `sys.path` manipulation; pytest discovers the package via the editable install's `.pth` file.
3. Editable-install double-distribution — `[CITED: github.com/python/importlib_metadata/issues/481]` notes that some setuptools setups produce a `PathDistribution` for both the `dist-info` *and* a local `.egg-info`. `importlib.metadata.version("musicstreamer")` returns one of the two; in this repo's `.venv`, only the `dist-info` is present (verified — no `musicstreamer.egg-info/` in `site-packages` or repo root). Low risk.

`[CITED: docs.python.org/3.11/library/importlib.metadata.html]` — "version(distribution_name): For a given package name, return the version string."

**Test recommendation (recommended D-09 shape):**

```python
# tests/test_version.py
from importlib.metadata import version, PackageNotFoundError
import re
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent

def test_metadata_version_matches_pyproject():
    """The installed package's metadata version must match pyproject.toml's
    [project].version. This guards against a broken `uv sync` / `pip install -e`
    leaving an outdated dist-info in .venv (which would be invisible to a
    pyproject-only check)."""
    pyproject = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    expected = pyproject["project"]["version"]
    actual = version("musicstreamer")
    assert actual == expected, (
        f"importlib.metadata.version('musicstreamer') = {actual!r} but "
        f"pyproject.toml [project].version = {expected!r}. Run `uv sync` "
        f"to refresh .venv dist-info."
    )

def test_metadata_version_is_semver_shape():
    """Version string is M.m.p triple of integers (Phase 63 VER-01 contract)."""
    v = version("musicstreamer")
    assert re.match(r"^\d+\.\d+\.\d+$", v), f"Expected M.m.p triple, got {v!r}"
```

This shape avoids any Qt dependency and runs in <50ms. It's the simplest D-09 option (a) realisation.

**On the `v(unknown)` defensive fallback (D-11):** Research recommends **dropping it**. Rationale:

- `_run_gui` is the single startup path. If `importlib.metadata.version("musicstreamer")` raises `PackageNotFoundError` there, Kyle has bigger problems (broken install) and a hard fail at startup is more informative than a silently-rendered `v(unknown)`.
- The unit test from Q2 above guards the dev path.
- The bundle path is guarded by D-08's `copy_metadata` + the PyInstaller build itself failing if metadata is missing.
- The `v(unknown)` defensive fallback adds branching to a path that should never exist in a healthy installation. Belt-and-braces is a code smell in tight startup paths.

**Counter-argument:** if the planner wants belt-and-braces anyway, the cost is one `try/except PackageNotFoundError` in `__main__.py` and a `or "v(unknown)"` in the menu site. Cheap. Either way reads cleanly. CONTEXT.md leaves this to the planner.

---

### Q3: Qt `QCoreApplication.applicationVersion()` semantics

**Answer (HIGH):**

- **Before `QApplication(...)` is constructed:** Behaviour is undefined / app-may-crash territory — `QCoreApplication` accessor methods require the singleton to exist. **Don't read pre-construction.** In this codebase, MainWindow is constructed *after* `QApplication(argv)` at `__main__.py:184` so this is not a concern at the menu construction site.
- **After construction, before `setApplicationVersion(...)`:** Returns a platform-derived default — Windows VERSIONINFO, macOS CFBundleVersion, Android android:versionName. **On Linux it returns the empty string.** `[CITED: doc.qt.io/qt-6/qcoreapplication.html#applicationVersion-prop]` — "If not set, the application version defaults to a platform-specific value determined from the main application executable or package (since Qt 5.9). On other platforms, the default is the empty string."
- **After `setApplicationVersion("2.1.63")`:** Returns `"2.1.63"` exactly.
- **Threading:** Qt's docs do not explicitly mark `applicationVersion()` as thread-safe, but the property is a simple `QString` stored on the singleton and there's no locking documented. **Safe answer: read it from the main thread only** (which is where MainWindow construction always runs anyway). Phase 65 has zero cross-thread reads.

**The test-surface gotcha:** When `MainWindow` is constructed in pytest fixtures, `_run_gui` is **not** called — pytest-qt's `qtbot` provides a bare `QApplication` but does not invoke `setApplicationVersion`. Therefore `QCoreApplication.applicationVersion()` returns `""` in tests on Linux unless the test explicitly calls it.

**Hybrid read pattern (recommended):** At the menu construction site in `main_window.py`, prefer `applicationVersion()` if non-empty, else fall back to a direct `importlib.metadata.version("musicstreamer")` call:

```python
# musicstreamer/ui_qt/main_window.py — at the version action site (D-01)
from PySide6.QtCore import QCoreApplication

def _resolve_app_version() -> str:
    """Resolve the running app's version. Prefers the Qt slot
    (set by __main__._run_gui via D-07) so production reads cheaply.
    Falls back to importlib.metadata so unit tests that construct
    MainWindow without going through _run_gui still get a real string."""
    v = QCoreApplication.applicationVersion()
    if v:
        return v
    from importlib.metadata import version
    return version("musicstreamer")
```

This is a 6-line helper. It can live as a private function in `main_window.py` or in a tiny `musicstreamer/version.py` module (planner's call per CONTEXT discretion). The benefit of `version.py` is cleaner mocking in tests; the drawback is one more module for one function.

**Alternative (simpler, planner discretion):** Skip the hybrid entirely and call `importlib.metadata.version("musicstreamer")` inline at the menu site, ignoring the Qt slot at the read site (the Qt slot is still set in `__main__.py` per D-07 because Qt itself uses it for things like `QSettings` paths and crash-handler integration — that's a separate concern from in-app reads). This is fewer moving parts and the test surface is cleaner. **Research recommends this simpler path** unless the planner wants to lean on the Qt slot for symmetry with `setApplicationName` / `setApplicationDisplayName`.

---

### Q4: `addAction(label).setEnabled(False)` rendering on Qt6 Windows / Wayland

**Answer (HIGH):**

- **Greyed rendering:** `[CITED: doc.qt.io/qt-6/qaction.html#enabled-prop]` — "Disabled actions cannot be chosen by the user. They do not disappear from menus or toolbars, but they are displayed in a way which indicates that they are unavailable. For example, they might be displayed using only shades of gray." This holds on both Windows (Fusion style is forced for this app per `__main__.py:189`) and Wayland (default style, GNOME).
- **Keyboard navigation:** Qt's general navigation behaviour skips disabled items in focus chains `[CITED: doc.qt.io/qt-6/qmenu.html]`, but disabled QActions in a QMenu can still receive *visual* highlight (mouse hover, arrow-key transit) — they're just not triggerable. This is the standard, expected behaviour for an informational footer. Nothing to do here.
- **Platform quirks:** None documented for Qt6. There were Qt 4.8-era tickets `[CITED: bugreports.qt.io/browse/QTBUG-37024]` about disabled-rendering edge cases, but those are resolved in Qt5+. Qt6 + Fusion (Windows) + default GNOME (Wayland) both render greyed-out menu items consistently — verified empirically by every other Qt app on Linux (Firefox, GIMP, etc.).

**`addAction(...).setEnabled(False)` vs. `addSection(label)`:** The CONTEXT calls out both as options. Research recommends **`addAction + setEnabled(False)`** because:

1. `addSection` renders as a non-interactive header *with separator-style emphasis* (bold or underlined depending on style) — not the same visual idiom as a menu item.
2. The test surface for `addSection` is awkward — it returns an action but with `isSeparator()` semantics in some styles, breaking the existing `[a for a in menu.actions() if not a.isSeparator()]` filter used in `test_main_window_integration.py:422`.
3. `addAction + setEnabled(False)` is a one-line idiom every Qt developer recognises and tests trivially via `action.isEnabled() is False`.

`[CITED: copyprogramming.com/howto/non-interactive-items-in-qmenu]` — "Mastering Non-Interactive Items in QMenu: Qt 6.10 Best Practices" recommends `addAction + setEnabled(False)` for informational entries.

---

### Q5: `__version__.py` deletion safety — D-06a grep gate

**Answer (HIGH):** `[VERIFIED: live grep, 2026-05-08]`

```bash
$ git grep -l "from musicstreamer\\.__version__\\|musicstreamer/__version__\\|__version__\\.py\\|musicstreamer\\.__version__" -- ':!.planning' ':!.claude/worktrees' ':!.venv'
# (zero output)
```

```bash
$ git grep -n "__version__" -- ':!.planning' ':!.claude/worktrees' ':!.venv'
.claude/skills/spike-findings-musicstreamer/sources/43-gstreamer-windows-spike/build.ps1:72:        Invoke-Native { python -c "import gi, PyInstaller; print(f'PyInstaller={PyInstaller.__version__}  gi={gi.__version__}')" 2>&1 | Out-Host }
musicstreamer/__version__.py:13:__version__ = "2.0.0"
packaging/windows/build.ps1:85:        Invoke-Native { python -c "import gi, PyInstaller; print(f'PyInstaller={PyInstaller.__version__}  gi={gi.__version__}')" 2>&1 | Out-Host }
```

The only `__version__` hits outside `__version__.py` itself are `PyInstaller.__version__` / `gi.__version__` in build.ps1 diagnostic lines (third-party packages, unrelated to musicstreamer's `__version__.py`).

**Conclusion:** D-06a's gate is satisfied today. The deletion is safe. The plan should still re-run the grep at execution time as a belt-and-braces guard (a future Plan 65-XX task could in theory introduce a new importer between research time and execution time — extremely unlikely in a sequential single-user workflow but cheap to verify).

**Recommended grep command for the plan:**

```bash
git grep -nl "from musicstreamer\\.__version__\\|musicstreamer/__version__\\|__version__\\.py\\|musicstreamer\\.__version__" -- ':!.planning' ':!.claude/worktrees' ':!.venv' && exit 1 || echo "GREP_GATE_OK no remaining importers"
```

(Inverted exit — fails with exit code 1 if matches found, succeeds with `GREP_GATE_OK` otherwise.)

---

### Q6: `build.ps1` does not break when `__version__.py` is deleted

**Answer (HIGH):** `[VERIFIED: read packaging/windows/build.ps1:141-148]`

```powershell
# Read version from pyproject.toml (D-06) — passed to iscc.exe as /DAppVersion
$pyproject = Get-Content "..\..\pyproject.toml" -Raw
if ($pyproject -match '(?ms)^\[project\].*?^version\s*=\s*"([^"]+)"') {
    $appVersion = $matches[1]
} else {
    Write-Error "BUILD_FAIL reason=version_not_found_in_pyproject"
    exit 5
}
```

build.ps1 reads version exclusively from `pyproject.toml` via regex. `musicstreamer/__version__.py` is never opened, never imported, never referenced. **Deletion is safe for the build pipeline.**

**No build.ps1 edit is needed in Phase 65.** This phase touches only:

1. `musicstreamer/__main__.py` — one-line `setApplicationVersion` add.
2. `musicstreamer/ui_qt/main_window.py` — separator + disabled action + (optional) helper.
3. `musicstreamer/__version__.py` — `git rm`.
4. `packaging/windows/MusicStreamer.spec` — `copy_metadata` import + datas concatenation.
5. New tests.
6. *(Optional)* `musicstreamer/version.py` — tiny helper (planner's discretion).

---

### Q7: Validation Architecture

See dedicated §Validation Architecture below.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `importlib.metadata` | Python 3.10+ stdlib | Read installed-package version at runtime | Stdlib, zero install cost, single-source-of-truth read pattern. Already implicitly used via `tomllib` in this repo's tests. |
| PySide6 (`QCoreApplication`, `QMenu`, `QAction`) | 6.11+ (per pyproject) | Qt application slot + UI surface | Already the project's GUI framework. |
| `PyInstaller.utils.hooks.copy_metadata` | PyInstaller 6.x | Ship dist-info in Windows bundle | Already used pattern (`collect_all` for charset_normalizer / streamlink / yt_dlp). `copy_metadata` is the lighter sibling for our own package. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tomllib` | Python 3.11+ stdlib | Read `pyproject.toml` in tests | Asserts metadata version matches pyproject's `[project].version`. Already used in `tests/test_media_keys_smtc.py:9, 148`. |
| `pytest-qt` (`qtbot` fixture) | 4.x (per pyproject `[project.optional-dependencies].test`) | Construct MainWindow in tests | Existing fixture; no new dependency. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `importlib.metadata.version("musicstreamer")` | Hard-coded literal (the status quo of `__version__.py`) | Drift risk — Phase 63 auto-bump rewrites `pyproject.toml` only. The literal becomes stale on every phase. **Not viable.** |
| `importlib.metadata.version("musicstreamer")` | Parse `pyproject.toml` at runtime via `tomllib` | Works, but: (a) `pyproject.toml` isn't shipped in the PyInstaller bundle by default, (b) requires bundle path discovery, (c) adds a parser to the runtime path. `importlib.metadata` is purpose-built for this. **Use importlib.metadata.** |
| `app.setApplicationVersion(...)` | Skip Qt slot, read `importlib.metadata` directly at the menu site only | Works, but loses the symmetry with `setApplicationName` / `setApplicationDisplayName` and forfeits Qt's own use of the slot (e.g. `QSettings` Windows-registry paths use `applicationVersion`). CONTEXT D-07 locks: set the Qt slot. |
| `copy_metadata("musicstreamer")` | `--copy-metadata musicstreamer` CLI flag in `build.ps1` | Equivalent semantically but mixes concerns — version-shipping decisions belong in the `.spec` next to other bundle-content decisions. CONTEXT D-08 locks: spec edit. |

**Installation:** No new dependencies. Everything is already in `pyproject.toml` or stdlib.

**Version verification:**

`[VERIFIED: live shell run, 2026-05-08]`
- Python `importlib.metadata`: stdlib in 3.10+, no version pin needed. This repo's `requires-python = ">=3.10"`.
- PySide6: project pins `PySide6>=6.11` in `pyproject.toml:13`. `QCoreApplication.applicationVersion` exists since Qt 4.4; `setApplicationVersion` since Qt 4.4. No version concerns.
- PyInstaller: project's Windows VM uses PyInstaller 6.x (per Phase 43/44 spike findings). `copy_metadata` exists since PyInstaller 3.4. No version concerns.

## Implementation Approach

This section is the concrete file-level shape the planner builds tasks against. Confidence is HIGH on all four edits.

### Edit 1: `musicstreamer/__main__.py` — D-07

Add one line in the existing Qt setup block at `__main__.py:184-187`:

```python
# Existing block:
app = QApplication(argv)
app.setApplicationName("MusicStreamer")              # D-07 (Phase 61): keep
app.setApplicationDisplayName("MusicStreamer")       # D-06 (Phase 61): NEW
# NEW Phase 65 D-07:
from importlib.metadata import version as _pkg_version
app.setApplicationVersion(_pkg_version("musicstreamer"))
app.setDesktopFileName(constants.APP_ID)             # D-02 (Phase 61): read from constants
```

Placement: between `setApplicationDisplayName` and `setDesktopFileName` per CONTEXT D-07. The `from importlib.metadata import version as _pkg_version` import can either be at the top of the file (stdlib, free) or inline-imported here (matches the existing inline-import style used at `__main__.py:172, 175, 178, 180-182, 195, 203` for lazy/conditional imports). **Recommended: top-level import** — it's stdlib, the cost is zero, and stdlib imports go at the top by PEP 8 convention.

If the planner prefers a helper module (CONTEXT discretion), this becomes:

```python
from musicstreamer.version import get_version
app.setApplicationVersion(get_version())
```

### Edit 2: `musicstreamer/ui_qt/main_window.py` — D-01, D-02, D-03

**Imports (top of file, after existing `PySide6.QtCore` block at line 32):**

```python
# If using QCoreApplication path (hybrid resolver):
from PySide6.QtCore import QCoreApplication
# (Append to existing line 32: `from PySide6.QtCore import Qt, QThread, Signal, QCoreApplication`)
```

If using direct `importlib.metadata` at the menu site (simpler, recommended):

```python
from importlib.metadata import version as _pkg_version  # top-of-file, stdlib
```

**Menu construction edit (after line 229, the Phase 44 D-13 Node-missing block):**

```python
# Phase 65 D-01/D-02/D-03/D-12: version footer. Always last, always disabled.
# Read via importlib.metadata so this works without _run_gui having been
# called (test fixtures construct MainWindow without going through __main__).
self._menu.addSeparator()
self._act_version = self._menu.addAction(f"v{_pkg_version('musicstreamer')}")
self._act_version.setEnabled(False)
```

This is six lines including the comment. The `self._act_version` retention follows the existing `self._act_*` convention (`self._act_stats`, `self._act_export`, `self._act_import_settings`, `self._act_node_missing`). Retention is **technically optional** (the action is static and disabled) but enables introspection in tests without re-walking `_menu.actions()`.

**Order guarantee:** This block runs *after* the conditional Phase 44 Node-missing block, so when Node is missing the order is:
- ... existing actions ...
- separator (Phase 47.1 stats group)
- Stats for Nerds
- separator
- Export Settings, Import Settings
- separator (Phase 44 D-13 conditional)
- Node-missing entry (conditional)
- **separator (Phase 65 D-02, NEW)**
- **v2.1.63 (Phase 65 D-01, NEW, disabled)**

When Node is *not* missing, the Phase 44 separator + Node-missing entry are absent; Phase 65's separator is the third (instead of fourth) separator and the version action is the last entry.

### Edit 3: `musicstreamer/__version__.py` — D-06

```bash
git rm musicstreamer/__version__.py
```

Pre-deletion gate: re-run the D-06a grep (see Q5).

### Edit 4: `packaging/windows/MusicStreamer.spec` — D-08

**Import (line 17, alongside existing `collect_all`):**

```python
from PyInstaller.utils.hooks import collect_all, copy_metadata
```

**Datas computation (alongside existing `_cn_datas` etc., near line 33):**

```python
# Phase 65 D-08: ship musicstreamer's dist-info so importlib.metadata.version
# resolves inside the bundle. No try/except fallback — bundle build must fail
# loudly if metadata is missing rather than ship a silent placeholder.
_ms_datas = copy_metadata("musicstreamer")
```

**Concatenation into `datas=` (line 100-103):**

```python
datas=[
    ("../../musicstreamer/ui_qt/icons", "musicstreamer/ui_qt/icons"),
    ("icons/MusicStreamer.ico", "icons"),
] + _cn_datas + _sl_datas + _yt_datas + _ms_datas,
```

That's it. No other spec changes.

### Optional Edit 5: `musicstreamer/version.py` — helper module (planner's call)

Tiny three-line module if the planner wants a single mockable read site:

```python
"""Single read-site for the running app's version.

Reads from the installed package's dist-info via importlib.metadata so the
canonical source remains pyproject.toml [project].version (Phase 63 auto-bump).
"""
from importlib.metadata import version


def get_version() -> str:
    """Return the running app's version (e.g. '2.1.63'). Raises
    PackageNotFoundError if the package's dist-info is missing — signals a
    broken install (`uv sync` not run, or PyInstaller bundle missing
    copy_metadata)."""
    return version("musicstreamer")
```

Trades 12 lines of new file for a single mockable function in tests. Useful if the planner wants to stub `get_version` in MainWindow tests instead of stubbing the broader `importlib.metadata.version` function. **Not strictly needed.**

## Test Strategy

### Unit tests (in-process, fast)

#### Test 1: `tests/test_version.py` (NEW, recommended) — read mechanism

```python
"""Phase 65 / VER-02 — version read-mechanism tests."""
from __future__ import annotations

import re
import tomllib
from importlib.metadata import version
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def test_metadata_version_matches_pyproject():
    pyproject = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    expected = pyproject["project"]["version"]
    assert version("musicstreamer") == expected, (
        "importlib.metadata version diverged from pyproject — "
        "run `uv sync` to refresh .venv dist-info."
    )


def test_metadata_version_is_semver_triple():
    """VER-02 contract: M.m.p triple of integers (Phase 63 VER-01 shape)."""
    assert re.match(r"^\d+\.\d+\.\d+$", version("musicstreamer"))
```

Two assertions, ~30 lines including docstrings. Runs in milliseconds.

#### Test 2: `tests/test_main_window_integration.py` — extend existing menu tests

The existing `EXPECTED_ACTION_TEXTS` list at `test_main_window_integration.py:404-416` does **not** include the version entry. The plan needs to update this list and the separator-count test:

```python
# UPDATE EXPECTED_ACTION_TEXTS to include the version footer:
EXPECTED_ACTION_TEXTS = [
    "New Station",
    "Discover Stations",
    "Import Stations",
    "Add GBS.FM",
    "Search GBS.FM…",
    "Accent Color",
    "Accounts",
    "Equalizer",
    "Stats for Nerds",
    "Export Settings",
    "Import Settings",
    # Phase 65 D-01: version footer, format "v{version}"
    # Asserted via regex in a separate test because the literal version
    # changes every phase via Phase 63 auto-bump.
]


def test_hamburger_menu_actions(window):
    """Hamburger menu's first 11 non-separator actions match the expected list;
    the 12th is the Phase 65 version footer (asserted via regex)."""
    menu = window._menu
    actions = [a for a in menu.actions() if not a.isSeparator()]
    texts = [a.text() for a in actions]
    assert texts[:11] == EXPECTED_ACTION_TEXTS
    assert len(actions) == 12
    assert re.match(r"^v\d+\.\d+\.\d+$", texts[11]), (
        f"Last menu action must be Phase 65 version footer, got {texts[11]!r}"
    )


def test_hamburger_menu_separators(window):
    """Phase 65 D-02 adds a 4th separator before the version footer."""
    menu = window._menu
    separators = [a for a in menu.actions() if a.isSeparator()]
    assert len(separators) == 4  # was 3 before Phase 65


def test_version_action_is_disabled_and_last(window):
    """Phase 65 D-03/D-12: version footer is disabled and is the literal last
    entry (regardless of Node-missing presence)."""
    menu = window._menu
    actions = list(menu.actions())
    assert actions[-1] is window._act_version
    assert window._act_version.isEnabled() is False
    assert re.match(r"^v\d+\.\d+\.\d+$", window._act_version.text())
```

#### Test 3: `tests/test_main_run_gui_ordering.py` — extend with setApplicationVersion source-position guard

Phase 61 established the source-text-ordering test pattern. Phase 65 D-07 adds a setter to the same block; the test should assert it's wired in `_run_gui`:

```python
def test_set_application_version_in_run_gui(main_source: str) -> None:
    """Phase 65 D-07: setApplicationVersion is called in _run_gui after
    QApplication construction (so the singleton exists), and uses
    importlib.metadata.version (not a hardcoded literal)."""
    qapp = _index(main_source, "QApplication(argv)")
    setver = _index(main_source, "setApplicationVersion(")
    assert setver > qapp, (
        "app.setApplicationVersion(...) must run AFTER QApplication(argv) "
        "construction so the application singleton exists. "
        f"Got QApplication @ byte {qapp}, setApplicationVersion @ byte {setver}."
    )
    # D-07 contract: must read via importlib.metadata, not a literal.
    assert "importlib.metadata" in main_source or "version(" in main_source[setver:setver+200], (
        "setApplicationVersion must read via importlib.metadata.version, "
        "not a hardcoded literal — single-source-of-truth in pyproject.toml."
    )
```

#### Test 4: `tests/test_constants_drift.py` or new `tests/test_pkg03_compliance.py` — bundle copy_metadata reference

If the existing `test_pkg03_compliance.py` covers the PyInstaller spec, extend it. Otherwise add a tiny test that reads `MusicStreamer.spec` as text and asserts `copy_metadata("musicstreamer")` is referenced:

```python
def test_spec_includes_copy_metadata_for_musicstreamer():
    """Phase 65 D-08: the PyInstaller spec must ship musicstreamer's dist-info
    so importlib.metadata.version resolves inside the bundle."""
    spec = (Path(__file__).resolve().parent.parent / "packaging" / "windows" / "MusicStreamer.spec").read_text()
    assert "copy_metadata" in spec, "spec must import copy_metadata"
    assert 'copy_metadata("musicstreamer")' in spec or "copy_metadata('musicstreamer')" in spec, (
        "spec must call copy_metadata('musicstreamer') so dist-info ships in the bundle"
    )
```

Source-text test — runs without needing PyInstaller installed in the test env. Same pattern as `test_main_run_gui_ordering.py`.

### Bundle smoke (out of scope for in-process tests)

CONTEXT D-09 lists three options. Research recommends **option (a) — in-process unit tests above**. Options (b) `--print-version` flag and (c) post-build dist-info inspection are deferred:

- (b) requires adding a CLI flag to `__main__.py` (CONTEXT explicitly scopes this OUT of Phase 65).
- (c) requires running the Windows build in CI, which doesn't currently happen — `build.ps1` is invoked manually on Kyle's Win11 VM.

The in-process tests guard the **dev** path (where Phase 65's bug is most likely to surface — running `uv run python -m musicstreamer` and seeing `v2.1.63` in the menu). The bundle path is guarded structurally by D-08's `copy_metadata` + the build itself failing if metadata is missing. If a regression slips through to the bundle anyway, Kyle catches it on the next manual build/UAT.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest>=9` + `pytest-qt>=4` (per `pyproject.toml:27-28`) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` (line 50-54) |
| Quick run command | `uv run pytest tests/test_version.py tests/test_main_run_gui_ordering.py -x` |
| Full suite command | `uv run pytest -x` |

### Phase Requirements → Test Map

| Req ID | Behaviour | Test Type | Automated Command | File Exists? |
|--------|-----------|-----------|-------------------|-------------|
| VER-02-A | `importlib.metadata.version("musicstreamer")` returns the same string as `pyproject.toml [project].version` | unit | `uv run pytest tests/test_version.py::test_metadata_version_matches_pyproject -x` | ❌ Wave 0 |
| VER-02-B | Returned version string is M.m.p triple of integers | unit | `uv run pytest tests/test_version.py::test_metadata_version_is_semver_triple -x` | ❌ Wave 0 |
| VER-02-C | Hamburger menu's last non-separator entry matches `^v\d+\.\d+\.\d+$` | unit (pytest-qt) | `uv run pytest tests/test_main_window_integration.py::test_version_action_is_disabled_and_last -x` | ❌ Wave 0 (extend existing file) |
| VER-02-D | The version action is disabled (`isEnabled() is False`) | unit (pytest-qt) | (same as above) | ❌ Wave 0 |
| VER-02-E | Hamburger menu has exactly one new separator before the version action (4 total, was 3) | unit (pytest-qt) | `uv run pytest tests/test_main_window_integration.py::test_hamburger_menu_separators -x` | ✅ exists, needs count-update |
| VER-02-F | `app.setApplicationVersion(...)` is invoked in `_run_gui` after `QApplication(argv)` | unit (source-text) | `uv run pytest tests/test_main_run_gui_ordering.py::test_set_application_version_in_run_gui -x` | ✅ exists, extend with new test fn |
| VER-02-G | `__version__.py` deleted; zero remaining importers | shell (grep gate, pre-commit) | `! git grep -l "from musicstreamer\\.__version__\\|musicstreamer/__version__\\|__version__\\.py\\|musicstreamer\\.__version__" -- ':!.planning' ':!.claude/worktrees' ':!.venv'` | N/A — shell |
| VER-02-H | PyInstaller spec includes `copy_metadata("musicstreamer")` reference | unit (source-text) | `uv run pytest tests/test_pkg03_compliance.py::test_spec_includes_copy_metadata_for_musicstreamer -x` *(new function or new file — planner picks)* | ❓ planner picks file |
| VER-02-I *(deferred — manual)* | Kyle visually sees `v2.1.63` at the bottom of the hamburger menu when launching the dev app | manual | `uv run python -m musicstreamer` and open hamburger menu | N/A — UAT |
| VER-02-J *(deferred — manual)* | The Windows-bundled exe shows the same `v2.1.63` in its hamburger menu | manual | run installer, launch, open hamburger menu | N/A — Win VM UAT |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_version.py tests/test_main_window_integration.py tests/test_main_run_gui_ordering.py -x` (≈ 5-10 sec)
- **Per wave merge:** `uv run pytest -x` (full suite, ≈ 30-60 sec)
- **Phase gate:** Full suite green + manual UAT items VER-02-I, VER-02-J before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_version.py` — covers VER-02-A, VER-02-B (NEW file, ~30 lines)
- [ ] `tests/test_main_window_integration.py` — extend `EXPECTED_ACTION_TEXTS`, update `test_hamburger_menu_separators` count from 3 → 4, add `test_version_action_is_disabled_and_last` (covers VER-02-C, VER-02-D, VER-02-E)
- [ ] `tests/test_main_run_gui_ordering.py` — add `test_set_application_version_in_run_gui` (covers VER-02-F)
- [ ] `tests/test_pkg03_compliance.py` (or new `tests/test_packaging_spec.py`) — add `test_spec_includes_copy_metadata_for_musicstreamer` (covers VER-02-H)
- [ ] No new framework install — `pytest>=9` and `pytest-qt>=4` already in `[project.optional-dependencies].test`.

## Landmines / Risks

### Landmine 1: pytest fixtures don't run `_run_gui` → `QCoreApplication.applicationVersion()` returns `""` in tests

**Severity:** MEDIUM (test-surface only; production path unaffected)

**What goes wrong:** If the menu construction site reads `QCoreApplication.applicationVersion()` directly (per CONTEXT D-11 default), tests that construct MainWindow via `qtbot` get an empty string and the menu entry renders as `v` (just the prefix). Test assertions on `r"^v\d+\.\d+\.\d+$"` fail.

**Why it happens:** `setApplicationVersion(...)` is called in `_run_gui` (D-07), but tests skip `_run_gui` and use pytest-qt's bare `QApplication`.

**How to avoid:** Use the hybrid resolver pattern from Q3 — fall back to `importlib.metadata.version("musicstreamer")` if `QCoreApplication.applicationVersion()` is empty. **OR** simpler: skip the Qt slot at the read site entirely and call `importlib.metadata.version` directly in `main_window.py` (the Qt slot in `__main__.py` per D-07 is independently valuable for Qt internals — `QSettings`, crash-handler integration — even if no in-app code reads from it).

**Detection:** The proposed `test_version_action_is_disabled_and_last` test will RED on day one if the planner picks a pure `applicationVersion()` read with no fallback.

**Recommended fix:** Use direct `importlib.metadata.version("musicstreamer")` at the menu site. Cleanest test surface. Set `setApplicationVersion` in `_run_gui` per D-07 for Qt-internal reasons, but don't have in-app code depend on it.

---

### Landmine 2: Editable-install double-distribution (`dist-info` + `egg-info`)

**Severity:** LOW (already verified clean in this repo's `.venv`)

**What goes wrong:** `[CITED: github.com/python/importlib_metadata/issues/481]` — some setuptools editable installs produce *both* a `.dist-info` directory in `site-packages` and a `.egg-info` directory in the source tree. `importlib.metadata.distributions()` finds both as separate `PathDistribution`s; `version("musicstreamer")` returns one of them (typically whichever appears first on `sys.path`).

**Why it happens:** Mixing legacy `python setup.py develop` with modern `pip install -e .` / `uv sync` in the same checkout.

**How to avoid:** Verified at research time — this repo's `.venv` has only the modern `dist-info`, no `.egg-info` in source tree:

```
.venv/lib/python*/site-packages/musicstreamer-2.1.63.dist-info/   ← only one
```

`[VERIFIED: ls .venv/lib/python*/site-packages/]`

**Detection:** Test 1 (`test_metadata_version_matches_pyproject`) catches it — if the wrong distribution wins, the version returned won't match pyproject.

---

### Landmine 3: Bundle missing `copy_metadata` produces silent or noisy failure

**Severity:** MEDIUM (production-surface; caught by manual UAT)

**What goes wrong:** Without D-08's `copy_metadata("musicstreamer")` in the spec, the PyInstaller bundle doesn't ship `musicstreamer.dist-info`. At runtime in the bundled exe, `importlib.metadata.version("musicstreamer")` raises `PackageNotFoundError`.

**Why it happens:** PyInstaller does not include package metadata by default. `[CITED: github.com/pyinstaller/pyinstaller/issues/5814]` — "Always copy metadata, on a best-effort basis" — is an open-since-2021 PyInstaller issue. Not the default behaviour.

**How to avoid:** D-08 mandates the spec edit. CONTEXT explicitly forbids a try/except fallback.

**Detection:** The bundle launches, the user opens the hamburger menu, and sees... an unhandled exception toast or an `ImportError: ...PackageNotFoundError` in the log. **Loud, not silent** — which is what we want.

**Mitigation if ever caught:** Re-add `copy_metadata` and rebuild. The `test_spec_includes_copy_metadata_for_musicstreamer` source-text test guards against accidentally removing it.

---

### Landmine 4: The `≡` (U+2261) hamburger glyph and `v2.1.63` rendering on Wayland

**Severity:** LOW (cosmetic; no functional impact)

**What goes wrong:** The hamburger menu label is `≡` (U+2261 IDENTICAL TO) per `main_window.py:164`. Some font fallback paths on Wayland render U+2261 as a tofu (□) if the Qt-default font has no glyph. This is **pre-existing** and unrelated to Phase 65 — Phase 65 only adds an entry *inside* the menu, not the launcher glyph.

**The version label** is pure ASCII (`v2.1.63`) — no Unicode glyph concerns.

**How to avoid:** N/A — Phase 65 doesn't touch the hamburger glyph.

---

### Landmine 5: Phase 63 auto-bump runs after Phase 65 completes → version assertions might race

**Severity:** LOW (test ordering)

**What goes wrong:** Phase 63's auto-bump hook runs on phase **completion** and rewrites `pyproject.toml`'s version to e.g. `2.1.65`. If a test asserts a literal `2.1.65` it would have to be updated at the moment of completion — same race as any phase that introduces version-aware tests.

**How to avoid:** Tests assert via regex (`^\d+\.\d+\.\d+$`) and via `tomllib.loads(pyproject.toml)["project"]["version"]` rather than literals. The proposed test surface follows this rule exclusively. **No literal version strings in tests.**

---

### Landmine 6: `addAction` with f-string evaluated at construction → version appears stale on hot-reload

**Severity:** ZERO (irrelevant — there is no hot-reload path)

**What goes wrong:** The label is computed at MainWindow construction time (`f"v{_pkg_version('musicstreamer')}"`). If the user somehow upgraded the package without restarting the app, the menu would show stale text.

**Why it happens:** It doesn't, in this product. There is no live-reload, no over-the-air update, and the only way the version changes is via Phase 63's auto-bump on phase completion (which the dev triggers themselves and which requires an app restart anyway). **No mitigation needed.**

## Reference Docs

### Primary (HIGH confidence)

- `[CITED: doc.qt.io/qt-6/qcoreapplication.html#applicationVersion-prop]` — `setApplicationVersion` / `applicationVersion` semantics, platform defaults, since-Qt-4.4.
- `[CITED: doc.qt.io/qt-6/qaction.html#enabled-prop]` — `setEnabled(false)` rendering and trigger semantics.
- `[CITED: doc.qt.io/qt-6/qmenu.html]` — QMenu navigation and disabled-action handling.
- `[CITED: pyinstaller.org/en/stable/hooks.html#PyInstaller.utils.hooks.copy_metadata]` — `copy_metadata` return shape and usage with `datas`.
- `[CITED: docs.python.org/3.11/library/importlib.metadata.html]` — `version(distribution_name)` and `PackageNotFoundError`.
- `[CITED: peps.python.org/pep-0660/]` — editable installs produce a real `.dist-info` directory.

### Secondary (MEDIUM confidence)

- `[CITED: github.com/pyinstaller/pyinstaller/issues/1706]` — `copy_metadata` documentation discussion (tuple format).
- `[CITED: github.com/pyinstaller/pyinstaller/issues/5814]` — PyInstaller does not collect metadata by default (rationale for D-08).
- `[CITED: github.com/python/importlib_metadata/issues/481]` — editable-install double-distribution edge case.
- `[CITED: copyprogramming.com/howto/non-interactive-items-in-qmenu]` — Qt 6.10 best practices for non-interactive menu entries.

### Repo-internal references

- `[VERIFIED: pyproject.toml:7]` — `version = "2.1.63"`.
- `[VERIFIED: musicstreamer/__main__.py:184-187]` — Qt setup block.
- `[VERIFIED: musicstreamer/ui_qt/main_window.py:163-229]` — hamburger menu construction.
- `[VERIFIED: musicstreamer/__version__.py]` — current contents (`__version__ = "2.0.0"`).
- `[VERIFIED: packaging/windows/MusicStreamer.spec:17, 25-33, 100-103]` — collect_all imports and datas concatenation pattern.
- `[VERIFIED: packaging/windows/build.ps1:141-148]` — pyproject.toml regex parse for `/DAppVersion`.
- `[VERIFIED: tests/test_main_window_integration.py:404-431]` — existing menu-entry and separator-count tests (need updating).
- `[VERIFIED: tests/test_main_run_gui_ordering.py]` — source-text ordering test pattern.
- `[VERIFIED: live grep, 2026-05-08]` — D-06a gate is satisfied; zero importers of `musicstreamer.__version__`.
- `[VERIFIED: live shell run]` — `uv run python -c 'from importlib.metadata import version; print(version("musicstreamer"))'` returns `2.1.63`.
- `[VERIFIED: ls .venv/lib/python*/site-packages/]` — `musicstreamer-2.1.63.dist-info/` present alongside the editable `.pth`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The Windows VM build runs PyInstaller against a non-editable install (per Phase 43/44 spike findings) so editable-install caveats don't apply to the bundle path. | Q1 | LOW — if the VM uses an editable install, `copy_metadata` still finds the dist-info per PEP 660; verified locally. |
| A2 | `pytest-qt`'s `qtbot` fixture provides a bare `QApplication` *without* calling `setApplicationVersion`. | Q3 / Landmine 1 | LOW — verified by reading `tests/conftest.py` (no `setApplicationVersion` call) + standard pytest-qt behaviour. If wrong, the hybrid resolver pattern handles both cases anyway. |
| A3 | The recommended `VER-02` requirement ID is not yet taken in `.planning/REQUIREMENTS.md`. | §Phase Requirements | LOW — if taken, planner picks `VER-03` or `UI-XX` instead. Cosmetic. |

**Confirmation needed before locking the plan:** None of the above blocks planning. A2 is the most consequential — but the recommended fix (read `importlib.metadata` directly at the menu site, with the Qt slot set in `_run_gui` for Qt-internal use) sidesteps the issue entirely.

## Open Questions (truly unresolved)

None. All seven questions in the research scope are answered with HIGH or HIGH-MEDIUM confidence. The only items left to the planner are CONTEXT-discretion choices already enumerated under `<user_constraints>`.

## Project Constraints (from CLAUDE.md)

- **Routing:** Spike findings for MusicStreamer (Windows packaging patterns, GStreamer+PyInstaller+conda-forge, PowerShell gotchas) → `Skill("spike-findings-musicstreamer")`. **Phase 65 relevance:** the spike skill confirms PyInstaller+conda-forge bundling pattern (Phase 43/44) — `copy_metadata` is a small additive change to that proven pattern. No GStreamer / GLib threading work in Phase 65 scope.

## Project conventions applied (from CONTEXT canonical_refs)

- **QA-05** (bound-method signal connections, no self-capturing lambdas) — N/A for the disabled action (no signal connection); applies if the planner introduces any future click handler.
- **`self._act_*` retention pattern** — `self._act_version` follows the convention.
- **`importlib.metadata` is stdlib** — no new dependency. Tests already use `tomllib` (same shape).
- **PyInstaller spec convention** — `copy_metadata` is the lighter-weight choice for our own package vs. `collect_all` (we only need dist-info, not binaries / submodules).
- **Linux Wayland deployment, DPR=1.0** — N/A for Phase 65 (no rendering / DPR concerns).
- **snake_case + type hints throughout, no formatter** (per `.planning/codebase/CONVENTIONS.md`).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library is stdlib or already in pyproject.toml.
- Architecture: HIGH — every edit lands in a documented, precedent-following slot (Phase 61 + Phase 63 + Phase 44 all blueprint this).
- Pitfalls: HIGH — landmines verified or sidestepped at research time (D-06a grep gate clean; live `importlib.metadata` returns expected value; .venv has clean dist-info).

**Research date:** 2026-05-08
**Valid until:** 2026-06-08 (30 days — stable APIs; only risk is a major PyInstaller release breaking `copy_metadata` shape, which is highly unlikely).

## RESEARCH COMPLETE

**Phase:** 65 - Show current version in app
**Confidence:** HIGH

### Key Findings
1. **D-06a grep gate is satisfied today** — zero remaining importers of `musicstreamer.__version__`. Deletion is safe; build.ps1 reads pyproject.toml directly.
2. **`importlib.metadata.version("musicstreamer")` returns `"2.1.63"` live in this repo's `.venv`** — `uv sync` produces a real `.dist-info` directory alongside the editable `.pth`, so test surface works without ceremony.
3. **`copy_metadata("musicstreamer")` slots into `datas` exactly like the existing `collect_all` blocks** — single-line `from PyInstaller.utils.hooks import copy_metadata`, single concatenation `+ _ms_datas` at line 103.
4. **Qt slot vs. menu read site is decoupled by design** — set `setApplicationVersion` in `_run_gui` per D-07 (Qt internals consume it), but read `importlib.metadata.version` directly at the menu construction site so pytest-qt fixtures don't need to fake `_run_gui`.
5. **No new dependencies, no spec format change, no build.ps1 edit, no Phase 63 auto-bump touchpoint** — Phase 65 is a pure consumer of Phase 63's output.

### File Created
`/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/phases/65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb/65-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | Every library is stdlib or already in pyproject.toml; live-verified `importlib.metadata` return value. |
| Architecture | HIGH | Each edit slots into a precedent block (Phase 61 setup line; Phase 44 menu-entry pattern; Phase 44 spec collect_all pattern). |
| Pitfalls | HIGH | All six landmines either verified safe at research time or have a recommended sidestep documented. |

### Open Questions
None — all seven scope questions answered with HIGH confidence. Planner's discretion items (action variable name, helper module, test placement) are cosmetic.

### Ready for Planning
Research complete. Planner can now create plans against the four edits in §Implementation Approach and the four-test surface in §Test Strategy / §Validation Architecture.
