# Phase 87B: GBS Zero-Token Single-Song Add — Pattern Map

**Mapped:** 2026-06-18
**Files analyzed:** 7 (5 modified, 1 created, 1 fixture directory created)
**Analogs found:** 7 / 7

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/gbs_api.py` | service | request-response | `gbs_api.submit()` at line 1129 (same file) | exact |
| `musicstreamer/ui_qt/now_playing_panel.py` | component | event-driven | `_gbs_relogin_btn` + `_refresh_gbs_visibility()` (same file, lines 717–722, 2962–3013) | exact |
| `musicstreamer/ui_qt/main_window.py` | controller | event-driven | `_open_gbs_search_dialog()` at line 1542 (same file) | exact |
| `musicstreamer/ui_qt/gbs_search_dialog.py` | component | request-response | Self — `submission_completed` signal at line 274 already exists; confirm-only | exact (no-change) |
| `tests/test_gbs_api.py` | test | CRUD | `test_submit_success_decodes_messages` at line 297 (same file) | exact |
| `tests/test_gbs_zero_token_drift_guard.py` | test | transform | `tests/test_gbs_marquee_drift_guard.py` lines 1–100 | exact |
| `tests/fixtures/gbs_zero_token/` | config | file-I/O | `tests/fixtures/gbs_marquee/` layout + `tests/fixtures/gbs/add_redirect_response.txt` | exact |

---

## Pattern Assignments

### `musicstreamer/gbs_api.py` (service, request-response) — ADD `add_song_zero_token()`

**Analog:** `gbs_api.submit()` at `musicstreamer/gbs_api.py:1129–1152`

**Module header / logger pattern** (lines 1–45):
```python
"""GBS.FM API client …"""
from __future__ import annotations

import http.cookiejar
import logging
# … other stdlib imports …
from musicstreamer import paths

_log = logging.getLogger(__name__)
```
The `_log` name is the target for the capture-hook `_log.warning(...)` call. `__name__` resolves to `musicstreamer.gbs_api`.

**Exception types to raise/propagate** (lines 82–87):
```python
class GbsApiError(Exception):
    """Generic GBS.FM API failure."""

class GbsAuthExpiredError(GbsApiError):
    """302 → /accounts/login/ — session cookie no longer authorizes."""
```
`add_song_zero_token()` must NOT catch `GbsAuthExpiredError` — let it propagate from `submit()` unchanged.

**Core analog: `submit()`** (lines 1129–1152):
```python
def submit(songid: int, cookies: http.cookiejar.MozillaCookieJar) -> str:
    """GET /add/<songid>; intercept 302; decode messages cookie; return text.

    Raises GbsAuthExpiredError if 302 Location is /accounts/login/.
    Returns "" if no messages cookie was set (caller can interpret as success
    with no message OR retry).
    """
    url = f"{GBS_BASE}/add/{int(songid)}"
    resp = _open_no_redirect(url, cookies, timeout=_TIMEOUT_WRITE)
    try:
        location = resp.headers.get("Location") or ""
        if "/accounts/login/" in location:
            raise GbsAuthExpiredError(f"Session expired (submit 302→login)")
        for cookie_line in (resp.headers.get_all("Set-Cookie") or []):
            if cookie_line.startswith("messages="):
                raw_val = cookie_line.split(";", 1)[0].split("=", 1)[1]
                msgs = _decode_django_messages(raw_val)
                return "; ".join(msgs)
        return ""
    finally:
        try:
            resp.close()
        except Exception:
            pass
```
`add_song_zero_token()` must call this function, not duplicate it. `_open_no_redirect`, `_decode_django_messages`, `GBS_BASE`, `_TIMEOUT_WRITE` must NOT appear inside the new wrapper.

**Structured no-PII warning pattern** (lines 227–230, from `_open_with_cookies`):
```python
_log.warning(
    "_open_with_cookies: non-login %s redirect to %r for %s (not followed)",
    getattr(resp, "status", None), location, url,
)
```
The capture hook follows this shape: `%`-style format string, positional args with scalar values only. No `cookies` object, no raw header values, no `songid` in a form that identifies the user.

**New function shape to write** (provisional, per RESEARCH Pattern 1):
```python
def add_song_zero_token(songid: int, cookies: http.cookiejar.MozillaCookieJar) -> str:
    """GBS-TOKEN-03: named add path, provisional contract per 87B-CONTEXT D-02.

    Wraps submit() with a no-PII capture hook (D-02 item 4 / 87-CONTEXT D-18).
    The server enforces any zero-token / one-at-a-time limit via the messages
    cookie (surfaced verbatim by the caller per D-07 / Pitfall 8).

    Raises GbsAuthExpiredError on session expiry (mirrors submit()).
    Returns "" if no messages cookie set (no message from server = success).
    """
    result = submit(songid, cookies)
    _capture_add_shape(songid=songid, message=result)
    return result


