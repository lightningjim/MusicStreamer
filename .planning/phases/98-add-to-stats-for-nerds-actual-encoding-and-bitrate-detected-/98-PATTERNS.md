# Phase 98: Add to Stats for Nerds — Actual Encoding & Bitrate Detected — Pattern Map

**Mapped:** 2026-06-24
**Files analyzed:** 6 (5 modified, 1 new)
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/player.py` | service | event-driven (GStreamer bus) | `player.py` `_on_caps_negotiated` / `_caps_armed_for_stream_id` / `audio_caps_detected` (lines 1240-1289) | exact — same file, same one-shot guard pattern |
| `musicstreamer/ui_qt/main_window.py` | controller | request-response (Qt slot) | `main_window.py` `_on_audio_caps_detected` (lines 701-784) | exact — same file, same cross-thread delivery slot pattern |
| `musicstreamer/ui_qt/now_playing_panel.py` | component | request-response (Qt update) | `now_playing_panel.py` `_build_stats_widget` (lines 3471-3521) + `_MutedLabel` (lines 179-201) + `set_underrun_count` / `set_buffer_duration` (lines 1171-1207) | exact — same file, same stats-row + setter pattern |
| `tests/_fake_player.py` | test | — | `tests/_fake_player.py` existing Signal block (lines 59-90) | exact — extend same block |
| `tests/test_player_codec_tag.py` | test | — | `tests/test_player_caps.py` (full file) + `tests/test_player_tag.py` (full file) | exact — same make_player/mock-taglist/waitSignal structure |
| `tests/test_now_playing_stats.py` | test | — | `tests/test_now_playing_panel.py` (full file) + `tests/test_hi_res.py` (truth-table style) | exact — same FakeRepo/FakePlayer/NowPlayingPanel construction |

---

## Pattern Assignments

---

### `musicstreamer/player.py` — new Signal + one-shot guard + `_on_gst_tag` extension

**Analogs (all same file):**
- Signal declaration: lines 362 (`audio_caps_detected`)
- One-shot guard `__init__`: line 552 (`_caps_armed_for_stream_id`)
- Guard arm in `_set_uri`: line 1622 (`_arm_caps_watch_for_current_stream()` call)
- Guard arm in `_on_playbin_state_changed` Pattern 1b: line 1335
- `_on_gst_tag` handler: lines 1134-1152
- One-shot disarm-before-emit: lines 1285-1289 (`_on_caps_negotiated`)

**Signal declaration pattern** (lines 359-362):
```python
# Phase 70 / DS-01: streaming/bus thread → main: persist sample_rate_hz / bit_depth
# for the playing stream. Emitted with QueuedConnection on the receiver side
# (MainWindow wires the slot in Plan 70-05 — qt-glib-bus-threading.md Rule 2).
audio_caps_detected = Signal(int, int, int)  # stream_id, rate_hz, bit_depth
```
**New signal to add immediately after:**
```python
audio_format_detected = Signal(int, str, int)  # stream_id, codec_norm, bitrate_kbps  (Phase 98)
```

**`__init__` guard initialisation pattern** (line 552):
```python
self._caps_armed_for_stream_id: int = 0  # per-URL one-shot guard; 0 = disarmed (Pitfall 6)
```
**New guard to add after it:**
```python
self._codec_tag_armed_for_stream_id: int = 0  # Phase 98: per-stream one-shot tag guard; 0 = disarmed
```

**`_on_gst_tag` handler — complete existing function** (lines 1134-1152):
```python
def _on_gst_tag(self, bus, msg) -> None:
    taglist = msg.parse_tag()
    found, value = taglist.get_string(Gst.TAG_TITLE)
    # Audio arrived -- cancel failover timer on the main thread via queued
    # signal. Bus-loop thread has no Qt event loop, so singleShot vanishes.
    self._cancel_timers_requested.emit()
    if not found:
        return
    # Phase 83 D-07 — suppress preroll's m4a title tag so Now Playing keeps
    # showing the station name through the ~5s ID. Set on main in Player.play
    # (before set_uri to the preroll URL) and cleared in _on_preroll_about_to_finish
    # (also main). This read is cross-thread; Python bool read is atomic. ...
    if self._preroll_in_flight:
        return
    title = _fix_icy_encoding(value)
    self.title_changed.emit(title)  # auto-queued cross-thread to main
