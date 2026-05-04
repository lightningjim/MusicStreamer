---
phase: 60
plan: 07
type: execute
wave: 4
depends_on: ["60-02", "60-04"]
files_modified:
  - musicstreamer/ui_qt/gbs_search_dialog.py
  - musicstreamer/ui_qt/main_window.py
  - tests/test_gbs_search_dialog.py
autonomous: true
requirements: [GBS-01e]
tags: [phase60, search-submit, dialog, gbs-fm]

must_haves:
  truths:
    - "New module musicstreamer/ui_qt/gbs_search_dialog.py defines GBSSearchDialog(QDialog)"
    - "Hamburger menu has 'Search GBS.FM…' entry in Group 1 next to 'Add GBS.FM' (D-08a recommended placement)"
    - "Dialog opens via _open_gbs_search_dialog handler in MainWindow"
    - "Dialog shows query QLineEdit + Search QPushButton + results table + Submit button + Close — explicit-button search (NOT debounced; RESEARCH §Claude's Discretion)"
    - "Search runs on a worker thread; results render in QStandardItemModel + QTableView (mirrors discovery_dialog.py pattern); each row has a per-row Submit button OR a single Submit button enabled when a row is selected"
    - "Submit calls gbs_api.submit(songid, cookies) on a worker; success → toast 'Track added to GBS.FM playlist'; duplicate / token-quota → INLINE error label below the table (D-08d)"
    - "Auth-expired (302→/accounts/login/) on search OR submit → toast 'GBS.FM session expired — reconnect via Accounts' + dialog stays open"
    - "Pagination via 'Next' / 'Prev' buttons reading total_pages from search() response (D-08e default — first 30 results per page; 'Show more' implemented as Next button)"
    - "All connections bound methods (QA-05); QStandardItem cells are PlainText (T-39-04 / T-40-04 — no Qt.RichText)"
    - "If user not logged in when dialog opens, search and submit are disabled with a 'Log in to search and submit' inline message (D-08c — entire dialog requires login)"
  artifacts:
    - path: "musicstreamer/ui_qt/gbs_search_dialog.py"
      provides: "GBSSearchDialog QDialog + _GbsSearchWorker + _GbsSubmitWorker classes"
      min_lines: 250
      exports: ["GBSSearchDialog"]
    - path: "musicstreamer/ui_qt/main_window.py"
      provides: "act_gbs_search menu entry + _open_gbs_search_dialog handler"
      contains: "_open_gbs_search_dialog"
    - path: "tests/test_gbs_search_dialog.py"
      provides: "Pytest-qt tests for search flow, submit flow, inline error, auth-expired, login gate, pagination"
      min_lines: 200
  key_links:
    - from: "MainWindow.act_gbs_search.triggered"
      to: "MainWindow._open_gbs_search_dialog"
      via: "QA-05 bound-method connection"
      pattern: "act_gbs_search\\.triggered\\.connect\\(self\\._open_gbs_search_dialog\\)"
    - from: "MainWindow._open_gbs_search_dialog"
      to: "GBSSearchDialog(self._repo, self.show_toast, parent=self)"
      via: "Mirrors _open_discovery_dialog at main_window.py:668-672 (drop player arg per CONTEXT.md 'no preview play')"
      pattern: "GBSSearchDialog\\(.*show_toast"
    - from: "GBSSearchDialog._search_btn.clicked"
      to: "gbs_api.search via _GbsSearchWorker"
      via: "QA-05 bound; Pitfall 6 anchor on data-songid"
      pattern: "_GbsSearchWorker|gbs_api\\.search"
    - from: "GBSSearchDialog Submit button"
      to: "gbs_api.submit via _GbsSubmitWorker"
      via: "Pitfall 7 (no retry); Pitfall 8 (decoded messages cookie surfaces in inline error)"
      pattern: "_GbsSubmitWorker|gbs_api\\.submit"
---

<objective>
Ship `GBSSearchDialog` (D-08): search the GBS.FM catalog by query, submit a selected song to the playlist queue. Worker-thread API calls, inline error for duplicates/quota, toasts for hard failures, full auth-gating per D-08c.

Purpose: Closes SC #5 of ROADMAP §Phase 60 ("user can search the GBS.FM catalog and submit a song to the station's playlist; submission round-trips to the API and confirms success/failure").

Output: New file `musicstreamer/ui_qt/gbs_search_dialog.py` (~280 LOC) + ~10 LOC added to `main_window.py` (1 menu action + 1 handler) + new test file ~250 LOC.
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
@.planning/phases/60-gbs-fm-integration/60-04-SUMMARY.md
@musicstreamer/ui_qt/discovery_dialog.py
@musicstreamer/ui_qt/main_window.py
@musicstreamer/gbs_api.py

<interfaces>
From musicstreamer/ui_qt/discovery_dialog.py (CLOSEST analog — 505 LOC):
```python
class DiscoveryDialog(QDialog):
    station_saved = Signal()
    def __init__(self, player, repo, toast_callback, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Discover Stations")
        self.setMinimumSize(720, 520)
        self.setModal(False)
        self._build_ui()

class _SearchWorker(QThread):
    finished = Signal(list)
    error = Signal(str)
    def __init__(self, name, tag, countrycode, parent=None): ...
    def run(self): ...
```

