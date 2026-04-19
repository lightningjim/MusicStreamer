"""Phase 47.2 EqualizerDialog — AutoEQ profile manager + live EQ controls.

Implements CONTEXT decisions D-06, D-07, D-09, D-10, D-11, D-12, D-13,
D-14, D-15 (read/write side), D-17 (auto-apply preamp header on select),
D-19 (read-only band sliders unless Manual mode), D-20 (save-as-new).

Layout (D-11, top to bottom):
  1. Profile switcher (QComboBox) + Import button + trash QToolButton
  2. Active profile name label
  3. ResponseCurve canvas
  4. Preamp slider row (label + slider + value)
  5. Per-band vertical slider row (one column per band)
  6. Manual toggle + "Save as new profile..." button
  7. Close button (QDialogButtonBox)

Security:
  - User-supplied filenames route through settings_export._sanitize
    (Pitfall 6). Empty / '.' / '..' names fall back to "profile".
  - Parse failure on import or on switcher selection shows a toast
    and keeps the prior active profile intact (D-06).
  - Import validates BEFORE copying to eq-profiles/ so bogus files
    never land on disk.
"""
from __future__ import annotations

import os
import shutil
from typing import Callable, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from musicstreamer import paths
from musicstreamer.eq_profile import (
    EqBand,
    EqProfile,
    parse_autoeq,
    serialize_autoeq,
)
from musicstreamer.settings_export import _sanitize
from musicstreamer.ui_qt.eq_response_curve import ResponseCurve


_PREAMP_MIN_DB = -20.0
_PREAMP_MAX_DB = 6.0
_BAND_MIN_DB = -15.0
_BAND_MAX_DB = 15.0
_SLIDER_SCALE = 10   # 0.1 dB precision on integer QSlider ticks


