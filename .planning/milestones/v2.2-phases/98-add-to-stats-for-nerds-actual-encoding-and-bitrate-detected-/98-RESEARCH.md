# Phase 98: Add to Stats for Nerds — Actual Encoding & Bitrate Detected — Research

**Researched:** 2026-06-24
**Domain:** GStreamer tag message extraction (PyGObject) + PySide6 Stats-for-Nerds panel extension
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** For **Encoding** and **Bitrate**, the panel shows the detected value AND the declared/expected value together (always, not only on mismatch).
- **D-02:** A mismatch (detected ≠ expected) is flagged by rendering the **detected value in an amber/warning color**; when they match, the value uses the normal muted stats-label color. No warning icon, no tooltip — color only.
- **D-03:** "Expected" is sourced from the **declared `Stream.codec` and `Stream.bitrate_kbps`** fields (the PLS/URL-parsed metadata, FIX-PLS-01). No new source of truth is introduced.
- **D-04:** Add **four** detected format rows to the Stats-for-Nerds panel: **Encoding, Bitrate, Sample-rate, Bit-depth.** Sample-rate/bit-depth are already detected (Phase 70) so surfacing them completes the "actual stream format" block.
- **D-05:** Only **Encoding** and **Bitrate** get the detected-vs-expected comparison and amber mismatch flag. **Sample-rate** and **Bit-depth** are **detected-only** rows.
- **D-06:** Detected encoding/bitrate are captured as a **one-shot snapshot at preroll** (mirroring the existing Phase 70 one-shot caps-detection pattern). No live/continuous updates as VBR bitrate tags fluctuate.
- **D-07:** When a stream exposes no codec or bitrate (raw PCM, some HLS/YouTube), the row value renders as an **em-dash `—`**. Rows are **always present** (stable panel layout regardless of station). When the expected value is also unknown, no mismatch flag is applied.

### Claude's Discretion

- Exact GStreamer detection mechanism for codec/bitrate.
- For VBR, whether the one-shot snapshot prefers a nominal/average bitrate tag over an instantaneous one.
- Bitrate mismatch tolerance — whether a tiny declared-vs-detected delta should suppress the amber flag.
- Exact row labels and ordering within the panel; how detected+expected are formatted in a single value cell.

### Deferred Ideas (OUT OF SCOPE)

- Live/continuous VBR bitrate updating (rejected in favor of D-06 one-shot snapshot).
- `pls-codec-bitrate-url-fallback` (already resolved as FIX-PLS-01, Phase 92).
</user_constraints>

---

## Summary

Phase 98 extends the Stats-for-Nerds panel (`_build_stats_widget`) with four new rows: Encoding, Bitrate, Sample-rate, and Bit-depth. The first two are net-new detected values that require reading GStreamer bus tag messages (`TAG_AUDIO_CODEC`, `TAG_NOMINAL_BITRATE`/`TAG_BITRATE`) from the existing `_on_gst_tag` bus handler. The last two (sample-rate/bit-depth) already exist as detected values via Phase 70 but need to be surfaced in the panel. The amber mismatch color (D-02) requires a parameterized variant of `_MutedLabel` that can switch between muted and amber while remaining theme-safe across light/dark flips.

The detection pathway mirrors Phase 70's one-shot caps-watch pattern exactly: a new per-stream guard flag `_codec_tag_armed_for_stream_id` (analogous to `_caps_armed_for_stream_id`) is set in `_set_uri`/`_on_playbin_state_changed`, read in the bus-thread `_on_gst_tag` handler after parsing `TAG_AUDIO_CODEC` and the best available bitrate tag, then emitted via a new `Signal(int, str, int)` with `QueuedConnection` to the main-thread receiver in `MainWindow`. The normalised codec string and bitrate-in-kbps are delivered to the panel via a new public method on `NowPlayingPanel`.

GStreamer tag messages carrying `audio-codec` and `bitrate`/`nominal-bitrate` arrive during the PAUSED (preroll) phase for typical HTTP audio streams, ahead of the PLAYING state transition — making one-shot tag capture viable and consistent with Phase 70 caps capture. For SomaFM prerolls the existing `_preroll_in_flight` guard (already in `_on_gst_tag`) prevents the preroll's AAC m4a tags from polluting the real stream's stats row.

**Primary recommendation:** Extend `_on_gst_tag` with a one-shot tag guard mirroring `_caps_armed_for_stream_id`; emit a new `audio_format_detected = Signal(int, str, int)` (stream_id, detected_codec_normalised, detected_bitrate_kbps) via QueuedConnection; deliver to the panel via `MainWindow._on_audio_format_detected`; add a parameterised `_StatLabel` subclass for amber-on-mismatch; wire four new `QFormLayout` rows in `_build_stats_widget`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Codec/bitrate detection from GStreamer | Player (bus-loop thread) | — | Tag messages arrive on GstBusLoopThread; only Player has the bus handler |
| Cross-thread delivery of detected values | Qt Signal (QueuedConnection) | — | Rule 2 of qt-glib-bus-threading.md: bus-thread MUST only emit signals |
| Codec name normalisation | Pure helper function (no Qt/GStreamer) | Player._on_gst_tag caller | Testable in isolation; called inside bus handler before emit |
| Mismatch logic (detected vs declared) | NowPlayingPanel | — | Panel owns both detected (via signal) and declared (via _station/_streams) |
| Amber mismatch color | NowPlayingPanel._StatLabel | _MutedLabel base | Theme-responsive subclass of _MutedLabel; no mismatch logic in player |
| Stats row layout (four rows) | NowPlayingPanel._build_stats_widget | — | Existing QFormLayout already owns all stats rows |
| Declared expected values source | Stream.codec / Stream.bitrate_kbps | repo (already persisted) | D-03: no new source of truth |
| Detected sample-rate/bit-depth surfacing | NowPlayingPanel | MainWindow (already signals via audio_caps_detected) | Phase 70 already detects; just needs new panel rows |

---

## Standard Stack

No new packages are required. This phase uses only existing project dependencies.

### Core (all already present)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `gi.repository.Gst` | GStreamer 1.28+ | `msg.parse_tag()`, `taglist.get_string()`, `taglist.get_uint()` | Existing dependency; bus handler already in player.py |
| `PySide6.QtCore` | 6.11+ | `Signal(int, str, int)`, `QueuedConnection` | Existing; pattern already in use for `audio_caps_detected` |
| `PySide6.QtWidgets` | 6.11+ | `_MutedLabel` subclass, `QFormLayout` row additions | Existing; `_build_stats_widget` already uses these |
| `PySide6.QtGui` | 6.11+ | `QColor`, `QPalette` for amber mismatch | Existing; `_MutedLabel.changeEvent` already uses `QPalette` |