From musicstreamer/ui_qt/main_window.py:131-141 (Group 1 menu — INSERT 'Search GBS.FM…' next to 'Add GBS.FM' from Plan 60-03):
```python
# After Plan 60-03 ships:
act_gbs_add = self._menu.addAction("Add GBS.FM")
act_gbs_add.triggered.connect(self._on_gbs_add_clicked)
# Plan 60-07 inserts here:
act_gbs_search = self._menu.addAction("Search GBS.FM…")
act_gbs_search.triggered.connect(self._open_gbs_search_dialog)
self._menu.addSeparator()
```

From musicstreamer/ui_qt/main_window.py:668-672 (open-dialog handler precedent):
```python
def _open_discovery_dialog(self) -> None:
    dlg = DiscoveryDialog(self._player, self._repo, self.show_toast, parent=self)
    dlg.exec()
    self._refresh_station_list()
```

From musicstreamer/gbs_api.py (Plan 60-02):
```python
def search(query: str, page: int, cookies) -> dict:
    """Returns {'results': [{songid, artist, title, duration, add_url}], 'page': int, 'total_pages': int}.
    Raises GbsAuthExpiredError on 302→/accounts/login/."""

def submit(songid: int, cookies) -> str:
    """Returns the decoded messages cookie text (success/error string)
    or '' if no messages cookie was set.
    Raises GbsAuthExpiredError on 302→/accounts/login/."""

def load_auth_context() -> Optional[MozillaCookieJar]: ...
class GbsAuthExpiredError(GbsApiError): ...
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create musicstreamer/ui_qt/gbs_search_dialog.py with GBSSearchDialog + workers</name>
  <read_first>
    - musicstreamer/ui_qt/discovery_dialog.py (read in full — 505 LOC; primary analog: __init__ + _build_ui + _SearchWorker + _start_search + _on_search_finished + _make_save_slot row factory)
    - musicstreamer/gbs_api.py (verify search/submit signatures + GbsAuthExpiredError + load_auth_context)
    - musicstreamer/paths.py (gbs_cookies_path)
    - .planning/phases/60-gbs-fm-integration/60-PATTERNS.md (§"musicstreamer/ui_qt/gbs_search_dialog.py" — pattern application)
    - .planning/phases/60-gbs-fm-integration/60-RESEARCH.md (§Capability 5 + 6 endpoints; §Pitfalls 6, 7, 8)
  </read_first>
  <behavior>
    - Class GBSSearchDialog(QDialog) with constructor `(repo, toast_callback, parent=None)` — drops the `player` arg (no preview play)
    - Window title "Search GBS.FM"; non-modal; minimum size 640×480
    - UI: top row = QLineEdit (query) + QPushButton "Search" + QLabel page indicator (e.g. "Page 1 of N"); middle = QTableView with model of 4 columns: Artist | Title | Duration | (per-row Add button); bottom row = inline error QLabel + Prev/Next pagination + Close
    - Login gate: in showEvent OR __init__, check load_auth_context(); if None → disable query field + search button, set inline label "Log in via Accounts to search GBS.FM"
    - Search flow: click "Search" → _GbsSearchWorker(query, page=1, cookies).start() → finished(list, int total_pages) → render rows
    - Per-row Submit (factory pattern from discovery_dialog.py:388-396 — _make_submit_slot(row_idx)) — closure-form bound to a method, NOT a self-capturing lambda (QA-05)
    - Submit flow: click row's "Add" → _GbsSubmitWorker(songid, cookies).start() → finished(str message, int row_idx) → toast on success / inline error on duplicate/quota
    - Pagination: Next/Prev buttons trigger search at page+1 / page-1
    - Auth-expired during search OR submit: toast "GBS.FM session expired — reconnect via Accounts"; dialog stays open
    - QStandardItem cells are PlainText (T-39-04 inherited from DiscoveryDialog)
    - All connections bound methods (QA-05)
  </behavior>
  <action>
Create `musicstreamer/ui_qt/gbs_search_dialog.py`:

```python
"""Phase 60 D-08 / GBS-01e: GBSSearchDialog — search gbs.fm + submit a song.

Mirrors DiscoveryDialog (musicstreamer/ui_qt/discovery_dialog.py) shape:
search-box + results-table + per-row action button + worker QThread +
QA-05 bound-method connections + T-40-04 PlainText labels.

Differences from DiscoveryDialog:
  - No preview-play (CONTEXT.md "Phase 60's search dialog does NOT need
    preview play"); constructor drops the `player` arg.
  - Action is "Submit" (D-08), not "Save to library."
  - Login-gated entire dialog (D-08c — RESOLVED): disabled UI until cookies
    file present.
  - Inline error label (D-08d) for duplicate/token-quota; toasts only for
    hard errors (auth, network, server 5xx).

Pitfalls covered:
  6 — HTML scraping fragility: parser anchors handled in gbs_api.search.
  7 — GET-with-side-effects: NO retries on submit failure.
  8 — Token-quota: messages cookie text surfaces verbatim via
       gbs_api.submit return value.
  10 — QA-05 bound-method connections.
  11 — PlainText only (QStandardItem default).
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from musicstreamer import gbs_api
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX

_COL_ARTIST = 0
_COL_TITLE = 1
_COL_DURATION = 2
_COL_ADD = 3


class _GbsSearchWorker(QThread):
    """Phase 60 D-08 / GBS-01e: gbs_api.search on a worker thread."""
    # finished payload: (results_list, page, total_pages)
    finished = Signal(list, int, int)
    # error: ('auth_expired' sentinel OR raw message)
    error = Signal(str)

    def __init__(self, query: str, page: int, cookies, parent=None):
        super().__init__(parent)
        self._query = query
        self._page = page
        self._cookies = cookies

    def run(self):
        try:
            out = gbs_api.search(self._query, self._page, self._cookies)
            self.finished.emit(
                list(out.get("results", [])),
                int(out.get("page", self._page)),
                int(out.get("total_pages", self._page)),
            )
        except Exception as exc:
            if isinstance(exc, gbs_api.GbsAuthExpiredError):
                self.error.emit("auth_expired")
            else:
                self.error.emit(str(exc))


class _GbsSubmitWorker(QThread):
    """Phase 60 D-08 / GBS-01e: gbs_api.submit on a worker thread.

    Pitfall 7 — NO retries on transient failure.
    Pitfall 8 — message text decoded from Django messages cookie.
    """
    # finished payload: (message_text, row_idx)
    finished = Signal(str, int)
    # error: (msg, row_idx)
    error = Signal(str, int)

    def __init__(self, songid: int, cookies, row_idx: int, parent=None):
        super().__init__(parent)
        self._songid = songid
        self._cookies = cookies
        self._row_idx = row_idx

    def run(self):
        try:
            msg = gbs_api.submit(self._songid, self._cookies)
            self.finished.emit(msg, self._row_idx)
        except Exception as exc:
            if isinstance(exc, gbs_api.GbsAuthExpiredError):
                self.error.emit("auth_expired", self._row_idx)
            else:
                self.error.emit(str(exc), self._row_idx)


class GBSSearchDialog(QDialog):
    """D-08: Search GBS.FM catalog + submit songs to the active playlist.

    Constructor: GBSSearchDialog(repo, toast_callback, parent=None)
      repo: project Repo (currently unused by Phase 60 v1; reserved for future
            "track favoriting" / "submit history" features per D-06c deferral).
      toast_callback: forwarded to main-window toast on success/auth-expiry.

    D-08c LOCKED: entire dialog is auth-gated. UI disabled until cookies present.
    """

    submission_completed = Signal()  # mirrors station_saved from DiscoveryDialog

    def __init__(
        self,
        repo,
        toast_callback: Callable[[str], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repo
        self._toast = toast_callback
        self.setWindowTitle("Search GBS.FM")
        self.setMinimumSize(640, 480)
        self.setModal(False)

        self._search_worker: Optional[_GbsSearchWorker] = None
        self._submit_worker: Optional[_GbsSubmitWorker] = None
        self._current_page = 1
        self._total_pages = 1
        self._current_query = ""
        self._results: list[dict] = []
        self._submit_buttons: list[QPushButton] = []

        self._build_ui()
        self._refresh_login_gate()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        # Top row: search + page indicator
        top_row = QHBoxLayout()
        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText("Enter a search term…")
        # RESEARCH §Claude's Discretion: explicit-button (NOT debounced) — Django
        # ORM LIKE queries are heavy; live debounce reads as a probe attack.
        self._search_edit.returnPressed.connect(self._start_search)  # QA-05
        top_row.addWidget(self._search_edit, stretch=1)

        self._search_btn = QPushButton("Search", self)
        self._search_btn.clicked.connect(self._start_search)  # QA-05
        top_row.addWidget(self._search_btn)

        self._page_label = QLabel("", self)
        self._page_label.setTextFormat(Qt.TextFormat.PlainText)
        top_row.addWidget(self._page_label)
        root.addLayout(top_row)

        # Progress bar (indeterminate during search)
        self._progress = QProgressBar(self)
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Results table
        self._results_table = QTableView(self)
        self._model = QStandardItemModel(0, 4, self)
        self._model.setHorizontalHeaderLabels(["Artist", "Title", "Duration", "Add"])
        self._results_table.setModel(self._model)
        # Auto-stretch the Title column
        header = self._results_table.horizontalHeader()
        header.setSectionResizeMode(_COL_TITLE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_ARTIST, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_COL_DURATION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_COL_ADD, QHeaderView.ResizeMode.ResizeToContents)
        self._results_table.verticalHeader().setVisible(False)
        self._results_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._results_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        root.addWidget(self._results_table, stretch=1)

        # Inline error label (D-08d — duplicate/quota errors land here)
        self._error_label = QLabel("", self)
        self._error_label.setTextFormat(Qt.TextFormat.PlainText)
        error_font = QFont()
        error_font.setPointSize(9)
        self._error_label.setFont(error_font)
        self._error_label.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        # Pagination row (Prev / Next)
        page_row = QHBoxLayout()
        self._prev_btn = QPushButton("← Prev", self)
        self._prev_btn.setEnabled(False)
        self._prev_btn.clicked.connect(self._on_prev_clicked)  # QA-05
        page_row.addWidget(self._prev_btn)
        page_row.addStretch(1)
        self._next_btn = QPushButton("Next →", self)
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._on_next_clicked)  # QA-05
        page_row.addWidget(self._next_btn)
        root.addLayout(page_row)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        root.addWidget(button_box)

    # ---------- Login gate (D-08c) ----------

    def _refresh_login_gate(self) -> None:
        """D-08c: disable search/submit until the user has imported cookies."""
        cookies = gbs_api.load_auth_context()
        logged_in = cookies is not None
        self._search_edit.setEnabled(logged_in)
        self._search_btn.setEnabled(logged_in)
        if not logged_in:
            self._show_inline_error("Log in via Accounts → GBS.FM to search and submit songs.")
        else:
            self._hide_inline_error()

    def showEvent(self, event):
        # Re-check login gate every time the dialog is shown (user may have
        # imported cookies via AccountsDialog while this dialog was hidden).
        self._refresh_login_gate()
        super().showEvent(event)

    # ---------- Search ----------

    def _start_search(self) -> None:
        query = self._search_edit.text().strip()
        if not query:
            self._show_inline_error("Enter a search term.")
            return
        cookies = gbs_api.load_auth_context()
        if cookies is None:
            self._refresh_login_gate()
            return
        self._current_query = query
        self._current_page = 1
        self._kick_search_worker(cookies, page=1)

    def _kick_search_worker(self, cookies, page: int) -> None:
        self._hide_inline_error()
        self._search_btn.setEnabled(False)
        self._prev_btn.setEnabled(False)
        self._next_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._clear_table()
        self._search_worker = _GbsSearchWorker(self._current_query, page, cookies, parent=self)
        self._search_worker.finished.connect(self._on_search_finished)  # QA-05
        self._search_worker.error.connect(self._on_search_error)        # QA-05
        self._search_worker.start()

    def _on_search_finished(self, results: list, page: int, total_pages: int) -> None:
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)
        self._results = list(results)
        self._current_page = int(page)
        self._total_pages = int(total_pages)
        self._page_label.setText(f"Page {self._current_page} of {self._total_pages}")
        self._prev_btn.setEnabled(self._current_page > 1)
        self._next_btn.setEnabled(self._current_page < self._total_pages)
        self._render_results()
        self._search_worker = None

    def _on_search_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)
        if msg == "auth_expired":
            self._toast("GBS.FM session expired — reconnect via Accounts")
            self._refresh_login_gate()
        else:
            truncated = (msg[:80] + "…") if len(msg) > 80 else msg
            self._show_inline_error(f"Search failed: {truncated}")
        self._search_worker = None

    # ---------- Pagination ----------

    def _on_prev_clicked(self) -> None:
        if self._current_page <= 1:
            return
        cookies = gbs_api.load_auth_context()
        if cookies is None:
            self._refresh_login_gate()
            return
        self._kick_search_worker(cookies, page=self._current_page - 1)

    def _on_next_clicked(self) -> None:
        if self._current_page >= self._total_pages:
            return
        cookies = gbs_api.load_auth_context()
        if cookies is None:
            self._refresh_login_gate()
            return
        self._kick_search_worker(cookies, page=self._current_page + 1)

    # ---------- Render ----------

    def _clear_table(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._submit_buttons = []

    def _render_results(self) -> None:
        self._clear_table()
        if not self._results:
            self._show_inline_error("No results.")
            return
        self._hide_inline_error()
        for idx, result in enumerate(self._results):
            artist = QStandardItem(str(result.get("artist", "")))   # PlainText default (T-39-04)
            title = QStandardItem(str(result.get("title", "")))
            duration = QStandardItem(str(result.get("duration", "")))
            placeholder = QStandardItem("")
            self._model.appendRow([artist, title, duration, placeholder])
            btn = QPushButton("Add!", self._results_table)
            btn.clicked.connect(self._make_submit_slot(idx))  # QA-05 (closure factory, not lambda)
            self._submit_buttons.append(btn)
            self._results_table.setIndexWidget(self._model.index(idx, _COL_ADD), btn)

    def _make_submit_slot(self, row_idx: int):
        """Closure-factory for per-row Submit buttons (mirrors discovery_dialog.py:388-396)."""
        def _slot():
            self._on_submit_row(row_idx)
        return _slot

    # ---------- Submit ----------

    def _on_submit_row(self, row_idx: int) -> None:
        if not (0 <= row_idx < len(self._results)):
            return
        result = self._results[row_idx]
        try:
            songid = int(result["songid"])
        except (KeyError, TypeError, ValueError):
            self._show_inline_error("Invalid songid in result.")
            return
        cookies = gbs_api.load_auth_context()
        if cookies is None:
            self._refresh_login_gate()
            return
        # Disable the submit button immediately to prevent double-submit
        if 0 <= row_idx < len(self._submit_buttons):
            self._submit_buttons[row_idx].setEnabled(False)
            self._submit_buttons[row_idx].setText("Adding…")
        self._submit_worker = _GbsSubmitWorker(songid, cookies, row_idx, parent=self)
        self._submit_worker.finished.connect(self._on_submit_finished)  # QA-05
        self._submit_worker.error.connect(self._on_submit_error)        # QA-05
        self._submit_worker.start()

    def _on_submit_finished(self, message: str, row_idx: int) -> None:
        # Pitfall 8: message comes from Django messages cookie. Success and
        # quota / duplicate errors all arrive here (the underlying transport
        # is 302 with a messages cookie either way). Disambiguate by content.
        msg_lower = message.lower()
        is_error = any(kw in msg_lower for kw in (
            "duplicate", "already", "not enough tokens", "quota", "limit", "rate"
        )) or "error" in msg_lower
        if is_error:
            self._show_inline_error(message or "Submit rejected.")
            self._reenable_submit_button(row_idx)
        else:
            self._toast(message or "Track added to GBS.FM playlist")
            self.submission_completed.emit()
            self._reenable_submit_button(row_idx, label="Added")
        self._submit_worker = None

    def _on_submit_error(self, msg: str, row_idx: int) -> None:
        if msg == "auth_expired":
            self._toast("GBS.FM session expired — reconnect via Accounts")
            self._refresh_login_gate()
        else:
            truncated = (msg[:80] + "…") if len(msg) > 80 else msg
            self._show_inline_error(f"Submit failed: {truncated}")
        self._reenable_submit_button(row_idx)
        self._submit_worker = None

    def _reenable_submit_button(self, row_idx: int, label: str = "Add!") -> None:
        if 0 <= row_idx < len(self._submit_buttons):
            self._submit_buttons[row_idx].setEnabled(label == "Add!")
            self._submit_buttons[row_idx].setText(label)

    # ---------- Inline error helpers ----------

    def _show_inline_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def _hide_inline_error(self) -> None:
        self._error_label.setVisible(False)
        self._error_label.setText("")
```

Decisions implemented: D-08 (new dialog), D-08a (search hamburger menu — wired in Task 2), D-08b (query+results+submit shape), D-08c RESOLVED (full login gate), D-08d (inline error vs toast), D-08e RESOLVED (pagination via Prev/Next), Pitfalls 6/7/8/10/11, T-39-04, T-40-04, QA-05.
  </action>
  <verify>
    <automated>python -c "from musicstreamer.ui_qt.gbs_search_dialog import GBSSearchDialog, _GbsSearchWorker, _GbsSubmitWorker; print('OK')" &amp;&amp; grep -q 'class GBSSearchDialog' musicstreamer/ui_qt/gbs_search_dialog.py &amp;&amp; grep -q 'class _GbsSearchWorker' musicstreamer/ui_qt/gbs_search_dialog.py &amp;&amp; grep -q 'class _GbsSubmitWorker' musicstreamer/ui_qt/gbs_search_dialog.py &amp;&amp; grep -q '_make_submit_slot' musicstreamer/ui_qt/gbs_search_dialog.py &amp;&amp; grep -q 'auth_expired' musicstreamer/ui_qt/gbs_search_dialog.py &amp;&amp; ! grep -E 'clicked\.connect\(lambda' musicstreamer/ui_qt/gbs_search_dialog.py &amp;&amp; python -c "import ast; ast.parse(open('musicstreamer/ui_qt/gbs_search_dialog.py').read())"</automated>
  </verify>
  <done>
- musicstreamer/ui_qt/gbs_search_dialog.py exists with GBSSearchDialog + 2 worker classes
- Login gate disables search until cookies file present (D-08c)
- Per-row Submit via _make_submit_slot closure factory (NOT self-capturing lambda — QA-05)
- Auth-expired path toasts + re-checks login gate
- Inline error label for duplicate/token-quota (D-08d)
- Pagination via Prev/Next buttons reads total_pages from search() response
- Module parses cleanly; no QA-05 lambda violations
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add 'Search GBS.FM…' menu entry + _open_gbs_search_dialog handler to main_window.py</name>
  <read_first>
    - musicstreamer/ui_qt/main_window.py (post Plan 60-03 state — verify act_gbs_add at lines 138-141 area; verify _open_discovery_dialog at lines 668-672)
    - musicstreamer/ui_qt/gbs_search_dialog.py (verify constructor signature from Task 1)
  </read_first>
  <behavior>
    - act_gbs_search menu entry inserted in Group 1 directly AFTER act_gbs_add (Plan 60-03 added the latter)
    - Bound-method connection: act_gbs_search.triggered.connect(self._open_gbs_search_dialog)
    - _open_gbs_search_dialog mirrors _open_discovery_dialog exactly (drops player arg per CONTEXT.md "no preview play")
  </behavior>
  <action>
**Step A — extend the Group 1 menu construction.** Plan 60-03 inserted:
```python
act_gbs_add = self._menu.addAction("Add GBS.FM")
act_gbs_add.triggered.connect(self._on_gbs_add_clicked)
self._menu.addSeparator()
```

Now insert TWO new lines BETWEEN `act_gbs_add.triggered.connect(...)` and `self._menu.addSeparator()`:

```python
        act_gbs_search = self._menu.addAction("Search GBS.FM…")  # U+2026 ellipsis
        act_gbs_search.triggered.connect(self._open_gbs_search_dialog)  # QA-05
```

**Step B — add the handler method** alongside `_open_discovery_dialog` (around line 668-672):

```python
    def _open_gbs_search_dialog(self) -> None:
        """Phase 60 D-08 / GBS-01e: open the search-and-submit dialog.

        Mirrors _open_discovery_dialog at line 668 (drops the player arg per
        CONTEXT.md "Phase 60's search dialog does NOT need preview play").
        """
        from musicstreamer.ui_qt.gbs_search_dialog import GBSSearchDialog
        dlg = GBSSearchDialog(self._repo, self.show_toast, parent=self)
        dlg.exec()
```

(`submission_completed` is fired by the dialog but Phase 60 doesn't need to refresh the station list on submit success — submitting a song doesn't touch the local library. Leave the signal unconnected for now; future phase can attach a "submit history" widget here if desired.)

**Step C — update EXPECTED_ACTION_TEXTS** if Plan 60-03 surfaced one. Run:
```bash
grep -n "EXPECTED_ACTION_TEXTS" tests/
```
If a list exists, append `"Search GBS.FM…"` (U+2026) in the correct order — directly after `"Add GBS.FM"`.

Decisions implemented: D-08a (Group 1 placement next to Add GBS.FM); QA-05.
  </action>
  <verify>
    <automated>grep -q 'addAction("Search GBS.FM' musicstreamer/ui_qt/main_window.py &amp;&amp; grep -q '_open_gbs_search_dialog' musicstreamer/ui_qt/main_window.py &amp;&amp; grep -q 'GBSSearchDialog' musicstreamer/ui_qt/main_window.py &amp;&amp; ! grep -E 'act_gbs_search\.triggered\.connect\(lambda' musicstreamer/ui_qt/main_window.py &amp;&amp; python -c "import ast; ast.parse(open('musicstreamer/ui_qt/main_window.py').read())"</automated>
  </verify>
  <done>
- "Search GBS.FM…" menu entry exists in Group 1 next to "Add GBS.FM"
- _open_gbs_search_dialog handler instantiates GBSSearchDialog with (repo, show_toast, parent)
- Bound-method connection (no QA-05 violation)
- Module parses cleanly
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Create tests/test_gbs_search_dialog.py with pytest-qt tests</name>
  <read_first>
    - tests/test_discovery_dialog.py (read in full — qtbot fixture + worker-stub pattern + table-row assertions)
    - musicstreamer/ui_qt/gbs_search_dialog.py (post Task 1)
    - .planning/phases/60-gbs-fm-integration/60-PATTERNS.md (§"tests/ui_qt/test_gbs_search_dialog.py")
    - .planning/phases/60-gbs-fm-integration/60-VALIDATION.md (§"Per-Task Verification Map" GBS-01e UI rows)
    - tests/conftest.py (fake_repo + mock_gbs_api fixtures from Plan 60-01)
  </read_first>
  <behavior>
    - test_dialog_opens_with_login_gate_when_no_cookies: no cookies file → search field disabled + inline message "Log in via Accounts"
    - test_dialog_opens_search_enabled_when_cookies_present: cookies file exists → search field enabled
    - test_search_populates_results_from_mock: stub _GbsSearchWorker; emit finished(results, 1, 3) → table has rows for each result, Add button per row
    - test_search_pagination_buttons_reflect_total_pages: emit finished([], 2, 5) → Prev enabled, Next enabled, page label "Page 2 of 5"
    - test_search_auth_expired_toasts_and_disables: emit error("auth_expired") → toast contains "session expired"
    - test_search_generic_error_inline: emit error("Connection refused") → inline error label shows truncated
    - test_submit_success_toasts_track_added: emit finished("Track added successfully!", 0) → toast captured
    - test_submit_inline_error_on_duplicate: emit finished("Track is already in queue", 0) → inline error visible (not toast)
    - test_submit_inline_error_on_token_quota: emit finished("You don't have enough tokens", 0) → inline error visible
    - test_submit_auth_expired_toasts_and_relocks_login: emit error("auth_expired", 0) → toast + login gate re-checked
    - test_no_self_capturing_lambdas_in_dialog: grep guard against `lambda` in clicked.connect
  </behavior>
  <action>
Create `tests/test_gbs_search_dialog.py`:

```python
"""Phase 60 / GBS-01e: GBSSearchDialog UI tests.

