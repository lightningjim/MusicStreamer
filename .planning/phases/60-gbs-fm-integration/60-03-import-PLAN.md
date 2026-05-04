---
phase: 60
plan: 03
type: execute
wave: 2
depends_on: ["60-02"]
files_modified:
  - musicstreamer/ui_qt/main_window.py
  - tests/test_main_window_gbs.py
autonomous: true
requirements: [GBS-01a]
tags: [phase60, import, hamburger-menu, gbs-fm]

must_haves:
  truths:
    - "Hamburger menu has 'Add GBS.FM' entry in Group 1 (between Import Stations and the first addSeparator at main_window.py line 141)"
    - "Clicking 'Add GBS.FM' on a fresh library inserts a Station + 6 streams + logo and toasts 'GBS.FM added'"
    - "Clicking 'Add GBS.FM' when a GBS.FM row exists refreshes streams in place (preserves station.id) and toasts 'GBS.FM streams updated' (D-02a)"
    - "The import call runs on a worker thread (_GbsImportWorker) — UI never freezes during the logo download"
    - "Auth-expired during import → typed exception → toast 'GBS.FM session expired — reconnect via Accounts'"
    - "Station list refreshes after a successful import (existing _refresh_station_list flow)"
    - "All connections are bound methods (QA-05) — no self-capturing lambdas"
  artifacts:
    - path: "musicstreamer/ui_qt/main_window.py"
      provides: "act_gbs_add menu entry + _on_gbs_add_clicked handler + _GbsImportWorker QThread + completion + error slots"
      contains: "_on_gbs_add_clicked"
    - path: "tests/test_main_window_gbs.py"
      provides: "Pytest-qt tests for menu wiring, idempotent toast, auth-expired path, worker retention"
      min_lines: 100
  key_links:
    - from: "MainWindow.act_gbs_add.triggered"
      to: "MainWindow._on_gbs_add_clicked"
      via: "QA-05 bound method connection (NOT lambda)"
      pattern: "act_gbs_add\\.triggered\\.connect\\(self\\._on_gbs_add_clicked\\)"
    - from: "MainWindow._on_gbs_add_clicked"
      to: "musicstreamer.gbs_api.import_station"
      via: "_GbsImportWorker.run on a QThread (mirrors _ExportWorker pattern at main_window.py:64-79)"
      pattern: "import_station|_GbsImportWorker"
    - from: "MainWindow._on_gbs_import_finished"
      to: "MainWindow.show_toast + MainWindow._refresh_station_list"
      via: "Signal-driven completion across thread boundary"
      pattern: "show_toast.*GBS\\.FM|_refresh_station_list"
---

<objective>
Wire the "Add GBS.FM" hamburger menu entry to `gbs_api.import_station` via a worker thread, with toast feedback for inserted/updated/auth-expired/error paths. Implements D-02 (menu placement), D-02a (idempotent UPDATE-vs-INSERT toast distinction), D-02b (always present, never disabled), D-02d (provider="GBS.FM"), and the worker-thread pattern from `_ExportWorker` (main_window.py:64-79).

Purpose: This is the user-visible entry point for GBS.FM import. SC #1 in ROADMAP.md §Phase 60 maps directly here.

Output: ~80 LOC added to main_window.py (1 menu action + 1 worker class + 3 handler methods) + 1 new test file (~120 LOC).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/60-gbs-fm-integration/60-CONTEXT.md
@.planning/phases/60-gbs-fm-integration/60-RESEARCH.md
@.planning/phases/60-gbs-fm-integration/60-PATTERNS.md
@.planning/phases/60-gbs-fm-integration/60-VALIDATION.md
@.planning/phases/60-gbs-fm-integration/60-02-SUMMARY.md
@musicstreamer/ui_qt/main_window.py
@musicstreamer/gbs_api.py

