# Phase 33: Fix YT video playback delay until all streams failed toast - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

YouTube streams currently fail over too aggressively: `_yt_poll_cb` polls mpv every 1s and declares the stream failed on any non-zero exit, with no minimum wait window. A dead video URL, yt-dlp resolve blip, or slow network drains the entire stream queue in a few seconds and surfaces "All streams failed" before the user has any indication playback was even attempted. This phase adds a minimum wait window for YT streams, provides immediate connection feedback, and ensures users see that attempts are happening.

**In scope:** YT-stream failover timing, connecting-state user feedback, preserving existing failover semantics from Phase 28.

**Out of scope:** Changing the failover order, adding retry-on-exhaustion, changing the GStreamer 10s watchdog, detecting specific mpv/yt-dlp failure modes (unavailable video vs network etc.).

</domain>

<decisions>
## Implementation Decisions

### YT Stream Minimum Wait Window
- **D-01:** YT streams get a 15-second hard minimum wait window before `_try_next_stream` can fire. `_yt_poll_cb` may observe mpv exit earlier, but failover must not trigger until the window elapses. Matches yt-dlp's typical resolve-and-start-playback budget.
- **D-02:** The 15s window applies to **every** YT attempt in the queue, not just the first. Predictable and simple; a dead station with N streams takes up to N×15s to exhaust. This is an accepted tradeoff — the bug is user-visible premature failure, not slow dead-station recovery.
- **D-03:** "Stream is working" signal: **mpv process still running at end of the 15s window**. No mpv IPC, no stdout parsing. If mpv is alive at 15s, cancel the watchdog and let normal playback continue. If mpv has exited (any code) or hangs and then exits, fail over after the window closes.

