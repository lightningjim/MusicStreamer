"""GBS.FM marquee parser + worker (Phase 87, Plans 87-02 and 87-03).

Endpoint discovery (Plan 87-01 harvest — 2026-05-25):
  The marquee text lives in the **homepage HTML** at ``<p id="noticearea">``,
  NOT in the /ajax event stream.  Plan 87-01 §Critical research finding
  inverted the prior Pitfall #3 probability estimate (60% /ajax, 25% homepage).

Auth + cookies reuse (Phase 76 contract):
  Fetching the authenticated homepage uses the Phase 76 cookie jar via
  ``musicstreamer.gbs_api.load_auth_context()`` and the canonical cookie path
  ``musicstreamer.paths.gbs_cookies_path()``.  These imports are present at
  module scope so that Plan 87-06's source-grep drift-guard finds them even
  before Plan 87-03 wires the live fetch path.

Parse algorithm (GBS-MARQ-02 / §Pitfall #6):
  1. Extract ``<p id="noticearea">…</p>`` from raw HTML via
     ``extract_noticearea_text(html)`` (a pure helper in this module).
  2. Drop the leading ``GBS-FM: `` prefix produced by the ``<b>GBS-FM</b>:``
     markup pattern observed in the harvest.
  3. Call ``parse_marquee(plain_text)`` which splits on ``|``, strips each
     segment, and returns ``(first_segment, full_text)``.

Delimiter convention (Pitfall #6):
  The live harvest observed space-padded delimiters (`` | ``).  Both bare
  ``|`` and space-padded `` | `` are handled uniformly via per-segment
  ``.strip()`` — ``MARQUEE_DELIMITER`` records the canonical separator.

Worker (Plan 87-03):
  ``GbsMarqueeWorker`` (QThread) drives the 60s/5min/idle cadence state
  machine.  The worker is constructed once at GBS bind time and stays alive
  for the app lifetime (long-lived divergence from ``_AaLiveWorker``).
  Cadence changes cross the thread boundary via the ``cadence_changed_internal``
  Signal with ``Qt.QueuedConnection`` (Pitfall #7 bridge).
"""
from __future__ import annotations

import logging
import re
import urllib.error
import urllib.request

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal

from musicstreamer import gbs_api, paths  # noqa: F401  # drift-guard (Plan 87-06)

# Module-level named logger — wired to buffer-events.log via
# buffer_log.install_gbs_marquee_handler() (Plan 87-05 wires the call site).
_log = logging.getLogger("musicstreamer.gbs_marquee")

# ---------- URL constant (locked from Plan 87-01 harvest dissection) ----------

#: Homepage URL — the marquee text lives in ``<p id="noticearea">`` in the
#: homepage HTML response.  Confirmed by Plan 87-01 harvest; the /ajax cold
#: stream does NOT carry the themed-day text.
#:
#: TODO(87-03): probe at runtime — if ``extract_noticearea_text(html)``
#: returns empty, fall back to the /ajax endpoint as a secondary candidate.
MARQUEE_URL: str = f"{gbs_api.GBS_BASE}/"

# ---------- Delimiter constant (Pitfall #6) -----------------------------------

#: Canonical field separator used by the GBS.FM operator.  Per-segment
#: ``.strip()`` handles both the bare-pipe (``|``) and space-padded (`` | ``)
#: conventions so callers never need to normalise input before parsing.
MARQUEE_DELIMITER: str = "|"

# ---------- HTML extraction helper -------------------------------------------

# Matches the full <p id="noticearea">…</p> block, capturing the inner HTML.
# re.DOTALL is required because the element spans multiple lines in the harvest.
_NOTICEAREA_RE = re.compile(
    r'<p\s+id=["\']noticearea["\'][^>]*>(.*?)</p>',
    re.DOTALL | re.IGNORECASE,
)

# Strip any remaining HTML/XML tags after extracting inner text.
_TAG_RE = re.compile(r'<[^>]+>', re.DOTALL)

# The ``<b>GBS-FM</b>:`` prefix pattern (with optional surrounding whitespace).
_GBS_FM_PREFIX_RE = re.compile(r'^\s*GBS-FM\s*:\s*', re.IGNORECASE)


def extract_noticearea_text(html: str) -> str:
    """Extract and normalise the marquee plain text from raw GBS.FM homepage HTML.

    Steps:
      1. Find ``<p id="noticearea">`` content via regex.
      2. Strip all inner HTML tags (``<b>``, ``<br>``, ``<a>``, etc.).
      3. Drop the leading ``GBS-FM:`` prefix emitted by the site's markup.
      4. Collapse any leading/trailing whitespace on the result.

    Returns an empty string if the element is not found or the content is
    blank after stripping.  Plan 87-03's worker passes the result directly
    to ``parse_marquee()``.

    Args:
        html: Raw HTML bytes decoded to str (UTF-8 assumed; the homepage
              Content-Type header confirms UTF-8).

    Returns:
        Plain-text marquee string, or ``""`` if not found.
    """
    if not html:
        return ""
    m = _NOTICEAREA_RE.search(html)
    if not m:
        return ""
    inner = m.group(1)
    # Strip tags, then normalise whitespace runs caused by block-level elements.
    plain = _TAG_RE.sub(" ", inner)
    # Collapse runs of whitespace (newlines produced by <br> → " ") into single spaces.
    plain = re.sub(r'[ \t]+', ' ', plain)
    # Newlines become spaces (the element spans multiple lines in the harvest).
    plain = plain.replace("\n", " ").replace("\r", "")
    plain = plain.strip()
    # Drop the operator's leading "GBS-FM:" prefix.
    plain = _GBS_FM_PREFIX_RE.sub("", plain)
    return plain.strip()