<interfaces>
From main_window.py:64-79 (_ExportWorker analog):
```python
class _ExportWorker(QThread):
    finished = Signal(str)
    error = Signal(str)
    def __init__(self, dest_path: str, parent=None):
        super().__init__(parent)
        self._dest_path = dest_path
    def run(self):
        try:
            from musicstreamer.repo import Repo
            repo = Repo(db_connect())
            settings_export.build_zip(repo, self._dest_path)
            self.finished.emit(self._dest_path)
        except Exception as exc:
            self.error.emit(str(exc))
```

From main_window.py:131-141 (Group 1 menu — INSERT new entries before the addSeparator at line 141):
```python
act_new = self._menu.addAction("New Station")
act_new.triggered.connect(self._on_new_station_clicked)
act_discover = self._menu.addAction("Discover Stations")
act_discover.triggered.connect(self._open_discovery_dialog)
act_import = self._menu.addAction("Import Stations")
act_import.triggered.connect(self._open_import_dialog)
self._menu.addSeparator()    # line 141
```

From main_window.py:302-304 (toast):
```python
def show_toast(self, text: str, duration_ms: int = 3000) -> None:
    self._toast.show_toast(text, duration_ms)
```

From musicstreamer/gbs_api.py (Plan 60-02):
```python
def import_station(repo: Repo, on_progress=None) -> tuple[int, int]:
    """Returns (inserted, updated). 1+0 first call, 0+1 idempotent re-import."""

class GbsAuthExpiredError(GbsApiError):
    """302 → /accounts/login/."""
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add act_gbs_add menu entry + _GbsImportWorker + handler methods to main_window.py</name>
  <read_first>
    - musicstreamer/ui_qt/main_window.py (lines 1-100 for imports + worker class shape; lines 125-200 for menu construction; lines 580-700 for refresh + dialog launchers; line 302 for show_toast)
    - musicstreamer/gbs_api.py (verify Plan 60-02 exports import_station + GbsAuthExpiredError)
    - .planning/phases/60-gbs-fm-integration/60-PATTERNS.md (§"musicstreamer/ui_qt/main_window.py modifications" — line-by-line)
    - .planning/phases/60-gbs-fm-integration/60-RESEARCH.md (§Pitfall 3 auth-expired; §Pitfall 5 worker-thread DoS UX)
  </read_first>
  <behavior>
    - act_gbs_add menu entry rendered between "Import Stations" and the first addSeparator (line 141)
    - Bound-method connection (QA-05): act_gbs_add.triggered.connect(self._on_gbs_add_clicked)
    - _on_gbs_add_clicked instantiates _GbsImportWorker, connects finished/error to bound slots, retains the worker on self for GC (SYNC-05), shows "Importing GBS.FM…" toast immediately
    - Worker.run calls gbs_api.import_station(repo) on a fresh DB connection (mirrors _ExportWorker), emits finished(int, int) for (inserted, updated) or error(str)
    - Worker emits sentinel string "auth_expired" via error when GbsAuthExpiredError raised
    - _on_gbs_import_finished: routes by counts → toast "GBS.FM added" if inserted=1, "GBS.FM streams updated" if updated=1, then _refresh_station_list
    - _on_gbs_import_error: special-cases "auth_expired" → "GBS.FM session expired — reconnect via Accounts"; other errors → "GBS.FM import failed: {msg}" (truncated to 80 chars)
    - Worker stored as self._gbs_import_worker for retention; cleared to None after both success and error paths
  </behavior>
  <action>
**Step A — add `_GbsImportWorker` class at top of file** after the existing `_ImportPreviewWorker` class (around line 100):

```python
class _GbsImportWorker(QThread):
    """Phase 60 D-02 / GBS-01a: kick gbs_api.import_station() off the UI thread.

    Mirrors _ExportWorker shape (main_window.py:64-79). Pitfall 3 — emits the
    sentinel string ``"auth_expired"`` via the error signal when the gbs_api
    raises GbsAuthExpiredError so the UI surfaces a re-auth prompt instead
    of the raw exception text.
    """
    finished = Signal(int, int)   # (inserted, updated) per import_station signature
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            from musicstreamer.repo import Repo
            from musicstreamer import gbs_api
            repo = Repo(db_connect())
            inserted, updated = gbs_api.import_station(repo)
            self.finished.emit(int(inserted), int(updated))
        except Exception as exc:
            from musicstreamer import gbs_api
            if isinstance(exc, gbs_api.GbsAuthExpiredError):
                self.error.emit("auth_expired")
            else:
                self.error.emit(str(exc))
