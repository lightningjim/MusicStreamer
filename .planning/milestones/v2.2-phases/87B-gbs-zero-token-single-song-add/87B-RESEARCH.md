# Phase 87B: GBS Zero-Token Single-Song Add — Research

**Researched:** 2026-06-18
**Domain:** GBS.FM API integration, Qt UI (QPushButton, QThread workers, signal wiring), provisional fixture strategy
**Confidence:** HIGH — all findings verified against current source code

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** The zero-token POST spec does NOT exist and cannot be captured now. There is no `tests/fixtures/gbs_zero_token/` directory and no documented `tokens==0` POST behavior anywhere in `.planning/`.
- **D-02:** Strategy = Provisional contract + capture-on-first-use. Assume the zero-token add reuses the existing GET `/add/<songid>` path (server-gated). Build gating-free UI + wiring + named add path now. Fixture-lock what IS observable today. Add a no-PII runtime capture hook. Emit a follow-up todo.
- **D-03:** GBS-TOKEN-05 relaxed — fixture-lock the observable `/add` shape now; real `tokens==0` fixture captured on first live use. Quote-don't-paraphrase rule still applies to whatever IS captured.
- **D-04:** Persistent "Add a song" QPushButton placed with/just below the existing GBS active-playlist widget (`now_playing_panel.py` `_gbs_*` cluster, ~line 689).
- **D-05:** Button is visible whenever bound station is GBS.FM — NOT gated on token count or queue state. Amends GBS-TOKEN-01 / ROADMAP SC#1.
- **D-06:** Label is "Add a song"; no token wording in button label, tooltip, or surrounding text. GBS-TOKEN-02 literal.
- **D-07:** Server is truth — no local pre-gating. `/add/<songid>` hit; server's `messages`-cookie text surfaced verbatim on rejection.
- **D-08:** GBS-TOKEN-04 obsolete — button persists; post-add behavior is dialog-close + playlist re-poll.
- **D-09:** After successful add — confirm inline (server message text), close dialog, re-poll `fetch_active_playlist`.
- **D-10:** Reuse `GBSSearchDialog` as-is. New button calls existing `_open_gbs_search_dialog()` launch path.

### Claude's Discretion

- `add_song_zero_token()` factoring — thin wrapper/alias over existing `/add` path (preferred) or distinct function.
- Capture-hook mechanics — where scrubbed request/response is written, scrubbing implementation, first-live-use trigger/flag. Must follow 87-CONTEXT D-18: structured key=value, no PII, no cookie/session values.
- Auth-expiry surfacing — reuse Phase 87.1 `gbs_relogin_handler` for `GbsAuthExpiredError` from the add path.
- Worker-thread vs inline submit — existing dialog already runs submit on a worker; keep that shape.
- Button enabled-state while a request is in flight (debounce/disable) — mirror existing dialog submit-button behavior.

### Deferred Ideas (OUT OF SCOPE)

- Capture the true `tokens==0` endpoint now — happens on first live use via the capture hook.
- Local pre-gating / disabled-button + tooltip at the one-at-a-time limit.
- Multi-add "stay open" dialog session.
- Surfacing token cost for token-holders in the affordance.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GBS-TOKEN-01 | Persistent "Add a song" affordance visible whenever bound station is GBS.FM (any token count) — AMENDED from original tokens==0+queue==0 gating per D-05 | Button wired to `_station.provider_name == "GBS.FM"` predicate in `_refresh_gbs_visibility` / `bind_station`; D-05 is locked |
| GBS-TOKEN-02 | UI never uses the word "token" in label, tooltip, or surrounding text | Source-grep drift-guard test mirrors `test_marquee_module_reuses_phase76_auth_only` pattern; target is the new `gbs_api` add function module |
| GBS-TOKEN-03 | Activating affordance opens existing GBSSearchDialog; confirms call `gbs_api.add_song_zero_token()` which posts to the /add endpoint | `add_song_zero_token()` is a thin wrapper over `submit()`; `GBSSearchDialog` already calls `submit()` via `_GbsSubmitWorker`; the new button reuses `_open_gbs_search_dialog()` |
| GBS-TOKEN-04 | OBSOLETE per D-08 — button persists; post-add = dialog-close + playlist re-poll | Plan-phase must rewrite or retire this requirement |
| GBS-TOKEN-05 | Provisional fixture + capture-on-use — per D-03 | `tests/fixtures/gbs_zero_token/` created with observable `/add` shape at 48 tokens; placeholder for `tokens==0` response added with follow-up todo |
</phase_requirements>

---

## Summary

Phase 87B delivers a persistent "Add a song" QPushButton in the GBS widget cluster of `now_playing_panel.py`, wired to open the existing `GBSSearchDialog` whenever the bound station is GBS.FM regardless of token count. The core implementation reuses three already-proven mechanisms: (1) `gbs_api.submit()` for the `/add/<songid>` HTTP path, (2) `GBSSearchDialog` for the search-and-confirm UI, and (3) `GbsReloginHandler` for auth-expiry surfacing. The only net-new elements are the button widget and visibility wiring, the thin `add_song_zero_token()` wrapper with its no-PII capture hook, the provisional fixture directory, and two test files (unit test for the wrapper, drift-guard for the "no token word" contract).

The provisional contract (D-02) is sound: `gbs_api.submit()` at `gbs_api.py:1129` is already the GET `/add/<songid>` path, already intercepts the 302, already decodes the `messages` cookie verbatim, and already raises `GbsAuthExpiredError` — exactly the behavior GBS-TOKEN-03 requires. The server enforces any per-token limits itself via the `messages` cookie text, which is already surfaced inline by `GBSSearchDialog._on_submit_finished()`. No local pre-gating is needed or permitted (D-07).

The post-add re-poll (D-09) reuses `_on_gbs_poll_tick()` in `now_playing_panel.py`, which is already the 15-second polling engine and already safe to call directly (it is called from `_refresh_gbs_visibility`, `on_title_changed`, and `_on_gbs_relogin_succeeded` today). The `submission_completed` signal already exists on `GBSSearchDialog` but is not connected anywhere in `main_window._open_gbs_search_dialog()`; the planner must wire it.

