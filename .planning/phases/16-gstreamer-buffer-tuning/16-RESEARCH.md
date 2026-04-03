# Phase 16: GStreamer Buffer Tuning - Research

**Researched:** 2026-04-03
**Domain:** GStreamer playbin3 buffer properties, Python GObject bindings
**Confidence:** HIGH

## Summary

Phase 16 is a single-file, single-function change: add two constants to `constants.py` and two `set_property` calls in `Player.__init__()`. The GStreamer API is well-understood, directly verified against the live runtime (GStreamer 1.26.6 on this machine), and the chosen values (5s / 5MB) are confirmed to work on playbin3 without error.

The default value for both `buffer-duration` and `buffer-size` is `-1` (automatic). GStreamer's automatic sizing delegates to `queue2`'s defaults: 2 MB and 2 seconds. That 2-second window is likely the source of audible drop-outs on high-bitrate streams — a momentary network hiccup larger than 2 seconds causes rebuffering. Raising to 5 seconds / 5 MB gives a comfortable margin for 320 kbps streams.

ICY TAG messages are delivered via the GStreamer bus after data has flowed through the buffer. A larger buffer means the first TAG fires up to ~5 seconds into playback — within the accepted tolerance from CONTEXT.md.

**Primary recommendation:** Add constants to `constants.py`, set both properties in `Player.__init__()` after `audio-sink` assignment, before any URI is set.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Store buffer values as named constants in `musicstreamer/constants.py` — not hardcoded inline
- `BUFFER_DURATION_S = 5` applied as `5 * Gst.SECOND` to `buffer-duration`
- `BUFFER_SIZE_BYTES = 5 * 1024 * 1024` applied to `buffer-size`
- Both set on `self._pipeline` in `Player.__init__()` before first URI is assigned
- ICY latency tolerance: ~5-second delay acceptable
- Test target: 320 kbps ShoutCast streams
- YouTube path (mpv / `_play_youtube()`) is unaffected — no changes there

### Claude's Discretion
- Nothing specified

### Deferred Ideas (OUT OF SCOPE)
- Buffer UI setting (future preferences panel) — constants approach keeps path open
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STREAM-01 | ShoutCast/HTTP streams play without audible drop-outs after GStreamer buffer-duration and buffer-size are tuned; ICY track title latency is not noticeably increased | Properties verified on live GStreamer 1.26.6; values confirmed writable and accepted without error |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GStreamer (python-gi) | 1.26.6 (verified on machine) | playbin3 pipeline, buffer properties | Already in use; this phase adds property calls only |
| `musicstreamer.constants` | project module | Named buffer constants | Locked decision from CONTEXT.md |

No new dependencies. No pip installs required.

## Architecture Patterns

### Insertion Point: `Player.__init__()`

Current `__init__` order:
1. Create `playbin3` pipeline
2. Set `video-sink` (fakesink)
3. Set `audio-sink` (pulsesink)
4. Get bus, attach signal handlers
5. Init instance vars

Buffer properties go after step 3 (sink assignment), before step 4 (bus setup) — or anywhere before the first URI assignment. Either position is correct; after sinks is the natural grouping.

### Constants Pattern (matching existing `constants.py`)

```python
# constants.py additions
BUFFER_DURATION_S = 5          # seconds; set as BUFFER_DURATION_S * Gst.SECOND
BUFFER_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
```

```python
# player.py — inside Player.__init__(), after audio-sink assignment
# Source: verified against GStreamer 1.26.6 property introspection
self._pipeline.set_property("buffer-duration", BUFFER_DURATION_S * Gst.SECOND)
self._pipeline.set_property("buffer-size", BUFFER_SIZE_BYTES)
```

`Gst.SECOND = 1_000_000_000` (nanoseconds). Verified: `5 * Gst.SECOND = 5_000_000_000`. Both properties accept these values without error.

### Anti-Patterns to Avoid
- **Hardcoding values inline in player.py:** Contradicts locked decision; makes future UI setting harder.
- **Setting properties after `set_state(PLAYING)`:** Property changes on a live pipeline can be ignored or have undefined behavior for buffer sizing. Set in NULL state (i.e., at init time) for reliability.
- **Touching `_play_youtube()`:** mpv manages its own buffering; these GStreamer properties have no effect on the mpv subprocess path.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Network rebuffering logic | Custom ring buffer, retry loop | playbin3 built-in buffering | queue2 inside playbin3 handles fill monitoring, BUFFERING messages, and stall detection automatically |
| Bitrate-based buffer math | `bitrate * 625` style calculation | Fixed `buffer-size` constant | Bitrate varies; a fixed 5 MB covers 320 kbps with headroom and is simpler |

## Common Pitfalls

### Pitfall 1: `buffer-duration` type is `gint64` (nanoseconds)
**What goes wrong:** Passing integer seconds (e.g., `5`) instead of nanoseconds — GStreamer silently accepts it but the buffer is 5 nanoseconds, not 5 seconds.
**Why it happens:** The property blurb says "duration" but the unit is nanoseconds.
**How to avoid:** Always multiply by `Gst.SECOND`. `BUFFER_DURATION_S * Gst.SECOND` is explicit and correct.
**Warning signs:** No crash; drop-outs continue unchanged.

