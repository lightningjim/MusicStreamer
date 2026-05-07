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

import logging
import re
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
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX, WARNING_COLOR_HEX

_log = logging.getLogger(__name__)

_COL_ARTIST = 0
_COL_TITLE = 1
_COL_DURATION = 2
_COL_ADD = 3

# Phase 60.1 / GBS-01e drill-down: regex-validate hrefs from artist/album panel UserRole
# data BEFORE constructing fetch URLs (T-60.1-09 URL injection mitigation).
_ARTIST_HREF_RE = re.compile(r"^/artist/(\d+)$")
_ALBUM_HREF_RE = re.compile(r"^/album/(\d+)$")


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


class _GbsArtistWorker(QThread):
    """Phase 60.1 / GBS-01e drill-down: gbs_api.fetch_artist_songs on a worker thread.

    Mirrors _GbsSubmitWorker's typed-signal shape — finished emits a single payload
    (the drilled artist's songs as a list[dict] with keys
    {songid, artist, title, duration, add_url} matching _SongRowParser output).

    Per CONTEXT.md D-06: own typed `finished` signal, dedicated dialog slot
    (_on_artist_drilled). NO multi-mode signal, NO metadata_ready (drilled pages
    have no <p class="artists"> blocks per Pitfall 4).
    """
    # finished payload: list of result dicts
    finished = Signal(list)
    # error: 'auth_expired' sentinel OR raw msg
    error = Signal(str)

    def __init__(self, artist_id: int, artist_name: str, cookies, parent=None):
        super().__init__(parent)
        self._artist_id = artist_id
        self._artist_name = artist_name  # carried for breadcrumb rendering
        self._cookies = cookies

    @property
    def artist_name(self) -> str:
        """Read-only artist name for the breadcrumb label."""
        return self._artist_name

    def run(self):
        try:
            out = gbs_api.fetch_artist_songs(self._artist_id, self._cookies)
            self.finished.emit(list(out.get("results", [])))
        except Exception as exc:
            if isinstance(exc, gbs_api.GbsAuthExpiredError):
                self.error.emit("auth_expired")
            else:
                self.error.emit(str(exc))


class _GbsAlbumWorker(QThread):
    """Phase 60.1 / GBS-01e drill-down: gbs_api.fetch_album_songs on a worker thread.

    Mirrors _GbsArtistWorker exactly with album_id and fetch_album_songs.
    Per RESEARCH §Pattern 2 + project minimum-diff convention: duplicate, do NOT factor
    a base class.
    """
    # finished payload: list of result dicts
    finished = Signal(list)
    # error: 'auth_expired' sentinel OR raw msg
    error = Signal(str)

    def __init__(self, album_id: int, album_name: str, cookies, parent=None):
        super().__init__(parent)
        self._album_id = album_id
        self._album_name = album_name
        self._cookies = cookies

    @property
    def album_name(self) -> str:
        return self._album_name

    def run(self):
        try:
            out = gbs_api.fetch_album_songs(self._album_id, self._cookies)
            self.finished.emit(list(out.get("results", [])))
        except Exception as exc:
            if isinstance(exc, gbs_api.GbsAuthExpiredError):
                self.error.emit("auth_expired")
            else:
                self.error.emit(str(exc))