**Primary recommendation:** Add the button to `now_playing_panel.py` inside the GBS cluster, wire visibility to the same `is_gbs` predicate already driving `_gbs_playlist_widget`, wire `GBSSearchDialog.submission_completed` to a new `trigger_gbs_repoll()` public method on the panel, add `add_song_zero_token()` as a thin two-liner in `gbs_api.py`, create the provisional fixture directory, and add the drift-guard test. Five files touched, roughly 100 lines net-new.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| "Add a song" button visibility | Frontend (NowPlayingPanel) | — | Button lives in the GBS widget cluster; visibility driven by `provider_name == "GBS.FM"` already checked in `_refresh_gbs_visibility` |
| Search-and-submit UX | Frontend (GBSSearchDialog) | — | Dialog already owns search + submit + inline messages + token counter; reused as-is per D-10 |
| HTTP song-add endpoint call | API layer (gbs_api.py) | — | `submit()` / new `add_song_zero_token()` wrapper — urllib, cookies, no Qt |
| Server limit enforcement | Server (gbs.fm) | — | D-07: server returns rejection text in `messages` cookie; no client-side gating |
| Auth-expiry surfacing | Frontend (GbsReloginHandler) | NowPlayingPanel | `GbsReloginHandler.notify_expiry_detected()` already wired; add path raises `GbsAuthExpiredError` which the dialog already handles |
| Post-add playlist re-poll | Frontend (NowPlayingPanel) | — | `_on_gbs_poll_tick()` is the existing re-poll path; need a public `trigger_gbs_repoll()` surface or wire `submission_completed` directly |
| No-PII capture hook | API layer (gbs_api.py) | buffer_log | Hook attaches to `add_song_zero_token()` return path; logs via `musicstreamer.gbs_api` logger using `buffer_log` structured format |
| Provisional fixture lock | Test infrastructure | — | `tests/fixtures/gbs_zero_token/` holds observable `/add` shape |

---

## Standard Stack

### Core (no new packages — all reused)

| Component | Location | Purpose |
|-----------|----------|---------|
| `gbs_api.submit()` | `musicstreamer/gbs_api.py:1129` | GET `/add/<songid>`, 302 intercept, messages-cookie decode — the provisional zero-token path |
| `gbs_api.load_auth_context()` | `musicstreamer/gbs_api.py:92` | Returns `MozillaCookieJar | None` from Phase 76 cookies file |
| `gbs_api._open_no_redirect()` | `musicstreamer/gbs_api.py:235` | urllib helper used by `submit()` |
| `GBSSearchDialog` | `musicstreamer/ui_qt/gbs_search_dialog.py:263` | Search + submit + inline messages + token counter, reused as-is |
| `_GbsSubmitWorker` | `musicstreamer/ui_qt/gbs_search_dialog.py:116` | QThread worker that calls `gbs_api.submit()` — already in the dialog |
| `GbsReloginHandler` | `musicstreamer/ui_qt/gbs_relogin_handler.py:44` | Single-flight auth-expiry handler, already wired in `NowPlayingPanel` |
| `buffer_log.py` | `musicstreamer/buffer_log.py` | Structured WARN logging for the capture hook |
| `GbsApiError / GbsAuthExpiredError` | `musicstreamer/gbs_api.py:82-87` | Exception types the add path raises |

### No new dependencies required [VERIFIED: source inspection]

The entire phase is implemented using existing stdlib (urllib, logging, hashlib) and already-imported PySide6 widgets. No new pip/conda packages needed.

---

## Package Legitimacy Audit

No new external packages are installed in this phase. The phase is pure code changes within the existing codebase.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
User clicks "Add a song" button
        |
        v
NowPlayingPanel._on_add_song_clicked()
        |
        v
main_window._open_gbs_search_dialog()
  [creates GBSSearchDialog, calls dlg.exec()]
        |
        v
GBSSearchDialog (existing — reused as-is)
  search → select → submit button click
        |
        v
_GbsSubmitWorker.run()
  → gbs_api.submit() [= add_song_zero_token() wrapper]
  → GET https://gbs.fm/add/<songid>
  ← 302 + Set-Cookie: messages=...
        |
   [success path]              [error path]
        |                           |
GBSSearchDialog._on_submit_finished()    GBSSearchDialog._on_submit_error()
  → server message inline         → inline error label (server text verbatim)
  → submission_completed.emit()   → [GbsAuthExpiredError → gbs_relogin_handler]
        |
        v
NowPlayingPanel.trigger_gbs_repoll()   ← connected to submission_completed
        |
        v
NowPlayingPanel._on_gbs_poll_tick()
  → _GbsPollWorker → fetch_active_playlist()
  ← updated queue_rows with newly-added song
        |
        v
NowPlayingPanel._on_gbs_playlist_ready() renders updated playlist

[Capture hook — fires inside add_song_zero_token() on completion]
        |
        v
buffer_log (musicstreamer.gbs_api logger)
  structured WARN: gbs.add.zero_token_capture
  key=value, no cookies, no session values
```

### Recommended Project Structure (new files / changes)

```
musicstreamer/
└── gbs_api.py              # ADD: add_song_zero_token() thin wrapper + capture hook

musicstreamer/ui_qt/
└── now_playing_panel.py    # ADD: "Add a song" QPushButton in GBS cluster
                            #      visibility wiring (_refresh_gbs_visibility extension)
                            #      trigger_gbs_repoll() public method

musicstreamer/ui_qt/main_window.py
                            # CHANGE: wire GBSSearchDialog.submission_completed
                            #         → panel.trigger_gbs_repoll() in
                            #           _open_gbs_search_dialog()

.planning/REQUIREMENTS.md   # CHANGE: rewrite GBS-TOKEN-01/04/05 per D-05/D-08/D-03
.planning/ROADMAP.md        # CHANGE: amend SC#1/#3/#4/#5 per context canonical_refs