### Pitfall 2: `buffer-size` type is `gint` (max ~2.1 GB)
**What goes wrong:** Passing a Python `int` larger than `2_147_483_647` raises `OverflowError`.
**Why it happens:** GObject `gint` is 32-bit signed.
**How to avoid:** 5 MB = 5_242_880, well within range. Not an issue at the chosen constant value.

### Pitfall 3: Default `-1` looks like "disabled"
**What goes wrong:** Assuming `-1` means buffering is off and adding extra logic.
**Why it happens:** `-1` conventionally means "disabled" in many APIs.
**In GStreamer:** `-1` means "automatic" — GStreamer picks defaults (queue2: 2 MB / 2 s). Setting explicit values overrides, does not add to, the automatic defaults.

### Pitfall 4: ICY TAG timing
**What goes wrong:** First ICY TAG fires ~5 seconds into stream instead of immediately.
**Why it happens:** The larger buffer fills before the decoder emits the initial TAG message.
**How to avoid:** This is expected and acceptable per CONTEXT.md (5-second tolerance). Do not reduce buffer to chase faster TAG delivery.

## Code Examples

### Verified: set properties on playbin3

```python
# Source: verified live — GStreamer 1.26.6, python-gi introspection
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst
from musicstreamer.constants import BUFFER_DURATION_S, BUFFER_SIZE_BYTES

# In Player.__init__():
self._pipeline.set_property("buffer-duration", BUFFER_DURATION_S * Gst.SECOND)
self._pipeline.set_property("buffer-size", BUFFER_SIZE_BYTES)
# Verified: get_property returns 5000000000 and 5242880 respectively
```

### Test pattern (follows existing mock convention)

```python
# Matches make_player() pattern in test_player_tag.py and test_player_volume.py
def test_init_sets_buffer_properties():
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch("musicstreamer.player.Gst.ElementFactory.make", return_value=mock_pipeline):
        player = Player()
    calls = mock_pipeline.set_property.call_args_list
    names = {c[0][0]: c[0][1] for c in calls}
    assert names["buffer-duration"] == BUFFER_DURATION_S * Gst.SECOND
    assert names["buffer-size"] == BUFFER_SIZE_BYTES
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Default `-1` (automatic, ~2 s) | Explicit 5 s / 5 MB | This phase | Eliminates drop-outs on 320 kbps streams; adds up to ~5 s initial TAG delay |

## Open Questions

None. All properties verified live. Values locked in CONTEXT.md.

## Environment Availability

Step 2.6: SKIPPED (no new external dependencies — only GStreamer, already installed and verified at 1.26.6).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (verified — 127 tests pass) |
| Config file | none (pytest.ini / pyproject.toml discovery) |
| Quick run command | `python3 -m pytest tests/test_player_tag.py tests/test_player_volume.py -q` |
| Full suite command | `python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STREAM-01 | `Player.__init__()` calls `set_property("buffer-duration", ...)` and `set_property("buffer-size", ...)` with correct values | unit | `python3 -m pytest tests/test_player_buffer.py -q` | ❌ Wave 0 |
| STREAM-01 | Constants `BUFFER_DURATION_S` and `BUFFER_SIZE_BYTES` exist in `constants.py` | unit | `python3 -m pytest tests/test_player_buffer.py -q` | ❌ Wave 0 |

Note: Acceptance criteria #1 (5+ min no drop-outs on 320 kbps) and #3 (YouTube unaffected) are manual-only — automated tests cannot reproduce live network streaming conditions or verify mpv subprocess behavior.

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_player_buffer.py tests/test_player_tag.py -q`
- **Per wave merge:** `python3 -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_player_buffer.py` — covers STREAM-01 (unit: buffer property values set in `__init__`, constants exist)

## Sources

### Primary (HIGH confidence)
- Live GStreamer 1.26.6 runtime introspection — property names, types, defaults, valid ranges, and successful `set_property` calls verified directly
- `musicstreamer/player.py` + `musicstreamer/constants.py` — existing code, insertion point confirmed

### Secondary (MEDIUM confidence)
- [pithos/pithos issue #393](https://github.com/pithos/pithos/issues/393) — confirms `buffer-duration = 5 * Gst.SECOND` pattern works in practice for audio streaming
- [Mopidy discourse thread](https://discourse.mopidy.com/t/buffer-size-and-buffer-duration-configurable-where-to-post-my-patch/4591) — original hardcoded defaults in Mopidy were 5 MB / 5 s; same values chosen here

### Tertiary (LOW confidence)
- GStreamer buffering docs (403 during fetch) — content inferred from web search snippets confirming queue2 2 MB / 2 s defaults

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; verified on running system
- Architecture: HIGH — insertion point clear from code, property API confirmed live
- Pitfalls: HIGH — nanoseconds pitfall verified by direct introspection; others from code review

**Research date:** 2026-04-03
**Valid until:** 2027-04-03 (GStreamer property API is stable)