**No new installation required.**

---

## Package Legitimacy Audit

Not applicable — no new packages installed in this phase.

---

## Architecture Patterns

### System Architecture Diagram

```
playbin3 pipeline (GStreamer streaming thread)
    │
    │  message::tag (TAG_AUDIO_CODEC, TAG_BITRATE/TAG_NOMINAL_BITRATE)
    ▼
player.py _on_gst_tag (bus-loop thread)
    │  guard: _codec_tag_armed_for_stream_id != 0
    │  guard: not _preroll_in_flight  (existing guard — prevents preroll contamination)
    │  normalise: _normalise_audio_codec(raw_gst_string) -> "MP3"/"AAC"/...
    │  bitrate: prefer TAG_NOMINAL_BITRATE, fallback TAG_BITRATE, units: bps -> kbps
    │  one-shot disarm: _codec_tag_armed_for_stream_id = 0
    │  emit: audio_format_detected(stream_id, codec_norm, bitrate_kbps)  [QueuedConnection]
    ▼
main_window.py _on_audio_format_detected (Qt main thread)
    │  idempotency check: cache payload
    │  panel.update_detected_format(stream_id, codec_norm, bitrate_kbps)
    ▼
now_playing_panel.py update_detected_format (Qt main thread)
    │  look up declared codec/bitrate from self._streams[combo_index]
    │  update _encoding_label (detected text + mismatch colour)
    │  update _bitrate_label  (detected text + mismatch colour)
    │  (sample_rate / bit_depth rows already populated via existing audio_caps_detected path)
```

The existing `audio_caps_detected` path (Phase 70) that already carries `(stream_id, rate_hz, bit_depth)` to the panel via MainWindow is **not modified** — it remains the source for the Sample-rate and Bit-depth rows. The new `audio_format_detected` signal carries codec+bitrate only.

### Recommended Project Structure

No new files or directories required. Changes are confined to:

```
musicstreamer/
├── player.py                        # new Signal, new guard, new tag extraction in _on_gst_tag
└── ui_qt/
    ├── main_window.py               # new slot _on_audio_format_detected + connect
    └── now_playing_panel.py         # new rows in _build_stats_widget, new _StatLabel, new update_detected_format()
tests/
├── _fake_player.py                  # add audio_format_detected = Signal(int, str, int)  (D-16 parity)
├── test_player_codec_tag.py         # new — codec tag extraction, normalisation, one-shot guard
└── test_now_playing_stats.py        # new — panel stats rows: label text, amber colour, em-dash fallback
```

### Pattern 1: One-Shot Tag Guard (mirrors `_caps_armed_for_stream_id`)

**What:** A per-stream integer guard (`_codec_tag_armed_for_stream_id`) that disarms after the first tag emission, preventing duplicate or stale tag deliveries.

**When to use:** Any time bus-loop thread handler must emit exactly once per stream lifecycle.

```python
# Source: existing player.py _on_caps_negotiated — mirror this exactly

# In __init__:
self._codec_tag_armed_for_stream_id: int = 0   # 0 = disarmed

# In _set_uri (main thread, after set_state):
self._codec_tag_armed_for_stream_id = self._current_stream.id if self._current_stream else 0

# In _on_playbin_state_changed (main thread, Pattern 1b):
if self._current_stream:
    self._codec_tag_armed_for_stream_id = self._current_stream.id

# In _on_gst_tag (bus-loop thread):
if not self._codec_tag_armed_for_stream_id:
    return   # already emitted or not armed
if self._preroll_in_flight:
    return   # existing guard — suppresses SomaFM preroll contamination
# ... parse tags ...
if codec_norm or bitrate_kbps:               # only emit if at least one value found
    sid = self._codec_tag_armed_for_stream_id
    self._codec_tag_armed_for_stream_id = 0  # disarm BEFORE emit (Pitfall 6)
    self.audio_format_detected.emit(sid, codec_norm, bitrate_kbps)
```

**Timing note:** `_codec_tag_armed_for_stream_id` is NOT reset in `_arm_caps_watch_for_current_stream` (that method handles only the caps pad). The codec guard reset lives in the same sites as the caps guard: `_set_uri` (armed) and the tag handler (disarmed). [VERIFIED: codebase grep]

### Pattern 2: Tag Parsing in `_on_gst_tag` (bus-loop thread)

**What:** Read `TAG_AUDIO_CODEC` (string) and `TAG_NOMINAL_BITRATE`/`TAG_BITRATE` (uint, bits per second) from the existing `taglist` already parsed by `_on_gst_tag`.

**When to use:** Inside the one-shot guard block in `_on_gst_tag` after the existing `_preroll_in_flight` guard.

```python
# Source: [VERIFIED: .venv/bin/python GstPbutils + live Gst.TagList API probe]

def _on_gst_tag(self, bus, msg) -> None:
    taglist = msg.parse_tag()
    found_title, value = taglist.get_string(Gst.TAG_TITLE)
    self._cancel_timers_requested.emit()
    if self._preroll_in_flight:
        return   # existing preroll guard (handles SomaFM preroll AAC tags)

    # --- NEW codec/bitrate one-shot block ---
    if self._codec_tag_armed_for_stream_id:
        # Codec: TAG_AUDIO_CODEC is gchararray (string)
        found_codec, raw_codec = taglist.get_string(Gst.TAG_AUDIO_CODEC)
        # Bitrate: TAG_NOMINAL_BITRATE is guint (bits-per-second)
        # Prefer nominal (stable) over instantaneous (fluctuates on VBR)
        found_nb, nb_bps = taglist.get_uint(Gst.TAG_NOMINAL_BITRATE)
        found_b,  b_bps  = taglist.get_uint(Gst.TAG_BITRATE)
        bitrate_kbps = 0
        if found_nb and nb_bps > 0:
            bitrate_kbps = nb_bps // 1000
        elif found_b and b_bps > 0:
            bitrate_kbps = b_bps // 1000
        codec_norm = _normalise_audio_codec(raw_codec if found_codec else None)
        if codec_norm or bitrate_kbps:
            sid = self._codec_tag_armed_for_stream_id
            self._codec_tag_armed_for_stream_id = 0
            self.audio_format_detected.emit(sid, codec_norm, bitrate_kbps)

    # --- existing title path (unchanged) ---
    if not found_title:
        return
    title = _fix_icy_encoding(value)
    self.title_changed.emit(title)
```

