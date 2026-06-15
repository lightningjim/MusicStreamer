"""Phase 87 drift-guards — source-level enforcement of D-05, D-07, GBS-THEME-03/05,
D-18 invariants. Mirrors tests/test_fake_player_no_inline.py (Phase 77 D-17) and
tests/test_constants_drift.py:48-60 (Phase 61 D-02). Per
memory/feedback_gstreamer_mock_blind_spot.md — behavioral mocks can pass through
pipeline calls; only source-level grep catches construction-time pollution. Phase
87's correctness depends on these tests staying GREEN across all future commits.

Guards enforced:
    D-07 / GBS-MARQ-06 / Pitfall #1 (auth reuse):
        gbs_marquee.py MUST import from musicstreamer (gbs_api + paths); MUST NOT
        contain QWebEngineProfile, GBS_WEB_PROFILE_NAME, GBS_WEB_STORAGE_PATH,
        oauth_helper, or _GbsLoginWindow.

    D-05 / GBS-THEME-04 (no disk write):
        gbs_marquee.py MUST NOT call repo.set_setting, set_station_art, .save(, or
        open( — the themed logo is session-scoped in-memory only.

    GBS-THEME-03 (logo slot only):
        gbs_marquee.py MUST NOT reference cover_label, set_station_art, or
        set_cover — the themed logo override targets logo_label only.

    GBS-THEME-05 / D-18 (no toast):
        gbs_marquee.py AND announcement_banner.py MUST NOT call show_toast, libnotify,
        or QSystemTrayIcon — themed-day and banner detection surfaces no toast.

    Pitfall #7 (exec_ loop):
        gbs_marquee.py MUST contain self.exec_() in GbsMarqueeWorker.run — without
        the event loop the QTimer never fires.
"""
from __future__ import annotations

import re
from pathlib import Path

GBS_MARQUEE_SRC = Path(__file__).resolve().parent.parent / "musicstreamer" / "gbs_marquee.py"
ANNOUNCEMENT_BANNER_SRC = (
    Path(__file__).resolve().parent.parent
    / "musicstreamer"
    / "ui_qt"
    / "announcement_banner.py"
)


def _strip_comments(text: str) -> str:
    """Strip # comments from each source line.

    For each line, drops everything from the first ``#`` onward (defensive
    against ``# noqa``, banner comments, etc.). This prevents header-prose that
    mentions a banned identifier from causing a false-positive ban hit.

    Note: this approach also strips ``#`` inside string literals, but Phase 87
    source contains no banned-identifier substrings inside string literals so the
    defensive behaviour is acceptable.
    """
    lines = []
    for line in text.splitlines():
        idx = line.find("#")
        if idx >= 0:
            lines.append(line[:idx])
        else:
            lines.append(line)
    return "\n".join(lines)


def test_marquee_module_reuses_phase76_auth_only() -> None:
    """D-07 / GBS-MARQ-06 / Pitfall #1: gbs_marquee.py reuses Phase 76 auth path.

    Required imports check (on RAW text — imports are never comments):
        ``from musicstreamer import ... gbs_api`` AND
        ``from musicstreamer import ... paths``
        must both appear at module scope.

    Ban-list check (on comment-stripped text):
        No QWebEngineProfile, QWebEnginePage, GBS_WEB_PROFILE_NAME,
        GBS_WEB_STORAGE_PATH, oauth_helper, or _GbsLoginWindow.
    """
    src = GBS_MARQUEE_SRC.read_text(encoding="utf-8")

    # Required-imports check operates on raw source (imports are not comments).
    assert re.search(r"^from\s+musicstreamer\s+import\b.*\bgbs_api\b", src, re.M), (
        "gbs_marquee.py must import gbs_api from musicstreamer (D-07 / Pitfall #1)"
    )
    assert re.search(r"^from\s+musicstreamer\s+import\b.*\bpaths\b", src, re.M), (
        "gbs_marquee.py must import paths from musicstreamer (D-07 / Pitfall #1)"
    )

    stripped = _strip_comments(src)
    banned = [
        "QWebEngineProfile",
        "QWebEnginePage",
        "GBS_WEB_PROFILE_NAME",
        "GBS_WEB_STORAGE_PATH",
        "oauth_helper",
        "_GbsLoginWindow",
    ]
    for b in banned:
        assert b not in stripped, (
            f"gbs_marquee.py must not reference {b!r} (D-07 / Pitfall #1 — "
            "Phase 76 auth reuse means no parallel QtWebEngine/oauth_helper path)"
        )


