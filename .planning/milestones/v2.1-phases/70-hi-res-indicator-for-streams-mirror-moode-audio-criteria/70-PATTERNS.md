# Phase 70: Hi-res indicator for streams (mirror moOde audio criteria) — Pattern Map

**Mapped:** 2026-05-11
**Files analyzed:** 21 (3 new + 18 modified)
**Analogs found:** 21 / 21 (all 100% in-tree templates — Phase 70 is a "join existing trails" phase)

## File Classification

### New files

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `musicstreamer/hi_res.py` | utility (pure helper module) | transform | `musicstreamer/stream_ordering.py` + `musicstreamer/eq_profile.py` | exact (one-concept-per-file pure-Python module with enum dicts) |
| `tests/test_hi_res.py` | test (unit) | request-response | `tests/test_stream_ordering.py` (parametrize + assert truth-table) | exact |
| `tests/test_player_caps.py` | test (integration) | event-driven | `tests/test_player_tag.py` (mocked-bus signal-emission pattern) | exact |

### Modified files

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------|------|-----------|----------------|---------------|
| `musicstreamer/models.py` | dataclass | n/a | self (Phase 47.1 `bitrate_kbps` append at line 21) | exact (in-file precedent) |
| `musicstreamer/repo.py` | model (SQLite CRUD) | CRUD | self lines 85-89 + 185-200 (Phase 47.2 `bitrate_kbps` migration shape) | exact (in-file precedent) |
| `musicstreamer/stream_ordering.py` | utility (sort) | transform | self lines 43-64 (extend the sort key) | exact (in-file precedent) |
| `musicstreamer/player.py` | service (GStreamer) | event-driven | self lines 674-707 (`_on_gst_tag` / `_on_gst_buffering` bus → queued-signal) | exact (in-file precedent) |
| `musicstreamer/settings_export.py` | service (export/import) | CRUD + forward-compat | self lines 118-130, 405-420, 461-477 (Phase 47.3 forward-compat idiom) | exact (in-file precedent) |
| `musicstreamer/ui_qt/now_playing_panel.py` | component (badge + picker) | request-response | self lines 369-395 (`_live_badge`) + 1424-1483 (`_refresh_live_status`) + 1028-1037 (`_populate_stream_picker`) | exact (in-file precedent) |
| `musicstreamer/ui_qt/station_star_delegate.py` | delegate (paint) | transform | self lines 55-99 (Phase 54 BUG-05 multi-pixmap paint train) | exact (in-file extension) |
| `musicstreamer/ui_qt/station_tree_model.py` | model (Qt) | request-response | self lines 144-173 (`data(index, role)` UserRole hook) | exact (in-file precedent) — OPTIONAL per RESEARCH OQ 2 |
| `musicstreamer/ui_qt/station_list_panel.py` | component (panel + chip) | request-response | self lines 271-298 (`_live_chip`) + 554-587 (`update_live_map` / `set_live_chip_visible`) | exact (in-file precedent) |
| `musicstreamer/ui_qt/station_filter_proxy.py` | proxy (filter) | transform | self lines 57-79 + 106-148 (Phase 68 `set_live_map` / `set_live_only` + Pitfall 7) | exact (in-file precedent) |
| `musicstreamer/ui_qt/edit_station_dialog.py` | component (dialog) | CRUD | self lines 208-213 + 398-414 (column constants + `_BitrateDelegate`) | exact (in-file precedent) |
| `musicstreamer/ui_qt/main_window.py` | wiring | event-driven | self lines 346-351 (Phase 68 `live_map_changed` fan-out) | exact (in-file precedent) |
| `tests/test_repo.py` | test (unit) | CRUD | self lines 529-579 (Phase 47.2 `bitrate_kbps` hydrate + idempotent ALTER) | exact |
| `tests/test_stream_ordering.py` | test (unit) | request-response | self lines 147-172 (`test_gbs_flac_ordering` regression target) | exact |
| `tests/test_settings_export.py` | test (integration) | CRUD | self lines 611-720 (Phase 47.3 `bitrate_kbps` round-trip + missing-key fwd-compat) | exact |
| `tests/test_station_filter_proxy.py` | test (integration) | request-response | self lines 215-271 (Phase 68 `set_live_only` + Pitfall 7 invalidate-guard) | exact |
| `tests/test_now_playing_panel.py` | test (integration) | request-response | (badge visibility + picker formatter tests — pattern from Phase 68 `_live_badge` tests) | role-match |
| `tests/test_station_list_panel.py` | test (integration) | request-response | (chip-visibility tests — pattern from Phase 68 `_live_chip`) | role-match |
| `tests/test_edit_station_dialog.py` | test (integration) | request-response | (existing column tests — extend with audio-quality column) | role-match |
| `tests/test_station_star_delegate.py` | test (integration) | request-response | self (Phase 54 paint + sizeHint geometry tests) | exact |
| `.planning/REQUIREMENTS.md` | requirements (doc) | n/a | self `### Features (FEAT)` section | exact |
| `.planning/ROADMAP.md` | roadmap (doc) | n/a | self Phase 70 entry | exact |

---

## Pattern Assignments

### `musicstreamer/hi_res.py` (NEW — utility, transform)

**Analog A (module shape):** `musicstreamer/eq_profile.py` — one-concept-per-file, pure helpers, dataclass + module-level regexes/constants.
**Analog B (enum-dict idiom):** `musicstreamer/stream_ordering.py` lines 17-22 — small `_CODEC_RANK = {...}` dict + helper that does `(value or "").strip().upper()` lookup with `.get(key, 0)`.

**Module header pattern** (copy from `eq_profile.py:1-8`):
```python
"""Hi-Res audio classification helpers (Phase 70).

Pure functions — no GStreamer imports, no I/O, no Qt.
Mirrors stream_ordering.py shape (small enum-mapped helpers).

Public API:
  bit_depth_from_format(format_str: str) -> int
  classify_tier(codec: str, sample_rate_hz: int, bit_depth: int) -> str
  best_tier_for_station(station: Station) -> str

Constants:
  TIER_LABEL_BADGE: dict[str, str]   # uppercase badge labels
  TIER_LABEL_PROSE: dict[str, str]   # title-case prose labels
"""
from __future__ import annotations
```

**Enum-dict pattern** (copy shape from `stream_ordering.py:17-22`):
```python
# D-05: FLAC=3 > AAC=2 > MP3=1 > other=0.
_CODEC_RANK = {"FLAC": 3, "AAC": 2, "MP3": 1}

# WR-01: quality tier is the primary sort key so hi-MP3-320 beats med-AAC-128.
# hi=3, med=2, low=1, unknown/custom=0 (falls through to codec+bitrate ordering).
_QUALITY_RANK = {"hi": 3, "med": 2, "low": 1}
```

Phase 70 equivalent (per RESEARCH lines 365-378):
```python
_FORMAT_BIT_DEPTH = {
    "S8": 0, "U8": 0,
    "S16LE": 16, "S16BE": 16, "U16LE": 16, "U16BE": 16,
    "S24LE": 24, "S24BE": 24, "U24LE": 24, "U24BE": 24,
    "S24_32LE": 24, "S24_32BE": 24, "U24_32LE": 24, "U24_32BE": 24,
    "S32LE": 32, "S32BE": 32, "U32LE": 32, "U32BE": 32,
    "F32LE": 32, "F32BE": 32,
    "F64LE": 32, "F64BE": 32,
}
_HIRES_RATE_THRESHOLD_HZ = 48_000
_HIRES_BIT_DEPTH_THRESHOLD = 16
_LOSSLESS_CODECS = {"FLAC", "ALAC"}
```

**Case-/None-safe lookup pattern** (copy from `stream_ordering.py:25-31`):
```python
def codec_rank(codec: str) -> int:
    """Case-insensitive, whitespace-tolerant, None-safe."""
    return _CODEC_RANK.get((codec or "").strip().upper(), 0)
```

Phase 70 `classify_tier` follows the same shape — `(codec or "").strip().upper()` then membership-test against `_LOSSLESS_CODECS`.

**i18n forward-compat constant pattern** (UI-SPEC §Copywriting Contract):
```python
TIER_LABEL_BADGE: dict[str, str] = {"hires": "HI-RES", "lossless": "LOSSLESS", "": ""}
TIER_LABEL_PROSE: dict[str, str] = {"hires": "Hi-Res",  "lossless": "Lossless", "": ""}
```