```

**Step B — extend the menu construction block** (lines 138-141 area). Insert two lines BEFORE `self._menu.addSeparator()` (line 141):

```python
        act_import = self._menu.addAction("Import Stations")
        act_import.triggered.connect(self._open_import_dialog)

        # Phase 60 D-02 / GBS-01a: idempotent multi-quality GBS.FM import
        act_gbs_add = self._menu.addAction("Add GBS.FM")
        act_gbs_add.triggered.connect(self._on_gbs_add_clicked)  # QA-05 bound method

        self._menu.addSeparator()
```

(Plan 60-07 will add a sibling `act_gbs_search` entry at this location.)

**Step C — initialize worker slot in __init__** (after `self._toast = ToastOverlay(self)` at line 218):

```python
        # Phase 60 D-02: GBS.FM import worker retention
        self._gbs_import_worker = None
```

**Step D — handler methods** (add at the bottom of MainWindow class, near `_open_accounts_dialog`):

```python
    def _on_gbs_add_clicked(self) -> None:
        """Phase 60 D-02 / D-02a: kick the GBS.FM import on a worker thread.

        Idempotent: re-clicking refreshes streams in place. UI never blocks —
        worker runs the urllib calls + logo download off-thread. Pitfall 3:
        auth-expired surfaces as a re-auth toast.
        """
        self.show_toast("Importing GBS.FM…")
        self._gbs_import_worker = _GbsImportWorker(parent=self)  # SYNC-05 retain
        self._gbs_import_worker.finished.connect(self._on_gbs_import_finished)  # QA-05
        self._gbs_import_worker.error.connect(self._on_gbs_import_error)        # QA-05
        self._gbs_import_worker.start()

    def _on_gbs_import_finished(self, inserted: int, updated: int) -> None:
        """D-02a: distinct toast for fresh insert vs in-place refresh."""
        if inserted:
            self.show_toast("GBS.FM added")
        elif updated:
            self.show_toast("GBS.FM streams updated")
        else:
            self.show_toast("GBS.FM import: no changes")
        self._refresh_station_list()
        self._gbs_import_worker = None

    def _on_gbs_import_error(self, msg: str) -> None:
        """Pitfall 3: auth_expired sentinel → reconnect prompt; else generic."""
        if msg == "auth_expired":
            self.show_toast("GBS.FM session expired — reconnect via Accounts")
        else:
            truncated = (msg[:80] + "…") if len(msg) > 80 else msg
            self.show_toast(f"GBS.FM import failed: {truncated}")
        self._gbs_import_worker = None
