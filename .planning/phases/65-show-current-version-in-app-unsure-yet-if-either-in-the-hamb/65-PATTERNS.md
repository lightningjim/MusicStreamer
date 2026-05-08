# Phase 65: Show current version in app - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 8 (4 source + 4 test)
**Analogs found:** 8 / 8 (all in-repo precedents)

## Drift Summary (CONTEXT/RESEARCH cited line numbers vs. current source)

| File | Cited | Actual | Status |
|------|-------|--------|--------|
| `musicstreamer/__main__.py` setup block | 184-187 | 184-187 (line 184 = `app = QApplication(argv)`; setters span 185-187) | OK — citation is "block 184-187" inclusive of QApplication construction; setter trio is 185-187 |
| `musicstreamer/ui_qt/main_window.py` menu construction | 162-229 | 162-229 | OK — verified verbatim |
| `main_window.py` separators | 184, 197, 206 | 184, 197, 206 | OK |
| `main_window.py` `self._act_stats` | 200-205 | 200-205 | OK |
| `main_window.py` `self._act_export` / `_act_import_settings` | 211-214 | 211-214 | OK |
| `main_window.py` `self._act_node_missing` | 220-229 | 220-229 (entry at 226-229; conditional `if` at 224; separator at 225) | OK |
| `musicstreamer/__version__.py` stale literal | `__version__ = "2.0.0"` line 13 | line 13: `__version__ = "2.0.0"` | OK — confirmed stale |
| `MusicStreamer.spec` collect_all + datas | 25-33, 100-103 | 25-33 (collect_all triple), 100-103 (datas list with `+ _cn_datas + _sl_datas + _yt_datas`) | OK |
| `MusicStreamer.spec` hook import | line 17 | line 17: `from PyInstaller.utils.hooks import collect_all` | OK |
| `tests/test_main_window_integration.py` `EXPECTED_ACTION_TEXTS` | 404-416 | 404-416 (11 entries) | OK |
| `tests/test_main_window_integration.py` separator test | 422 ("isSeparator filter"); 427-431 (separator-count test) | 422 + 427-431 | OK |
| `tests/test_main_run_gui_ordering.py` | exists | exists, 52 lines | OK |
| `tests/test_media_keys_smtc.py` tomllib | 9, 148 | 9 (`import tomllib`), 148 (`tomllib.load(f)`) | OK |
| `tests/test_pkg03_compliance.py` | exists, "PKG-03 hook test pattern" | exists, 31 lines — but it is a **source-tree grep test against `musicstreamer/*.py`**, NOT a PyInstaller-spec source-text assertion test | **DRIFT** — see VER-02-H row below |

**Notable drift:** `test_pkg03_compliance.py` does not contain an analog for asserting against `MusicStreamer.spec` text. The closest existing precedent for the VER-02-H source-text assertion is **`test_main_run_gui_ordering.py`** (source-text + `_index` pattern), not `test_pkg03_compliance.py`. The planner can still extend `test_pkg03_compliance.py` if they want to keep PKG-* compliance tests co-located, but the *pattern* to copy comes from `test_main_run_gui_ordering.py`. Recommendation: new `tests/test_packaging_spec.py` modelled after `test_main_run_gui_ordering.py`.

---

## File Classification & Pattern Assignments

### 1. `musicstreamer/__main__.py` (MODIFY) — Qt application setter, request-response

**Role:** application bootstrap (setter idempotent). **Data Flow:** one-shot startup configuration.

**Closest analog:** `musicstreamer/__main__.py:185-187` (the existing `setApplicationName` / `setApplicationDisplayName` / `setDesktopFileName` trio — Phase 61 precedent).

**Excerpt (lines 184-190):**
```python
app = QApplication(argv)
app.setApplicationName("MusicStreamer")              # D-07: keep
app.setApplicationDisplayName("MusicStreamer")       # D-06: NEW (Phase 61)
app.setDesktopFileName(constants.APP_ID)             # D-02: read from constants (no .desktop suffix per Qt convention)
if sys.platform == "win32":
    app.setStyle("Fusion")          # D-14: BEFORE widget construction
    _apply_windows_palette(app)     # D-15: dark-mode palette if applicable
```

**Why it's the right precedent:** Phase 65 D-07 adds a fourth peer setter (`app.setApplicationVersion(...)`) into this exact block. Single-line Qt setter, ordered with siblings, runs after `QApplication(argv)` and before `setStyle("Fusion")`. Mirrors the Phase 61 D-06 line-for-line edit shape.