def _capture_add_shape(songid: int, message: str) -> None:
    """No-PII structured WARN log for D-02 capture hook.

    Logs: endpoint shape, message length/category.
    MUST NOT log: cookies, session values, raw cookie headers.
    """
    _log.warning(
        "gbs.add.zero_token_capture endpoint=/add/%s message_len=%d message_category=%s",
        int(songid),
        len(message),
        "empty" if not message else ("error" if "not enough" in message.lower() else "success"),
    )
```
**Placement:** Insert after `submit()` at line 1153 (before the `# ---------- Import orchestrator` comment). `add_song_zero_token` goes into the module docstring public-API list at line 10.

**GBS-TOKEN-02 constraint on docstrings:** The docstring above uses "zero-token" only in comment form that does NOT appear as a string literal in the function body. The drift-guard (see test file below) checks `r'"[^"]*\btoken\b[^"]*"'` and `r"'[^']*\btoken\b[^']*'"` — verify the docstring triple-quotes do NOT contain `token` as a bare word.

---

### `musicstreamer/ui_qt/now_playing_panel.py` (component, event-driven) — ADD button + `trigger_gbs_repoll()`

**Analog A: `_gbs_relogin_btn` construction** (lines 717–722):
```python
self._gbs_relogin_btn = QPushButton("Log in again", self._gbs_expiry_widget)
self._gbs_relogin_btn.clicked.connect(self._on_gbs_relogin_clicked)  # QA-05 bound method
_expiry_layout.addWidget(self._gbs_relogin_btn)

self._gbs_expiry_widget.setVisible(False)  # hidden-when-empty pattern
center.addWidget(self._gbs_expiry_widget)  # immediately after _gbs_playlist_widget
```
The "Add a song" button uses the same constructor pattern: `QPushButton("Add a song", self)`, bound-method signal connect, `setVisible(False)` initial state, `center.addWidget(...)`.

**Insertion point in `__init__`** (after line 722, before line 748):
```
# After:
center.addWidget(self._gbs_expiry_widget)   # line 722

# Insert here:
self._gbs_add_btn = QPushButton("Add a song", self)
self._gbs_add_btn.setVisible(False)
self._gbs_add_btn.clicked.connect(self._on_add_song_clicked)  # QA-05 bound method
center.addWidget(self._gbs_add_btn)

# Before:
self._gbs_vote_row = QHBoxLayout()          # line 748
```
Order is load-bearing: must go BEFORE `_gbs_vote_row` (added at line 767).

**Analog B: `_refresh_gbs_visibility()` — visibility gate to extend** (lines 2962–3013):
```python
def _refresh_gbs_visibility(self) -> None:
    is_gbs = (self._station is not None
              and self._station.provider_name == "GBS.FM")
    logged_in = self._is_gbs_logged_in()
    should_show = is_gbs and logged_in

    self._gbs_playlist_widget.setVisible(should_show)

    if should_show:
        self._gbs_expiry_widget.setVisible(False)
        # … poll start …
    else:
        self._gbs_poll_timer.stop()
        self._gbs_expiry_widget.setVisible(False)

    for btn in self._gbs_vote_buttons:
        btn.setVisible(should_show)
```
Add `self._gbs_add_btn.setVisible(should_show)` alongside the vote-button loop. The same `should_show` predicate (`is_gbs and logged_in`) is the D-05-compliant visibility gate.

**Analog C: `_on_gbs_relogin_succeeded()` — direct `_on_gbs_poll_tick()` call pattern** (lines 3181–3194):
```python
def _on_gbs_relogin_succeeded(self) -> None:
    self._gbs_expiry_widget.setVisible(False)
    self._gbs_relogin_btn.setEnabled(True)
    self._gbs_ajax_disabled = False
    self._gbs_label_source = None
    self._refresh_gbs_visibility()  # re-checks cookie existence → restarts poll
    if self._gbs_marquee_worker is not None:
        self._gbs_marquee_worker.force_poll()
```
`trigger_gbs_repoll()` uses the same direct call to `_on_gbs_poll_tick()`. New public method shape:
```python
def trigger_gbs_repoll(self) -> None:
    """Phase 87B: re-poll GBS active playlist after a song add.

    Called from main_window when GBSSearchDialog.submission_completed fires.
    Mirrors the direct _on_gbs_poll_tick() call in _on_gbs_relogin_succeeded
    (now_playing_panel.py:3192). Guard: only polls when worker idle and
    station is still GBS.FM bound.
    """
    if (
        self._station is not None
        and self._station.provider_name == "GBS.FM"
        and not self._gbs_poll_in_flight()
    ):
        self._gbs_poll_cursor = {}   # force full re-fetch so new song appears
        self._on_gbs_poll_tick()
```

