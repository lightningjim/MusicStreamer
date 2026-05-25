"""Phase 84 / D-11 / Pattern 4 — source-grep hygiene gate for playbin3
property names + flags|0x100 regression lock.

This file is the static-analysis half of the Phase 84 mock-blind-spot
guardrail documented in MEMORY ``feedback_gstreamer_mock_blind_spot.md``:

  > pipeline mocks pass through any ``pipeline.emit(...)`` call; add
  > source-level grep gates to ban legacy ``playbin`` 1.x signals on
  > playbin3 code paths.

Three invariants are pinned here:

  1. **Allowlist enforcement** — every
     ``self._pipeline.set_property(<NAME>, ...)`` callsite in
     ``musicstreamer/player.py`` must use a property name on the
     ``_ALLOWED_PIPELINE_PROPERTIES`` allowlist. New playbin3 properties
     must be added to the allowlist in the same commit as the callsite.

  2. **Banned-spellings rejection** — the underscore-form Python-ish
     spellings (``buffer_duration``, ``buffer_size``, ``connection_speed``)
     are silently no-op'd by playbin3 — it expects dash-form. The
     ``low-percent`` / ``high-percent`` queue2 knobs are Phase 78/84
     DEFERRED items; landing them without an explicit decision is a
     regression.

  3. **flags|0x100 regression lock** — ``musicstreamer/player.py`` must
     contain the literal ``flags | 0x100`` (GST_PLAY_FLAG_BUFFERING).
     Without this bit, playbin3 bypasses queue2 entirely and ALL
     buffer-duration / buffer-size writes are silently ignored — making
     every Phase 84 / D-10 / D-11 behavior invisible.

The tokenize-blanking pattern mirrors
``tests/test_db_connect_is_sole_connection_factory.py`` (Phase 80 source-
grep gate precedent) — STRING and COMMENT token ranges are blanked before
regex scanning so docstring/comment mentions of banned strings do not
false-positive.

Failure messages are grep-friendly per Pattern S-8: prefix with
``"Phase 84 / D-11 / Pattern 4 drift-guard FAIL:"`` and include the
offending file path + line number + remediation hint.

This test file is GREEN-by-coincidence on the current Wave 0 codebase —
the gate is structural / forward-looking (Wave 1 implementation must
keep it green). The flags|0x100 bit lives at ``player.py:325`` today; the
allowlist matches the current set_property callsites; no banned
spellings are present.
"""
from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import pytest


# Production package root, located relative to ``tests/``.
_MUSICSTREAMER_PKG = Path(__file__).resolve().parent.parent / "musicstreamer"
_PLAYER_PATH = _MUSICSTREAMER_PKG / "player.py"


# ----------------------------------------------------------------------
# Allowlist + banned set + regexes
# ----------------------------------------------------------------------

# Property names that may legitimately appear as the first arg to
# ``self._pipeline.set_property(...)`` in musicstreamer/player.py. Add to
# this set ONLY when a phase decision documents the addition; otherwise
# the gate fires.
_ALLOWED_PIPELINE_PROPERTIES = {
    "video-sink",
    "audio-sink",
    "buffer-duration",
    "buffer-size",
    "flags",
    "audio-filter",
    "uri",
    "volume",
}

# Banned legacy spellings — if any of these appear as the first arg to
# ``self._pipeline.set_property(...)`` the gate fires with a grep-friendly
# error. Five banned strings:
#   - buffer_duration / buffer_size : playbin 1.x Pythonic underscore forms;
#     silently no-op on playbin3 but pass through MagicMock pipelines.
#   - connection_speed              : same — dash-form is "connection-speed".
#   - low-percent / high-percent    : Phase 78/84 DEFERRED queue2 watermark
#     knobs; landing them without an explicit decision is a regression.
_BANNED_SPELLINGS = {
    "buffer_duration",
    "buffer_size",
    "connection_speed",
    "low-percent",
    "high-percent",
}