# ---------- Core parser (GBS-MARQ-02 / D-13 / Pitfall #6) --------------------


def parse_marquee(raw_text: str) -> tuple[str, str]:
    """Return ``(first_segment, full_text)`` from a plain-text marquee string.

    ``raw_text`` is **plain text** (already HTML-stripped via
    ``extract_noticearea_text()`` or a synthetic fixture).  This function is
    a pure transformation: no I/O, no Qt, no DB.

    Delimiter handling (Pitfall #6):
      Splits on the literal ``|`` character.  Each segment is individually
      ``.strip()``-ed so that both bare ``|`` and space-padded `` | ``
      conventions produce identical first-segment results.

    Empty-segment handling (D-13):
      Segments that are empty or whitespace-only after stripping are skipped
      when selecting ``first_segment``; they do NOT affect ``full_text``.
      This defends against leading-pipe artefacts (e.g. ``"|leading|text"``).

    Args:
        raw_text: Plain-text marquee content (may be ``""`` or ``None``-safe
                  via ``raw_text or ""``.

    Returns:
        A ``(first_segment, full_text)`` tuple where:
          - ``first_segment``: the first non-empty pipe-segment, stripped.
            ``""`` if all segments are empty.
          - ``full_text``: the outer-stripped input (inner spacing preserved).
            ``""`` if the input is empty/whitespace-only.
    """
    full = (raw_text or "").strip()
    if not full:
        return ("", "")
    segments = [s.strip() for s in full.split(MARQUEE_DELIMITER) if s.strip()]
    first = segments[0] if segments else ""
    return (first, full)


# ---------- Network fetch helper (Plan 87-03 / D-11 auth ladder) --------------


def _fetch_marquee() -> str | None:
    """Fetch the GBS.FM homepage HTML and return the raw HTML string.

    Auth ladder (D-11):
      1. Try ``gbs_api.load_auth_context()`` — if non-None, use
         ``gbs_api._open_with_cookies`` (Phase 76 cookie jar).
      2. If ``load_auth_context()`` returns None, fall back to plain
         ``urllib.request.urlopen`` (anonymous, no cookies).

    Failure handling (D-18 — quiet failures, no toast, no UI surface):
      - ``GbsAuthExpiredError``: log ``gbs.marquee.auth_expired`` WARN; return
        None.  No anonymous retry (D-19: operator's server-side rate limiting
        handles abuse; client-side backoff adds state-machine complexity).
      - ``URLError | TimeoutError | OSError``: log ``gbs.marquee.fetch_failed``
        WARN with exception class name only (no marquee body text in log).
      - Generic ``Exception`` belt-and-suspenders: same ``fetch_failed`` WARN.

    Returns:
        Raw HTML string (UTF-8, errors=replace) or None on any failure.
    """
    auth = gbs_api.load_auth_context()
    try:
        if auth is not None:
            with gbs_api._open_with_cookies(
                MARQUEE_URL, auth, timeout=gbs_api._TIMEOUT_READ
            ) as resp:
                return resp.read().decode("utf-8", errors="replace")
        else:
            with urllib.request.urlopen(
                MARQUEE_URL, timeout=gbs_api._TIMEOUT_READ
            ) as resp:
                return resp.read().decode("utf-8", errors="replace")
    except gbs_api.GbsAuthExpiredError:
        _log.warning("gbs.marquee.auth_expired url=%s", MARQUEE_URL)
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        _log.warning(
            "gbs.marquee.fetch_failed url=%s error=%s",
            MARQUEE_URL,
            exc.__class__.__name__,
        )
        return None
    except Exception as exc:  # noqa: BLE001  # belt-and-suspenders (T-87-03-06)
        _log.warning(
            "gbs.marquee.fetch_failed url=%s error=%s",
            MARQUEE_URL,
            exc.__class__.__name__,
        )
        return None


# ---------- QThread worker (Plan 87-03 / D-15 long-lived shape) ---------------