**Key API shapes confirmed in project venv:**
- `taglist.get_string("audio-codec")` → `(found: bool, value: str | None)` — `_ResultTuple`
- `taglist.get_uint("nominal-bitrate")` → `(found: bool, value: int)` — `_ResultTuple`
- `Gst.TAG_AUDIO_CODEC` = `"audio-codec"` (string constant)
- `Gst.TAG_NOMINAL_BITRATE` = `"nominal-bitrate"` (string constant)
- `Gst.TAG_BITRATE` = `"bitrate"` (string constant)
- GStreamer tag bitrate values are in **bits per second** — divide by 1000 for kbps

[VERIFIED: .venv/bin/python GstTagList API probe, 2026-06-24]

### Pattern 3: Codec Name Normalisation (pure function, no imports)

**What:** Map GStreamer's human-readable `TAG_AUDIO_CODEC` strings to the project's declared `Stream.codec` vocabulary (`MP3`, `AAC`, `FLAC`, `OPUS`, `OGG`, `WMA`, `""`).

**When to use:** Called in `_on_gst_tag` before emit; also unit-testable in isolation.

**GStreamer → normalised mapping** (authoritative, from `GstPbutils.pb_utils_get_codec_description` probe on this machine):

| GStreamer `TAG_AUDIO_CODEC` value | Normalised (`Stream.codec` format) |
|----------------------------------|-------------------------------------|
| `"MPEG-1 Layer 3 (MP3)"` | `"MP3"` |
| `"MPEG-2 Layer 3 (MP3)"` | `"MP3"` |
| `"MPEG-4 AAC"` | `"AAC"` |
| `"MPEG-2 AAC"` | `"AAC"` |
| `"Free Lossless Audio Codec (FLAC)"` | `"FLAC"` |
| `"Opus"` | `"OPUS"` |
| `"Vorbis"` | `"OGG"` |
| `"MPEG-1 Layer 2 (MP2)"` | `"MP3"` (family match) |
| `None` / `""` / anything unrecognised | `""` (empty — em-dash in panel per D-07) |

[VERIFIED: `GstPbutils.pb_utils_get_codec_description()` called for each caps type in project venv, 2026-06-24]

**Implementation (pure function — no GStreamer/Qt imports, add to `player.py` module level or `hi_res.py`):**

```python
def _normalise_audio_codec(raw: str | None) -> str:
    """Map GStreamer TAG_AUDIO_CODEC string to Stream.codec vocabulary.

    Returns one of: 'MP3' | 'AAC' | 'FLAC' | 'OPUS' | 'OGG' | '' (unknown).
    Case-insensitive substring match mirrors the established codec_rank idiom.
    Called from _on_gst_tag (bus-loop thread); pure — no imports.
    """
    if not raw:
        return ""
    s = raw.lower()
    if "layer 3" in s or "layer3" in s:
        return "MP3"
    if "layer 2" in s or "mp2" in s:
        return "MP3"           # MP2 treated as MP3 family for display
    if "aac" in s:
        return "AAC"           # covers "MPEG-4 AAC", "MPEG-2 AAC", HE-AAC
    if "flac" in s:
        return "FLAC"
    if s == "opus":
        return "OPUS"
    if "vorbis" in s:
        return "OGG"
    return ""
```

### Pattern 4: `_StatLabel` — Theme-Safe Amber-on-Mismatch Label

**What:** A `_MutedLabel` subclass that supports a `set_mismatch(bool)` method. When `mismatch=True`, overrides the palette color with an amber/warning tone that survives light/dark theme flips. When `mismatch=False`, falls back to the normal muted color via the parent class.

**When to use:** The Encoding and Bitrate detected-value labels only.

```python
# Source: extends existing _MutedLabel pattern (now_playing_panel.py:179-201)

class _StatLabel(_MutedLabel):
    """_MutedLabel extended with amber mismatch state (Phase 98 D-02).

    Amber color is applied to WindowText only (mirrors _MutedLabel's
    QPalette.Disabled approach). Theme changes re-trigger _apply_muted_palette
    via the inherited changeEvent — overriding to re-apply amber when active.
    """
    _AMBER_LIGHT = QColor(180, 120, 0)   # readable on light backgrounds
    _AMBER_DARK  = QColor(255, 180, 60)  # readable on dark backgrounds

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._mismatch = False

    def set_mismatch(self, mismatch: bool) -> None:
        if mismatch == self._mismatch:
            return
        self._mismatch = mismatch
        self._apply_muted_palette()   # re-apply with amber if mismatch

    def _apply_muted_palette(self) -> None:
        if not self._mismatch:
            super()._apply_muted_palette()
            return
        # Detect light vs dark background to pick amber variant
        pal = self.palette()
        bg = pal.color(QPalette.Window)
        amber = self._AMBER_DARK if bg.lightness() < 128 else self._AMBER_LIGHT
        pal.setColor(QPalette.WindowText, amber)
        self.setPalette(pal)
```

**Amber color choice rationale:** `QColor(255, 180, 60)` on dark / `QColor(180, 120, 0)` on light provides WCAG AA contrast (4.5:1 minimum) against typical Qt dark palette backgrounds (~`#2b2b2b`) and light backgrounds (~`#f0f0f0`). [ASSUMED — exact WCAG ratios not computed here; verify visually in UAT]

### Pattern 5: New Stats Rows in `_build_stats_widget`

