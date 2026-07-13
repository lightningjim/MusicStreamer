---
phase: 87-gbs-fm-marquee-themed-day-detection
reviewed: 2026-06-15T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - musicstreamer/gbs_marquee.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - tests/test_gbs_marquee.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 87 (gap-closure 87-07): Code Review Report

**Reviewed:** 2026-06-15
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the gap-closure changes in plan 87-07: the dynamic `#leftmenulogo`
URL resolver (`extract_leftmenulogo_url`), the homepage-bytes caching
(`_last_homepage_html`), the CR-01 raw-bytes / dual-accept slot
(`set_themed_logo_override`), the WR-02 marquee-success gate, and the
User-Agent addition. The CR-01 fix is correct and well-tested: the worker emits
raw `bytes`, the QPixmap is built on the main thread, and the dual-accept slot
robustly handles `None`, bad/empty bytes (decode-fail early-return), and the
cached-QPixmap re-apply path. The full suite (33 tests) passes under
`.venv/bin/python`.

Two real issues survived the adversarial pass. (1) The WR-02 fix coupled
themed-logo detection to marquee-text parse success, which silently suppresses
the logo override on a themed homepage that lacks a `<p id="noticearea">`
element — a behavioral regression against D-12's keyword-independent fallback.
(2) `_fetch_logo_bytes` passes the page-derived URL straight to
`urllib.request.urlopen`, which accepts `file://` (verified: reads local files)
and `ftp://` schemes — an unbounded-scheme SSRF / local-file-read surface,
bounded in impact by the HTTPS trust in gbs.fm and the fact that bytes are only
hashed/displayed, never exfiltrated.

The ReDoS concern raised in the plan does NOT survive: `_LEFTMENULOGO_RE` uses
only linear `[^}]*` / `[^'"]+` classes with no nested quantifiers; 200k-char
pathological inputs return in ~1-11 ms. The regex correctly anchors on
`#leftmenulogo` (rejects `#leftmenulogohover`, skips a sibling `#leftmenu`
url(), handles minified no-space CSS and both quote styles, and stops `[^}]*`
at the first `}` so it never leaks a later rule's url()).

## Warnings

### WR-01: Themed-logo detection is now gated on noticearea-text parse success (D-12 fallback bypassed)

**File:** `musicstreamer/gbs_marquee.py:580-595`
**Issue:** In `_on_tick`, the WR-02 fix changed the one-shot trigger from
`if not self._themed_day_detected_this_session` (pre-87-07, commit `b9957e67`)
to `if marquee_ok and not self._themed_day_detected_this_session`. `marquee_ok`
is only `True` when `extract_noticearea_text(html)` returns a non-empty string.
Consequently, if the homepage is fetched successfully and contains a themed
`#leftmenulogo {background-image:url(...)}` rule but the `<p id="noticearea">`
element is absent or empty, `_on_first_gbs_bind()` is never called and the
themed logo never applies. This contradicts D-12, whose fallback
(`fallback_unknown_theme`) explicitly applies the logo *regardless of keyword
presence* — empty/absent marquee text is supposed to take the fallback path,
not suppress detection entirely. WR-02's stated intent was only to avoid
scanning empty text for keywords; an empty scan simply yields no keyword match,
which D-12 already handles. The gate over-corrects and couples two independent
features (announcement text vs. logo theming).
**Fix:** Gate the themed-logo one-shot on a successful homepage fetch, not on
marquee-text success. Track them separately:
```python
# in _on_tick, after self._last_homepage_html = html or ""
fetch_ok = html is not None
marquee_ok = False
if fetch_ok:
    plain = extract_noticearea_text(html)
    if plain:
        first, full = parse_marquee(plain)
        self._last_full_marquee_text = full
        self.marquee_ready.emit(first, full)
        marquee_ok = True
# Logo detection only needs the homepage bytes (the URL lives in the CSS),
# not the marquee text — D-12 handles the empty-text case via the fallback path.
if fetch_ok and not self._themed_day_detected_this_session:
    self._on_first_gbs_bind()
```
(`_on_first_gbs_bind` already tolerates empty `_last_full_marquee_text`: it
takes the D-12 fallback branch.)

### WR-02: `_fetch_logo_bytes` accepts arbitrary URL schemes (file://, ftp://) from page-derived input

**File:** `musicstreamer/gbs_marquee.py:399-404` (resolver: `gbs_marquee.py:248-272`)
**Issue:** `extract_leftmenulogo_url` returns whatever string sits inside the
`url('...')` of the `#leftmenulogo` rule with no scheme validation
(verified: `url('file:///etc/passwd')` and `url('javascript:...')` are returned
verbatim). `_fetch_logo_bytes` then hands that string directly to
`urllib.request.urlopen`, which honors `file://` and `ftp://`. I confirmed
`urllib.request.urlopen(Request("file:///tmp/x", headers=...))` reads local
file contents. Because the URL is parsed from the gbs.fm homepage HTML (fetched
over HTTPS), exploitation requires control of that HTML (TLS MITM or a
compromised gbs.fm), and the read bytes are only SHA-256-hashed and rendered as
a 180x180 logo — never written to disk or exfiltrated — so impact is bounded.
But accepting non-HTTP(S) schemes is an unnecessary local-file-read / SSRF
surface that the plan explicitly asked to assess, and it is trivially closed.
**Fix:** Restrict to http/https before fetching (in the resolver or the fetch
helper):
```python
from urllib.parse import urlparse

def extract_leftmenulogo_url(html: str) -> str | None:
    if not html:
        return None
    m = _LEFTMENULOGO_RE.search(html)
    if not m:
        return None
    url = m.group(1)
    if urlparse(url).scheme not in ("http", "https"):
        _log.warning("gbs.themed_day.logo_url_bad_scheme")  # no URL body in log
        return None
    return url
```

## Info

### IN-01: `themed_logo_ready` signal comment/docstring still says "QPixmap or None" after CR-01 switched to bytes

**File:** `musicstreamer/gbs_marquee.py:450` and `musicstreamer/gbs_marquee.py:455`
**Issue:** The class docstring line 450 (`Carries a ``QPixmap`` or None.`) and
the inline comment on the `Signal(object)` declaration at line 455
(`# QPixmap or None — Plan 87-04 emits`) both still describe the *pre-CR-01*
contract. After the CR-01 fix the worker emits raw `bytes`
(`gbs_marquee.py:550`), and constructing a QPixmap off the GUI thread is exactly
what CR-01 forbade. Leaving the comment describing the old contract risks a
future maintainer re-introducing the off-thread QPixmap.
**Fix:** Update both to reflect the bytes contract, e.g.
`themed_logo_ready = Signal(object)  # raw PNG bytes — main-thread slot builds QPixmap (CR-01)`
and amend the docstring `Signals:` block accordingly.

### IN-02: Redundant clause in `is_drift` expression

**File:** `musicstreamer/gbs_marquee.py:135`
**Issue:** `is_drift = (label_in_table is None) or (label_in_table != "canonical")`
is logically equivalent to `label_in_table != "canonical"` alone, because
`None != "canonical"` is already `True`. The first clause is dead/redundant.
Behavior is correct (matches D-12 verbatim, which is presumably why it is
written this way), so this is documentation-fidelity-only — flagging for
awareness, not a bug.
**Fix:** Optional — keep as-is for D-12 verbatim traceability, or simplify to
`is_drift = label_in_table != "canonical"` with a comment noting the
None-is-drift equivalence.

---

_Reviewed: 2026-06-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