def test_themed_logo_never_persists() -> None:
    """D-05 / GBS-THEME-04: themed logo is session-scoped; never written to disk.

    Ban-list:
        repo.set_setting — no SQLite write
        set_station_art  — no station-art table touch
        .save(           — no pixmap.save() to disk
        builtin open(    — no file IO of any kind in gbs_marquee.py
                           (checked as bare-word open, not urlopen/fdopen/etc.)
    """
    src = GBS_MARQUEE_SRC.read_text(encoding="utf-8")
    stripped = _strip_comments(src)

    # String-literal ban-list for repo/station-art/save surfaces.
    str_banned = [
        "repo.set_setting",
        "set_station_art",
        ".save(",
    ]
    for b in str_banned:
        assert b not in stripped, (
            f"gbs_marquee.py must not call {b!r} "
            "(D-05 — themed logo is session-scoped in-memory only; no disk write)"
        )

    # The builtin open( ban uses a word-boundary regex to avoid matching
    # urllib.request.urlopen( (which is NOT file IO).
    # \bopen\( matches: "open(", " open(", "=open(", but NOT "urlopen(" or "fdopen(".
    assert not re.search(r"\bopen\(", stripped), (
        "gbs_marquee.py must not call the builtin open() for file IO "
        "(D-05 — no disk writes; network opens via urllib.request.urlopen are permitted)"
    )


def test_themed_logo_targets_logo_slot_only() -> None:
    """GBS-THEME-03: themed logo override touches logo_label only; never cover slot.

    Ban-list:
        cover_label    — themed logo must not touch the cover art slot
        set_station_art — cross-coverage with D-05; no station-art table write
        set_cover      — catch-all for any cover-setter pattern
    """
    src = GBS_MARQUEE_SRC.read_text(encoding="utf-8")
    stripped = _strip_comments(src)
    banned = [
        "cover_label",
        "set_station_art",
        "set_cover",
    ]
    for b in banned:
        assert b not in stripped, (
            f"gbs_marquee.py must not reference {b!r} "
            "(GBS-THEME-03 — themed logo override targets logo_label only)"
        )


def test_no_toast_in_themed_day_path() -> None:
    """GBS-THEME-05 / D-18: no toast or notification surface in themed-day path.

    Both gbs_marquee.py AND announcement_banner.py are checked:
        show_toast     — no toast surface
        libnotify      — no native libnotify call
        QSystemTrayIcon — no tray icon instantiation
    """
    marquee_src = GBS_MARQUEE_SRC.read_text(encoding="utf-8")
    banner_src = ANNOUNCEMENT_BANNER_SRC.read_text(encoding="utf-8")
    marquee_stripped = _strip_comments(marquee_src)
    banner_stripped = _strip_comments(banner_src)

    banned = [
        "show_toast",
        "libnotify",
        "QSystemTrayIcon",
    ]
    for b in banned:
        assert b not in marquee_stripped, (
            f"gbs_marquee.py must not call {b!r} "
            "(GBS-THEME-05 / D-18 — themed-day detection surfaces no toast)"
        )
        assert b not in banner_stripped, (
            f"announcement_banner.py must not call {b!r} "
            "(GBS-THEME-05 / D-18 — banner surfaces no toast or notification)"
        )


def test_worker_run_calls_exec_loop() -> None:
    """Pitfall #7 source-grep: GbsMarqueeWorker.run() must call self.exec_().

    Without self.exec_() the worker thread's Qt event loop never starts, so
    the QTimer constructed in _apply_cadence_on_worker_thread never fires.
    This belt-and-suspenders grep complements the behavioral cadence test from
    Plan 87-03.
    """
    src = GBS_MARQUEE_SRC.read_text(encoding="utf-8")
    stripped = _strip_comments(src)
    assert "self.exec_()" in stripped, (
        "GbsMarqueeWorker.run must call self.exec_() (Pitfall #7 — without the "
        "exec_() event loop the QTimer never fires and the worker stalls)"
    )
