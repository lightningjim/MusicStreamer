---
phase: 87-gbs-fm-marquee-themed-day-detection
plan: "07"
subsystem: gbs-marquee
tags:
  - gbs.fm
  - themed-day
  - logo-swap
  - gap-closure
  - cr-01
  - thread-safety
dependency_graph:
  requires:
    - 87-04 (GbsMarqueeWorker._on_first_gbs_bind, _fetch_logo_bytes, GBS_LOGO_BASELINE_HASHES,
             NowPlayingPanel.set_themed_logo_override)
    - 87-03 (_fetch_marquee, GbsMarqueeWorker._on_tick)
  provides:
    - extract_leftmenulogo_url(html) pure helper in gbs_marquee.py
    - _fetch_logo_bytes(url: str) with User-Agent header in gbs_marquee.py
    - self._last_homepage_html cache in GbsMarqueeWorker (single fetch, no 2nd round-trip)
    - _on_first_gbs_bind rewritten to use dynamic URL + emit raw bytes (CR-01 cleared)
    - set_themed_logo_override accepting bytes|QPixmap (main-thread decode)
    - Anonymous _fetch_marquee with User-Agent header (URLError mitigation)
    - Pride fixture (2026-06-15_pride_homepage.html) + MANIFEST entry
  affects:
    - 87-HUMAN-UAT (Test 2 gap closed; Test 3 unblocked)
tech_stack:
  added: []
  patterns:
    - TDD (RED f544a8b9 Task1 / 9b7a82fd Task2)
    - D-12 hash-drift fallback (unchanged — any unseen hash is themed)
    - D-09 once-per-session gate (preserved — try/finally flip)
    - CR-01 thread-safety: worker emits raw bytes, main thread decodes to QPixmap
    - User-Agent on anonymous urllib fetches (URLError mitigation)
key_files:
  created:
    - tests/fixtures/gbs_marquee/2026-06-15_pride_homepage.html
  modified:
    - musicstreamer/gbs_marquee.py
    - musicstreamer/ui_qt/now_playing_panel.py
    - tests/test_gbs_marquee.py
    - tests/fixtures/gbs_marquee/MANIFEST.md
decisions:
  - "extract_leftmenulogo_url uses regex _LEFTMENULOGO_RE anchored on '#leftmenulogo' selector
     (not '#leftmenu') with [^'\"]+  URL capture to handle trailing /raw suffix (Pride 2026)"
  - "QPixmap import fully removed from gbs_marquee.py — worker is now GUI-free (CR-01 clean)"
  - "set_themed_logo_override accepts bytes|bytearray (new worker path) and QPixmap (D-09 re-apply
     from bind_station/_show_station_logo) — union type, no breaking change to internal callers"
  - "WR-02 (code review) applied: _on_first_gbs_bind only fires when marquee_ok=True (after
     successful parse), preventing keyword correlation against empty text on first-tick failure"
  - "GBS_LOGO_BASELINE_HASHES comment corrected: 'bd2b83...' is the DYNAMIC imgur #leftmenulogo
     hash, not logo_3.png; no canonical entry exists yet (accretion TODO still open)"
  - "User-Agent added to anonymous _fetch_marquee branch and _fetch_logo_bytes to mitigate
     CDN rejections (hypothesis for the intermittent gbs.marquee.fetch_failed URLError)"
metrics:
  duration: "~18 minutes"
  completed: "2026-06-15"
  tasks: 2
  files: 4
---

# Phase 87 Plan 07: Gap-Closure — Dynamic #leftmenulogo Resolution + CR-01 Summary

## What Was Built

**UAT Test 2 gap closed: the themed-day correlator now hashes the DYNAMIC
`#leftmenulogo` CSS logo URL (resolved from reused homepage bytes), not the
static `logo_3.png`. CR-01 cleared: QPixmap is built only on the main thread.**

### Task 1 — extract_leftmenulogo_url + Pride Fixture + Regression Tests (TDD)

`musicstreamer/gbs_marquee.py`:

- Added module-level compiled regex `_LEFTMENULOGO_RE`:
  ```
  r'#leftmenulogo\s*\{[^}]*background-image\s*:\s*url\([\'"]([^\'"]+)[\'"]\)'
  ```
  with `re.IGNORECASE | re.DOTALL`. Anchors on `#leftmenulogo` (not `#leftmenu`);
  captures `[^'"]+` so URLs ending in `/raw` (Pride 2026) are fully returned.
  Tested against: imgur form (`https://i.imgur.com/l27hhaY.png`), img.gbs.fm/raw
  form (`https://img.gbs.fm/NIgE8/yucEqesu87.png/raw`), absent rule (None), earlier
  sibling `#leftmenu` selector (skipped correctly), double quotes + whitespace.