tests/
├── fixtures/
│   └── gbs_zero_token/     # NEW directory
│       ├── add_redirect_response_48tokens.txt   # Observable /add shape at 48 tokens
│       ├── add_redirect_zero_token_PLACEHOLDER.txt  # Placeholder for future capture
│       └── MANIFEST.md     # Capture date, token state, source URL, provisional status
├── test_gbs_api.py         # ADD: test_add_song_zero_token_calls_submit()
│                           #      test_add_song_zero_token_raises_auth_expired()
│                           #      test_capture_hook_no_pii()
└── test_gbs_token_drift_guard.py  # NEW: no "token" word in add_song_zero_token source
```

### Pattern 1: `add_song_zero_token()` as thin wrapper with capture hook

**What:** A two-layer function in `gbs_api.py`. Layer 1: call `submit(songid, cookies)`. Layer 2: on return, write a structured no-PII log line via the `musicstreamer.gbs_api` logger. [ASSUMED] for the exact hook flag/trigger mechanics.

**When to use:** Called by `_GbsSubmitWorker` whenever the GBS add path fires, regardless of token count. The "zero token" name refers to the use-case it enables, not a code path it gates.

**Example (provisional shape):**
```python
# Source: gbs_api.py — new function, thin wrapper over submit()
def add_song_zero_token(songid: int, cookies: http.cookiejar.MozillaCookieJar) -> str:
    """GBS-TOKEN-03: named add path, provisional contract per 87B-CONTEXT D-02.

    Wraps submit() with a no-PII capture hook (D-02 item 4 / 87-CONTEXT D-18).
    The server enforces any zero-token / one-at-a-time limit via the messages
    cookie (surfaced verbatim by the caller per D-07 / Pitfall 8).

    Raises GbsAuthExpiredError on session expiry (mirrors submit()).
    Returns "" if no messages cookie set (no message from server = success).
    """
    result = submit(songid, cookies)
    _capture_add_shape(songid=songid, message=result)  # no-PII hook
    return result


def _capture_add_shape(songid: int, message: str) -> None:
    """No-PII structured WARN log for D-02 capture hook.

    Logs: endpoint shape, message category, token_state=unknown.
    MUST NOT log: cookies, session values, raw cookie headers.
    """
    _log.warning(
        "gbs.add.zero_token_capture endpoint=/add/%s message_len=%d message_category=%s",
        int(songid),
        len(message),
        "empty" if not message else ("error" if "not enough" in message.lower() else "success"),
    )
```

### Pattern 2: Button placement in the GBS widget cluster

**What:** Add a `QPushButton("Add a song")` immediately after `_gbs_playlist_widget` and `_gbs_expiry_widget` in `now_playing_panel.py`'s center-column layout. Visibility driven by the same `should_show` predicate in `_refresh_gbs_visibility` (i.e., `is_gbs and logged_in`).

**Layout insertion point** (verified at `now_playing_panel.py:689-722`):
```
center layout (QVBoxLayout):
  _gbs_playlist_widget   (line 692 — visible when is_gbs AND logged_in)
  _gbs_expiry_widget     (line 701 — Phase 87.1, visible on auth-expiry)
  [NEW] _gbs_add_btn     (QPushButton("Add a song") — visible when is_gbs AND logged_in)
  _gbs_vote_row          (QHBoxLayout — line 752, same gate)
```

**Visibility wiring** — `_refresh_gbs_visibility()` at `now_playing_panel.py:2962` already sets `self._gbs_playlist_widget.setVisible(should_show)` and the vote buttons. Add `self._gbs_add_btn.setVisible(should_show)` in the same block.

**Click wiring:** The button's `clicked` signal connects to `self._on_add_song_clicked` (bound method per QA-05 convention). That slot calls `self._open_gbs_search_dialog()` — but `_open_gbs_search_dialog` lives in `main_window.py`. The wiring options are:

- Option A: The panel emits a signal `add_song_requested = Signal()` that `main_window` connects to `self._open_gbs_search_dialog`. Keeps concerns separated.
- Option B: `now_playing_panel.py` accepts a callback at construction (or a method is called by `main_window` to inject the handler). Simpler but couples more.

Option A matches the project's existing signal-driven architecture (planner's discretion per D-04 discretion section).

### Pattern 3: `submission_completed` signal → re-poll wiring

**What:** `GBSSearchDialog.submission_completed = Signal()` already exists at `gbs_search_dialog.py:274` and emits at line 1093 (`_on_submit_finished` success path). It is currently NOT connected anywhere (the comment at `main_window.py:1547` explicitly says "submission_completed is not connected here").

**Plan:** In `_open_gbs_search_dialog()`, connect `dlg.submission_completed` to a new `trigger_gbs_repoll()` public method on `self._now_playing_panel`:

```python
# main_window.py — _open_gbs_search_dialog() amended
def _open_gbs_search_dialog(self) -> None:
    from musicstreamer.ui_qt.gbs_search_dialog import GBSSearchDialog
    dlg = GBSSearchDialog(self._repo, self.show_toast, parent=self)
    dlg.submission_completed.connect(
        self._now_playing_panel.trigger_gbs_repoll  # QA-05 bound method
    )
    dlg.exec()
```

`trigger_gbs_repoll()` on the panel:
```python
def trigger_gbs_repoll(self) -> None:
    """Phase 87B: re-poll GBS active playlist after a song add.

    Called from main_window when GBSSearchDialog.submission_completed fires.
    Mirrors the direct _on_gbs_poll_tick() call already in _on_gbs_relogin_succeeded
    (now_playing_panel.py:3192) — same guard: only polls when worker is idle
    and station is still GBS.FM bound.
    """
    if (
        self._station is not None
        and self._station.provider_name == "GBS.FM"
        and not self._gbs_poll_in_flight()
    ):
        self._on_gbs_poll_tick()
```

### Pattern 4: Source-grep drift-guard for "no token word"

**What:** Mirrors `test_marquee_module_reuses_phase76_auth_only` at `tests/test_gbs_marquee_drift_guard.py:65`. That test reads the source file, strips `#` comments, then asserts banned identifiers are absent from the comment-stripped text.

**Target file:** `musicstreamer/gbs_api.py` scoped to the `add_song_zero_token` function (or the full module, with a regex anchor).

**Concrete shape** (follows exactly the Phase 87 drift-guard pattern [VERIFIED: test_gbs_marquee_drift_guard.py]):
```python
# tests/test_gbs_token_drift_guard.py

from pathlib import Path
import re

GBS_API_SRC = Path(__file__).resolve().parent.parent / "musicstreamer" / "gbs_api.py"

def _strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        idx = line.find("#")
        lines.append(line[:idx] if idx >= 0 else line)
    return "\n".join(lines)


def test_add_song_zero_token_has_no_token_wording() -> None:
    """GBS-TOKEN-02: no 'token' word in add_song_zero_token() or surrounding code.

    The affordance UX never frames the action as spending a token.
    Scoped to the add_song_zero_token function body via regex extraction;
    the broader gbs_api module contains 'token' legitimately elsewhere
    (fetch_user_tokens, _TOKEN_RE, etc.).
    """
    src = GBS_API_SRC.read_text(encoding="utf-8")
    stripped = _strip_comments(src)

    # Extract from 'def add_song_zero_token' to the next 'def ' at same indent.
    # Simpler: assert the function body string contains no bare 'token' word
    # that would appear in label/tooltip/docstring context.
    m = re.search(
        r"def add_song_zero_token\b.*?(?=\ndef |\Z)", stripped, re.S
    )
    assert m, "add_song_zero_token() must exist in gbs_api.py (GBS-TOKEN-03)"
    fn_body = m.group(0)

    # The word 'token' is banned only in string literals / UI-facing text.
    # We check for quoted token strings. The function name itself contains
    # 'token' as an identifier — that is allowed (naming convention, not UI text).
    banned_patterns = [
        r'"[^"]*\btoken\b[^"]*"',   # "...token..." in double-quoted string
        r"'[^']*\btoken\b[^']*'",   # '...token...' in single-quoted string
    ]
    for pat in banned_patterns:
        assert not re.search(pat, fn_body, re.IGNORECASE), (
            f"add_song_zero_token() must not contain the word 'token' in "
            f"any string literal (GBS-TOKEN-02 — no token framing in the add affordance)"
        )
```

