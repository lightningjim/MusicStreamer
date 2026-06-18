"""Phase 87B drift-guards — GBS-TOKEN-02: no 'token' wording in add_song_zero_token.

Guards enforced:
    GBS-TOKEN-02: add_song_zero_token() MUST NOT contain the word 'token' in
    any string literal (label, tooltip, docstring, or error message).
    The function name identifier contains 'token' — that is allowed.
"""
from __future__ import annotations

import re
from pathlib import Path

GBS_API_SRC = Path(__file__).resolve().parent.parent / "musicstreamer" / "gbs_api.py"


def _strip_comments(text: str) -> str:
    """Strip # comments from each source line.

    For each line, drops everything from the first ``#`` onward (defensive
    against ``# noqa``, banner comments, etc.). This prevents header-prose that
    mentions a banned identifier from causing a false-positive ban hit.

    Note: this approach also strips ``#`` inside string literals, but Phase 87B
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


def test_add_song_zero_token_has_no_token_wording() -> None:
    """GBS-TOKEN-02: no 'token' word in add_song_zero_token() string literals.

    Scoped to the function body via regex extraction — gbs_api.py legitimately
    contains 'token' elsewhere (fetch_user_tokens, _TOKEN_RE, etc.).
    """
    src = GBS_API_SRC.read_text(encoding="utf-8")
    stripped = _strip_comments(src)

    m = re.search(
        r"def add_song_zero_token\b.*?(?=\ndef |\Z)", stripped, re.S
    )
    assert m, "add_song_zero_token() must exist in gbs_api.py (GBS-TOKEN-03)"
    fn_body = m.group(0)

    banned_patterns = [
        r'"[^"]*\btoken\b[^"]*"',   # "...token..." in double-quoted string
        r"'[^']*\btoken\b[^']*'",   # '...token...' in single-quoted string
    ]
    for pat in banned_patterns:
        assert not re.search(pat, fn_body, re.IGNORECASE), (
            f"add_song_zero_token() must not contain the word 'token' in "
            f"any string literal (GBS-TOKEN-02 — no affordance-economics framing)"
        )