---

### `musicstreamer/models.py` (modify — dataclass)

**Analog:** self lines 11-21 (Phase 47.1 D-01 append-after precedent for positional-construction compat).

**Field-append pattern** (copy from existing `StationStream` lines 11-21):
```python
@dataclass
class StationStream:
    id: int
    station_id: int
    url: str
    label: str = ""
    quality: str = ""        # "hi" | "med" | "low" | custom string
    position: int = 1
    stream_type: str = ""    # "shoutcast" | "youtube" | "hls" | ""
    codec: str = ""          # "MP3" | "AAC" | "OPUS" | "FLAC" | ""
    bitrate_kbps: int = 0     # numeric bitrate in kbps; 0 = unknown (D-01)
    # Phase 70 — append AFTER bitrate_kbps to preserve positional-construction
    # compat with aa_import / yt_import / discovery_dialog / settings_export.
    sample_rate_hz: int = 0   # 0 = unknown until first caps detection (DS-05)
    bit_depth: int = 0        # 0 = unknown until first caps detection (DS-05)
```

---

### `musicstreamer/repo.py` (modify — model, CRUD)

**Analog:** self lines 51-89 + 176-201 (Phase 47.2 `bitrate_kbps` migration shape).

**CREATE TABLE body pattern** (copy from lines 51-62, append two columns after line 60):
```python
CREATE TABLE IF NOT EXISTS station_streams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    label TEXT NOT NULL DEFAULT '',
    quality TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 1,
    stream_type TEXT NOT NULL DEFAULT '',
    codec TEXT NOT NULL DEFAULT '',
    bitrate_kbps INTEGER NOT NULL DEFAULT 0,
    sample_rate_hz INTEGER NOT NULL DEFAULT 0,  -- Phase 70
    bit_depth INTEGER NOT NULL DEFAULT 0,        -- Phase 70
    FOREIGN KEY(station_id) REFERENCES stations(id) ON DELETE CASCADE
);
```

**Idempotent ALTER TABLE pattern** (copy verbatim from lines 85-89, repeat twice):
```python
try:
    con.execute("ALTER TABLE station_streams ADD COLUMN bitrate_kbps INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists
```

Phase 70 adds two new try/except blocks below the existing one (mirrors verbatim — RESEARCH Pitfall 5):
```python
try:
    con.execute("ALTER TABLE station_streams ADD COLUMN sample_rate_hz INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists

try:
    con.execute("ALTER TABLE station_streams ADD COLUMN bit_depth INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists
```

**`list_streams` hydration pattern** (copy from lines 176-183, add two row reads):
```python
def list_streams(self, station_id: int) -> List[StationStream]:
    rows = self.con.execute(
        "SELECT * FROM station_streams WHERE station_id=? ORDER BY position", (station_id,)
    ).fetchall()
    return [StationStream(id=r["id"], station_id=r["station_id"], url=r["url"],
            label=r["label"], quality=r["quality"], position=r["position"],
            stream_type=r["stream_type"], codec=r["codec"],
            bitrate_kbps=r["bitrate_kbps"]) for r in rows]
```

Phase 70 appends `sample_rate_hz=r["sample_rate_hz"], bit_depth=r["bit_depth"]` to the constructor.

**`insert_stream` / `update_stream` signature pattern** (copy from lines 185-201):
```python
def insert_stream(self, station_id: int, url: str, label: str = "",
                  quality: str = "", position: int = 1,
                  stream_type: str = "", codec: str = "",
                  bitrate_kbps: int = 0) -> int:
    cur = self.con.execute(
        "INSERT INTO station_streams(station_id,url,label,quality,position,stream_type,codec,bitrate_kbps) VALUES(?,?,?,?,?,?,?,?)",
        (station_id, url, label, quality, position, stream_type, codec, bitrate_kbps))
    self.con.commit()
    return int(cur.lastrowid)

def update_stream(self, stream_id: int, url: str, label: str,
                  quality: str, position: int, stream_type: str, codec: str,
                  bitrate_kbps: int = 0):
    self.con.execute(
        "UPDATE station_streams SET url=?,label=?,quality=?,position=?,stream_type=?,codec=?,bitrate_kbps=? WHERE id=?",
        (url, label, quality, position, stream_type, codec, bitrate_kbps, stream_id))
    self.con.commit()
```

Phase 70 appends `, sample_rate_hz: int = 0, bit_depth: int = 0` to both signatures (kwargs at the tail — RESEARCH Assumption A6 preserves positional compat for all existing callers: `aa_import`, `yt_import`, `edit_station_dialog`, `discovery_dialog`, `settings_export`).

---

### `musicstreamer/stream_ordering.py` (modify — utility, transform)

**Analog:** self lines 43-64.

**Sort-key extension pattern** (current state lines 52-63):
```python
known = [s for s in streams if (s.bitrate_kbps or 0) > 0]
unknown = [s for s in streams if (s.bitrate_kbps or 0) <= 0]
known_sorted = sorted(
    known,
    key=lambda s: (
        -quality_rank(s.quality),
        -codec_rank(s.codec),
        -(s.bitrate_kbps or 0),
        s.position,
    ),
)
unknown_sorted = sorted(unknown, key=lambda s: s.position)
return known_sorted + unknown_sorted
```

Phase 70 S-01 inserts two terms between `-bitrate_kbps` and `position` (CONTEXT.md decision):
```python
key=lambda s: (
    -quality_rank(s.quality),
    -codec_rank(s.codec),
    -(s.bitrate_kbps or 0),
    -(s.sample_rate_hz or 0),   # Phase 70 / S-01
    -(s.bit_depth or 0),         # Phase 70 / S-01
    s.position,
),
```

Unknown rate/depth (0) keep current behavior — sort behind known via the `-x or 0` negation (0 ties, falls through to position).

---

### `musicstreamer/player.py` (modify — service, event-driven)

**Analog:** self lines 265-273 (Signal class-attribute declarations) + 381-401 (queued-connection wiring) + 674-707 (bus-handler → queued-Signal pattern) + 736-746 (main-thread state-changed slot).

**Class-level queued Signal declaration pattern** (copy shape from lines 265-273):
```python
# Phase 57 / WIN-03 D-12: bus-loop -> main: re-apply self._volume after every
# transition to PLAYING.
_playbin_playing_state_reached = Signal()    # bus-loop -> main

# Phase 62 / BUG-09: buffer-underrun cycle Signals.
_underrun_cycle_opened    = Signal()         # bus-loop → main: arm dwell timer
_underrun_cycle_closed    = Signal(object)   # bus-loop → main: log + cancel dwell
underrun_recovery_started = Signal()         # main → MainWindow: show_toast
```

Phase 70 adds (RESEARCH Pattern 1, Pitfall 9 Option A):
```python
# Phase 70 / DS-01: audio sink pad caps detection.
# Streaming/bus-loop thread → main: persist sample_rate_hz / bit_depth
# to the playing stream's row in repo via MainWindow fan-out.
audio_caps_detected = Signal(int, int, int)  # stream_id, rate_hz, bit_depth
```

**Queued-connection wiring pattern** (copy verbatim from lines 381-401):
```python
# 43.1 follow-up: queue bus-loop → main for timer/recovery work.
self._cancel_timers_requested.connect(
    self._cancel_timers, Qt.ConnectionType.QueuedConnection
)
...
# Phase 57 / WIN-03 D-12: queue bus-loop -> main re-apply on PLAYING.
self._playbin_playing_state_reached.connect(
    self._on_playbin_state_changed, Qt.ConnectionType.QueuedConnection
)
```

Phase 70 wiring (per RESEARCH Pitfall 9 Option A — MainWindow connects, NOT Player itself, because Player has no repo handle):
```python
# Phase 70 — caps detection emits to MainWindow (Pitfall 9 Option A).
# Player does NOT call repo.update_stream directly; MainWindow's
# slot fans out repo write + UI refresh.
# NOTE: connected at MainWindow level — see main_window.py wiring below.
```