- Added `extract_leftmenulogo_url(html: str) -> str | None` pure helper near
  `extract_noticearea_text`. No I/O, no Qt, no DB. Returns URL string or None.

- Changed `_fetch_logo_bytes()` to `_fetch_logo_bytes(url: str)`: now takes the
  resolved dynamic URL (any off-site host). Sends `User-Agent: gbs_api._USER_AGENT`
  header to avoid bare `Python-urllib/3.x` CDN rejections. D-18 quiet failures
  (WARN + None) preserved; `url=%s` log field now records the off-host URL.

- Added `User-Agent` header to anonymous branch of `_fetch_marquee` (same fix,
  same root cause — secondary URLError mitigation).

- Added `self._last_homepage_html: str = ""` in `__init__`. In `_on_tick`,
  `self._last_homepage_html = html or ""` cached before the noticearea parse,
  so `_on_first_gbs_bind` can reuse it with NO second homepage round-trip.

- Rewrote `_on_first_gbs_bind`:
  1. `logo_url = extract_leftmenulogo_url(self._last_homepage_html)` — resolves
     the dynamic URL from cached bytes (single fetch).
  2. If None: log `gbs.themed_day.logo_url_unresolved` WARN, return (gate flips).
  3. `logo_bytes = _fetch_logo_bytes(logo_url)` — fetches the off-site URL.
  4. `compute_logo_theme(logo_bytes, ...)` — unchanged.
  5. If `result.is_themed`: emit `self.themed_logo_ready.emit(logo_bytes)` — RAW
     BYTES, not QPixmap (CR-01 fix, folded in here for clean intermediate state).
  - Removed dead `logo_url = gbs_api.GBS_STATION_METADATA["logo_url"]` (IN-01).

- Applied WR-02 (code review): `_on_first_gbs_bind` now only fires when
  `marquee_ok=True` (marquee parse succeeded), preventing keyword correlation
  against empty text on a first-tick fetch failure.

- Corrected `GBS_LOGO_BASELINE_HASHES` comment block: `bd2b83...` is the DYNAMIC
  `#leftmenulogo` imgur hash (Memorial Day 2026), not `logo_3.png`. No canonical
  entry captured yet — any unseen hash drifts per D-12 (intentional).

`tests/fixtures/gbs_marquee/2026-06-15_pride_homepage.html`:
- Pride Month 2026 homepage fixture with `#leftmenulogo {background-image:
  url('https://img.gbs.fm/NIgE8/yucEqesu87.png/raw');}` plus other sibling
  background-image rules (`#leftmenu`, `#bottomcont`, `#bg1`, `#commentsbox`) to
  test resolver specificity.

`tests/fixtures/gbs_marquee/MANIFEST.md`: new Pride fixture row with
`capture_date=2026-06-15`, `theme=Pride`,
`leftmenulogo_url=https://img.gbs.fm/NIgE8/yucEqesu87.png/raw`,
`source=user-reported live URL (87-HUMAN-UAT Test 2)`.

`tests/test_gbs_marquee.py` — 6 new tests:
- `test_extract_leftmenulogo_url_imgur_form`: Memorial Day fixture → imgur URL.
- `test_extract_leftmenulogo_url_imggbsfm_raw_form`: Pride fixture → img.gbs.fm URL with /raw.
- `test_extract_leftmenulogo_url_absent_returns_none`: no rule → None.
- `test_extract_leftmenulogo_url_selects_correct_rule`: skips earlier `#leftmenu` url().
- `test_extract_leftmenulogo_url_quote_and_whitespace_tolerant`: double quotes + spaces.
- `test_pride_logo_drifts_from_baseline` (UAT Test 2 regression): Pride fixture URL resolved;
  bytes not in baseline drift → `is_themed=True`.
- Updated `test_once_per_session_gate`: fixture HTML now includes `#leftmenulogo` CSS rule;
  `_fake_fetch_logo_bytes` accepts `url` param (Rule 1 auto-fix).

### Task 2 — Main-Thread QPixmap Decode (CR-01) + User-Agent (TDD)

`musicstreamer/gbs_marquee.py`:
- `from PySide6.QtGui import QPixmap` import **fully removed** — gbs_marquee.py is
  now GUI-free. QPixmap appears only in comments/docstrings.