**`_on_add_song_clicked` slot** — calls a signal or delegates to main_window. Preferred: emit an `add_song_requested = Signal()` (Option A from RESEARCH Pattern 2), which `main_window` connects to `_open_gbs_search_dialog`. Signal declaration mirrors `submission_completed` in `gbs_search_dialog.py:274`.

---

### `musicstreamer/ui_qt/main_window.py` (controller, event-driven) — WIRE `submission_completed`

**Analog: `_open_gbs_search_dialog()`** (lines 1542–1552):
```python
def _open_gbs_search_dialog(self) -> None:
    """Phase 60 D-08 / GBS-01e: open the search-and-submit dialog.

    Mirrors _open_discovery_dialog at line 704 (drops the player arg per
    CONTEXT.md "Phase 60's search dialog does NOT need preview play").
    submission_completed is not connected here — submitting a song does not
    touch the local library, so no station-list refresh is needed.
    """
    from musicstreamer.ui_qt.gbs_search_dialog import GBSSearchDialog
    dlg = GBSSearchDialog(self._repo, self.show_toast, parent=self)
    dlg.exec()
```
The amendment adds one `connect()` call before `dlg.exec()`:
```python
def _open_gbs_search_dialog(self) -> None:
    from musicstreamer.ui_qt.gbs_search_dialog import GBSSearchDialog
    dlg = GBSSearchDialog(self._repo, self.show_toast, parent=self)
    dlg.submission_completed.connect(
        self._now_playing_panel.trigger_gbs_repoll  # QA-05 bound method
    )
    dlg.exec()
```
The docstring must be updated to remove "submission_completed is not connected here." No other change to this method.

**If `add_song_requested` signal wiring is used:** The new button's `add_song_requested` signal from `NowPlayingPanel` must also be connected here (in whatever method sets up the panel, e.g., `__init__` or a `_setup_*` method):
```python
self._now_playing_panel.add_song_requested.connect(
    self._open_gbs_search_dialog  # QA-05 bound method
)
```

---

### `musicstreamer/ui_qt/gbs_search_dialog.py` (component, request-response) — CONFIRM NO CHANGE

**Verification target — `submission_completed` signal** (line 274):
```python
submission_completed = Signal()  # mirrors station_saved from DiscoveryDialog
```

**Verification target — emit site** (line 1093, inside `_on_submit_finished`):
```python
self._toast(message or "Track added to GBS.FM playlist")
self.submission_completed.emit()
self._reenable_submit_button(row_idx, label="Added")
```

**Verification target — `_GbsSubmitWorker.run()` call site** (line 139):
```python
def run(self):
    try:
        msg = gbs_api.submit(self._songid, self._cookies)
        self.finished.emit(msg, self._row_idx)
    except Exception as exc:
        if isinstance(exc, gbs_api.GbsAuthExpiredError):
            self.error.emit("auth_expired", self._row_idx)
        else:
            self.error.emit(str(exc), self._row_idx)
```
The planner must decide: change `gbs_api.submit(...)` here to `gbs_api.add_song_zero_token(...)` (recommended — makes the wrapper the live code path, ensures capture hook always fires) OR leave `submit()` here and rely on the named function existing for the GBS-TOKEN-03 test contract. RESEARCH Open Question 1 recommends changing this call site.

If the call site is changed, this file gains one modification: `gbs_api.submit` → `gbs_api.add_song_zero_token` at line 139.

---

### `tests/test_gbs_api.py` (test, CRUD) — ADD zero-token tests