class _GbsTokenWorker(QThread):
    """Phase 60.4 D-T1: gbs_api.fetch_user_tokens on a worker thread.

    Mirrors _GbsSubmitWorker (lines 113-142) shape with one deliberate
    deviation: signals carry the request_id as the LEADING positional
    payload, not via the worker.attribute + sender() pattern. This makes
    the consumer-side stale-discard guard a positional comparison
    (`if request_id != self._token_request_id: return`) that works
    correctly when the slot is called directly in tests (where
    `self.sender()` returns None).

    Pitfall 5+7 (60-RESEARCH): NO retry on transient failure. Caller's next
    trigger (next submit, next dialog open) is the retry.

    Pitfall A (60.4-RESEARCH): self.request_id stamped at construction AND
    emitted in payload; consumer slots discard callbacks whose request_id
    != current dialog id.
    """
    # finished payload: (request_id, count)
    finished = Signal(int, int)
    # error payload: (request_id, msg)
    # msg: 'auth_expired' sentinel OR 'parse_failed' OR raw exception message
    error = Signal(int, str)

    def __init__(self, cookies, request_id: int, parent=None):
        super().__init__(parent)
        self._cookies = cookies
        self.request_id = request_id  # public; mirrors _GbsSubmitWorker.search_version

    def run(self):
        try:
            count = gbs_api.fetch_user_tokens(self._cookies)
            if count is None:
                # D-T2 path: parse miss / network / 5xx / malformed → '—' placeholder
                self.error.emit(self.request_id, "parse_failed")
            else:
                self.finished.emit(self.request_id, int(count))
        except Exception as exc:
            if isinstance(exc, gbs_api.GbsAuthExpiredError):
                self.error.emit(self.request_id, "auth_expired")
            else:
                self.error.emit(self.request_id, str(exc))


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
        # Phase 60.1 / GBS-01e drill-down state
        self._artist_drill_worker: Optional[_GbsArtistWorker] = None
        self._album_drill_worker: Optional[_GbsAlbumWorker] = None
        # Snapshot of pre-drill dialog state; None when not in drill-down mode.
        # Single-shot per drill session (Pitfall 8 — second click while drilled
        # must NOT overwrite this snapshot).
        self._pre_drill_state: Optional[dict] = None

        # Phase 60.4 D-T1/D-T3: token-counter state. _last_known_tokens
        # carries the optimistic-decrement integer between submit and refetch.
        # _token_request_id is the monotonic id stamped on each kick AND emitted
        # in the worker's finished/error payloads; slot-side discard guard
        # (Pitfall A) drops stale callbacks via positional request_id arg.
        # _was_logged_in tracks the prior login state so _refresh_login_gate
        # only kicks _GbsTokenWorker on the False→True transition (avoids
        # redundant fetches on showEvent re-fires).
        # _token_worker is the SYNC retain ref (mirrors _submit_worker line 243).
        self._last_known_tokens: Optional[int] = None
        self._token_request_id: int = 0
        self._was_logged_in: bool = False
        self._token_worker: Optional[_GbsTokenWorker] = None

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
        # Phase 60.1: breadcrumb replaces _page_label slot during drill-down (UI-SPEC Delta 1).
        # PlainText (T-40-04); no font override (UI-SPEC Typography); no setStyleSheet.
        self._breadcrumb_label = QLabel("", self)
        self._breadcrumb_label.setTextFormat(Qt.TextFormat.PlainText)
        self._breadcrumb_label.setVisible(False)
        top_row.addWidget(self._breadcrumb_label)
        # Phase 60.4 D-T4/D-T5/D-T7: token counter label.
        # Hidden by default; toggled by _refresh_login_gate.
        # PlainText (T-40-04 / Pitfall H) — mirrors _breadcrumb_label at line 288.
        self._token_label = QLabel("", self)
        self._token_label.setTextFormat(Qt.TextFormat.PlainText)
        self._token_label.setVisible(False)
        top_row.addWidget(self._token_label)
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
        # Phase 60.1: Back button replaces Prev/Next during drill-down (UI-SPEC Delta 2).
        # Hidden by default; shown by drill-down render slots, hidden by _on_back_clicked
        # and _reset_drill_chrome.
        self._back_btn = QPushButton("← Back to search", self)
        self._back_btn.setVisible(False)
        self._back_btn.clicked.connect(self._on_back_clicked)  # QA-05
        page_row.addWidget(self._back_btn)
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
        """D-08c: disable search/submit until the user has imported cookies.

        Phase 60.4 D-T7: also toggles _token_label visibility and, on the
        False→True logged-in transition (tracked via self._was_logged_in),
        kicks _GbsTokenWorker for the initial fetch. Repeated logged-in
        calls (e.g., showEvent re-fires) do NOT spawn redundant workers —
        only the actual logged-out → logged-in transition does.
        """
        cookies = gbs_api.load_auth_context()
        logged_in = cookies is not None
        prev_logged_in = self._was_logged_in
        self._was_logged_in = logged_in
        self._search_edit.setEnabled(logged_in)
        self._search_btn.setEnabled(logged_in)
        # D-T7: toggle _token_label visibility; the attribute may not yet
        # exist if _refresh_login_gate is called from the constructor BEFORE
        # _build_ui — guard accordingly (defense in depth; current code path
        # always has _build_ui run first at line 261 before this call at 262).
        # Note: we ONLY toggle visibility here — text and stylesheet are managed
        # by _on_submit_error / _on_token_error / _on_token_fetched. Specifically,
        # D-T8 stamps "Tokens: —" via _on_submit_error BEFORE the gate runs;
        # clearing the text here would erase that stamp before the user sees it.
        if hasattr(self, "_token_label"):
            self._token_label.setVisible(logged_in)
        if not logged_in:
            self._show_inline_error("Log in via Accounts → GBS.FM to search and submit songs.")
        else:
            self._hide_inline_error()
        # D-T1: kick initial token fetch ONLY on the False→True transition.
        # Avoids redundant kicks on showEvent re-fires while already logged-in.
        if logged_in and not prev_logged_in:
            self._kick_token_worker(cookies)

    # ------------------- Phase 60.4 token counter (D-T1..D-T8) -------------------

    def _kick_token_worker(self, cookies) -> None:
        """D-T1: spawn a fresh _GbsTokenWorker for fetch_user_tokens.

        Pitfall A: monotonic _token_request_id stamped per kick AND emitted
        as the leading positional payload in the worker's finished/error
        signals. Slot-side guard discards callbacks whose request_id != the
        current dialog id.
        """
        self._token_request_id += 1
        rid = self._token_request_id
        worker = _GbsTokenWorker(cookies, rid, parent=self)
        worker.finished.connect(self._on_token_fetched)  # QA-05 bound-method
        worker.error.connect(self._on_token_error)        # QA-05 bound-method
        self._token_worker = worker  # SYNC retain (mirrors _submit_worker line 243)
        worker.start()

    def _on_token_fetched(self, request_id: int, count: int) -> None:
        """D-T1 + D-T6: stamp _token_label with the fetched count + apply color tier.

        Pitfall A: discard if request_id is stale (a newer kick is authoritative).
        The guard is a POSITIONAL comparison — no self.sender() use — so it
        works correctly both when wired via Signal (sender returns the
        QThread) AND when called directly in tests (sender returns None).
        """
        if request_id != self._token_request_id:
            return  # stale — newer kick is authoritative
        self._last_known_tokens = int(count)
        self._token_label.setText(f"Tokens: {int(count)}")
        self._apply_token_color(int(count))
        self._token_worker = None

    def _on_token_error(self, request_id: int, msg: str) -> None:
        """D-T2 + D-T8: '—' placeholder on parse miss / network; auth-expired
        flips state to None + clears style + delegates to _refresh_login_gate.

        Pitfall A: discard if request_id is stale.
        Pitfall 3: silent log; NO toast.
        """
        if request_id != self._token_request_id:
            return  # stale — discard
        if msg == "auth_expired":
            # Auth expired during in-flight fetch — flip the label, clear state,
            # and let _refresh_login_gate take over visibility. The toast for
            # auth-expired is owned by _on_submit_error (the canonical path);
            # this branch is the rare race where the token fetch itself trips
            # the auth-expired sentinel.
            self._last_known_tokens = None
            self._token_label.setText("Tokens: —")
            self._token_label.setStyleSheet("")
            self._refresh_login_gate()
        else:
            # parse_failed / network / 5xx / malformed → '—' placeholder
            _log.warning("GBS.FM token fetch failed: %s", msg)
            self._token_label.setText("Tokens: —")
            self._token_label.setStyleSheet("")
        self._token_worker = None

    def _apply_token_color(self, n: Optional[int]) -> None:
        """D-T6: 0 → red, 1-3 → amber, 4+ / None → default theme color.

        setStyleSheet('') resets the foreground to the inherited theme
        palette. Verified at the existing _error_label flow (lines 349,
        956-958) which has shipped in production since Phase 60.
        """
        if n is None:
            self._token_label.setStyleSheet("")
        elif n == 0:
            self._token_label.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
        elif 1 <= n <= 3:
            self._token_label.setStyleSheet(f"color: {WARNING_COLOR_HEX};")
        else:  # n >= 4
            self._token_label.setStyleSheet("")

    # ------------------- end Phase 60.4 token counter -------------------

    def showEvent(self, event):
        # Re-check login gate every time the dialog is shown (user may have
        # imported cookies via AccountsDialog while this dialog was hidden).
        self._refresh_login_gate()
        super().showEvent(event)

    # ---------- Search ----------

    def _start_search(self) -> None:
        # Phase 60.1 / Pitfall 10: new search abandons drill-down snapshot.
        self._reset_drill_chrome()
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
        """Phase 60.1 / GBS-01e drill-down: navigate to /artist/<id>.

        Reads href from item.data(Qt.ItemDataRole.UserRole) — NOT item.text().
        Regex-validates the href shape (T-60.1-09 URL injection mitigation).

        Snapshots pre-drill state ONCE per drill session (Pitfall 8 + UI-SPEC FLAG-03):
        subsequent clicks while drilling REPLACE the drilled view but PRESERVE the
        original snapshot — Back always returns to the original search.

        Per D-07: this REPLACES the Phase 60-11 D-11a Shape 4 free-text-search fallback.
        """
        href = item.data(Qt.ItemDataRole.UserRole) or ""
        m = _ARTIST_HREF_RE.match(href)
        if not m:
            # Malformed entry — defensive; should not happen post-Phase 60-11
            # since _on_metadata_ready stores hrefs from gbs_api.search() output.
            return
        artist_id = int(m.group(1))
        artist_name = item.text()
        cookies = gbs_api.load_auth_context()
        if cookies is None:
            self._refresh_login_gate()
            return
        # Pitfall 8: snapshot is single-shot per drill session.
        if self._pre_drill_state is None:
            self._pre_drill_state = self._snapshot_pre_drill_state()
        self._kick_artist_drill_worker(artist_id, artist_name, cookies)

    def _on_album_link_activated(self, item) -> None:
        """Phase 60.1 / GBS-01e drill-down: navigate to /album/<id>.

        Mirrors _on_artist_link_activated. See that docstring for invariants.
        """
        href = item.data(Qt.ItemDataRole.UserRole) or ""
        m = _ALBUM_HREF_RE.match(href)
        if not m:
            return
        album_id = int(m.group(1))
        album_name = item.text()
        cookies = gbs_api.load_auth_context()
        if cookies is None:
            self._refresh_login_gate()
            return
        if self._pre_drill_state is None:
            self._pre_drill_state = self._snapshot_pre_drill_state()
        self._kick_album_drill_worker(album_id, album_name, cookies)

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

    def _clear_table(self, clear_panels: bool = True) -> None:
        """Clear the results table model.

        Phase 60.1: clear_panels=False is used by the drill-down render path so
        the artist/album panels remain visible during drill-down (UI-SPEC Delta 3 /
        RESEARCH §Pitfall 3). Existing call sites pass no kwarg → True → unchanged
        behavior.

        60-11 / T12: also hide artist/album panels — they re-show only when
        the next search response includes non-empty links via _on_metadata_ready.
        See ORDERING INVARIANT in _GbsSearchWorker.run(): metadata_ready emits
        AFTER finished, so this hide is always followed by the correct re-show.

        Phase 60.2 / Pitfall 1+9: clearSpans() FIRST (BEFORE removeRows) drops any
        stale section-header spans set during a prior artist drill-down so a
        subsequent search render doesn't merge its first row's columns. Order
        matters — clearSpans must reference rows the model still knows about.
        Defense-in-depth: removeRows(0, rowCount) implicitly drops spans when
        rowCount→0, but the explicit clearSpans is load-bearing when rowCount>0
        (e.g., reset between drill→back→search transitions where rows persist
        briefly).
        """
        self._results_table.clearSpans()                       # Phase 60.2 Pitfall 1+9
        self._model.removeRows(0, self._model.rowCount())
        self._submit_buttons = []
        if clear_panels and hasattr(self, "_artist_list"):
            self._artist_list.clear()
            self._artist_label.setVisible(False)
            self._artist_list.setVisible(False)
        if clear_panels and hasattr(self, "_album_list"):
            self._album_list.clear()
            self._album_label.setVisible(False)
            self._album_list.setVisible(False)

    # ---------- Phase 60.1 drill-down helpers ----------

    def _reset_drill_chrome(self) -> None:
        """Reset all drill-down chrome to pre-drill state.

        Called from _start_search (Pitfall 10 — new search abandons snapshot)
        and from _on_back_clicked (after restoring search state).
        """
        self._pre_drill_state = None
        if hasattr(self, "_back_btn"):
            self._back_btn.setVisible(False)
        if hasattr(self, "_breadcrumb_label"):
            self._breadcrumb_label.setVisible(False)
            self._breadcrumb_label.setText("")
        if hasattr(self, "_page_label"):
            self._page_label.setVisible(True)
        if hasattr(self, "_prev_btn"):
            self._prev_btn.setVisible(True)
        if hasattr(self, "_next_btn"):
            self._next_btn.setVisible(True)

    def _snapshot_pre_drill_state(self) -> dict:
        """Capture dialog state to restore on Back. Called once per drill-down session
        (Pitfall 8 — second click while drilled preserves this snapshot).
        """
        return {
            "results": list(self._results),
            "current_page": self._current_page,
            "total_pages": self._total_pages,
            "current_query": self._current_query,
            "search_version": self._search_version,
            "artist_links": [
                {"text": self._artist_list.item(i).text(),
                 "url": self._artist_list.item(i).data(Qt.ItemDataRole.UserRole) or ""}
                for i in range(self._artist_list.count())
            ],
            "album_links": [
                {"text": self._album_list.item(i).text(),
                 "url": self._album_list.item(i).data(Qt.ItemDataRole.UserRole) or ""}
                for i in range(self._album_list.count())
            ],
            "artist_panel_visible": not self._artist_list.isHidden(),
            "album_panel_visible": not self._album_list.isHidden(),
            "prev_enabled": self._prev_btn.isEnabled(),
            "next_enabled": self._next_btn.isEnabled(),
        }

    def _kick_artist_drill_worker(self, artist_id: int, artist_name: str, cookies) -> None:
        """Dispatch a _GbsArtistWorker. Mirrors _kick_search_worker shape.

        Does NOT call _clear_table() here — UI-SPEC Delta 4: table is swapped in
        the finished slot (user keeps seeing search results during the fetch).
        """
        self._hide_inline_error()
        self._progress.setVisible(True)
        # Pitfall 9 mitigation Approach A: disable _back_btn during fetch.
        self._back_btn.setEnabled(False)
        self._artist_drill_worker = _GbsArtistWorker(
            artist_id, artist_name, cookies, parent=self,
        )
        self._artist_drill_worker.finished.connect(self._on_artist_drilled)  # QA-05
        self._artist_drill_worker.error.connect(self._on_artist_drill_error)  # QA-05
        self._artist_drill_worker.start()

    def _kick_album_drill_worker(self, album_id: int, album_name: str, cookies) -> None:
        """Dispatch a _GbsAlbumWorker. Mirrors _kick_artist_drill_worker."""
        self._hide_inline_error()
        self._progress.setVisible(True)
        self._back_btn.setEnabled(False)
        self._album_drill_worker = _GbsAlbumWorker(
            album_id, album_name, cookies, parent=self,
        )
        self._album_drill_worker.finished.connect(self._on_album_drilled)  # QA-05
        self._album_drill_worker.error.connect(self._on_album_drill_error)  # QA-05
        self._album_drill_worker.start()

    def _on_artist_drilled(self, results: list) -> None:
        """Phase 60.1 / GBS-01e: artist drill-down fetch returned successfully.

        Replaces the search-results table in place (UI-SPEC Delta 4) while keeping
        the artist/album panels visible (Delta 3 + Pitfall 3). Switches the top row
        (page_label → breadcrumb_label) and the bottom row (prev/next → back_btn).
        """
        self._progress.setVisible(False)
        self._back_btn.setEnabled(True)
        artist_name = (self._artist_drill_worker.artist_name
                       if self._artist_drill_worker is not None
                       else "")
        self._results = list(results)
        # UI-SPEC Delta 4 + Pitfall 3: keep panels visible during drill-down.
        # Phase 60.2 D-01..D-03: insert per-album section-header span rows.
        self._render_results(clear_panels=False, group_by_album=True)
        # UI-SPEC Delta 1: page_label hidden, breadcrumb shown.
        self._page_label.setVisible(False)
        self._breadcrumb_label.setText(f"Viewing artist: {artist_name}")
        self._breadcrumb_label.setVisible(True)
        # UI-SPEC Delta 2: prev/next hidden, back shown.
        self._prev_btn.setVisible(False)
        self._next_btn.setVisible(False)
        self._back_btn.setVisible(True)
        # Pattern S-4: clear worker reference after settled.
        self._artist_drill_worker = None

    def _on_album_drilled(self, results: list) -> None:
        """Phase 60.1 / GBS-01e: album drill-down fetch returned successfully."""
        self._progress.setVisible(False)
        self._back_btn.setEnabled(True)
        album_name = (self._album_drill_worker.album_name
                      if self._album_drill_worker is not None
                      else "")
        self._results = list(results)
        self._render_results(clear_panels=False)
        self._page_label.setVisible(False)
        self._breadcrumb_label.setText(f"Viewing album: {album_name}")
        self._breadcrumb_label.setVisible(True)
        self._prev_btn.setVisible(False)
        self._next_btn.setVisible(False)
        self._back_btn.setVisible(True)
        self._album_drill_worker = None

    def _on_artist_drill_error(self, msg: str) -> None:
        """Phase 60.1 / GBS-01e: artist drill-down fetch failed."""
        self._progress.setVisible(False)
        self._back_btn.setEnabled(True)
        if msg == "auth_expired":
            self._toast("GBS.FM session expired — reconnect via Accounts")
            self._refresh_login_gate()
            # User can click _back_btn (now re-enabled) to retreat to search state.
        else:
            truncated = (msg[:80] + "…") if len(msg) > 80 else msg
            self._show_inline_error(f"Failed to load artist page: {truncated}")
        self._artist_drill_worker = None

    def _on_album_drill_error(self, msg: str) -> None:
        """Phase 60.1 / GBS-01e: album drill-down fetch failed."""
        self._progress.setVisible(False)
        self._back_btn.setEnabled(True)
        if msg == "auth_expired":
            self._toast("GBS.FM session expired — reconnect via Accounts")
            self._refresh_login_gate()
        else:
            truncated = (msg[:80] + "…") if len(msg) > 80 else msg
            self._show_inline_error(f"Failed to load album page: {truncated}")
        self._album_drill_worker = None

    def _on_back_clicked(self) -> None:
        """Phase 60.1 / GBS-01e: restore pre-drill state per UI-SPEC Delta 5."""
        if self._pre_drill_state is None:
            return  # defensive: not in drill mode
        state = self._pre_drill_state
        # Restore search state (results + pagination)
        self._results = list(state["results"])
        self._current_page = state["current_page"]
        self._total_pages = state["total_pages"]
        self._current_query = state["current_query"]
        # Re-render the search results table (default clear_panels=True is fine — we
        # re-populate panels next via _on_metadata_ready).
        self._render_results()
        # Re-populate panels via the same logic as _on_metadata_ready
        self._on_metadata_ready(state["artist_links"], state["album_links"])
        # Restore page label + button enabled flags
        self._page_label.setText(f"Page {self._current_page} of {self._total_pages}")
        self._prev_btn.setEnabled(state["prev_enabled"])
        self._next_btn.setEnabled(state["next_enabled"])
        # Hide drill chrome + show search chrome + clear snapshot
        self._reset_drill_chrome()
        self._hide_inline_error()

    def _render_results(self, *, clear_panels: bool = True,
                        group_by_album: bool = False) -> None:
        """Render self._results into the table model.

        Phase 60.1: drill-down render slot calls this with clear_panels=False so
        the artist/album panels remain visible during drill-down (UI-SPEC Delta 3).
        Existing callers use the default clear_panels=True (no behavior change).

        Phase 60.2 / D-01..D-03/D-11: group_by_album=True (artist drill-down only,
        per Pitfall 6) inserts span-row section headers between album groups.
        Empty-string album group renders WITHOUT a header per D-11. Existing
        callers pass the default group_by_album=False (no behavior change).
        """
        self._clear_table(clear_panels=clear_panels)
        if not self._results:
            self._show_inline_error("No results.")
            return
        self._hide_inline_error()

        if not group_by_album:
            # Original Phase 60.1 path: every row is a song row. Behavior unchanged.
            self._render_song_rows(self._results, base_idx=0, original_idx_offset=0)
            return

        # Phase 60.2 drill-view path: insert per-album section-header span rows
        # (CONTEXT.md D-01..D-03). Empty-string albums render WITHOUT a header
        # per D-11.
        groups = self._group_rows_by_album(self._results)
        next_row = 0
        original_idx = 0
        for album, rows_in_group in groups:
            if album != "":
                self._insert_album_section_header(next_row, album, len(rows_in_group))
                next_row += 1
            self._render_song_rows(
                rows_in_group,
                base_idx=next_row,
                original_idx_offset=original_idx,
            )
            next_row += len(rows_in_group)
            original_idx += len(rows_in_group)

    def _group_rows_by_album(self, results: list) -> list:
        """Phase 60.2 / D-01: group consecutive same-album rows; preserve order.

        Returns list[tuple[str, list[dict]]]. Empty-string albums form their own
        group (rendered without a header per D-11).
        """
        groups: list = []
        for row in results:
            album = str(row.get("album", ""))
            if groups and groups[-1][0] == album:
                groups[-1][1].append(row)
            else:
                groups.append((album, [row]))
        return groups

    def _insert_album_section_header(self, row: int, album: str, song_count: int) -> None:
        """Phase 60.2 / D-02/D-03: insert a span-row section header at the given
        table row index.

        Header text: f"{album} ({song_count} songs)" (D-03 verbatim — plain UTF-8).
        Bold font (Pattern S-4 — bold-only differentiation; UI-SPEC FLAG-01 binds —
        do NOT call setStyleSheet or setBackground). Non-selectable + non-editable
        but visually present (Qt.ItemFlag.ItemIsEnabled — D-02 contract).
        """
        header_text = f"{album} ({song_count} songs)"
        item = QStandardItem(header_text)            # PlainText default (T-40-04)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)     # not selectable, not editable, but enabled
        bold = QFont()
        bold.setBold(True)
        item.setFont(bold)
        # Model row needs columnCount cells; populate cols 1..N-1 with empty placeholders
        # so the model row has the correct shape; setSpan then visually merges them.
        placeholders = [QStandardItem("") for _ in range(self._model.columnCount() - 1)]
        for ph in placeholders:
            ph.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._model.appendRow([item, *placeholders])
        self._results_table.setSpan(row, 0, 1, self._model.columnCount())

    def _render_song_rows(self, rows: list, *, base_idx: int,
                          original_idx_offset: int = 0) -> None:
        """Phase 60.2 / Pitfall 3: append `rows` as song rows starting at table-row
        index `base_idx`.

        Add! button slot uses song-list index `original_idx_offset + i` (NOT
        table-row index) so _on_submit_row(idx) reads self._results[idx] correctly
        when section-header span rows shift table rows.
        """
        for i, result in enumerate(rows):
            artist = QStandardItem(str(result.get("artist", "")))   # PlainText (T-40-04)
            title = QStandardItem(str(result.get("title", "")))
            duration = QStandardItem(str(result.get("duration", "")))
            placeholder = QStandardItem("")
            self._model.appendRow([artist, title, duration, placeholder])
            btn = QPushButton("Add!", self._results_table)
            # Pitfall 3: pass song-list index (original_idx_offset + i), NOT
            # table-row index (base_idx + i). _on_submit_row reads self._results[idx]
            # which remains song-list-indexed.
            btn.clicked.connect(self._make_submit_slot(original_idx_offset + i))  # QA-05
            self._submit_buttons.append(btn)
            self._results_table.setIndexWidget(
                self._model.index(base_idx + i, _COL_ADD), btn,
            )

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
            # === Phase 60.4 D-T1 + D-T3: optimistic decrement + server-confirm refetch ===
            # Pitfall B: call BOTH setText AND _apply_token_color so color tier
            # follows the displayed integer across the 4→3 (default→amber) and
            # 1→0 (amber→red) boundaries. Pitfall A's request-id guard ensures
            # the refetch result discards if a faster second submit kicks again.
            if self._last_known_tokens is not None:
                self._last_known_tokens = max(0, self._last_known_tokens - 1)
                self._token_label.setText(f"Tokens: {self._last_known_tokens}")
                self._apply_token_color(self._last_known_tokens)
            cookies = gbs_api.load_auth_context()
            if cookies is not None:
                self._kick_token_worker(cookies)
            # ============================================================================
        self._submit_worker = None

    def _on_submit_error(self, msg: str, row_idx: int) -> None:
        # HIGH 5 fix: discard if a re-search has invalidated row_idx.
        # Same semantics as _on_submit_finished: only discard when sender is a
        # live worker with a mismatched search_version.
        worker = self.sender()
        if worker is not None and getattr(worker, "search_version", -1) != self._search_version:
            return
        if msg == "auth_expired":
            # === Phase 60.4 D-T8 + Pitfall C: flip token label BEFORE _refresh_login_gate ===
            # Order is load-bearing: the label stamp + style clear + state nul
            # MUST land before _refresh_login_gate because the gate's logged-out
            # branch hides the label via setVisible(False) — pre-gate stamping
            # gives a cleaner momentary "Tokens: —" before the hide.
            self._last_known_tokens = None
            self._token_label.setText("Tokens: —")
            self._token_label.setStyleSheet("")
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