### Connecting Feedback
- **D-04:** On every `play()` / `play_stream()` invocation, show an `Adw.Toast` "Connecting…" immediately (before any stream resolution work). Applies to **all stream types** (GStreamer, YouTube, Twitch) — consistent feedback pattern, not YT-specific.
- **D-05:** The "Connecting…" toast auto-dismisses on a short timer (Claude's discretion — 3–5s) OR when audio actually starts (`_on_gst_tag` for GStreamer, 15s mpv-alive signal for YT). Toast overlap with "Stream failed — trying next…" is acceptable; Adw.ToastOverlay handles stacking.
- **D-06:** This supersedes Phase 28 D-06's "silent on first attempt" implicit behavior. Phase 28 decision was about failover toasts; this adds a distinct "connecting" toast on top without removing failover toasts.

### Cookie Retry Interaction
- **D-07:** Existing 2-second "no-cookies retry" path in `_play_youtube` (`_check_cookie_retry`) stays as-is. The new 15s watchdog supervises the **current** mpv process — if the first mpv (with cookies) dies at 1s and gets replaced by a cookies-less mpv at 2s, the 15s window is measured against the replacement process. Net effect: a YT stream gets ~15s of mpv runtime to prove itself, regardless of cookie-retry substitution.

### Claude's Discretion
- Exact "Connecting…" toast message wording and timeout duration (3–5s range)
- Whether the 15s watchdog is implemented as a separate `GLib.timeout_add` guard on top of the existing `_yt_poll_cb`, or by adding a `_yt_attempt_start_ts` timestamp and gating `_try_next_stream` inside `_yt_poll_cb`
- Whether to reset/restart the 15s window when the cookie retry replaces the mpv process, or keep the original start time
- Whether `play_stream()` (manual stream picker) also gets the "Connecting…" toast (recommended: yes, for consistency)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Player
- `musicstreamer/player.py` — Full player implementation
  - Lines 68–77: `_on_gst_error` → `_try_next_stream` (GStreamer failover path)
  - Lines 90–97: `_cancel_failover_timer` (cancels both GStreamer and YT timers)
  - Lines 99–103: `_on_timeout_cb` (GStreamer 10s watchdog)
  - Lines 105–131: `_try_next_stream` (queue drain, YT skips GStreamer watchdog)
  - Lines 133–163: `play()` — builds queue from preferred quality + position order
  - Lines 165–176: `play_stream()` — manual stream picker entry point (bypasses queue)
  - Lines 206–220: `_yt_poll_cb` — the buggy poll loop (exit-code-only, no min wait)
  - Lines 222–268: `_play_youtube` — mpv subprocess launch + 2s cookie retry at 253–265
- `musicstreamer/constants.py` — `BUFFER_DURATION_S` (current GStreamer watchdog = 10s); may add a new `YT_MIN_WAIT_S = 15` constant

### UI Integration
- `musicstreamer/ui/main_window.py`
  - Lines 350: `toast_overlay = Adw.ToastOverlay()`
  - Lines 960–973: `play()` call site; passes `on_failover` callback
  - Lines 979–991: `_show_toast` helper and `_on_player_failover` (shows "Stream failed — trying…" / "All streams failed")
  - Lines 1033–1049: `play_stream()` call site from stream picker

### Prior Phase Context
- `.planning/phases/28-stream-failover-logic-with-server-round-robin-and-quality-fa/28-CONTEXT.md` — Original failover decisions (D-01 10s GStreamer watchdog, D-03 try-once-per-stream, D-06 toast pattern)
- `.planning/phases/31-integrate-twitch-streaming-via-streamlink/31-CONTEXT.md` — Twitch integration (relevant because `_play_twitch` also uses subprocess pattern and shares `_try_next_stream`)

### Requirements
- No `FIX-XX` requirement exists yet in `.planning/REQUIREMENTS.md` for this phase. Planner should add one (suggested: `FIX-07` or next available) capturing D-01 through D-05 as the testable criteria.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Adw.Toast` + `toast_overlay.add_toast()` pattern is established in `main_window._show_toast` — reuse directly for "Connecting…"
- `GLib.timeout_add` pattern already used for `_failover_timer_id` (GStreamer watchdog) and `_yt_poll_timer_id` (YT poll) and `_check_cookie_retry` (2s cookie check) — adding a 15s YT watchdog is the same pattern
- `_cancel_failover_timer` already centralizes timer cleanup — extend it for any new timer ID
- `_on_failover` callback hook is already wired through `play()` and `play_stream()` signatures

### Established Patterns
- Timer state lives on `Player` instance as `_*_timer_id: int | None` with `None` = inactive
- `GLib.idle_add` for cross-thread → main-loop callbacks (`_on_failover`, `_on_title`)
- Toast lifetime is caller-managed via `set_timeout(seconds)`
- `_is_first_attempt: bool` on Player already tracks whether the current play is the first stream (used to suppress the failover toast on first attempt) — the new "Connecting…" toast does NOT need this; it should fire every time `play()`/`play_stream()` is called

### Integration Points
- `main_window._on_play` → `self.player.play(...)` — add `self._show_toast("Connecting…", timeout=4)` immediately before the `player.play` call
- `main_window._on_stream_picker_row_activated` → `self.player.play_stream(...)` — same addition for consistency
- `Player._yt_poll_cb` is the focal change — it must consult an attempt-start timestamp before calling `_try_next_stream`
- `Player._play_youtube` needs to record the attempt start timestamp (`self._yt_attempt_start_ts = time.monotonic()` or similar)

</code_context>

<specifics>
## Specific Ideas

- The 15s figure was chosen over 10s because yt-dlp's resolve step alone can take 5–10s on cold DNS / slow network, and the 10s GStreamer watchdog is intentionally tight for HTTP streams (which start producing audio within ~1s normally). YT needs more slack.
- The "Connecting…" toast is the fix for the user's reported symptom: "it just stops with [the All streams failed toast] before any stream seems to maybe start". The root issue there is that Phase 28 intentionally left the first attempt silent; combined with premature failover, the user sees **zero** UI activity before the failure toast. A "Connecting…" toast gives immediate feedback that playback was attempted.
- `_is_first_attempt` gating on failover toasts (`_try_next_stream` line 116) should NOT be removed — it still correctly prevents a misleading "Stream failed — trying X" on the initial play. The "Connecting…" toast handles the initial-feedback gap instead.
- Tests for this phase should cover: (a) YT stream with mpv exiting at 1s does not trigger failover before 15s, (b) YT stream with mpv still alive at 15s is considered successful and watchdog clears, (c) "Connecting…" toast fires on every `play()` call, (d) cookie-retry substitution at 2s does not bypass the 15s window (accepted: may reset the window on substitution per D-07 discretion).

</specifics>

<deferred>
## Deferred Ideas

- **Detect specific mpv/yt-dlp failure modes** (video unavailable, network error, auth required) to fail faster on genuinely dead URLs while still being patient on slow-network good URLs — would require parsing mpv stderr or using IPC. Belongs in a future phase if dead-station exhaustion time becomes a complaint.
- **Progress indicator in the title area** ("Connecting…", "Resolving…", "Buffering…") instead of just a toast — richer UX but scope creep for a bug fix.
- **Adaptive timeout based on observed yt-dlp resolve time** — machine-learn-y, deferred indefinitely.

</deferred>

---

*Phase: 33-fix-yt-video-playback-delay-until-all-streams-failed-toast*
*Context gathered: 2026-04-10*
