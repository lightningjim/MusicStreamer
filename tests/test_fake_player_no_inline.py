"""Phase 77 D-17 drift-guard: only tests/_fake_player.py may define a
FakePlayer subclass of QObject. Any test file that re-introduces an inline
FakePlayer class fails this guard immediately.

KNOWN RED until Plan 77-02 lands. This test ships intentionally failing at
Wave 1 close -- its purpose is to enumerate the 11 inline-FakePlayer(QObject)
sites that Plan 77-02 will migrate. Plan 77-06's full-suite phase gate is the
first commit that requires this test GREEN. If you see this test RED during
Wave 1, do NOT retry/revise -- Wave 1's success criterion is the
baseline-offender-count == 11 assertion in the orchestrator's <automated>
command, NOT pytest exit 0 on this specific file.

Mirrors the existing tests/test_yt_dlp_opts_drift.py source-grep pattern
(Phase 79) and tests/test_constants_drift.py:48-60 (Phase 61) rglob + ban-list
shape.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tests"
FAKE_PLAYER_RE = re.compile(r'^\s*class\s+_?FakePlayer\s*\(QObject\)', re.M)
ALLOWED = {"_fake_player.py"}


def test_no_inline_fake_player_subclass_in_tests():
    """Only tests/_fake_player.py may declare class FakePlayer(QObject).

    Any inline declaration elsewhere is a violation of D-17.  Each offender
    should ``from tests._fake_player import FakePlayer`` and delete its local
    copy.

    NOTE: intentionally RED at Wave 1 close (11 known offenders).  Plan 77-02
    migrates all 11 sites; Plan 77-06 full-suite gate is the first GREEN
    checkpoint.
    """
    offenders = []
    for py in sorted(ROOT.rglob("*.py")):
        if py.name in ALLOWED:
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if FAKE_PLAYER_RE.search(text):
            offenders.append(str(py.relative_to(ROOT.parent)))
    assert not offenders, (
        "Inline FakePlayer(QObject) class definitions found in tests/. "
        "Phase 77 D-17 invariant: only tests/_fake_player.py may declare this "
        "class. Each offender below should `from tests._fake_player import "
        "FakePlayer` and delete its local copy:\n  " + "\n  ".join(offenders)
    )
