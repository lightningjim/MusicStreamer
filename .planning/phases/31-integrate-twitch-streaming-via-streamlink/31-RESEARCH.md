# Phase 31: Integrate Twitch Streaming via Streamlink - Research

**Researched:** 2026-04-09
**Domain:** streamlink subprocess integration, GStreamer HLS playback, Twitch offline detection
**Confidence:** HIGH

## Summary

This phase adds a Twitch playback branch to `player.py` alongside the existing YouTube (mpv subprocess) and HTTP (GStreamer direct) paths. streamlink resolves a `twitch.tv` URL to a direct `.m3u8` HLS URL via `--stream-url` flag, then GStreamer playbin3 plays that URL identically to any ShoutCast/HTTP stream. The offline detection is clean: streamlink exits 1 with a parseable stdout message when a channel is offline, vs exit 0 + URL when live. Re-resolve on GStreamer error handles HLS URL expiry (~6h TTL).

**Primary recommendation:** Run streamlink synchronously in a thread (via `GLib.idle_add` to return result to main thread), parse stdout for URL or offline message, then either call `_set_uri()` or show toast and abort without failover.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use `streamlink --stream-url <twitch_url> best` to resolve Twitch URLs to direct HLS/MPEG-TS URLs, then feed to GStreamer playbin3.
- **D-02:** On GStreamer error, re-run streamlink to get a fresh URL and resume. This hooks into the existing failover error handler — for Twitch streams, re-resolve before trying next stream.
- **D-03:** Auto-detect Twitch URLs by `"twitch.tv" in url`. No explicit `stream_type` required from user.
- **D-04:** Always request `best` quality. No multi-quality variants. Twitch ABR handles adaptation.
- **D-05:** Detect "no playable streams" error, show "Channel offline" toast, do NOT trigger failover. Station stays selected (like pause).

### Claude's Discretion
- Exact streamlink subprocess invocation details (env setup, error parsing)
- Whether to store `stream_type='twitch'` automatically when a twitch.tv URL is detected at add/import time
- Toast message wording and duration for offline state

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| streamlink | 8.2.1 | Resolve Twitch URL → HLS URL | Already installed at `~/.local/bin/streamlink` |
| GStreamer playbin3 | existing | Play resolved HLS `.m3u8` URL | Same pipeline as ShoutCast — no new component |
| GLib.idle_add | existing | Cross-thread UI callback | Already used for YouTube and timer |

**No new packages to install.** [VERIFIED: `command -v streamlink` → `/home/kcreasey/.local/bin/streamlink`]

### Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| streamlink | Twitch URL resolution | ✓ | 8.2.1 | None — required |
| GStreamer playbin3 | HLS playback | ✓ | system | None — already in use |

streamlink is at `~/.local/bin/streamlink`, so PATH must include `~/.local/bin` (same pattern as `_play_youtube()`). [VERIFIED: env check]

---

## Architecture Patterns

### Integration Points (from codebase audit)

**`player.py` — `_try_next_stream()` (lines 93–117):**
```python
# Existing pattern:
if "youtube.com" in url or "youtu.be" in url:
    self._play_youtube(url, ...)
else:
    self._set_uri(url, ...)

# Extend with Twitch branch:
if "youtube.com" in url or "youtu.be" in url:
    self._play_youtube(url, ...)
elif "twitch.tv" in url:
    self._play_twitch(url, ...)
else:
    self._set_uri(url, ...)
```
No failover timeout arm for Twitch (same as YouTube — `_play_twitch` arms its own mechanism). [VERIFIED: player.py lines 113–117]

**`player.py` — `_on_gst_error()` (line 61–65):**
Currently calls `_try_next_stream()` directly. For Twitch, re-resolve must happen before popping the next stream from queue. The re-resolve path needs to know the current stream is Twitch — check `_current_stream.url` or re-detect via `"twitch.tv" in url`.