**Bus-handler emit-only pattern** (copy from lines 674-707, Phase 43.1 Pitfall 2 invariant):
```python
def _on_gst_tag(self, bus, msg) -> None:
    taglist = msg.parse_tag()
    found, value = taglist.get_string(Gst.TAG_TITLE)
    # Audio arrived -- cancel failover timer on the main thread via queued
    # signal. Bus-loop thread has no Qt event loop, so singleShot vanishes.
    self._cancel_timers_requested.emit()
    if not found:
        return
    title = _fix_icy_encoding(value)
    self.title_changed.emit(title)  # auto-queued cross-thread to main

def _on_gst_buffering(self, bus, msg) -> None:
    """Bus-loop-thread handler: parse buffer percent, emit Qt signal.

    Runs on GstBusLoopThread (not main thread). May only emit signals,
    never touch Qt widgets directly (Pitfall 2)."""
    ...
    self.buffer_percent.emit(percent)  # auto-queued cross-thread to main
```

Phase 70 caps handler follows this exact shape (RESEARCH Pattern 1, lines 279-307): runs on the streaming thread, may ONLY emit `audio_caps_detected`, never touch `self._pipeline.set_property(...)` or repo or any Qt widget.

**Main-thread state-changed slot pattern** (copy from lines 736-746 — Pattern 1b sync-read fallback):
```python
def _on_playbin_state_changed(self) -> None:
    """Main-thread slot (Phase 57 / WIN-03 D-12 + D-13).

    Re-applies the user's last-set volume to playbin3.volume on every
    transition to PLAYING."""
```

Phase 70 hooks the same slot to do the SYNCHRONOUS one-shot caps read (Pattern 1b — RESEARCH lines 310-314): inside this slot, call `pad = self._pipeline.emit("get-audio-pad", 0); caps = pad.get_current_caps()` and if non-None, `audio_caps_detected.emit(...)` directly on main; otherwise wire `notify::caps` on the pad as the deferred async path.

**Anti-pattern reminder** (RESEARCH lines 593-601):
- DO NOT call `QTimer.singleShot(0, fn)` from the streaming-thread caps handler — Phase 43.1 Pitfall 2.
- DO NOT mutate `self._pipeline.set_property(...)` from the caps handler.
- DO NOT auto-correct codec from caps — DS-03.

---

### `musicstreamer/settings_export.py` (modify — service, CRUD)

**Analog:** self lines 108-130 (`_station_to_dict`) + 405-420 (`_insert_station`) + 461-477 (`_replace_station`).

**`_station_to_dict` extension pattern** (copy from lines 118-130, add two keys):
```python
"streams": [
    {
        "url": s.url,
        "label": s.label,
        "quality": s.quality,
        "position": s.position,
        "stream_type": s.stream_type,
        "codec": s.codec,
        "bitrate_kbps": s.bitrate_kbps,
        # Phase 70 — added two keys after bitrate_kbps.
        "sample_rate_hz": s.sample_rate_hz,
        "bit_depth": s.bit_depth,
    }
    for s in station.streams
],
```

**`_insert_station` forward-compat pattern** (copy from lines 405-420 verbatim shape):
```python
for stream in data.get("streams", []):
    repo.con.execute(
        "INSERT INTO station_streams"
        "(station_id, url, label, quality, position, stream_type, codec, bitrate_kbps) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            station_id,
            stream.get("url", ""),
            stream.get("label", ""),
            stream.get("quality", ""),
            stream.get("position", 1),
            stream.get("stream_type", ""),
            stream.get("codec", ""),
            int(stream.get("bitrate_kbps", 0) or 0),  # P-2 forward-compat + defense
        ),
    )
```

Phase 70 extends the column list (`+ ", sample_rate_hz, bit_depth"`), placeholders (`,?,?`), and adds two `int(stream.get(...))` lines (RESEARCH Pattern 4 lines 446-462):
```python
"(station_id, url, label, quality, position, stream_type, codec, bitrate_kbps, "
"sample_rate_hz, bit_depth) "
"VALUES (?,?,?,?,?,?,?,?,?,?)",
(
    station_id,
    stream.get("url", ""),
    stream.get("label", ""),
    stream.get("quality", ""),
    stream.get("position", 1),
    stream.get("stream_type", ""),
    stream.get("codec", ""),
    int(stream.get("bitrate_kbps", 0) or 0),     # P-2 forward-compat
    int(stream.get("sample_rate_hz", 0) or 0),   # Phase 70 forward-compat
    int(stream.get("bit_depth", 0) or 0),        # Phase 70 forward-compat
),
```

**`_replace_station` pattern** is identical to `_insert_station` (lines 461-477) — apply the same two-line extension. The `int(x or 0)` idiom (line 418, line 474) neutralizes missing key + None + empty string + malformed value in one expression.

---

### `musicstreamer/ui_qt/now_playing_panel.py` (modify — component)

**Analog A (badge construction):** self lines 369-395 (`_live_badge` QLabel + QSS).
**Analog B (badge refresh slot):** self lines 1424-1483 (`_refresh_live_status`).
**Analog C (picker formatter):** self lines 1028-1037 (`_populate_stream_picker`).

**Badge QLabel pattern** (copy verbatim from lines 381-393):
```python
self._live_badge = QLabel("LIVE", self)
self._live_badge.setTextFormat(Qt.PlainText)
self._live_badge.setVisible(False)
self._live_badge.setStyleSheet(
    "QLabel {"
    " background-color: palette(highlight);"
    " color: palette(highlighted-text);"
    " border-radius: 8px;"
    " padding: 2px 6px;"
    " font-weight: bold;"
    "}"
)
icy_row.addWidget(self._live_badge)
icy_row.addWidget(self.icy_label, 1)   # stretch=1 so icy_label fills
```

Phase 70 creates `_quality_badge` with identical QSS (UI-SPEC DP-07 / DP-04 verbatim) and inserts BEFORE `_live_badge` (final order `[QUALITY] 6px [LIVE] 6px [icy_label]`):
```python
self._quality_badge = QLabel("", self)           # text set in _refresh_quality_badge
self._quality_badge.setTextFormat(Qt.PlainText)
self._quality_badge.setVisible(False)
self._quality_badge.setStyleSheet(<same QSS verbatim>)
icy_row.addWidget(self._quality_badge)            # FIRST (left)
icy_row.addWidget(self._live_badge)               # SECOND
icy_row.addWidget(self.icy_label, 1)              # stretch — fills remaining
```

**Refresh-slot pattern** (copy shape from lines 1424-1483 — `_refresh_live_status`):
```python
def _refresh_live_status(self) -> None:
    """Single coupling point per CONTEXT C-03. Slots-never-raise: any
    exception hides the badge silently."""
    try:
        ...
        self._live_badge.setVisible(is_live)
        ...
    except Exception:
        try:
            self._live_badge.setVisible(False)
        except Exception:
            pass
```

Phase 70 `_refresh_quality_badge` mirrors this shape:
- read `self._station.streams` (avoid repo round-trip per RESEARCH OQ 1),
- find the currently-playing stream's `sample_rate_hz` + `bit_depth`,
- compute `tier = classify_tier(s.codec, s.sample_rate_hz, s.bit_depth)`,
- `self._quality_badge.setText(TIER_LABEL_BADGE[tier])`,
- `self._quality_badge.setVisible(bool(tier))`,
- `self._quality_badge.setToolTip(...)` per UI-SPEC Copywriting Contract,
- `self._quality_badge.setAccessibleName(f"Stream quality: {TIER_LABEL_PROSE[tier]}")`,
- slot-never-raise guard wrapping the body.

Wired from: `_on_station_bind` + main-thread `audio_caps_detected` payload + theme refresh.

**Stream picker formatter pattern** (current lines 1028-1037):
```python
def _populate_stream_picker(self, station) -> None:
    streams = self._repo.list_streams(station.id)
    self._streams = streams
    self.stream_combo.blockSignals(True)
    self.stream_combo.clear()
    for s in streams:
        label = f"{s.quality} — {s.codec}" if s.codec else s.quality or s.label or "stream"
        self.stream_combo.addItem(label, userData=s.id)
    self.stream_combo.blockSignals(False)
    self.stream_combo.setVisible(len(streams) > 1)
```

Phase 70 DP-05 / UI-SPEC OD-7 — append " — {TIER}" when tier is non-empty:
```python
for s in streams:
    base_label = f"{s.quality} — {s.codec}" if s.codec else s.quality or s.label or "stream"
    tier = classify_tier(s.codec, s.sample_rate_hz, s.bit_depth)
    tier_suffix = TIER_LABEL_BADGE.get(tier, "")
    label = f"{base_label} — {tier_suffix}" if tier_suffix else base_label
    self.stream_combo.addItem(label, userData=s.id)
```