```

**Step E — `EXPECTED_ACTION_TEXTS` housekeeping**: Run

```bash
grep -rn "EXPECTED_ACTION_TEXTS" tests/
```

If a list of expected hamburger menu labels exists (Phase 53 added one for the Accounts-menu refactor), append `"Add GBS.FM"` in the correct position — after `"Import Stations"`. If grep returns nothing, skip this step (Plan 60-07 will reconcile if needed).

Decisions implemented: D-02 (menu placement), D-02a (idempotent toast distinction), D-02b (always-present), D-02d (provider via gbs_api), D-03c (typed exception sentinel), QA-05 (bound methods), Pitfalls 3 + 5.
  </action>
  <verify>
    <automated>grep -q "addAction(\"Add GBS\\.FM\")" musicstreamer/ui_qt/main_window.py &amp;&amp; grep -q '_on_gbs_add_clicked' musicstreamer/ui_qt/main_window.py &amp;&amp; grep -q '_GbsImportWorker' musicstreamer/ui_qt/main_window.py &amp;&amp; grep -q 'GBS.FM streams updated' musicstreamer/ui_qt/main_window.py &amp;&amp; grep -q 'auth_expired' musicstreamer/ui_qt/main_window.py &amp;&amp; python -c "import ast; ast.parse(open('musicstreamer/ui_qt/main_window.py').read())"</automated>
  </verify>
  <done>
- Menu action "Add GBS.FM" exists at main_window.py
- _GbsImportWorker class defined with finished(int, int) and error(str) signals
- _on_gbs_add_clicked, _on_gbs_import_finished, _on_gbs_import_error methods exist
- Bound-method connections (no `lambda` near act_gbs_add)
- Module parses cleanly (no syntax errors)
- self._gbs_import_worker initialized to None in __init__
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create tests/test_main_window_gbs.py with 5 pytest-qt tests</name>
  <read_first>
    - tests/test_main_window_node_indicator.py (read in full for ui_qt MainWindow construction shape — qtbot fixture + repo + Player double)
    - tests/test_now_playing_panel.py (read top 50 lines for FakePlayer pattern + Repo mock idiom)
    - .planning/phases/60-gbs-fm-integration/60-PATTERNS.md (§"musicstreamer/ui_qt/main_window.py modifications" — pattern application)
    - musicstreamer/ui_qt/main_window.py (re-read after Task 1 — to confirm signal names + slot signatures)
    - .planning/phases/60-gbs-fm-integration/60-VALIDATION.md (§"Per-Task Verification Map" — relevant rows for GBS-01a UI)
  </read_first>
  <behavior>
    - test_add_gbs_menu_entry_exists — MainWindow has an action with text "Add GBS.FM" in the hamburger menu
    - test_add_gbs_triggers_import_worker — clicking the action constructs _GbsImportWorker and starts it (patch import_station to short-circuit)
    - test_import_finished_toasts_added_on_first_call — emit finished(1, 0) → show_toast called with "GBS.FM added"
    - test_import_finished_toasts_updated_on_refresh — emit finished(0, 1) → show_toast called with "GBS.FM streams updated"
    - test_import_error_auth_expired_toasts_reconnect_prompt — emit error("auth_expired") → toast with "session expired" string
    - test_import_error_generic_toasts_truncated — emit error("very long error " * 20) → toast text contains truncated marker (length-cap)
    - test_no_self_capturing_lambda_in_gbs_action — grep guard inside the test (read main_window.py source, regex check)
  </behavior>
  <action>
Create `tests/test_main_window_gbs.py` (~150 LOC):

```python
"""Phase 60 / GBS-01a UI: hamburger menu wiring + worker flow + idempotent toasts.

Mirrors tests/test_main_window_node_indicator.py shape — qtbot fixture +
in-memory MainWindow construction with Repo + Player doubles.
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt

from musicstreamer.ui_qt.main_window import MainWindow, _GbsImportWorker


@pytest.fixture
def main_window(qtbot, fake_repo, monkeypatch, tmp_path):
    """Construct a MainWindow with a stubbed Player + fake_repo.

    Patches db_connect so the worker can spin up its own Repo without
    touching the real database file.
    """
    # MainWindow constructor talks to the DB and the player; substitute
    # both with mocks. The construction details vary by codebase; mirror
    # whatever tests/test_main_window_node_indicator.py does.
    from musicstreamer.player import Player
    monkeypatch.setattr("musicstreamer.ui_qt.main_window.db_connect",
                        lambda: MagicMock())
    monkeypatch.setattr("musicstreamer.ui_qt.main_window.Repo",
                        lambda con: fake_repo)
    fake_player = MagicMock(spec=Player)
    fake_player.cookies_cleared = MagicMock()
    fake_player.cookies_cleared.connect = MagicMock()
    fake_player.title_changed = MagicMock()
    fake_player.title_changed.connect = MagicMock()
    fake_player.elapsed_updated = MagicMock()
    fake_player.elapsed_updated.connect = MagicMock()
    fake_player.playing_state_changed = MagicMock()
    fake_player.playing_state_changed.connect = MagicMock()
    fake_player.buffer_progress = MagicMock()
    fake_player.buffer_progress.connect = MagicMock()
    fake_player.playback_error = MagicMock()
    fake_player.playback_error.connect = MagicMock()
    try:
        win = MainWindow(player=fake_player, repo=fake_repo)
    except TypeError:
        # Some MainWindow constructors only take repo
        win = MainWindow(fake_repo)
    qtbot.addWidget(win)
    return win


def _find_action(window, text: str):
    for action in window._menu.actions():
        if action.text() == text:
            return action
    return None


def test_add_gbs_menu_entry_exists(main_window):
    """D-02: 'Add GBS.FM' menu entry is rendered in the hamburger menu."""
    action = _find_action(main_window, "Add GBS.FM")
    assert action is not None, "Expected 'Add GBS.FM' menu entry"
    assert action.isEnabled(), "D-02b: menu entry must always be enabled"


def test_add_gbs_triggers_worker_start(main_window, monkeypatch):
    """D-02: click should start a _GbsImportWorker."""
    started = {"flag": False}
    real_init = _GbsImportWorker.__init__
    real_start = _GbsImportWorker.start
    def fake_init(self, parent=None):
        real_init(self, parent=parent)
    def fake_start(self):
        started["flag"] = True
    monkeypatch.setattr(_GbsImportWorker, "__init__", fake_init)
    monkeypatch.setattr(_GbsImportWorker, "start", fake_start)
    main_window._on_gbs_add_clicked()
    assert started["flag"] is True
    assert main_window._gbs_import_worker is not None


def test_import_finished_toasts_added_on_first_call(main_window, monkeypatch):
    """D-02a: finished(1, 0) → 'GBS.FM added' toast."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    monkeypatch.setattr(main_window, "_refresh_station_list", lambda: None)
    main_window._gbs_import_worker = MagicMock()
    main_window._on_gbs_import_finished(1, 0)
    assert captured["text"] == "GBS.FM added"
    assert main_window._gbs_import_worker is None


