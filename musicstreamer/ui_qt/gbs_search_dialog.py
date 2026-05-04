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
    QListWidget,
    QListWidgetItem,
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
    # 60-11 / T12: pre-existing finished signal kept stable; artist/album link
    # metadata streams via a separate signal so the existing 16 tests don't churn.
    metadata_ready = Signal(list, list)  # (artist_links, album_links)
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
            # =====================================================================
            # ORDERING INVARIANT (60-11 / T12 — DEFENSIVE; DO NOT REORDER):
            #
            # finished MUST emit BEFORE metadata_ready.
            #
            # Why: _on_search_finished -> _render_results -> _clear_table HIDES
            # the artist/album panels. _on_metadata_ready then RE-SHOWS them by
            # populating the lists (D-11c). If metadata_ready emits first, the
            # subsequent _clear_table call from finished will hide the panels
            # we just populated. Qt signal queue order matches emit order, so
            # the emit ordering here is the load-bearing invariant.
            #
            # If a future refactor splits this method or adds buffering, the
            # invariant must be preserved (or _clear_table must be made aware
            # of the metadata state — currently the simpler invariant is the
            # right call per diagnosis §5d acceptable trade-off).
            # =====================================================================
            self.finished.emit(
                list(out.get("results", [])),
                int(out.get("page", self._page)),
                int(out.get("total_pages", self._page)),
            )
            self.metadata_ready.emit(
                list(out.get("artist_links", [])),
                list(out.get("album_links", [])),
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

    def __init__(self, songid: int, cookies, row_idx: int,
                 search_version: int, parent=None):
        super().__init__(parent)
        self._songid = songid
        self._cookies = cookies
        self._row_idx = row_idx
        # HIGH 5 fix: stamp search_version so the dialog can discard
        # callbacks from in-flight submits that belong to a stale search.
        self.search_version = search_version

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
        # HIGH 5 fix: monotonic version token. Incremented on every new
        # search; submits from stale searches are discarded by version mismatch
        # in _on_submit_finished / _on_submit_error.
        self._search_version: int = 0

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

        # 60-11 / T12: Artist:/Album: panels — hidden by default, shown when
        # search response includes non-empty artist_links / album_links (page 1
        # with matches per diagnosis §2a). D-11b LOCKED max-height 80px.
        # D-11c LOCKED: hidden when empty, shown only via _on_metadata_ready.
        self._artist_label = QLabel("Artist:", self)
        self._artist_label.setTextFormat(Qt.TextFormat.PlainText)
        self._artist_label.setVisible(False)
        root.addWidget(self._artist_label)

        self._artist_list = QListWidget(self)
        self._artist_list.setMaximumHeight(80)  # D-11b LOCKED default
        self._artist_list.setVisible(False)
        # D-11a Shape 4 LOCKED: click navigates via free-text search (QA-05)
        self._artist_list.itemActivated.connect(self._on_artist_link_activated)
        root.addWidget(self._artist_list)

        self._album_label = QLabel("Album:", self)
        self._album_label.setTextFormat(Qt.TextFormat.PlainText)
        self._album_label.setVisible(False)
        root.addWidget(self._album_label)

        self._album_list = QListWidget(self)
        self._album_list.setMaximumHeight(80)  # D-11b LOCKED default
        self._album_list.setVisible(False)
        # D-11a Shape 4 LOCKED: click navigates via free-text search (QA-05)
        self._album_list.itemActivated.connect(self._on_album_link_activated)
        root.addWidget(self._album_list)

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
        # HIGH 5 fix: bump search_version BEFORE dispatching the worker so any
        # in-flight submits from the previous results set get discarded by
        # version mismatch when their callbacks fire.
        self._search_version += 1
        self._kick_search_worker(cookies, page=1)

    def _kick_search_worker(self, cookies, page: int) -> None:
        self._hide_inline_error()
        self._search_btn.setEnabled(False)
        self._prev_btn.setEnabled(False)
        self._next_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._clear_table()
        self._search_worker = _GbsSearchWorker(self._current_query, page, cookies, parent=self)
        self._search_worker.finished.connect(self._on_search_finished)          # QA-05
        self._search_worker.metadata_ready.connect(self._on_metadata_ready)    # 60-11 / T12 QA-05
        self._search_worker.error.connect(self._on_search_error)               # QA-05
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

    def _on_metadata_ready(self, artist_links: list, album_links: list) -> None:
        """60-11 / T12: populate Artist:/Album: panels above the song results.

        D-11c LOCKED: hide entirely when the corresponding list is empty.
        Each entry stores its href in Qt.ItemDataRole.UserRole for navigation.

        Per the ORDERING INVARIANT in _GbsSearchWorker.run(), this slot runs
        AFTER _on_search_finished -> _clear_table, so we always start with
        cleared+hidden panels. Population here is the only path that re-shows.
        """
        # Artist panel
        self._artist_list.clear()
        for entry in artist_links:
            item = QListWidgetItem(str(entry.get("text", "")))  # PlainText (T-40-04)
            item.setData(Qt.ItemDataRole.UserRole, str(entry.get("url", "")))
            self._artist_list.addItem(item)
        has_artists = bool(artist_links)
        self._artist_label.setVisible(has_artists)
        self._artist_list.setVisible(has_artists)
        # Album panel
        self._album_list.clear()
        for entry in album_links:
            item = QListWidgetItem(str(entry.get("text", "")))  # PlainText (T-40-04)
            item.setData(Qt.ItemDataRole.UserRole, str(entry.get("url", "")))
            self._album_list.addItem(item)
        has_albums = bool(album_links)
        self._album_label.setVisible(has_albums)
        self._album_list.setVisible(has_albums)

    # ---------- Artist/Album click navigation (D-11a Shape 4 LOCKED) ----------
    # Per Task 0 capture: Shape 4 locked — /artist/<id> has no <table class='songs'>;
    # /album/<id> has no <table class='songs'>. Both surfaces use free-text search fallback.
    # Navigation: clicking an entry sets the search field to the item text and re-runs search.

    def _on_artist_link_activated(self, item) -> None:
        """60-11 / T12 — D-11a Shape 4: free-text search fallback for artist navigation.

        Sets the search input to the artist name and kicks a new search.
        Uses item.text() (plain text, T-40-04) — NOT the href (Shape 4 ignores /artist/<id>
        since that page has no parseable song table per Task 0 fixture inspection).
        """
        artist_text = item.text()
        if not artist_text:
            return
        self._search_edit.setText(artist_text)
        self._start_search()

    def _on_album_link_activated(self, item) -> None:
        """60-11 / T12 — D-11a Shape 4: free-text search fallback for album navigation.

        Sets the search input to the album name and kicks a new search.
        Uses item.text() (plain text, T-40-04) — NOT the href (Shape 4 ignores /album/<id>
        since that page has no parseable song table per Task 0 fixture inspection).
        """
        album_text = item.text()
        if not album_text:
            return
        self._search_edit.setText(album_text)
        self._start_search()

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
        # 60-11 / T12: also hide artist/album panels — they re-show only when
        # the next search response includes non-empty links via _on_metadata_ready.
        # See ORDERING INVARIANT in _GbsSearchWorker.run(): metadata_ready emits
        # AFTER finished, so this hide is always followed by the correct re-show.
        if hasattr(self, "_artist_list"):
            self._artist_list.clear()
            self._artist_label.setVisible(False)
            self._artist_list.setVisible(False)
        if hasattr(self, "_album_list"):
            self._album_list.clear()
            self._album_label.setVisible(False)
            self._album_list.setVisible(False)

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
        # HIGH 5 fix: stamp current _search_version so callbacks know whether
        # the underlying results list is still the one this submit was
        # dispatched against.
        self._submit_worker = _GbsSubmitWorker(
            songid, cookies, row_idx,
            search_version=self._search_version,
            parent=self,
        )
        self._submit_worker.finished.connect(self._on_submit_finished)  # QA-05
        self._submit_worker.error.connect(self._on_submit_error)        # QA-05
        self._submit_worker.start()

    def _on_submit_finished(self, message: str, row_idx: int) -> None:
        # HIGH 5 fix: discard if a re-search has invalidated row_idx.
        # sender() is non-None only when called via Qt signal machinery.
        # When None (direct call in tests or GC'd), the staleness check is
        # inapplicable — proceed normally. Only discard when the sender is a
        # live worker object with a mismatched search_version.
        worker = self.sender()
        if worker is not None and getattr(worker, "search_version", -1) != self._search_version:
            return  # stale callback — buttons in current results list belong to a different search
        # Pitfall 8: message comes from Django messages cookie. Success and
        # quota / duplicate errors all arrive here (the underlying transport
        # is 302 with a messages cookie either way). Disambiguate by content.
        msg_lower = message.lower()
        is_error = any(kw in msg_lower for kw in (
            "duplicate", "already", "not enough tokens", "enough tokens",
            "quota", "limit", "rate",
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
        # HIGH 5 fix: discard if a re-search has invalidated row_idx.
        # Same semantics as _on_submit_finished: only discard when sender is a
        # live worker with a mismatched search_version.
        worker = self.sender()
        if worker is not None and getattr(worker, "search_version", -1) != self._search_version:
            return
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