Em-dash `—` reused verbatim (matches existing line 1035 separator).

---

### `musicstreamer/ui_qt/station_star_delegate.py` (modify — delegate)

**Analog:** self lines 55-79 (`paint()`) + 85-99 (`sizeHint()`) — Phase 54 BUG-05 already trained this delegate for multi-pixmap painting (UI-SPEC DP-03 lock).

**Star geometry constant pattern** (current lines 23-32):
```python
_STAR_SIZE = 20
_STAR_MARGIN = 4
_PROVIDER_TREE_MIN_ROW_HEIGHT = 32
```

Phase 70 adds (RESEARCH Pattern 6 + UI-SPEC §Component Inventory item 2):
```python
_PILL_PADDING_X = 6   # horizontal inner padding (matches Phase 68 LIVE QSS)
_PILL_PADDING_Y = 4   # vertical inner padding
_PILL_TO_STAR_GAP = 8 # gap between pill right edge and star left edge
_PILL_RADIUS = 8      # corner radius (matches Phase 68 LIVE)
```

**`_star_rect` geometry helper pattern** (copy shape from lines 35-39):
```python
def _star_rect(row_rect: QRect) -> QRect:
    """Compute the 20x20 star icon rect, right-aligned with STAR_MARGIN from edge."""
    x = row_rect.right() - _STAR_SIZE - _STAR_MARGIN
    y = row_rect.top() + (row_rect.height() - _STAR_SIZE) // 2
    return QRect(x, y, _STAR_SIZE, _STAR_SIZE)
```

Phase 70 adds `_pill_rect(row_rect, pill_width)` (right-aligned LEFT of `_star_rect`, vertically centered — UI-SPEC OD-1).

**`paint()` extension pattern** (current lines 55-79):
```python
def paint(self, painter, option, index) -> None:
    station = index.data(Qt.UserRole)
    if isinstance(station, Station):
        option.decorationSize = QSize(STATION_ICON_SIZE, STATION_ICON_SIZE)
        option.decorationAlignment = Qt.AlignVCenter | Qt.AlignLeft
    super().paint(painter, option, index)
    if not isinstance(station, Station):
        return  # provider row — no star

    is_fav = self._repo.is_favorite_station(station.id)
    icon_name = "starred-symbolic" if is_fav else "non-starred-symbolic"
    icon = QIcon.fromTheme(icon_name, QIcon(f":/icons/{icon_name}.svg"))

    rect = _star_rect(option.rect)
    icon.paint(painter, rect, Qt.AlignCenter, QIcon.Normal, QIcon.On)
```