class EqualizerDialog(QDialog):
    """Modal dialog for managing AutoEQ profiles and live EQ settings.

    Constructor signature mirrors DiscoveryDialog: (player, repo,
    toast_callback, parent=None). Follows the same `player + repo +
    toast` triad used by dialogs that need live player control and
    settings persistence.
    """

    def __init__(
        self,
        player,
        repo,
        toast_callback: Callable[[str], None],
        parent=None,
    ):
        super().__init__(parent)
        self._player = player
        self._repo = repo
        self._toast = toast_callback
        self._active_profile: Optional[EqProfile] = None
        self._active_filename: str = ""
        self._manual_mode: bool = False

        self.setWindowTitle("Equalizer")
        self.setMinimumWidth(560)
        self.setMinimumHeight(520)
        self.setModal(True)

        self._build_ui()
        self._load_state()

    # ------------------------------------------------------------------
    # Layout (D-11)
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Row 1: switcher + import + delete
        row1 = QHBoxLayout()
        self._profile_combo = QComboBox(self)
        self._profile_combo.setMinimumWidth(260)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        row1.addWidget(self._profile_combo, 1)

        self._import_btn = QPushButton("Import\u2026", self)
        self._import_btn.clicked.connect(self._on_import)
        row1.addWidget(self._import_btn)

        self._delete_btn = QToolButton(self)
        self._delete_btn.setIcon(
            QIcon.fromTheme(
                "user-trash-symbolic",
                QIcon(":/icons/user-trash-symbolic.svg"),
            )
        )
        self._delete_btn.setToolTip("Delete selected profile")
        self._delete_btn.clicked.connect(self._on_delete)
        row1.addWidget(self._delete_btn)
        root.addLayout(row1)

        # Active profile name label
        self._active_label = QLabel("(no profile)", self)
        root.addWidget(self._active_label)

        # Response curve (D-09 / D-10)
        self._curve = ResponseCurve(self)
        root.addWidget(self._curve, 1)

        # Preamp slider row
        preamp_row = QHBoxLayout()
        preamp_row.addWidget(QLabel("Preamp:", self))
        self._preamp_slider = QSlider(Qt.Horizontal, self)
        self._preamp_slider.setRange(
            int(_PREAMP_MIN_DB * _SLIDER_SCALE),
            int(_PREAMP_MAX_DB * _SLIDER_SCALE),
        )
        self._preamp_slider.setValue(0)
        self._preamp_slider.valueChanged.connect(self._on_preamp_changed)
        preamp_row.addWidget(self._preamp_slider, 1)
        self._preamp_label = QLabel("0.0 dB", self)
        self._preamp_label.setMinimumWidth(60)
        preamp_row.addWidget(self._preamp_label)
        root.addLayout(preamp_row)

        # Per-band slider row (populated on profile load)
        self._bands_container = QWidget(self)
        self._bands_layout = QHBoxLayout(self._bands_container)
        self._bands_layout.setContentsMargins(0, 0, 0, 0)
        self._band_sliders: List[QSlider] = []
        self._band_labels: List[QLabel] = []
        root.addWidget(self._bands_container)

        # Manual toggle + Save-as-new button
        toggle_row = QHBoxLayout()
        self._manual_check = QCheckBox("Manual mode (edit bands)", self)
        self._manual_check.toggled.connect(self._on_manual_toggled)
        toggle_row.addWidget(self._manual_check)
        toggle_row.addStretch(1)
        self._save_as_btn = QPushButton("Save as new profile\u2026", self)
        self._save_as_btn.setEnabled(False)
        self._save_as_btn.clicked.connect(self._on_save_as_new)
        toggle_row.addWidget(self._save_as_btn)
        root.addLayout(toggle_row)

        # Close
        btn_box = QDialogButtonBox()
        self._close_btn = btn_box.addButton("Close", QDialogButtonBox.RejectRole)
        self._close_btn.clicked.connect(self.reject)
        root.addWidget(btn_box)

    # ------------------------------------------------------------------
    # State load / save (D-15 — read side)
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        """Populate dropdown + restore preamp + select last-active profile."""
        self._refresh_profile_list()
        try:
            preamp = float(self._repo.get_setting("eq_preamp_db", "0.0"))
        except (TypeError, ValueError):
            preamp = 0.0
        self._preamp_slider.setValue(int(preamp * _SLIDER_SCALE))
        active = self._repo.get_setting("eq_active_profile", "")
        if active:
            idx = self._profile_combo.findData(active)
            if idx >= 0:
                self._profile_combo.setCurrentIndex(idx)

    def _refresh_profile_list(self) -> None:
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        self._profile_combo.addItem("(none)", userData="")
        eq_dir = paths.eq_profiles_dir()
        if os.path.isdir(eq_dir):
            for fname in sorted(os.listdir(eq_dir)):
                if fname.endswith(".txt"):
                    stem = os.path.splitext(fname)[0]
                    self._profile_combo.addItem(stem, userData=fname)
        self._profile_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_profile_selected(self, idx: int) -> None:
        fname = self._profile_combo.itemData(idx) or ""
        if not fname:
            self._set_active_profile(None, "")
            return
        path = os.path.join(paths.eq_profiles_dir(), fname)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                profile = parse_autoeq(fh.read())
        except (OSError, ValueError) as e:
            # D-06: toast + keep prior active profile intact.
            self._toast(f"Failed to parse EQ profile: {e}")
            return
        # D-17: auto-apply preamp header from the file on select.
        self._preamp_slider.setValue(int(profile.preamp_db * _SLIDER_SCALE))
        self._set_active_profile(profile, fname)

    def _set_active_profile(
        self, profile: Optional[EqProfile], filename: str
    ) -> None:
        self._active_profile = profile
        self._active_filename = filename
        self._active_label.setText(filename or "(no profile)")
        self._repo.set_setting("eq_active_profile", filename)
        self._player.set_eq_profile(profile)
        self._rebuild_band_sliders()
        self._redraw_curve()

    def _on_preamp_changed(self, value: int) -> None:
        db = value / _SLIDER_SCALE
        self._preamp_label.setText(f"{db:+.1f} dB")
        self._repo.set_setting("eq_preamp_db", f"{db:.2f}")
        self._player.set_eq_preamp(db)
        self._redraw_curve()

    def _on_manual_toggled(self, checked: bool) -> None:
        self._manual_mode = checked
        for s in self._band_sliders:
            s.setEnabled(checked)
        self._save_as_btn.setEnabled(checked and self._active_profile is not None)

    def _on_band_changed(self, band_idx: int, value: int) -> None:
        if self._active_profile is None or not self._manual_mode:
            return
        db = value / _SLIDER_SCALE
        band = self._active_profile.bands[band_idx]
        self._active_profile.bands[band_idx] = EqBand(
            filter_type=band.filter_type,
            freq_hz=band.freq_hz,
            gain_db=db,
            q=band.q,
        )
        self._band_labels[band_idx].setText(f"{db:+.1f}")
        self._player.set_eq_profile(self._active_profile)  # live update
        self._redraw_curve()

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import AutoEQ profile",
            "",
            "AutoEQ ParametricEQ (*.txt);;All files (*)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            _ = parse_autoeq(text)   # validate before copy
        except (OSError, ValueError) as e:
            # D-06: toast + do NOT copy to eq-profiles/.
            self._toast(f"Failed to parse EQ profile: {e}")
            return
        stem = os.path.splitext(os.path.basename(path))[0]
        safe_stem = _sanitize(stem) or "profile"   # Pitfall 6
        eq_dir = paths.eq_profiles_dir()
        os.makedirs(eq_dir, exist_ok=True)
        dest = os.path.join(eq_dir, f"{safe_stem}.txt")
        try:
            shutil.copyfile(path, dest)
        except OSError as e:
            self._toast(f"Failed to copy EQ profile: {e}")
            return
        self._refresh_profile_list()
        new_fname = f"{safe_stem}.txt"
        idx = self._profile_combo.findData(new_fname)
        if idx >= 0:
            self._profile_combo.setCurrentIndex(idx)

    def _on_delete(self) -> None:
        fname = self._profile_combo.currentData() or ""
        if not fname:
            return
        result = QMessageBox.warning(
            self,
            "Delete profile",
            f"Delete '{os.path.splitext(fname)[0]}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if result != QMessageBox.Yes:
            return
        path = os.path.join(paths.eq_profiles_dir(), fname)
        try:
            os.remove(path)
        except OSError as e:
            self._toast(f"Failed to delete profile: {e}")
            return
        # D-14: clear active if the deleted file was the active one.
        if self._active_filename == fname:
            self._set_active_profile(None, "")
        self._refresh_profile_list()

    def _on_save_as_new(self) -> None:
        if self._active_profile is None:
            return
        name, ok = QInputDialog.getText(
            self, "Save as new profile", "Profile name:"
        )
        if not ok or not name.strip():
            return
        safe_stem = _sanitize(name.strip()) or "profile"
        eq_dir = paths.eq_profiles_dir()
        os.makedirs(eq_dir, exist_ok=True)
        dest = os.path.join(eq_dir, f"{safe_stem}.txt")
        # D-20: preamp_db on the saved profile = currently-displayed preamp.
        saved = EqProfile(
            preamp_db=self._preamp_slider.value() / _SLIDER_SCALE,
            bands=list(self._active_profile.bands),
        )
        try:
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(serialize_autoeq(saved))
        except OSError as e:
            self._toast(f"Failed to save profile: {e}")
            return
        self._refresh_profile_list()
        idx = self._profile_combo.findData(f"{safe_stem}.txt")
        if idx >= 0:
            self._profile_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Per-band sliders
    # ------------------------------------------------------------------

    def _rebuild_band_sliders(self) -> None:
        # Clear existing sliders + labels.
        for s in self._band_sliders:
            s.setParent(None)
            s.deleteLater()
        for lbl in self._band_labels:
            lbl.setParent(None)
            lbl.deleteLater()
        self._band_sliders = []
        self._band_labels = []
        # Clear any prior column wrappers still in the layout.
        while self._bands_layout.count():
            item = self._bands_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if self._active_profile is None:
            # Still refresh the save-as state.
            self._save_as_btn.setEnabled(False)
            return
        for i, b in enumerate(self._active_profile.bands):
            col = QVBoxLayout()
            freq_label = QLabel(self._format_freq(b.freq_hz), self)
            freq_label.setAlignment(Qt.AlignCenter)
            col.addWidget(freq_label)
            slider = QSlider(Qt.Vertical, self)
            slider.setRange(
                int(_BAND_MIN_DB * _SLIDER_SCALE),
                int(_BAND_MAX_DB * _SLIDER_SCALE),
            )
            slider.setValue(int(b.gain_db * _SLIDER_SCALE))
            slider.setEnabled(self._manual_mode)   # D-19: read-only unless Manual
            slider.setFixedWidth(28)
            slider.valueChanged.connect(
                lambda v, idx=i: self._on_band_changed(idx, v)
            )
            col.addWidget(slider, 1)
            gain_label = QLabel(f"{b.gain_db:+.1f}", self)
            gain_label.setAlignment(Qt.AlignCenter)
            col.addWidget(gain_label)
            self._band_sliders.append(slider)
            self._band_labels.append(gain_label)
            wrap = QWidget(self)
            wrap.setLayout(col)
            self._bands_layout.addWidget(wrap)
        self._save_as_btn.setEnabled(
            self._manual_mode and self._active_profile is not None
        )

    @staticmethod
    def _format_freq(hz: float) -> str:
        return f"{int(hz)} Hz" if hz < 1000 else f"{hz / 1000:.1f}k"

    def _redraw_curve(self) -> None:
        preamp = self._preamp_slider.value() / _SLIDER_SCALE
        self._curve.set_profile(self._active_profile, preamp)