**Drift:** none. Cited line range 184-187 matches actual source (line 184 = `QApplication(argv)`, 185-187 = the setter trio).

---

### 2. `musicstreamer/ui_qt/main_window.py` (MODIFY) — Qt menu action, event-driven (but disabled)

**Role:** UI widget construction (QMenu/QAction). **Data Flow:** one-shot menu population at MainWindow init.

**Closest analog:** `main_window.py:200-205` (the `self._act_stats` retained-action pattern) and `main_window.py:226-229` (the conditional `self._act_node_missing` — informational menu entry pattern).

**Excerpt — `self._act_stats` retention pattern (lines 199-206):**
```python
# Phase 47.1 D-03: Stats for Nerds toggle -- its own menu group.
self._act_stats = self._menu.addAction("Stats for Nerds")
self._act_stats.setCheckable(True)
self._act_stats.setChecked(
    self._repo.get_setting("show_stats_for_nerds", "0") == "1"
)
self._act_stats.toggled.connect(self._on_stats_toggled)
self._menu.addSeparator()
```

**Excerpt — `self._act_node_missing` informational entry (lines 220-229):**
```python
# Phase 44 D-13 part 3: persistent Node-missing indicator. Added AFTER
# existing Group 3 to keep menu order stable; only surfaces when
# node_runtime was passed AND Node is absent. The "⚠" warning glyph
# matches the existing copywriting convention (e.g., "…" ellipsis).
if self._node_runtime is not None and not self._node_runtime.available:
    self._menu.addSeparator()
    self._act_node_missing = self._menu.addAction(
        "⚠ Node.js: Missing (click to install)"
    )
    self._act_node_missing.triggered.connect(self._on_node_install_clicked)
```

**Why it's the right precedent:** `_act_stats` shows the `self._act_*` retention idiom. `_act_node_missing` shows the "informational menu entry appended at the bottom, with `addSeparator()` immediately preceding" idiom — exactly what Phase 65 D-01 / D-02 / D-03 require, except unconditional and disabled. Phase 65 lands *after* this conditional block so the version footer is the literal last entry whether or not Node is missing.

**Drift:** none.

---

### 3. `musicstreamer/__version__.py` (DELETE) — stale literal mirror

**Role:** legacy version literal mirror (being retired). **Data Flow:** N/A — file deletion.

**Closest analog:** N/A — there is no precedent for deleting a `__version__.py` in this repo. The deletion gate (D-06a) is the controlling precedent.

**Excerpt (full file, 13 lines — confirms stale `2.0.0` literal):**
```python
"""Single source of truth for the application version.
...
"""
__version__ = "2.0.0"
```

**Why it's the right precedent:** CONTEXT D-06 mandates deletion; RESEARCH Q5 verified the D-06a grep gate is clean (zero remaining importers). The file's own docstring at line 6 explicitly forecasts Phase 65 ("Future About dialog / hamburger menu footer (runtime read)"). The literal `"2.0.0"` is stale (pyproject.toml currently has `2.1.63`), confirming the drift this phase closes.

**Drift:** none — file exists exactly as CONTEXT cited.

---

### 4. `packaging/windows/MusicStreamer.spec` (MODIFY) — PyInstaller spec, build-time

**Role:** PyInstaller bundle configuration. **Data Flow:** build-time datas/binaries enumeration.

**Closest analog:** `MusicStreamer.spec:17` (hook import) and `MusicStreamer.spec:25-33, 100-103` (the `_cn_datas + _sl_datas + _yt_datas` concatenation pattern).

**Excerpt — hook import (line 17):**
```python
from PyInstaller.utils.hooks import collect_all
```

**Excerpt — `collect_all` triple pattern (lines 25-33):**
```python
_cn_datas, _cn_binaries, _cn_hiddenimports = collect_all("charset_normalizer")
...
_sl_datas, _sl_binaries, _sl_hiddenimports = collect_all("streamlink")
_yt_datas, _yt_binaries, _yt_hiddenimports = collect_all("yt_dlp")
```

**Excerpt — `datas=` concatenation (lines 100-103):**
```python
datas=[
    ("../../musicstreamer/ui_qt/icons", "musicstreamer/ui_qt/icons"),  # SVG source
    ("icons/MusicStreamer.ico", "icons"),                              # installed icon
] + _cn_datas + _sl_datas + _yt_datas,
```

