"""Phase 38-01: FlowLayout — wrapping QLayout for chip rows.

In-repo implementation based on the canonical Qt FlowLayout C++ example,
translated to Python/PySide6.

h_spacing: horizontal gap between items (default 4px — xs token)
v_spacing: vertical gap between rows (default 8px — sm token)
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtWidgets import QLayout, QSizePolicy, QWidgetItem


class FlowLayout(QLayout):
    """Wrapping layout for chip buttons.

    Lays out items left-to-right, wrapping to a new row when the container
    width is exceeded.
    """

    def __init__(self, parent=None, h_spacing: int = 4, v_spacing: int = 8) -> None:
        super().__init__(parent)
        self._items: list[QWidgetItem] = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing

    # ------------------------------------------------------------------
    # QLayout required overrides
    # ------------------------------------------------------------------

    def addItem(self, item) -> None:  # noqa: N802 (Qt override)
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        s = QSize()
        for item in self._items:
            s = s.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return QSize(
            s.width() + margins.left() + margins.right(),
            s.height() + margins.top() + margins.bottom(),
        )

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    # ------------------------------------------------------------------
    # Internal layout engine
    # ------------------------------------------------------------------

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        x = rect.x() + margins.left()
        y = rect.y() + margins.top()
        row_height = 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h_spacing
            if next_x - self._h_spacing > rect.right() - margins.right() and row_height > 0:
                x = rect.x() + margins.left()
                y += row_height + self._v_spacing
                next_x = x + hint.width() + self._h_spacing
                row_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y() + margins.bottom()
