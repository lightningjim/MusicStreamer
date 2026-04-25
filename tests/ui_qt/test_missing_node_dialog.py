"""Tests for runtime_check.show_missing_node_dialog (Phase 44, RUNTIME-01 D-13.1).

When invoked, the missing-Node startup dialog must wire two buttons:
  - "Open nodejs.org" — primary action; opens the install URL.
  - "OK" — dismiss the dialog.

This test patches QMessageBox at the runtime_check module level with a fake
that records addButton invocations and short-circuits exec() — avoiding any
modal blocking on a headless Qt test runner.

RED until Plan 02 lands musicstreamer/runtime_check.py.
"""
from __future__ import annotations

from typing import Any


class _FakeButton:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class _FakeBox:
    """Records every QMessageBox call relevant to the dialog contract."""

    instances: list["_FakeBox"] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.added_buttons: list[tuple[str, Any]] = []
        self.title: str = ""
        self.text_body: str = ""
        self.exec_called: bool = False
        self._clicked: Any = None
        _FakeBox.instances.append(self)

    def setWindowTitle(self, title: str) -> None:
        self.title = title

    def setText(self, body: str) -> None:
        self.text_body = body

    def setIcon(self, icon: Any) -> None:
        pass

    def addButton(self, *args: Any, **kwargs: Any) -> _FakeButton:
        # Two call signatures supported by QMessageBox.addButton:
        #   addButton(text: str, role: ButtonRole)
        #   addButton(button: QPushButton, role: ButtonRole)
        text = args[0] if args and isinstance(args[0], str) else "<button>"
        role = args[1] if len(args) > 1 else None
        btn = _FakeButton(text)
        self.added_buttons.append((text, role))
        return btn

    def setDefaultButton(self, *args: Any, **kwargs: Any) -> None:
        pass

    def exec(self) -> int:
        self.exec_called = True
        return 0

    def clickedButton(self) -> Any:
        return self._clicked


def test_dialog_has_open_and_ok_buttons(qtbot, monkeypatch):
    """Dialog adds at least one button labeled 'Open nodejs.org' and one 'OK'."""
    # Lazy import: musicstreamer.runtime_check lands in Plan 02 (Wave 1).
    # Keeps collection green; test RED-fails at execution until Plan 02.
    from musicstreamer import runtime_check
    _FakeBox.instances.clear()
    monkeypatch.setattr(runtime_check, "QMessageBox", _FakeBox)

    runtime_check.show_missing_node_dialog(parent=None)

    assert _FakeBox.instances, "show_missing_node_dialog did not construct a QMessageBox"
    box = _FakeBox.instances[-1]
    button_texts = [text for text, _role in box.added_buttons]
    assert any("Open nodejs.org" in t for t in button_texts), (
        f"missing 'Open nodejs.org' button: {button_texts!r}"
    )
    assert any("OK" in t for t in button_texts), (
        f"missing 'OK' button: {button_texts!r}"
    )
    assert box.exec_called, "dialog was constructed but exec() was not called"