```python
def _on_gst_error(self, bus, msg):
    err, debug = msg.parse_error()
    print(f"GStreamer ERROR: {err}\n  debug: {debug}")
    self._cancel_failover_timer()
    # Re-resolve Twitch URL before advancing queue
    if self._current_stream and "twitch.tv" in self._current_stream.url:
        self._play_twitch(self._current_stream.url, re_resolve=True)
    else:
        self._try_next_stream()
```

**`main_window.py` — offline callback:**
`_on_player_failover(stream)` is the existing callback. A new `on_offline` callback must be threaded similarly (via `GLib.idle_add`). Pattern matches existing `_show_toast()` at line 978. [VERIFIED: main_window.py lines 978–990]

### `_play_twitch()` Implementation Pattern

Modeled directly on `_play_youtube()` (lines 202–245):

```python
def _play_twitch(self, url: str, re_resolve: bool = False):
    """Resolve Twitch URL via streamlink, then play HLS URI via GStreamer."""
    env = os.environ.copy()
    local_bin = os.path.expanduser("~/.local/bin")
    if local_bin not in env.get("PATH", "").split(os.pathsep):
        env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")

    def _resolve():
        result = subprocess.run(
            ["streamlink", "--stream-url", url, "best"],
            capture_output=True, text=True, env=env
        )
        # stdout contains either the HLS URL (exit 0) or error message (exit 1)
        resolved_url = result.stdout.strip()
        if result.returncode != 0 or not resolved_url.startswith("http"):
            # Offline or error
            GLib.idle_add(self._on_twitch_offline, url)
        else:
            GLib.idle_add(self._on_twitch_resolved, resolved_url)

    import threading
    threading.Thread(target=_resolve, daemon=True).start()
```

Key: use `threading.Thread` to avoid blocking the GTK main loop during the streamlink network call (which can take 1–3 seconds). [ASSUMED — threading is the standard pattern for subprocess in GTK; YouTube path avoids blocking via Popen+poll]

### Offline Callback (D-05)