`musicstreamer/ui_qt/now_playing_panel.py`:
- `set_themed_logo_override(payload)` now accepts:
  - `bytes | bytearray`: decodes `QPixmap().loadFromData(bytes(payload), "PNG")` on
    the main thread. Decode failure → return (keep canonical logo, T-87-04-01).
  - `QPixmap`: passes through unchanged (D-09 re-apply callers: `bind_station` ~937,
    `_show_station_logo` ~2172 — both pass the cached QPixmap, no change needed there).
  - `None`: return immediately (defensive no-op; WR-04 noted as out of scope).
  - Cache result as `self._themed_logo_override` (always a QPixmap after decode).
  - Scaling + `logo_label.setPixmap(scaled)` logic unchanged.

`tests/test_gbs_marquee.py` — 3 new tests:
- `test_worker_emits_raw_bytes_not_qpixmap`: asserts emission is `bytes`, not QPixmap.
- `test_set_themed_logo_override_accepts_bytes`: bytes → QPixmap decode (Part 1);
  QPixmap re-apply (Part 2); confirms both paths work end-to-end.
- `test_anonymous_marquee_fetch_sends_user_agent`: asserts anonymous `_fetch_marquee`
  passes a `urllib.request.Request` with `User-Agent: gbs_api._USER_AGENT`.

## extract_leftmenulogo_url Regex — Forms Tested

| Form | URL | Resolved |
|------|-----|---------|
| Imgur (Memorial Day 2026) | `https://i.imgur.com/l27hhaY.png` | Yes |
| img.gbs.fm + /raw (Pride 2026) | `https://img.gbs.fm/NIgE8/yucEqesu87.png/raw` | Yes |
| Absent rule | (none) | None |
| Earlier sibling `#leftmenu` url() | (skipped) | Correctly not matched |
| Double quotes + spaces | `http://x/y.png` | Yes |

## CR-01 Status

**Cleared.** Evidence:
- `from PySide6.QtGui import QPixmap` is absent from `musicstreamer/gbs_marquee.py`.
- `_on_first_gbs_bind` emits `logo_bytes` (raw bytes), not a QPixmap.
- `set_themed_logo_override` decodes bytes → QPixmap inside the main-thread slot.
- `test_worker_emits_raw_bytes_not_qpixmap` asserts `isinstance(payload, (bytes, bytearray))`.
- UAT Test 3 (macOS/Windows thread-safety) can now be re-verified: the swap path
  fires (UAT Test 2 gap is closed), so CR-01 will be exercised on the next live verify.

## set_themed_logo_override Slot Shape (bytes-or-QPixmap Union)

```python
def set_themed_logo_override(self, payload) -> None:
    if payload is None:
        return
    if isinstance(payload, (bytes, bytearray)):
        pix = QPixmap()
        ok = pix.loadFromData(bytes(payload), "PNG")
        if not ok or pix.isNull():
            return
    else:
        pix = payload
        if pix.isNull():
            return
    self._themed_logo_override = pix
    # ... scale + setPixmap
```

Internal re-apply callers confirmed unchanged:
- `bind_station` (~937): `self.set_themed_logo_override(self._themed_logo_override)` — passes QPixmap.
- `_show_station_logo` (~2172): `self.set_themed_logo_override(self._themed_logo_override)` — passes QPixmap.

Both pass the cached QPixmap, which the `else` branch handles unchanged.

## User-Agent Change

The `User-Agent: MusicStreamer/2.0 (gbs_api)` header is now sent on:
- Anonymous branch of `_fetch_marquee` (previously bare `Python-urllib/3.x`).
- `_fetch_logo_bytes(url)` (new helper, always sends UA).

The cookie-authenticated path (`gbs_api._open_with_cookies`) already sent this header.
This is believed to fix the intermittent `gbs.marquee.fetch_failed url=https://gbs.fm/
error=URLError` observed at 10:20:18 in the UAT report. If the error recurs, the WARN
log now records the URL for further diagnosis — no over-engineering.

## GBS_LOGO_BASELINE_HASHES State

Still **1 themed entry** (no canonical). Comment corrected to note that `bd2b83...` is
the DYNAMIC `#leftmenulogo` imgur URL hash (not `logo_3.png`). No canonical entry has
been captured — this is intentional: any unseen hash drifts per D-12, which makes the
live Pride logo fire without needing a named entry. The baseline-accretion TODO
(`todos/2026-05-25-gbs-theme-hash-baseline-grow.md`) remains open.

## Single-Fetch Confirmation

