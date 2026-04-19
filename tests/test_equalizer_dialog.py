"""Phase 47.2-03: EqualizerDialog widget smoke tests.

Mirrors the FakeRepo + qtbot fixture pattern from
``tests/test_accent_color_dialog.py``. FakePlayer is local (only three
methods needed for this dialog). ``paths._root_override`` is monkeypatched
to a tmp_path so every ``paths.eq_profiles_dir()`` call routes under test.

All QFileDialog / QInputDialog / QMessageBox interactions are monkeypatched
at the ``musicstreamer.ui_qt.equalizer_dialog`` module scope so the tests
are hermetic and do not open real OS dialogs.
"""
from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from musicstreamer import paths
from musicstreamer.eq_profile import parse_autoeq
from musicstreamer.ui_qt.equalizer_dialog import EqualizerDialog


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeRepo:
    def __init__(self):
        self._settings: dict[str, str] = {}

    def get_setting(self, key: str, default: str = "") -> str:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._settings[key] = value


class FakePlayer:
    def __init__(self):
        self.calls: list = []

    def set_eq_enabled(self, v):
        self.calls.append(("enabled", v))

    def set_eq_profile(self, p):
        self.calls.append(("profile", p))

    def set_eq_preamp(self, db):
        self.calls.append(("preamp", db))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def player():
    return FakePlayer()


@pytest.fixture
def toast_sink():
    """Collect toast messages for later assertions."""
    messages: list[str] = []

    def _sink(msg: str) -> None:
        messages.append(msg)

    _sink.messages = messages  # type: ignore[attr-defined]
    return _sink


@pytest.fixture
def _eq_root(tmp_path, monkeypatch):
    """Redirect every paths accessor under tmp_path for the duration."""
    monkeypatch.setattr(paths, "_root_override", str(tmp_path))
    # Pre-create the eq-profiles dir so listdir always succeeds.
    eq_dir = paths.eq_profiles_dir()
    os.makedirs(eq_dir, exist_ok=True)
    return tmp_path


@pytest.fixture
def dialog(qtbot, player, repo, toast_sink, _eq_root):
    dlg = EqualizerDialog(player, repo, toast_sink)
    qtbot.addWidget(dlg)
    return dlg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_VALID_AUTOEQ = (
    "Preamp: -6.2 dB\n"
    "Filter 1: ON PK Fc 105 Hz Gain -3.5 dB Q 0.7\n"
    "Filter 2: ON PK Fc 500 Hz Gain 2.0 dB Q 1.0\n"
    "Filter 3: ON PK Fc 8000 Hz Gain -2.0 dB Q 0.7\n"
)

_BAD_AUTOEQ = "this is not an AutoEQ file at all\nno filters here"


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dialog_opens_without_crash(dialog):
    """Core widgets exist after construction; dialog is not yet visible."""
    assert dialog.isVisible() is False
    for attr in (
        "_profile_combo",
        "_import_btn",
        "_delete_btn",
        "_preamp_slider",
        "_manual_check",
        "_save_as_btn",
        "_close_btn",
        "_curve",
    ):
        assert hasattr(dialog, attr), f"missing widget: {attr}"


def test_profile_switcher_lists_dir(qtbot, player, repo, toast_sink, _eq_root):
    """Combo lists '(none)' plus every .txt in the eq-profiles dir, sorted."""
    eq_dir = paths.eq_profiles_dir()
    _write(os.path.join(eq_dir, "b.txt"), _VALID_AUTOEQ)
    _write(os.path.join(eq_dir, "a.txt"), _VALID_AUTOEQ)
    # Non-txt noise should be ignored.
    _write(os.path.join(eq_dir, "readme.md"), "noise")
    dlg = EqualizerDialog(player, repo, toast_sink)
    qtbot.addWidget(dlg)
    items = [dlg._profile_combo.itemText(i) for i in range(dlg._profile_combo.count())]
    assert items == ["(none)", "a", "b"]


def test_import_bad_file_shows_toast(
    qtbot, player, repo, toast_sink, _eq_root, tmp_path, monkeypatch
):
    """A malformed file triggers a toast and is NOT copied into eq-profiles."""
    src = tmp_path / "bogus.txt"
    src.write_text(_BAD_AUTOEQ, encoding="utf-8")
    monkeypatch.setattr(
        "musicstreamer.ui_qt.equalizer_dialog.QFileDialog.getOpenFileName",
        lambda *a, **k: (str(src), ""),
    )
    dlg = EqualizerDialog(player, repo, toast_sink)
    qtbot.addWidget(dlg)
    dlg._on_import()
    # Toast was invoked with the exact D-06 message prefix.
    assert any("Failed to parse EQ profile" in m for m in toast_sink.messages)
    # Nothing got copied.
    eq_dir = paths.eq_profiles_dir()
    assert [f for f in os.listdir(eq_dir) if f.endswith(".txt")] == []