**Note on scoping:** The drift-guard must be narrow enough to allow `token` to appear legitimately elsewhere in `gbs_api.py` (e.g., in `fetch_user_tokens`, `_TOKEN_RE`). Scoping to the function body or checking only string literals achieves this without false positives.

### Anti-Patterns to Avoid

- **Local pre-gating by token count:** Do not add `if fetch_user_tokens(cookies) == 0` before submitting. Server is truth (D-07). If the server rejects, `messages` cookie text surfaces verbatim in the dialog already.
- **Widget placement after `_gbs_vote_row`:** Vote row is added with `center.addLayout(self._gbs_vote_row)` at line 767. The "Add a song" button must go BEFORE the vote row (after `_gbs_expiry_widget` at line 722) per D-04's insertion-order-is-load-bearing note (Pattern 3 Landmine in panel layout).
- **Using `dlg.exec()` return value as success signal:** `exec()` returns `QDialog.Accepted/Rejected` on close, not on successful submit. The `submission_completed` signal is the correct success notification.
- **Connecting `submission_completed` inside `NowPlayingPanel` directly:** The dialog is constructed in `main_window._open_gbs_search_dialog()`. The panel should not import or construct the dialog itself; the wiring belongs in `main_window`.
- **Putting PII in the capture hook log line:** The hook must log endpoint path, message length/category, and `token_state=unknown` — never the `cookies` object, the raw `messages` cookie value, or the `songid` in a way that identifies the user. Follows 87-CONTEXT D-18.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP add request with cookie auth | Custom urllib opener | `gbs_api.submit()` → `_open_no_redirect()` | All 302-intercept, messages-cookie decode, and auth-expiry detection already working and tested (T13 regression suite) |
| "Track already queued" error surfacing | Client-side duplicate check | `submit()` return value → GBSSearchDialog inline display | Server already returns "you already have a song queued" verbatim; the dialog already surfaces it |
| Auth-expiry flow from add path | New login prompt widget | `GbsReloginHandler.notify_expiry_detected()` | Phase 87.1 already built single-flight auth-expiry handler with `notify_expiry_detected()` API |
| Search-and-select UI | New song picker | `GBSSearchDialog` reused via `_open_gbs_search_dialog()` | Phase 60.1/60.2 built the full search → artist drill-down → album drill-down → submit flow |
| Post-add playlist refresh | Custom refresh mechanism | `_on_gbs_poll_tick()` direct call | Already the polling engine for GBS; called directly from 3 other sites today |
| Structured no-PII logging | Custom log format | `logging.getLogger("musicstreamer.gbs_api").warning(...)` + `buffer_log.install_gbs_marquee_handler()` pattern | Phase 87 established `buffer_log` as the structured diagnostic sink; gbs_api already uses `_log = logging.getLogger(__name__)` |

**Key insight:** This phase is almost entirely wiring existing components together. The only true net-new code is the button widget + visibility wiring (~15 lines), `add_song_zero_token()` (~8 lines), the capture hook (~12 lines), the fixture directory + MANIFEST, and the drift-guard test (~35 lines). Resisting the temptation to duplicate any part of `GBSSearchDialog` or `submit()` is the central discipline.

---

## Research Target Findings (cited by file:line)

### 1. `gbs_api.submit()` — confirmations [VERIFIED: source inspection]

**Shape** (`gbs_api.py:1129-1152`):
```python
def submit(songid: int, cookies: http.cookiejar.MozillaCookieJar) -> str:
    url = f"{GBS_BASE}/add/{int(songid)}"
    resp = _open_no_redirect(url, cookies, timeout=_TIMEOUT_WRITE)
    try:
        location = resp.headers.get("Location") or ""
        if "/accounts/login/" in location:
            raise GbsAuthExpiredError(...)
        for cookie_line in (resp.headers.get_all("Set-Cookie") or []):
            if cookie_line.startswith("messages="):
                raw_val = cookie_line.split(";", 1)[0].split("=", 1)[1]
                msgs = _decode_django_messages(raw_val)
                return "; ".join(msgs)
        return ""  # no messages cookie = success with no message
    finally:
        resp.close()
```

This IS safely reusable as the provisional zero-token path. The server already enforces "one free song at a time" server-side; the messages cookie text arrives verbatim when rejected.

`add_song_zero_token()` as a thin wrapper:
- Calls `submit(songid, cookies)` — no logic duplication
- Adds a no-PII structured log line via `_log.warning(...)` before returning
- Raises `GbsAuthExpiredError` transparently (not caught here)
- The capture hook attaches on the response return path (message content + status category, no cookie/session values)

### 2. `GBSSearchDialog` — signal surface [VERIFIED: source inspection]

**Key facts** (`gbs_search_dialog.py`):
- `submission_completed = Signal()` exists at line 274 — emits at line 1093 on successful `_on_submit_finished`.
- It is NOT connected anywhere today (`main_window.py:1547` explicitly: "submission_completed is not connected here").
- The dialog already calls `gbs_api.submit()` via `_GbsSubmitWorker.run()` (line 139). `add_song_zero_token()` is a drop-in for this call site — OR the worker can continue calling `submit()` directly and `add_song_zero_token()` is called from a different entry point.
- The dialog is constructed in `main_window._open_gbs_search_dialog()` at line 1542: `GBSSearchDialog(self._repo, self.show_toast, parent=self)`.
- Auth-expiry from the add path: `_GbsSubmitWorker` already emits `error("auth_expired")`, which `_on_submit_error` at line 1110 handles by calling `self._toast(...)` and `self._refresh_login_gate()`. This does NOT call `GbsReloginHandler.notify_expiry_detected()` today. **The planner must decide** whether to wire auth-expiry from the submit path through `GbsReloginHandler` (consistent with the Phase 87.1 pattern) or leave the existing dialog toast behavior unchanged. The dialog's toast-then-refresh-login-gate behavior is simpler and may be sufficient for token-holders (CONTEXT Claude's Discretion on auth-expiry surfacing).

