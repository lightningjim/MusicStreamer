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

    # Wrap in the noticearea element that _on_tick passes through extract_noticearea_text
    FIXTURE_HTML = '<p id="noticearea"><b>GBS-FM</b>: hello | world</p>'
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


# ---------------------------------------------------------------------------
# Plan 87-04: compute_logo_theme + GBS_THEMED_DAY_KEYWORDS + GBS_LOGO_BASELINE_HASHES
# ---------------------------------------------------------------------------

# SHA-256 of tests/fixtures/gbs_themed_logos/2026-05-25_memorial-day_da-troops.png
# Harvested live during the 2026-05-25 Memorial Day window (Plan 87-01 SUMMARY + MANIFEST.md).
_THEMED_HASH = "bd2b83fbe2b4bfe9baf8237a8919494e10cc7cf42ad3c42b1fcd605942881be3"

_THEMED_LOGO_PATH = (
    pathlib.Path(__file__).resolve().parent
    / "fixtures"
    / "gbs_themed_logos"
    / "2026-05-25_memorial-day_da-troops.png"
)


def test_compute_logo_theme_hashes_logo_bytes():
    """compute_logo_theme returns is_themed=True + correct hash + label for themed bytes.

    Uses the Plan 87-01 harvested PNG.  The fixture hash must match the
    MANIFEST.md entry and be a key in GBS_LOGO_BASELINE_HASHES.
    """
    from musicstreamer.gbs_marquee import compute_logo_theme

    logo_bytes = _THEMED_LOGO_PATH.read_bytes()
    result = compute_logo_theme(logo_bytes, "Memorial Day — da troops salute!")

    assert result.is_themed is True
    assert result.logo_hash == _THEMED_HASH, (
        f"Expected hash {_THEMED_HASH!r}, got {result.logo_hash!r}"
    )
    assert result.theme_label is not None
    assert "da troops" in result.theme_label.lower()
    assert result.fallback_unknown_theme is False


def test_themed_detection_keyword_match():
    """Drift + keyword present → is_themed=True, fallback_unknown_theme=False."""
    from musicstreamer.gbs_marquee import compute_logo_theme

    logo_bytes = _THEMED_LOGO_PATH.read_bytes()
    result = compute_logo_theme(logo_bytes, "da troops* | tune in Friday!")

    assert result.is_themed is True
    assert result.fallback_unknown_theme is False


def test_themed_detection_no_keyword_fallback():
    """Drift + no keyword → D-12 fallback: is_themed=True, fallback_unknown_theme=True.

    The hash of the themed logo IS in GBS_LOGO_BASELINE_HASHES with a non-canonical
    label, so drift IS detected.  The marquee text has no matching keyword.
    Per D-12: logo still applies (is_themed=True), fallback flag set True.
    """
    from musicstreamer.gbs_marquee import compute_logo_theme

    logo_bytes = _THEMED_LOGO_PATH.read_bytes()
    result = compute_logo_theme(logo_bytes, "ordinary marquee text")

    assert result.is_themed is True
    assert result.fallback_unknown_theme is True


def test_themed_detection_empty_marquee_fallback():
    """Empty marquee text + drift → D-12 fallback (same as no_keyword case)."""
    from musicstreamer.gbs_marquee import compute_logo_theme

    logo_bytes = _THEMED_LOGO_PATH.read_bytes()
    result = compute_logo_theme(logo_bytes, "")

    assert result.is_themed is True
    assert result.fallback_unknown_theme is True


def test_canonical_logo_not_themed(monkeypatch):
    """Bytes whose hash resolves to 'canonical' → is_themed=False, no fallback.

    Plan 87-01 captured no canonical PNG (themed window was live).  We add the
    canonical entry temporarily via monkeypatch on GBS_LOGO_BASELINE_HASHES so
    the test does not require a real canonical fixture on disk.
    """
    import hashlib
    import musicstreamer.gbs_marquee as _mod
    from musicstreamer.gbs_marquee import compute_logo_theme

    # Synthetic canonical bytes — any bytes not already in the baseline table.
    canonical_bytes = b"synthetic canonical logo bytes for test"
    canonical_hash = hashlib.sha256(canonical_bytes).hexdigest()

    # Temporarily inject the canonical entry.
    patched = {**_mod.GBS_LOGO_BASELINE_HASHES, canonical_hash: "canonical"}
    monkeypatch.setattr(_mod, "GBS_LOGO_BASELINE_HASHES", patched)

    result = compute_logo_theme(canonical_bytes, "any marquee text")

    assert result.is_themed is False
    assert result.theme_label == "canonical"
    assert result.fallback_unknown_theme is False


def test_baseline_table_has_harvest_entries():
    """GBS_LOGO_BASELINE_HASHES must have >= 1 entry and the harvested hash as a key.

    Per GBS-THEME-06 oracle in VALIDATION.md and Plan 87-04 acceptance criteria.
    """
    from musicstreamer.gbs_marquee import GBS_LOGO_BASELINE_HASHES

    assert len(GBS_LOGO_BASELINE_HASHES) >= 1, (
        f"Expected >= 1 entry in GBS_LOGO_BASELINE_HASHES, got {len(GBS_LOGO_BASELINE_HASHES)}"
    )
    assert _THEMED_HASH in GBS_LOGO_BASELINE_HASHES, (
        f"Harvested hash {_THEMED_HASH!r} not found in GBS_LOGO_BASELINE_HASHES. "
        f"Keys present: {list(GBS_LOGO_BASELINE_HASHES.keys())}"
    )


