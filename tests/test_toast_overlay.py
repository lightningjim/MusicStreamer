"""Phase 37-03 — ToastOverlay widget tests (UI-12, QA-05 lifetime).

Covers the 14 behaviors enumerated in 37-03-PLAN.md Task 1:
construction, show/hide lifecycle, QPropertyAnimation targeting
windowOpacity, auto-dismiss, width clamp, positioning, re-anchor on
parent resize, re-show-during-fade-out interrupt (QA-05 lifetime guard),
mouse transparency, NO Qt.WA_DeleteOnClose, construct/destroy cycle,
animation parent ownership, inner QLabel objectName, and QSS contract.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QAbstractAnimation, Qt
from PySide6.QtWidgets import QApplication, QWidget

from musicstreamer.theme import THEME_PRESETS, build_palette_from_dict
from musicstreamer.ui_qt.toast import ToastOverlay


@pytest.fixture
def parent_widget(qtbot):
    parent = QWidget()
    parent.resize(1200, 800)
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitExposed(parent)
    return parent


def test_1_construct_hidden(qtbot, parent_widget):
    toast = ToastOverlay(parent_widget)
    assert toast.isVisible() is False
    assert toast.parent() is parent_widget


def test_2_show_toast_sets_text_and_visible(qtbot, parent_widget):
    toast = ToastOverlay(parent_widget)
    toast.show_toast("Hello")
    assert toast.label.text() == "Hello"
    assert toast.isVisible() is True


def test_3_fade_in_running_on_opacity(qtbot, parent_widget):
    toast = ToastOverlay(parent_widget)
    toast.show_toast("X")
    assert toast._fade_in.state() == QAbstractAnimation.Running
    assert toast._fade_in.propertyName() == b"opacity"
    assert toast._fade_in.startValue() == 0.0
    assert toast._fade_in.endValue() == 1.0
    assert toast._fade_in.duration() == 150


def test_4_auto_dismiss(qtbot, parent_widget):
    toast = ToastOverlay(parent_widget)
    toast.show_toast("X", duration_ms=10)
    # 10 ms hold + 300 ms fade-out + 100 ms buffer
    qtbot.wait(500)
    assert toast.isVisible() is False


def test_5_width_clamp(qtbot, parent_widget):
    # parent width 1200 → max clamp min(1200-64, 480) == 480
    toast = ToastOverlay(parent_widget)
    toast.show_toast("A short message")
    assert toast.width() >= 240
    assert toast.width() <= 480


def test_6_position_bottom_center(qtbot, parent_widget):
    toast = ToastOverlay(parent_widget)
    toast.show_toast("A short message")
    expected_x = (parent_widget.width() - toast.width()) // 2
    expected_y = parent_widget.height() - toast.height() - 32
    assert toast.x() == expected_x
    assert toast.y() == expected_y


def test_7_reposition_on_parent_resize(qtbot, parent_widget):
    toast = ToastOverlay(parent_widget)
    toast.show_toast("Resize me")
    parent_widget.resize(800, 600)
    qtbot.wait(50)
    expected_x = (parent_widget.width() - toast.width()) // 2
    expected_y = parent_widget.height() - toast.height() - 32
    assert toast.x() == expected_x
    assert toast.y() == expected_y


def test_8_reshow_during_fade_out(qtbot, parent_widget):
    """QA-05: re-show during fade-out must interrupt cleanly, no crash."""
    toast = ToastOverlay(parent_widget)
    toast.show_toast("A", duration_ms=10)
    qtbot.wait(50)  # now in fade-out phase
    # Re-show should not raise RuntimeError or create phantom animation
    toast.show_toast("B")
    assert toast.label.text() == "B"
    assert toast.isVisible() is True
    # fade_out must have been stopped
    assert toast._fade_out.state() != QAbstractAnimation.Running


def test_9_mouse_transparent(qtbot, parent_widget):
    toast = ToastOverlay(parent_widget)
    assert toast.testAttribute(Qt.WA_TransparentForMouseEvents) is True


def test_10_no_wa_delete_on_close(qtbot, parent_widget):
    """QA-05: parent-owned lifetime, not WA_DeleteOnClose."""
    toast = ToastOverlay(parent_widget)
    assert toast.testAttribute(Qt.WA_DeleteOnClose) is False


def test_11_construct_destroy_cycle(qtbot):
    """QA-05: 3 construct/destroy cycles on same parent — no C++ leak."""
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)
    parent.show()
    try:
        for _ in range(3):
            toast = ToastOverlay(parent)
            toast.show_toast("cycle", duration_ms=10)
            toast.deleteLater()
            qtbot.wait(50)
    except RuntimeError as exc:
        pytest.fail(f"construct/destroy cycle raised RuntimeError: {exc}")


def test_12_animation_parent_ownership(qtbot, parent_widget):
    """Pitfall §6: animations must be parented to the toast to avoid GC freeze."""
    toast = ToastOverlay(parent_widget)
    assert toast._fade_in.parent() is toast
    assert toast._fade_out.parent() is toast


def test_13_inner_label_object_name(qtbot, parent_widget):
    toast = ToastOverlay(parent_widget)
    assert toast.label.objectName() == "ToastLabel"


def test_14_stylesheet_system_theme_color_contract(qtbot, parent_widget, qapp):
    """Phase 75 D-09 / UI-SPEC §Color §System-theme legacy fallback IMMUTABLE QSS LOCK.

    Gated to theme='system' explicit setup so the legacy QSS substring is locked
    only when the system branch is active. Non-system branches are covered by
    test_stylesheet_non_system_uses_tooltip_palette + overrun variant.
    """
    qapp.setProperty("theme_name", "system")
    toast = ToastOverlay(parent_widget)
    qss = toast.styleSheet()
    assert "rgba(40, 40, 40, 220)" in qss
    assert "color: white" in qss
    assert "border-radius: 8px" in qss
    assert "padding: 8px 12px" in qss


def test_stylesheet_non_system_uses_tooltip_palette(qtbot, parent_widget, qapp):
    """Phase 75 D-09 — non-system theme yields palette-driven QSS.

    Vaporwave UI-SPEC LOCKED pair: ToolTipBase=#f9d6f0 → rgb(249, 214, 240);
    ToolTipText=#3a2845. Geometry pair (border-radius / padding) invariant.

    Headless test note (PLAN-03 SUMMARY): QApplication.sendPostedEvents() is
    required after app.setPalette so the queued PaletteChange events flush to
    the parent_widget BEFORE we construct the toast. Without the flush, the
    parent's cached palette is stale and the toast (which reads self.palette()
    inheriting from parent) sees Qt's default ToolTipBase.
    """
    qapp.setProperty("theme_name", "vaporwave")
    qapp.setPalette(build_palette_from_dict(THEME_PRESETS["vaporwave"]))
    QApplication.sendPostedEvents()
    toast = ToastOverlay(parent_widget)
    qss = toast.styleSheet()
    assert "rgba(249, 214, 240, 220)" in qss
    assert "color: #3a2845" in qss
    assert "border-radius: 8px" in qss
    assert "padding: 8px 12px" in qss


def test_stylesheet_non_system_overrun_palette(qtbot, parent_widget, qapp):
    """Phase 75 D-09 — overrun (dark family) palette-driven QSS.

    Overrun UI-SPEC LOCKED pair: ToolTipBase=#1a0a18 → rgb(26, 10, 24);
    ToolTipText=#ffe8f4. Bright (vaporwave) + dark (overrun) families both
    locked → covers the two contrast regimes UI-SPEC enforces.
    """
    qapp.setProperty("theme_name", "overrun")
    qapp.setPalette(build_palette_from_dict(THEME_PRESETS["overrun"]))
    QApplication.sendPostedEvents()
    toast = ToastOverlay(parent_widget)
    qss = toast.styleSheet()
    assert "rgba(26, 10, 24, 220)" in qss
    assert "color: #ffe8f4" in qss


def test_changeEvent_palette_change_rebuilds_qss(qtbot, parent_widget, qapp):
    """Phase 75 D-09 / RESEARCH §Pattern 2 — changeEvent(PaletteChange) retint.

    Snapshot-mutate-assert: construct with theme='system' (legacy QSS),
    snapshot styleSheet(); flip theme + setPalette; assert qss_after differs
    and contains the non-system substring. Qt dispatches PaletteChange to
    existing widgets; ToastOverlay.changeEvent(PaletteChange) calls
    _rebuild_stylesheet which re-reads QApplication.property('theme_name').

    Headless note: sendPostedEvents() ensures the queued PaletteChange is
    delivered to the toast widget BEFORE we read styleSheet().
    """
    qapp.setProperty("theme_name", "system")
    toast = ToastOverlay(parent_widget)
    qss_before = toast.styleSheet()
    assert "rgba(40, 40, 40, 220)" in qss_before
    # Flip to vaporwave — Qt dispatches PaletteChange via posted events.
    qapp.setProperty("theme_name", "vaporwave")
    qapp.setPalette(build_palette_from_dict(THEME_PRESETS["vaporwave"]))
    QApplication.sendPostedEvents()
    qss_after = toast.styleSheet()
    assert qss_after != qss_before
    assert "rgba(249, 214, 240, 220)" in qss_after


def test_stylesheet_no_font_properties(qtbot, parent_widget, qapp):
    """Phase 75 UI-SPEC §Typography invariance lock.

    No `font-size:`, `font-family:`, or `font-weight:` in either branch.
    Iterates across system + 3 non-system themes (vaporwave bright,
    overrun dark, dark neutral).
    """
    for theme in ("system", "vaporwave", "overrun", "dark"):
        qapp.setProperty("theme_name", theme)
        if theme != "system":
            qapp.setPalette(build_palette_from_dict(THEME_PRESETS[theme]))
            QApplication.sendPostedEvents()
        toast = ToastOverlay(parent_widget)
        qss = toast.styleSheet()
        assert "font-size:" not in qss, f"font-size leaked in {theme!r}"
        assert "font-family:" not in qss, f"font-family leaked in {theme!r}"
        assert "font-weight:" not in qss, f"font-weight leaked in {theme!r}"


def test_stylesheet_geometry_invariant_both_branches(qtbot, parent_widget, qapp):
    """Phase 75 UI-SPEC §Geometry invariance lock.

    `border-radius: 8px` and `padding: 8px 12px` MUST appear in every branch
    (system + every non-system theme). Geometry is decoupled from palette.
    """
    for theme in ("system", "vaporwave", "overrun", "dark"):
        qapp.setProperty("theme_name", theme)
        if theme != "system":
            qapp.setPalette(build_palette_from_dict(THEME_PRESETS[theme]))
            QApplication.sendPostedEvents()
        toast = ToastOverlay(parent_widget)
        qss = toast.styleSheet()
        assert "border-radius: 8px" in qss, f"border-radius missing in {theme!r}"
        assert "padding: 8px 12px" in qss, f"padding missing in {theme!r}"