**Analog: `test_submit_success_decodes_messages`** (lines 297–322):
```python
def test_submit_success_decodes_messages(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    """submit() returns the decoded messages cookie text."""
    raw_response = (gbs_fixtures_dir / "add_redirect_response.txt").read_text()
    def fake_open(url, cookies, timeout=15):
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=cm)
        cm.__exit__ = MagicMock(return_value=False)
        cookie_lines = [l for l in raw_response.splitlines()
                       if l.lower().startswith("set-cookie:") and "messages=" in l]
        cookie_values = [l.split(":", 1)[1].strip() for l in cookie_lines]
        location_lines = [l for l in raw_response.splitlines() if l.lower().startswith("location:")]
        location = location_lines[0].split(":", 1)[1].strip() if location_lines else "/playlist"
        headers = MagicMock()
        headers.get = MagicMock(side_effect=lambda k, *_: {"Location": location}.get(k))
        headers.get_all = MagicMock(return_value=cookie_values)
        cm.headers = headers
        cm.close = MagicMock()
        return cm
    monkeypatch.setattr(gbs_api, "_open_no_redirect", fake_open)
    result = submit(88135, fake_cookies_jar)
    assert result, f"submit returned empty string; expected decoded messages text"
    assert "added" in result.lower() or "track" in result.lower()
```
Copy this `fake_open` shape verbatim for `test_add_song_zero_token_calls_submit`.

**Analog: `test_submit_auth_expired`** (lines 325–338):
```python
def test_submit_auth_expired(fake_cookies_jar, monkeypatch):
    def fake_open(url, cookies, timeout=15):
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=cm)
        cm.__exit__ = MagicMock(return_value=False)
        headers = MagicMock()
        headers.get = MagicMock(return_value="/accounts/login/?next=/add/123")
        headers.get_all = MagicMock(return_value=[])
        cm.headers = headers
        cm.close = MagicMock()
        return cm
    monkeypatch.setattr(gbs_api, "_open_no_redirect", fake_open)
    with pytest.raises(GbsAuthExpiredError):
        submit(123, fake_cookies_jar)
```
Copy for `test_add_song_zero_token_raises_auth_expired`, replacing `submit(...)` with `gbs_api.add_song_zero_token(...)`.

**Import block pattern** (lines 1–38): New tests import `gbs_api.add_song_zero_token` the same way `submit` is imported. Add `add_song_zero_token` to the named-import list at line 25–38.

**`test_capture_hook_no_pii` shape** — monkeypatch `_log.warning` (or use `caplog`), call `add_song_zero_token`, assert `"sessionid"` / `"csrftoken"` / `"Set-Cookie"` not in logged args:
```python
def test_capture_hook_no_pii(fake_cookies_jar, monkeypatch):
    """D-02 / D-18: capture hook must not log PII or cookie values."""
    log_calls = []
    monkeypatch.setattr(gbs_api._log, "warning",
                        lambda msg, *args, **kw: log_calls.append((msg, args)))
    # fake_open returning a successful 302 + messages cookie
    # (reuse the fake_open from test_submit_success_decodes_messages)
    ...
    gbs_api.add_song_zero_token(88135, fake_cookies_jar)
    assert log_calls, "capture hook must emit at least one log call"
    for msg, args in log_calls:
        all_text = msg + " ".join(str(a) for a in args)
        assert "sessionid" not in all_text
        assert "csrftoken" not in all_text
        assert "Set-Cookie" not in all_text
```

**Fixture path for zero-token tests:** Use `gbs_zero_token_fixtures_dir` fixture (new conftest or inline) pointing at `tests/fixtures/gbs_zero_token/`, mirroring the existing `gbs_fixtures_dir` conftest fixture.

---

### `tests/test_gbs_zero_token_drift_guard.py` (test, transform) — CREATE

**Analog:** `tests/test_gbs_marquee_drift_guard.py` lines 1–100 (entire file structure)

**File header / imports pattern** (lines 1–41 of analog):
```python
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
```

**`_strip_comments()` function** — copy verbatim from analog (lines 44–62):
```python
def _strip_comments(text: str) -> str:
    """Strip # comments from each source line."""
    lines = []
    for line in text.splitlines():
        idx = line.find("#")
        if idx >= 0:
            lines.append(line[:idx])
        else:
            lines.append(line)
    return "\n".join(lines)
```

**Drift-guard test** (per RESEARCH Pattern 4):
```python
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
            f"any string literal (GBS-TOKEN-02 — no token framing)"
        )
```
Note: triple-quoted docstrings are string literals and will match these patterns if they contain `token`. Write the `add_song_zero_token` docstring to avoid the bare word `token`.

**Existence assertion** — the test simultaneously guards GBS-TOKEN-03 (function must exist). No separate "function exists" test needed.