`self._last_homepage_html` is populated in `_on_tick` with the same HTML bytes already
fetched for the marquee. `_on_first_gbs_bind` reads this cached string — no second
`_fetch_marquee()` or `urllib.request.urlopen(MARQUEE_URL)` call is made. Confirmed by
inspecting the rewrite of `_on_tick` and `_on_first_gbs_bind`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_once_per_session_gate fixture lacked #leftmenulogo rule**
- **Found during:** Task 1 GREEN run
- **Issue:** The existing test's `FIXTURE_HTML` had noticearea content but no
  `#leftmenulogo` CSS rule. After Plan 87-07's rewrite, `_on_first_gbs_bind`
  calls `extract_leftmenulogo_url(self._last_homepage_html)` first; without the
  rule, it logs `gbs.themed_day.logo_url_unresolved` and returns before calling
  `_fetch_logo_bytes`, so `logo_call_count[0]` stayed 0 instead of 1.
- **Fix:** Added `#leftmenulogo {background-image:url('...');}` rule to the fixture
  HTML; updated `_fake_fetch_logo_bytes` to accept the `url` param.
- **Files modified:** `tests/test_gbs_marquee.py`
- **Commit:** `f544a8b9` (Task 1)

**2. [Rule 2 - Missing critical functionality] WR-02 applied: marquee-ok gate**
- **Found during:** Task 1 implementation review (WR-02 from 87-REVIEW.md was a
  Warning item — applying it here was low-risk and directly in scope since
  `_on_tick` was already being modified).
- **Issue:** Original `_on_tick` fired `_on_first_gbs_bind` even when
  `_fetch_marquee()` returned None, burning the once-per-session gate on empty text.
- **Fix:** Added `marquee_ok` flag; `_on_first_gbs_bind` only fires when
  `marquee_ok=True` (successful parse).
- **Files modified:** `musicstreamer/gbs_marquee.py`
- **Commit:** `f544a8b9` (Task 1)

**3. [Implementer's choice] CR-01 emission change folded into Task 1 commit**
- The plan explicitly noted: "it is acceptable to land Steps 5 and the Task-2
  emission change together if cleaner." The raw-bytes emission (`self.themed_logo_ready
  .emit(logo_bytes)`) was written in Task 1's `_on_first_gbs_bind` rewrite to
  avoid a broken intermediate state. Task 2 then updated the slot to decode the
  bytes on the main thread.

## Known Stubs

None. All deliverables are fully implemented:
- `extract_leftmenulogo_url` — pure function, tested against 5 cases.
- `_fetch_logo_bytes(url)` — full urllib fetch with User-Agent and D-18 quiet failures.
- `_on_first_gbs_bind` — dynamic URL resolution, raw-bytes emission, once-per-session gate.
- `set_themed_logo_override` — bytes-or-QPixmap union, main-thread decode, D-09 re-apply.
- `self._last_homepage_html` — single-fetch cache.

## Threat Surface Scan

No new network endpoints, auth paths, file access, or schema changes beyond the plan's
threat model (T-87-07-01 through T-87-07-SC). The logo fetch now points at off-site
hosts (imgur, img.gbs.fm) — this is the intended fix and is covered by T-87-07-02/03.
No cookies are sent to off-host URLs (anonymous Request, no cookie jar).

## Self-Check: PASSED

- `[ -f tests/fixtures/gbs_marquee/2026-06-15_pride_homepage.html ]` — FOUND
- `grep -c "def extract_leftmenulogo_url" musicstreamer/gbs_marquee.py` → 1
- `grep -c "_LEFTMENULOGO_RE" musicstreamer/gbs_marquee.py` → 2 (compile + search)
- `grep -c "def _fetch_logo_bytes" musicstreamer/gbs_marquee.py` → 1
- `grep "def _fetch_logo_bytes" musicstreamer/gbs_marquee.py` → `def _fetch_logo_bytes(url: str)`
- `grep -c "from PySide6.QtGui import QPixmap" musicstreamer/gbs_marquee.py` → 0 (removed)
- `grep -c "loadFromData" musicstreamer/ui_qt/now_playing_panel.py` → 1 (main-thread decode)
- `grep -c "_last_homepage_html" musicstreamer/gbs_marquee.py` → 4 (init + assignment + 2 reads)
- `grep -c "gbs.themed_day.logo_url_unresolved" musicstreamer/gbs_marquee.py` → 1
- `grep -c "User-Agent" musicstreamer/gbs_marquee.py` → 2 (marquee anon + logo fetch)
- Task 1 commit `f544a8b9` — exists
- Task 2 commit `9b7a82fd` — exists
- `.venv/bin/python -m pytest tests/test_gbs_marquee.py tests/test_gbs_marquee_drift_guard.py` → 38/38 passed