# IN-03 (Phase 84 code review): module-level invariant lock — a property name
# must NEVER appear on both the allowlist and the banned set. If a future
# commit drifts (e.g. adds "buffer_duration" to the allowlist by accident),
# this assert fires at import time so the gate's failure mode stays well-
# defined (allowlist + banned set tests would otherwise produce confusing
# overlapping diagnostics).
assert _ALLOWED_PIPELINE_PROPERTIES.isdisjoint(_BANNED_SPELLINGS), (
    "Phase 84 / D-11 / Pattern 4 drift-guard config FAIL: a property name "
    "appears on both _ALLOWED_PIPELINE_PROPERTIES and _BANNED_SPELLINGS: "
    f"{_ALLOWED_PIPELINE_PROPERTIES & _BANNED_SPELLINGS}. Fix by removing "
    "the duplicate from whichever set is wrong, then update the offending "
    "commit's phase decision to document the change."
)

# Matches ``self._pipeline.set_property("NAME", ...)`` or
# ``self._pipeline.set_property('NAME', ...)``. Strings / comments are
# blanked in ``_scan_setproperty_args`` before this regex runs, so
# docstring mentions of ``set_property(...)`` are intentionally ignored.
_SETPROPERTY_RE = re.compile(
    r"""self\._pipeline\.set_property\(\s*["']([^"']+)["']"""
)

# Matches the literal ``flags | 0x100`` (any internal whitespace). Strings
# and comments are blanked before this regex runs.
_FLAGS_BIT_RE = re.compile(r"flags\s*\|\s*0x100")


# ----------------------------------------------------------------------
# Tokenize-blanking helpers (mirrors test_db_connect_is_sole_connection_factory.py)
# ----------------------------------------------------------------------

def _blank_strings_and_comments(src: str) -> str:
    """Return ``src`` with all STRING and COMMENT token ranges blanked
    (replaced with spaces). Docstring / comment mentions of the patterns
    below are intentionally ignored — only executable code is scanned.

    If the file cannot be tokenized (e.g. a vendored chunk has a syntax
    error), return the raw text unchanged — drift-guard prefers false-
    positive over false-negative.
    """
    rows = [list(line) for line in src.splitlines()]
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except tokenize.TokenizeError:
        return src
    for tok in tokens:
        if tok.type not in (tokenize.STRING, tokenize.COMMENT):
            continue
        (start_row, start_col), (end_row, end_col) = tok.start, tok.end
        for ln in range(start_row, end_row + 1):
            if ln - 1 >= len(rows):
                continue
            row = rows[ln - 1]
            lo = start_col if ln == start_row else 0
            hi = end_col if ln == end_row else len(row)
            for j in range(lo, min(hi, len(row))):
                row[j] = " "
    return "\n".join("".join(r) for r in rows)


def _scan_setproperty_args(path: Path) -> list[tuple[int, str]]:
    """Scan ``path`` for ``self._pipeline.set_property("NAME", ...)``
    callsites. Returns a list of ``(1-based-line-number, property-name)``
    tuples found in executable code (STRING/COMMENT tokens are blanked
    before scanning).
    """
    src = path.read_text(encoding="utf-8")
    blanked = _blank_strings_and_comments(src)
    return [
        (i, m.group(1))
        for i, line in enumerate(blanked.splitlines(), 1)
        for m in _SETPROPERTY_RE.finditer(line)
    ]


def _scan_flags_bit(path: Path) -> int:
    """Return count of ``flags | 0x100`` literal occurrences in
    executable code (STRING/COMMENT tokens are blanked before scanning).
    """
    src = path.read_text(encoding="utf-8")
    blanked = _blank_strings_and_comments(src)
    return len(_FLAGS_BIT_RE.findall(blanked))


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------

