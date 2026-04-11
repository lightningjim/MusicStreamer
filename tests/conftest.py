"""pytest-qt session configuration.

Sets the Qt platform plugin to ``offscreen`` so tests run headless on CI
and on headless dev boxes. Must happen BEFORE any PySide6 import.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# pytest-qt auto-provides the ``qtbot`` fixture; no explicit re-export needed.
