"""Phase 47.2 frequency-response curve widget (D-09, D-10).

Display-only (no click/drag). Redrawn on profile load, preamp change, or
Manual-mode band edit. Uses QPainter + stdlib math — no numpy/scipy.

Palette-driven: all colors come through ``self.palette()`` so the widget
recolors automatically on light/dark theme and accent-color changes
(Phase 46 theme contract). ``_MutedLabel``'s ``changeEvent(PaletteChange)``
idiom (now_playing_panel.py lines 73-76) is reused here.

Biquad magnitude math is the standard RBJ cookbook (47.2-RESEARCH.md
§Code Examples §3). Preamp is ADDED to each band's gain (Pitfall 5 —
AutoEQ preamp is conventionally negative; addition yields net
attenuation).
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from musicstreamer.eq_profile import EqProfile


_FS = 48000.0           # display sample rate (pulsesink default); cosmetic
_F_LO, _F_HI = 20.0, 20000.0
_DB_RANGE = 12.0        # +/-12 dB vertical span
_N_POINTS = 256         # log-spaced grid (D-09)


def _biquad_coeffs(filter_type: str, freq_hz: float, q: float, gain_db: float):
    # Verbatim from 47.2-RESEARCH.md Section Code Examples #3 _biquad_coeffs
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * freq_hz / _FS
    cos_w0 = math.cos(w0)
    sin_w0 = math.sin(w0)
    alpha = sin_w0 / (2.0 * max(q, 1e-6))
    if filter_type == "PK":
        b0 = 1.0 + alpha * A
        b1 = -2.0 * cos_w0
        b2 = 1.0 - alpha * A
        a0 = 1.0 + alpha / A
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha / A
    elif filter_type == "LSC":
        sA = math.sqrt(A)
        b0 = A * ((A + 1) - (A - 1) * cos_w0 + 2 * sA * alpha)
        b1 = 2 * A * ((A - 1) - (A + 1) * cos_w0)
        b2 = A * ((A + 1) - (A - 1) * cos_w0 - 2 * sA * alpha)
        a0 = (A + 1) + (A - 1) * cos_w0 + 2 * sA * alpha
        a1 = -2 * ((A - 1) + (A + 1) * cos_w0)
        a2 = (A + 1) + (A - 1) * cos_w0 - 2 * sA * alpha
    elif filter_type == "HSC":
        sA = math.sqrt(A)
        b0 = A * ((A + 1) + (A - 1) * cos_w0 + 2 * sA * alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
        b2 = A * ((A + 1) + (A - 1) * cos_w0 - 2 * sA * alpha)
        a0 = (A + 1) - (A - 1) * cos_w0 + 2 * sA * alpha
        a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
        a2 = (A + 1) - (A - 1) * cos_w0 - 2 * sA * alpha
    else:
        raise ValueError(f"Unknown filter_type: {filter_type}")
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def _biquad_magnitude_db(b0, b1, b2, a1, a2, freq_hz: float) -> float:
    # Verbatim from 47.2-RESEARCH.md Section Code Examples #3
    w = 2.0 * math.pi * freq_hz / _FS
    cos1, sin1 = math.cos(w), math.sin(w)
    cos2, sin2 = math.cos(2 * w), math.sin(2 * w)
    num_re = b0 + b1 * cos1 + b2 * cos2
    num_im = -b1 * sin1 - b2 * sin2
    den_re = 1.0 + a1 * cos1 + a2 * cos2
    den_im = -a1 * sin1 - a2 * sin2
    num_mag2 = num_re * num_re + num_im * num_im
    den_mag2 = den_re * den_re + den_im * den_im
    return 10.0 * math.log10(max(num_mag2 / max(den_mag2, 1e-30), 1e-30))


def compute_response(profile: EqProfile, preamp_db: float,
                     n_points: int = _N_POINTS) -> List[Tuple[float, float]]:
    """Log-spaced (20 Hz - 20 kHz) combined magnitude response in dB (D-09).

    Pitfall 5: preamp is ADDED to each band's gain_db (additive convention).
    """
    freqs = [_F_LO * (_F_HI / _F_LO) ** (i / (n_points - 1)) for i in range(n_points)]
    coeffs = [_biquad_coeffs(b.filter_type, b.freq_hz, b.q, b.gain_db + preamp_db)
              for b in profile.bands]
    out = []
    for f in freqs:
        total = 0.0
        for c in coeffs:
            total += _biquad_magnitude_db(*c, f)
        out.append((f, total))
    return out


class ResponseCurve(QWidget):
    """Static log-freq dB response curve (D-09).

    Call ``set_profile(profile, preamp_db)`` to update the displayed curve.
    A flat reference line is drawn when ``profile`` is None or empty.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self._points: List[Tuple[float, float]] = []

    def set_profile(self, profile: Optional[EqProfile], preamp_db: float = 0.0) -> None:
        if profile is None or not profile.bands:
            self._points = [(_F_LO, 0.0), (_F_HI, 0.0)]
        else:
            self._points = compute_response(profile, preamp_db)
        self.update()

    # _MutedLabel idiom: redraw on theme flip (now_playing_panel.py lines 73-76)
    def changeEvent(self, event) -> None:  # type: ignore[override]
        if event.type() in (QEvent.PaletteChange, QEvent.StyleChange):
            self.update()
        super().changeEvent(event)

    def _freq_to_x(self, freq_hz: float, w: int) -> float:
        t = math.log10(max(freq_hz, 1e-3) / _F_LO) / math.log10(_F_HI / _F_LO)
        return max(0.0, min(1.0, t)) * (w - 1)

    def _db_to_y(self, db: float, h: int) -> float:
        t = (db + _DB_RANGE) / (2.0 * _DB_RANGE)
        return (1.0 - max(0.0, min(1.0, t))) * (h - 1)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pal = self.palette()
        p.fillRect(self.rect(), pal.base())

        # Grid: vertical decades at 100 / 1000 / 10000 Hz
        grid_pen = QPen(pal.mid().color(), 1, Qt.DotLine)
        p.setPen(grid_pen)
        for f in (100.0, 1000.0, 10000.0):
            x = self._freq_to_x(f, w)
            p.drawLine(int(x), 0, int(x), h)
        # Horizontal lines at 0, +/-6 dB
        for db in (-6.0, 0.0, 6.0):
            y = self._db_to_y(db, h)
            p.drawLine(0, int(y), w, int(y))

        # Axis labels (small font, text color from palette)
        label_pen = QPen(pal.text().color(), 1)
        p.setPen(label_pen)
        font = QFont()
        font.setPointSize(8)
        p.setFont(font)
        for f, label in ((100.0, "100"), (1000.0, "1k"), (10000.0, "10k")):
            x = self._freq_to_x(f, w)
            p.drawText(int(x) + 3, h - 3, f"{label} Hz")
        p.drawText(4, int(self._db_to_y(0.0, h)) - 2, "0 dB")

        # Curve path
        if self._points:
            path = QPainterPath()
            for i, (freq, db) in enumerate(self._points):
                x = self._freq_to_x(freq, w)
                y = self._db_to_y(db, h)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            curve_pen = QPen(pal.highlight().color(), 2)
            p.setPen(curve_pen)
            p.drawPath(path)