```
**WARNING:** The current `_on_gst_tag` returns early on `if not found` (no title tag) BEFORE the `_preroll_in_flight` guard. The new codec/bitrate block must NOT depend on `found`; restructure so both paths share the same `_preroll_in_flight` guard. The block below shows the refactored version:
```python
def _on_gst_tag(self, bus, msg) -> None:
    taglist = msg.parse_tag()
    found_title, value = taglist.get_string(Gst.TAG_TITLE)
    self._cancel_timers_requested.emit()
    if self._preroll_in_flight:
        return

    # --- Phase 98: one-shot codec/bitrate tag block ---
    if self._codec_tag_armed_for_stream_id:
        found_codec, raw_codec = taglist.get_string(Gst.TAG_AUDIO_CODEC)
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
            self._codec_tag_armed_for_stream_id = 0  # disarm BEFORE emit (Pitfall 6)
            self.audio_format_detected.emit(sid, codec_norm, bitrate_kbps)

    # --- existing title path (unchanged) ---
    if not found_title:
        return
    title = _fix_icy_encoding(value)
    self.title_changed.emit(title)
```

**One-shot disarm-before-emit pattern** (lines 1285-1289 in `_on_caps_negotiated`):
```python
# Disarm one-shot guard BEFORE emit so a re-entrant call from a
# synchronous context cannot trigger a second emission (Pitfall 6).
sid = self._caps_armed_for_stream_id
self._caps_armed_for_stream_id = 0
self.audio_caps_detected.emit(sid, rate, depth)  # queued → main thread
```
Mirror identically for codec: `sid = self._codec_tag_armed_for_stream_id`, set to 0, then emit.

**Guard arm in `_set_uri`** (line 1622):
```python
# Phase 70 / DS-01: install a fresh caps watch on the new pipeline lifecycle.
# MUST happen AFTER set_state(PLAYING) so playbin3 starts negotiating streams.
self._arm_caps_watch_for_current_stream()
```
Add directly after (same arming site, NOT inside `_arm_caps_watch_for_current_stream`):
```python
# Phase 98: arm codec/bitrate one-shot tag guard for the new stream.
self._codec_tag_armed_for_stream_id = self._current_stream.id if self._current_stream else 0
```

**Guard arm in `_on_playbin_state_changed` (Pattern 1b)** (line 1335):
```python
# Pattern 1b: synchronous one-shot caps read on the main thread.
self._arm_caps_watch_for_current_stream()
```
Add directly after:
```python
# Phase 98 Pattern 1b: arm codec tag guard at PLAYING transition.
if self._current_stream:
    self._codec_tag_armed_for_stream_id = self._current_stream.id
```

**Pure normalisation function to add at module level** (new, based on RESEARCH §Pattern 3):
```python
def _normalise_audio_codec(raw: str | None) -> str:
    """Map GStreamer TAG_AUDIO_CODEC string to Stream.codec vocabulary.

    Returns one of: 'MP3' | 'AAC' | 'FLAC' | 'OPUS' | 'OGG' | '' (unknown).
    Case-insensitive substring match. Called from _on_gst_tag (bus-loop thread);
    pure — no Qt/GStreamer imports. Phase 98.
    """
    if not raw:
        return ""
    s = raw.lower()
    if "layer 3" in s or "layer3" in s:
        return "MP3"
    if "layer 2" in s or "mp2" in s:
        return "MP3"
    if "aac" in s:
        return "AAC"
    if "flac" in s:
        return "FLAC"
    if s == "opus":
        return "OPUS"
    if "vorbis" in s:
        return "OGG"
    return ""