**Why it's the right precedent:** Phase 65 D-08 adds (a) `copy_metadata` to the existing hook import line, and (b) a `_ms_datas = copy_metadata("musicstreamer")` assignment alongside the three `collect_all` triples, and (c) `+ _ms_datas` to the existing concatenation. Same shape as `_cn_datas` / `_sl_datas` / `_yt_datas` — a single `list[(src, dst)]` tuple-list appended to `datas`. RESEARCH Q1 verified `copy_metadata` returns the same shape.

**Drift:** none.

---

### 5. `tests/test_version.py` (NEW) — unit test, in-process

**Role:** read-mechanism unit test. **Data Flow:** read-only (importlib.metadata + tomllib).

**Closest analog:** `tests/test_media_keys_smtc.py:9, 140-148` (the `tomllib` + pyproject-read pattern).

**Excerpt — `tomllib` import (line 9):**
```python
import tomllib
```

**Excerpt — pyproject read (lines 140-148):**
```python
def test_pyproject_has_windows_optional_deps():
    """D-05: [project.optional-dependencies].windows lists the four pywinrt packages."""
    # Locate pyproject.toml at the repo root — use this file's path as anchor.
    repo_root = Path(__file__).resolve().parent.parent
    pyproject = repo_root / "pyproject.toml"
    assert pyproject.is_file(), f"expected pyproject.toml at {pyproject}"

    with open(pyproject, "rb") as f:
        data = tomllib.load(f)

    optional = data["project"]["optional-dependencies"]
```

**Why it's the right precedent:** Phase 65 VER-02-A asserts `importlib.metadata.version("musicstreamer") == pyproject["project"]["version"]`. The `tomllib.load` + `Path(__file__).resolve().parent.parent / "pyproject.toml"` anchor is exactly the read-only TOML-inspection pattern needed. VER-02-B's regex on the M.m.p triple is a separate one-line `re.match` test.

**Drift:** none. RESEARCH already cites this analog at lines 9 and 148; both are correct.

---

### 6. `tests/test_main_window_integration.py` (MODIFY) — extend menu-construction tests

**Role:** pytest-qt menu introspection. **Data Flow:** read-only widget tree inspection.

**Closest analog:** in-file: lines 404-431 (existing `EXPECTED_ACTION_TEXTS` constant, `test_hamburger_menu_actions`, `test_hamburger_menu_separators`).

**Excerpt — `EXPECTED_ACTION_TEXTS` constant (lines 404-416):**
```python
EXPECTED_ACTION_TEXTS = [
    "New Station",         # Phase 999.1 D-01 (Plan 03)
    "Discover Stations",
    "Import Stations",
    "Add GBS.FM",          # Phase 60 D-02 (Plan 60-03)
    "Search GBS.FM…",  # Phase 60 D-08a (Plan 60-07; U+2026 ellipsis)
    "Accent Color",
    "Accounts",            # Phase 53 D-13: YouTube Cookies entry removed; cookie management consolidated into Accounts dialog
    "Equalizer",           # Phase 47.2 D-07
    "Stats for Nerds",
    "Export Settings",
    "Import Settings",
]
```

**Excerpt — `test_hamburger_menu_actions` + `test_hamburger_menu_separators` (lines 419-431):**
```python
def test_hamburger_menu_actions(window):
    """Hamburger menu contains exactly 11 non-separator actions with correct text."""
    menu = window._menu
    actions = [a for a in menu.actions() if not a.isSeparator()]
    texts = [a.text() for a in actions]
    assert texts == EXPECTED_ACTION_TEXTS


def test_hamburger_menu_separators(window):
    """Hamburger menu has exactly 3 separators (4 groups; Phase 47.1 adds Stats group)."""
    menu = window._menu
    separators = [a for a in menu.actions() if a.isSeparator()]
    assert len(separators) == 3
```

**Why it's the right precedent:** Phase 65 extends EXPECTED_ACTION_TEXTS in-place (or splits it, since the version label is regex-asserted not literal-asserted), updates `test_hamburger_menu_separators`'s count from 3 to 4, and adds a new `test_version_action_is_disabled_and_last`. The `[a for a in menu.actions() if not a.isSeparator()]` filter is the key idiom — RESEARCH Q4 specifically chose `addAction + setEnabled(False)` over `addSection` to preserve compatibility with this filter.

