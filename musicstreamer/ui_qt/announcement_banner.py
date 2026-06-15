"""Phase 87 / Plan 87-05 / D-14: GBS.FM announcement banner widget.

AnnouncementBanner is a narrow QWidget displayed at the top of NowPlayingPanel
whenever the GBS.FM marquee first-segment carries a non-empty announcement text.

Security (T-87-05-01 / CONVENTIONS T-40-04):
    The banner QLabel MUST use Qt.TextFormat.PlainText. GBS.FM marquee text is
    operator-controlled but is not trusted HTML — using RichText would allow
    HTML/JS injection through a compromised or rogue marquee feed. PlainText is
    enforced at construction time and validated by ``test_banner_uses_plaintext_format``.

Content rendering (GBS-MARQ-04 / D-14):
    Internal ``|`` characters in the first-segment are replaced by ``\\n`` so
    QLabel's ``wordWrap=True`` wraps at pipe boundaries, giving multi-part
    announcements a readable vertical layout.

Dismissal (GBS-MARQ-03):
    The × QPushButton emits ``dismissed(str)`` carrying the current
    ``announcement_hash``. NowPlayingPanel adds the hash to its
    ``_dismissed_announcement_hashes: set[str]`` so the same text never
    re-appears for the rest of the session, even if the 60s marquee poll
    returns the same first-segment on subsequent ticks.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class AnnouncementBanner(QWidget):
    """Top-of-panel announcement banner for GBS.FM marquee first-segment text.

    Layout: ``[ _label (stretch=1) | _dismiss_btn (24×24 flat) ]``

    Signals:
        dismissed(str): Emitted when the × button is clicked.
                        Payload is the ``announcement_hash`` (SHA-256 hex digest
                        of the first_segment encoded as UTF-8), not the text itself.
                        NowPlayingPanel's ``_on_banner_dismissed`` slot adds this
                        hash to ``_dismissed_announcement_hashes``.

    Usage::

        banner.set_announcement(first_segment, announcement_hash)  # show
        banner.clear()                                              # hide without clearing hash
    """

    # Class-scope Signal declaration (Pitfall 4 — MUST be class scope, not instance).
    dismissed = Signal(str)  # payload: announcement_hash

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construct the banner in its initial hidden state.

        The banner starts hidden (``setVisible(False)``) and is only shown when
        ``set_announcement`` is called with a non-empty first_segment that is not
        dismissed.
        """
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(8)

        # Announcement text label.
        # PlainText: non-negotiable (CONVENTIONS T-40-04 / T-87-05-01).
        self._label = QLabel(self)
        self._label.setTextFormat(Qt.TextFormat.PlainText)
        self._label.setWordWrap(True)
        layout.addWidget(self._label, 1)  # stretch=1 — fills available width

        # Dismiss × button.
        # Flat + fixed small size so it doesn't dominate the banner visually.
        self._dismiss_btn = QPushButton("×", self)
        self._dismiss_btn.setFlat(True)
        self._dismiss_btn.setFixedSize(24, 24)
        self._dismiss_btn.setToolTip("Dismiss")
        # QA-05: bound-method connection (no self-capturing lambda).
        self._dismiss_btn.clicked.connect(self._on_dismiss_clicked)
        layout.addWidget(self._dismiss_btn)

        # Current announcement hash — set by set_announcement, carried in dismissed Signal.
        self._current_hash: str = ""

        # Start hidden; caller drives visibility via set_announcement / clear.
        self.setVisible(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_announcement(self, first_segment: str, announcement_hash: str) -> None:
        """Display ``first_segment`` as the banner text.

        Pipe characters in ``first_segment`` are replaced by ``\\n`` so
        QLabel's ``wordWrap=True`` wraps at pipe boundaries (GBS-MARQ-04 / D-14).

        If ``first_segment.strip()`` is empty, the banner is hidden and this
        method returns early without updating the hash cache.

        Args:
            first_segment: Whitespace-trimmed first marquee segment (from
                ``parse_marquee``). May contain ``|`` pipe characters for
                multi-line wrap hints.
            announcement_hash: SHA-256 hex digest of the original
                ``first_segment`` (UTF-8 encoded). Carried as the
                ``dismissed`` Signal payload.
        """
        if not first_segment.strip():
            self.clear()
            return

        # Replace internal pipe characters with newlines for multi-line wrapping.
        wrapped = first_segment.replace("|", "\n")
        self._label.setText(wrapped)
        self._current_hash = announcement_hash
        self.setVisible(True)

    def clear(self) -> None:
        """Hide the banner without clearing the hash cache.

        The hash cache is preserved so callers (NowPlayingPanel._on_marquee_ready)
        can detect whether the current hash was dismissed or merely absent.

        Note: ``_current_hash`` is NOT reset here — the caller controls cache
        lifecycle through ``_dismissed_announcement_hashes``.
        """
        self.setVisible(False)
        self._label.setText("")

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _on_dismiss_clicked(self) -> None:
        """Emit ``dismissed(announcement_hash)`` and hide the banner.

        The hash is emitted so NowPlayingPanel's ``_on_banner_dismissed`` slot
        can add it to ``_dismissed_announcement_hashes`` before this banner
        hides itself via ``clear()``.

        QA-05: bound-method slot connected in ``__init__``; no lambda.
        """
        self.dismissed.emit(self._current_hash)
        self.clear()