---

### `tests/fixtures/gbs_zero_token/` (fixture directory) — CREATE

**Analog layout:** `tests/fixtures/gbs_marquee/` (MANIFEST.md + data files)
**Analog fixture content:** `tests/fixtures/gbs/add_redirect_response.txt`

**Directory contents to create:**

`add_redirect_response_48tokens.txt` — copy content verbatim from `tests/fixtures/gbs/add_redirect_response.txt`:
```
HTTP/2 302
location: /playlist
set-cookie: messages=W1siX19qc29uX21lc3NhZ2UiLDAsMjUsIlRyYWNrIGFkZGVkIHN1Y2Nlc3NmdWxseSEiLCIiXV0:1wJtOd:6O1abc; path=/; httponly

```
Label it "48-token capture" in MANIFEST.

`add_redirect_zero_token_PLACEHOLDER.txt` — empty or single-comment line, reserved for first-live-use capture.

`MANIFEST.md` — follow `tests/fixtures/gbs_marquee/MANIFEST.md` schema (columns: filename, capture_date, sha256, source_url, capture_method, provenance, notes). Add one row for `add_redirect_response_48tokens.txt` (capture_date: 2026-06-18, capture_method: `cookies`, provenance: `real-captured`, notes: "Observable /add shape at 48 tokens; provisional for zero-token contract per 87B-CONTEXT D-02"). Add a placeholder row for `add_redirect_zero_token_PLACEHOLDER.txt` (provenance: `pending-capture`, notes: "resolves_phase: 87b — to be populated on first live tokens==0 add").

---

## Shared Patterns

### Worker-thread pattern (applies to `gbs_search_dialog.py` call site)
**Source:** `musicstreamer/ui_qt/gbs_search_dialog.py:116–145` (`_GbsSubmitWorker`)
**Apply to:** The `_GbsSubmitWorker.run()` call site change (line 139)
```python
def run(self):
    try:
        msg = gbs_api.submit(self._songid, self._cookies)   # → change to add_song_zero_token
        self.finished.emit(msg, self._row_idx)
    except Exception as exc:
        if isinstance(exc, gbs_api.GbsAuthExpiredError):
            self.error.emit("auth_expired", self._row_idx)
        else:
            self.error.emit(str(exc), self._row_idx)
```
Exception handling stays identical — `GbsAuthExpiredError` passes through `add_song_zero_token` → `submit` → up to this `except` block.

### QA-05 bound-method signal connections (applies to all new `connect()` calls)
**Source:** Throughout `now_playing_panel.py` (e.g., line 718: `self._gbs_relogin_btn.clicked.connect(self._on_gbs_relogin_clicked)`)
**Apply to:** Every new `.connect()` call in this phase
Convention: always pass a bound method reference, never a lambda. Comment with `# QA-05 bound method`.

### Qt.TextFormat.PlainText for GBS-sourced text (applies to any new QLabel)
**Source:** `now_playing_panel.py:707` — `_expiry_primary.setTextFormat(Qt.TextFormat.PlainText)`
**Apply to:** Any `QLabel` that might display GBS-server-originated text
No new QLabels in this phase's primary scope, but if error text labels are added to the panel, this applies.

### `should_show` visibility gate pattern (applies to `_refresh_gbs_visibility` extension)
**Source:** `now_playing_panel.py:2998–3000`
```python
for btn in self._gbs_vote_buttons:
    btn.setVisible(should_show)
```
Add `self._gbs_add_btn.setVisible(should_show)` in both the `if should_show:` block AND the `else:` block (or equivalently, add it unconditionally with the vote-button block where `should_show` is always defined).

---

## No Analog Found

All files have direct analogs. No file requires falling back to external reference patterns.

---

## Metadata

**Analog search scope:**
- `musicstreamer/gbs_api.py` (primary — submit + _log patterns)
- `musicstreamer/ui_qt/now_playing_panel.py` (primary — button, visibility, re-poll)
- `musicstreamer/ui_qt/main_window.py` (primary — dialog launch wiring)
- `musicstreamer/ui_qt/gbs_search_dialog.py` (primary — signal verification)
- `tests/test_gbs_marquee_drift_guard.py` (primary — drift-guard template)
- `tests/test_gbs_api.py` (primary — submit test template)
- `tests/fixtures/gbs/` + `tests/fixtures/gbs_marquee/` (fixture layout)

**Files scanned:** 9 source files read directly
**Pattern extraction date:** 2026-06-18
