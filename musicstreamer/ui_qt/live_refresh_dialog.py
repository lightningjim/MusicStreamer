"""Phase 96-04: LiveRefreshDialog — manual refresh of live-stream URLs from channel.

Dialog + worker + pure apply helpers for the provider-level "Refresh live streams"
workflow (D-04..D-10).

Constructor:
    LiveRefreshDialog(repo, provider_id, provider_name, channel_scan_url, *,
                      node_runtime=None, toast_callback=None, parent=None)

Signals:
    refresh_complete() — emitted after successful Apply.

Threading discipline (mirrors import_dialog.py):
    All blocking I/O (yt-dlp channel scan) runs on _LiveRefreshScanWorker (QThread).
    run() MUST NOT touch any widget.
    Results marshalled to main thread exclusively via queued Signal connections.
    node_runtime is stored in __init__ and forwarded to scan_playlist (D-09 /
    MEMORY.md yt-dlp-callsites-need-resolved-node-runtime landmine).

Security:
    D-10: DROP defaults unchecked; delete_station fires ONLY on explicit tick.
    Pitfall 6: apply path NEVER calls station_exists_by_url.
    Pitfall 5: update_stream preserves ALL non-URL fields from existing stream.
    T-96-10: scan title surfaced as-is; user reviews before Apply commits.
    T-96-11: fully manual map; no auto-apply by anchor match (D-05).
"""
from __future__ import annotations

import difflib
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from musicstreamer import yt_import
from musicstreamer.runtime_check import NodeRuntime
from musicstreamer.repo import Repo
from musicstreamer.models import Station
from musicstreamer.ui_qt._theme import ERROR_COLOR_HEX


# ---------------------------------------------------------------------------
# Worker thread (mirrors _YtScanWorker from import_dialog.py:75-101)
# ---------------------------------------------------------------------------


class _LiveRefreshScanWorker(QThread):
    """Phase 96 D-09: off-UI-thread channel scan.

    Mirrors _YtScanWorker exactly. The node_runtime kwarg is CRITICAL —
    omitting it causes silent failures under .desktop launchers with a minimal
    PATH that cannot locate the Node.js binary (MEMORY.md landmine).
    """

    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        url: str,
        toast_callback: Optional[Callable[[str], None]] = None,
        *,
        node_runtime: "NodeRuntime | None" = None,
        parent=None,
    ):
        super().__init__(parent)
        self._url = url
        self._toast = toast_callback
        self._node_runtime = node_runtime  # CRITICAL: must thread through; see Pitfall 3

    def run(self):
        """Blocking scan — runs on worker thread. MUST NOT touch any widget."""
        try:
            results = yt_import.scan_playlist(
                self._url,
                toast_callback=self._toast,
                node_runtime=self._node_runtime,
            )
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Pure helpers (testable without a live QApplication)
# ---------------------------------------------------------------------------


def _build_row_suggestions(station: "Station", scan_results: list) -> list:
    """Phase 96 D-05: pre-order scan results by title-anchor similarity.

    Returns ALL scan_results, with the anchor-closest match sorted first.
    NEVER auto-selects or auto-stages a mapping — the return value is a
    plain list; no staged change is applied (D-05 no-auto-apply invariant).

    Args:
        station: Station with live_url_title_anchor for hint ordering.
        scan_results: List of dicts from scan_playlist (keys: title, url, provider).

    Returns:
        List of scan result dicts, anchor-closest first, rest in original order.
    """
    if not scan_results:
        return []

    anchor = (station.live_url_title_anchor or "") if station is not None else ""

    if not anchor:
        # No anchor — return results as-is
        return list(scan_results)

    # Score each result by title similarity to anchor (SequenceMatcher ratio)
    def _similarity(entry: dict) -> float:
        title = entry.get("title", "")
        return difflib.SequenceMatcher(None, anchor.lower(), title.lower()).ratio()

    scores = [(_similarity(e), i, e) for i, e in enumerate(scan_results)]
    # Sort by similarity descending; stable tie-break by original index ascending
    scores.sort(key=lambda x: (-x[0], x[1]))
    return [e for _, _, e in scores]


