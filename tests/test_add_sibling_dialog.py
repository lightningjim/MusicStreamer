"""Phase 71 / Wave 0 RED contract: AddSiblingDialog picker behavior tests.

Modeled on tests/test_discovery_dialog.py (FakeRepo + qtbot dialog fixture)
and tests/test_edit_station_dialog.py (MagicMock-style repo + dialog fixture).

Asserts the contract Plan 71-04 will implement:

- class AddSiblingDialog(QDialog) at musicstreamer.ui_qt.add_sibling_dialog
- Constructor: AddSiblingDialog(station, repo, parent=None)
- Public attribute after exec(): dialog._linked_station_name: str
- Children:
    self._provider_combo: QComboBox       (defaults to editing station's provider)
    self._search_edit: QLineEdit
    self._station_list: QListWidget
    self._button_box: QDialogButtonBox    (Ok="Link Station", Cancel="Don't Link")
- Behavior:
    * Self excluded from list (CONTEXT D-13).
    * Already-linked siblings excluded (UI-SPEC line 269 / RESEARCH Pitfall 4).
    * Ok button disabled until selection (UI-SPEC line 261).
    * Accept calls Repo.add_sibling_link(current_station_id, selected_id) (D-13).
    * Switching provider repopulates _station_list (D-12).

Per project convention the module-level
`from musicstreamer.ui_qt.add_sibling_dialog import AddSiblingDialog` import
WILL FAIL at collection time today — that IS the RED state.
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QListWidget

from musicstreamer.models import Provider, Station, StationStream
from musicstreamer.ui_qt.add_sibling_dialog import AddSiblingDialog


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakeRepo:
    """Mirrors tests/test_discovery_dialog.py FakeRepo + extends with sibling APIs.

    Tests configure self._providers / self._stations / self._sibling_links
    directly to drive picker population.
    """

    def __init__(self) -> None:
        self.add_sibling_link_calls = []
        self._providers = []
        self._stations = []
        self._sibling_links = []

    def list_providers(self):
        return self._providers

    def list_stations(self):
        return self._stations

    def list_sibling_links(self, station_id):
        return list(self._sibling_links)

    def add_sibling_link(self, a_id, b_id):
        self.add_sibling_link_calls.append((a_id, b_id))


def _mk_station(id_, name, provider_id=None, provider_name=None,
                url="http://example.com/stream"):
    return Station(
        id=id_,
        name=name,
        provider_id=provider_id,
        provider_name=provider_name,
        tags="",
        station_art_path=None,
        album_fallback_path=None,
        streams=[StationStream(id=id_ * 10, station_id=id_, url=url, position=1)],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo():
    r = FakeRepo()
    # Two providers; "ProviderA" is the editing station's provider.
    r._providers = [Provider(1, "ProviderA"), Provider(2, "ProviderB")]
    return r


@pytest.fixture
def station():
    """The station being edited (id=1, on ProviderA)."""
    return _mk_station(1, "Test Station", provider_id=1, provider_name="ProviderA")


@pytest.fixture
def dialog(qtbot, station, repo):
    d = AddSiblingDialog(station, repo, parent=None)
    qtbot.addWidget(d)
    return d


# ---------------------------------------------------------------------------
# Tests — copy contract (UI-SPEC lines 234, 261 / CONTEXT D-13)
# ---------------------------------------------------------------------------


def test_dialog_window_title_is_add_sibling_station(dialog):
    """UI-SPEC line 234: window title is the exact string 'Add Sibling Station'."""
    assert dialog.windowTitle() == "Add Sibling Station"


def test_ok_button_label_is_link_station(dialog):
    """UI-SPEC line 261 / CONTEXT D-13: Ok button labeled 'Link Station', not 'OK'."""
    assert dialog._button_box.button(QDialogButtonBox.Ok).text() == "Link Station"


def test_dismiss_button_label_is_dont_link(dialog):
    """UI-SPEC line 261: Cancel button labeled "Don't Link"."""
    assert dialog._button_box.button(QDialogButtonBox.Cancel).text() == "Don't Link"


# ---------------------------------------------------------------------------
# Tests — provider combo behavior (CONTEXT D-12)
# ---------------------------------------------------------------------------


def test_provider_combo_defaults_to_current_station_provider(dialog):
    """CONTEXT D-12: provider combo defaults to the editing station's provider."""
    assert dialog._provider_combo.currentText() == "ProviderA"