**Drift:** none. The test currently asserts `texts == EXPECTED_ACTION_TEXTS` (full equality, line 424) — Phase 65 must change this to either (a) extend EXPECTED_ACTION_TEXTS with a sentinel and regex-match the last entry separately, OR (b) slice `texts[:11]` for the literal compare and regex-match `texts[11]` separately (RESEARCH §Test Strategy Test 2 chose option b).

---

### 7. `tests/test_main_run_gui_ordering.py` (MODIFY) — add `setApplicationVersion` source-position test

**Role:** source-text ordering assertion. **Data Flow:** read-only file-content inspection.

**Closest analog:** in-file: lines 35-52 (existing `test_ensure_installed_runs_before_qapplication` and `test_ensure_installed_runs_after_gst_init` — same `_index` source-byte ordering pattern).

**Excerpt — full ordering-test pattern (lines 24-52):**
```python
@pytest.fixture(scope="module")
def main_source() -> str:
    return _MAIN.read_text(encoding="utf-8")


def _index(haystack: str, needle: str) -> int:
    idx = haystack.find(needle)
    assert idx != -1, f"expected {needle!r} in musicstreamer/__main__.py"
    return idx


def test_ensure_installed_runs_before_qapplication(main_source: str) -> None:
    ensure = _index(main_source, "desktop_install.ensure_installed(")
    qapp = _index(main_source, "QApplication(")
    assert ensure < qapp, (
        "desktop_install.ensure_installed() must precede QApplication(...) so "
        "the .desktop file is in the XDG path before the first window binds. "
        f"Got ensure_installed @ byte {ensure}, QApplication @ byte {qapp}."
    )
```

**Why it's the right precedent:** Phase 65 D-07 adds `app.setApplicationVersion(...)` AFTER `app = QApplication(argv)`. The new `test_set_application_version_in_run_gui` can reuse the existing `main_source` fixture and `_index` helper verbatim, asserting `_index(...,"setApplicationVersion(") > _index(..., "QApplication(argv)")`. RESEARCH §Test 3 spells out the exact shape.

**Drift:** none.

---

### 8. `tests/test_packaging_spec.py` (NEW, recommended) OR `tests/test_pkg03_compliance.py` (MODIFY) — VER-02-H source-text assertion

**Role:** PyInstaller spec source-text assertion. **Data Flow:** read-only file-content inspection.

**Closest analog:** **`tests/test_main_run_gui_ordering.py`** (source-text inspection pattern with `Path(...).read_text(...)` + substring assertion). The originally-cited `tests/test_pkg03_compliance.py` has a *different* shape — it iterates `musicstreamer/**/*.py` looking for `subprocess.{Popen,run,call}` violations across the whole package tree. It does NOT read a single named file and assert substrings in it.

**Excerpt — `test_pkg03_compliance.py` (lines 1-31, full file):**
```python
"""PKG-03 compliance: no bare subprocess.{Popen,run,call} outside subprocess_utils.py.
...
"""
from __future__ import annotations

import re
from pathlib import Path

_FORBIDDEN = re.compile(r"\bsubprocess\.(Popen|run|call)\b")


def test_no_raw_subprocess_in_musicstreamer():
    """Pure-Python grep: zero bare subprocess.{Popen,run,call} hits outside subprocess_utils.py."""
    root = Path(__file__).resolve().parent.parent / "musicstreamer"
    assert root.is_dir(), f"musicstreamer/ not found at {root}"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "subprocess_utils.py":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _FORBIDDEN.search(line):
                offenders.append(f"{path}:{lineno}: {stripped}")
    assert not offenders, "PKG-03 violation:\n" + "\n".join(offenders)
```

**Excerpt — `test_main_run_gui_ordering.py` single-file source-text shape (lines 21-32, the actual closer analog):**
```python
_MAIN = Path(__file__).resolve().parent.parent / "musicstreamer" / "__main__.py"


@pytest.fixture(scope="module")
def main_source() -> str:
    return _MAIN.read_text(encoding="utf-8")


def _index(haystack: str, needle: str) -> int:
    idx = haystack.find(needle)
    assert idx != -1, f"expected {needle!r} in musicstreamer/__main__.py"
    return idx
```

**Why it's the right precedent:** VER-02-H is a single-file substring assertion (`copy_metadata("musicstreamer")` MUST appear in `MusicStreamer.spec`). That's the `test_main_run_gui_ordering.py` shape (one `Path(...) / "..." / "MusicStreamer.spec"` constant + a substring check), not the `test_pkg03_compliance.py` shape (multi-file glob + regex iteration over a package tree). Recommendation: create a new `tests/test_packaging_spec.py` modelled after `test_main_run_gui_ordering.py`. If the planner prefers in-place extension, `test_pkg03_compliance.py` works structurally but mixes concerns (PKG-03 is a `musicstreamer/*.py` rule; VER-02-H is a `packaging/windows/*.spec` rule — different scopes).