```

---

### `musicstreamer/ui_qt/main_window.py` — new slot `_on_audio_format_detected` + connect

**Analog:** `_on_audio_caps_detected` (lines 701-784) + connection wiring (lines 537-545)

**Connection wiring pattern** (lines 541-545):
```python
# Explicit QueuedConnection for documentation clarity (belt-and-suspenders
# — Qt auto-queues cross-thread; Plan 70-00 grep test requires QueuedConnection
# near audio_caps_detected).
self._player.audio_caps_detected.connect(
    self._on_audio_caps_detected, Qt.ConnectionType.QueuedConnection
)
```
**New connection to add immediately after:**
```python
# Phase 98: detected codec/bitrate from GStreamer bus → panel stats rows.
self._player.audio_format_detected.connect(
    self._on_audio_format_detected, Qt.ConnectionType.QueuedConnection
)
```

**Slot pattern** (lines 701-784, key structure to mirror):
```python
def _on_audio_caps_detected(
    self, stream_id: int, rate_hz: int, bit_depth: int
) -> None:
    """Phase 70 / DS-01 / Pitfall 4 DB-write-first invariant. ..."""
    try:
        # Step 1 — idempotency: skip if rate/depth already cached for this stream.
        if self._last_quality_payload.get(stream_id) == (rate_hz, bit_depth):
            return
        # ... DB write, cache update, fan-out to panel ...
        if hasattr(self.now_playing, "_refresh_quality_badge"):
            self.now_playing._refresh_quality_badge()
    except Exception:
        _log.exception("_on_audio_caps_detected: unhandled exception (stream_id=%r)", stream_id)
```
**New slot to add (NO DB write — detected values are transient per RESEARCH Finding 6):**
```python
def _on_audio_format_detected(
    self, stream_id: int, codec_norm: str, bitrate_kbps: int
) -> None:
    """Phase 98: cross-thread slot for Player.audio_format_detected.

    Bus-loop thread emits audio_format_detected(stream_id, codec_norm, bitrate_kbps);
    QueuedConnection delivers here on the main thread (qt-glib-bus-threading.md Rule 2).

    NOTE: detected codec/bitrate are NOT persisted to DB (RESEARCH Finding 6).
    The declared Stream.codec / Stream.bitrate_kbps remain the persistent source of
    truth (D-03). This slot delivers only to the panel for transient display.
    """
    try:
        if hasattr(self.now_playing, "update_detected_format"):
            self.now_playing.update_detected_format(stream_id, codec_norm, bitrate_kbps)
    except Exception:
        _log.exception("_on_audio_format_detected: unhandled exception (stream_id=%r)", stream_id)
```

**Slot for caps path — also extend to call new panel method** (inside `_on_audio_caps_detected`, after existing `_refresh_quality_badge` call, line ~773-776):
```python
# Step 5 — fan-out (hasattr-guarded for Wave 3 plan compat).
if hasattr(self.now_playing, "_refresh_quality_badge"):
    self.now_playing._refresh_quality_badge()
# Phase 98: also populate sample-rate / bit-depth stats rows.
if hasattr(self.now_playing, "update_detected_caps"):
    self.now_playing.update_detected_caps(stream_id, rate_hz, bit_depth)