def test_provider_switch_reloads_station_list(qtbot, station, repo):
    """CONTEXT D-12: changing the combo selection repopulates _station_list with the new provider's stations."""
    # ProviderA has one other station (id=2). ProviderB has one station (id=3).
    repo._stations = [
        station,  # id=1, ProviderA (self — excluded)
        _mk_station(2, "Sibling On A", provider_id=1, provider_name="ProviderA"),
        _mk_station(3, "Sibling On B", provider_id=2, provider_name="ProviderB"),
    ]
    d = AddSiblingDialog(station, repo, parent=None)
    qtbot.addWidget(d)
    # ProviderA active initially: list contains "Sibling On A", not "Sibling On B".
    initial_names = [d._station_list.item(i).text()
                     for i in range(d._station_list.count())]
    assert "Sibling On A" in initial_names
    assert "Sibling On B" not in initial_names
    # Switch to ProviderB.
    provider_b_index = d._provider_combo.findText("ProviderB")
    d._provider_combo.setCurrentIndex(provider_b_index)
    after_names = [d._station_list.item(i).text()
                   for i in range(d._station_list.count())]
    assert "Sibling On B" in after_names
    assert "Sibling On A" not in after_names


# ---------------------------------------------------------------------------
# Tests — exclusion rules (CONTEXT D-13 / RESEARCH Pitfall 4)
# ---------------------------------------------------------------------------


def test_self_excluded_from_list(qtbot, station, repo):
    """CONTEXT D-13: the editing station MUST NOT appear in _station_list."""
    repo._stations = [
        station,  # id=1 — must be excluded
        _mk_station(2, "Other Station", provider_id=1, provider_name="ProviderA"),
    ]
    d = AddSiblingDialog(station, repo, parent=None)
    qtbot.addWidget(d)
    names = [d._station_list.item(i).text()
             for i in range(d._station_list.count())]
    assert "Test Station" not in names
    assert "Other Station" in names


def test_already_linked_excluded_from_list(qtbot, station, repo):
    """RESEARCH Pitfall 4 + UI-SPEC line 269: stations already linked are excluded."""
    repo._stations = [
        station,
        _mk_station(42, "Already Linked", provider_id=1, provider_name="ProviderA"),
        _mk_station(43, "Linkable", provider_id=1, provider_name="ProviderA"),
    ]
    repo._sibling_links = [42]  # station 42 is already a sibling of station 1
    d = AddSiblingDialog(station, repo, parent=None)
    qtbot.addWidget(d)
    names = [d._station_list.item(i).text()
             for i in range(d._station_list.count())]
    assert "Already Linked" not in names
    assert "Linkable" in names


# ---------------------------------------------------------------------------
# Tests — Ok gate + accept (CONTEXT D-13)
# ---------------------------------------------------------------------------


def test_ok_disabled_initially(dialog):
    """UI-SPEC line 261: Ok button starts disabled (no selection yet)."""
    assert dialog._button_box.button(QDialogButtonBox.Ok).isEnabled() is False


def test_accept_calls_add_sibling_link(qtbot, station, repo):
    """CONTEXT D-13: accept persists the link via Repo.add_sibling_link(a, b)."""
    target = _mk_station(2, "Sibling On A", provider_id=1, provider_name="ProviderA")
    repo._stations = [station, target]
    d = AddSiblingDialog(station, repo, parent=None)
    qtbot.addWidget(d)
    # Select the only item in the list.
    d._station_list.setCurrentRow(0)
    d._on_accept()
    assert repo.add_sibling_link_calls == [(1, 2)]


# ---------------------------------------------------------------------------
# CR-03 regression: AA exclusion uses live URL, not stale streams[0].url
# ---------------------------------------------------------------------------
# During EditStationDialog editing the URL field is the source of truth
# (Pitfall 4). When the user edits the URL without saving and then clicks
# "+ Add sibling", the dialog must use the IN-PROGRESS URL to compute the
# AA exclusion set, not the saved stale URL.


@pytest.fixture
def aa_repo():
    """Repo whose providers match the AA networks used by find_aa_siblings.

    AddSiblingDialog filters candidates by provider_name exact match against
    the combo selection, so the candidate stations' provider_name must be in
    the combo for the picker to show them.
    """
    r = FakeRepo()
    r._providers = [Provider(1, "DI.fm"), Provider(2, "ZenRadio")]
    return r


