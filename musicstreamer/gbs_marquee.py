"""GBS.FM marquee parser + constants (Phase 87, Plan 87-02).

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

Module boundary:
  This file ships the **skeleton** only.  ``GbsMarqueeWorker`` (QThread) is
  Plan 87-03's deliverable and will be added to this same module.

  # Placeholder for GbsMarqueeWorker — Plan 87-03 fills this
"""
from __future__ import annotations

import re

from musicstreamer import gbs_api, paths  # noqa: F401  # drift-guard (Plan 87-06)

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