**What:** Four rows added BEFORE the existing Buffer/Underruns/Buf-duration block (or AFTER — ordering is Claude's Discretion; recommended: format block first, then perf block).

**Recommended row order (D-04):**
1. Encoding (detected `_StatLabel` + declared suffix)
2. Bitrate (detected `_StatLabel` + declared suffix)
3. Sample rate (detected `_MutedLabel` — detected only, D-05)
4. Bit depth (detected `_MutedLabel` — detected only, D-05)
5. [existing] Buffer progress bar
6. [existing] Underruns count
7. [existing] Buf duration

**Format for Encoding row value cell (D-01):** `"MP3  (exp: AAC)"` when mismatched; `"MP3  (exp: MP3)"` when matched; `"—  (exp: AAC)"` when detected unknown but expected known; `"—"` when both unknown (D-07, no flag).

**Format for Bitrate row value cell (D-01):** `"128 kbps  (exp: 320 kbps)"` when mismatched; `"320 kbps  (exp: 320 kbps)"` when matched; `"—  (exp: 320 kbps)"` when detected unknown; `"—"` when both unknown.

**Critical: Pitfall 8 (Phase 47.1):** Do NOT add `setVisible` per-row. Wrapper-level `set_stats_visible` governs all rows — adding new rows inside the existing wrapper inherits its visibility automatically. No per-row visibility code.

```python
# In _build_stats_widget, before the Buffer row:
enc_row_label = _MutedLabel("Encoding", wrapper)
self._encoding_label = _StatLabel("—", wrapper)        # D-07: em-dash default
form.addRow(enc_row_label, self._encoding_label)

brate_row_label = _MutedLabel("Bitrate", wrapper)
self._bitrate_label = _StatLabel("—", wrapper)         # D-07: em-dash default
form.addRow(brate_row_label, self._bitrate_label)

rate_row_label = _MutedLabel("Sample rate", wrapper)
self._sample_rate_label = _MutedLabel("—", wrapper)    # detected only (D-05)
form.addRow(rate_row_label, self._sample_rate_label)

depth_row_label = _MutedLabel("Bit depth", wrapper)
self._bit_depth_label = _MutedLabel("—", wrapper)      # detected only (D-05)
form.addRow(depth_row_label, self._bit_depth_label)
# ... then existing Buffer row ...
```

### Pattern 6: `update_detected_format` Panel Method

**What:** Public method on `NowPlayingPanel` that receives `(stream_id, detected_codec, detected_bitrate_kbps)` from MainWindow and renders the four format rows.

**Key design:** The method looks up the declared codec/bitrate from `self._streams` using the same index as the combo (or stream_id match). This avoids passing declared values through the signal chain — the panel already has `self._streams` populated by `_populate_stream_picker`.

```python
def update_detected_format(
    self,
    stream_id: int,
    detected_codec: str,     # normalised: "MP3"/"AAC"/"FLAC"/"OPUS"/"OGG"/"" 
    detected_bitrate_kbps: int,
) -> None:
    """Phase 98: populate Encoding/Bitrate stats rows from detected values.

    Retrieves declared codec/bitrate from self._streams (same source as
    stream picker labels) to build the detected + expected comparison (D-01).
    """
    # Find the matching stream for declared values (D-03)
    declared = next(
        (s for s in self._streams if s.id == stream_id), None
    )
    declared_codec = (declared.codec or "") if declared else ""
    declared_kbps = int(declared.bitrate_kbps or 0) if declared else 0

    # --- Encoding row ---
    if detected_codec:
        enc_text = detected_codec
        if declared_codec:
            enc_text += f"  (exp: {declared_codec})"
        mismatch_enc = bool(declared_codec) and (
            detected_codec.upper() != declared_codec.upper()
        )
    else:
        enc_text = "—"
        if declared_codec:
            enc_text += f"  (exp: {declared_codec})"
        mismatch_enc = False   # D-07: no flag when detected unknown
    self._encoding_label.setText(enc_text)
    self._encoding_label.set_mismatch(mismatch_enc)

    # --- Bitrate row ---
    _BITRATE_TOLERANCE_KBPS = 5  # see § Mismatch Tolerance below
    if detected_bitrate_kbps > 0:
        brate_text = f"{detected_bitrate_kbps} kbps"
        if declared_kbps > 0:
            brate_text += f"  (exp: {declared_kbps} kbps)"
        mismatch_brate = bool(declared_kbps) and (
            abs(detected_bitrate_kbps - declared_kbps) > _BITRATE_TOLERANCE_KBPS
        )
    else:
        brate_text = "—"
        if declared_kbps > 0:
            brate_text += f"  (exp: {declared_kbps} kbps)"
        mismatch_brate = False   # D-07: no flag when detected unknown
    self._bitrate_label.setText(brate_text)
    self._bitrate_label.set_mismatch(mismatch_brate)
```

### Pattern 7: Sample-rate and Bit-depth Rows — Surfacing Phase 70 Values

**What:** The `_on_audio_caps_detected` path in `MainWindow` already delivers `(stream_id, rate_hz, bit_depth)` to the panel via `_on_audio_caps_detected`. The panel needs to store those values and populate the two new detected-only rows.

**Options:**
1. Call `panel.update_detected_caps(stream_id, rate_hz, bit_depth)` from `MainWindow._on_audio_caps_detected` (new method call, alongside the existing `_refresh_quality_badge` call).
2. The panel already re-reads the stream from the DB indirectly via `_refresh_quality_badge`. However, the detected values are written to DB first and re-read there, so the panel could re-read from `self._streams` after the DB write.

**Recommended: Option 1.** The panel should expose `update_detected_caps(stream_id, rate_hz, bit_depth)` that sets the sample-rate and bit-depth label text. This keeps the UI update co-located with the data delivery.

```python
def update_detected_caps(self, stream_id: int, rate_hz: int, bit_depth: int) -> None:
    """Phase 98: populate Sample-rate and Bit-depth stats rows."""
    self._sample_rate_label.setText(
        f"{rate_hz / 1000:g} kHz" if rate_hz > 0 else "—"
    )
    self._bit_depth_label.setText(
        f"{bit_depth}-bit" if bit_depth > 0 else "—"
    )
```

### Pattern 8: New Signal on Player + FakePlayer Parity

**What:** Add `audio_format_detected = Signal(int, str, int)` to `Player` and mirror it in `tests/_fake_player.py` (D-16 drift-guard).

**Signal definition:**
```python
# In player.py Signal block (alongside audio_caps_detected):
audio_format_detected = Signal(int, str, int)   # stream_id, codec_norm, bitrate_kbps
```

**FakePlayer parity (must be added in the same wave as the Signal):**
```python
# In tests/_fake_player.py:
audio_format_detected = Signal(int, str, int)   # Phase 98 / D-16 parity
```

**Connect in MainWindow.__init__ with QueuedConnection:**
```python
self._player.audio_format_detected.connect(
    self._on_audio_format_detected, Qt.ConnectionType.QueuedConnection
)
```

### Anti-Patterns to Avoid

- **Touching Qt widgets from the bus-loop thread:** `_on_gst_tag` runs on GstBusLoopThread. NEVER call `self._encoding_label.setText(...)` there. Always emit the signal and let the QueuedConnection deliver to the main thread.
- **Persisting detected codec/bitrate to the DB:** Unlike Phase 70 sample-rate/bit-depth (which were persisted because the quality badge needs them), detected codec/bitrate are **transient/panel-only**. The declared values in `Stream.codec`/`Stream.bitrate_kbps` are already the persisted source of truth for codec/bitrate. Persisting the detected values would overwrite the human-curated declared values. [ASSUMED — not explicitly stated in decisions; follows from D-03 which says declared values are sourced from PLS parsing, not detection]
- **Using TAG_BITRATE exclusively:** TAG_BITRATE is instantaneous and jitters on VBR streams. Always prefer TAG_NOMINAL_BITRATE first. See § Bitrate Tag Selection.
- **Arming the codec guard in `_arm_caps_watch_for_current_stream`:** That method handles caps-pad watch only. The codec guard (`_codec_tag_armed_for_stream_id`) is armed directly in `_set_uri` and `_on_playbin_state_changed`, mirroring the pattern but NOT routed through `_arm_caps_watch_for_current_stream`.
- **Adding per-row `setVisible` calls:** Pitfall 8 from Phase 47.1. All rows inside the stats wrapper inherit visibility from `wrapper.setVisible()` in `set_stats_visible`. Never add row-level visibility toggles.
- **Not guarding against `_preroll_in_flight`:** SomaFM plays an AAC m4a preroll before the real station stream. If `_preroll_in_flight` is True when a `TAG_AUDIO_CODEC` tag arrives, it must be suppressed — the existing `if self._preroll_in_flight: return` check in `_on_gst_tag` already provides this. The new codec/bitrate block must be placed AFTER this guard, not before it.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Codec description string | Don't parse raw GStreamer caps strings | Read `TAG_AUDIO_CODEC` from tag messages | GStreamer plugins set this via `gst_pb_utils_add_codec_description_to_tag_list` — already human-readable |
| Theme-responsive amber color | Don't hardcode a color constant | Subclass `_MutedLabel`, override `_apply_muted_palette` | The `changeEvent` pattern is already proven in `_MutedLabel`; one-line override keeps theme-safety |
| Cross-thread delivery | Don't call panel methods from bus-loop thread | New `Signal(int, str, int)` with QueuedConnection | Rule 2 of `qt-glib-bus-threading.md`; exactly mirrors `audio_caps_detected` |

---

## Key Technical Findings

### Finding 1: GStreamer TAG_AUDIO_CODEC Strings (the Authoritative Values)

The GStreamer `TAG_AUDIO_CODEC` tag contains the output of `gst_pb_utils_get_codec_description()` set by parsers/demuxers. Verified on this machine:

| Input caps | TAG_AUDIO_CODEC value |
|------------|----------------------|
| `audio/mpeg, mpegversion=1, layer=3` | `"MPEG-1 Layer 3 (MP3)"` |
| `audio/mpeg, mpegversion=4` | `"MPEG-4 AAC"` |
| `audio/mpeg, mpegversion=4, profile=he-aac` | `"MPEG-4 AAC"` (no HE-AAC distinction) |
| `audio/mpeg, mpegversion=2` | `"MPEG-2 AAC"` |
| `audio/x-flac` | `"Free Lossless Audio Codec (FLAC)"` |
| `audio/x-opus` | `"Opus"` |
| `audio/x-vorbis` | `"Vorbis"` |
| `audio/mpeg, mpegversion=1, layer=2` | `"MPEG-1 Layer 2 (MP2)"` |

HE-AAC (AACP) streams present as `"MPEG-4 AAC"` in the tag — no SBR/PS distinction at the tag level. So normalising `"MPEG-4 AAC"` → `"AAC"` is correct for all AAC variants including AACP.

[VERIFIED: `GstPbutils.pb_utils_get_codec_description()` on project venv GStreamer 1.28, 2026-06-24]

### Finding 2: PyGObject API Shapes for TagList

All `taglist.get_*()` methods return a `_ResultTuple(found: bool, value: T)` namedtuple-like object. Confirmed:

```python
found, value = taglist.get_string(Gst.TAG_AUDIO_CODEC)   # (bool, str | None)
found, value = taglist.get_uint(Gst.TAG_NOMINAL_BITRATE)  # (bool, int)  -- bps
found, value = taglist.get_uint(Gst.TAG_BITRATE)          # (bool, int)  -- bps
```

[VERIFIED: .venv/bin/python Gst.TagList API probe on empty taglist, 2026-06-24]

### Finding 3: Bitrate Tag Selection

Two bitrate tags are relevant:
- `TAG_BITRATE` (`"bitrate"`, guint): instantaneous bitrate — fluctuates on VBR streams
- `TAG_NOMINAL_BITRATE` (`"nominal-bitrate"`, guint): declared/average bitrate — stable

For the D-06 one-shot snapshot, prefer `TAG_NOMINAL_BITRATE`. Fall back to `TAG_BITRATE` if nominal is absent. Both values are in **bits per second** — divide by 1000 for kbps.

`TAG_MINIMUM_BITRATE` and `TAG_MAXIMUM_BITRATE` also exist but are not useful for the panel display.

[VERIFIED: `Gst.tag_get_type()` probe, 2026-06-24]

### Finding 4: Tag Message Timing Relative to Preroll

Tag messages for `TAG_AUDIO_CODEC` and `TAG_BITRATE`/`TAG_NOMINAL_BITRATE` are emitted by parsers and demuxers during the **PAUSED** state (GStreamer's "preroll" in the internal sense — not SomaFM preroll). For typical HTTP audio streams (MP3/AAC Shoutcast/Icecast), the tag message arrives before the pipeline reaches PLAYING. This makes the one-shot guard pattern viable.

**SomaFM preroll special case:** The existing `_preroll_in_flight` guard in `_on_gst_tag` already blocks tag processing during the SomaFM m4a preroll clip. The new codec/bitrate block must be placed inside the same guard (after the `if self._preroll_in_flight: return`). When the real station stream starts after the preroll handoff, `_preroll_in_flight` is cleared and `_codec_tag_armed_for_stream_id` is re-armed (in `_set_uri`), so the real stream's tags are captured correctly.

[ASSUMED — timing of tag messages on HLS/YouTube streams may differ; those streams may not emit `TAG_AUDIO_CODEC` at all (the D-07 em-dash fallback handles this)]

### Finding 5: Mismatch Tolerance for Bitrate

A tolerance of **5 kbps** suppresses false positives from typical encoder rounding (e.g., declared 320 vs detected 319 kbps) without hiding meaningful mismatches (e.g., declared 320 vs detected 128 kbps). Real-world mismatches are typically family-level: 128 vs 320, or MP3 vs AAC — not 1 kbps drift.

For codec mismatch, case-insensitive string comparison is sufficient since normalisation maps both sides to the same vocabulary.

[ASSUMED — exact tolerance not validated against live streams; adjust in verify phase if false positives observed]

### Finding 6: Detected Codec/Bitrate Should NOT Be Persisted to DB

The Phase 70 pattern persists sample-rate/bit-depth to `station_streams` because those detected values ARE the ground truth (no declaration exists for them). But `Stream.codec` and `Stream.bitrate_kbps` are DECLARED values set at station creation/import time (FIX-PLS-01, Phase 92). Overwriting them with detected values would:
1. Erase the human-curated declared value (breaking D-03's "expected" source)
2. Eliminate the mismatch signal on the next session startup

Therefore detected codec/bitrate are **transient panel-only** — they live in the panel's label widgets and are cleared on `bind_station()`. No `repo.update_stream()` call is needed.

### Finding 7: FakePlayer Signal Parity is Load-Bearing

The `test_fake_player_signal_parity.py` drift-guard checks that every `Signal(...)` in `player.py` appears in `tests/_fake_player.py` with identical arity. Adding `audio_format_detected = Signal(int, str, int)` to `player.py` **will immediately fail this test** until the same declaration is added to `_fake_player.py`. The FakePlayer parity update must ship in the same plan wave as the Signal addition.

[VERIFIED: tests/test_fake_player_signal_parity.py source read, 2026-06-24]

---

## Common Pitfalls

### Pitfall 1: SomaFM Preroll Contaminates Codec Tag
**What goes wrong:** The SomaFM preroll is an AAC m4a clip. When it plays, `_on_gst_tag` fires with `TAG_AUDIO_CODEC = "MPEG-4 AAC"` — but this is the preroll, not the user's chosen stream.
**Why it happens:** The preroll plays on the same pipeline as the main stream (Phase 83 design). Tag messages from the preroll arrive during `_preroll_in_flight = True`.
**How to avoid:** Place the new codec/bitrate extraction block AFTER the existing `if self._preroll_in_flight: return` check in `_on_gst_tag`. The guard is already there.
**Warning signs:** Stats panel shows "AAC" for a station declared as MP3 on SomaFM stations.

### Pitfall 2: Double-Emission After Guard Disarm
**What goes wrong:** `_on_gst_tag` may fire multiple times with successive tag messages (title, bitrate, codec arrive in separate messages). After the one-shot emits and disarms, a subsequent tag message for the same stream must be ignored.
**Why it happens:** GStreamer can deliver multiple tag messages per stream. The one-shot guard disarms after first emission.
**How to avoid:** Check `if not self._codec_tag_armed_for_stream_id: return` at the TOP of the new block (before parsing). Disarm BEFORE emit (Pitfall 6 pattern from Phase 70).
**Warning signs:** `audio_format_detected` emitting multiple times per stream.

### Pitfall 3: FakePlayer Parity Test Fails Immediately
**What goes wrong:** Adding `audio_format_detected = Signal(int, str, int)` to `player.py` causes `test_fake_player_mirrors_every_player_signal` to fail.
**Why it happens:** The drift-guard is a source-level grep that fires the moment the Signal count in `player.py` exceeds `_fake_player.py`.
**How to avoid:** Always update `tests/_fake_player.py` in the SAME plan wave as the Signal addition to `player.py`.
**Warning signs:** `test_fake_player_signal_parity.py::test_fake_player_mirrors_every_player_signal` fails.

### Pitfall 4: Bitrate Units Confusion (bps vs kbps)
**What goes wrong:** `taglist.get_uint(Gst.TAG_BITRATE)` returns bits-per-second (e.g., 320000 for 320 kbps). Displaying this raw value or comparing it to `Stream.bitrate_kbps` (which is in kbps) causes wrong display and false mismatch flags.
**Why it happens:** GStreamer's bitrate tags follow the SI/media convention of bps; the project's `Stream.bitrate_kbps` uses kbps.
**How to avoid:** Always divide by 1000 when converting: `bitrate_kbps = nb_bps // 1000`.
**Warning signs:** Bitrate row shows "128000 kbps" or false mismatch on 320 kbps stream.

### Pitfall 5: `_codec_tag_armed_for_stream_id` not Reset on New Stream
**What goes wrong:** Old stream's tag is not delivered; new stream begins. If the guard was never disarmed (no tags arrived), it carries the old stream_id. When new stream's tags arrive, the guard fires with the wrong stream_id.
**Why it happens:** `_codec_tag_armed_for_stream_id` is set in `_set_uri` — that reset is correct. The issue only arises if `_set_uri` is not called (edge case: pipeline rebuild that bypasses `_set_uri`).
**How to avoid:** Also reset the guard in `_on_playbin_state_changed` (Pattern 1b path), just like `_caps_armed_for_stream_id` is reset via `_arm_caps_watch_for_current_stream`. Check both arming sites.
**Warning signs:** Codec row shows stale values from a previous stream after station switch.

### Pitfall 6: Amber Color Invisible on Wrong Theme
**What goes wrong:** Hardcoded amber `QColor` is invisible or illegible on certain Qt themes (e.g., amber on a yellow-tinted light theme).
**Why it happens:** `QPalette.Window.lightness()` is the simplest proxy for light/dark mode but is not perfect for all themes.
**How to avoid:** Use two amber variants (`_AMBER_LIGHT` and `_AMBER_DARK`); re-evaluate in `changeEvent`. UAT on both light and dark themes before closing.
**Warning signs:** Mismatch flag invisible in UAT; no amber visible.

### Pitfall 7: Stats Rows Reset to Em-dash on Station Switch but Caps Row Persists
**What goes wrong:** When `bind_station()` is called for a new station, the codec/bitrate stats rows must be reset to `"—"` (D-07), but if the panel does not reset `_encoding_label` and `_bitrate_label` on `bind_station`, stale values remain.
**Why it happens:** The new signal fires asynchronously after the pipeline starts; between `bind_station()` and signal delivery, stale labels from the previous station are visible.
**How to avoid:** In `bind_station()`, reset `_encoding_label`, `_bitrate_label`, `_sample_rate_label`, and `_bit_depth_label` to `"—"` and clear mismatch state: `self._encoding_label.set_mismatch(False)`. This is consistent with the Phase 70 caps values being stale on station switch until `audio_caps_detected` fires.

---

## Codec Name Normalisation — Full Reference

```python
def _normalise_audio_codec(raw: str | None) -> str:
    if not raw:
        return ""
    s = raw.lower()
    if "layer 3" in s or "layer3" in s:   # "MPEG-1 Layer 3 (MP3)"
        return "MP3"
    if "layer 2" in s or "mp2" in s:      # "MPEG-1 Layer 2 (MP2)"
        return "MP3"                        # treat MP2 as MP3 family
    if "aac" in s:                          # "MPEG-4 AAC", "MPEG-2 AAC"
        return "AAC"
    if "flac" in s:                         # "Free Lossless Audio Codec (FLAC)"
        return "FLAC"
    if s == "opus":                         # "Opus" (exact match)
        return "OPUS"
    if "vorbis" in s:                       # "Vorbis"
        return "OGG"
    return ""                               # unrecognised → em-dash in panel
```

---

## Bitrate Mismatch Tolerance

**Recommended tolerance: 5 kbps**

Rationale:
- A declared bitrate of 320 kbps may be detected as 319 or 321 kbps due to encoder rounding — not a meaningful mismatch.
- Real mismatches are typically family-level: 128 vs 256, MP3 vs AAC, etc.
- 5 kbps is wide enough to suppress rounding noise but narrow enough to catch a 128-vs-320 mismatch (delta 192).

[ASSUMED — validate against live streams in verify phase; tune if false positives surface]

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No detected codec/bitrate in Stats panel | TAG_AUDIO_CODEC + nominal-bitrate one-shot | Phase 98 | Validates stream identity |
| Sample-rate/bit-depth detected but panel-invisible | Four-row format block in Stats panel | Phase 98 | Completes the "actual stream format" block |
| `_MutedLabel` for all stats values | `_StatLabel` subclass with amber mismatch | Phase 98 | Theme-safe mismatch signal without icons |

---

## Validation Architecture

Nyquist validation is enabled (`workflow.nyquist_validation: true` in config.json).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (project standard) |
| Config file | None detected (inline pytest) |
| Quick run command | `.venv/bin/python -m pytest tests/test_player_codec_tag.py tests/test_now_playing_stats.py -x -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ -x -q` (scope to relevant tests for speed) |

### Testable Seams

Phase 98 has four fully testable seams that do NOT require a live GStreamer stream:

**Seam 1: `_normalise_audio_codec` pure function**
No imports from Qt or GStreamer. Parameterisable truth-table test exactly like `test_hi_res.py`.

**Seam 2: `_on_gst_tag` codec/bitrate extraction with mocked taglist**
Mirroring `test_player_tag.py` and `test_player_caps.py` patterns: mock `msg.parse_tag()` to return a `MagicMock` taglist with configured `get_string` / `get_uint` return values. Verify that `audio_format_detected` is emitted with correct (stream_id, codec_norm, bitrate_kbps).

**Seam 3: One-shot guard and disarm logic**
Verify `_codec_tag_armed_for_stream_id` is 0 after emission; verify second call does not re-emit (exact mirror of `test_caps_no_double_emit_for_same_stream`).

**Seam 4: `update_detected_format` panel rendering**
Construct `NowPlayingPanel` with a `FakeRepo` containing a stream record. Call `update_detected_format(stream_id, codec, bitrate)` and assert label text and `set_mismatch` state (accessible via `_encoding_label._mismatch`).

### Phase Requirements → Test Map

| Capability (from D-NN) | Behavior | Test Type | Automated Command | File |
|------------------------|----------|-----------|-------------------|------|
| D-06 one-shot tag capture | `_on_gst_tag` emits `audio_format_detected` on first tag arrival | unit | `pytest tests/test_player_codec_tag.py::test_codec_tag_emits_on_first_tag` | Wave 0 gap |
| D-06 one-shot guard | Second `_on_gst_tag` call for same stream does not re-emit | unit | `pytest tests/test_player_codec_tag.py::test_codec_tag_one_shot_disarm` | Wave 0 gap |
| Codec normalisation | Truth-table for all known GStreamer strings | unit | `pytest tests/test_player_codec_tag.py::test_normalise_audio_codec` | Wave 0 gap |
| Bitrate bps→kbps | 128000 bps → 128 kbps; nominal preferred over instantaneous | unit | `pytest tests/test_player_codec_tag.py::test_bitrate_bps_to_kbps_conversion` | Wave 0 gap |
| Preroll guard | `_preroll_in_flight=True` suppresses codec tag emission | unit | `pytest tests/test_player_codec_tag.py::test_codec_tag_suppressed_during_preroll` | Wave 0 gap |
| FakePlayer parity | `audio_format_detected` present + arity matches | drift-guard | `pytest tests/test_fake_player_signal_parity.py` | Wave 0 gap |
| D-01 panel format | Detected + expected both shown in label text | unit | `pytest tests/test_now_playing_stats.py::test_encoding_row_shows_detected_and_expected` | Wave 0 gap |
| D-02 amber mismatch | `_encoding_label._mismatch=True` on codec mismatch | unit | `pytest tests/test_now_playing_stats.py::test_encoding_mismatch_sets_amber` | Wave 0 gap |
| D-02 no flag on match | `_encoding_label._mismatch=False` when codec matches | unit | `pytest tests/test_now_playing_stats.py::test_no_mismatch_flag_when_codec_matches` | Wave 0 gap |
| D-05 no flag on sample-rate | `_sample_rate_label` has no `set_mismatch` (is plain `_MutedLabel`) | source-grep | `pytest tests/test_now_playing_stats.py::test_sample_rate_label_is_muted_not_stat` | Wave 0 gap |
| D-07 em-dash when unknown | `"—"` shown when detected codec is empty | unit | `pytest tests/test_now_playing_stats.py::test_em_dash_when_codec_unknown` | Wave 0 gap |
| D-07 no mismatch on double-unknown | No amber when both detected and expected are unknown | unit | `pytest tests/test_now_playing_stats.py::test_no_mismatch_when_both_unknown` | Wave 0 gap |
| Pitfall 8 no per-row visibility | No `setVisible` on individual format rows in `_build_stats_widget` | source-grep | `pytest tests/test_now_playing_stats.py::test_no_per_row_visible_in_build_stats` | Wave 0 gap |
| Bitrate tolerance | 5 kbps delta does not trigger amber; >5 kbps does | unit | `pytest tests/test_now_playing_stats.py::test_bitrate_mismatch_tolerance` | Wave 0 gap |

### Sampling Rate

- **Per task commit:** `.venv/bin/python -m pytest tests/test_player_codec_tag.py tests/test_now_playing_stats.py tests/test_fake_player_signal_parity.py -x -q`
- **Per wave merge:** `.venv/bin/python -m pytest tests/test_player_codec_tag.py tests/test_now_playing_stats.py tests/test_fake_player_signal_parity.py tests/test_now_playing_panel.py tests/test_player_tag.py tests/test_player_caps.py -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_player_codec_tag.py` — new file; covers Seam 2 (tag extraction) + Seam 3 (one-shot guard) + normalisation + preroll suppression
- [ ] `tests/test_now_playing_stats.py` — new file; covers Seam 4 (panel rendering: D-01, D-02, D-07, Pitfall 8)
- [ ] `tests/_fake_player.py` — add `audio_format_detected = Signal(int, str, int)` (D-16 parity; blocks `test_fake_player_signal_parity.py`)

*(Existing `test_player_tag.py`, `test_player_caps.py`, `test_now_playing_panel.py` require no changes — they test the unchanged existing paths.)*

---

## Environment Availability

Step 2.6: No new external dependencies. GStreamer 1.28+ and PySide6 6.11+ are already confirmed installed (used throughout the project). No new tools, services, or runtimes required.

---

## Security Domain

Step 2.6: Security enforcement is not explicitly disabled. This phase reads GStreamer tag messages and renders them as text labels in a local desktop UI panel. No authentication, session management, or network requests are involved.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | Minimal | `_normalise_audio_codec` returns from a closed vocabulary — tag strings are never rendered as HTML/rich text; `setText()` on `QLabel` is plain text |
| All others | No | Local desktop UI only; no network, auth, or crypto |

The only injection surface is `TAG_AUDIO_CODEC` from the GStreamer bus — a trusted local IPC mechanism. The normalisation function maps all unrecognised strings to `""` (em-dash), ensuring no arbitrary strings reach the label.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Amber color values `QColor(255,180,60)` / `QColor(180,120,0)` meet WCAG AA contrast | `_StatLabel` pattern | Minor UAT correction; adjust color values |
| A2 | Bitrate mismatch tolerance of 5 kbps prevents false positives on real streams | Mismatch Tolerance | False positives on streams with minor encoder drift; increase tolerance to 10 kbps |
| A3 | Detected codec/bitrate should NOT be persisted to DB (transient panel-only) | Finding 6 | If user expectation is that detected values persist between sessions, need a separate column; low-risk for this phase |
| A4 | HLS/YouTube streams typically do NOT emit TAG_AUDIO_CODEC (em-dash fallback applies) | Finding 4, Pitfall 7 | If YouTube occasionally emits a codec tag, it would be captured correctly (no risk) |
| A5 | MP2 should normalise to MP3 for display purposes | Normalisation | Stations that serve MP2 would show "MP3" — arguably incorrect; could show "MP2" if distinction matters |
| A6 | TAG_AUDIO_CODEC arrives in the first tag message (one-shot viable) | Finding 4 | Some streams may need multiple tag messages before codec tag arrives; one-shot may capture incomplete info. If this happens, the em-dash fallback (D-07) applies cleanly. |

---

## Open Questions (RESOLVED)

1. **Codec guard arming in `_on_playbin_state_changed` vs `_arm_caps_watch_for_current_stream`**
   - What we know: `_arm_caps_watch_for_current_stream` is called from `_on_playbin_state_changed` and handles the caps pad. The codec tag guard needs analogous arming.
   - What's unclear: Should the codec guard be armed inside `_arm_caps_watch_for_current_stream` (co-locating both guards) or armed directly in `_set_uri` + `_on_playbin_state_changed` (parallel to caps guard but not inside the helper)?
   - Recommendation: Direct arming in `_set_uri` + `_on_playbin_state_changed` (NOT inside `_arm_caps_watch_for_current_stream`) to keep the caps-pad helper focused on pad concerns only. The guard is a simple integer assignment — two callsites are fine.

2. **`update_detected_format` for the already-detected sample-rate/bit-depth values**
   - What we know: Phase 70 persists these to DB. The panel can re-read them from `_streams` (after `repo.update_stream` runs in `_on_audio_caps_detected`).
   - What's unclear: Is calling `panel.update_detected_caps(rate, depth)` from `MainWindow._on_audio_caps_detected` the cleanest approach, or should the panel query `self._streams` after `_refresh_quality_badge`?
   - Recommendation: Call `panel.update_detected_caps(rate, depth)` from `MainWindow._on_audio_caps_detected` for explicit delivery (same pattern as `update_detected_format`).

---

## Sources

### Primary (HIGH confidence)

- Codebase: `musicstreamer/player.py` — `_on_gst_tag`, `_caps_armed_for_stream_id`, `audio_caps_detected`, `_on_playbin_state_changed`, `_set_uri` — read 2026-06-24
- Codebase: `musicstreamer/ui_qt/now_playing_panel.py` — `_MutedLabel`, `_build_stats_widget`, `set_stats_visible` — read 2026-06-24
- Codebase: `musicstreamer/ui_qt/main_window.py` — `_on_audio_caps_detected` — read 2026-06-24
- Codebase: `musicstreamer/models.py` — `StationStream` fields — read 2026-06-24
- Codebase: `tests/_fake_player.py` + `test_fake_player_signal_parity.py` + `test_player_caps.py` — read 2026-06-24
- `.venv/bin/python` GstTagList API probe — `Gst.TAG_AUDIO_CODEC`, `Gst.TAG_BITRATE`, `Gst.TAG_NOMINAL_BITRATE`, `taglist.get_string()`, `taglist.get_uint()` — verified 2026-06-24
- `.venv/bin/python` `GstPbutils.pb_utils_get_codec_description()` — codec description string values for MP3, AAC, FLAC, Opus, Vorbis, etc. — verified 2026-06-24

### Secondary (MEDIUM confidence)

- [GStreamer Codec Utilities docs](https://gstreamer.freedesktop.org/documentation/pbutils/gstpbutilscodecutils.html) — confirms `pb_utils_get_codec_description` exists; string values confirmed via live API call above
- [GStreamer aacparse docs](https://gstreamer.freedesktop.org/documentation/audioparsers/aacparse.html) — confirmed HE-AAC presents as MPEG-4 AAC
- [GStreamer mpegaudioparse docs](https://gstreamer.freedesktop.org/documentation/audioparsers/mpegaudioparse.html) — confirms MP3 parser identity

### Tertiary (LOW confidence — [ASSUMED] items only)

- A5 (MP2→MP3 normalisation), A6 (TAG_AUDIO_CODEC timing on HLS), A3 (transient-only detection) — training knowledge, not verified against live streams

---

## Metadata

**Confidence breakdown:**
- GStreamer tag API shapes: HIGH — verified via live .venv Python probe
- Codec description strings: HIGH — verified via `GstPbutils.pb_utils_get_codec_description` 
- Threading pattern (new signal): HIGH — mirrors existing `audio_caps_detected` exactly
- Normalisation map: HIGH — derived from verified GstPbutils output
- Mismatch tolerance (5 kbps): MEDIUM-LOW — reasoned estimate, needs UAT validation
- Amber color values: LOW — not WCAG-computed; UAT required

**Research date:** 2026-06-24
**Valid until:** 60 days (GStreamer tag API is stable; PySide6 API changes very slowly)