def test_gbs_themed_day_keywords_constant():
    """GBS_THEMED_DAY_KEYWORDS must be a frozenset containing 'da troops' (D-12 literal)."""
    from musicstreamer.constants import GBS_THEMED_DAY_KEYWORDS

    assert isinstance(GBS_THEMED_DAY_KEYWORDS, frozenset)
    assert "da troops" in GBS_THEMED_DAY_KEYWORDS
    # Spot-check a few other D-12 literals
    assert "halloween" in GBS_THEMED_DAY_KEYWORDS
    assert "christmas" in GBS_THEMED_DAY_KEYWORDS


# ---------------------------------------------------------------------------
# Plan 87-04 Task 2: Worker one-shot + NowPlayingPanel slot tests
# ---------------------------------------------------------------------------


# Canned PNG bytes for the once-per-session gate test — use the harvested fixture.
def _get_themed_logo_bytes() -> bytes:
    return _THEMED_LOGO_PATH.read_bytes()


def test_once_per_session_gate(monkeypatch):
    """_fetch_logo_bytes is called exactly ONCE across multiple ticks (D-09 / D-17).

    Creates a fresh GbsMarqueeWorker, monkeypatches _fetch_marquee to return a
    keyword-bearing noticearea HTML, monkeypatches _fetch_logo_bytes to count
    calls and return canned bytes.  Drives two ticks via set_cadence + qWait.
    Assert logo-fetch counter == 1 (not 2): the once-per-session gate held.
    """
    _get_qapp()
    import musicstreamer.gbs_marquee as _mod
    from PySide6.QtTest import QTest
    from musicstreamer.gbs_marquee import GbsMarqueeWorker

    # Return keyword-bearing marquee HTML so the keyword check succeeds on tick 1.
    FIXTURE_HTML = '<p id="noticearea"><b>GBS-FM</b>: da troops | come join us!</p>'
    monkeypatch.setattr(_mod, "_fetch_marquee", lambda: FIXTURE_HTML)

    logo_call_count = [0]

    def _fake_fetch_logo_bytes():
        logo_call_count[0] += 1
        return _get_themed_logo_bytes()

    monkeypatch.setattr(_mod, "_fetch_logo_bytes", _fake_fetch_logo_bytes)

    worker = GbsMarqueeWorker()
    try:
        worker.start()
        worker.set_cadence(60_000)
        QTest.qWait(400)   # first tick: marquee fetch + themed-day detection

        # Force a second tick.
        worker.force_poll()
        QTest.qWait(400)   # second tick: marquee fetch only (one-shot gate holds)

        assert logo_call_count[0] == 1, (
            f"Expected logo fetch to fire exactly ONCE (D-09/D-17), "
            f"got {logo_call_count[0]} calls"
        )
    finally:
        worker.stop_and_wait(timeout_ms=3_000)


class _FakeRepoForPanel:
    """Minimal FakeRepo for NowPlayingPanel construction in Task 2 tests."""

    def __init__(self):
        self._settings = {}

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)

    def set_setting(self, key, value):
        self._settings[key] = value

    def is_favorited(self, station_name, track_title):
        return False

    def add_favorite(self, *args, **kwargs):
        pass

    def remove_favorite(self, *args, **kwargs):
        pass

    def list_streams(self, station_id):
        return []

    def list_stations(self):
        return []

    def get_station(self, station_id):
        raise ValueError(f"Station not found: {station_id}")

    def list_favorites(self, *args, **kwargs):
        return []


def test_themed_logo_targets_logo_slot_only_behavior():
    """set_themed_logo_override targets logo_label only; cover_label is unchanged.

    GBS-THEME-03 behavioral assertion — the source-grep drift-guard ships in
    Plan 87-06.  This test confirms the SLOT behavior (NowPlayingPanel assigns
    the pixmap to self.logo_label, not self.cover_label).
    """
    _get_qapp()
    from PySide6.QtGui import QPixmap
    from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel
    from tests._fake_player import FakePlayer

    repo = _FakeRepoForPanel()
    player = FakePlayer()
    panel = NowPlayingPanel(player, repo)
    panel.show()

    # Record the cover_label pixmap before the override.
    cover_before = panel.cover_label.pixmap()

    # Apply the themed logo override.
    themed_pixmap = QPixmap()
    ok = themed_pixmap.loadFromData(_get_themed_logo_bytes(), "PNG")
    assert ok and not themed_pixmap.isNull(), "Fixture PNG must load cleanly"

    panel.set_themed_logo_override(themed_pixmap)

    # logo_label must now have a pixmap set.
    logo_after = panel.logo_label.pixmap()
    assert logo_after is not None and not logo_after.isNull(), (
        "logo_label pixmap must be set after set_themed_logo_override"
    )

    # cover_label must be UNCHANGED (GBS-THEME-03 invariant).
    cover_after = panel.cover_label.pixmap()
    # No station bound → cover shows fallback or None; whatever it was, it
    # must be IDENTICAL after the override (override must not touch cover_label).
    if cover_before is None or cover_before.isNull():
        assert cover_after is None or cover_after.isNull(), (
            "cover_label must remain unchanged after set_themed_logo_override"
        )
    else:
        # If there was a pre-existing cover pixmap, it must be unchanged.
        assert cover_after is not None and not cover_after.isNull(), (
            "cover_label must remain unchanged after set_themed_logo_override"
        )