def build_row_data(
    action: str,
    *,
    scan_result: Optional[dict] = None,
    station: Optional[Station] = None,
) -> dict:
    """Phase 96 D-08: build a row data dict with correct name pre-population.

    ADD rows: name defaults to scan result title (the new stream's title).
    REMAP/REPLACE rows: name defaults to existing station name (preserve identity).

    Pure function — no widget construction.
    """
    scan_result = scan_result or {}
    name: str
    if action == "add":
        name = scan_result.get("title", "")
    else:
        # remap or replace: keep existing station name
        name = (station.name if station is not None else "") or scan_result.get("title", "")

    return {
        "action": action,
        "name": name,
        "scan_result": scan_result,
        "station": station,
    }


def default_check_state(action: str) -> bool:
    """Phase 96 D-10: return the default checked state for a row action.

    REMAP rows are checked by default (resolving an existing flagged station).
    DROP and ADD rows are unchecked by default (conservative — explicit opt-in required).
    """
    return action == "remap"


def apply_refresh(repo: Repo, staged_changes: list) -> None:
    """Phase 96 D-06/D-07/D-10: apply staged refresh changes to the repo.

    Pure function (no Qt; testable without a live event loop).

    Each staged-change record is a dict with keys:
        action: "remap" | "drop" | "add"

        For "remap":
            station_id: int
            stream_id: int       (primary stream to update in place)
            scan_result: dict    (keys: title, url, provider)

        For "drop":
            station_id: int

        For "add":
            name: str
            provider_name: str
            scan_result: dict    (keys: title, url, provider)

    Security:
        NEVER calls station_exists_by_url (Pitfall 6 — bypasses dedup path).
        Preserves ALL non-URL stream fields on remap (Pitfall 5 metadata loss).
        Fires delete_station ONLY for explicit "drop" records (T-96-09 / D-10).
        Empty staged_changes produces ZERO repo mutations (D-10 empty-apply guard).
    """
    if not staged_changes:
        return  # D-10 empty-apply guard: zero mutations

    # WR-03 duplicate-target guard: remap/add rows each point a station at a
    # chosen live stream. Because every combo defaults to the anchor-closest
    # match, a careless Apply could silently collapse several stations onto the
    # same URL. Fail closed BEFORE any mutation so the user re-maps instead.
    target_urls = [
        change["scan_result"].get("url")
        for change in staged_changes
        if change.get("action") in ("remap", "add")
        and isinstance(change.get("scan_result"), dict)
    ]
    target_urls = [url for url in target_urls if url]
    dupes = sorted({url for url in target_urls if target_urls.count(url) > 1})
    if dupes:
        raise ValueError(
            "Multiple stations are mapped to the same live stream "
            f"({', '.join(dupes)}). Each station must map to a distinct stream."
        )

    for change in staged_changes:
        action = change.get("action")

        if action == "remap":
            station_id = change["station_id"]
            stream_id = change["stream_id"]
            scan_result = change["scan_result"]
            new_url = scan_result["url"]
            new_title = scan_result.get("title", "")

            # Fetch primary stream to preserve ALL non-URL fields (Pitfall 5)
            streams = repo.list_streams(station_id)
            primary = next(
                (s for s in streams if s.id == stream_id),
                streams[0] if streams else None,
            )
            if primary is None:
                continue  # defensive: no stream to update

            # Update URL in-place, preserving label/quality/position/stream_type/codec/bitrate
            repo.update_stream(
                primary.id,
                new_url,
                primary.label,
                primary.quality,
                primary.position,
                primary.stream_type,
                primary.codec,
                bitrate_kbps=primary.bitrate_kbps,
                sample_rate_hz=primary.sample_rate_hz,
                bit_depth=primary.bit_depth,
            )
            # D-06: update title anchor to new scan result title
            repo.set_live_url_title_anchor(station_id, new_title)

        elif action == "drop":
            station_id = change["station_id"]
            repo.delete_station(station_id)  # D-07: explicit drop only

        elif action == "add":
            scan_result = change["scan_result"]
            name = change.get("name") or scan_result.get("title", "")
            url = scan_result["url"]
            provider_name = change.get("provider_name", "")
            new_title = scan_result.get("title", "")

            # D-07: insert new station (never goes through station_exists_by_url — Pitfall 6)
            new_id = repo.insert_station(name, url, provider_name, "")
            # Set flag so the new station is itself refresh-eligible (D-07)
            repo.set_live_url_syncs_from_channel(new_id, True)
            repo.set_live_url_title_anchor(new_id, new_title)