**Drift flag:** **MEDIUM** — RESEARCH §Test Strategy Test 4 says "If the existing `test_pkg03_compliance.py` covers the PyInstaller spec, extend it." Verification: it does NOT cover the spec. The planner should pick the new-file path or expand `test_pkg03_compliance.py`'s scope explicitly.

---

## Shared Patterns

### `_index`-based source-text ordering (applies to test files 7 + 8)
**Source:** `tests/test_main_run_gui_ordering.py:29-32`
**Apply to:** `test_set_application_version_in_run_gui` (VER-02-F) and `test_spec_includes_copy_metadata_for_musicstreamer` (VER-02-H, if added as a new file).
```python
def _index(haystack: str, needle: str) -> int:
    idx = haystack.find(needle)
    assert idx != -1, f"expected {needle!r} in musicstreamer/__main__.py"
    return idx
```

### `self._act_*` retention idiom (applies to source file 2)
**Source:** `musicstreamer/ui_qt/main_window.py:200, 211, 213, 226`
**Apply to:** `self._act_version` (Phase 65).
```python
self._act_stats = self._menu.addAction("Stats for Nerds")
...
self._act_export = self._menu.addAction("Export Settings")
self._act_import_settings = self._menu.addAction("Import Settings")
...
self._act_node_missing = self._menu.addAction(...)
```

### `addSeparator()` between menu groups (applies to source file 2)
**Source:** `musicstreamer/ui_qt/main_window.py:184, 197, 206, 225` (existing 3 unconditional + 1 conditional Phase 44 separator).
**Apply to:** new separator before `self._act_version` (D-02).
```python
self._menu.addSeparator()
```

### `[a for a in menu.actions() if not a.isSeparator()]` filter (applies to test file 6)
**Source:** `tests/test_main_window_integration.py:422` (and four other call sites at 458, 470, 508, 524, 612 — same idiom across the integration suite).
**Apply to:** `test_version_action_is_disabled_and_last` and the updated `test_hamburger_menu_actions`.
```python
actions = [a for a in menu.actions() if not a.isSeparator()]
```

### `tomllib.load(f)` + `data["project"]["version"]` (applies to test file 5)
**Source:** `tests/test_media_keys_smtc.py:9, 144-148`
**Apply to:** `test_metadata_version_matches_pyproject` (VER-02-A).
```python
import tomllib
...
repo_root = Path(__file__).resolve().parent.parent
pyproject = repo_root / "pyproject.toml"
with open(pyproject, "rb") as f:
    data = tomllib.load(f)
expected = data["project"]["version"]
```

### `collect_all` / `copy_metadata` datas concatenation (applies to source file 4)
**Source:** `packaging/windows/MusicStreamer.spec:17, 25-33, 100-103`
**Apply to:** `_ms_datas = copy_metadata("musicstreamer")` + `+ _ms_datas` in datas list.
```python
from PyInstaller.utils.hooks import collect_all   # extend with `, copy_metadata`
...
_yt_datas, _yt_binaries, _yt_hiddenimports = collect_all("yt_dlp")
# NEW (Phase 65 D-08):
_ms_datas = copy_metadata("musicstreamer")
...
] + _cn_datas + _sl_datas + _yt_datas + _ms_datas,
```

---

## No Analog Found

None. Every Phase 65 edit has a direct in-repo precedent.

---

## Metadata

**Analog search scope:**
- `musicstreamer/__main__.py` (Qt setup block)
- `musicstreamer/ui_qt/main_window.py` (hamburger menu construction)
- `musicstreamer/__version__.py` (file slated for deletion)
- `packaging/windows/MusicStreamer.spec` (PyInstaller spec)
- `tests/test_main_window_integration.py` (existing menu tests)
- `tests/test_main_run_gui_ordering.py` (source-text ordering tests)
- `tests/test_pkg03_compliance.py` (originally cited as VER-02-H analog — drift documented)
- `tests/test_media_keys_smtc.py` (tomllib precedent)

**Files scanned:** 8 (all line-citations confirmed against current source).

**Pattern extraction date:** 2026-05-08

## PATTERN MAPPING COMPLETE