```

**Cache init pattern** (line 540):
```python
self._last_quality_payload: dict[int, tuple[int, int]] = {}
```
Add alongside it if caching the format payload (optional — the slot is simple enough to skip the cache):
```python
self._last_format_payload: dict[int, tuple[str, int]] = {}  # Phase 98 idempotency
```

---

### `musicstreamer/ui_qt/now_playing_panel.py` — `_StatLabel`, four new rows, two new public methods

**Analogs (all same file):**
- `_MutedLabel` class: lines 179-201
- `_build_stats_widget`: lines 3471-3521
- `set_underrun_count`: lines 1171-1179
- `set_buffer_duration`: lines 1181-1203
- `set_stats_visible`: lines 1205-1207

**`_MutedLabel` class to subclass** (lines 179-201):
```python
class _MutedLabel(QLabel):
    """QLabel that renders WindowText in the Disabled palette color and
    re-applies the muted color whenever the application palette changes.
    Phase 47.1 D-10: stats-for-nerds rows read dimmer than primary labels.
    IN-03 / UAT follow-up: static palette capture broke on light/dark theme
    flips; overriding ``changeEvent`` keeps the muted color in sync.
    """
    def __init__(self, text: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self._apply_muted_palette()

    def _apply_muted_palette(self) -> None:
        pal = self.palette()
        muted = pal.color(QPalette.Disabled, QPalette.WindowText)
        pal.setColor(QPalette.WindowText, muted)
        self.setPalette(pal)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() in (QEvent.PaletteChange, QEvent.StyleChange):
            self._apply_muted_palette()
        super().changeEvent(event)
```
**New `_StatLabel` subclass to add immediately after `_MutedLabel`:**
```python
class _StatLabel(_MutedLabel):
    """_MutedLabel with amber mismatch state (Phase 98 D-02).

    set_mismatch(True) overrides WindowText with an amber color that
    survives light/dark theme flips via the inherited changeEvent.
    set_mismatch(False) falls back to the normal muted color.
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
        self._apply_muted_palette()

    def _apply_muted_palette(self) -> None:
        if not self._mismatch:
            super()._apply_muted_palette()
            return
        pal = self.palette()
        bg = pal.color(QPalette.Window)
        amber = self._AMBER_DARK if bg.lightness() < 128 else self._AMBER_LIGHT
        pal.setColor(QPalette.WindowText, amber)
        self.setPalette(pal)
```
Note: `QColor` is already imported via `from PySide6.QtGui import ... QPalette, QPixmap` (line 35); add `QColor` to that import.

**`_build_stats_widget` existing rows — exact pattern** (lines 3471-3521):
```python
def _build_stats_widget(self) -> QWidget:
    """Construct the stats-for-nerds wrapper (D-07/D-08/D-09). Phase 47.1."""
    wrapper = QWidget(self)
    form = QFormLayout(wrapper)
    form.setContentsMargins(0, 0, 0, 0)

    buffer_row_label = _MutedLabel("Buffer", wrapper)
    # ... QProgressBar row ...
    form.addRow(buffer_row_label, value_row)

    underrun_row_label = _MutedLabel("Underruns", wrapper)
    self._underrun_count_label = _MutedLabel("0", wrapper)
    form.addRow(underrun_row_label, self._underrun_count_label)

    buffer_duration_row_label = _MutedLabel("Buf duration", wrapper)
    self._buffer_duration_label = _MutedLabel(f"{BUFFER_DURATION_S}s", wrapper)
    form.addRow(buffer_duration_row_label, self._buffer_duration_label)

    # D-05: default hidden. MainWindow drives visibility from the QAction's
    # checked state after construction.
    wrapper.setVisible(False)
    return wrapper
```
**New rows to add BEFORE the existing Buffer row** (copy exact `addRow` pattern — no `setVisible` per row, Pitfall 8):
```python
# Phase 98 D-04: four actual-stream-format rows. No per-row setVisible — the
# wrapper-level setVisible(False) below governs all rows (Pitfall 8 / Phase 47.1).
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

**Existing setter pattern to mirror** (lines 1171-1203):
```python
def set_underrun_count(self, count: int) -> None:
    """Phase 78 / BUG-09 Commit A: receiver for Player.underrun_count_changed.
    Updates the Underruns stats-for-nerds row text to the new cumulative
    cycle count. ... wrapper-level set_stats_visible governs visibility ...
    """
    self._underrun_count_label.setText(str(int(count)))

def set_buffer_duration(self, seconds: int, is_adapted: bool) -> None:
    """Phase 84 / BUG-09 Commit B / D-12: receiver for Player.buffer_duration_changed.
    ... int() / bool() coercions are defensive ...
    Wrapper-level set_stats_visible governs visibility for this row + the
    Underruns row + the Buffer progressbar row — no per-row toggle code (Pitfall 8).
    """
    s = int(seconds)
    if bool(is_adapted):
        self._buffer_duration_label.setText(f"{s}s (adapted)")
    else:
        self._buffer_duration_label.setText(f"{s}s")
```
**New public methods to add alongside `set_underrun_count` / `set_buffer_duration`:**
```python
def update_detected_format(
    self,
    stream_id: int,
    detected_codec: str,      # normalised: "MP3"/"AAC"/"FLAC"/"OPUS"/"OGG"/""
    detected_bitrate_kbps: int,
) -> None:
    """Phase 98: populate Encoding/Bitrate stats rows from detected values.

    Retrieves declared codec/bitrate from self._streams (same source as
    stream picker labels) to build the detected + expected comparison (D-01).
    Mismatch flag (D-02) is applied via _StatLabel.set_mismatch.
    Not persisted to DB (RESEARCH Finding 6 — declared values remain source of truth).
    """
    declared = next((s for s in self._streams if s.id == stream_id), None)
    declared_codec = (declared.codec or "") if declared else ""
    declared_kbps  = int(declared.bitrate_kbps or 0) if declared else 0

    _BITRATE_TOLERANCE_KBPS = 5

    # Encoding row
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

    # Bitrate row
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

def update_detected_caps(self, stream_id: int, rate_hz: int, bit_depth: int) -> None:
    """Phase 98: populate Sample-rate and Bit-depth stats rows.

    Called from MainWindow._on_audio_caps_detected after the existing DB write
    + _refresh_quality_badge fan-out (RESEARCH §Pattern 7 Option 1).
    stream_id is accepted but not used — rows are panel-wide, not per-stream.
    """
    self._sample_rate_label.setText(
        f"{rate_hz / 1000:g} kHz" if rate_hz > 0 else "—"
    )
    self._bit_depth_label.setText(
        f"{bit_depth}-bit" if bit_depth > 0 else "—"
    )
```

**`bind_station` reset pattern** (lines 966-994, partial):
```python
def bind_station(self, station: Station) -> None:
    """Attach a Station and reset the panel for playback of that station."""
    self._station = station
    # ... name label, icy_label, star, logo resets ...
    self._last_cover_icy = None
    self._last_icy_title = ""
```
**Add to `bind_station` — reset format rows to em-dash on station switch (RESEARCH Pitfall 7):**
```python
# Phase 98: reset detected format rows on station switch (Pitfall 7 stale values).
self._encoding_label.setText("—")
self._encoding_label.set_mismatch(False)
self._bitrate_label.setText("—")
self._bitrate_label.set_mismatch(False)
self._sample_rate_label.setText("—")
self._bit_depth_label.setText("—")
```

---

### `tests/_fake_player.py` — add `audio_format_detected` Signal

**Analog:** Existing Signal block (lines 59-90), especially line 90:
```python
# Phase 70 / DS-01 caps signal (1)
audio_caps_detected = Signal(int, int, int)  # stream_id, rate_hz, bit_depth
```
**New line to add immediately after:**
```python
audio_format_detected = Signal(int, str, int)  # Phase 98: stream_id, codec_norm, bitrate_kbps
```
**Critical:** Must ship in the same plan wave as `audio_format_detected = Signal(int, str, int)` in `player.py` — the drift-guard `test_fake_player_mirrors_every_player_signal` fails the moment `player.py` has the signal but `_fake_player.py` does not (RESEARCH Pitfall 3, Finding 7).

---

### `tests/test_player_codec_tag.py` — new test file

**Analogs:**
- `tests/test_player_caps.py` (lines 1-224) — one-shot guard pattern, `make_player`, `waitSignal`, `assertNotEmitted`, disarm check
- `tests/test_player_tag.py` (lines 1-143) — `_fake_tag_msg` / `taglist.get_string` mock pattern

**`make_player` fixture pattern** (from `test_player_caps.py` lines 38-52 — module-local copy, do NOT import):
```python
def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out.
    Mirrors test_player_tag.py:28-38 pattern exactly (module-local copy for
    isolation — do NOT import from test_player_tag.py).
    """
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch(
        "musicstreamer.player.Gst.ElementFactory.make",
        return_value=mock_pipeline,
    ):
        player = Player()
    return player
```

**Fake tag message helper pattern** (from `test_player_tag.py` lines 41-46):
```python
def _fake_tag_msg(title, found=True):
    taglist = MagicMock()
    taglist.get_string.return_value = (found, title)
    msg = MagicMock()
    msg.parse_tag.return_value = taglist
    return msg
```
**New helper for codec/bitrate tag messages:**
```python
def _fake_codec_tag_msg(codec=None, nominal_bps=0, bitrate_bps=0):
    """Build a fake GStreamer tag message with codec/bitrate fields.

    taglist.get_string is called for TAG_AUDIO_CODEC;
    taglist.get_uint is called for TAG_NOMINAL_BITRATE and TAG_BITRATE.
    Uses side_effect lists to return different values per call site.
    """
    taglist = MagicMock()
    # get_string: first call = TAG_TITLE (found=False), second call = TAG_AUDIO_CODEC
    codec_found = codec is not None
    taglist.get_string.side_effect = [
        (False, None),                          # TAG_TITLE — no title → won't short-circuit
        (codec_found, codec or ""),             # TAG_AUDIO_CODEC
    ]
    taglist.get_uint.side_effect = [
        (nominal_bps > 0, nominal_bps),         # TAG_NOMINAL_BITRATE
        (bitrate_bps > 0, bitrate_bps),         # TAG_BITRATE
    ]
    msg = MagicMock()
    msg.parse_tag.return_value = taglist
    return msg
```
**Note:** The current `_on_gst_tag` calls `taglist.get_string(Gst.TAG_TITLE)` first. After the refactor (which moves the `if not found_title` check to after the preroll guard), the mock must reflect that the title lookup happens first via positional `side_effect`. Alternatively, use a `MagicMock` that routes by argument:
```python
def _fake_codec_tag_msg(codec=None, nominal_bps=0, bitrate_bps=0):
    taglist = MagicMock()
    def _get_string(tag):
        if "audio-codec" in str(tag):
            return (codec is not None, codec or "")
        return (False, None)  # TAG_TITLE not found
    taglist.get_string.side_effect = _get_string
    def _get_uint(tag):
        if "nominal" in str(tag):
            return (nominal_bps > 0, nominal_bps)
        return (bitrate_bps > 0, bitrate_bps)
    taglist.get_uint.side_effect = _get_uint
    msg = MagicMock()
    msg.parse_tag.return_value = taglist
    return msg
```

**One-shot guard test pattern** (from `test_player_caps.py` lines 142-166):
```python
def test_caps_no_double_emit_for_same_stream(qtbot):
    """Pitfall 6: after first emit the guard disarms; calling handler again
    does NOT emit a second audio_caps_detected for the same stream_id."""
    player = make_player(qtbot)
    player._caps_armed_for_stream_id = 42
    pad = _fake_caps_pad(96000, "S24LE")
    emission_count = []
    def _on_caps(*args):
        emission_count.append(args)
    player.audio_caps_detected.connect(_on_caps)
    player._on_caps_negotiated(pad, None)
    # After first emit, guard == 0, so second call must not emit
    player._on_caps_negotiated(pad, None)
    qtbot.waitUntil(lambda: True, timeout=200)
    assert len(emission_count) == 1, (
        f"expected exactly 1 emission, got {len(emission_count)} "
        "(Pitfall 6 one-shot guard failure)"
    )
```
Mirror exactly for codec: arm `_codec_tag_armed_for_stream_id`, call `_on_gst_tag` twice, assert 1 emission.

**Disarm-after-emit test pattern** (from `test_player_caps.py` lines 106-114):
```python
def test_caps_disarm_after_emit(qtbot):
    """Pitfall 6 one-shot guard: after _on_caps_negotiated emits,
    _caps_armed_for_stream_id is reset to 0."""
    player = make_player(qtbot)
    player._caps_armed_for_stream_id = 42
    pad = _fake_caps_pad(96000, "S24LE")
    with qtbot.waitSignal(player.audio_caps_detected, timeout=1000):
        player._on_caps_negotiated(pad, None)
    assert player._caps_armed_for_stream_id == 0
```
Mirror for codec: arm `_codec_tag_armed_for_stream_id = 42`, call `_on_gst_tag`, assert `_codec_tag_armed_for_stream_id == 0`.

**assertNotEmitted pattern** (from `test_player_caps.py` lines 117-127):
```python
def test_caps_ignores_unknown_format(qtbot):
    player = make_player(qtbot)
    player._caps_armed_for_stream_id = 42
    pad = _fake_caps_pad(96000, "GIBBERISH")
    with qtbot.assertNotEmitted(player.audio_caps_detected, wait=200):
        player._on_caps_negotiated(pad, None)
```
Mirror for preroll guard test: set `player._preroll_in_flight = True`, call `_on_gst_tag`, assert `audio_format_detected` NOT emitted.

---

### `tests/test_now_playing_stats.py` — new test file

**Analogs:**
- `tests/test_now_playing_panel.py` lines 39-115 — `FakeRepo`, `FakePlayer`, `_station()` factories
- `tests/test_now_playing_panel.py` lines 152-156 — `NowPlayingPanel(FakePlayer(), FakeRepo(...))` construction
- `tests/test_hi_res.py` lines 22-55 — truth-table helper pattern

**NowPlayingPanel construction pattern** (from `test_now_playing_panel.py` lines 152-155):
```python
def test_panel_construction(qtbot):
    panel = NowPlayingPanel(FakePlayer(), FakeRepo({"volume": "80"}))
    qtbot.addWidget(panel)
    assert panel.minimumWidth() == 560
```
**New panel tests use same construction:**
```python
def _make_panel(qtbot, streams=None):
    """Construct NowPlayingPanel with FakePlayer and a FakeRepo containing streams."""
    repo = FakeRepo({"volume": "80"})
    panel = NowPlayingPanel(FakePlayer(), repo)
    qtbot.addWidget(panel)
    if streams:
        # Inject streams directly so update_detected_format can look them up
        panel._streams = streams
    return panel
```

**FakeRepo pattern with stream support** (extend `test_now_playing_panel.py` lines 39-98):
```python
class FakeRepo:
    def __init__(self, settings=None, stations=None):
        self._settings = dict(settings or {})
        self._stations = list(stations or [])

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)

    def set_setting(self, key, value):
        self._settings[key] = value

    def list_stations(self):
        return list(self._stations)

    def list_streams(self, station_id):
        return []
    # ... (copy from test_now_playing_panel.py as needed)