Phase 70 inserts pill paint between `super().paint(...)` and the star paint, ONLY for station rows (provider-row safety per UI-SPEC §Component Inventory item 2). Use `QPainter` primitives directly (NO QSS — QSS doesn't flow into delegate paint, UI-SPEC §Color "Delegate paint setup"):

```python
# Phase 70 — paint quality pill BEFORE the star, in the same column.
from musicstreamer.hi_res import best_tier_for_station, TIER_LABEL_BADGE
tier = best_tier_for_station(station)
if tier:
    label = TIER_LABEL_BADGE[tier]
    text_font = QFont(option.font); text_font.setBold(True)
    painter.save()
    painter.setFont(text_font)
    fm = painter.fontMetrics()
    text_w = fm.horizontalAdvance(label)
    pill_w = text_w + 2 * _PILL_PADDING_X
    pill_h = fm.height() + 2 * _PILL_PADDING_Y
    r = _pill_rect(option.rect, pill_w, pill_h)
    # UI-SPEC §Color OD-3: swap fill/text under State_Selected so the pill
    # stays visible against the selected-row palette(highlight) background.
    if option.state & QStyle.State_Selected:
        pill_fill = option.palette.color(QPalette.HighlightedText)
        pill_text = option.palette.color(QPalette.Highlight)
    else:
        pill_fill = option.palette.color(QPalette.Highlight)
        pill_text = option.palette.color(QPalette.HighlightedText)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(pill_fill)
    painter.drawRoundedRect(r, _PILL_RADIUS, _PILL_RADIUS)
    painter.setPen(pill_text)
    painter.drawText(r, Qt.AlignCenter, label)
    painter.restore()
```

**`sizeHint()` extension pattern** (current lines 85-99):
```python
def sizeHint(self, option, index) -> QSize:
    base = super().sizeHint(option, index)
    station = index.data(Qt.UserRole)
    if isinstance(station, Station):
        h = max(base.height(), STATION_ICON_SIZE)
        return QSize(base.width() + _STAR_SIZE + _STAR_MARGIN, h)
    h = max(base.height(), _PROVIDER_TREE_MIN_ROW_HEIGHT)
    return QSize(base.width(), h)
```

Phase 70 grows station-row width by `pill_w + _PILL_TO_STAR_GAP` (UI-SPEC §Spacing Scale sample math) — for worst-case "LOSSLESS" pill (~78 px), the new width is `base.width() + _STAR_SIZE + _STAR_MARGIN + 78 + _PILL_TO_STAR_GAP`. Height unchanged (32 px floor already exceeds pill ~22 px).

---

### `musicstreamer/ui_qt/station_tree_model.py` (modify — model — OPTIONAL per RESEARCH OQ 2)

**Analog:** self lines 144-173 (`data(index, role)` UserRole dispatch).

**UserRole branch pattern** (current lines 161-173):
```python
def data(self, index: QModelIndex, role=Qt.DisplayRole):
    if not index.isValid():
        return None
    node: _TreeNode = index.internalPointer()
    if node is None:
        return None
    if role == Qt.DisplayRole:
        return node.label
    if role == Qt.DecorationRole and node.kind == "station":
        return load_station_icon(node.station)
    if role == Qt.FontRole and node.kind == "provider":
        f = QFont()
        f.setBold(True)
        f.setPointSize(13)
        return f
    if role == Qt.UserRole and node.kind == "station":
        return node.station
    return None
```

Phase 70 OPTIONAL: add a new role constant `QUALITY_TIER_ROLE = Qt.UserRole + 1` and branch returning `best_tier_for_station(node.station)`. RESEARCH OQ 2 recommends **skipping** this for now — deriving on each paint is O(streams per station) on 50-200 stations (~tiny). Add only if profiling shows a regression.

---

### `musicstreamer/ui_qt/station_list_panel.py` (modify — component)

**Analog A (chip construction + QSS):** self lines 53-67 (`_CHIP_QSS`) + 271-298 (`_live_chip`).
**Analog B (chip visibility gate):** self lines 565-587 (`update_live_map` + `set_live_chip_visible`).

**Chip QSS pattern** (current lines 53-67 — reused verbatim for `_hi_res_chip`):
```python
_CHIP_QSS = """
QPushButton[chipState="unselected"] {
    background-color: palette(base);
    border: 1px solid palette(mid);
    border-radius: 12px;
    padding: 4px 8px;
}
QPushButton[chipState="selected"] {
    background-color: palette(highlight);
    color: palette(highlighted-text);
    border: 1px solid palette(highlight);
    border-radius: 12px;
    padding: 4px 8px;
}
"""
```

**Chip construction pattern** (copy from lines 280-298):
```python
live_chip_row = QWidget(stations_page)
lc_layout = QHBoxLayout(live_chip_row)
lc_layout.setContentsMargins(16, 4, 16, 0)
self._live_chip = QPushButton("Live now", live_chip_row)
self._live_chip.setCheckable(True)
self._live_chip.setProperty("chipState", "unselected")
self._live_chip.setStyleSheet(_CHIP_QSS)
# F-07: initial visibility from settings — visible iff a listen key
# is currently saved.
_get_setting = getattr(self._repo, "get_setting", None)
_has_aa_key = bool(_get_setting("audioaddict_listen_key", "") if _get_setting else "")
self._live_chip.setVisible(_has_aa_key)
lc_layout.addWidget(self._live_chip)
lc_layout.addStretch(1)
sp_layout.addWidget(live_chip_row)
# QA-05: bound method connection (no self-capturing lambda).
self._live_chip.toggled.connect(self._on_live_chip_toggled)
```

Phase 70 mirrors this exactly — UI-SPEC §Component Inventory item 5 locks placement INSIDE the existing `live_chip_row` (with `setSpacing(8)` between chips) OR a new sibling row. Initial visibility: `setVisible(False)` (F-02 default — gated by `set_quality_map` discovering a hi-res entry).

**Chip toggle slot pattern** (current lines 554-563):
```python
def _on_live_chip_toggled(self, checked: bool) -> None:
    """Phase 68 / F-02: drive proxy live-only predicate from chip toggle.

    Mirrors `_on_provider_chip_clicked` / `_on_tag_chip_clicked` — updates
    the chipState style property (so the QSS picks up the selected look)
    and forwards to the proxy. The proxy invalidates and the tree
    re-filters automatically.
    """
    self._set_chip_state(self._live_chip, checked)
    self._proxy.set_live_only(checked)
```

Phase 70 `_on_hi_res_chip_toggled` mirrors this verbatim — call `self._proxy.set_hi_res_only(checked)`.

**Update-map fan-out pattern** (current lines 565-572):
```python
def update_live_map(self, live_map: dict) -> None:
    """Phase 68 / B-02: forward poll-result live_map into the filter proxy.

    MainWindow calls this from NowPlayingPanel's poll callback chain.
    Pitfall 7 is implemented inside the proxy: invalidate fires only when
    live_only is currently active.
    """
    self._proxy.set_live_map(live_map)
```

Phase 70 adds an analogous `update_quality_map(quality_map: dict[int, str])` that forwards to `self._proxy.set_quality_map(...)` AND calls `self.set_hi_res_chip_visible(any(t == "hires" for t in quality_map.values()))` (per RESEARCH OQ 4 — re-evaluate visibility on every map update).

**Chip-visibility gate pattern** (current lines 574-587):
```python
def set_live_chip_visible(self, visible: bool) -> None:
    """Phase 68 / F-07 / N-03: reactive chip visibility for key save/clear."""
    self._live_chip.setVisible(visible)
    if not visible and self._live_chip.isChecked():
        self._live_chip.setChecked(False)  # fires toggled -> _on_live_chip_toggled
```

Phase 70 `set_hi_res_chip_visible(visible: bool)` mirrors this — flip visibility AND uncheck if hiding while checked (prevents stuck filter).

---

### `musicstreamer/ui_qt/station_filter_proxy.py` (modify — proxy)

**Analog:** self lines 33-100 (state + setters + `clear_all` + `has_active_filter`) + 106-148 (`filterAcceptsRow`).

**Predicate-state pattern** (current lines 33-39 — Phase 68 / F-02 / Pitfall 7):
```python
# Phase 68 / F-02 / F-04 / Pitfall 7: live-only predicate state.
#   _live_only: True when the "Live now" chip is engaged.
#   _live_channel_keys: set of AA channel keys currently broadcasting
#     a live show; updated by set_live_map from MainWindow when a
#     poll cycle completes.
self._live_only: bool = False
self._live_channel_keys: set[str] = set()
```

Phase 70 adds two sibling fields:
```python
# Phase 70 / F-02 / Pitfall 7 (mirrors Phase 68 _live_only):
self._hi_res_only: bool = False
self._hi_res_station_ids: set[int] = set()
```

**Map-setter + invalidate-guard pattern (Pitfall 7)** (copy verbatim shape from lines 57-79):
```python
def set_live_map(self, live_map: dict[str, str]) -> None:
    """Phase 68 / B-02: update the set of currently-live AA channel keys.

    Pitfall 7: invalidate ONLY when _live_only is active. Otherwise the
    proxy would re-run filterAcceptsRow for every row every 60 s even when
    the chip is off, causing visible tree-flicker.
    """
    self._live_channel_keys = set(live_map.keys()) if live_map else set()
    if self._live_only:
        self.invalidate()

def set_live_only(self, enabled: bool) -> None:
    """Phase 68 / F-02: toggle the live-only predicate.

    Always invalidates because the predicate state itself changed —
    unlike set_live_map, the user-visible result MUST update.
    """
    self._live_only = bool(enabled)
    self.invalidate()
```

Phase 70 (RESEARCH Pattern 5):
```python
def set_quality_map(self, quality_map: dict[int, str]) -> None:
    """Phase 70 / F-02: update station_ids whose best tier is "hires".

    Pitfall 7 mirror of Phase 68: invalidate ONLY when _hi_res_only=True."""
    self._hi_res_station_ids = {
        sid for sid, tier in (quality_map or {}).items() if tier == "hires"
    }
    if self._hi_res_only:
        self.invalidate()

def set_hi_res_only(self, enabled: bool) -> None:
    """Phase 70 / F-01: toggle the hi-res-only predicate (always invalidates)."""
    self._hi_res_only = bool(enabled)
    self.invalidate()
```

**`clear_all` extension pattern** (current lines 81-90):
```python
def clear_all(self) -> None:
    self._search_text = ""
    self._provider_set = set()
    self._tag_set = set()
    # Phase 68 / F-03 (clear_all extension): the "Live now" chip is one
    # of the predicate dimensions; clear_all wipes it too.
    self._live_only = False
    self.invalidate()
```

Phase 70 adds `self._hi_res_only = False` before the `invalidate()` call.

**`has_active_filter` extension pattern** (current lines 92-100):
```python
def has_active_filter(self) -> bool:
    return bool(
        self._search_text
        or self._provider_set
        or self._tag_set
        or self._live_only
    )
```

Phase 70 adds `or self._hi_res_only` to the OR chain.

**`filterAcceptsRow` extension pattern** (current lines 106-148):
```python
if node.kind == "station":
    # Phase 68 / F-02 / F-03: live-only short-circuit AND-composed with
    # other chip filters.
    if self._live_only:
        ...
        if ch_key is None or ch_key not in self._live_channel_keys:
            return False
    return matches_filter_multi(...)
```

Phase 70 inserts (BEFORE the existing `_live_only` branch, or after — both compose AND):
```python
if self._hi_res_only:
    station = node.station
    if int(station.id) not in self._hi_res_station_ids:
        return False
```

---

### `musicstreamer/ui_qt/edit_station_dialog.py` (modify — component)

**Analog:** self lines 208-213 (column constants) + 398-414 (table widget setup + delegate registration).

**Column-constant pattern** (current lines 208-213):
```python
# Stream table columns
_COL_URL = 0
_COL_QUALITY = 1
_COL_CODEC = 2
_COL_BITRATE = 3
_COL_POSITION = 4
```

Phase 70 appends (UI-SPEC §Component Inventory item 4 — keeps existing indices stable for snapshot tests):
```python
_COL_AUDIO_QUALITY = 5   # Phase 70 — read-only auto-detected tier
```

NOTE: UI-SPEC OD-8 names this `Audio quality` to disambiguate from the existing `_COL_QUALITY=1` (which stores `s.quality` user-authored string).

**Table widget setup pattern** (current lines 398-414):
```python
self.streams_table = QTableWidget(0, 5)
self.streams_table.setHorizontalHeaderLabels(
    ["URL", "Quality", "Codec", "Bitrate (kbps)", "Position"]
)
self.streams_table.setAlternatingRowColors(True)
self.streams_table.setSelectionBehavior(QTableWidget.SelectRows)
hdr = self.streams_table.horizontalHeader()
hdr.setSectionResizeMode(_COL_URL, QHeaderView.Stretch)
hdr.setSectionResizeMode(_COL_QUALITY, QHeaderView.Fixed)
hdr.setSectionResizeMode(_COL_CODEC, QHeaderView.Fixed)
hdr.setSectionResizeMode(_COL_BITRATE, QHeaderView.Fixed)
hdr.setSectionResizeMode(_COL_POSITION, QHeaderView.Fixed)
self.streams_table.setColumnWidth(_COL_QUALITY, 80)
self.streams_table.setColumnWidth(_COL_CODEC, 80)
self.streams_table.setColumnWidth(_COL_BITRATE, 95)
self.streams_table.setColumnWidth(_COL_POSITION, 60)
self.streams_table.setItemDelegateForColumn(_COL_BITRATE, _BitrateDelegate(self))
```

Phase 70 changes `QTableWidget(0, 5)` → `QTableWidget(0, 6)`, extends header labels with `"Audio quality"` (UI-SPEC OD-8), and adds:
```python
hdr.setSectionResizeMode(_COL_AUDIO_QUALITY, QHeaderView.Fixed)
self.streams_table.setColumnWidth(_COL_AUDIO_QUALITY, 90)  # UI-SPEC OD-8 sized to fit "Lossless"
self.streams_table.horizontalHeaderItem(_COL_AUDIO_QUALITY).setToolTip(
    "Auto-detected from playback. Hi-Res ≥ 48 kHz or ≥ 24-bit on a lossless codec."
)
```

**Read-only cell pattern** (planner can model on existing read-only Position column — search `_add_stream_row` for QTableWidgetItem construction):
```python
tier = classify_tier(stream.codec, stream.sample_rate_hz, stream.bit_depth)
item = QTableWidgetItem(TIER_LABEL_PROSE[tier])  # "Hi-Res" / "Lossless" / ""
item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # UI-SPEC OD-8 read-only
self.streams_table.setItem(row_idx, _COL_AUDIO_QUALITY, item)
```

---

### `musicstreamer/ui_qt/main_window.py` (modify — wiring)

**Analog:** self lines 346-351 (Phase 68 `live_map_changed` fan-out).

**Signal fan-out pattern** (current lines 346-351):
```python
# Phase 68 / B-02 fan-out: route poll-cycle live_map updates from
# NowPlayingPanel into StationListPanel's filter proxy (so the
# "Live now" chip's predicate stays fresh). Distinct slot rather
# than a direct connect to station_panel.update_live_map so the
# signal payload type is validated (must be dict).
self.now_playing.live_map_changed.connect(self._on_live_map_changed)
```

Phase 70 fan-out (RESEARCH Pitfall 9 Option A — MainWindow owns repo + the cross-component dispatch):
```python
# Phase 70 — wire Player.audio_caps_detected → MainWindow slot that
# (1) persists rate/depth via repo.update_stream (Phase 50 D-04: DB
# write FIRST), (2) rebuilds quality_map and fans out to
# now_playing._refresh_quality_badge + station_panel.update_quality_map
# (Phase 68 sibling fan-out shape).
self._player.audio_caps_detected.connect(self._on_audio_caps_detected)
```

Wire `_on_audio_caps_detected(stream_id, rate_hz, bit_depth)`:
1. `self._repo.update_stream(stream_id, ..., sample_rate_hz=rate_hz, bit_depth=bit_depth)` — DB FIRST (Pitfall 4).
2. Rebuild `quality_map = {st.id: best_tier_for_station(st) for st in repo.list_stations()}`.
3. `self.now_playing._refresh_quality_badge()` (or via a Signal — match Phase 68 pattern at `_refresh_live_status`).
4. `self.station_panel.update_quality_map(quality_map)` (which forwards to proxy + flips chip visibility).

---

## Test pattern assignments

### `tests/test_hi_res.py` (NEW)

**Analog:** `tests/test_stream_ordering.py` lines 20-39 — parametrize + truth-table assertions on pure helpers.

**Pattern:** `pytest.mark.parametrize` cycling through the four corners of the D-02 truth table:
```python
@pytest.mark.parametrize("codec,expected", [
    ("FLAC", 3), ("flac", 3), ("  FLAC  ", 3),
    ("AAC", 2), ("aac", 2),
    ("MP3", 1), ("mp3", 1),
    ("OPUS", 0), ("", 0), (None, 0),
])
def test_codec_rank(codec, expected):
    # PB-10: case-insensitive + whitespace-tolerant + None-safe
    assert codec_rank(codec) == expected
```

Phase 70 cases (per RESEARCH T-01 + UI-SPEC §Copywriting Contract):
- `("FLAC", 44100, 16)` → `"lossless"`
- `("FLAC", 96000, 24)` → `"hires"`
- `("FLAC", 48000, 24)` → `"hires"` (bit-depth-only trigger)
- `("FLAC", 96000, 16)` → `"hires"` (rate-only trigger)
- `("FLAC", 0, 0)` → `"lossless"` (D-03 default)
- `("ALAC", 0, 0)` → `"lossless"` (forward-compat)
- `("MP3", 0, 0)` → `""` (D-04)
- `("AAC", 96000, 24)` → `""` (D-04 — no hi-res for lossy)
- Case/None safety: `("flac", 44100, 16)`, `("", 0, 0)`, `(None, 0, 0)`

Also covers `bit_depth_from_format` for all GstAudioFormat strings in `_FORMAT_BIT_DEPTH` and `best_tier_for_station` across multi-stream stations.

---

### `tests/test_player_caps.py` (NEW)

**Analog:** `tests/test_player_tag.py` lines 28-75 — mocked GStreamer pipeline + `qtbot.waitSignal` for emission assertions.

**Player-fixture pattern** (copy from `test_player_tag.py:28-38`):
```python
def make_player(qtbot):
    """Create a Player with the GStreamer pipeline factory mocked out."""
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

**Fake-caps fixture pattern** (RESEARCH lines 812-823):
```python
def _fake_caps_pad(rate, format_str):
    """Build a fake pad whose get_current_caps() returns a structure with
    rate + format."""
    pad = MagicMock()
    structure = MagicMock()
    structure.get_int.return_value = (True, rate)
    structure.get_string.return_value = format_str
    caps = MagicMock()
    caps.get_size.return_value = 1
    caps.get_structure.return_value = structure
    pad.get_current_caps.return_value = caps
    return pad
```

**Signal-emission assertion pattern** (copy from `test_player_tag.py:69-75`):
```python
def test_on_gst_tag_emits_title_changed(qtbot):
    """A TAG message with a title causes title_changed.emit(title)."""
    player = make_player(qtbot)
    msg = _fake_tag_msg("Some Track")
    with qtbot.waitSignal(player.title_changed, timeout=1000) as blocker:
        player._on_gst_tag(bus=None, msg=msg)
    assert blocker.args == ["Some Track"]
```

Phase 70 T-06 test:
```python
def test_caps_persists_rate_and_bit_depth(qtbot):
    player = make_player(qtbot)
    pad = _fake_caps_pad(96000, "S24LE")
    player._caps_armed_for_stream_id = 42
    with qtbot.waitSignal(player.audio_caps_detected, timeout=1000) as blocker:
        player._on_caps_negotiated(pad, None)
    assert blocker.args == [42, 96000, 24]
```

---

### `tests/test_repo.py` (extend)

**Analog:** self lines 529-579 (Phase 47.2 `test_bitrate_kbps_hydrated_from_row` + `test_bitrate_kbps_migration_adds_column`).

**Hydration test pattern** (copy from lines 529-541):
```python
def test_bitrate_kbps_hydrated_from_row():
    """PB-01: list_streams hydrates bitrate_kbps from the row."""
    con = _make_bare_con()
    db_init(con)
    repo = Repo(con)
    con.execute("INSERT INTO stations(name) VALUES ('S')")
    station_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
    repo.insert_stream(station_id, "http://a", bitrate_kbps=320)
    repo.insert_stream(station_id, "http://b")  # legacy — no bitrate arg

    streams = repo.list_streams(station_id)
    bitrates = sorted(s.bitrate_kbps for s in streams)
    assert bitrates == [0, 320]
```

Phase 70 sibling tests:
- `test_sample_rate_hz_hydrated_from_row` — `repo.insert_stream(sid, "http://a", sample_rate_hz=96000)` + hydration check
- `test_bit_depth_hydrated_from_row` — analogous

**Idempotent-migration test pattern** (copy from lines 544-579):
```python
def test_bitrate_kbps_migration_adds_column():
    """PB-02: pre-47 DB (no bitrate_kbps column) gains the column on db_init."""
    con = _make_bare_con()
    # Simulate pre-47 schema — station_streams without bitrate_kbps
    con.executescript(<schema without bitrate_kbps>)
    con.commit()

    # Run db_init — additive ALTER TABLE must succeed without raising
    db_init(con)

    # Column now exists on old row with default 0
    row = con.execute(
        "SELECT bitrate_kbps FROM station_streams WHERE station_id=1"
    ).fetchone()
    assert row["bitrate_kbps"] == 0

    # Idempotency — second db_init must not raise
    db_init(con)
```

Phase 70 sibling: `test_sample_rate_hz_and_bit_depth_migration_adds_columns` — simulate pre-70 schema (with `bitrate_kbps` but without sample_rate_hz / bit_depth), assert columns appear with default 0 after `db_init`, and idempotency on second run.

---

### `tests/test_stream_ordering.py` (extend)

**Analog:** self lines 147-176 (`test_gbs_flac_ordering` regression).

**Tiebreak-test pattern** (copy shape from line 42-54 `test_quality_tier_beats_codec_rank`):
```python
def test_quality_tier_beats_codec_rank():
    # WR-01: hi-MP3-320 must beat med-AAC-128 (user's explicit quality choice
    # outranks codec-efficiency tiebreak).
    result = order_streams([
        _s("AAC", 128, 2, quality="med"),
        _s("MP3", 320, 1, quality="hi"),
    ])
    assert [(s.quality, s.codec, s.bitrate_kbps) for s in result] == [
        ("hi", "MP3", 320),
        ("med", "AAC", 128),
    ]
```

Phase 70 T-03 — `_s` helper extended with `sample_rate_hz`/`bit_depth` kwargs:
```python
def test_hires_flac_outranks_cd_flac():
    """Phase 70 / S-01: FLAC-96/24 sorts above FLAC-44/16 within the same codec."""
    result = order_streams([
        _s("FLAC", 1411, 2, sample_rate_hz=44100, bit_depth=16),
        _s("FLAC", 1411, 1, sample_rate_hz=96000, bit_depth=24),
    ])
    assert [(s.sample_rate_hz, s.bit_depth) for s in result] == [
        (96000, 24), (44100, 16),
    ]
```

Plus a regression check: `test_gbs_flac_ordering` at line 147-175 must still pass (no rate/depth set in GBS fixtures → 0/0 → sort behavior unchanged).

---

### `tests/test_settings_export.py` (extend)

**Analog:** self lines 626-720 (Phase 47.3 `test_export_import_roundtrip_preserves_bitrate_kbps` + `test_commit_import_forward_compat_missing_bitrate_key`).

**Round-trip-preservation pattern** (copy from lines 626-673):
```python
def test_export_import_roundtrip_preserves_bitrate_kbps(repo, tmp_path):
    # Seed station + stream via raw SQL with bitrate_kbps=320
    ...
    # Export
    build_zip(repo, str(zip_path))
    # Sanity check: bitrate_kbps appears in exported JSON
    ...
    # Import into a fresh repo, replace_all mode.
    fresh = _fresh_repo(fresh_dir)
    preview = preview_import(str(zip_path), fresh)
    commit_import(preview, fresh, mode="replace_all")
    row = fresh.con.execute(
        "SELECT bitrate_kbps FROM station_streams WHERE url = ?",
        ("http://bitrate-test.example/stream",),
    ).fetchone()
    assert row["bitrate_kbps"] == 320
```

Phase 70 sibling: `test_export_import_roundtrip_preserves_sample_rate_hz_and_bit_depth` — seed with `sample_rate_hz=96000, bit_depth=24`, assert both survive.

**Forward-compat-missing-key pattern** (copy from lines 676-720):
```python
def test_commit_import_forward_compat_missing_bitrate_key(tmp_path):
    """PB-15: pre-47 ZIP (stream dict without bitrate_kbps) imports cleanly with default 0."""
    payload = {
        "stations": [
            {
                ...
                "streams": [
                    # NO bitrate_kbps key — simulates a pre-47 export.
                    {"url": "http://legacy.example/stream", ...},
                ],
            }
        ],
    }
```

Phase 70 sibling: `test_commit_import_forward_compat_missing_quality_keys` — payload omits both `sample_rate_hz` and `bit_depth`, assert import succeeds with both columns defaulting to 0.

---

### `tests/test_station_filter_proxy.py` (extend)

**Analog:** self lines 215-271 (Phase 68 `set_live_only` + Pitfall 7 invalidate-guard).

**Filter-only test pattern** (copy from lines 215-222):
```python
def test_set_live_only_with_live_map_filters_stations(qtbot):
    """Phase 68 / F-02: set_live_only(True) shows only stations in live_map."""
    _, proxy = _make_proxy(_DI_STATIONS)
    proxy.set_live_map({"house": "Show A", "trance": "Show B"})
    proxy.set_live_only(True)
    visible = _visible_station_names(proxy)
    assert "Lounge" not in visible
    assert "House" in visible and "Trance" in visible
```

Phase 70 sibling: `test_set_hi_res_only_with_quality_map_filters_stations` — feed `{101: "hires", 102: "lossless", 103: ""}` + `set_hi_res_only(True)` → assert only station 101 visible.

**Pitfall 7 invalidate-guard test pattern** (copy from lines 258-270):
```python
def test_set_live_map_no_invalidate_when_chip_off(qtbot):
    """Phase 68 / Pitfall 7: set_live_map must NOT call invalidate when live_only=False."""
    _, proxy = _make_proxy(_DI_STATIONS)
    proxy.set_live_only(False)
    calls = []
    original = proxy.invalidate
    proxy.invalidate = lambda: calls.append(1) or original()  # type: ignore[method-assign]
    proxy.set_live_map({"house": "Test"})
    assert calls == []
    proxy.set_live_only(True)
    invalidate_count_after_set_only = len(calls)
    proxy.set_live_map({"trance": "Test2"})
    assert len(calls) > invalidate_count_after_set_only
```

Phase 70 sibling: `test_set_quality_map_no_invalidate_when_chip_off` — exact mirror with `set_hi_res_only` / `set_quality_map`.

Plus optional: AND-compose test with `_live_only` (similar to lines 235-247).

---

### `tests/test_station_star_delegate.py` (extend)

**Analog:** self (Phase 54 paint + sizeHint geometry tests at lines 36-60 already established).

The file exists and already covers paint-state mutation + sizeHint geometry assertions. Phase 70 T-05 extends with:
- `test_paints_hires_pill_for_hires_station` — station has at least one FLAC/96/24 stream → assert delegate calls `drawText` (or `drawRoundedRect`) with `"HI-RES"` payload (use `QPainter` mock or pixel-scan a known region).
- `test_paints_lossless_pill_for_cd_flac_station` — analogous for `"LOSSLESS"`.
- `test_no_pill_for_lossy_station` — MP3-only station → no pill paint call.
- `test_sizehint_grows_for_pill` — assert returned `QSize.width()` exceeds Phase 54 baseline by `pill_w + _PILL_TO_STAR_GAP`.

---

### `tests/test_now_playing_panel.py` (extend)

**Pattern:** mirror Phase 68 `_live_badge` visibility tests (search for `_live_badge` in the file). Phase 70 adds:
- `test_quality_badge_visible_for_hires_stream`
- `test_quality_badge_hidden_for_lossy_stream`
- `test_quality_badge_text_matches_tier`
- `test_picker_label_appends_tier_suffix`
- `test_picker_label_no_suffix_for_lossy_stream`

---

### `tests/test_station_list_panel.py` (extend)

**Pattern:** mirror Phase 68 `_live_chip` visibility tests. Phase 70 adds:
- `test_hi_res_chip_hidden_when_no_hi_res_streams` (F-02 initial state)
- `test_hi_res_chip_visible_after_update_quality_map_with_hires` (F-02 reactive flip)
- `test_set_hi_res_chip_visible_unchecks_when_hiding`

---

### `tests/test_edit_station_dialog.py` (extend)

**Pattern:** existing column-presence tests (model on `_COL_BITRATE` snapshot tests). Phase 70 adds:
- `test_audio_quality_column_present_and_read_only`
- `test_audio_quality_cell_shows_prose_label` (FLAC/96/24 → "Hi-Res"; FLAC/44/16 → "Lossless"; MP3 → "")
- `test_audio_quality_header_tooltip` (UI-SPEC OD-8 text)

---

## Shared Patterns

### Pattern S1: Phase 68 Badge QSS (verbatim)

**Source:** `musicstreamer/ui_qt/now_playing_panel.py:381-393` (Phase 68 LIVE badge).
**Apply to:** Phase 70 `_quality_badge` QLabel (now_playing_panel.py). Tree-row pill (station_star_delegate.py) uses `QPainter` primitives that produce the SAME visual via `option.palette.color(QPalette.Highlight)` / `QPalette.HighlightedText` + `drawRoundedRect(rect, 8, 8)` + bold font.

```python
self._XXX_badge.setStyleSheet(
    "QLabel {"
    " background-color: palette(highlight);"
    " color: palette(highlighted-text);"
    " border-radius: 8px;"
    " padding: 2px 6px;"
    " font-weight: bold;"
    "}"
)
self._XXX_badge.setTextFormat(Qt.PlainText)   # V5 ASVS plain-text invariant
```

**Why shared:** UI-SPEC §Color attests all 7 preset themes + Custom render the highlight/highlighted-text pair as a deliberately-contrasted accent pair. Reusing the pair on Phase 70 chrome gets theme guarantees for free.

### Pattern S2: Phase 68 Chip QSS (verbatim)

**Source:** `musicstreamer/ui_qt/station_list_panel.py:53-67` (`_CHIP_QSS`).
**Apply to:** Phase 70 `_hi_res_chip`.

```python
self._hi_res_chip.setCheckable(True)
self._hi_res_chip.setProperty("chipState", "unselected")
self._hi_res_chip.setStyleSheet(_CHIP_QSS)
self._hi_res_chip.toggled.connect(self._on_hi_res_chip_toggled)  # bound method, NOT lambda
```

### Pattern S3: Bus-Handler → Queued-Signal (Phase 43.1 Pitfall 2)

**Source:** `musicstreamer/player.py:381-401` (queued-connection wiring) + `674-707` (bus handlers emit only).
**Apply to:** Phase 70's new `_on_caps_negotiated` streaming-thread handler. The handler:
1. Reads caps off the pad (synchronous on streaming thread).
2. Calls `self.audio_caps_detected.emit(stream_id, rate, depth)`.
3. Returns immediately — does NOT touch Qt widgets, does NOT call `repo.update_stream`, does NOT mutate `self._pipeline.set_property(...)`.

The MAIN thread queued-connection slot (wired on MainWindow per Pitfall 9 Option A) is the only place repo writes + UI refresh happen.

**Why shared:** Phase 43.1 cross-OS 10s-Shoutcast-death regression. Documented in `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` Rule 2. Violating this is a BLOCKING bug, not a style issue.

### Pattern S4: Idempotent ALTER TABLE (Phase 47.2 — try/except OperationalError)

**Source:** `musicstreamer/repo.py:85-89`.
**Apply to:** Phase 70's two new `ALTER TABLE station_streams ADD COLUMN ...` statements for `sample_rate_hz` and `bit_depth`.

```python
try:
    con.execute("ALTER TABLE station_streams ADD COLUMN <col> INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists
```

**Why shared:** SQLite has no `ALTER TABLE ... IF NOT EXISTS`. Without the guard, second app launch crashes (Pitfall 5). No `PRAGMA user_version` bump — codebase has zero `user_version` references (RESEARCH verified).

### Pattern S5: Forward-Compat ZIP Idiom (Phase 47.3)

**Source:** `musicstreamer/settings_export.py:418, 474`.
**Apply to:** Phase 70's two new keys in `_insert_station` + `_replace_station`.

```python
int(stream.get("KEY", 0) or 0),  # Phase 70 forward-compat + defense
```

**Why shared:** Neutralizes missing key + None + empty string + malformed value in ONE expression. Old ZIPs without new keys default both columns to 0.

### Pattern S6: Phase 68 Pitfall 7 Invalidate-Guard

**Source:** `musicstreamer/ui_qt/station_filter_proxy.py:67-70` (`set_live_map`).
**Apply to:** Phase 70's `set_quality_map`.

```python
def set_quality_map(self, quality_map: dict[int, str]) -> None:
    self._hi_res_station_ids = {sid for sid, tier in (quality_map or {}).items() if tier == "hires"}
    if self._hi_res_only:                # <-- gate invalidate
        self.invalidate()
```

Always invalidate from `set_hi_res_only`; conditionally invalidate from `set_quality_map`.

**Why shared:** Without the guard, every caps event invalidates the proxy → visible tree-flicker even when the chip is off. Documented in Phase 68 Pitfall 7.

### Pattern S7: DB Write Precedes UI Refresh (Phase 50 D-04 / Pitfall 4)

**Source:** Phase 50 BUG-01 (`update_last_played` preceded `refresh_recent`).
**Apply to:** Phase 70's main-thread `_on_audio_caps_detected` slot (in MainWindow).

Strict ordering:
1. Compare payload `(rate, depth)` against in-memory cache (idempotency).
2. `repo.update_stream(stream_id, ..., sample_rate_hz=rate, bit_depth=depth)` — DB write FIRST.
3. Rebuild `quality_map` from `repo.list_stations()`.
4. Fan out to `now_playing._refresh_quality_badge()` + `station_panel.update_quality_map(quality_map)`.

**Why shared:** Violating order means the UI re-reads stale rate/depth (still 0). Badge takes two playback cycles to appear (RESEARCH Pitfall 4 warning sign).

### Pattern S8: `Qt.PlainText` Security Lock (V5 ASVS — Phase 68 enforcement)

**Source:** `musicstreamer/ui_qt/now_playing_panel.py:382` (`_live_badge.setTextFormat(Qt.PlainText)`).
**Apply to:** Phase 70 `_quality_badge` + stream-picker label concatenation (already plain text via `QComboBox.addItem`).

```python
self._quality_badge.setTextFormat(Qt.PlainText)
```

Tier strings come from a closed-enum `{"hires", "lossless", ""}` — injection from user-controlled fields is impossible. Defensive plain-text lock applied regardless.

**Note for planner:** UI-SPEC §Component Inventory item 1 mentions T-40-04 grep baseline (`setTextFormat|setHtml|RichText` count = 4); Phase 70 adds 1 → baseline becomes 5. Planner must bump the baseline assertion in whichever test owns it.

### Pattern S9: bound-method connection (no self-capturing lambda) — QA-05

**Source:** `musicstreamer/ui_qt/station_list_panel.py:298` (`self._live_chip.toggled.connect(self._on_live_chip_toggled)`).
**Apply to:** Phase 70 `self._hi_res_chip.toggled.connect(self._on_hi_res_chip_toggled)`.

Never `lambda checked: self._do_thing(checked)` — captures self and creates ownership/lifetime hazards. Always a bound method.

---

## No Analog Found

**None.** Every file in Phase 70's change set has at least a role-match analog in-tree, and 19/21 have an exact analog (in-file precedent or sibling-file template).

Phase 70 is, per RESEARCH §Summary, "mechanically a five-surface UI/feature phase grounded on one GStreamer plumbing decision" — the only genuinely novel piece is the GStreamer caps API entry point (`playbin.emit('get-audio-pad', 0)` + `notify::caps`). Everything else has a verbatim Phase 47.x / 68 template.

---

## Metadata

**Analog search scope:**
- `musicstreamer/` (all top-level modules)
- `musicstreamer/ui_qt/` (Qt widgets, delegates, models, proxies)
- `tests/` (test_player_*.py, test_repo.py, test_settings_export.py, test_station_*.py, test_stream_ordering.py)

**Files read (file:line ranges, no duplicates):**
- `.planning/phases/70-.../70-CONTEXT.md:1-248`
- `.planning/phases/70-.../70-RESEARCH.md:1-1003` (in three contiguous reads)
- `.planning/phases/70-.../70-UI-SPEC.md:1-407`
- `musicstreamer/models.py:1-47`
- `musicstreamer/repo.py:1-220`
- `musicstreamer/stream_ordering.py:1-64`
- `musicstreamer/eq_profile.py:1-81`
- `musicstreamer/player.py:260-410, 665-746`
- `musicstreamer/settings_export.py:100-130, 390-477`
- `musicstreamer/ui_qt/now_playing_panel.py:365-410, 1020-1064, 1420-1490`
- `musicstreamer/ui_qt/station_list_panel.py:45-130, 265-330, 540-600`
- `musicstreamer/ui_qt/station_filter_proxy.py:1-148`
- `musicstreamer/ui_qt/station_star_delegate.py:1-112`
- `musicstreamer/ui_qt/station_tree_model.py:1-173`
- `musicstreamer/ui_qt/edit_station_dialog.py:200-290, 390-440`
- `musicstreamer/ui_qt/main_window.py:340-369`
- `tests/test_player_tag.py:1-80`
- `tests/test_repo.py:515-595` (Phase 47.2 templates)
- `tests/test_settings_export.py:608-720` (Phase 47.3 templates)
- `tests/test_station_filter_proxy.py:200-275`
- `tests/test_station_star_delegate.py:1-60`
- `tests/test_stream_ordering.py:1-176`

**Pattern extraction date:** 2026-05-11