class GbsMarqueeWorker(QThread):
    """Long-lived QThread that owns its own QTimer and drives the cadence machine.

    Architecture (D-15):
      Constructed once at GBS bind time; lives for the app lifetime.  Unlike
      ``_AaLiveWorker`` which spawns per poll cycle, this worker stays alive and
      transitions between cadence modes via the ``cadence_changed_internal`` Signal
      bridge (Pitfall #7).  The bridge is necessary because ``QTimer`` objects must
      be started/stopped on the thread they were created on.

    Cadence state machine (D-16):
      - 60 000 ms while GBS is playing
      - 300 000 ms while GBS is not playing
      - 0 (idle / paused) — timer stopped

    Thread safety:
      ``set_cadence()`` and ``force_poll()`` are safe to call from any thread
      (they only emit signals).  All timer + urllib logic runs on the worker thread.

    Signals:
      marquee_ready(first_segment: str, full_text: str):
        Emitted after each successful parse.  ``first_segment`` is for the
        announcement banner (Plan 87-05); ``full_text`` is for themed-day
        keyword search (Plan 87-04).
      themed_logo_ready(pixmap: object):
        Declared here for forward-compatibility (Plan 87-04 emits this).
        Carries a ``QPixmap`` or None.
      cadence_changed_internal(ms: int):
        Internal cross-thread bridge — DO NOT emit from user code.
    """

    themed_logo_ready = Signal(object)   # QPixmap or None — Plan 87-04 emits
    marquee_ready = Signal(str, str)     # (first_segment, full_text)
    cadence_changed_internal = Signal(int)  # ms — cross-thread cadence bridge

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer: QTimer | None = None
        self._themed_day_detected_this_session: bool = False
        self._last_full_marquee_text: str = ""
        self._interval_ms: int = 0
        # Pitfall #7 bridge: set_cadence() emits this from any thread;
        # Qt.QueuedConnection guarantees delivery to the worker-thread slot
        # AFTER exec_() is running in run().
        self.cadence_changed_internal.connect(
            self._apply_cadence_on_worker_thread, Qt.QueuedConnection
        )

    def set_cadence(self, ms: int) -> None:
        """Set poll cadence from any thread (0 = pause; >0 = restart interval).

        Emits ``cadence_changed_internal`` which is delivered via
        ``Qt.QueuedConnection`` to ``_apply_cadence_on_worker_thread`` running
        on the worker thread.  Safe to call before ``start()`` — the signal
        will queue and deliver once ``exec_()`` starts.
        """
        self.cadence_changed_internal.emit(int(ms))

    def force_poll(self) -> None:
        """Request an immediate tick from any thread.

        Emits ``cadence_changed_internal`` with the current interval (or 60 000
        if not yet set).  The worker-thread slot will restart the timer at 0
        (immediate tick) while preserving the ongoing cadence.

        Used by tests to skip real-time waits.
        """
        self.cadence_changed_internal.emit(self._interval_ms or 60_000)

    def _apply_cadence_on_worker_thread(self, ms: int) -> None:
        """Slot — runs on worker thread via QueuedConnection.

        Lazy-constructs QTimer on first call (ensures the timer is created on
        the worker thread, which is required for timer events to fire correctly).
        """
        if self._timer is None:
            self._timer = QTimer()
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._on_tick)
        if ms == 0:
            self._timer.stop()
            self._interval_ms = 0
        else:
            self._interval_ms = ms
            self._timer.start(0)  # immediate first tick after cadence change

    def _on_tick(self) -> None:
        """Timer callback — runs on worker thread.

        Calls ``_fetch_marquee()`` (blocking urllib call — safe on worker thread),
        parses the HTML, emits ``marquee_ready``, and reschedules the timer.
        """
        try:
            html = _fetch_marquee()
            if html is not None:
                plain = extract_noticearea_text(html)
                if plain:
                    first, full = parse_marquee(plain)
                    self._last_full_marquee_text = full
                    self.marquee_ready.emit(first, full)
        except Exception as exc:  # noqa: BLE001  # belt-and-suspenders (T-87-03-06)
            _log.warning(
                "gbs.marquee.fetch_failed url=%s error=%s",
                MARQUEE_URL,
                exc.__class__.__name__,
            )
        finally:
            # Always reschedule so the worker keeps running despite transient failures.
            if self._timer is not None and self._interval_ms > 0:
                self._timer.start(self._interval_ms)

    def current_interval_ms(self) -> int:
        """Return the current cadence interval in milliseconds (test affordance)."""
        return self._interval_ms

    def stop_and_wait(self, timeout_ms: int = 5_000) -> bool:
        """Stop the worker and wait for the thread to finish.

        Calls ``quit()`` (posts a quit event to the worker's event loop) then
        ``wait(timeout_ms)``.  Returns True if the thread exited within timeout.
        Called from main_window closeEvent (Plan 87-05 wires the call site).
        """
        self.quit()
        return self.wait(timeout_ms)

    def run(self) -> None:
        # CRITICAL (Pitfall #7 — 87-RESEARCH.md §Pitfall #7):
        # exec_() drives the worker thread's Qt event loop.  Without it,
        # the QTimer constructed in _apply_cadence_on_worker_thread never
        # fires because there is no event loop to dispatch its timeout signal.
        # A run() body of `pass` or `while True: time.sleep()` is a regression.
        self.exec_()