Mirrors tests/test_discovery_dialog.py pattern — qtbot fixture +
worker-stub via monkeypatch.
"""
from __future__ import annotations

import os
import re
from unittest.mock import MagicMock

import pytest

from musicstreamer import paths
from musicstreamer.ui_qt.gbs_search_dialog import (
    GBSSearchDialog,
    _GbsSearchWorker,
    _GbsSubmitWorker,
)


def _ensure_cookies(tmp_path):
    """Create a fake cookies file at paths.gbs_cookies_path()."""
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(paths.gbs_cookies_path(), "w") as f:
        f.write("# fake")


@pytest.fixture
def dialog_no_login(qtbot, fake_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: None)
    captured = []
    dlg = GBSSearchDialog(fake_repo, captured.append)
    qtbot.addWidget(dlg)
    return dlg, captured


@pytest.fixture
def dialog_logged_in(qtbot, fake_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    _ensure_cookies(tmp_path)
    fake_jar = MagicMock()
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: fake_jar)
    captured = []
    dlg = GBSSearchDialog(fake_repo, captured.append)
    # Stub worker .start() so no real network/threads spawn
    monkeypatch.setattr(_GbsSearchWorker, "start", lambda self: None)
    monkeypatch.setattr(_GbsSubmitWorker, "start", lambda self: None)
    qtbot.addWidget(dlg)
    return dlg, captured


def test_dialog_opens_with_login_gate_when_no_cookies(dialog_no_login):
    """D-08c: no cookies → search field disabled + inline message."""
    dlg, _ = dialog_no_login
    assert dlg._search_edit.isEnabled() is False
    assert dlg._search_btn.isEnabled() is False
    assert dlg._error_label.isVisible() is True
    assert "Log in" in dlg._error_label.text()


def test_dialog_opens_search_enabled_when_cookies_present(dialog_logged_in):
    dlg, _ = dialog_logged_in
    assert dlg._search_edit.isEnabled() is True
    assert dlg._search_btn.isEnabled() is True


def test_search_populates_results_from_mock(dialog_logged_in):
    dlg, _ = dialog_logged_in
    dlg._search_edit.setText("test")
    dlg._start_search()
    # Worker is stubbed; emit finished directly
    results = [
        {"songid": 100, "artist": "A1", "title": "T1", "duration": "3:00", "add_url": "/add/100"},
        {"songid": 101, "artist": "A2", "title": "T2", "duration": "4:00", "add_url": "/add/101"},
    ]
    dlg._on_search_finished(results, 1, 3)
    assert dlg._model.rowCount() == 2
    # Artist column
    assert dlg._model.item(0, 0).text() == "A1"
    assert dlg._model.item(1, 0).text() == "A2"
    # Per-row Add button
    assert len(dlg._submit_buttons) == 2
    assert dlg._submit_buttons[0].text() == "Add!"


def test_search_pagination_buttons_reflect_total_pages(dialog_logged_in):
    dlg, _ = dialog_logged_in
    dlg._on_search_finished([], 2, 5)
    assert dlg._prev_btn.isEnabled() is True
    assert dlg._next_btn.isEnabled() is True
    assert "Page 2 of 5" in dlg._page_label.text()


def test_search_first_page_disables_prev(dialog_logged_in):
    dlg, _ = dialog_logged_in
    dlg._on_search_finished([], 1, 3)
    assert dlg._prev_btn.isEnabled() is False
    assert dlg._next_btn.isEnabled() is True


def test_search_last_page_disables_next(dialog_logged_in):
    dlg, _ = dialog_logged_in
    dlg._on_search_finished([], 5, 5)
    assert dlg._prev_btn.isEnabled() is True
    assert dlg._next_btn.isEnabled() is False


def test_search_auth_expired_toasts_and_disables(dialog_logged_in, monkeypatch):
    """Pitfall 3: auth_expired → toast + relock login gate."""
    dlg, captured = dialog_logged_in
    # Simulate cookies disappearing
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: None)
    dlg._on_search_error("auth_expired")
    assert any("session expired" in t.lower() and "Accounts" in t for t in captured)
    assert dlg._search_edit.isEnabled() is False


def test_search_generic_error_inline(dialog_logged_in):
    dlg, captured = dialog_logged_in
    dlg._on_search_error("Connection refused")
    assert dlg._error_label.isVisible() is True
    assert "Search failed" in dlg._error_label.text()
    assert "Connection refused" in dlg._error_label.text()
    # Generic errors do NOT toast (only auth-expired does)
    assert all("Connection refused" not in t for t in captured)


def test_submit_success_toasts_track_added(dialog_logged_in):
    """D-08d: success message comes via Django messages cookie text."""
    dlg, captured = dialog_logged_in
    dlg._results = [{"songid": 100, "artist": "A", "title": "T", "duration": "3:00", "add_url": "/add/100"}]
    dlg._on_search_finished(dlg._results, 1, 1)
    dlg._on_submit_finished("Track added successfully!", 0)
    assert any("Track added successfully" in t for t in captured)


def test_submit_inline_error_on_duplicate(dialog_logged_in):
    """D-08d: 'duplicate' message → inline error, NOT toast."""
    dlg, captured = dialog_logged_in
    dlg._results = [{"songid": 100, "artist": "A", "title": "T", "duration": "3:00", "add_url": "/add/100"}]
    dlg._on_search_finished(dlg._results, 1, 1)
    dlg._on_submit_finished("Track is already in queue (duplicate)", 0)
    assert dlg._error_label.isVisible() is True
    assert "duplicate" in dlg._error_label.text().lower() or "already" in dlg._error_label.text().lower()
    # Should NOT toast (D-08d — inline preserves search context)
    assert all("duplicate" not in t.lower() for t in captured)


def test_submit_inline_error_on_token_quota(dialog_logged_in):
    """Pitfall 8: quota / token-limit message → inline error."""
    dlg, _ = dialog_logged_in
    dlg._results = [{"songid": 100, "artist": "A", "title": "T", "duration": "3:00", "add_url": "/add/100"}]
    dlg._on_search_finished(dlg._results, 1, 1)
    dlg._on_submit_finished("You don't have enough tokens", 0)
    assert dlg._error_label.isVisible() is True
    assert "tokens" in dlg._error_label.text().lower()


def test_submit_auth_expired_toasts_and_relocks_login(dialog_logged_in, monkeypatch):
    dlg, captured = dialog_logged_in
    dlg._results = [{"songid": 100, "artist": "A", "title": "T", "duration": "3:00", "add_url": "/add/100"}]
    dlg._on_search_finished(dlg._results, 1, 1)
    monkeypatch.setattr("musicstreamer.gbs_api.load_auth_context", lambda: None)
    dlg._on_submit_error("auth_expired", 0)
    assert any("session expired" in t.lower() and "Accounts" in t for t in captured)
    assert dlg._search_edit.isEnabled() is False


def test_submit_disabled_button_during_request(dialog_logged_in):
    """Double-submit prevention: button disabled + 'Adding…' label during in-flight."""
    dlg, _ = dialog_logged_in
    dlg._results = [{"songid": 100, "artist": "A", "title": "T", "duration": "3:00", "add_url": "/add/100"}]
    dlg._on_search_finished(dlg._results, 1, 1)
    dlg._on_submit_row(0)
    assert dlg._submit_buttons[0].isEnabled() is False
    assert "Adding" in dlg._submit_buttons[0].text()


def test_no_self_capturing_lambdas_in_dialog():
    """QA-05 / Pitfall 10: no `clicked.connect(lambda...)` in gbs_search_dialog.py."""
    src = open("musicstreamer/ui_qt/gbs_search_dialog.py").read()
    matches = re.findall(r"\.connect\(([^)]+)\)", src)
    for m in matches:
        # Allow self-bound methods and well-formed closures from _make_submit_slot
        assert "lambda" not in m, f"QA-05 violation: connect({m!r})"


def test_main_window_search_menu_entry_exists():
    """D-08a: 'Search GBS.FM…' menu action exists in main_window.py."""
    src = open("musicstreamer/ui_qt/main_window.py").read()
    assert re.search(r'addAction\(["\']Search GBS\.FM', src), \
        "Expected 'Search GBS.FM…' menu entry in main_window.py"
    assert "_open_gbs_search_dialog" in src
```

Decisions implemented: VALIDATION.md GBS-01e UI rows; Pitfalls 3/6/7/8/10/11; D-08a/b/c/d/e.
  </action>
  <verify>
    <automated>pytest tests/test_gbs_search_dialog.py -x -q 2>&amp;1 | tail -15 &amp;&amp; pytest tests/test_gbs_api.py -x -q 2>&amp;1 | tail -5</automated>
  </verify>
  <done>
- 14 tests in tests/test_gbs_search_dialog.py — all pass
- Login gate tests cover D-08c
- Pagination tests cover D-08e
- Submit-success vs inline-error distinction tested (D-08d)
- Auth-expired tested for both search and submit
- Double-submit prevention tested
- QA-05 grep guard test inside the suite
- main_window menu entry sanity-check via regex
- pytest -x runs green
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User input ↔ HTTP query | Query string urlencoded by gbs_api.search; no SQL or shell exposure |
| gbs.fm HTML response ↔ QStandardItem cells | Untrusted HTML parsed in gbs_api; cells set with PlainText (T-39-04) |
| /add/<id> 302 ↔ Django messages cookie | Decoded text surfaces in inline error / toast verbatim |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-60-34 | Tampering | Search HTML parser regression breaks results | mitigate | gbs_api.search anchors on /song/<id> + /add/<id> hrefs (Pitfall 6); fixture-pinned tests in test_gbs_api.py catch shape regressions; dialog renders empty list gracefully on parse failure. |
| T-60-35 | Repudiation | Submit GET retried on transient failure | mitigate | NO retry in gbs_api.submit (Pitfall 7); inline error surfaces; user re-clicks Add to retry. |
| T-60-36 | Information Disclosure | Token-quota error not surfaced to user | mitigate | gbs_api.submit decodes Django messages cookie (Pitfall 8); _on_submit_finished surfaces verbatim into inline error label (D-08d). |
| T-60-37 | Spoofing | Auth-expired during submit silently fails | mitigate | "auth_expired" sentinel triggers toast + login-gate refresh; dialog stays open so user can re-import cookies and retry without losing the search context. |
| T-60-38 | Denial of Service | Live-debounced search probes Django ORM | mitigate | Explicit Search button (NOT debounced — RESEARCH §Claude's Discretion + Pitfall 5). returnPressed on QLineEdit also triggers a single search. |
| T-60-39 | Information Disclosure | gbs.fm artist/title injects HTML into result cells | mitigate | QStandardItem cells default to PlainText (T-39-04); explicit `Qt.TextFormat.PlainText` on inline error label (T-40-04); page label same. Pitfall 11. |
| T-60-40 | Tampering | Self-capturing lambda in per-row Submit button | mitigate | `_make_submit_slot(row_idx)` closure factory (mirrors discovery_dialog.py:388-396); explicit `lambda` guard test. Pitfall 10. |
| T-60-41 | Information Disclosure | Login-gate bypassed if cookies expire mid-session | mitigate | Every action (search start, submit, prev/next) re-checks `gbs_api.load_auth_context()` before kicking the worker; if None → falls back to login-gate UI. |

Citations: Pitfalls 3, 5, 6, 7, 8, 10, 11 from RESEARCH.md.
</threat_model>

<verification>
```bash
pytest tests/test_gbs_search_dialog.py tests/test_gbs_api.py -x -q
python -c "from musicstreamer.ui_qt.gbs_search_dialog import GBSSearchDialog; from musicstreamer.ui_qt.main_window import MainWindow; print('OK')"
pytest -x   # full suite green
```
</verification>

<success_criteria>
- `musicstreamer/ui_qt/gbs_search_dialog.py` exists with GBSSearchDialog + 2 worker classes
- "Search GBS.FM…" hamburger menu entry exists next to "Add GBS.FM"
- Login gate disables UI when no cookies file (D-08c)
- Search flow: query + Search button → results table → per-row Add button → submit → toast OR inline error (D-08d)
- Pagination Prev/Next buttons enabled based on total_pages
- Auth-expired during search OR submit → toast + login-gate refresh (dialog stays open)
- 14 tests in tests/test_gbs_search_dialog.py pass
- pytest -x runs green (no regressions)
</success_criteria>

<output>
After completion, create `.planning/phases/60-gbs-fm-integration/60-07-SUMMARY.md`
</output>