def test_import_finished_toasts_updated_on_refresh(main_window, monkeypatch):
    """D-02a: finished(0, 1) → 'GBS.FM streams updated' toast."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    monkeypatch.setattr(main_window, "_refresh_station_list", lambda: None)
    main_window._gbs_import_worker = MagicMock()
    main_window._on_gbs_import_finished(0, 1)
    assert captured["text"] == "GBS.FM streams updated"


def test_import_error_auth_expired_toasts_reconnect_prompt(main_window, monkeypatch):
    """Pitfall 3: error('auth_expired') → reconnect-via-Accounts toast."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    main_window._gbs_import_worker = MagicMock()
    main_window._on_gbs_import_error("auth_expired")
    assert "session expired" in captured["text"].lower()
    assert "Accounts" in captured["text"]
    assert main_window._gbs_import_worker is None


def test_import_error_generic_toasts_failure(main_window, monkeypatch):
    """Generic error → 'GBS.FM import failed: {msg}' toast."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    main_window._gbs_import_worker = MagicMock()
    main_window._on_gbs_import_error("Connection refused")
    assert "GBS.FM import failed" in captured["text"]
    assert "Connection refused" in captured["text"]


def test_no_self_capturing_lambda_in_gbs_action():
    """QA-05 / Pitfall 10: act_gbs_add must use a bound method, not a lambda."""
    src = open("musicstreamer/ui_qt/main_window.py").read()
    # The connection line must look like:
    #   act_gbs_add.triggered.connect(self._on_gbs_add_clicked)
    matches = re.findall(r"act_gbs_add\.triggered\.connect\(([^)]+)\)", src)
    assert matches, "Expected act_gbs_add.triggered.connect(...) line"
    for m in matches:
        assert "lambda" not in m, f"QA-05 violation: {m!r}"
        assert m.strip().startswith("self.") or m.strip().startswith("self,"), \
            f"QA-05 expects bound method, got: {m!r}"
```

If the MainWindow constructor signature is different from `MainWindow(player=..., repo=...)`, copy the construction idiom from `tests/test_main_window_node_indicator.py`. The fixture is the only place that needs adjustment; tests use the fixture.

Decisions implemented: VALIDATION.md GBS-01a UI rows; QA-05; D-02a (toast distinction).
  </action>
  <verify>
    <automated>pytest tests/test_main_window_gbs.py -x -q 2>&amp;1 | tail -15</automated>
  </verify>
  <done>
- tests/test_main_window_gbs.py exists with 7 tests (all pass)
- test_add_gbs_menu_entry_exists confirms D-02 menu placement
- test_add_gbs_triggers_worker_start confirms worker is started on click
- test_import_finished_* covers D-02a inserted vs updated toast distinction
- test_import_error_auth_expired_* covers Pitfall 3 reconnect prompt
- test_no_self_capturing_lambda_* enforces QA-05 grep guard
- pytest -x runs green (no regressions in other test files)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| UI thread ↔ Worker thread | `_GbsImportWorker` runs urllib calls + logo download off-main-thread; results cross via Signal/Slot Qt.QueuedConnection |
| MainWindow ↔ gbs_api | Imports the API client and Repo; passes Repo+player into worker via fresh `db_connect()` |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-60-12 | Denial of Service (UX) | UI thread blocked during logo download | mitigate | _GbsImportWorker QThread off-loads import_station; UI shows toast "Importing GBS.FM…" pre-emptively. Pitfall 5. |
| T-60-13 | Spoofing / Repudiation | Auth-expired during import | mitigate | Worker special-cases GbsAuthExpiredError, emits sentinel "auth_expired" string; UI translates into actionable reconnect toast. Pitfall 3. |
| T-60-14 | Tampering | Self-capturing lambda leaks self into closure | mitigate | QA-05 bound-method connections enforced by grep guard test (test_no_self_capturing_lambda_in_gbs_action). Pitfall 10. |
| T-60-15 | Information Disclosure | Long error messages leak stack-trace text into toast | mitigate | Error msg truncated to 80 chars + ellipsis before display. |
| T-60-16 | Tampering | Worker GC race with main window destroy | mitigate | self._gbs_import_worker retention slot (SYNC-05 pattern) + None-out on completion. Mirrors existing _export_worker idiom. |

Citations: Pitfalls 3, 5, 10 from RESEARCH.md.
</threat_model>

<verification>
```bash
# Targeted subset (per VALIDATION.md sampling)
pytest tests/test_main_window_gbs.py tests/test_gbs_api.py -x -q

# Module imports
python -c "from musicstreamer.ui_qt.main_window import MainWindow, _GbsImportWorker; print('OK')"

# QA-05 grep guard
grep -E "act_gbs_add\.triggered\.connect\(self\._on_gbs_add_clicked\)" musicstreamer/ui_qt/main_window.py

# Full suite regression
pytest -x
```
</verification>

<success_criteria>
- "Add GBS.FM" menu entry visible in MainWindow's hamburger menu
- Click flow: shows "Importing…" toast → worker runs gbs_api.import_station → finished signal triggers correct insert/update toast → station list refreshes
- Auth-expired during import → "GBS.FM session expired — reconnect via Accounts" toast
- Generic errors → "GBS.FM import failed: {truncated}" toast
- All 7 tests in tests/test_main_window_gbs.py pass
- No QA-05 violations (no `lambda` in act_gbs_add connection)
- pytest -x runs green
</success_criteria>

<output>
After completion, create `.planning/phases/60-gbs-fm-integration/60-03-SUMMARY.md`
</output>