def test_import_good_file_copies_to_eq_profiles_dir(
    qtbot, player, repo, toast_sink, _eq_root, tmp_path, monkeypatch
):
    """A valid AutoEQ file is copied and the combo auto-selects it."""
    src = tmp_path / "HD 650.txt"
    src.write_text(_VALID_AUTOEQ, encoding="utf-8")
    monkeypatch.setattr(
        "musicstreamer.ui_qt.equalizer_dialog.QFileDialog.getOpenFileName",
        lambda *a, **k: (str(src), ""),
    )
    dlg = EqualizerDialog(player, repo, toast_sink)
    qtbot.addWidget(dlg)
    dlg._on_import()
    eq_dir = paths.eq_profiles_dir()
    copied = [f for f in os.listdir(eq_dir) if f.endswith(".txt")]
    assert len(copied) == 1
    # _sanitize converts spaces to underscores, stays ASCII.
    assert copied[0] == "HD_650.txt"
    # Combo now contains the imported profile's stem.
    items = [dlg._profile_combo.itemText(i) for i in range(dlg._profile_combo.count())]
    assert "HD_650" in items


def test_manual_mode_unlocks_sliders(
    qtbot, player, repo, toast_sink, _eq_root, monkeypatch
):
    """Band sliders are disabled until Manual toggle is checked."""
    eq_dir = paths.eq_profiles_dir()
    _write(os.path.join(eq_dir, "x.txt"), _VALID_AUTOEQ)
    dlg = EqualizerDialog(player, repo, toast_sink)
    qtbot.addWidget(dlg)
    idx = dlg._profile_combo.findData("x.txt")
    dlg._profile_combo.setCurrentIndex(idx)
    # Three bands from _VALID_AUTOEQ.
    assert len(dlg._band_sliders) == 3
    for s in dlg._band_sliders:
        assert s.isEnabled() is False
    dlg._manual_check.setChecked(True)
    for s in dlg._band_sliders:
        assert s.isEnabled() is True


def test_save_as_new_profile_writes_file(
    qtbot, player, repo, toast_sink, _eq_root, monkeypatch
):
    """Save-as-new writes a parseable AutoEQ file under the sanitized name."""
    eq_dir = paths.eq_profiles_dir()
    _write(os.path.join(eq_dir, "base.txt"), _VALID_AUTOEQ)
    dlg = EqualizerDialog(player, repo, toast_sink)
    qtbot.addWidget(dlg)
    idx = dlg._profile_combo.findData("base.txt")
    dlg._profile_combo.setCurrentIndex(idx)
    dlg._manual_check.setChecked(True)
    monkeypatch.setattr(
        "musicstreamer.ui_qt.equalizer_dialog.QInputDialog.getText",
        lambda *a, **k: ("My HD 650", True),
    )
    dlg._on_save_as_new()
    saved_path = os.path.join(eq_dir, "My_HD_650.txt")
    assert os.path.isfile(saved_path)
    with open(saved_path, "r", encoding="utf-8") as fh:
        reparsed = parse_autoeq(fh.read())
    assert len(reparsed.bands) == 3


def test_delete_with_confirm_removes_file_and_clears_active(
    qtbot, player, repo, toast_sink, _eq_root, monkeypatch
):
    """Delete with confirm removes the file and clears eq_active_profile."""
    eq_dir = paths.eq_profiles_dir()
    target = os.path.join(eq_dir, "to_delete.txt")
    _write(target, _VALID_AUTOEQ)
    dlg = EqualizerDialog(player, repo, toast_sink)
    qtbot.addWidget(dlg)
    idx = dlg._profile_combo.findData("to_delete.txt")
    dlg._profile_combo.setCurrentIndex(idx)
    assert dlg._active_filename == "to_delete.txt"
    monkeypatch.setattr(
        "musicstreamer.ui_qt.equalizer_dialog.QMessageBox.warning",
        lambda *a, **k: QMessageBox.Yes,
    )
    dlg._on_delete()
    assert not os.path.exists(target)
    assert dlg._active_filename == ""
    assert repo.get_setting("eq_active_profile", "UNSET") == ""


def test_preamp_slider_applies_to_player_and_persists(qtbot, dialog, repo, player):
    """Moving the preamp slider fires set_eq_preamp and persists to repo."""
    dialog._preamp_slider.setValue(-60)  # -6.0 dB
    # Last preamp call should carry -6.0.
    preamp_calls = [v for (kind, v) in player.calls if kind == "preamp"]
    assert preamp_calls and abs(preamp_calls[-1] - (-6.0)) < 1e-9
    assert repo.get_setting("eq_preamp_db") == "-6.00"


def test_parse_failure_on_select_keeps_previous_profile(
    qtbot, player, repo, toast_sink, _eq_root, monkeypatch
):
    """Selecting a malformed profile toasts + keeps the previously-active profile."""
    eq_dir = paths.eq_profiles_dir()
    _write(os.path.join(eq_dir, "good.txt"), _VALID_AUTOEQ)
    _write(os.path.join(eq_dir, "bad.txt"), _BAD_AUTOEQ)
    dlg = EqualizerDialog(player, repo, toast_sink)
    qtbot.addWidget(dlg)
    good_idx = dlg._profile_combo.findData("good.txt")
    dlg._profile_combo.setCurrentIndex(good_idx)
    good_profile = dlg._active_profile
    assert good_profile is not None
    bad_idx = dlg._profile_combo.findData("bad.txt")
    dlg._profile_combo.setCurrentIndex(bad_idx)
    assert any("Failed to parse EQ profile" in m for m in toast_sink.messages)
    # Prior active profile object is unchanged.
    assert dlg._active_profile is good_profile
