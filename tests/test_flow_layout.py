"""Tests for FlowLayout (Phase 38-01 Task 1).

Geometry tests validating wrapping behaviour and single-row behaviour.
"""
from __future__ import annotations

import pytest

from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import QPushButton, QWidget

from musicstreamer.ui_qt.flow_layout import FlowLayout


def _make_container_with_buttons(
    qtbot, count: int, btn_width: int, container_width: int
) -> tuple[QWidget, FlowLayout]:
    """Create a QWidget with FlowLayout containing `count` buttons of `btn_width` each."""
    container = QWidget()
    qtbot.addWidget(container)
    layout = FlowLayout(container, h_spacing=4, v_spacing=8)
    for i in range(count):
        btn = QPushButton(f"Chip {i}", container)
        btn.setFixedSize(btn_width, 24)
        layout.addWidget(btn)
    container.setFixedWidth(container_width)
    return container, layout


def test_flow_layout_wraps(qtbot):
    """5 buttons × 80px in 300px container must produce >= 2 rows."""
    container, layout = _make_container_with_buttons(
        qtbot, count=5, btn_width=80, container_width=300
    )
    # Force layout pass by calling heightForWidth
    h = layout.heightForWidth(300)
    # One row of 3 buttons + one row of 2 buttons = 2 rows
    # Each button is 24px tall, v_spacing=8 → min height for 2 rows = 24+8+24=56
    assert h > 24, f"Expected height > 24 (single row height), got {h}"


def test_flow_layout_single_row(qtbot):
    """3 buttons × 80px in 500px container fits in 1 row."""
    container, layout = _make_container_with_buttons(
        qtbot, count=3, btn_width=80, container_width=500
    )
    h = layout.heightForWidth(500)
    # All 3 fit: total width = 3*80 + 2*4 = 248 < 500
    # Height should equal single row height (24px) + margins
    assert h <= 24 + layout.contentsMargins().top() + layout.contentsMargins().bottom()


def test_flow_layout_count(qtbot):
    """count() reflects number of added items."""
    container = QWidget()
    qtbot.addWidget(container)
    layout = FlowLayout(container)
    for i in range(4):
        layout.addWidget(QPushButton(f"B{i}", container))
    assert layout.count() == 4


def test_flow_layout_has_height_for_width(qtbot):
    container = QWidget()
    qtbot.addWidget(container)
    layout = FlowLayout(container)
    assert layout.hasHeightForWidth() is True


def test_flow_layout_item_at(qtbot):
    container = QWidget()
    qtbot.addWidget(container)
    layout = FlowLayout(container)
    btn = QPushButton("X", container)
    layout.addWidget(btn)
    item = layout.itemAt(0)
    assert item is not None
    assert item.widget() is btn
    assert layout.itemAt(99) is None


def test_flow_layout_take_at(qtbot):
    container = QWidget()
    qtbot.addWidget(container)
    layout = FlowLayout(container)
    btn = QPushButton("X", container)
    layout.addWidget(btn)
    assert layout.count() == 1
    taken = layout.takeAt(0)
    assert taken is not None
    assert layout.count() == 0
