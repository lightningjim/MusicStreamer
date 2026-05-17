"""Phase 77 D-16 drift-guard: FakePlayer must mirror every Signal declared on
musicstreamer.player.Player — by name AND by argument arity.

This file fails the moment a new Signal lands on Player without a parity
update in tests/_fake_player.py.

Recurrence pattern: the same FakePlayer-drift failure was logged across at
least 10 phases (51, 54, 55, 60.4, 61, 65, 66, 68, 71, 72, 72.1, 73) since
Phase 62 shipped underrun_recovery_started. This guard fires immediately when
a future Player Signal is added without updating tests/_fake_player.py.

Implementation notes:
  - Both the name-parity check and the arity check use regex source-parse of
    the production source file (musicstreamer/player.py) rather than importing
    the Player class at collection time.  This avoids the gi/GStreamer import
    requirement — musicstreamer/player.py imports ``gi`` at module level, and
    gi is not available in all test environments.  Source-parse is the
    established project convention (per RESEARCH §Pattern 1 and Pitfall 4;
    equivalent to the Phase 79 tests/test_yt_dlp_opts_drift.py precedent).
  - Arity check uses the same ``_grep_signal_decls`` helper as the name check,
    comparing argument-list text strings (catches Signal(object) vs
    Signal(int, int, int) drift — the audio_caps_detected gotcha at gbs/soma).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Regex: matches `NAME = Signal(ARGS)` at any indentation level.
# Captures: group(1) = signal name, group(2) = argument list text.
_SIGNAL_RE = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*Signal\(([^)]*)\)', re.M)


def _grep_signal_decls(path: Path) -> dict[str, str]:
    """Extract ``name = Signal(...)`` declarations from source file.

    Returns a mapping of ``{signal_name: argument_list_text}`` where
    argument_list_text is the stripped content inside the Signal() parens.
    """
    text = path.read_text(encoding="utf-8")
    return {m.group(1): m.group(2).strip() for m in _SIGNAL_RE.finditer(text)}


def test_fake_player_mirrors_every_player_signal():
    """Every Signal declared in player.py must be present in _fake_player.py (name parity).

    Uses source-grep of both files so the test does not need to import
    musicstreamer.player (which requires gi/GStreamer at module load time).
    """
    player_decls = _grep_signal_decls(ROOT / "musicstreamer" / "player.py")
    fake_decls = _grep_signal_decls(ROOT / "tests" / "_fake_player.py")
    player_names = set(player_decls)
    fake_names = set(fake_decls)
    missing = player_names - fake_names
    assert not missing, (
        f"FakePlayer missing Player signal(s): {sorted(missing)}. "
        f"Add `<name> = Signal(...)` to tests/_fake_player.py mirroring the "
        f"declaration in musicstreamer/player.py."
    )


def test_fake_player_signal_arity_matches_player():
    """Every shared signal must have IDENTICAL argument list.

    Catches Signal(object) vs Signal(int, int, int) drift — the
    audio_caps_detected gotcha present at gbs/soma sites before Phase 77.

    Uses regex source-parse NOT PySide6 metaobject introspection (Pitfall 4 —
    Shiboken metaobject inspection is fragile and version-dependent).
    """
    player_decls = _grep_signal_decls(ROOT / "musicstreamer" / "player.py")
    fake_decls = _grep_signal_decls(ROOT / "tests" / "_fake_player.py")
    mismatches = []
    for name, player_args in player_decls.items():
        if name not in fake_decls:
            continue  # name-parity test above already covers this
        if player_args != fake_decls[name]:
            mismatches.append(
                f"{name}: Player has `Signal({player_args})`, "
                f"FakePlayer has `Signal({fake_decls[name]})`"
            )
    assert not mismatches, (
        "FakePlayer signal arity drift:\n  " + "\n  ".join(mismatches)
    )