def test_live_url_drives_aa_exclusion(qtbot, aa_repo):
    """CR-03: AddSiblingDialog uses live_url (not station.streams[0].url) for
    AA exclusion.

    Setup:
      - Editing station (DI.fm) has a NON-AA persisted URL (so streams[0].url
        produces no AA siblings).
      - Candidate station (ZenRadio Ambient) has a real ZenRadio Ambient URL.
      - live_url is set to a DI.fm Ambient URL — find_aa_siblings should
        cross-network-match the candidate and exclude it from the picker.
    """
    editing = _mk_station(
        1, "Editing", provider_id=1, provider_name="DI.fm",
        url="http://stale.example/saved-url",  # non-AA persisted URL
    )
    candidate = _mk_station(
        2, "Ambient", provider_id=2, provider_name="ZenRadio",
        url="http://prem4.zenradio.com/zrambient?listen_key=abc",
    )
    aa_repo._stations = [editing, candidate]
    # live URL is the user's in-progress edit — a DI.fm Ambient URL.
    d = AddSiblingDialog(
        editing, aa_repo, parent=None,
        live_url="http://prem1.di.fm:80/ambient_hi?listen_key=abc",
    )
    qtbot.addWidget(d)
    # Switch to ZenRadio provider so we'd see the candidate if not excluded.
    zr_idx = d._provider_combo.findText("ZenRadio")
    d._provider_combo.setCurrentIndex(zr_idx)
    names = [
        d._station_list.item(i).text() for i in range(d._station_list.count())
    ]
    # Candidate must be EXCLUDED because AA detection under the live URL
    # treats it as an auto-sibling.
    assert "Ambient" not in names


def test_stale_url_no_longer_drives_aa_exclusion(qtbot, aa_repo):
    """CR-03 (counter-case): the stale streams[0].url MUST NOT be used when
    live_url is provided.

    Setup is the inverse of above:
      - Editing station (DI.fm) has a STALE persisted DI.fm Ambient URL.
      - Candidate (ZenRadio Ambient) would be AA-matched under the stale URL.
      - live_url is a non-AA URL — find_aa_siblings should NOT detect the
        candidate, so it remains in the picker.
    """
    editing = _mk_station(
        1, "Editing", provider_id=1, provider_name="DI.fm",
        url="http://prem1.di.fm:80/ambient_hi?listen_key=abc",  # stale AA
    )
    candidate = _mk_station(
        2, "Ambient", provider_id=2, provider_name="ZenRadio",
        url="http://prem4.zenradio.com/zrambient?listen_key=abc",
    )
    aa_repo._stations = [editing, candidate]
    # User has changed the URL to a non-AA value before clicking + Add sibling.
    d = AddSiblingDialog(
        editing, aa_repo, parent=None,
        live_url="http://example.com/not-aa/anymore",
    )
    qtbot.addWidget(d)
    zr_idx = d._provider_combo.findText("ZenRadio")
    d._provider_combo.setCurrentIndex(zr_idx)
    names = [
        d._station_list.item(i).text() for i in range(d._station_list.count())
    ]
    # Candidate is NOT excluded — the stale persisted URL no longer drives
    # AA detection.
    assert "Ambient" in names


def test_live_url_omitted_falls_back_to_streams(qtbot, aa_repo):
    """CR-03: backwards compatibility — when live_url is omitted (None) the
    dialog falls back to station.streams[0].url so existing call sites and
    tests that construct AddSiblingDialog without live_url still work."""
    editing = _mk_station(
        1, "Editing", provider_id=1, provider_name="DI.fm",
        url="http://prem1.di.fm:80/ambient_hi?listen_key=abc",
    )
    candidate = _mk_station(
        2, "Ambient", provider_id=2, provider_name="ZenRadio",
        url="http://prem4.zenradio.com/zrambient?listen_key=abc",
    )
    aa_repo._stations = [editing, candidate]
    # No live_url passed — fallback path.
    d = AddSiblingDialog(editing, aa_repo, parent=None)
    qtbot.addWidget(d)
    zr_idx = d._provider_combo.findText("ZenRadio")
    d._provider_combo.setCurrentIndex(zr_idx)
    names = [
        d._station_list.item(i).text() for i in range(d._station_list.count())
    ]
    # The saved DI.fm URL should AA-match the ZenRadio candidate.
    assert "Ambient" not in names
