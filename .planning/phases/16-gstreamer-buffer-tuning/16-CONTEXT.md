# Phase 16 Context: GStreamer Buffer Tuning

**Phase goal:** Tune `playbin3` buffer properties to eliminate audible drop-outs on ShoutCast/HTTP streams without adding noticeable ICY title delay.

**Requirement:** STREAM-01

---

## Decisions

### Buffer property approach
Store buffer values as named constants in `musicstreamer/constants.py` — not hardcoded inline in `player.py`. This makes them easy to find and adjust, and anticipates a future UI setting (see Deferred).

Proposed constants:
```python
BUFFER_DURATION_S = 5       # seconds; applied as 5 * Gst.SECOND to playbin3 buffer-duration
BUFFER_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB; applied to playbin3 buffer-size
```

Both constants set on `self._pipeline` in `Player.__init__()` before first URI is assigned.

### ICY latency tolerance
A ~5-second ICY title update delay is acceptable. Buffer values should not be reduced to chase tighter title latency.

### Test target
Drop-outs are most reproducible at 320 kbps (high-bitrate ShoutCast streams). Validation should use a 320 kbps stream and confirm 5+ minutes without audible drop-outs. Lower-bitrate streams (128 kbps) are secondary.

### YouTube path
mpv handles YouTube streams — no changes to `_play_youtube()`. The buffer constants apply only to the GStreamer pipeline path (`_set_uri()`).

---

## Canonical refs

- `musicstreamer/player.py` — `Player.__init__()` is where buffer properties are set; `_set_uri()` is the ShoutCast path
- `musicstreamer/constants.py` — where new buffer constants live
- `.planning/REQUIREMENTS.md` — STREAM-01 definition and acceptance criteria
- `.planning/ROADMAP.md` — Phase 16 success criteria (5+ min, no drop-outs; ICY timing unchanged; YouTube unaffected)

---

## Deferred Ideas

- **Buffer UI setting** — User mentioned buffer duration as a candidate for a future UI setting (e.g., in preferences). Deferred to a future phase. The constant approach chosen here keeps the path open.