The offline case must:
1. NOT call `_try_next_stream()` — no failover
2. Show toast "[channel] is offline"
3. Leave station selected (do not call `_stop()`)
4. Stop the elapsed timer (stream isn't playing)

The channel name can be extracted from the URL: `url.rstrip('/').split('/')[-1]`.

The `on_offline` callback must be passed into `player.py` from `main_window.py`, similar to `on_failover`. Add it to `play()` and `_play_twitch()` signatures.

### streamlink Subprocess Behavior (VERIFIED by direct test)

| Scenario | stdout | exit code |
|----------|--------|-----------|
| Channel live | `https://...ttvnw.net/...m3u8` | 0 |
| Channel offline / not found | `error: No playable streams found on this URL: <url>` | 1 |

**Critical finding:** streamlink sends its error message to **stdout** (not stderr). `capture_output=True` is correct — do NOT discard stdout. [VERIFIED: subprocess test in session]

The offline error string is: `"No playable streams found on this URL:"` — reliable to match for D-05 detection. Exit code 1 alone is sufficient; string match adds clarity.

### Re-resolve on GStreamer Error (D-02)

HLS URLs from Twitch (ttvnw.net) expire after ~6 hours. When GStreamer fires an error on a Twitch stream:
- Call `_play_twitch(url)` again (not `_try_next_stream()`)
- If re-resolve succeeds: resume playback via `_set_uri()`
- If re-resolve fails (offline): show offline toast, no failover
- If re-resolve fails for another reason: then call `_try_next_stream()`

To distinguish re-resolve failure from offline: parse stdout for "No playable streams" vs other errors.

### `stream_type` Storage (Claude's Discretion)

Recommendation: do NOT auto-set `stream_type='twitch'` at insert time — detection via URL string (`"twitch.tv" in url`) is sufficient and avoids touching `repo.py` and schema logic. The `stream_type` field exists for future use (e.g., UI labeling) but is not needed for playback routing. [ASSUMED — consistent with how YouTube detection works today without a stored stream_type]

### Toast Wording (Claude's Discretion)

Recommendation: `"[channel] is offline"` — e.g., `"shroud is offline"`. Duration: 5 seconds (matches "All streams failed" severity). [ASSUMED]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Twitch HLS URL extraction | Custom Twitch API client | streamlink | Handles auth, CDN selection, ABR, API changes |
| HLS playback | Custom HLS segmenter | GStreamer playbin3 | Already in the pipeline |
| Cross-thread UI update | Direct widget calls from thread | GLib.idle_add | GTK is single-threaded; direct calls crash |

---

## Common Pitfalls

### Pitfall 1: Blocking the GTK Main Loop
**What goes wrong:** Calling `subprocess.run()` synchronously in `_play_twitch()` freezes the UI for 1–3s while streamlink resolves.
**Why it happens:** streamlink makes a network request to Twitch API before returning the URL.
**How to avoid:** Run streamlink in a `threading.Thread(daemon=True)`, use `GLib.idle_add` to deliver result to main thread.
**Warning signs:** UI freeze on station click.

### Pitfall 2: Treating All Non-Zero Exit Codes as Offline
**What goes wrong:** streamlink may exit 1 for network errors (not just offline). Triggering "Channel offline" for a transient network failure misleads the user.
**How to avoid:** Parse stdout for the specific string `"No playable streams found"`. If the error is different (e.g., network timeout), treat as a stream error and call `_try_next_stream()`.
**Warning signs:** Toast says "offline" during network outage.

### Pitfall 3: Double Failover on Re-resolve
**What goes wrong:** `_on_gst_error` calls `_try_next_stream()` which pops the current stream before re-resolve attempt, losing it.
**How to avoid:** In `_on_gst_error`, check for Twitch URL and branch to `_play_twitch(url, re_resolve=True)` BEFORE the normal `_try_next_stream()` path. Only call `_try_next_stream()` if re-resolve fails and is not an offline condition.

### Pitfall 4: streamlink Not on PATH
**What goes wrong:** `subprocess.run(["streamlink", ...])` fails with FileNotFoundError because `~/.local/bin` is not in the subprocess environment PATH.
**How to avoid:** Build `env` with `~/.local/bin` prepended, identical to `_play_youtube()` pattern (lines 207–209). [VERIFIED: _play_youtube() already does this]

### Pitfall 5: Forgetting Failover Timer for Twitch
**What goes wrong:** If `_try_next_stream()` arms the failover timeout for Twitch (the `if "youtube.com" not in url` branch), the timeout fires while streamlink is still resolving.
**How to avoid:** Extend the failover timer guard condition: `if "youtube.com" not in url and "twitch.tv" not in url`. [VERIFIED: player.py lines 113–117 — this exact guard exists for YouTube]

---

## Code Examples

### Subprocess invocation (VERIFIED by direct test)
```python
# Source: verified via subprocess.run() in session — streamlink 8.2.1
result = subprocess.run(
    ["streamlink", "--stream-url", url, "best"],
    capture_output=True, text=True, env=env
)
# result.stdout.strip() is either the HLS URL or error text
# result.returncode == 0 means live, 1 means offline/error
```

### URL detection extension (Source: player.py lines 108–117)
```python
# In _try_next_stream():
if "youtube.com" in url or "youtu.be" in url:
    self._play_youtube(url, self._current_station_name, self._on_title)
elif "twitch.tv" in url:
    self._play_twitch(url)
    # Do NOT arm failover timer — _play_twitch arms its own
else:
    self._stop_yt_proc()
    self._set_uri(url, self._current_station_name, self._on_title)
    self._failover_timer_id = GLib.timeout_add(
        BUFFER_DURATION_S * 1000, self._on_timeout_cb
    )
```

### Channel name extraction from URL
```python
# "https://www.twitch.tv/shroud" → "shroud"
channel = url.rstrip("/").split("/")[-1]
toast_msg = f"{channel} is offline"
```

---

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| Twitch public API (deprecated) | streamlink plugin | streamlink maintains Twitch plugin with auth handling |
| RTMP streams (Twitch legacy) | HLS/MPEG-TS via m3u8 | Twitch dropped RTMP for viewers in 2022 |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (detected via pyproject.toml) |
| Config file | pyproject.toml |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map
| Behavior | Test Type | Notes |
|----------|-----------|-------|
| Twitch URL detection (`"twitch.tv" in url`) | unit | Simple string check |
| streamlink subprocess called with correct args | unit (mock subprocess) | Mock `subprocess.run` |
| Live channel: HLS URL passed to `_set_uri` | unit (mock) | Verify `_set_uri` called with m3u8 URL |
| Offline channel: toast shown, no failover | unit (mock) | Verify `on_offline` called, `_try_next_stream` not called |
| GStreamer error on Twitch → re-resolve | unit (mock) | Verify re-resolve path taken |
| PATH includes ~/.local/bin in subprocess env | unit | Inspect env passed to subprocess |

### Wave 0 Gaps
- [ ] `tests/test_twitch_integration.py` — covers all behaviors above with mocked subprocess

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | URL passed to subprocess — validate it contains `twitch.tv` before calling streamlink (already enforced by detection branch) |
| V6 Cryptography | no | — |
| V2 Authentication | no | No Twitch auth required for public streams |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| URL injection via station URL field | Tampering | URL only passed if `"twitch.tv" in url` detection already branched it; subprocess uses list form (not shell=True) |

**subprocess.run with list args (not shell=True):** Prevents shell injection. The URL is an argument, not interpolated into a shell string. [VERIFIED: subprocess list invocation confirmed safe — no `shell=True` in `_play_youtube()` or proposed `_play_twitch()`]

---

## Open Questions (RESOLVED)

1. **Re-resolve retry limit**
   - What we know: D-02 says re-resolve on GStreamer error; no limit specified.
   - What's unclear: Should re-resolve retry be bounded (e.g., max 3 attempts) to avoid infinite loop on persistent errors?
   - RESOLVED: On first GStreamer error, re-resolve once. On second consecutive error for same URL, call `_try_next_stream()` to advance queue. Track `_twitch_resolve_attempts` counter, reset on station change.

2. **Elapsed timer on offline state**
   - What we know: D-05 says "station stays selected (like pause)" — timer should pause, not stop.
   - What's unclear: CONTEXT.md says "like pause" but offline is not user-initiated.
   - RESOLVED: Call `_pause_timer()` (not `_stop_timer()`) so elapsed time is preserved if user manually retries or channel comes back online.

---

## Sources

### Primary (HIGH confidence)
- `musicstreamer/player.py` — direct codebase read, all patterns verified
- `musicstreamer/ui/main_window.py` — `_show_toast`, `_on_player_failover`, timer methods verified
- streamlink 8.2.1 — live subprocess tests in session (stdout behavior, exit codes, URL format)

### Secondary (MEDIUM confidence)
- streamlink plugin list — `streamlink --plugins` output confirms Twitch plugin present

### Tertiary (LOW confidence)
- None

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `threading.Thread` is the correct pattern for blocking subprocess in GTK | Architecture Patterns | UI freeze if wrong — but this is standard GTK practice |
| A2 | `stream_type='twitch'` storage not needed at insert time | Architecture Patterns | Low risk — URL detection is sufficient for routing |
| A3 | Re-resolve retry should be bounded to 1 attempt | Open Questions | Infinite loop risk if unbounded |
| A4 | `_pause_timer()` is correct for offline state (not `_stop_timer()`) | Open Questions | Minor UX inconsistency if wrong |

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — streamlink verified installed at 8.2.1, all subprocess behavior verified live
- Architecture: HIGH — codebase read directly, patterns match existing YouTube implementation
- Pitfalls: HIGH — most discovered from direct code/subprocess testing, one (A1) is standard GTK knowledge

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (streamlink Twitch plugin stable; HLS URL expiry behavior unlikely to change)