**Connection for post-add re-poll:** `dlg.submission_completed.connect(self._now_playing_panel.trigger_gbs_repoll)` in `_open_gbs_search_dialog()`. Since the dialog is created and destroyed per-call (via `dlg.exec()`), no persistent connection management is needed.

### 3. `now_playing_panel.py` — GBS widget cluster insertion point [VERIFIED: source inspection]

**Insertion point** (lines 689-767):
```
line 692: self._gbs_playlist_widget = QListWidget(...)   # hide-when-empty
line 695: center.addWidget(self._gbs_playlist_widget)
line 701: self._gbs_expiry_widget = QWidget(...)          # Phase 87.1 expiry prompt
line 722: self._gbs_expiry_widget.setVisible(False)
line 722: center.addWidget(self._gbs_expiry_widget)
# <-- INSERT: self._gbs_add_btn = QPushButton("Add a song", self)
# <--         center.addWidget(self._gbs_add_btn)
line 748: self._gbs_vote_row = QHBoxLayout()
line 767: center.addLayout(self._gbs_vote_row)
```

**Visibility wiring** in `_refresh_gbs_visibility()` (`now_playing_panel.py:2962`):
```python
should_show = is_gbs and logged_in
self._gbs_playlist_widget.setVisible(should_show)
# ... vote buttons ...
for btn in self._gbs_vote_buttons:
    btn.setVisible(should_show)
```
Add: `self._gbs_add_btn.setVisible(should_show)` in both the `should_show=True` and `should_show=False` branches (or just call `setVisible(should_show)` unconditionally at the bottom with the vote buttons, since `should_show` covers both cases).

**Provider predicate** (`now_playing_panel.py:2968`):
```python
is_gbs = (self._station is not None
          and self._station.provider_name == "GBS.FM")
logged_in = self._is_gbs_logged_in()
should_show = is_gbs and logged_in
```
This is identical to D-05's specified visibility predicate. No new attribute or signal is needed.

**Re-poll trigger:** `_on_gbs_poll_tick()` is private (`now_playing_panel.py:3032`). For the external `submission_completed` connection, a new `trigger_gbs_repoll()` public method is needed (or the connection is wired from within `main_window` using a lambda — but CONVENTIONS.md forbids self-capturing lambdas per QA-05). The public method is the clean approach.

### 4. `fetch_active_playlist()` + `queue_rows` — what they represent [VERIFIED: source inspection]

`fetch_active_playlist()` (`gbs_api.py:298`) calls `/ajax` and folds events via `_fold_ajax_events()`. The `queue_rows` key (`gbs_api.py:327,353`) is populated from `adds` events, parsed by `_QueueRowParser`. Each row has `{entryid, songid, artist, title, duration}`.

**Critical: `queue_rows` is the GLOBAL upcoming queue** — all songs added by all users — not just the current user's adds. A freshly submitted song appears in `queue_rows` once the server's next `/ajax` response includes an `adds` event for it.

**Re-poll will show the new song** as long as `/ajax` returns the updated queue on the next call. Since gbs.fm's `/ajax` is the real-time state endpoint (polled at 15s by the app), the immediate re-poll after `submission_completed` should reflect the added song.

**Cursor note:** `_on_gbs_poll_tick()` uses `self._gbs_poll_cursor` (initialized to `{}`). After a successful add, the cursor may have non-zero `last_add` from prior polls. A full cursor reset is not needed — the delta-based `/ajax` protocol will include the new add in the `adds` events if `last_add` is stale. If the planner wants certainty, they can reset `self._gbs_poll_cursor = {}` in `trigger_gbs_repoll()` before calling `_on_gbs_poll_tick()`.

### 5. Source-grep drift-guard precedent [VERIFIED: source inspection]

`tests/test_gbs_marquee_drift_guard.py` is the canonical precedent. The pattern:
1. Read source file as text
2. `_strip_comments()` — removes `#`-prefixed comment tails from each line
3. Assert banned identifiers are absent from the comment-stripped text
4. Assert required identifiers/patterns are present in the raw text (for imports) or stripped text

The GBS-TOKEN-02 "no token word in the button module" drift-guard should check `gbs_api.py` scoped to the `add_song_zero_token()` function body, looking for `token` in string literals only (since the identifier `add_song_zero_token` and `fetch_user_tokens` legitimately contain `token` as part of their name). The exact regex: `r'"[^"]*\btoken\b[^"]*"'` and `r"'[^']*\btoken\b[^']*'"` on the extracted function body.

### 6. Auth-expiry surfacing from the add path [VERIFIED: source inspection]

`GbsReloginHandler` (`gbs_relogin_handler.py`) is Phase 87.1's shared handler. It already:
- Provides `notify_expiry_detected()` (main-thread-only, single-flight de-dup)
- Is owned by `NowPlayingPanel.__init__` (line 728) and wired to `_on_gbs_relogin_succeeded` / `_on_gbs_relogin_failed`
- Is used today by the marquee worker's `auth_expired` signal (connected at `now_playing_panel.py:1297`)
- References Phase 87b explicitly in its docstring (`gbs_relogin_handler.py:6`) as a future consumer

The add path expiry comes through `GBSSearchDialog._on_submit_error("auth_expired")` — which today calls `self._toast(...)` and `self._refresh_login_gate()` but does NOT call `GbsReloginHandler.notify_expiry_detected()`. 

For this phase, the existing dialog toast behavior ("GBS.FM session expired — reconnect via Accounts") is likely sufficient — the user will see the message inline in the dialog. The planner may optionally wire the dialog's auth_expired path through a new signal to `GbsReloginHandler.notify_expiry_detected()` for consistency, but this is Claude's discretion.

### 7. Fixture + test conventions [VERIFIED: source inspection]

**Existing GBS fixtures** live at `tests/fixtures/gbs/` with files like `add_redirect_response.txt` (the raw HTTP 302 response) and `messages_cookie_track_added.txt` (the base64-encoded Django messages cookie value).

**New fixture directory:** `tests/fixtures/gbs_zero_token/` following the `tests/fixtures/gbs_marquee/` precedent from Phase 87.

