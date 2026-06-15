"""Tests for musicstreamer.gbs_marquee — parse_marquee + fixture corpus (Plan 87-02).

All tests in this file are pure (no Qt, no HTTP, no DB).  They verify the
parser behaviour described in 87-RESEARCH.md §Pitfall #6 and the GBS-MARQ-07
fixture-count requirement (§Pitfall #8 relaxation allows synthetic samples).
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


def test_no_qt_import_in_module():
    """gbs_marquee.py must not import Qt — it is a pure-Python parser module."""
    import ast
    import importlib.util

    spec = importlib.util.find_spec("musicstreamer.gbs_marquee")
    assert spec is not None, "musicstreamer.gbs_marquee not found"
    src = pathlib.Path(spec.origin).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [
                a.name for a in getattr(node, "names", [])
            ]
            module = getattr(node, "module", "") or ""
            for n in names + [module]:
                assert "PySide6" not in n, f"Qt import found: {n}"
                assert "PyQt" not in n, f"Qt import found: {n}"
