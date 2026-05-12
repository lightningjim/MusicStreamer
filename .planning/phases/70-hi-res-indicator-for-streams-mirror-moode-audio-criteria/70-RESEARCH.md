# Phase 70: Hi-Res Indicator for Streams (mirror moOde audio criteria) — Research

**Researched:** 2026-05-11
**Domain:** GStreamer audio caps extraction + SQLite schema migration + Qt delegate painting + StationFilterProxyModel extension
**Confidence:** HIGH (architecture, surgical surfaces, threading invariants); MEDIUM (one GStreamer caps API call; researcher recommends notify::caps with one-shot fallback)

## Summary

Phase 70 is mechanically a five-surface UI/feature phase grounded on one GStreamer plumbing decision. CONTEXT.md locks 30+ decisions; only the GStreamer caps-extraction API surface and the exact SQL migration shape need researcher framing. Every other moving piece has a verbatim Phase 47.x / 68 template already in the codebase.

The schema migration mirrors Phase 47.2 `bitrate_kbps` at `repo.py:86` exactly — two extra columns (`sample_rate_hz`, `bit_depth`), both `INTEGER NOT NULL DEFAULT 0`, with idempotent `ALTER TABLE` in a try/except `sqlite3.OperationalError` block, no PRAGMA `user_version` bump (the codebase doesn't use them).

The runtime caps extraction recommendation is **`playbin.emit('get-audio-pad', 0)` + `notify::caps` signal** on the returned pad, with a **one-shot `get_current_caps()` poll** as a deterministic fallback at the moment we already filter `STATE_CHANGED → PLAYING` (player.py:709-734). The notify path captures the negotiated PCM as soon as it stabilizes; the fallback gives us a synchronous read on the same bus-thread we already use for the volume-reapply hook. Both paths run on the GStreamer bus-loop / streaming thread and MUST emit a queued Qt Signal to reach main (Phase 43.1 Pitfall — `qt-glib-bus-threading.md` Rule 2).

The two-tier classifier (`classify_tier(codec, sample_rate_hz, bit_depth) → "" | "lossless" | "hires"`) goes in a new `musicstreamer/hi_res.py` (mirrors `eq_profile.py`'s one-concept-per-file precedent). The tree-row delegate is best handled by **extending the existing `station_star_delegate.py`** rather than adding a sibling — the row geometry is already trained for non-square painting (Phase 54 BUG-05) and a single delegate avoids row-height churn.

**Primary recommendation:** Hook `pad = playbin.emit('get-audio-pad', 0)` once per `_set_uri` call. Connect `notify::caps` once on the player (re-used across pipeline rebuilds); the handler reads `pad.get_current_caps()`, parses rate + format, and emits a new class-level Signal `audio_caps_detected = Signal(int, int, int)` (stream_id, rate_hz, bit_depth) via `Qt.ConnectionType.QueuedConnection` — same architecture as `_cancel_timers_requested` / `_underrun_cycle_opened`. Idempotency-guard in main-thread slot via cached `(stream_id, rate, depth)`; persist only when value changes.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HRES-01 (proposed) | The app surfaces a two-tier audio-quality badge ("LOSSLESS" / "HI-RES") on the now-playing panel, station tree rows, stream picker, and EditStationDialog's streams table; runtime GStreamer caps detect the rate/depth, persist them per stream, and feed an "Hi-Res only" filter chip plus a rate/depth tiebreak in `stream_ordering.order_streams`. | Entire research doc; planner locks final wording. CONTEXT.md `<domain>` is the operative scope. |

**Planner action:** Insert `HRES-01` row in `.planning/REQUIREMENTS.md` `### Features (FEAT)` section, after `THEME-01` (line 43). Suggested text:

> **HRES-01**: User sees an automatic two-tier audio-quality badge ("LOSSLESS" / "HI-RES") next to each station's now-playing panel, station-tree row, stream-picker entry, and EditStationDialog row, plus a "Hi-Res only" filter chip and a hi-res-preferring tiebreak in stream failover ordering — all driven from negotiated GStreamer caps cached per stream after first replay, mirroring moOde Audio's Hi-Res convention.

`HRES-01` (or whatever final ID the planner picks — `HIRES-01` and `BADGE-01` are equally valid) becomes the traceability anchor under Phase 70.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Caps extraction (rate, format) | GStreamer (bus-loop/streaming thread) | — | Only place where negotiated PCM is observable. Cannot be done from main. |
| Bit-depth + tier classification (pure) | Pure-Python helper (`musicstreamer/hi_res.py`) | — | Mirrors `stream_ordering._CODEC_RANK` shape; importable by both player and UI tiers without cycles. |
| Persistence (rate/depth → DB) | Repo (Qt main thread) | — | Phase 50 D-04 / Pitfall 1: DB write must precede UI re-query. Same as Phase 47.2 `bitrate_kbps` writes. |
| Schema migration | Repo (`db_init`) | — | Idempotent ALTER TABLE in try/except — Phase 47.2 precedent (`repo.py:86`). |
| Settings-export round-trip | `settings_export._station_to_dict` / `_insert_station` / `_replace_station` | — | Phase 47.3 forward-compat idiom: `int(stream.get("KEY", 0) or 0)`. |
| Sort key tiebreak | Pure-Python helper (`stream_ordering.order_streams`) | `hi_res` | Two-line sort-key extension; depends on the persisted rate/depth columns. |
| Tree-row badge paint | `station_star_delegate.py` (combined delegate) | — | Phase 54 BUG-05 trained this delegate for multi-pixmap painting; single-delegate model avoids row-height churn. |
| Now-playing badge | `now_playing_panel.py` `_quality_badge` QLabel | — | Sibling of `_live_badge` (Phase 68) in `icy_row` — verbatim QSS template. |
| Stream picker badge | `now_playing_panel._populate_stream_picker` text formatter | — | One-line change to the existing `f"{s.quality} — {s.codec}"` template. |
| Filter chip | `station_list_panel._hi_res_chip` + `StationFilterProxyModel.set_quality_map` / `set_hi_res_only` | — | Verbatim mirror of Phase 68 `_live_chip` / `set_live_map` / `set_live_only`. Pitfall 7 invalidate-guard applies. |
| EditStationDialog "Quality" column | `edit_station_dialog._add_stream_row` | — | New `_COL_QUALITY_TIER` column (read-only) constructed alongside `_COL_BITRATE`. |
| Threading boundary (caps→main) | New queued `Signal` on Player | — | Phase 43.1 Pitfall 2 — bus-loop thread has no Qt event loop. |

## Project Constraints (from CLAUDE.md)

- **Routing:** Windows packaging, GStreamer+PyInstaller, conda-forge, PowerShell topics → `Skill("spike-findings-musicstreamer")`. Phase 70 touches GStreamer (caps API on the audio pad). The new caps handler MUST honor Phase 43.1 invariants documented in `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md`:
  - **Rule 1 — `bus.add_signal_watch()` thread-context lock.** Already handled by `Player.__init__` via `_bridge.run_sync(...)`. Phase 70 does NOT add a new `add_signal_watch` call site, so Rule 1 is not in scope. **`pad.connect("notify::caps", ...)`** is a GObject signal connection, NOT a bus-watch attach — but the handler still runs on the streaming/bus-loop thread.
  - **Rule 2 — no bare `QTimer.singleShot` from non-Qt threads.** The new caps handler runs on a non-`QThread` (GStreamer streaming thread for `notify::caps`; bus-loop thread for the fallback path). It MUST cross to main via a queued `Signal.emit()`, never via `QTimer.singleShot` and never by writing to `self._pipeline` from the handler.

`Skill("spike-findings-musicstreamer")` should be auto-loaded for planning the player-side caps work.

## User Constraints (from CONTEXT.md)

### Locked Decisions

(Verbatim from CONTEXT.md `<decisions>`. These are inputs to planning, not researcher questions.)

**Criteria:**
- **D-01:** Two tiers only — `Lossless` and `Hi-Res`. No DSD tier.
- **D-02:** `Lossless` = `codec ∈ {FLAC, ALAC}` AND `sample_rate_hz ≤ 48000` AND `bit_depth ≤ 16`. `Hi-Res` = `codec ∈ {FLAC, ALAC}` AND (`sample_rate_hz > 48000` OR `bit_depth > 16`). Lossy codecs: no badge.
- **D-03:** FLAC + unknown rate/depth defaults to `Lossless`.
- **D-04:** No badge for lossy streams.
- **D-05:** Labels `LOSSLESS` and `HI-RES` (all-caps, Phase 68 typography).

**Source of truth:**
- **DS-01:** Runtime GStreamer caps + persistent per-stream cache. Write-once per playback on first caps after PLAYING.
- **DS-02:** Bit-depth mapping from GstAudioFormat string (S16* → 16; S24*/S24_32* → 24; S32*/F32* → 32; else 0).
- **DS-03:** Don't auto-correct codec. Only rate/depth flow back.
- **DS-04:** Settings ZIP round-trip carries the cache via forward-compat idiom.
- **DS-05:** No automatic backfill.

**Display surfaces:** DP-01..DP-07 lock all four surfaces, best-tier-across-streams for tree rows, immediate-left-of-LIVE placement, picker text format `f"{label} — {tier_text}"`, EditStationDialog Quality column read-only, Phase 68 LIVE QSS verbatim.

**Filter & sort:** F-01..F-03 lock one "Hi-Res only" chip with visibility gate. S-01 extends sort key to `(-quality_rank, -codec_rank, -bitrate_kbps, -sample_rate_hz, -bit_depth, position)`. S-02 forbids cross-codec hi-res promotion.

**Test discipline:** T-01..T-06 lock six test families.

**Migration:** M-01 mirrors Phase 47.2 idempotent ALTER TABLE. M-02 no backfill. M-03 no `bitrate_kbps=1411` repurposing.

### Claude's Discretion

- GStreamer caps API entry point (this RESEARCH.md recommends one path + fallback; planner locks).
- Module location for `classify_tier` (this RESEARCH.md recommends new `musicstreamer/hi_res.py`).
- Column names — defaults `sample_rate_hz`, `bit_depth` (mirroring `bitrate_kbps`). Researcher endorses these.
- Tree-delegate strategy: extend `station_star_delegate.py` vs. add sibling (this RESEARCH.md recommends extend).
- `set_quality_map` shape — flat `dict[int, str]` of station_best_tier (parallels Phase 68 `set_live_map`).
- Now-playing badge tooltip — yes (small QA win, free if rate/depth carried on `currently_playing`).
- EditStationDialog Quality column position — last column to keep snapshot indices stable.

### Deferred Ideas (OUT OF SCOPE)

- Manual "This is Hi-Res" override checkbox.
- DSD tier.
- Numeric rate/depth on tree row.
- Bitrate-derived hi-res inference (GBS.FM 1411 sentinel stays a codec-rank hint).
- Backfill migration (cache fills organically).
- Cross-codec hi-res promotion.
- `Lossless+` filter chip.
- `Gst.Registry` audit (Phase 69's domain).
- Codec auto-correction.
- HE-AAC "HD" mid-tier.

## Standard Stack

### Core (already in-project — Phase 70 adds nothing to dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GStreamer | 1.28.2 pinned (Windows conda-forge; Linux distro) | Audio playback + negotiated caps via `playbin3` | `[VERIFIED: codebase pyproject.toml + PROJECT.md Key Decisions]` Existing playbin3 already negotiates caps; we only add a read of the audio pad's `current-caps`. |
| PyGObject (gi.repository.Gst) | matches GStreamer | Python bindings for caps query + signal connect | `[VERIFIED: codebase player.py imports]` |
| PySide6 | `>=6.10` | QObject + Signal + QStyledItemDelegate | `[VERIFIED: pyproject.toml]` |
| sqlite3 (stdlib) | — | Idempotent ALTER TABLE pattern | `[VERIFIED: codebase repo.py:67-89]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `musicstreamer.gst_bus_bridge.GstBusLoopThread` | — | Already wires bus signals on a bridge thread | Phase 70 does NOT add a new `add_signal_watch` call site, so the bridge stays untouched. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `playbin.emit('get-audio-pad', 0)` + `notify::caps` | `playbin.emit('get-audio-tags', 0)` returning `Gst.TagList` | TagList carries `Gst.TAG_AUDIO_CODEC` (codec mime) and `Gst.TAG_BITRATE` (bitrate); it does **not reliably expose negotiated PCM rate or bit-depth** for HTTP audio streams. Caps query on the audio pad is the only reliable path. `[CITED: GStreamer Python tutorial + gstreamer-devel mailing list]` |
| Audio-sink pad caps | Probe `decodebin3` element caps | playbin3 hides decodebin3 internals; pad-level probing is fragile and version-dependent. `get-audio-pad` is the public playbin3 API. `[ASSUMED]` |
| `bus.add_signal_watch` + new `message::tag` consumer | (existing path) | We already consume `message::tag` for ICY title at `player.py:674`. Adding bit-depth detection there would tangle ICY metadata with caps detection. `notify::caps` on the pad is cleaner separation. |

**Installation:** No new dependencies. Phase 70 reuses the existing GStreamer + PySide6 + sqlite3 stack.

**Version verification:** Not applicable — no new packages. Existing GStreamer pin (1.28.2) was verified in Phase 43.1.

## Architecture Patterns

### System Architecture Diagram

```
                              ┌──────────────────────────┐
   GStreamer playbin3  ──────►│  audio pad (playbin)     │
   (streaming thread)         │  notify::caps signal     │
                              └────────────┬─────────────┘
                                           │  (streaming/bus-loop thread)
                                           │  emits audio_caps_detected
                                           ▼  (Signal, Qt.QueuedConnection)
                              ┌──────────────────────────┐
                              │  Player main-thread slot │
                              │  _on_audio_caps_detected │
                              │  - dedupe cached value   │
                              │  - repo.update_stream    │
                              │  - emit quality_changed  │
                              └────────────┬─────────────┘
                                           │
                ┌──────────────────────────┼──────────────────────────┐
                ▼                          ▼                          ▼
   ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
   │ NowPlayingPanel      │   │ StationListPanel     │   │ EditStationDialog    │
   │ _refresh_quality_    │   │ proxy.set_quality_   │   │ refresh Quality col  │
   │ badge                │   │ map (Pitfall 7 grd)  │   │ if dialog is open    │
   └──────────────────────┘   └──────────┬───────────┘   └──────────────────────┘
                                         │
                                         ▼
                              ┌──────────────────────┐
                              │ StationFilterProxy   │
                              │ filterAcceptsRow:    │
                              │  if _hi_res_only and │
                              │  station not in hi-  │
                              │  res set → reject    │
                              └──────────────────────┘

Pure helpers (no UI / no I/O):
  ┌──────────────────────────────────────────┐
  │ musicstreamer/hi_res.py (NEW)            │
  │   classify_tier(codec,rate,depth)→str    │
  │   best_tier_for_station(station)→str     │
  │   bit_depth_from_format(format_str)→int  │
  └──────────────────────────────────────────┘
            │
            ├──► stream_ordering.order_streams (sort tiebreak)
            └──► NowPlayingPanel._refresh_quality_badge
                 station_star_delegate.paint (tree row)
                 station_filter_proxy.set_quality_map (chip)
```

### Recommended Project Structure

```
musicstreamer/
├── hi_res.py                       # NEW — pure tier classifier (mirrors eq_profile.py)
├── models.py                       # +2 fields on StationStream
├── repo.py                         # +2 columns CREATE TABLE body, +2 ALTER TABLE, +2 kwargs on insert/update_stream
├── stream_ordering.py              # extend order_streams sort key
├── settings_export.py              # +2 forward-compat lines in _insert_station / _replace_station + 2 keys in _station_to_dict
├── player.py                       # add audio_caps_detected Signal + notify::caps connect + main-thread slot
└── ui_qt/
    ├── now_playing_panel.py        # _quality_badge QLabel in icy_row + _refresh_quality_badge slot + picker formatter
    ├── station_list_panel.py       # _hi_res_chip parallel to _live_chip
    ├── station_filter_proxy.py     # set_quality_map / set_hi_res_only / filterAcceptsRow hi-res branch
    ├── station_star_delegate.py    # extend paint() + sizeHint() to render tier pill before star
    ├── station_tree_model.py       # +1 Qt.UserRole role for best_tier (Qt.UserRole + N) — optional, planner discretion
    └── edit_station_dialog.py      # new _COL_QUALITY_TIER column (read-only)

tests/
├── test_hi_res.py                  # NEW — classify_tier + bit_depth_from_format + best_tier_for_station
├── test_repo.py                    # +sample_rate_hz / bit_depth round-trip
├── test_stream_ordering.py         # +rate/depth tiebreak (T-03)
├── test_settings_export.py         # +forward-compat sibling assertion (T-04)
├── test_station_star_delegate.py   # NEW or extend — best-tier-across-streams paint test (T-05)
└── test_player_caps.py             # NEW — mocked notify::caps signal → repo.update_stream (T-06)
```

### Pattern 1: Caps Extraction (Recommended Path — `notify::caps` on audio pad)

**What:** On every new `_set_uri` call, fetch the audio pad via `playbin.emit('get-audio-pad', 0)`, connect a one-shot `notify::caps` handler that reads the negotiated caps and emits a queued Signal carrying `(stream_id, rate_hz, bit_depth)` to the main thread.

**When to use:** Phase 70's only required usage — first negotiated caps after `STATE_CHANGED → PLAYING`.

**Example:**

```python
# Source: synthesized from gstreamer-devel narkive thread (Mar 2015) + lazka.github.io
# Verified pattern via: pad = playbin.emit('get-audio-pad', 0); caps = pad.get_current_caps()
# Source thread: https://gstreamer-devel.narkive.com/JEGHHXNp/getting-sample-rate-sample-format-channels-cound-of-playbin-in-python

class Player(QObject):
    # ... existing Signals ...
    audio_caps_detected = Signal(int, int, int)   # stream_id, rate_hz, bit_depth (queued → main)

    def __init__(self, parent=None):
        super().__init__(parent)
        # ... existing __init__ body ...
        # Phase 70 — main-thread slot for caps-detected payloads.
        self.audio_caps_detected.connect(
            self._on_audio_caps_detected, Qt.ConnectionType.QueuedConnection
        )
        self._caps_pad = None                 # cached audio-pad ref so we can disconnect
        self._caps_handler_id = 0
        self._caps_armed_for_stream_id = 0    # per-URL one-shot guard

    def _set_uri(self, uri: str) -> None:
        # (existing body)
        uri = aa_normalize_stream_url(uri)
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
        self._pipeline.set_property("uri", uri)
        self._pipeline.set_state(Gst.State.PLAYING)
        # Phase 70 — install a fresh caps watch on the NEW pipeline lifecycle.
        # MUST happen AFTER set_state(PLAYING) so playbin3 starts negotiating
        # streams; AFTER state_changed → PLAYING fires, get_current_caps()
        # returns the negotiated caps (narkive thread + GStreamer docs).
        self._arm_caps_watch_for_current_stream()

    def _arm_caps_watch_for_current_stream(self) -> None:
        # Disconnect prior watch (per-URL one-shot).
        if self._caps_pad is not None and self._caps_handler_id:
            try:
                self._caps_pad.disconnect(self._caps_handler_id)
            except (TypeError, Exception):
                pass
        self._caps_pad = None
        self._caps_handler_id = 0
        if self._current_stream is None:
            return
        self._caps_armed_for_stream_id = self._current_stream.id

        # Defer until PLAYING — but the simplest robust approach is to
        # arm in _on_playbin_state_changed (the existing PLAYING-only slot
        # at player.py:736). See Pattern 1b below.
        pad = self._pipeline.emit("get-audio-pad", 0)
        if pad is None:
            return
        self._caps_pad = pad
        self._caps_handler_id = pad.connect("notify::caps", self._on_caps_negotiated)
        # Also do a synchronous one-shot read in case caps are already set.
        self._on_caps_negotiated(pad, None)

    def _on_caps_negotiated(self, pad, _pspec) -> None:
        """Streaming-thread handler — MUST emit a queued Signal, never touch
        Qt widgets or self._pipeline directly (Phase 43.1 Pitfall 2)."""
        if not self._caps_armed_for_stream_id:
            return
        caps = pad.get_current_caps()
        if caps is None or caps.get_size() == 0:
            return
        s = caps.get_structure(0)
        # Format extraction — GstStructure supports .get_string / .get_int with
        # tuple-return (found, value). Defensive: any None / missing field → 0.
        rate_ok, rate = s.get_int("rate") if hasattr(s, "get_int") else (False, 0)
        if not rate_ok:
            try:
                rate = int(s["rate"])
            except (KeyError, TypeError, ValueError):
                rate = 0
        try:
            fmt = s.get_string("format") or s["format"]
        except (KeyError, TypeError):
            fmt = ""
        from musicstreamer.hi_res import bit_depth_from_format
        depth = bit_depth_from_format(fmt or "")
        if rate <= 0 or depth <= 0:
            return  # nothing useful yet
        # Disarm so we only persist once per URL.
        sid = self._caps_armed_for_stream_id
        self._caps_armed_for_stream_id = 0
        self.audio_caps_detected.emit(sid, rate, depth)  # queued → main
```

**Pattern 1b — fallback / belt-and-suspenders:** the existing `_on_playbin_state_changed` slot at `player.py:736` already runs on the **main thread** after a queued Signal carrying the PLAYING transition. Within that slot, call `pad = self._pipeline.emit('get-audio-pad', 0); caps = pad.get_current_caps()` synchronously. If `caps` is non-None, persist immediately. If `None`, install the `notify::caps` handler as a deferred read. This pattern gives us:
- A main-thread synchronous read for streams where caps are already set at PLAYING (most common case once a connection is established);
- An async `notify::caps` handler for streams where caps stabilize after PLAYING (HLS, some Icecast servers that re-negotiate).

**Recommendation to planner:** ship Pattern 1b. The main-thread `get_current_caps()` call inside `_on_playbin_state_changed` is the "if known, persist now" path; the streaming-thread `notify::caps` is the "if not known yet, persist when negotiated" path. Both end up calling `repo.update_stream(stream_id, sample_rate_hz=rate, bit_depth=depth)` via the queued `audio_caps_detected` Signal.

### Pattern 2: Idempotent ALTER TABLE Migration (Verbatim Phase 47.2)

**What:** Two CREATE TABLE body additions + two idempotent ALTER TABLE blocks in `db_init`.

**Example (literal SQL, copy-pasteable):**

```python
# In repo.py db_init, inside executescript CREATE TABLE station_streams (line 51-62):
#   ADD AFTER line 60 (bitrate_kbps line):
#     sample_rate_hz INTEGER NOT NULL DEFAULT 0,
#     bit_depth INTEGER NOT NULL DEFAULT 0,

# After line 89 (the bitrate_kbps ALTER block):
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

No PRAGMA `user_version` bump. `[VERIFIED: repo.py:67-89 — the codebase has zero `PRAGMA user_version` references and uses the try/except OperationalError idiom for all four prior migrations.]`

### Pattern 3: Bit-Depth Mapping (Pure Helper)

```python
# musicstreamer/hi_res.py

"""Hi-Res audio classification helpers (Phase 70).

Pure functions — no GStreamer imports, no I/O, no Qt.
Mirrors stream_ordering.py shape (small enum-mapped helpers).
"""
from __future__ import annotations

# DS-02 verbatim mapping (caps validated against GstAudioFormat enum,
# https://lazka.github.io/pgi-docs/GstAudio-1.0/enums.html):
#   - S8 / U8 → 8 (excluded from hi-res classification entirely)
#   - S16LE/S16BE/U16LE/U16BE → 16
#   - S24LE/S24BE/U24LE/U24BE/S24_32LE/S24_32BE/U24_32LE/U24_32BE → 24
#   - S32LE/S32BE/U32LE/U32BE → 32
#   - F32LE/F32BE → 32 (treat IEEE 754 32-bit float as 32-bit-equivalent for hi-res)
#   - F64LE/F64BE → 32 (treat IEEE 754 64-bit float as 32-bit-equivalent; DS-02 ceiling)
#   - Anything else → 0 (unknown)
_FORMAT_BIT_DEPTH = {
    "S8": 0, "U8": 0,                                    # below 16-bit: not classified
    "S16LE": 16, "S16BE": 16, "U16LE": 16, "U16BE": 16,
    "S24LE": 24, "S24BE": 24, "U24LE": 24, "U24BE": 24,
    "S24_32LE": 24, "S24_32BE": 24, "U24_32LE": 24, "U24_32BE": 24,
    "S32LE": 32, "S32BE": 32, "U32LE": 32, "U32BE": 32,
    "F32LE": 32, "F32BE": 32,
    "F64LE": 32, "F64BE": 32,   # planner finalizes — DS-02 caps at 32
}

# Hi-res criteria (D-02, mirrors moOde + JAS).
_HIRES_RATE_THRESHOLD_HZ = 48_000
_HIRES_BIT_DEPTH_THRESHOLD = 16
_LOSSLESS_CODECS = {"FLAC", "ALAC"}


def bit_depth_from_format(format_str: str) -> int:
    """Return bit-depth for a GstAudioFormat string. Unknown → 0.

    Case-sensitive (GStreamer's format strings are canonical upper-case
    short-codes, not free-form text); None/empty → 0.
    """
    return _FORMAT_BIT_DEPTH.get((format_str or ""), 0)


def classify_tier(codec: str, sample_rate_hz: int, bit_depth: int) -> str:
    """Return "hires" | "lossless" | "" per CONTEXT D-02 / D-03 / D-04.

    Lossy codecs always return "" (D-04).
    Lossless codec + (rate>48kHz OR depth>16) → "hires" (D-02).
    Lossless codec + everything else → "lossless" (D-02 + D-03 fallback).
    """
    c = (codec or "").strip().upper()
    if c not in _LOSSLESS_CODECS:
        return ""
    rate = int(sample_rate_hz or 0)
    depth = int(bit_depth or 0)
    if rate > _HIRES_RATE_THRESHOLD_HZ or depth > _HIRES_BIT_DEPTH_THRESHOLD:
        return "hires"
    return "lossless"


def best_tier_for_station(station) -> str:
    """Return the best tier across a station's streams (D-02 DP-02).

    Hi-Res > Lossless > "" (no tier). Pure: reads station.streams attribute,
    no DB calls. Safe with empty / None streams list.
    """
    tiers = {
        classify_tier(s.codec, s.sample_rate_hz, s.bit_depth)
        for s in (station.streams or [])
    }
    if "hires" in tiers:
        return "hires"
    if "lossless" in tiers:
        return "lossless"
    return ""
```

### Pattern 4: Forward-Compat Settings ZIP Idiom (Phase 47.3 verbatim)

```python
# In settings_export._station_to_dict (line 118-127), add two keys:
"streams": [
    {
        "url": s.url,
        "label": s.label,
        "quality": s.quality,
        "position": s.position,
        "stream_type": s.stream_type,
        "codec": s.codec,
        "bitrate_kbps": s.bitrate_kbps,
        "sample_rate_hz": s.sample_rate_hz,   # Phase 70
        "bit_depth": s.bit_depth,             # Phase 70
    }
    for s in station.streams
],

# In settings_export._insert_station (line 408-420) and _replace_station (line 461-477):
# Extend the INSERT SQL column list + value tuple by two columns. Pattern is
# identical between both functions.
repo.con.execute(
    "INSERT INTO station_streams"
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
)
```

Old ZIPs without the new keys → both default to 0 (cache rebuilds on first replay).

### Pattern 5: StationFilterProxyModel `set_quality_map` / `set_hi_res_only`

```python
# musicstreamer/ui_qt/station_filter_proxy.py — verbatim mirror of Phase 68

class StationFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # ... existing __init__ body ...
        # Phase 70 / F-02 / Pitfall 7 (parallels Phase 68 _live_only):
        self._hi_res_only: bool = False
        self._hi_res_station_ids: set[int] = set()

    def set_quality_map(self, quality_map: dict[int, str]) -> None:
        """Phase 70 / F-02: update the set of station_ids whose best tier is "hires".

        quality_map is dict[station_id, "hires"|"lossless"|""].
        Pitfall 7 (Phase 68): invalidate ONLY when _hi_res_only is active.
        Otherwise the proxy would re-run filterAcceptsRow every cache-update,
        causing visible tree-flicker.
        """
        self._hi_res_station_ids = {
            sid for sid, tier in (quality_map or {}).items() if tier == "hires"
        }
        if self._hi_res_only:
            self.invalidate()

    def set_hi_res_only(self, enabled: bool) -> None:
        """Phase 70 / F-01: toggle the hi-res-only predicate.

        Always invalidates — the user-visible filter set MUST update."""
        self._hi_res_only = bool(enabled)
        self.invalidate()

    def clear_all(self) -> None:
        # ... existing body ...
        self._hi_res_only = False
        self.invalidate()

    def has_active_filter(self) -> bool:
        return bool(
            self._search_text or self._provider_set or self._tag_set
            or self._live_only or self._hi_res_only
        )

    def filterAcceptsRow(self, source_row, source_parent):
        # ... existing provider-row branch ...
        if node.kind == "station":
            # Phase 70 / F-02: hi-res-only short-circuit AND-composed with
            # other chip filters. Read station.id, check membership.
            if self._hi_res_only:
                station = node.station
                if int(station.id) not in self._hi_res_station_ids:
                    return False
            # ... existing live_only branch + matches_filter_multi ...
```

### Pattern 6: Tree Delegate — Extend `station_star_delegate.py`

```python
# musicstreamer/ui_qt/station_star_delegate.py — pseudocode delta

# Module-level constants:
_PILL_HEIGHT = 18
_PILL_PADDING_X = 6
_PILL_MARGIN_X = 6
_PILL_FONT_POINT = 8

def _pill_rect(row_rect: QRect, pill_width: int) -> QRect:
    """Right-aligned pill before the star (star is at right_edge - _STAR_SIZE - _STAR_MARGIN).
    Pill anchors to LEFT of the star with _PILL_MARGIN_X gap."""
    star_left = row_rect.right() - _STAR_SIZE - _STAR_MARGIN
    pill_right = star_left - _PILL_MARGIN_X
    pill_left = pill_right - pill_width
    y = row_rect.top() + (row_rect.height() - _PILL_HEIGHT) // 2
    return QRect(pill_left, y, pill_width, _PILL_HEIGHT)

class StationStarDelegate(QStyledItemDelegate):
    # ... existing fields ...

    def paint(self, painter, option, index) -> None:
        # ... existing portrait-fix body ...
        super().paint(painter, option, index)
        if not isinstance(station, Station):
            return
        # Phase 70 — paint quality pill BEFORE the star, in the same column.
        from musicstreamer.hi_res import best_tier_for_station
        tier = best_tier_for_station(station)
        if tier:
            label = "HI-RES" if tier == "hires" else "LOSSLESS"
            fm = painter.fontMetrics()   # delegate's own font
            f = QFont(painter.font())
            f.setPointSize(_PILL_FONT_POINT)
            f.setBold(True)
            painter.save()
            painter.setFont(f)
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(label)
            pill_w = text_w + 2 * _PILL_PADDING_X
            r = _pill_rect(option.rect, pill_w)
            path = QPainterPath()
            path.addRoundedRect(r, 8, 8)
            # palette tokens match Phase 68 LIVE QSS (palette(highlight) bg,
            # palette(highlighted-text) fg). For painter draw use option.palette
            # to honor theme — same single-token semantics as the LIVE label.
            painter.fillPath(path, option.palette.highlight())
            painter.setPen(option.palette.highlightedText().color())
            painter.drawText(r, Qt.AlignCenter, label)
            painter.restore()

        is_fav = self._repo.is_favorite_station(station.id)
        # ... existing star paint ...

    def sizeHint(self, option, index) -> QSize:
        base = super().sizeHint(option, index)
        if isinstance(index.data(Qt.UserRole), Station):
            # Floor row height + reserve width for star + pill.
            # Worst-case pill is "LOSSLESS" — ~70px at 8pt bold.
            extra = _STAR_SIZE + _STAR_MARGIN + 80 + _PILL_MARGIN_X
            h = max(base.height(), STATION_ICON_SIZE)
            return QSize(base.width() + extra, h)
        # ... existing provider branch ...
```

### Anti-Patterns to Avoid

- **Caps read on main thread before PLAYING:** `pad.get_current_caps()` returns `None` until streams are negotiated. Always check for `None` and rely on the queued `audio_caps_detected` Signal for late-arriving caps.
- **Connecting `notify::caps` on the pipeline (vs. on the pad):** the signal lives on the audio sink pad, not on playbin3 itself.
- **`QTimer.singleShot(0, fn)` from the caps handler:** Phase 43.1 Pitfall 2 — the streaming/bus-loop thread has no Qt event loop. The callable vanishes silently.
- **Mutating `self._pipeline.set_property(...)` from the streaming-thread caps handler:** all property writes go through the main-thread queued Signal slot.
- **Trying to derive bit-depth from `Gst.TAG_BITRATE`:** TAG_BITRATE is the encoded-stream bitrate (e.g., 320000 for 320 kbps MP3), not the PCM bit-depth. They are different domains.
- **Auto-correcting codec from caps:** CONTEXT DS-03 explicit rejection — only persist rate/depth.
- **Re-invalidating the proxy on every set_quality_map call when chip is off:** Pitfall 7 (Phase 68) — invalidate only when `_hi_res_only=True`.
- **Hand-rolling a rounded-rect pill via setStyleSheet on a delegate:** delegates paint directly; use `QPainterPath.addRoundedRect` + `painter.fillPath`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Audio format → bit-depth mapping | Custom string parser, regex | Hardcoded dict keyed on GstAudioFormat short names | GstAudioFormat strings are a finite, canonical enum (`[VERIFIED: lazka.github.io/pgi-docs/GstAudio-1.0/enums.html]`); a dict lookup is the entire correct implementation. |
| Caps polling loop on a QTimer | Wake every 500ms to `get_current_caps()` | `notify::caps` signal on the pad | GStreamer fires it when caps stabilize; polling wastes CPU and races with the streaming thread. |
| Best-tier-across-streams computation in the delegate | Loop in `paint()` over `station.streams` each frame | Helper `best_tier_for_station(station)` called once per paint; or expose via a `Qt.UserRole + N` cached on the model | The data is stable until DB write; pre-compute or expose via UserRole and read in delegate. Planner's discretion — both work. |
| String comparison for tier classification in three+ surfaces | `if tier == "hires": ...` in five files | Two module-level constants `TIER_HIRES = "hires"` / `TIER_LOSSLESS = "lossless"` in `hi_res.py` | Single source of truth; one rename if the spelling ever changes. |
| ZIP forward-compat tolerance | `try: stream["sample_rate_hz"] except KeyError: ...` | `int(stream.get("sample_rate_hz", 0) or 0)` | Phase 47.3 idiom; neutralizes missing key + None + empty string + malformed value in one expression. |
| Threading across the caps → main boundary | `QTimer.singleShot(0, ...)` or raw `threading.Lock` | Queued `Signal` with `Qt.ConnectionType.QueuedConnection` | Phase 43.1 Pitfall 2 — bare singleShot from non-QThread silently drops. |

**Key insight:** Phase 70 is a "join existing trails" phase. The only novel piece is the GStreamer caps API entry point. Everything else has a verbatim Phase 47.x / 68 template.

## Runtime State Inventory

Phase 70 is a **feature-add phase** (new columns, new module, new badge, new chip). It is NOT a rename/refactor/migration phase in the sense Step 2.5 targets. The Runtime State Inventory checklist asks "what runtime systems still have the OLD string cached?" — Phase 70 doesn't rename anything.

**Explicit none-found inventory for completeness (so the planner doesn't need to recheck):**

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no rename. New DB columns (sample_rate_hz, bit_depth) start at default 0 per DS-05 (no backfill). Existing rows are not edited by Phase 70. | None |
| Live service config | None — Phase 70 makes zero changes to external services (n8n, Datadog, Tailscale, Cloudflare, etc.). | None |
| OS-registered state | None — no changes to launchd plists, systemd unit names, Windows Task Scheduler tasks, pm2 saved process names. | None |
| Secrets/env vars | None — no env var or secret name changes; no new env vars consumed. | None |
| Build artifacts | None for fresh builds. **Note:** existing dev installations will see the new columns added via `db_init` idempotent ALTER TABLE on next app launch (M-01). The columns default to 0; no .egg-info / .whl artifact churn. | None |

## Common Pitfalls

### Pitfall 1: `pad.get_current_caps()` returns `None` until streams negotiate (BLOCKING)

**What goes wrong:** Calling `pad.get_current_caps()` immediately after `pipeline.set_state(PLAYING)` returns `None` because the pipeline hasn't connected to the source yet. If Phase 70 reads caps in `_set_uri` (which fires before any data arrives), every read is `None` and the cache never fills.

**Why it happens:** `playbin3` does ASYNC state transitions. Caps are negotiated once a buffer arrives. Per the gstreamer-devel narkive thread, the safe time is on `ASYNC_DONE` or `STREAM_START` bus messages — both of which fire after the `STATE_CHANGED → PLAYING` boundary.

**How to avoid:** Read caps in `_on_playbin_state_changed` (already a queued main-thread slot at player.py:736-746, post-PLAYING). If `get_current_caps()` returns non-None there, persist immediately. If `None`, fall back to `notify::caps` signal on the pad — fires when caps stabilize.

**Warning signs:** Test fixture sees `audio_caps_detected` never emitted; SQL row still has `sample_rate_hz=0, bit_depth=0` after one full PLAYING cycle.

### Pitfall 2: Threading boundary violation in caps handler (BLOCKING — Phase 43.1 regression)

**What goes wrong:** The `notify::caps` handler runs on the GStreamer streaming thread (not a `QThread`, not the bus-loop thread, no Qt event loop). Touching Qt widgets or calling `QTimer.singleShot(0, fn)` from this handler silently fails — exactly the Phase 43.1 cross-OS 10s-Shoutcast-death regression.

**Why it happens:** documented in `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` Rule 2.

**How to avoid:** The caps handler MUST only emit a queued `Signal` and return. ANY Qt-affined work (repo writes, widget updates, badge refresh) lives in the main-thread slot `_on_audio_caps_detected`. Use `Qt.ConnectionType.QueuedConnection` explicitly in the `connect()` call (mirrors `_cancel_timers_requested` at player.py:381-383).

**Warning signs:** Caps detected (test capture shows the streaming-thread handler ran) but the main-thread slot never fired; OR pipeline state changes mid-handler causing a CRITICAL assertion.

### Pitfall 3: `set_quality_map` invalidate-storm when chip is off (WARNING — Phase 68 Pitfall 7)

**What goes wrong:** If `set_quality_map(...)` calls `self.invalidate()` unconditionally, then every time the cache updates (and it can update on every playback cycle), the proxy re-filters all rows, causing visible tree-flicker even when the chip is off.

**Why it happens:** documented in Phase 68 D-04 / Pitfall 7 (see `station_filter_proxy.py:64-70` for the existing `set_live_map` precedent).

**How to avoid:** Guard `invalidate()` behind `if self._hi_res_only:`. Always invalidate from `set_hi_res_only` (predicate state changed). Never invalidate from `set_quality_map` unless `_hi_res_only=True`.

**Warning signs:** Tree flickers visibly on every poll cycle / repo update.

### Pitfall 4: DB write must precede UI re-query (BLOCKING — Phase 50 D-04)

**What goes wrong:** If `_on_audio_caps_detected` emits a UI-refresh signal BEFORE calling `repo.update_stream(...)`, the UI re-reads the station and gets stale rate/depth (still 0). The badge stays empty until the next refresh.

**Why it happens:** Phase 50 BUG-01 surfaced this — `update_last_played` had to precede `refresh_recent`. Same shape applies here.

**How to avoid:** `_on_audio_caps_detected` orders strictly as: (1) compare new (rate, depth) against in-memory cache; (2) if different, call `repo.update_stream(stream_id, sample_rate_hz=rate, bit_depth=depth)` first; (3) THEN emit any `quality_changed` signal that UI surfaces consume.

**Warning signs:** Badge takes two playback cycles to appear; tree-row pill missing on first replay.

### Pitfall 5: Idempotent ALTER TABLE re-run on every launch (NICE-TO-KNOW — Phase 47.2 precedent)

**What goes wrong:** `db_init` runs on every app launch. The try/except `sqlite3.OperationalError` is the only thing keeping it from being a hard error on the second run. If the planner deviates and uses raw ALTER without try/except, the app crashes on second launch.

**Why it happens:** SQLite doesn't have `ALTER TABLE ... IF NOT EXISTS` (planned but not landed); the standard idiom is the try/except.

**How to avoid:** Verbatim copy of the `bitrate_kbps` block at `repo.py:85-89`.

**Warning signs:** Second-launch `OperationalError: duplicate column name: sample_rate_hz`.

### Pitfall 6: Bus-thread captured `self._streams_queue` race with main-thread modification (NICE-TO-KNOW)

**What goes wrong:** The caps handler emits the stream's id captured at `_set_uri` time. If a failover races between the caps arriving and the handler firing, the captured id is for the OLD stream — but we persist rate/depth on the OLD id (which is correct — that's the stream we actually played caps from).

**Why it happens:** Failover replaces `self._current_stream`. Capturing the id at `_set_uri` time freezes the pairing.

**How to avoid:** Capture `self._caps_armed_for_stream_id = self._current_stream.id` at `_set_uri` time (or `_on_playbin_state_changed`), pass through to `audio_caps_detected.emit(sid, ...)`. The main-thread slot trusts the payload, never re-reads `self._current_stream`.

**Warning signs:** Rate/depth occasionally written to the wrong stream row during rapid failover (rare; unit-test guards via T-06 happy path).

### Pitfall 7: HLS adaptive-bitrate caveat (WARNING — DS-05 + S-01 acknowledge)

**What goes wrong:** Twitch streams go through streamlink+HLS. HLS playlists can switch bitrate mid-session (e.g., 720p → 480p → 360p). Phase 70's first-buffer-after-PLAYING caps read captures the INITIAL negotiated rate; subsequent HLS bitrate switches don't trigger a re-read because the one-shot guard disarms.

**Why it happens:** intentional simplification per CONTEXT DS-05 + S-01.

**How to avoid (documented behaviour, not a bug):** treat the cached rate/depth as "the rate/depth observed when this stream was first heard." Acceptable for the badge UX — the user understands a label, not a continuous gauge.

**Warning signs:** none — this is documented behaviour. The badge is informational; HLS dynamism is hidden from the user.

### Pitfall 8: Codec field validation if caps reveal codec mismatch (NICE-TO-KNOW — CONTEXT DS-03)

**What goes wrong:** Caps describe PCM (the decoded format), not the source codec. A FLAC stream and a 320kbps MP3 both decode to PCM at the negotiated rate/depth. Treating caps-derived PCM format as a "codec" would lie.

**Why it happens:** PCM-side caps come from `decodebin3`'s output, not the source side.

**How to avoid:** Phase 70 NEVER writes to `codec`. The classifier reads `codec` AS-IS (user/import-authored) and combines it with the caps-derived rate/depth. CONTEXT DS-03 explicit.

**Warning signs:** User reports "I labeled this AAC but it shows HI-RES" — that would be a classifier-logic bug, not a codec-correction concern (AAC is lossy, so `classify_tier` returns "" regardless of rate/depth).

### Pitfall 9: Player doesn't have access to `repo` (BLOCKING — discovery)

**What goes wrong:** `Player.__init__(self, parent=None)` does not currently take `repo` as a parameter (see `player.py:275`). The main-thread caps slot needs to call `repo.update_stream(...)`. If we naively reach for `self._repo`, it doesn't exist.

**Why it happens:** Player is constructed by `MainWindow.__init__` separately from the Repo. Repo is owned by MainWindow.

**How to avoid (planner's call):** Two viable options:
- **(A) Expose a queued public Signal on Player** (`audio_caps_detected = Signal(int, int, int)`); MainWindow connects it to its own slot that calls `self._repo.update_stream(...)` AND fans out to the panels (`now_playing._refresh_quality_badge`, `station_panel.update_quality_map`). Mirrors how `live_map_changed` is wired at `main_window.py:351`.
- **(B) Pass repo to Player on construction** (`Player(repo, parent)`). More invasive (changes all `make_player` test fixtures).

**Recommendation:** Option A. Mirrors Phase 68's signal-fan-out pattern verbatim. Test fixtures stay simple (mock Player is unchanged).

**Warning signs:** Plan writes `self._repo.update_stream(...)` in Player and discovers `AttributeError: 'Player' object has no attribute '_repo'` mid-implementation.

## Code Examples

### GStreamer caps query — verified API surface

```python
# Source: https://gstreamer-devel.narkive.com/JEGHHXNp/getting-sample-rate-sample-format-channels-cound-of-playbin-in-python
# Source: https://lazka.github.io/pgi-docs/GstAudio-1.0/enums.html

# Get the audio pad on a playbin / playbin3.
pad = playbin.emit('get-audio-pad', 0)   # 0 = first audio stream

# Read negotiated caps (returns None if not yet negotiated).
caps = pad.get_current_caps()
if caps is not None and caps.get_size() > 0:
    structure = caps.get_structure(0)
    # GstStructure.get_int returns (success, value) tuple in Python bindings.
    rate_ok, rate = structure.get_int('rate')
    fmt = structure.get_string('format')   # e.g., "S16LE"

# Watch for caps changes — fires on streaming thread.
handler_id = pad.connect('notify::caps', on_caps_changed_callback)
# To disconnect later:
pad.disconnect(handler_id)
```

### Phase 68 LIVE badge — verbatim template for `_quality_badge`

```python
# Source: musicstreamer/ui_qt/now_playing_panel.py:381-392 (Phase 68)
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

# Phase 70 — analogous _quality_badge construction, placed BEFORE _live_badge:
self._quality_badge = QLabel("", self)            # text set in _refresh_quality_badge
self._quality_badge.setTextFormat(Qt.PlainText)
self._quality_badge.setVisible(False)
self._quality_badge.setStyleSheet(<same QSS as above>)
icy_row.addWidget(self._quality_badge)            # FIRST
icy_row.addWidget(self._live_badge)               # SECOND
icy_row.addWidget(self.icy_label, 1)              # stretch — fills remaining
```

### Phase 47.2 idempotent migration — verbatim

```python
# Source: musicstreamer/repo.py:85-89 (Phase 47.2)
try:
    con.execute("ALTER TABLE station_streams ADD COLUMN bitrate_kbps INTEGER NOT NULL DEFAULT 0")
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists
```

### Phase 47.3 forward-compat idiom — verbatim

```python
# Source: musicstreamer/settings_export.py:418, 474 (Phase 47.3)
int(stream.get("bitrate_kbps", 0) or 0),  # P-2 forward-compat + defense
```

### Player test pattern for mocked `Gst.Message`

```python
# Source: tests/test_player_buffering.py (Phase 47.1, extended Phase 62)
from unittest.mock import MagicMock, patch

def make_player(qtbot):
    mock_pipeline = MagicMock()
    mock_bus = MagicMock()
    mock_pipeline.get_bus.return_value = mock_bus
    with patch("musicstreamer.player.Gst.ElementFactory.make",
               return_value=mock_pipeline):
        player = Player()
    return player

# Phase 70 — extend the pattern for caps:
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

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-stream model | Multi-stream per station (Phase 27 / STR-01..14) | v1.5 | Each stream gets its own row → Phase 70 caches rate/depth per-row. |
| sort by `position` only | `(-quality_rank, -codec_rank, -bitrate_kbps, position)` | Phase 47.1 | Phase 70 inserts `-sample_rate_hz, -bit_depth` between bitrate and position. |
| Inline `bus.add_signal_watch` | `GstBusLoopThread.run_sync` marshal | Phase 43.1 | Phase 70's caps work goes through queued Signals, not new bus-watch. |
| Hardcoded badge colors | `palette(highlight)` / `palette(highlighted-text)` | Phase 68 | Phase 70's `_quality_badge` inherits Phase 66 theme automatically. |

**Deprecated/outdated (NOT to use):**
- `playbin` (vs. `playbin3`) — Phase 35 migrated to `playbin3`. Don't reach for the older element.
- `bus.connect("sync-message", ...)` — Phase 35 explicit rejection (Pitfall 5 in player.py docstring). Don't add a sync-message handler.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `playbin.emit('get-audio-pad', 0)` works on `playbin3` (not just legacy `playbin`) | Pattern 1 | If wrong, fallback is `playbin3.get_property('current-audio')` + iterate audio sink pads. Test fixture in T-06 surfaces this. `[CITED: gstreamer-devel narkive thread Mar 2015 — answer references playbin generally; not verified specifically on playbin3 here.]` |
| A2 | `Gst.Structure` Python binding returns `(bool, int)` for `get_int("rate")` and a string for `get_string("format")` | Pattern 1 / classify_tier | Defensive both-paths handler in Pattern 1 (`hasattr(s, 'get_int')` + dict access fallback) makes this safe even if binding differs. |
| A3 | `notify::caps` on the audio pad is a stable signal name across GStreamer 1.20+ | Pattern 1 | If signal name differs, the connect raises immediately at test-setup time (visible). |
| A4 | ALAC is in CONTEXT D-02 as future-proofing (no current ALAC stations in the library) | Codec interaction | Confirmed against `_CODEC_RANK = {"FLAC": 3, "AAC": 2, "MP3": 1}` — ALAC isn't a known rank. Including ALAC in `_LOSSLESS_CODECS` is a dead branch today; documented as forward-compat. |
| A5 | Per `_populate_stream_picker` (now_playing_panel.py:1028-1038), text format is `f"{s.quality} — {s.codec}" if s.codec else s.quality or s.label or "stream"` — Phase 70's tier suffix is appended after the codec | Pattern picker | Verified in code; planner just adds `+ f" — {tier_text.upper()}"` when tier is non-empty. |
| A6 | `repo.update_stream` keyword-only kwargs preserve all existing positional callers | Repo signature | Verified: signature is `update_stream(self, stream_id, url, label, quality, position, stream_type, codec, bitrate_kbps=0)`. Phase 70 adds two more `=0` kwargs at the tail — same shape, same compat. |
| A7 | `Gst.TAG_AUDIO_CODEC` / `Gst.TAG_BITRATE` are encoded-stream tags, NOT PCM rate/depth | Don't Hand-Roll table | `[CITED: GStreamer audio_format docs — TAG_BITRATE describes encoded bitrate]` |
| A8 | moOde Audio's Hi-Res convention follows the JAS (Japan Audio Society) "Hi-Res Audio" certification: ≥24-bit AND/OR ≥96 kHz on a lossless codec, with the wider industry interpretation extending the rate threshold down to >48 kHz | Specifics | `[CITED: en.wikipedia.org/wiki/High-resolution_audio — "AES, CTA, JAS set 24-bit/96 kHz as the minimum"]`. CONTEXT D-02 deliberately picks >48 kHz (broader, more inclusive than strict JAS); this is a UX choice, not a spec violation. |

**User-confirm-before-execute:** A4 (no current ALAC stations) is the only assumption worth surfacing in plan-check — if the user has an ALAC station, A4 changes from "dead branch" to "live branch," but the classifier still classifies correctly. No correctness risk.

## Open Questions

1. **Should we expose `sample_rate_hz` / `bit_depth` on `currently_playing` for the tooltip?**
   - What we know: CONTEXT DP-04 / Claude's Discretion says "tooltip: yes — small QA win"; the player tracks the currently playing stream's id and the persisted columns are in the DB.
   - What's unclear: whether the tooltip reads from `self._station.streams` (in-memory) or re-queries the repo on each refresh.
   - Recommendation: read from `self._station.streams` (the panel already holds the bound station); avoid a repo round-trip. Planner picks the exact mechanism.

2. **`Qt.UserRole + N` for best_tier in tree model — required or optional?**
   - What we know: `station_tree_model.py:171` exposes the full `Station` via `Qt.UserRole`. The delegate can derive `best_tier` from `index.data(Qt.UserRole).streams` each paint.
   - What's unclear: paint perf with many tree rows (50–200 stations); deriving on each paint is O(streams per station).
   - Recommendation: skip the extra UserRole for now; the loop is tiny. Add a cached UserRole only if profiling shows it.

3. **Where does `set_quality_map` update get triggered from?**
   - What we know: Phase 68 wires `_on_aa_live_ready` → `live_map_changed.emit` → `MainWindow._on_live_map_changed` → `station_panel.update_live_map(live_map)` → proxy.
   - What's unclear: there's no analog "polling worker" for quality; quality updates are episodic (one per first-replay).
   - Recommendation: rebuild the map on every `audio_caps_detected` event — straightforward loop over `repo.list_stations()` since the data is in-memory after refresh anyway. Cost is O(stations) per replay (very rare event). Planner finalizes.

4. **Should `_hi_res_chip` visibility flip on every `set_quality_map` call, or only on app launch?**
   - What we know: CONTEXT F-02 says "visible when at least one station has a cached Hi-Res stream."
   - What's unclear: do we re-evaluate on every caps event (chip pops into existence as soon as the first Hi-Res stream is heard), or only at app launch / settings-import?
   - Recommendation: re-evaluate on every `set_quality_map` call. Tiny cost; better UX (user gets the chip the moment it becomes useful).

5. **Should the EditStationDialog Quality column update live while the dialog is open and a stream is playing?**
   - What we know: the dialog is modal-ish; it reads `repo.list_streams(station.id)` in `_populate`.
   - What's unclear: do we wire a signal so caps detected mid-dialog re-populates the table?
   - Recommendation: NO. Dialog is short-lived and the user opens it to edit, not to monitor. Save+Reopen sees the updated value. Keeps dialog code minimal.

## Environment Availability

Phase 70 is a code/config-only change. No new external dependencies. The existing GStreamer + PySide6 + sqlite3 stack covers all requirements. (`Skip` skipped — but doc'd for clarity: no system-level installs needed.)

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| GStreamer (with playbin3) | Caps extraction | ✓ | 1.28.2 (Win conda-forge); distro (Linux) | — |
| PyGObject (gi.repository.Gst) | Python bindings for Gst | ✓ | matched to GStreamer | — |
| PySide6 | All Qt widgets | ✓ | ≥6.10 | — |
| sqlite3 (stdlib) | DB migration | ✓ | Python stdlib | — |

**Missing dependencies:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-qt + (existing PyGObject mock via `unittest.mock`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| Quick run command | `uv run --with pytest --with pytest-qt pytest tests/test_hi_res.py tests/test_stream_ordering.py -x` |
| Full suite command | `uv run --with pytest --with pytest-qt pytest -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HRES-01 (T-01) | `classify_tier(codec, rate, depth)` returns "lossless" / "hires" / "" per D-02 / D-03 / D-04 | unit | `uv run --with pytest pytest tests/test_hi_res.py::test_classify_tier_truth_table -x` | ❌ Wave 0 |
| HRES-01 (T-01) | `bit_depth_from_format("S16LE")=16`, etc. — full GstAudioFormat coverage | unit | `uv run --with pytest pytest tests/test_hi_res.py::test_bit_depth_from_format -x` | ❌ Wave 0 |
| HRES-01 (T-01) | `best_tier_for_station(station)` picks Hi-Res > Lossless > "" across streams | unit | `uv run --with pytest pytest tests/test_hi_res.py::test_best_tier_for_station -x` | ❌ Wave 0 |
| HRES-01 (T-02) | Repo round-trip preserves `sample_rate_hz` + `bit_depth` (mirrors `test_export_import_roundtrip_preserves_bitrate_kbps`) | unit | `uv run --with pytest pytest tests/test_repo.py -k "sample_rate_hz or bit_depth" -x` | ✅ extend |
| HRES-01 (T-02) | Idempotent ALTER TABLE: second `db_init` call doesn't raise | unit | `uv run --with pytest pytest tests/test_repo.py::test_db_init_idempotent_for_sample_rate_hz -x` | ❌ Wave 0 |
| HRES-01 (T-03) | FLAC-96/24 sorts above FLAC-44/16 in `order_streams` | unit | `uv run --with pytest pytest tests/test_stream_ordering.py::test_hires_flac_outranks_cd_flac -x` | ✅ extend |
| HRES-01 (T-03) | Existing `test_gbs_flac_ordering` regression still passes | unit | `uv run --with pytest pytest tests/test_stream_ordering.py::test_gbs_flac_ordering -x` | ✅ |
| HRES-01 (T-04) | Settings-export ZIP round-trip preserves `sample_rate_hz` + `bit_depth`; pre-70 ZIP missing keys → 0 | unit | `uv run --with pytest pytest tests/test_settings_export.py -k "sample_rate_hz or bit_depth" -x` | ✅ extend |
| HRES-01 (T-05) | `station_star_delegate.paint` paints "HI-RES" pill for a station with one FLAC-96/24 stream | integration | `uv run --with pytest --with pytest-qt pytest tests/test_station_star_delegate.py::test_paints_hires_pill_for_hires_station -x` | ❌ Wave 0 |
| HRES-01 (T-06) | Player caps-extraction integration: synthetic `audio/x-raw,rate=96000,format=S24LE` → `repo.update_stream(stream_id, sample_rate_hz=96000, bit_depth=24)` called | integration | `uv run --with pytest --with pytest-qt pytest tests/test_player_caps.py::test_caps_persists_rate_and_bit_depth -x` | ❌ Wave 0 |
| HRES-01 (proxy) | `set_quality_map({1: "hires"})` + `set_hi_res_only(True)` filters tree to station_id=1 | integration | `uv run --with pytest --with pytest-qt pytest tests/test_station_filter_proxy.py::test_hi_res_only_filter -x` | ✅ extend |
| HRES-01 (proxy) | Pitfall 7 invalidate guard: `set_quality_map` does NOT call `invalidate()` when `_hi_res_only=False` | integration | `uv run --with pytest --with pytest-qt pytest tests/test_station_filter_proxy.py::test_set_quality_map_no_invalidate_when_chip_off -x` | ✅ extend |
| HRES-01 (threading) | Caps handler emits queued Signal; main-thread slot receives | integration | `uv run --with pytest --with pytest-qt pytest tests/test_player_caps.py::test_caps_emitted_as_queued_signal -x` | ❌ Wave 0 |
| HRES-01 (settings_export) | `_station_to_dict` emits `sample_rate_hz` + `bit_depth` keys | unit | `uv run --with pytest pytest tests/test_settings_export.py::test_station_to_dict_emits_quality_keys -x` | ✅ extend |

### Sampling Rate

- **Per task commit:** `uv run --with pytest --with pytest-qt pytest tests/test_hi_res.py tests/test_repo.py tests/test_stream_ordering.py -x`
- **Per wave merge:** `uv run --with pytest --with pytest-qt pytest tests/test_hi_res.py tests/test_repo.py tests/test_stream_ordering.py tests/test_settings_export.py tests/test_station_filter_proxy.py tests/test_station_star_delegate.py tests/test_player_caps.py tests/test_now_playing_panel.py tests/test_station_list_panel.py tests/test_edit_station_dialog.py -x`
- **Phase gate:** `uv run --with pytest --with pytest-qt pytest -x` (full suite green before `/gsd-verify-work`)

### Wave 0 Gaps

- [ ] `tests/test_hi_res.py` — covers HRES-01 T-01 (classify_tier + bit_depth_from_format + best_tier_for_station)
- [ ] `tests/test_player_caps.py` — covers HRES-01 T-06 (mocked notify::caps signal → repo.update_stream)
- [ ] `tests/test_station_star_delegate.py` — covers HRES-01 T-05 (best-tier-across-streams paint test); MAY exist already as portion of test_station_list_panel.py — confirm existence in Wave 0
- [ ] Extend `tests/test_repo.py` with sample_rate_hz + bit_depth round-trip + idempotent ALTER assertion
- [ ] Extend `tests/test_settings_export.py` with sample_rate_hz / bit_depth round-trip + missing-key forward-compat
- [ ] Extend `tests/test_stream_ordering.py` with rate/depth tiebreak case (T-03)
- [ ] Extend `tests/test_station_filter_proxy.py` with hi-res-only + Pitfall 7 guard cases

*(`tests/test_station_filter_proxy.py` exists with Phase 68 live_only coverage; it's the natural home for the hi-res-only mirror.)*

## Security Domain

`security_enforcement` is absent from `.planning/config.json` workflow block, so treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 70 adds no auth surface. |
| V3 Session Management | no | No session state. |
| V4 Access Control | no | Single-user desktop app. |
| V5 Input Validation | yes | `Qt.PlainText` on the new `_quality_badge` QLabel — same as Phase 68 LIVE badge (T-39-01 invariant). Tier text comes from a closed enum `{"hires", "lossless", ""}` so injection from user-controlled fields is impossible; defensive plain-text lock still applied. |
| V6 Cryptography | no | No new crypto. |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| HTML/markup in label text via metadata | Tampering | `setTextFormat(Qt.PlainText)` on `_quality_badge`. Tier strings are closed-enum, so this is belt-and-suspenders. |
| SQL injection via new columns | Tampering | Parameterized queries (sqlite3 `?` placeholders) — already the codebase convention. |
| Bus-thread → Qt object reach | Tampering / DoS | Queued Signal pattern (Phase 43.1 Pitfall 2) — bus handlers MUST NOT touch Qt widgets. |
| Caps payload as untrusted | Tampering | `bit_depth_from_format` returns 0 for unknown strings — closed allowlist; never executes attacker-controlled content. |

## Sources

### Primary (HIGH confidence)

- `musicstreamer/repo.py:51-90` — Phase 47.2 migration template (in-tree, verified)
- `musicstreamer/settings_export.py:108-130, 388-477` — Phase 47.3 forward-compat idiom (in-tree, verified)
- `musicstreamer/stream_ordering.py:1-65` — Phase 47.1 sort-key precedent (in-tree, verified)
- `musicstreamer/ui_qt/station_filter_proxy.py:1-148` — Phase 68 `set_live_map` / Pitfall 7 invalidate-guard (in-tree, verified)
- `musicstreamer/ui_qt/now_playing_panel.py:369-395, 1424-1483` — Phase 68 LIVE badge construction + `_refresh_live_status` (in-tree, verified)
- `musicstreamer/ui_qt/station_list_panel.py:271-296, 554-587` — Phase 68 `_live_chip` + `update_live_map` + `set_live_chip_visible` (in-tree, verified)
- `musicstreamer/ui_qt/station_star_delegate.py:1-113` — Phase 54 BUG-05 multi-pixmap painting template (in-tree, verified)
- `musicstreamer/player.py:235-410, 633-746` — Player signal/queued-connection patterns + bus-handler architecture (in-tree, verified)
- `musicstreamer/gst_bus_bridge.py:1-145` — `GstBusLoopThread.run_sync` contract (in-tree, verified)
- `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` — Phase 43.1 Pitfall 1 & 2 (in-tree, verified)
- `tests/test_player_buffering.py:1-82` — mocked GStreamer Player test pattern (in-tree, verified)
- `tests/test_settings_export.py:610-721` — forward-compat round-trip test template (in-tree, verified)
- `tests/test_stream_ordering.py:147-172` — `test_gbs_flac_ordering` regression target (in-tree, verified)

### Secondary (MEDIUM confidence — verified against official docs)

- [GstAudio.Format enum (lazka.github.io PGI docs)](https://lazka.github.io/pgi-docs/GstAudio-1.0/enums.html) — bit-depth-per-format mapping (verified via WebFetch)
- [Wikipedia: High-resolution audio](https://en.wikipedia.org/wiki/High-resolution_audio) — JAS / AES / CTA Hi-Res criteria (24-bit/96 kHz minimum)
- [enjoythemusic.com — JAS Hi-Res Audio criteria editorial](https://www.enjoythemusic.com/magazine/viewpoint/0319/JAS_Hi_Res_Audio_Music_Possibly_Misleading.htm) — JAS logo certification criteria details

### Tertiary (LOW confidence — single-source community)

- [gstreamer-devel narkive thread: "Getting sample rate / sample format / channels count of playbin in python"](https://gstreamer-devel.narkive.com/JEGHHXNp/getting-sample-rate-sample-format-channels-cound-of-playbin-in-python) — `playbin.emit('get-audio-pad', 0)` + `pad.get_current_caps()` + `notify::caps` Python pattern. Cross-verified against the [official GStreamer Python tutorial](https://brettviren.github.io/pygst-tutorial-org/pygst-tutorial.html) and [GStreamer playback docs](https://gstreamer.freedesktop.org/documentation/playback/playbin.html). Specifically the `playbin3` variant of `get-audio-pad` is `[ASSUMED]` to mirror `playbin` (verified to work for `playbin` in the thread; assumed equivalent for `playbin3`). Test T-06 surfaces a mismatch if any.
- [moodeaudio.org forum threads](https://moodeaudio.org/forum/) — moOde-specific Hi-Res indicator UI behaviour not found in public search; convention inferred from JAS criteria per CONTEXT D-02.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library is already in-project and verified.
- Architecture: HIGH — five surgical surfaces all have verbatim Phase 47.x / 68 templates.
- Caps API: MEDIUM — `notify::caps` is documented for `playbin` per community sources; we recommend Pattern 1b (combined sync-read in `_on_playbin_state_changed` + async notify) so either path catches the data.
- Pitfalls: HIGH — Phase 43.1 + 50 + 68 documented all blocking pitfalls.

**Research date:** 2026-05-11
**Valid until:** 2026-06-10 (30 days — codebase is stable, GStreamer pin is locked, no external dependencies in flux)