```

**Source-grep truth-table test pattern** (from `test_player_caps.py` lines 87-103):
```python
def test_caps_emitted_as_queued_signal(qtbot):
    import inspect as _inspect
    import musicstreamer.player as player_module
    src = _inspect.getsource(player_module)
    lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
    joined = "\n".join(lines)
    assert "audio_caps_detected" in joined
    assert "QueuedConnection" in joined
```
Mirror for Pitfall 8 no-per-row-visibility test:
```python
def test_no_per_row_visible_in_build_stats(qtbot):
    import inspect
    from musicstreamer.ui_qt.now_playing_panel import NowPlayingPanel
    src = inspect.getsource(NowPlayingPanel._build_stats_widget)
    code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
    # Count setVisible calls inside _build_stats_widget; only the wrapper's
    # setVisible(False) is permitted (exactly 1 call).
    visible_calls = [l for l in code_lines if "setVisible" in l]
    assert len(visible_calls) == 1, (
        "Only wrapper.setVisible(False) is permitted in _build_stats_widget — "
        f"found {len(visible_calls)} setVisible calls (Pitfall 8)"
    )
```

---

## Shared Patterns

### Cross-Thread Guard: Disarm BEFORE Emit (Pitfall 6)
**Source:** `musicstreamer/player.py` lines 1285-1289 (`_on_caps_negotiated`)
**Apply to:** `_on_gst_tag` codec/bitrate block in `player.py`
```python
sid = self._caps_armed_for_stream_id
self._caps_armed_for_stream_id = 0          # disarm BEFORE emit — Pitfall 6
self.audio_caps_detected.emit(sid, rate, depth)
```

### QueuedConnection Signal Wiring
**Source:** `musicstreamer/ui_qt/main_window.py` lines 541-545
**Apply to:** New `audio_format_detected` connection in `main_window.py`
```python
self._player.audio_caps_detected.connect(
    self._on_audio_caps_detected, Qt.ConnectionType.QueuedConnection
)
```

### Never-Raise Slot Pattern
**Source:** `musicstreamer/ui_qt/main_window.py` lines 782-784
**Apply to:** `_on_audio_format_detected` slot body
```python
except Exception:
    _log.exception("_on_audio_caps_detected: unhandled exception (stream_id=%r)", stream_id)
