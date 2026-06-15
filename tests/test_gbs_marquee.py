"""Tests for musicstreamer.gbs_marquee — parse_marquee, fixture corpus, and
GbsMarqueeWorker (Plans 87-02 and 87-03).

Plan 87-02 tests are pure (no Qt, no HTTP, no DB).
Plan 87-03 tests exercise GbsMarqueeWorker (QThread) via Qt event-loop
infrastructure (QApplication + QTest.qWait for QueuedConnection delivery).
"""
from __future__ import annotations

import pathlib


# ---------------------------------------------------------------------------
# parse_marquee behavioural tests
# ---------------------------------------------------------------------------

def test_parse_marquee_empty():
    """Empty/None/whitespace-only input returns ("", "")."""
    from musicstreamer.gbs_marquee import parse_marquee

    assert parse_marquee("") == ("", "")
    assert parse_marquee("   ") == ("", "")


def test_parse_marquee_single_segment():
    """Single segment without any pipe delimiter."""
    from musicstreamer.gbs_marquee import parse_marquee

    assert parse_marquee("only one") == ("only one", "only one")
    assert parse_marquee("Welcome to GBS.FM") == ("Welcome to GBS.FM", "Welcome to GBS.FM")


def test_parse_marquee_pipe_split():
    """Space-padded pipe delimiter: first segment and full_text preserved."""
    from musicstreamer.gbs_marquee import parse_marquee

    first, full = parse_marquee("first | second | third")
    assert first == "first"
    assert full == "first | second | third"


def test_parse_marquee_bare_pipe_delimiter():
    """Bare pipe (no surrounding spaces) is also handled."""
    from musicstreamer.gbs_marquee import parse_marquee

    first, full = parse_marquee("first|second")
    assert first == "first"
    assert full == "first|second"


def test_parse_marquee_whitespace_padded():
    """Per-segment strip normalises surrounding whitespace; full_text strips outer only."""
    from musicstreamer.gbs_marquee import parse_marquee

    first, full = parse_marquee("  spaced  |  perpetual  ")
    # first segment must be stripped
    assert first == "spaced"
    # full_text strips outer whitespace only (outer .strip() on the raw input)
    # the returned full_text is raw_text.strip() — inner spacing preserved
    assert full == "spaced  |  perpetual"


def test_parse_marquee_leading_empty_segment():
    """Leading empty segment (from a leading `|`) is filtered out."""
    from musicstreamer.gbs_marquee import parse_marquee

    first, full = parse_marquee("|leading pipe|middle")
    # The leading empty segment is skipped; first non-empty segment is returned.
    assert first == "leading pipe"
    assert full == "|leading pipe|middle"


def test_parse_marquee_unicode():
    """Unicode characters pass through the parser unmodified."""
    from musicstreamer.gbs_marquee import parse_marquee

    first, full = parse_marquee("unicode • 你好 | next")
    assert first == "unicode • 你好"
    assert full == "unicode • 你好 | next"


def test_parse_marquee_real_day_specimen():
    """Memorial Day real marquee (HTML-stripped) parses correctly."""
    from musicstreamer.gbs_marquee import parse_marquee

    raw = (
        "da troops* | Tune in to A Queerdo's Storytime hosted by Venomous at "
        "4pm BST/10am CDT/8am PDT FRIDAY! | RIP Rob Base & Dick Parry & Dennis Locorriere"
    )
    first, full = parse_marquee(raw)
    assert first == "da troops*"
    assert full == raw


# ---------------------------------------------------------------------------
# GBS-MARQ-07 fixture count test
# ---------------------------------------------------------------------------

def test_fixture_count_ten_or_more():
    """Fixture directory must contain >= 10 data files (real-captured + synthetic).

    GBS-MARQ-07 requires >= 10 samples.  Pitfall #8 allows synthetic top-up.
    Files counted: *.txt + *.json + *.html (MANIFEST.md is excluded from count
    as it is a metadata file, not a sample).
    """
    fixture_dir = pathlib.Path(__file__).resolve().parent / "fixtures" / "gbs_marquee"
    data_files = (
        list(fixture_dir.glob("*.txt"))
        + list(fixture_dir.glob("*.json"))
        + list(fixture_dir.glob("*.html"))
    )
    assert len(data_files) >= 10, (
        f"Expected >= 10 fixture files, got {len(data_files)}: "
        + ", ".join(f.name for f in sorted(data_files))
    )


# ---------------------------------------------------------------------------
# Module-level constant smoke tests
# ---------------------------------------------------------------------------

def test_marquee_url_is_homepage():
    """MARQUEE_URL must point to the GBS.FM homepage (evidence from Plan 87-01)."""
    from musicstreamer.gbs_marquee import MARQUEE_URL

    assert "gbs.fm" in MARQUEE_URL.lower()
    # Per Plan 87-01 critical finding: marquee lives in homepage HTML, NOT /ajax
    assert "/ajax" not in MARQUEE_URL


def test_marquee_url_constant_type():
    """MARQUEE_URL must be a non-empty string."""
    from musicstreamer.gbs_marquee import MARQUEE_URL

    assert isinstance(MARQUEE_URL, str)
    assert len(MARQUEE_URL) > 0


# ---------------------------------------------------------------------------
# GbsMarqueeWorker tests (Plan 87-03) — Qt event-loop scaffolding
# ---------------------------------------------------------------------------

