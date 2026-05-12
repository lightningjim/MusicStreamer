"""Phase 71 / Plan 71-04: AddSiblingDialog — two-step picker modal.

Opened by the "+ Add sibling" button in EditStationDialog (Plan 71-03). Lets
the user pick a station to link as a manual sibling of the currently-edited
station, in two steps:

  1. Provider QComboBox (defaults to the editing station's provider — D-12).
  2. Station QListWidget filtered to the selected provider, with a live
     case-insensitive search filter on the station name.

Excludes from the picker list:
  - the editing station itself (CONTEXT D-13);
  - stations already auto-detected as AA siblings (RESEARCH Pitfall 4);
  - stations already manually linked (RESEARCH Pitfall 4 / UI-SPEC line 269).

CTA labels (CONTEXT D-13 / UI-SPEC line 261):
  - Ok button: "Link Station" (not "OK").
  - Cancel button: "Don't Link" (not "Cancel").

The dialog is synchronous — the station list is already in memory, so unlike
DiscoveryDialog there is no QThread / QProgressBar machinery. Modal QDialog
structure is reused from DiscoveryDialog without the network-fetch widgets.

Security: station names appear as plain text in QListWidgetItem (no RichText,
no HTML). T-40-04 plain-text invariant preserved — this file introduces zero
Qt.RichText labels.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from musicstreamer.repo import Repo
from musicstreamer.url_helpers import find_aa_siblings


class AddSiblingDialog(QDialog):
    """Two-step picker modal for manual sibling linking (Phase 71 / D-11..D-13).

    Args:
        station: The Station being edited; its provider pre-selects the combo,
            and its id drives the exclusion-set computation.
        repo: Repo instance providing list_providers / list_stations /
            list_sibling_links / add_sibling_link.
        parent: Optional parent widget for modal stacking.
        live_url: Optional override for the editing station's current URL.
            When the dialog is launched from EditStationDialog the user may
            have edited the URL field without saving (RESEARCH Pitfall 4);
            EditStationDialog passes its url_edit.text().strip() so the AA
            exclusion set reflects the in-progress URL rather than the stale
            persisted streams[0].url. When omitted the dialog falls back to
            station.streams[0].url for backwards compatibility (CR-03).

    Public read-only attribute after exec() == QDialog.Accepted:
        _linked_station_name: str — the display name of the station the user
            linked; consumed by the caller (EditStationDialog) to fire its
            "Linked to {name}" toast.
    """

    def __init__(
        self,
        station,
        repo: Repo,
        parent: Optional[QWidget] = None,
        live_url: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self._current_station = station
        self._current_station_id = station.id
        self._repo = repo
        # CR-03: live URL takes precedence over station.streams[0].url. None
        # means "use stale fallback"; "" (empty string) is a valid live value
        # meaning "user cleared the URL field" and is preserved as-is.
        self._live_url: Optional[str] = live_url
        # Caller reads this after exec() == Accepted for the toast (UI-SPEC line 285).
        self._linked_station_name: str = ""

        self.setWindowTitle("Add Sibling Station")
        self.setMinimumSize(480, 360)
        self.setModal(True)

        self._build_ui()
        self._repopulate_station_list()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        # Provider + Search rows in a QFormLayout (UI-SPEC line 244).
        form = QFormLayout()
        form.setSpacing(8)
        form.setContentsMargins(0, 0, 0, 0)

        # Provider combo — defaults to editing station's provider (CONTEXT D-12).
        self._provider_combo = QComboBox(self)
        for p in self._repo.list_providers():
            self._provider_combo.addItem(p.name, p.id)
        # Default selection: editing station's provider. When the station has
        # no provider_name, leave the combo on its first item (we do NOT add
        # a synthetic "(no provider)" entry — RESEARCH Open Decision 1 was
        # not resolved with a definitive "include"; defaulting to the first
        # available provider keeps the UI simple). Stations with no provider
        # are still reachable by the user switching the combo manually.
        if self._current_station.provider_name:
            idx = self._provider_combo.findText(self._current_station.provider_name)
            if idx >= 0:
                self._provider_combo.setCurrentIndex(idx)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("Provider:", self._provider_combo)

        # Search filter — live case-insensitive substring filter on station.name.
        # Placeholder uses U+2026 HORIZONTAL ELLIPSIS (not three ASCII dots) per
        # UI-SPEC line 126.
        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText("Filter stations…")
        self._search_edit.textChanged.connect(self._on_search_changed)
        form.addRow("Station:", self._search_edit)

        root.addLayout(form)

        # Station list — single-select QListWidget (RESEARCH Q4: chosen over
        # QListView + QSortFilterProxyModel — in-memory list of 50-200 items).
        self._station_list = QListWidget(self)
        self._station_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._station_list.itemSelectionChanged.connect(self._on_selection_changed)
        # WR-07: itemDoubleClicked emits a QListWidgetItem arg; accepted emits
        # zero args. Wiring both to a single slot with *args was fragile —
        # split into named slots that delegate to a shared helper.
        self._station_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        root.addWidget(self._station_list, 1)

        # Button box — labels overridden per UI-SPEC line 261 / CONTEXT D-13.
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self,
        )
        ok_btn = self._button_box.button(QDialogButtonBox.Ok)
        cancel_btn = self._button_box.button(QDialogButtonBox.Cancel)
        ok_btn.setText("Link Station")
        cancel_btn.setText("Don't Link")
        ok_btn.setEnabled(False)
        ok_btn.setDefault(True)
        ok_btn.setAutoDefault(True)
        # WR-07: accepted() emits zero args — wire to a zero-arg slot.
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)
        root.addWidget(self._button_box)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_provider_changed(self, index: int) -> None:  # noqa: ARG002
        """Provider changed — clear search, repopulate list, disable Ok."""
        # Clear search text without re-triggering _on_search_changed (which
        # would cause a redundant _repopulate_station_list call).
        self._search_edit.blockSignals(True)
        try:
            self._search_edit.setText("")
        finally:
            self._search_edit.blockSignals(False)
        self._repopulate_station_list()

    def _on_search_changed(self, text: str) -> None:  # noqa: ARG002
        """Search text changed — rebuild filtered list."""
        self._repopulate_station_list()

    def _on_selection_changed(self) -> None:
        """Enable Ok iff current item is selectable (not the empty-state row)."""
        item = self._station_list.currentItem()
        enabled = item is not None and bool(item.flags() & Qt.ItemIsSelectable)
        self._button_box.button(QDialogButtonBox.Ok).setEnabled(enabled)

    def _on_accept(self) -> None:
        """QDialogButtonBox.accepted slot — zero-arg.

        Persist the selected link via Repo.add_sibling_link and close the
        dialog. WR-07: split out from the variadic *args slot — itemDoubleClicked
        now routes through _on_item_double_clicked which delegates here.
        """
        self._accept_selected()

    def _on_item_double_clicked(self, item) -> None:
        """QListWidget.itemDoubleClicked slot — receives the clicked item.

        The item argument is unused — _accept_selected reads the currentItem
        which is already set by the click that initiated the double-click.
        Keeping the parameter (rather than discarding via *_args) documents
        the signal shape explicitly per WR-07.
        """
        del item  # documented but unused; currentItem is the source of truth
        self._accept_selected()

    def _accept_selected(self) -> None:
        """Shared helper: validate selection, persist, accept the dialog."""
        item = self._station_list.currentItem()
        if item is None or not bool(item.flags() & Qt.ItemIsSelectable):
            return
        station_id = item.data(Qt.UserRole)
        if station_id is None:
            return
        self._repo.add_sibling_link(self._current_station_id, int(station_id))
        self._linked_station_name = item.text()
        self.accept()

    # ------------------------------------------------------------------
    # List population
    # ------------------------------------------------------------------

    def _repopulate_station_list(self) -> None:
        """Rebuild _station_list from the current provider + search filter.

        Exclusion rules (RESEARCH Pitfall 4 / UI-SPEC line 269):
          - self._current_station_id (the editing station — CONTEXT D-13);
          - AA auto-detected siblings (would already show in 'Also on:');
          - Repo.list_sibling_links(current) — manually linked already.

        Empty-state copy distinguishes:
          - "All stations in this provider are already linked." — provider has
            other stations but they're all excluded.
          - "No other stations found for this provider." — provider has no
            stations other than self at all.
        """
        self._station_list.clear()
        # _on_selection_changed will re-disable Ok when there's no selection,
        # but clearing the list may not fire that signal in all Qt versions,
        # so disable defensively here.
        self._button_box.button(QDialogButtonBox.Ok).setEnabled(False)

        all_stations = self._repo.list_stations()

        # CR-03: prefer the live URL passed in from EditStationDialog (the
        # in-progress url_edit.text()), falling back to the saved
        # streams[0].url only when no live URL was provided. An explicit
        # empty-string live_url is honored (user cleared the field) — only
        # `None` triggers the fallback. Defensively allow an empty URL for
        # new/streamless stations.
        if self._live_url is not None:
            current_url = self._live_url
        elif self._current_station.streams:
            current_url = self._current_station.streams[0].url or ""
        else:
            current_url = ""

        # Build exclusion ID set (RESEARCH Pitfall 4).
        excluded: set[int] = {self._current_station_id}
        for _, sid, _ in find_aa_siblings(
            stations=all_stations,
            current_station_id=self._current_station_id,
            current_first_url=current_url,
        ):
            excluded.add(sid)
        for sid in self._repo.list_sibling_links(self._current_station_id):
            excluded.add(sid)

        # WR-03: filter by provider_id (currentData), not by display name
        # (currentText). Today providers.name is UNIQUE so the two would
        # agree, but keying on the integer id is the robust shape — it
        # survives a provider rename and is one fewer string comparison per
        # candidate. currentData() returns None when the combo is empty;
        # we fall through to empty results in that case.
        provider_id = self._provider_combo.currentData()

        # Provider candidates: stations matching the selected provider id,
        # not equal to self. Used for empty-state copy disambiguation.
        provider_candidates = [
            st for st in all_stations
            if st.id != self._current_station_id
            and st.provider_id == provider_id
        ]

        # Apply exclusion set.
        eligible = [st for st in provider_candidates if st.id not in excluded]

        # Apply case-insensitive substring filter (str.lower(); no debounce,
        # no QSortFilterProxyModel — RESEARCH Q4).
        search_text = self._search_edit.text().strip().lower()
        if search_text:
            eligible = [st for st in eligible if search_text in (st.name or "").lower()]

        if not eligible:
            if not provider_candidates:
                copy = "No other stations found for this provider."
            else:
                copy = "All stations in this provider are already linked."
            placeholder = QListWidgetItem(copy)
            placeholder.setFlags(Qt.NoItemFlags)
            self._station_list.addItem(placeholder)
            return

        # Sort alphabetically by name (casefold) for visual stability.
        for st in sorted(eligible, key=lambda s: (s.name or "").casefold()):
            item = QListWidgetItem(st.name)
            item.setData(Qt.UserRole, st.id)
            self._station_list.addItem(item)