**Fixture content for `add_redirect_response_48tokens.txt`** — copy the observable `/add` shape from `tests/fixtures/gbs/add_redirect_response.txt`. The 48-token response is structurally identical to the zero-token response (per the provisional contract — D-02); only the server-side enforcement differs. Include a MANIFEST.md noting: capture date, token count at capture (48), source URL, provisional status, and the follow-up todo for `tokens==0` capture.

**Test pattern for `test_add_song_zero_token_calls_submit()`** — mirrors `test_submit_success_decodes_messages` (`test_gbs_api.py:297`):
- `monkeypatch.setattr(gbs_api, "_open_no_redirect", fake_open)`
- Call `gbs_api.add_song_zero_token(88135, fake_cookies_jar)`
- Assert result contains "added" or is a non-empty string
- Assert that the underlying submit path was exercised (via the same monkeypatch)

**`test_capture_hook_no_pii()`** — monkeypatch `_log.warning` to capture the log call, invoke `add_song_zero_token()`, assert no cookie/session values appear in the log message. Specifically: assert `"sessionid"` not in log args, `"csrftoken"` not in log args, `"Set-Cookie"` not in log args.

### 8. PyInstaller datas — fixtures are test-only [VERIFIED: source inspection]

`tests/fixtures/` directories are test-only and are never referenced by `MusicStreamer.spec` or any production code path. No new `datas` entry is needed in `MusicStreamer.spec`.

---

## Common Pitfalls

### Pitfall 1: Connecting `submission_completed` inside `now_playing_panel.py` directly
**What goes wrong:** The panel would need to import `GBSSearchDialog`, creating a coupling between `now_playing_panel` and the search dialog that doesn't exist today. Panel doesn't own dialog construction.
**Why it happens:** The re-poll should happen "when a song is added," so it feels natural to connect inside the panel.
**How to avoid:** Wire the connection in `main_window._open_gbs_search_dialog()`, which already owns dialog construction. The panel exposes a `trigger_gbs_repoll()` public method; `main_window` connects `dlg.submission_completed` to it.
**Warning signs:** Any import of `GBSSearchDialog` inside `now_playing_panel.py`.

### Pitfall 2: Token-gating the button visibility
**What goes wrong:** The original REQUIREMENTS.md GBS-TOKEN-01 says `tokens==0 AND queue==0`. If the planner follows the stale requirement text instead of CONTEXT D-05, the button becomes hidden for all users with tokens.
**Why it happens:** REQUIREMENTS.md has not been amended yet (plan-phase must do that).
**How to avoid:** Follow CONTEXT.md D-05 explicitly. Visibility predicate is `provider_name == "GBS.FM" AND station bound (AND logged in)` — same as the existing `_gbs_playlist_widget` gate.
**Warning signs:** Any `fetch_user_tokens()` call in the button visibility path.

### Pitfall 3: Placing the button after `_gbs_vote_row`
**What goes wrong:** Visually wrong order. The "Add a song" button should appear above the vote buttons (closer to the playlist context) not below.
**Why it happens:** `center.addLayout(self._gbs_vote_row)` is at line 767; a naive "add at end" appends below.
**How to avoid:** Insert before `center.addLayout(self._gbs_vote_row)`. Add the button at line ~723 (after `_gbs_expiry_widget`).
**Warning signs:** Button appears at the bottom of the GBS cluster in visual testing.

### Pitfall 4: Duplicating `submit()` logic in `add_song_zero_token()`
**What goes wrong:** Two code paths for `/add/<songid>` — one in `submit()`, one in a new function — that can drift.
**Why it happens:** `add_song_zero_token()` "feels" like it should own the zero-token logic.
**How to avoid:** `add_song_zero_token()` is a thin wrapper: `result = submit(songid, cookies); _capture_add_shape(...); return result`. All HTTP logic stays in `submit()`.
**Warning signs:** `_open_no_redirect()` or `_decode_django_messages()` appearing inside `add_song_zero_token()`.

### Pitfall 5: `queue_rows` cursor confusion on re-poll
**What goes wrong:** After an add, the immediate re-poll uses a stale `last_add` cursor value, and the server omits the new song from the `adds` delta.
**Why it happens:** `/ajax` is delta-based; `last_add` tracks the highest seen add entryid. If the new song's entryid > `last_add`, it will appear in the response. If not, the cursor may need to be reset.
**How to avoid:** `trigger_gbs_repoll()` optionally resets `self._gbs_poll_cursor` to `{}` before calling `_on_gbs_poll_tick()`. This forces a full cold-start poll at the cost of re-fetching the full queue — acceptable for a post-add refresh.
**Warning signs:** Playlist widget doesn't show the newly added song after dialog close.

### Pitfall 6: Using `self.token` wording in docstrings of `add_song_zero_token()`
**What goes wrong:** GBS-TOKEN-02 drift-guard fails. The drift-guard checks string literals, but docstrings are string literals too.
**Why it happens:** The developer writes "costs a token" or "uses a token" in the docstring.
**How to avoid:** Write docstrings that describe the HTTP contract and provisional status, not the token economics. The word "zero_token" is in the function name (identifier, not a string literal) — that's allowed.
**Warning signs:** Drift-guard test `test_add_song_zero_token_has_no_token_wording` fails.

---

## Code Examples

### `gbs_api.submit()` — the reused add path (verified source)
Source: `musicstreamer/gbs_api.py:1129`