```

### `_MutedLabel` changeEvent Theme-Safety
**Source:** `musicstreamer/ui_qt/now_playing_panel.py` lines 198-201
**Apply to:** `_StatLabel._apply_muted_palette` — must re-trigger on theme flip via inherited `changeEvent`
```python
def changeEvent(self, event: QEvent) -> None:
    if event.type() in (QEvent.PaletteChange, QEvent.StyleChange):
        self._apply_muted_palette()
    super().changeEvent(event)
```
`_StatLabel` inherits `changeEvent` from `_MutedLabel` — no need to override it, since `_apply_muted_palette` is already the dispatch point. The inherited `changeEvent` calls `self._apply_muted_palette()`, which dispatches to `_StatLabel._apply_muted_palette` via normal Python MRO.

### No Per-Row `setVisible` (Pitfall 8)
**Source:** `musicstreamer/ui_qt/now_playing_panel.py` lines 3499-3517
**Apply to:** All four new format rows in `_build_stats_widget`
The existing rows (Underruns, Buf duration) carry this comment:
```python
# the wrapper-level setVisible(False) below applies to BOTH rows —
# no per-row visibility code is needed (set_stats_visible governs both).
```

### FakePlayer Signal Parity (D-16)
**Source:** `tests/_fake_player.py` lines 54-90 + `tests/test_fake_player_signal_parity.py`
**Apply to:** `audio_format_detected` addition — must match production Signal arity exactly `Signal(int, str, int)`, in the same plan wave

---

## No Analog Found

All files in this phase have exact analogs. No new file requires patterns from RESEARCH.md alone.

---

## Critical Sequencing Note

The `_on_gst_tag` refactor (moving `if not found_title: return` to AFTER the new codec block, and moving the `_preroll_in_flight` check to cover both paths) changes the existing handler's control flow. The key structural change is:

**Before (lines 1134-1152):**
```
taglist = msg.parse_tag()
found, value = taglist.get_string(TAG_TITLE)     # title lookup first
_cancel_timers_requested.emit()
if not found: return                              # early-return on no title
if _preroll_in_flight: return                     # preroll guard AFTER title check
title_changed.emit(...)
```

**After (refactored for Phase 98):**
```
taglist = msg.parse_tag()
found_title, value = taglist.get_string(TAG_TITLE)
_cancel_timers_requested.emit()
if _preroll_in_flight: return                     # preroll guard covers BOTH paths
[new codec/bitrate block here]
if not found_title: return                        # title early-return AFTER codec block
title_changed.emit(...)
```

The existing `test_on_gst_tag_ignores_missing_title` test in `test_player_tag.py` must still pass after the refactor — the existing mock returns `(found=False, "")` for `get_string`, and the `_preroll_in_flight` default is `False`, so the flow correctly reaches `if not found_title: return` before `title_changed.emit`.

---

## Metadata

**Analog search scope:** `musicstreamer/player.py`, `musicstreamer/ui_qt/main_window.py`, `musicstreamer/ui_qt/now_playing_panel.py`, `tests/_fake_player.py`, `tests/test_player_caps.py`, `tests/test_player_tag.py`, `tests/test_now_playing_panel.py`, `tests/test_hi_res.py`, `tests/test_fake_player_signal_parity.py`
**Files read:** 9
**Pattern extraction date:** 2026-06-24