def test_pipeline_setproperty_uses_only_allowed_names() -> None:
    """Phase 84 / D-11 / Pattern 4 drift-guard: every property name passed
    to ``self._pipeline.set_property(...)`` in musicstreamer/player.py
    must appear on the ``_ALLOWED_PIPELINE_PROPERTIES`` allowlist (or be
    in the banned set, which the sibling test catches separately for
    cleaner failure attribution).

    Adding a new playbin3 property? Add it to
    ``_ALLOWED_PIPELINE_PROPERTIES`` in this file in the SAME commit as
    the callsite — otherwise the gate fires.
    """
    assert _PLAYER_PATH.is_file(), (
        f"Phase 84 / D-11 / Pattern 4 drift-guard FAIL: expected "
        f"production source at {_PLAYER_PATH}; a missing file would "
        f"silently produce an empty scan result and mask real drift."
    )
    callsites = _scan_setproperty_args(_PLAYER_PATH)
    unknown = [
        (line, name) for line, name in callsites
        if name not in _ALLOWED_PIPELINE_PROPERTIES
        and name not in _BANNED_SPELLINGS
    ]
    assert not unknown, (
        f"Phase 84 / D-11 / Pattern 4 drift-guard FAIL: musicstreamer/"
        f"player.py contains self._pipeline.set_property(...) callsite(s) "
        f"with property name(s) not on the playbin3 allowlist: "
        f"{unknown}. Allowlist: {sorted(_ALLOWED_PIPELINE_PROPERTIES)}. "
        f"If this is a legitimate new playbin3 property, add it to "
        f"_ALLOWED_PIPELINE_PROPERTIES in this test file in the same "
        f"commit that introduces the callsite. See 84-RESEARCH §Pattern 4."
    )


def test_pipeline_setproperty_no_banned_legacy_spellings() -> None:
    """Phase 84 / D-11 / Pattern 4 drift-guard: musicstreamer/player.py
    must NOT contain banned legacy playbin 1.x spellings (underscore
    forms like ``buffer_duration``) or DEFERRED knobs (``low-percent`` /
    ``high-percent``) in ``self._pipeline.set_property(...)`` callsites.

    Banned spellings silently no-op on real playbin3 pipelines BUT pass
    through a MagicMock pipeline unchanged — behavioral tests with mocked
    pipelines cannot catch them. See MEMORY
    ``feedback_gstreamer_mock_blind_spot.md`` for the canonical write-up
    of why this static gate is mandatory.
    """
    callsites = _scan_setproperty_args(_PLAYER_PATH)
    bad = [(line, name) for line, name in callsites if name in _BANNED_SPELLINGS]
    assert not bad, (
        f"Phase 84 / D-11 / Pattern 4 drift-guard FAIL: musicstreamer/"
        f"player.py contains banned playbin 1.x / deferred property "
        f"name(s) in self._pipeline.set_property(...) callsites: {bad}. "
        f"Banned set: {sorted(_BANNED_SPELLINGS)}. "
        f"Underscore forms (e.g. 'buffer_duration') silently no-op on "
        f"playbin3 — it expects dash-form ('buffer-duration'). The "
        f"low-percent / high-percent knobs are Phase 78/84 DEFERRED; "
        f"landing them requires an explicit phase decision. "
        f"See 84-RESEARCH §Pattern 4 AND MEMORY "
        f"feedback_gstreamer_mock_blind_spot — pipeline mocks pass any "
        f"set_property call through unchanged, so behavioral tests "
        f"alone cannot catch this regression."
    )


def test_flags_buffering_bit_preserved() -> None:
    """Phase 16 / Phase 84 / D-10 invariant: musicstreamer/player.py must
    contain the literal ``flags | 0x100`` (GST_PLAY_FLAG_BUFFERING).
    Without this bit playbin3 bypasses queue2 entirely on live HTTP
    audio sources — ALL buffer-duration / buffer-size writes are
    silently ignored and decodebin3's internal multiqueue (~1s capacity)
    handles jitter against tiny defaults instead.

    This gate is independent of the spelling allowlist (separate test
    for clean failure attribution). It is the load-bearing bit that
    makes every Phase 84 D-10 / D-11 behavior visible — losing it
    silently breaks the entire phase.
    """
    count = _scan_flags_bit(_PLAYER_PATH)
    assert count >= 1, (
        f"Phase 84 / D-11 / Pattern 4 drift-guard FAIL: Phase 16 / "
        f"Phase 84 / D-10 invariant violated — musicstreamer/player.py "
        f"does not contain `flags | 0x100` (GST_PLAY_FLAG_BUFFERING) "
        f"in executable code. Without this bit, playbin3 bypasses "
        f"queue2 entirely and ALL buffer-duration / buffer-size writes "
        f"are silently ignored. See 84-RESEARCH §Standard Stack and "
        f"§D-11 Resolution. Restore the bit (currently at player.py:325) "
        f"or document an explicit deferral decision and update this "
        f"test to expect the new behavior."
    )