```python
def submit(songid: int, cookies: http.cookiejar.MozillaCookieJar) -> str:
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

The observable `/add` response shape (from `tests/fixtures/gbs/add_redirect_response.txt`):
```
HTTP/2 302
location: /playlist
set-cookie: messages=W1siX19qc29uX21lc3NhZ2UiLDAsMjUsIlRyYWNrIGFkZGVkIHN1Y2Nlc3NmdWxseSEiLCIiXV0:1wJtOd:6O1abc; path=/; httponly
```
Decoded `messages` cookie → `"Track added successfully!"` (verified at `tests/test_gbs_api.py:342`).

### `_refresh_gbs_visibility()` — the visibility predicate to extend
Source: `musicstreamer/ui_qt/now_playing_panel.py:2962`

The button's `setVisible(should_show)` call belongs here, in both the `should_show=True` branch (where the playlist widget and vote buttons are revealed) and implicitly via the `else` branch (where they are all hidden). Adding it symmetrically with the vote buttons is cleanest.

### `_on_gbs_poll_tick()` — the re-poll mechanism
Source: `musicstreamer/ui_qt/now_playing_panel.py:3032`

Already called directly in 3 places today:
- `_refresh_gbs_visibility()` line 2989 — on first GBS bind
- `on_title_changed()` line 1103 — when a new ICY track arrives
- `_on_gbs_relogin_succeeded()` — after re-login

The new `trigger_gbs_repoll()` adds a fourth call site.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The zero-token `/add/<songid>` response has the same HTTP structure as the 48-token response (302 + messages cookie) | Summary, Pattern 1 | If server returns a different path or method at tokens==0, `add_song_zero_token()` would fail silently or incorrectly; the capture hook would record the unexpected shape |
| A2 | The server allows exactly one free add when `tokens==0` (one-at-a-time, server-gated) | Standard Stack | If the server blocks adds entirely at tokens==0 (rather than gating to one), the feature doesn't work; the capture hook records the rejection message |
| A3 | `queue_rows` includes the user's own just-added song in the immediate next `/ajax` response | Research Target 4 | If the server delays the add appearing in `/ajax`, the post-add re-poll may show the playlist without the new song |
| A4 | `add_song_zero_token()` docstring does not contain the word "token" in a string-literal context that would trip the drift-guard | Pattern 4, Pitfall 6 | Drift-guard test fails; easy fix |

**If this table is empty for A1/A2:** These cannot be resolved until first live zero-token use. That is the explicit premise of D-02; the follow-up todo captures the resolution path.

---

## Open Questions

1. **Should `add_song_zero_token()` be called from `_GbsSubmitWorker.run()` or as a separate entry point?**
   - What we know: `_GbsSubmitWorker.run()` currently calls `gbs_api.submit(self._songid, self._cookies)` directly (line 139). `add_song_zero_token()` wraps `submit()`.
   - What's unclear: Whether to change the call site inside the worker to `add_song_zero_token()`, or keep `submit()` in the worker and expose `add_song_zero_token()` only for the explicit test contract (GBS-TOKEN-03).
   - Recommendation: Change the call site in `_GbsSubmitWorker.run()` to `gbs_api.add_song_zero_token()`. This makes the wrapper the actual code path, not just a named alias, and ensures the capture hook always fires when a GBS add happens.

2. **Does the cursor need to be reset in `trigger_gbs_repoll()`?**
   - What we know: `/ajax` is delta-based. If `last_add` cursor is at the previous add's entryid and the new song has a higher entryid, it will appear in the delta. If the add's entryid is lower (unusual), it may be missed.
   - What's unclear: Whether gbs.fm assigns monotonically increasing entryids for adds.
   - Recommendation: Reset `self._gbs_poll_cursor = {}` in `trigger_gbs_repoll()` for a clean full-state re-fetch. Cost is fetching redundant data once; benefit is seeing the new song reliably.

3. **Should auth-expiry from the add path go through `GbsReloginHandler`?**
   - What we know: `GbsReloginHandler.notify_expiry_detected()` is already wired for the marquee worker. The add-path expiry comes through `_on_submit_error("auth_expired")` in the dialog, which currently only toasts.
   - What's unclear: Whether users want the re-login prompt to appear from a failed add (vs just a toast and a "reconnect via Accounts" message).
   - Recommendation: Leave existing dialog auth-expiry behavior unchanged (toast + login gate refresh). The user is already in the dialog when the error fires; the inline message is sufficient. The `GbsReloginHandler` path is more important for background workers (marquee, playlist poller) where there's no dialog context.

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — this phase is code/fixture changes only; no new CLI tools, services, or runtimes required beyond what Phase 87 already established).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (`.venv/bin/python -m pytest`) |
| Config file | `pytest.ini` or `pyproject.toml [tool.pytest]` |
| Quick run command | `.venv/bin/python -m pytest tests/test_gbs_api.py tests/test_gbs_token_drift_guard.py -x` |
| Full suite command | `.venv/bin/python -m pytest tests/ -x --timeout=60` (note: full suite >600s per MEMORY.md — scope it) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GBS-TOKEN-01 | Button visible when GBS.FM bound (any token count) | unit | `.venv/bin/python -m pytest tests/test_now_playing_gbs_expiry.py -x -k gbs_add` | ❌ Wave 0 (extend existing file) |
| GBS-TOKEN-02 | No "token" wording in add_song_zero_token source | source-grep | `.venv/bin/python -m pytest tests/test_gbs_token_drift_guard.py -x` | ❌ Wave 0 |
| GBS-TOKEN-03 | add_song_zero_token() calls submit(), raises GbsAuthExpiredError on expiry | unit | `.venv/bin/python -m pytest tests/test_gbs_api.py -x -k zero_token` | ❌ Wave 0 (extend existing file) |
| GBS-TOKEN-04 | OBSOLETE — button persists (no behavior to test) | n/a | n/a | n/a |
| GBS-TOKEN-05 | Provisional fixture exists at tests/fixtures/gbs_zero_token/ | file-existence | `.venv/bin/python -m pytest tests/test_gbs_api.py -x -k fixture` | ❌ Wave 0 |
| D-09 | submission_completed → trigger_gbs_repoll() wiring | unit | `.venv/bin/python -m pytest tests/test_main_window_gbs.py -x -k repoll` | ❌ Wave 0 (extend existing file) |
| D-18 | Capture hook logs no PII | unit | `.venv/bin/python -m pytest tests/test_gbs_api.py -x -k capture_hook_no_pii` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_gbs_api.py tests/test_gbs_token_drift_guard.py -x`
- **Per wave merge:** `.venv/bin/python -m pytest tests/test_gbs_api.py tests/test_gbs_token_drift_guard.py tests/test_main_window_gbs.py tests/test_now_playing_gbs_expiry.py tests/test_gbs_marquee_drift_guard.py -x`
- **Phase gate:** Full GBS test suite before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_gbs_token_drift_guard.py` — new file, GBS-TOKEN-02 source-grep
- [ ] `tests/fixtures/gbs_zero_token/` — directory + MANIFEST.md + provisional fixture files
- [ ] Extend `tests/test_gbs_api.py` — add `test_add_song_zero_token_calls_submit`, `test_add_song_zero_token_raises_auth_expired`, `test_capture_hook_no_pii`
- [ ] Extend `tests/test_now_playing_gbs_expiry.py` — add button visibility tests for GBS-TOKEN-01
- [ ] Extend `tests/test_main_window_gbs.py` — add `trigger_gbs_repoll` wiring test

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes — session cookies used | Phase 76 `load_auth_context()` cookie jar; 0o600 file permissions; `GbsAuthExpiredError` surfaces expiry |
| V3 Session Management | yes — 302-based session check | `_open_no_redirect()` intercepts 302→login; no retry on GET-with-side-effects (Pitfall 7) |
| V4 Access Control | partial — server-enforced add limit | Server enforces one-at-a-time via messages cookie; no client-side enforcement per D-07 |
| V5 Input Validation | yes — songid is cast to int | `url = f"{GBS_BASE}/add/{int(songid)}"` in submit() — int() cast prevents injection |
| V6 Cryptography | no | No new cryptographic operations |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| songid URL injection | Tampering | `int(songid)` cast in `submit()` — already present |
| PII in capture hook log | Information Disclosure | Hook logs only: endpoint pattern, message length, message category — no cookies, session values, or raw cookie text; verified at test time |
| Double-submit (fast double-click) | Spoofing | Mirror existing `_GbsSubmitWorker` pattern: disable submit button during in-flight request; re-enable on completion |
| Cookie value exposure in log | Information Disclosure | The capture hook must use `_log.warning(...)` with structured key=value; never log `cookies`, `resp.headers`, or any raw `Set-Cookie` value |

---

## Sources

### Primary (HIGH confidence)
- `musicstreamer/gbs_api.py:1129` — `submit()` function — direct source inspection, confirmed reusable as provisional zero-token path
- `musicstreamer/gbs_api.py:92` — `load_auth_context()` — Phase 76 auth model
- `musicstreamer/ui_qt/gbs_search_dialog.py:274,1093` — `submission_completed` signal — exists but unconnected today
- `musicstreamer/ui_qt/now_playing_panel.py:689-767,2962-3013` — GBS widget cluster layout and `_refresh_gbs_visibility()` — exact insertion point verified
- `musicstreamer/ui_qt/now_playing_panel.py:3032` — `_on_gbs_poll_tick()` — the existing re-poll mechanism
- `musicstreamer/ui_qt/gbs_relogin_handler.py:44,74` — `GbsReloginHandler.notify_expiry_detected()` — Phase 87.1 auth-expiry path
- `tests/test_gbs_marquee_drift_guard.py:65` — drift-guard test pattern (`_strip_comments` + banned-identifier loop) — direct source inspection
- `tests/fixtures/gbs/add_redirect_response.txt` — observable `/add` response shape at 48 tokens
- `tests/fixtures/gbs/messages_cookie_track_added.txt` — decoded message: "Track added successfully!"
- `musicstreamer/buffer_log.py` — structured logging surface for the capture hook

### Secondary (MEDIUM confidence)
- 87B-CONTEXT.md decisions D-01..D-10 — user decisions gathered 2026-06-18
- 87-CONTEXT.md D-04/D-07/D-18 — Phase 87 patterns this phase mirrors

### Tertiary (LOW confidence)
- A1-A3 in the Assumptions Log — runtime behavior of the zero-token path; cannot be verified without live tokens==0 state

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all components verified by source inspection; no new packages
- Architecture: HIGH — insertion points, signals, and method names confirmed at exact file:line
- Pitfalls: HIGH — all derived from existing code constraints (layout order, cursor behavior, signal wiring conventions)
- Assumptions: LOW for zero-token endpoint behavior (A1/A2) — cannot be resolved until first live use; explicitly deferred per D-02

**Research date:** 2026-06-18
**Valid until:** 90 days — the GBS API and widget layout are stable; only the zero-token runtime behavior (A1/A2) changes when first live use is captured

---

## RESEARCH COMPLETE

**Phase:** 87B — GBS Zero-Token Single-Song Add
**Confidence:** HIGH (code-level findings) / LOW (zero-token runtime assumptions A1/A2 — deferred by design)

### Key Findings

1. **`gbs_api.submit()` is a safe provisional zero-token path** — already handles GET `/add/<songid>`, 302 intercept, messages-cookie decode, `GbsAuthExpiredError`, and returns the server's message text verbatim. `add_song_zero_token()` should be a thin wrapper (~8 lines) calling `submit()` plus a no-PII structured log.

2. **`GBSSearchDialog.submission_completed` exists but is unconnected** — the signal is defined at line 274, emits at line 1093 on success, and is explicitly noted as unconnected at `main_window.py:1547`. Connecting it to a new `trigger_gbs_repoll()` public method on `NowPlayingPanel` is the clean wiring path.

3. **Button insertion point is confirmed** — `_gbs_expiry_widget` at line 722 is the last widget added to `center` before `_gbs_vote_row` at line 767. The "Add a song" button goes between them, with `setVisible(should_show)` wired alongside the existing vote-button visibility gate in `_refresh_gbs_visibility()`.

4. **Phase 87 drift-guard pattern is the exact template for GBS-TOKEN-02** — `_strip_comments()` + banned-pattern loop from `test_gbs_marquee_drift_guard.py` should be cloned for `test_gbs_token_drift_guard.py`, scoped to the function body and checking string literals only (since `add_song_zero_token` and `fetch_user_tokens` legitimately contain "token" as identifiers).

5. **`_on_gbs_poll_tick()` is the re-poll engine** — already called directly from 3 call sites; `trigger_gbs_repoll()` adds a fourth. Reset `_gbs_poll_cursor = {}` before the call to guarantee the newly added song appears in the next `/ajax` delta.

### File Created
`.planning/phases/87B-gbs-zero-token-single-song-add/87B-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | All components verified by source inspection; no new packages |
| Architecture / Integration Points | HIGH | Exact file:line for every insertion point, signal, and method |
| Drift-guard test shape | HIGH | Direct copy of Phase 87 precedent, adjusted for token-word scoping |
| Post-add re-poll behavior | MEDIUM | `_on_gbs_poll_tick()` mechanism verified; cursor-reset recommendation is defensive |
| Zero-token runtime behavior (A1/A2) | LOW | Cannot be verified at 48 tokens; explicitly deferred per D-02 — capture-on-first-use |

### Open Questions
- Cursor reset in `trigger_gbs_repoll()` — recommended but planner's call
- `_GbsSubmitWorker` call site: change to `add_song_zero_token()` or keep `submit()` — recommendation: change to wrapper
- Auth-expiry from add path: toast-only (current dialog behavior) vs `GbsReloginHandler` — recommendation: leave dialog behavior unchanged for this phase

### Ready for Planning
Research complete. Planner can now create PLAN.md files. Plan-phase must also amend REQUIREMENTS.md (GBS-TOKEN-01/04/05) and ROADMAP.md (SC#1/#3/#4/#5) per canonical_refs.