# ---------------------------------------------------------------------------
# Review dialog
# ---------------------------------------------------------------------------


class _RowWidget(QWidget):
    """One row in the review UI — represents a single flagged station or an ADD entry."""

    def __init__(
        self,
        action: str,
        station: Optional[Station],
        scan_results: list,
        provider_name: str,
        parent=None,
    ):
        super().__init__(parent)
        self._action = action
        self._station = station
        self._provider_name = provider_name

        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(4, 4, 4, 4)

        # Check box (controls whether this row is staged for apply)
        self._check = QCheckBox()
        self._check.setChecked(default_check_state(action))
        row_layout.addWidget(self._check)

        # Left: action label + station/anchor info
        left = QVBoxLayout()
        action_label_text = {
            "remap": "REMAP",
            "replace": "REPLACE",
            "drop": "DROP",
            "add": "ADD",
        }.get(action, action.upper())
        action_label = QLabel(f"<b>{action_label_text}</b>")
        action_label.setFixedWidth(60)
        left.addWidget(action_label)

        if station is not None:
            # T-39-01: station metadata and scan-derived anchors are untrusted —
            # force Qt.PlainText so a title like "<img src=http://attacker/x>"
            # cannot trigger rich-text / remote-resource injection (CR-01).
            station_label = QLabel(station.name)
            station_label.setTextFormat(Qt.PlainText)
            station_label.setWordWrap(True)
            left.addWidget(station_label)
            if station.live_url_title_anchor:
                anchor_label = QLabel(f"Anchor: {station.live_url_title_anchor}")
                anchor_label.setTextFormat(Qt.PlainText)
                anchor_label.setStyleSheet("font-style: italic;")
                anchor_label.setWordWrap(True)
                left.addWidget(anchor_label)
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setFixedWidth(200)
        row_layout.addWidget(left_widget)

        # Middle: name edit field
        self._name_edit = QLineEdit()
        row_data = build_row_data(action, scan_result={}, station=station)
        self._name_edit.setText(row_data["name"])
        name_container = QVBoxLayout()
        name_container.addWidget(QLabel("Name:"))
        name_container.addWidget(self._name_edit)
        name_widget = QWidget()
        name_widget.setLayout(name_container)
        name_widget.setFixedWidth(180)
        row_layout.addWidget(name_widget)

        # Right: "map to currently-live" combo (not shown for DROP rows)
        self._combo: Optional[QComboBox] = None
        if action != "drop":
            self._combo = QComboBox()
            self._combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            # Pre-order suggestions by anchor similarity (D-05)
            ordered = _build_row_suggestions(station, scan_results)
            for entry in ordered:
                self._combo.addItem(entry.get("title", ""), userData=entry)
            if self._combo.count() == 0:
                self._combo.addItem("(no live streams found)", userData=None)
            combo_container = QVBoxLayout()
            combo_container.addWidget(QLabel("Map to currently-live:"))
            combo_container.addWidget(self._combo)
            combo_widget = QWidget()
            combo_widget.setLayout(combo_container)
            row_layout.addWidget(combo_widget)

        # For ADD rows, update name when selection changes
        if action == "add" and self._combo is not None:
            self._combo.currentIndexChanged.connect(self._on_add_selection_changed)

    def _on_add_selection_changed(self, _index: int) -> None:
        """For ADD rows, update name field from selected scan result title (D-08)."""
        if self._combo is None:
            return
        entry = self._combo.currentData(Qt.UserRole)
        if entry and isinstance(entry, dict) and self._name_edit.text() == "":
            self._name_edit.setText(entry.get("title", ""))

    def is_staged(self) -> bool:
        return self._check.isChecked()

    def build_staged_change(self, station_id: Optional[int] = None) -> Optional[dict]:
        """Build a staged-change record for apply_refresh, or None if unchecked/invalid."""
        if not self.is_staged():
            return None

        name = self._name_edit.text().strip()

        if self._action == "drop":
            sid = station_id or (self._station.id if self._station else None)
            if sid is None:
                return None
            return {"action": "drop", "station_id": sid}

        # remap / replace / add — need a selected scan result
        selected_entry: Optional[dict] = None
        if self._combo is not None:
            selected_entry = self._combo.currentData(Qt.UserRole)

        if self._action == "add":
            if not selected_entry:
                return None
            return {
                "action": "add",
                "name": name or selected_entry.get("title", ""),
                "scan_result": selected_entry,
                "provider_name": self._provider_name,
            }

        # remap / replace
        sid = station_id or (self._station.id if self._station else None)
        if sid is None or not selected_entry:
            return None
        # Find primary stream id (position==1); will be resolved in apply_refresh
        primary_stream_id: Optional[int] = None
        if self._station is not None and hasattr(self._station, "streams"):
            for s in self._station.streams:
                if s.position == 1:
                    primary_stream_id = s.id
                    break
            if primary_stream_id is None and self._station.streams:
                primary_stream_id = self._station.streams[0].id
        return {
            "action": "remap",
            "station_id": sid,
            "stream_id": primary_stream_id,
            "scan_result": selected_entry,
        }


