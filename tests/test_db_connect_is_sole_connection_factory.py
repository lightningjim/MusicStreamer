"""Phase 80 / BUG-10 / D-09 / D-12 — source-grep drift-guard.

Asserts that the production tree (``musicstreamer/**/*.py``) contains
**exactly one** ``sqlite3.connect(`` callsite, and that callsite lives in
``musicstreamer/repo.py`` (inside :func:`db_connect`). The ``tests/`` tree
is intentionally excluded from the gate (D-12) so the negative-proof test
in Plan 80-03 can use raw ``sqlite3.connect(":memory:")`` legally.

This is the *static-analysis half* of the drift-guard pair documented in
CONTEXT decision D-09 ("defense in depth"). The *runtime half* is the
post-SET PRAGMA read-back inside ``db_connect()`` (Plan 80-01).

  - Runtime drift-guard (Plan 80-01) catches:
    "someone refactored ``db_connect()`` and dropped the PRAGMA SET line"
    — surfaces at WARN with the literal
    ``PRAGMA foreign_keys is OFF after SET — drift detected``.

  - Source-grep drift-guard (THIS FILE) catches:
    "someone added a new production file that opens its own
    ``sqlite3.connect(...)`` and never touches ``db_connect``" — surfaces
    here at test-collection time with a grep-friendly failure message
    naming the offending file + line numbers.

Either guard alone has a blind spot the other covers. Project precedent
for source-level grep gates is documented in user memory
``feedback_gstreamer_mock_blind_spot.md``: "pipeline mocks pass through
any ``pipeline.emit(...)`` call; add source-level grep gates to ban
legacy ``playbin`` 1.x signals on playbin3 code paths."

Implementation note (Pitfall — docstring false-positives):
``musicstreamer/repo.py``'s :func:`db_connect` docstring legitimately
*mentions* ``sqlite3.connect(...)`` as inline-RST prose, which would
trip a naive line-grep. We therefore use Python's :mod:`tokenize` module
to blank out STRING and COMMENT token ranges in each source file before
regex-scanning — this leaves only executable code visible to the gate,
so docstring/comment mentions are intentionally ignored while real
call sites are caught.

Shape: mirrors ``tests/test_packaging_spec.py`` (Phase 65 source-grep
gate precedent) — module-scope path constant, module-scope fixture
returning pre-scanned data, individual ``def test_*`` functions
asserting on the fixture output with grep-friendly failure messages.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import pytest


# Production package root, located relative to ``tests/``.
_MUSICSTREAMER_PKG = Path(__file__).resolve().parent.parent / "musicstreamer"

# Matches both ``sqlite3.connect(`` and ``sqlite3.dbapi2.connect(`` — the
# latter reaches the same C function (RESEARCH knowledge gap #4,
# belt-and-suspenders, two characters of regex; zero false-positive risk
# in this codebase). String / comment ranges are blanked before this
# regex runs (see ``_scan_file``), so docstring mentions of
# ``sqlite3.connect(...)`` do not match.
_PATTERN = re.compile(r"sqlite3(\.dbapi2)?\.connect\(")


def _scan_file(path: Path) -> list[int]:
    """Return 1-based line numbers in ``path`` whose executable code
    matches :data:`_PATTERN`. STRING and COMMENT token ranges are blanked
    before scanning so that docstring / comment mentions of
    ``sqlite3.connect(...)`` are intentionally ignored.

    If the file cannot be tokenized (e.g. a syntax error in a vendored
    chunk), fall back to a raw line scan — better to over-report than
    silently miss a real callsite.
    """
    src = path.read_text(encoding="utf-8")
    rows = [list(line) for line in src.splitlines()]
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except tokenize.TokenizeError:
        # Fall back to raw line scan; drift-guard prefers false-positive
        # over false-negative.
        return [
            i for i, line in enumerate(src.splitlines(), 1) if _PATTERN.search(line)
        ]
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
    return [i for i, row in enumerate(rows, 1) if _PATTERN.search("".join(row))]


@pytest.fixture(scope="module")
def production_callsites() -> dict[Path, list[int]]:
    """Walk ``musicstreamer/**/*.py`` once and return a mapping of file
    paths to 1-based line numbers where the regex matched executable code
    (strings and comments are blanked before scanning).

    Files with no matches are omitted from the dict, so
    ``len(production_callsites)`` is the number of *files* containing at
    least one match, and ``sum(len(v) for v in production_callsites.values())``
    is the total *line* count of matches across the production tree.
    """
    assert _MUSICSTREAMER_PKG.is_dir(), (
        f"expected production package directory at {_MUSICSTREAMER_PKG}; "
        "a missing tree would silently produce an empty result and mask "
        "real drift — fail loudly instead."
    )
    callsites: dict[Path, list[int]] = {}
    for py_file in _MUSICSTREAMER_PKG.rglob("*.py"):
        line_numbers = _scan_file(py_file)
        if line_numbers:
            callsites[py_file] = line_numbers
    return callsites


def test_only_one_sqlite_connect_callsite_in_production(
    production_callsites: dict[Path, list[int]],
) -> None:
    """Phase 80 / BUG-10 / D-09 / D-12: the production tree must contain
    exactly one ``sqlite3.connect(`` (or ``sqlite3.dbapi2.connect(``)
    callsite. That sole callsite is the line inside :func:`db_connect`
    in ``musicstreamer/repo.py``; every other production caller MUST go
    through ``db_connect()`` so the ``PRAGMA foreign_keys = ON`` SET
    (and the post-SET drift-guard read-back) is applied on every
    connection.

    If this assertion fires, a new production file has opened its own
    SQLite connection — the runtime drift-guard at ``repo.py``
    (WARN literal: ``PRAGMA foreign_keys is OFF after SET — drift
    detected``) does NOT cover this case, because the new file never
    touches ``db_connect()``. The fix is either:

      1. Route the new code through ``db_connect()`` (preferred), or
      2. If a truly independent connection is required, replicate the
         PRAGMA SET + drift-guard read-back at the new callsite.

    The ``tests/`` tree is intentionally excluded (CONTEXT D-12) so the
    negative-proof test in Plan 80-03 can use raw
    ``sqlite3.connect(":memory:")`` legally.
    """
    total = sum(len(line_numbers) for line_numbers in production_callsites.values())
    assert total == 1, (
        "Phase 80 / BUG-10 / D-09 / D-12 drift-guard FAIL: expected "
        f"exactly 1 `sqlite3.connect(` callsite in the production tree "
        f"(`musicstreamer/**/*.py`), found {total}. Offending files and "
        f"line numbers: {{ {', '.join(f'{p}: {ln}' for p, ln in production_callsites.items())} }}. "
        "Either route the new caller through `musicstreamer.repo.db_connect()` "
        "(preferred — it sets `PRAGMA foreign_keys = ON;` and runs the "
        "runtime drift-guard `PRAGMA foreign_keys is OFF after SET — "
        "drift detected`) or, if a truly independent connection is "
        "required, replicate the PRAGMA SET + drift-guard read-back at "
        "the new callsite. The `tests/` tree is intentionally excluded "
        "from this gate (D-12) so the negative-proof test in Plan 80-03 "
        "can use raw `sqlite3.connect(':memory:')` legally."
    )


def test_sole_sqlite_connect_callsite_lives_in_repo_py(
    production_callsites: dict[Path, list[int]],
) -> None:
    """Phase 80 / BUG-10 / D-09 / D-12: the sole production ``sqlite3.connect(``
    callsite must live in ``musicstreamer/repo.py`` (specifically inside
    the :func:`db_connect` factory function).

    This is the structural half of the invariant. Test 1 above proves the
    count is 1; this test proves the *location* is correct. A future
    refactor that moved ``db_connect`` to a new module (e.g.
    ``musicstreamer/db.py``) without also updating this test would
    deliberately fail this assertion, prompting the maintainer to
    re-evaluate whether the move was intentional and to update both the
    canonical location reference in ``CONTEXT.md`` and this test.
    """
    files = list(production_callsites.keys())
    # Defensive — covered by test 1, but makes the indexing below safe.
    assert len(files) == 1, (
        "Phase 80 / BUG-10 / D-09 / D-12 drift-guard FAIL: expected "
        "exactly 1 production file containing a `sqlite3.connect(` "
        f"callsite, found {len(files)}: {[str(p) for p in files]}. "
        "See `test_only_one_sqlite_connect_callsite_in_production` "
        "for the primary count assertion."
    )
    sole_file = files[0]
    assert sole_file.name == "repo.py", (
        "Phase 80 / BUG-10 / D-09 / D-12 drift-guard FAIL: the sole "
        f"production `sqlite3.connect(` callsite lives in `{sole_file}`, "
        "not in `musicstreamer/repo.py` as required. The canonical "
        "connection factory is `musicstreamer.repo.db_connect()` (see "
        "CONTEXT.md `<canonical_refs>`); every production caller MUST "
        "route through it so `PRAGMA foreign_keys = ON;` is set on every "
        "connection. To fix: either move the callsite into "
        "`db_connect()` inside `repo.py`, or refactor the new code to "
        "call `db_connect()` instead. If `db_connect` itself has moved "
        "to a different module, update this test AND the canonical-refs "
        "block in CONTEXT.md together so the two stay in sync."
    )