def _get_qapp():
    """Return the running QApplication or create one (module-scoped singleton)."""
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def test_cadence_state_machine():
    """GbsMarqueeWorker cadence changes are delivered via QueuedConnection.

    Pitfall #7 enforcement: the test exercises worker.start() → set_cadence() →
    QTest.qWait delivery → current_interval_ms() assertion sequence. If run()
    does NOT call self.exec_(), the QueuedConnection never delivers and
    _apply_cadence_on_worker_thread is never invoked — current_interval_ms()
    stays 0, failing the assertion. A test that passes without exec_() is
    insufficient (assumption in 87-PLAN-03).
    """
    _get_qapp()
    from PySide6.QtTest import QTest
    from musicstreamer.gbs_marquee import GbsMarqueeWorker

    worker = GbsMarqueeWorker()
    try:
        worker.start()
        assert worker.isRunning()

        # Transition to 60 000 ms (playing cadence)
        worker.set_cadence(60_000)
        QTest.qWait(200)  # allow QueuedConnection delivery
        assert worker.current_interval_ms() == 60_000

        # Transition to 300 000 ms (not-playing cadence)
        worker.set_cadence(300_000)
        QTest.qWait(200)
        assert worker.current_interval_ms() == 300_000

        # Pause (idle) — timer must stop
        worker.set_cadence(0)
        QTest.qWait(200)
        if worker._timer is not None:
            assert not worker._timer.isActive()
    finally:
        worker.stop_and_wait(timeout_ms=3_000)
        assert not worker.isRunning()


def test_force_poll_triggers_immediate_fetch(monkeypatch):
    """force_poll() causes _on_tick to fire and emit marquee_ready.

    monkeypatch replaces _fetch_marquee at module scope so the test does
    not make real network calls and exercises the fetch→parse→emit path
    deterministically.
    """
    _get_qapp()
    import musicstreamer.gbs_marquee as _mod
    from PySide6.QtTest import QTest
    from musicstreamer.gbs_marquee import GbsMarqueeWorker

    FIXTURE_HTML = "hello | world"
    monkeypatch.setattr(_mod, "_fetch_marquee", lambda: FIXTURE_HTML)

    emissions = []

    def _capture(first, full):
        emissions.append((first, full))

    worker = GbsMarqueeWorker()
    worker.marquee_ready.connect(_capture)
    try:
        worker.start()
        worker.set_cadence(60_000)
        QTest.qWait(300)  # wait for initial tick from set_cadence

        # Ensure at least one emission
        assert len(emissions) >= 1, "Expected at least one marquee_ready emission"
        assert emissions[0] == ("hello", "hello | world")
    finally:
        worker.stop_and_wait(timeout_ms=3_000)


def test_quiet_failure_logs_warn_no_toast(monkeypatch, caplog):
    """D-18: network failure logs gbs.marquee.fetch_failed WARN, no marquee_ready fired.

    The log line must NOT contain marquee body text (first_segment / full_text).
    """
    _get_qapp()
    import logging
    import urllib.error
    import musicstreamer.gbs_marquee as _mod
    from PySide6.QtTest import QTest
    from musicstreamer.gbs_marquee import GbsMarqueeWorker

    def _raise_url_error():
        raise urllib.error.URLError("simulated network failure")

    monkeypatch.setattr(_mod, "_fetch_marquee", _raise_url_error)

    emissions = []
    worker = GbsMarqueeWorker()
    worker.marquee_ready.connect(lambda f, t: emissions.append((f, t)))

    with caplog.at_level(logging.WARNING, logger="musicstreamer.gbs_marquee"):
        try:
            worker.start()
            worker.set_cadence(60_000)
            QTest.qWait(300)
        finally:
            worker.stop_and_wait(timeout_ms=3_000)

    # Assert no marquee_ready emission fired (D-18 — failure must not emit)
    assert emissions == [], f"Expected no marquee_ready emission, got: {emissions}"

    # Assert WARN log was emitted with the fetch_failed event name
    warn_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("gbs.marquee.fetch_failed" in r.message for r in warn_records), (
        f"Expected gbs.marquee.fetch_failed in WARN logs; got: {[r.message for r in warn_records]}"
    )

    # D-18: no marquee body text in log lines
    for rec in warn_records:
        assert "first_segment" not in rec.message
        assert "full_text" not in rec.message
        assert "raw_text" not in rec.message


def test_no_banned_identifiers_in_module():
    """gbs_marquee.py must not reference banned identifiers.

    Plan 87-02 shipped a pure-parser module with no Qt.  Plan 87-03 adds
    GbsMarqueeWorker (QThread), so PySide6 imports are now expected and the
    old Qt-absence check is retired.

    The drift-guard (Plan 87-06 pre-flight) checks that the Phase 76 WebEngine
    auth path (QWebEngineProfile, oauth_helper, GBS_WEB_PROFILE_NAME,
    GBS_WEB_STORAGE_PATH) and UI surface (show_toast, libnotify,
    QSystemTrayIcon) are NOT present — these would indicate scope creep.
    """
    spec = pathlib.Path(__file__).resolve().parent.parent / "musicstreamer" / "gbs_marquee.py"
    src = spec.read_text(encoding="utf-8")
    banned = [
        "QWebEngineProfile",
        "GBS_WEB_PROFILE_NAME",
        "GBS_WEB_STORAGE_PATH",
        "oauth_helper",
        "show_toast",
        "libnotify",
        "QSystemTrayIcon",
    ]
    for identifier in banned:
        assert identifier not in src, f"Banned identifier found in gbs_marquee.py: {identifier}"