class LiveRefreshDialog(QDialog):
    """Phase 96 D-04..D-10: Review-and-confirm live-stream URL refresh dialog.

    Opens with all flagged stations for the provider loaded in the left column.
    Kicks off a _LiveRefreshScanWorker to enumerate currently-live streams on
    the provider's YouTube channel.  The user maps each flagged station to a
    live stream (or drops/adds as needed) and clicks Apply.

    Constructor:
        LiveRefreshDialog(repo, provider_id, provider_name, channel_scan_url, *,
                          node_runtime=None, toast_callback=None, parent=None)

    Signals:
        refresh_complete — emitted after successful Apply (for station-list refresh).
    """

    refresh_complete = Signal()

    def __init__(
        self,
        repo: Repo,
        provider_id: int,
        provider_name: str,
        channel_scan_url: str,
        *,
        node_runtime: "NodeRuntime | None" = None,
        toast_callback: Optional[Callable[[str], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._repo = repo
        self._provider_id = provider_id
        self._provider_name = provider_name
        self._channel_scan_url = channel_scan_url
        self._node_runtime = node_runtime
        self._toast = toast_callback
        self._scan_worker: Optional[_LiveRefreshScanWorker] = None
        self._scan_results: list = []
        self._row_widgets: List[_RowWidget] = []

        self.setWindowTitle(f"Refresh Live Streams — {provider_name}")
        self.setMinimumSize(760, 520)
        self.setModal(True)

        # Root layout
        root = QVBoxLayout(self)

        # Status label (scan progress / errors)
        self._status_label = QLabel("Scanning channel for currently-live streams…")
        root.addWidget(self._status_label)

        # Indeterminate progress bar (visible during scan)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setVisible(True)
        root.addWidget(self._progress)

        # Scroll area for row widgets (populated after scan completes)
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setAlignment(Qt.AlignTop)
        self._scroll_area.setWidget(self._rows_container)
        root.addWidget(self._scroll_area)

        # Button box
        self._button_box = QDialogButtonBox()
        self._apply_btn = self._button_box.addButton(
            "Apply", QDialogButtonBox.AcceptRole
        )
        self._apply_btn.setEnabled(False)
        self._cancel_btn = self._button_box.addButton(QDialogButtonBox.Cancel)
        self._button_box.accepted.connect(self._on_apply)
        self._button_box.rejected.connect(self.reject)
        root.addWidget(self._button_box)

        # Load flagged stations and kick off scan
        self._flagged_stations: List[Station] = (
            repo.list_flagged_stations_for_provider(provider_id)
        )
        self._start_scan()

    # ------------------------------------------------------------------
    # Expose pure helpers as class attributes (required by tests)
    # ------------------------------------------------------------------

    _build_row_suggestions = staticmethod(_build_row_suggestions)

    # ------------------------------------------------------------------
    # Scan lifecycle
    # ------------------------------------------------------------------

    def _start_scan(self) -> None:
        """Kick off the channel scan on a worker thread (D-09)."""
        if not self._flagged_stations:
            self._progress.setVisible(False)
            self._status_label.setText(
                "No stations marked for live URL re-sync — "
                "enable the flag via Edit Station."
            )
            return

        self._scan_worker = _LiveRefreshScanWorker(
            self._channel_scan_url,
            toast_callback=self._toast,
            node_runtime=self._node_runtime,
            parent=self,
        )
        self._scan_worker.finished.connect(
            self._on_scan_complete, Qt.QueuedConnection
        )
        self._scan_worker.error.connect(
            self._on_scan_error, Qt.QueuedConnection
        )
        self._scan_worker.start()

    def _on_scan_complete(self, results: list) -> None:
        """Main-thread handler — called via queued Signal after worker finishes."""
        self._progress.setVisible(False)
        self._scan_results = results

        if not results:
            self._status_label.setText(
                "No live streams found in channel. "
                "You can still drop flagged stations below."
            )
            # Show DROP rows for each flagged station even with no live results
        else:
            count = len(results)
            self._status_label.setText(
                f"Found {count} currently-live stream{'s' if count != 1 else ''} on channel."
            )

        self._populate_rows(results)
        self._apply_btn.setEnabled(True)

    def _on_scan_error(self, msg: str) -> None:
        """Main-thread handler — scan failed."""
        self._progress.setVisible(False)
        self._status_label.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
        self._status_label.setText(f"Scan failed: {msg}")

    # ------------------------------------------------------------------
    # Row population
    # ------------------------------------------------------------------

    def _populate_rows(self, scan_results: list) -> None:
        """Populate the review UI with per-flagged-station rows (D-05/D-08)."""
        self._row_widgets.clear()
        # Clear any existing widgets
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._flagged_stations and not scan_results:
            return

        # One REMAP/REPLACE row per flagged station
        for station in self._flagged_stations:
            row = _RowWidget(
                "remap",
                station,
                scan_results,
                self._provider_name,
                parent=self._rows_container,
            )
            self._rows_layout.addWidget(row)
            self._row_widgets.append(row)

        # Separator label for ADD section
        if scan_results:
            add_label = QLabel(
                "<b>Add a currently-live stream as a new station (unchecked by default):</b>"
            )
            add_label.setWordWrap(True)
            self._rows_layout.addWidget(add_label)

            # One ADD row per scan result not already matched to a flagged station
            for entry in scan_results:
                row = _RowWidget(
                    "add",
                    None,
                    [entry],
                    self._provider_name,
                    parent=self._rows_container,
                )
                self._rows_layout.addWidget(row)
                self._row_widgets.append(row)

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def _on_apply(self) -> None:
        """Collect staged rows → call pure apply helper → emit refresh_complete."""
        staged: list = []
        for row in self._row_widgets:
            station_id = row._station.id if row._station else None
            change = row.build_staged_change(station_id=station_id)
            if change is not None:
                staged.append(change)

        try:
            apply_refresh(self._repo, staged)
        except Exception as exc:
            if self._toast:
                self._toast(f"Refresh failed: {exc}")
            self._status_label.setStyleSheet(f"color: {ERROR_COLOR_HEX};")
            self._status_label.setText(f"Apply failed: {exc}")
            return

        if self._toast:
            if staged:
                self._toast(f"Refresh applied — {len(staged)} change(s) committed.")
            else:
                self._toast("No changes staged — nothing to apply.")

        self.refresh_complete.emit()
        self.accept()
