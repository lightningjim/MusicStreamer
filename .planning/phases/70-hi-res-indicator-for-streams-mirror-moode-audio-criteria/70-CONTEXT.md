# Phase 70: Hi-res indicator for streams (mirror moOde audio criteria) - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a visual indicator that surfaces stream audio quality across the app, mirroring moOde Audio's standard distinction between **Lossless** (lossless codec at CD-quality or below) and **Hi-Res** (lossless codec at >48 kHz OR >16-bit). Detection is runtime-driven from the GStreamer audio sink's negotiated caps, and the resulting `sample_rate_hz` / `bit_depth` are persisted per stream so the badge can appear on tree rows before playback once each stream has been heard at least once.

The badge is purely informational + curation: it does not change codec routing or playback behavior, but it does feed two browsing affordances — a new "Hi-Res only" filter chip in the station list (parallel to Phase 68's "Live now" chip) and a secondary sort key inside `stream_ordering.py` so a Hi-Res FLAC stream beats a CD-FLAC sibling on the same station during failover.

**In scope:**
- New schema columns on `station_streams`: `sample_rate_hz INTEGER NOT NULL DEFAULT 0` and `bit_depth INTEGER NOT NULL DEFAULT 0` (mirror Phase 47.2 `bitrate_kbps` migration shape — body of `CREATE TABLE` + idempotent `ALTER TABLE` in try/except `sqlite3.OperationalError`, no `user_version` bump).
- New `StationStream` dataclass fields `sample_rate_hz: int = 0` and `bit_depth: int = 0`, positioned AFTER `bitrate_kbps` to preserve positional construction compat (Phase 47.1 D-01 precedent).
- New `Repo.insert_stream` / `Repo.update_stream` kwargs `sample_rate_hz=0`, `bit_depth=0` with safe defaults so existing positional callers (`aa_import`, `yt_import`, `edit_station_dialog`, `discovery_dialog`, `settings_export`) compile unchanged.
- Player-side caps extraction: hook the audio sink pad (or playbin3's `current-audio` query equivalent), on the first negotiated caps after `STATE_CHANGED → PLAYING`, parse `rate` and the `format` string (`S16LE` → 16, `S24LE` → 24, `S32LE`/`F32LE` → 32) into rate/bit-depth ints, emit a queued signal to main, and persist via `repo.update_stream` if (currently_empty OR value_differs_from_cache). Write-once per stream per playback; idempotent on repeat.
- Pure tier-classification helper in a new module (suggest `musicstreamer/hi_res.py`) or extension of `stream_ordering.py`: `classify_tier(codec, sample_rate_hz, bit_depth) → "" | "lossless" | "hires"`. Two tiers only.
- Now-playing badge: new `QLabel` sibling of `_live_badge` in `now_playing_panel.py:378-395` `icy_row`. Same QSS pattern (`palette(highlight)` bg, `palette(highlighted-text)` fg, `border-radius: 8px`, bold). Text: "LOSSLESS" or "HI-RES". Visibility driven by a `_refresh_quality_badge()` call from `_on_station_bind` / `_on_caps_detected` / theme refresh.
- Station-tree row badge: extend `station_star_delegate.py` (or add a sibling `station_quality_delegate.py` painted in the same column to the LEFT of the star) that paints a mini "HI-RES" / "LOSSLESS" pill before the star icon. Tier value = `max(classify_tier(s) for s in station.streams)` per station (best-tier-across-streams; Hi-Res > Lossless > nothing).
- Stream picker dropdown badge: append the tier label to the QComboBox item text (e.g., "FLAC 1411 — HI-RES") or use a custom item delegate. Lightweight reformatting of the existing picker entry.
- EditStationDialog streams table: add a new read-only "Quality" column showing the cached tier (or blank if unknown). No editing — populated from cached rate/depth.
- Station-list filter chip: new `_hi_res_chip = QPushButton("Hi-Res only", ...)` in `station_list_panel.py` near line 271-283, parallel structure to `_live_chip`. Hidden by default; visibility flips on when any station in the library has a cached Hi-Res stream (avoid dead chip on fresh installs). Backed by `StationFilterProxyModel.set_hi_res_only(bool)` + a `set_quality_map(...)` analog to Phase 68's `set_live_map` (with Pitfall 7 invalidate guard).
- `stream_ordering.order_streams` extended with rate/depth as secondary sort within same codec rank: key becomes `(-quality_rank, -codec_rank, -bitrate_kbps, -sample_rate_hz, -bit_depth, position)` — within FLAC, 96/24 sorts above 44/16. Unknown rate/depth (0) sort with current behavior (last among same codec).
- Settings export/import: `settings_export.py` `_insert_station` + `_replace_station` blocks gain `int(stream.get("sample_rate_hz", 0) or 0)` and `int(stream.get("bit_depth", 0) or 0)` idioms — exactly mirrors the Phase 47.3 `bitrate_kbps` forward-compat pattern. Old ZIPs missing the keys default to 0.
- Tests: pure-helper tests for `classify_tier` (lossless ≤16/48 → "lossless"; lossless +>48 → "hires"; lossless +>16 → "hires"; lossy → ""; unknown rate/depth + FLAC → "lossless"); repo round-trip; `order_streams` rate/depth tiebreak (FLAC-96 above FLAC-44); settings-export forward-compat; tree-delegate best-tier-across-streams; player caps-extraction integration (mocked GStreamer message).

**Out of scope:**
- No DSD tier. Internet radio essentially never carries DSD; the third state would not exercise on this user's library. Schema is two-tier-only.
- No user-set "this is Hi-Res" checkbox in EditStationDialog. Detection is automatic from caps; manual override stays in deferred ideas if accuracy gaps emerge.
- No codec auto-correction. If runtime caps reveal codec mismatch with the user-labeled `codec` field, only `sample_rate_hz` / `bit_depth` are written. The `codec` field stays user-authored (import/UI source of truth). Stream picker labels and codec-based sort are untouched.
- No in-tree quality badge with bitrate readout. Tree shows the two-tier text label only; numeric rate/depth display lives in the now-playing badge tooltip if at all (planner's discretion).
- No tooltip on the tree row badge revealing exact rate (e.g., "96/24"). Optional — leave to planner. Default: no tooltip on tree row (keeps delegate code minimal).
- No "Lossless+" / multi-chip filter combinations. One chip: "Hi-Res only". Lossless gets its badge but no dedicated filter (avoids chip-row clutter; small library doesn't need it).
- No `Gst.Registry` probing for plugin availability. Phase 69 owns the bundle-side codec presence question; Phase 70 trusts the cache.
- No retroactive sample-rate inference from `bitrate_kbps`. GBS.FM's `bitrate_kbps=1411` sentinel is left at face value; caps detection on first replay supplies the real rate. Cache stays empty until first replay populates it.
- No migration script to backfill existing streams. The cache populates on first replay; no migration wave. (Future option in deferred ideas if a fast-fill UAT job is wanted.)
- No Windows-specific extra work. GStreamer caps query API is identical on both platforms. UAT verifies playback caps land cleanly on Win11 VM as part of normal regression, not as a dedicated bundle phase.

</domain>

<decisions>
## Implementation Decisions

### Criteria definition

- **D-01:** **Two tiers only — `Lossless` and `Hi-Res`.** Internet radio reality: almost all lossless streams in this user's library are CD-quality FLAC; a third "DSD" tier would never fire. Two tiers cover Sony/JAS-style "Hi-Res Audio" intent without dead states.
- **D-02:** **Tier rules:**
  - `Lossless` = `codec ∈ {FLAC, ALAC}` AND `sample_rate_hz ≤ 48000` AND `bit_depth ≤ 16`.
  - `Hi-Res` = `codec ∈ {FLAC, ALAC}` AND (`sample_rate_hz > 48000` OR `bit_depth > 16`).
  - Lossy codecs (MP3, AAC, HE-AAC, OPUS, OGG, WMA): no badge at any rate/depth.
- **D-03:** **FLAC + unknown rate/depth defaults to `Lossless`.** Most common case (GBS.FM, SomaFM FLAC). On first replay the player's caps extraction may upgrade it to `Hi-Res` if rate > 48 kHz. Safe optimistic default; never over-claims Hi-Res without evidence.
- **D-04:** **No badge for lossy streams period.** No "HD AAC" / "high-bitrate MP3" tier. moOde doesn't recognize lossy as hi-res; we follow.
- **D-05:** **Tier labels: `LOSSLESS` and `HI-RES`.** All-caps, identical typography to Phase 68 `LIVE` badge.

### Source of truth

- **DS-01:** **Runtime GStreamer caps + persistent per-stream cache.** Schema gains `sample_rate_hz` and `bit_depth` columns on `station_streams` (Phase 47.2 `bitrate_kbps` precedent — see `repo.py:86`). On first negotiated audio caps after PLAYING, player parses rate + format-derived bit-depth and writes them to the playing stream's row if currently 0 OR if value differs. Write-once per playback (idempotent if cache already matches).
- **DS-02:** **Bit-depth derivation from GStreamer format string:**
  - `S16LE` / `S16BE` / `U16LE` / `U16BE` → 16
  - `S24LE` / `S24BE` / `S24_32LE` / `S24_32BE` → 24
  - `S32LE` / `S32BE` / `F32LE` / `F32BE` → 32 (treat float as 32-bit-equivalent for hi-res classification)
  - Anything else → 0 (unknown)
  Planner finalizes the mapping; researcher can validate exhaustiveness against GStreamer's `GstAudioFormat` enum.
- **DS-03:** **Don't auto-correct codec.** Codec stays user/import-authored (drives UI labels, stream picker, sort). Runtime caps describe negotiated PCM, not the source codec — they tell us rate/depth, not source compression. Phase 70 writes ONLY rate/depth back.
- **DS-04:** **Settings ZIP round-trip carries the cache.** `settings_export.py` `_insert_station` + `_replace_station` blocks gain `int(stream.get("sample_rate_hz", 0) or 0)` and `int(stream.get("bit_depth", 0) or 0)` — pure forward-compat idiom (Phase 47.3 pattern). Old ZIPs without the keys default to 0 (cache rebuilds on next replay).
- **DS-05:** **No automatic backfill.** Existing streams stay at 0/0 until first replay populates them. Acceptable — the user actively rotates through ~10–20 stations a week; the cache fills naturally within a few weeks.

### Display surfaces

- **DP-01:** **All four surfaces ship in this phase:**
  1. Now-playing panel — `_quality_badge` `QLabel` as sibling of `_live_badge` in `icy_row` (now_playing_panel.py:378-395). Same QSS pattern.
  2. Station tree row — delegate paints a mini-badge before the star column. Tier = best across station's streams.
  3. Stream picker dropdown — per-stream tier appended to the QComboBox item text.
  4. EditStationDialog streams table — new read-only "Quality" column.
- **DP-02:** **Tree row badge = best tier across streams.** If any stream is Hi-Res, row shows HI-RES; else if any is Lossless, row shows LOSSLESS; else nothing. Surfaces capability ("this station CAN deliver Hi-Res"), not the failover-default tier.
- **DP-03:** **Tree row badge placement: right side, before the star column.** Extend `station_star_delegate.py` (or add a parallel `station_quality_delegate.py` painted in the same item column to the LEFT of the star). Inline mini pill, NOT a name suffix and NOT a subtitle row (preserves library scan density).
- **DP-04:** **Now-playing badge layout: immediately LEFT of `_live_badge`.** Order in `icy_row`: `[QUALITY] [LIVE] icy_label` — both badges coexist when an AA station is live AND the cached stream is hi-res. Phase 68 LIVE badge is the inner template.
- **DP-05:** **Stream picker text format.** Reformat the existing picker label as `f"{label} — {tier_text}"` when tier is non-empty (e.g., "FLAC 1411 — HI-RES"). Tier suffix added by the picker's stream-formatter, not via a custom delegate (minimal change).
- **DP-06:** **EditStationDialog "Quality" column.** New non-editable column in the streams `QTableWidget`. Displays "Hi-Res", "Lossless", or empty. Read from cached `sample_rate_hz` / `bit_depth` on each row. No edit affordance (user picks a checkbox if D-11 future override lands; out of scope here).
- **DP-07:** **Badge styling = Phase 68 LIVE QSS verbatim.** `palette(highlight)` bg, `palette(highlighted-text)` fg, `border-radius: 8px`, `padding: 2px 6px`, bold. `Qt.PlainText` security lock. Same per-badge instance for now-playing and the delegate-painted tree badge can synthesize matching visuals via `QStyleOptionViewItem` or `painter.fillRect` + theme-aware color tokens.

### Filter & sort

- **F-01:** **New `Hi-Res only` filter chip in `station_list_panel.py`** parallel to Phase 68's `_live_chip` (lines 271-283). `QPushButton("Hi-Res only", ...)` with `setCheckable(True)`. Toggles `StationFilterProxyModel.set_hi_res_only(checked)` (new method).
- **F-02:** **Chip visibility gate.** Hidden by default. Visible when at least one station in the model has a cached Hi-Res stream (avoid dead chip on a clean install). Cached-quality map fed into the proxy via a new `set_quality_map(...)` analog to Phase 68's `set_live_map` — invalidate guard required per Phase 68 Pitfall 7.
- **F-03:** **No `Lossless+` chip.** One filter chip only ("Hi-Res only"). Keeps the chip row uncluttered.
- **S-01:** **`order_streams` extended with rate/depth as secondary sort within same codec.** Updated key: `(-quality_rank, -codec_rank, -bitrate_kbps, -sample_rate_hz, -bit_depth, position)`. A FLAC-96/24 stream sorts above a FLAC-44/16 sibling. Unknown (0) values keep current behavior (sort behind known).
- **S-02:** **No cross-codec hi-res promotion.** A theoretically hi-res AAC (rare/synthetic) does NOT outrank a CD-FLAC. `codec_rank` stays primary — lossless-over-lossy invariant preserved.

### Test discipline

- **T-01:** **Pure-helper tests for `classify_tier` first.** Six baseline cases minimum: FLAC/44/16 → lossless, FLAC/96/24 → hires, FLAC/48/24 → hires (bit-depth-only trigger), FLAC/0/0 → lossless (fallback), MP3/* → "", AAC/* → "".
- **T-02:** **Repo round-trip tests for `sample_rate_hz` / `bit_depth`.** Mirror Phase 47.2 bitrate_kbps coverage in `tests/test_repo.py`.
- **T-03:** **`order_streams` regression.** Add the FLAC-96/24-beats-FLAC-44/16 case to `tests/test_stream_ordering.py`. The existing GBS-FLAC-sentinel test (`test_gbs_flac_ordering`) must still pass.
- **T-04:** **Settings-export forward-compat.** `tests/test_settings_export.py` (or wherever the bitrate_kbps fwd-compat test lives) gets a sibling assertion for sample_rate_hz / bit_depth round-trip + missing-key tolerance.
- **T-05:** **Tree delegate best-tier test.** Construct a station with one MP3 + one FLAC-96/24 stream; assert delegate paints "HI-RES" (or at minimum the model exposes "hires" tier via a Qt.UserRole).
- **T-06:** **Player caps-extraction integration test.** Mock the GStreamer message bus or use the existing player test harness; feed a synthetic `audio/x-raw,rate=96000,channels=2,format=S24LE` caps; assert the stream row gets `sample_rate_hz=96000, bit_depth=24` after first PLAYING.

### Migration / rollout

- **M-01:** **DB migration: idempotent `ALTER TABLE` in try/except `sqlite3.OperationalError`.** Mirrors Phase 47.2 D-02. No `user_version` bump. Existing rows get default 0 for both new columns.
- **M-02:** **No data-fill migration.** Cache populates organically on replay. Acceptable per DS-05.
- **M-03:** **No deprecated `bitrate_kbps` repurposing.** GBS.FM's `bitrate_kbps=1411` sentinel stays put — it's a codec-rank tiebreak hint, not a hi-res signal. Rate/depth are independent columns.

### Claude's Discretion

- Researcher picks the exact GStreamer API entry point for caps extraction: `playbin.emit("get-audio-tags", n)`, sink-pad `get_current_caps()` after `pad-added`, or a `gst_element_get_static_pad("sink")` query on the audio sink. The end-to-end behavior is fixed (first-buffer-after-PLAYING → parse rate/format → persist if-changed); the GStreamer plumbing is researcher's call. Recommendation: hook the audio-sink pad's `notify::caps` signal and read on first caps-set.
- Planner picks whether `classify_tier` lives in a new `musicstreamer/hi_res.py` module or extends `musicstreamer/stream_ordering.py`. Recommendation: new module (one logical concept per file; mirrors `eq_profile.py` precedent). Both `order_streams` and the UI badge layer import from it.
- Planner picks the new column names. Defaults: `sample_rate_hz` and `bit_depth` (both `INTEGER NOT NULL DEFAULT 0`). Alternatives: `audio_rate_hz`, `audio_bit_depth` — researcher/planner may prefer the audio_ prefix for column-name clarity. Either is acceptable.
- Planner picks the tree-delegate strategy: extend `station_star_delegate.py` to also paint the quality pill, OR add a sibling `station_quality_delegate.py` for a different item column. Recommendation: a single combined delegate in the existing star column keeps row geometry simple; the Phase 54 BUG-05 portrait fix already trained this delegate to handle multi-pixmap painting.
- Planner picks how the proxy's `set_quality_map` is keyed (station_id → tier-string, or station_id → set-of-tiers). The chip-visibility predicate only needs "any Hi-Res in the library", so a flat `dict[int, str]` of station-best-tier is sufficient and parallels Phase 68's `set_live_map` shape.
- Planner picks whether the now-playing badge also shows a tooltip like "96 kHz / 24-bit". Default: yes — small QA win, minimal code. If the player exposes the cached rate/depth on `currently_playing`, the tooltip falls out for free.
- Planner picks the EditStationDialog "Quality" column index (insertion before/after existing columns). Recommendation: position it as the last column after the existing codec/bitrate columns so older test snapshots keep their indices stable.

### Folded Todos

No todos folded.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 70 inputs (high-level)
- `.planning/ROADMAP.md` — Phase 70 entry (one-line; this CONTEXT.md is the operative scope source)
- `.planning/PROJECT.md` — current state (Phase 69 complete, milestone v2.1, GStreamer 1.28+ on Windows pinned)
- `.planning/REQUIREMENTS.md` — v2.1 requirements table; Phase 70 likely adds a new HRES-01 (or similar) row

### Data model + schema (Phase 47.x precedent — the migration template to mirror)
- `musicstreamer/models.py` lines 11-21 — `StationStream` dataclass; new fields `sample_rate_hz`, `bit_depth` append AFTER `bitrate_kbps`
- `musicstreamer/repo.py` lines 51-90 — `station_streams` CREATE TABLE body + Phase 47.2 idempotent ALTER TABLE block (lines 86) — the exact migration shape Phase 70 mirrors
- `musicstreamer/repo.py` lines 188-200 — `insert_stream` / `update_stream` signatures (Phase 70 adds two kwargs)
- `.planning/phases/47-stream-quality-by-codec-rank/47-02-PLAN.md` — Phase 47.2 plan (bitrate_kbps migration walkthrough)

### Stream ordering (Phase 47.1 + GBS FLAC sentinel)
- `musicstreamer/stream_ordering.py` lines 17-65 — `_CODEC_RANK`, `_QUALITY_RANK`, `order_streams` (Phase 70 extends the sort key with rate/depth)
- `musicstreamer/gbs_api.py` lines 59-70 — GBS.FM FLAC bitrate_kbps=1411 CD-baseline sentinel (informs cache D-03 default-to-Lossless)
- `tests/test_stream_ordering.py` lines 147-172 — `test_gbs_flac_ordering` regression target

### Badge pattern (Phase 68 LIVE badge — verbatim template)
- `musicstreamer/ui_qt/now_playing_panel.py` lines 369-395 — `_live_badge` QLabel + QSS template Phase 70 reuses
- `musicstreamer/ui_qt/now_playing_panel.py` lines 1387-1480 — `_refresh_live_status` slot pattern (analog `_refresh_quality_badge`)
- `musicstreamer/ui_qt/station_list_panel.py` lines 271-283 — `_live_chip` filter chip pattern Phase 70 mirrors for `_hi_res_chip`
- `musicstreamer/ui_qt/station_filter_proxy.py` — `set_live_map` / `set_live_only` (Phase 68); Phase 70 adds `set_quality_map` / `set_hi_res_only`
- `.planning/phases/68-add-feature-for-detecting-live-performance-streams-di-fm-and/68-CONTEXT.md` — Phase 68 D-decisions covering Pitfall 7 invalidate-guard pattern

### Delegate / tree-row paint pattern
- `musicstreamer/ui_qt/station_star_delegate.py` — current single-icon delegate; Phase 70 either extends this or sibling-paints
- `.planning/phases/54-rectangular-logo-display/54-RESEARCH.md` lines 162 — portrait fix train: delegate handles multi-pixmap painting (D-09 reference)

### Player + GStreamer caps extraction
- `musicstreamer/player.py` lines 314-319 — GStreamer bus signal watches (`message::tag`, `message::error`); Phase 70 adds a caps source (pad notify::caps OR audio-tags message)
- `musicstreamer/player.py` lines 674-707 — `_on_gst_tag` + `_on_gst_buffering` handlers — the same bus-thread → Qt-queued-signal pattern Phase 70 uses for caps
- `musicstreamer/gst_bus_bridge.py` — `GstBusLoopThread`; reminder that caps-handlers run on bus-loop thread and may only emit signals (Phase 43.1 cross-OS regression in spike-findings)
- `.claude/skills/spike-findings-musicstreamer/references/qt-glib-bus-threading.md` — required reading for any new bus-handler in Phase 70

### Settings export round-trip
- `musicstreamer/settings_export.py` `_insert_station` / `_replace_station` — Phase 47.3 forward-compat `int(stream.get("bitrate_kbps", 0) or 0)` idiom; Phase 70 mirrors for sample_rate_hz / bit_depth
- `.planning/phases/47-stream-quality-by-codec-rank/47-03-PLAN.md` — Phase 47.3 export forward-compat pattern

### Stream picker + EditStationDialog
- `musicstreamer/ui_qt/edit_station_dialog.py` — streams `QTableWidget` (Phase 47.3 added `_BitrateDelegate` + QIntValidator at module scope); Phase 70 adds a non-editable Quality column
- `musicstreamer/ui_qt/now_playing_panel.py` stream picker QComboBox — picker formatter is the surface Phase 70 reformats with " — TIER" suffix

### Reference (informational)
- moOde Audio Player documentation — Lossless vs Hi-Res convention reference (Sony / Japan Audio Society "Hi-Res Audio" criteria: ≥24-bit AND/OR ≥48 kHz on a lossless codec). External doc — researcher links the canonical URL in 70-RESEARCH.md if needed.
- `.claude/skills/spike-findings-musicstreamer/SKILL.md` — auto-load for Windows + GStreamer work; no direct Phase 70 change but new bus handlers must respect Phase 43.1 threading invariants.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 68 LIVE badge QSS pattern** at `now_playing_panel.py:381-393` — verbatim template for the new `_quality_badge` (same `palette(highlight)` + `palette(highlighted-text)` theming, same border-radius, same bold). Means Phase 70's badge auto-respects Phase 66 theme switches with zero theme-token additions.
- **Phase 68 `_live_chip` filter chip** at `station_list_panel.py:271-283` — exact template for `_hi_res_chip`. Includes the visibility-gating pattern (hidden until backing data exists) that Phase 70 replicates.
- **`StationFilterProxyModel.set_live_map` / `set_live_only`** — sibling architecture for `set_quality_map` / `set_hi_res_only`. Phase 68's Pitfall 7 invalidate-guard documented and locked.
- **Phase 47.2 `bitrate_kbps` migration shape** at `repo.py:86` — idempotent ALTER TABLE in try/except `sqlite3.OperationalError`, no user_version bump, default-zero column. Phase 70 mirrors twice (one column each for sample_rate_hz, bit_depth).
- **Phase 47.3 settings-export forward-compat idiom** — `int(stream.get("KEY", 0) or 0)` in both `_insert_station` and `_replace_station`. Phase 70's two new columns slot into the same lines.
- **GStreamer bus → queued-signal pattern** in `player.py:674-707` (`_on_gst_tag` / `_on_gst_buffering`) — Phase 70's caps handler follows the same shape (bus-loop thread emits, main thread persists via repo).
- **`station_star_delegate.py`** — single-icon delegate with portrait/landscape painting trained in Phase 54 BUG-05. Phase 70's tree-row badge either extends this delegate or paints alongside.

### Established Patterns
- **Two-tier quality classification** is novel in this codebase, but the `_CODEC_RANK` dict (`stream_ordering.py:18`) is the prior art for "small enum-mapped helper, case-insensitive, None-safe". `classify_tier` mirrors that shape.
- **Caps-driven runtime data with persistent cache** is novel — no prior pattern in this app. Closest analog: `cover_art.py`'s iTunes session-dedup cache (`_last_cover_icy`) and `aa_live.py`'s Phase 68 poll-cache.
- **Best-of-N across station streams** — pattern matches `order_streams`'s within-station view but applied to "tier" instead of "ordering". Researcher confirms if a `best_tier_for_station(station) -> str` helper belongs in the same module as `classify_tier`.
- **Forward-compat ZIP round-trip with default-zero** — codified in Phase 47.3 (`int(stream.get("KEY", 0) or 0)`). Phase 70 inherits.
- **Filter-chip visibility gate** — Phase 68's `_live_chip` is hidden when `audioaddict_listen_key` is missing. Phase 70's `_hi_res_chip` is hidden until the quality_map contains any "hires" entry.
- **Plain-text invariant on badges** — `Qt.PlainText` setTextFormat is mandatory (V5 ASVS — Phase 68 enforcement); applies to the new `_quality_badge` and the picker text formatting.

### Integration Points
- **`musicstreamer/models.py:11-21`** — append `sample_rate_hz: int = 0` and `bit_depth: int = 0` to `StationStream`. Positional construction compat preserved by appending AFTER existing fields.
- **`musicstreamer/repo.py:51-90`** — extend CREATE TABLE body + add two idempotent ALTER TABLE blocks (lines ~86 analog) for the new columns. Update `insert_stream` / `update_stream` SQL + Python signatures (lines 188-200).
- **`musicstreamer/stream_ordering.py`** — extend `order_streams` sort key with `-sample_rate_hz, -bit_depth` between bitrate_kbps and position. New top-of-file constants documenting hi-res rate/depth thresholds.
- **`musicstreamer/hi_res.py` (NEW)** OR extension to `stream_ordering.py` — `classify_tier(codec, sample_rate_hz, bit_depth)` + `best_tier_for_station(station)`.
- **`musicstreamer/player.py`** — new caps handler (audio-sink pad `notify::caps` OR equivalent) emitting a queued `audio_caps_detected = Signal(int, int, int)` (stream_id, rate, bit_depth) → main thread → `repo.update_stream(stream_id, sample_rate_hz=..., bit_depth=...)`.
- **`musicstreamer/ui_qt/now_playing_panel.py:378-395`** — add `_quality_badge` QLabel before `_live_badge` in `icy_row`. New `_refresh_quality_badge()` slot wired to bind/caps signals.
- **`musicstreamer/ui_qt/station_star_delegate.py`** — extend `paint()` to render the tier pill before the star icon, OR add a sibling delegate. `sizeHint()` may need to grow to accommodate the pill.
- **`musicstreamer/ui_qt/station_tree_model.py`** — expose a new Qt.UserRole for "best tier" (`Qt.UserRole + N`) so the delegate can read it without re-deriving on every paint.
- **`musicstreamer/ui_qt/station_list_panel.py:271-283`** — add `_hi_res_chip` parallel to `_live_chip`. Signal wiring to a new method on `StationFilterProxyModel`.
- **`musicstreamer/ui_qt/station_filter_proxy.py`** — `set_quality_map`, `set_hi_res_only`, integration into `filterAcceptsRow`. Pitfall 7 invalidate-guard applies.
- **`musicstreamer/ui_qt/edit_station_dialog.py`** — new "Quality" column in the streams `QTableWidget`. Read-only.
- **`musicstreamer/ui_qt/now_playing_panel.py`** stream picker QComboBox — pull the picker's row-formatter and append " — TIER" when tier is non-empty.
- **`musicstreamer/settings_export.py`** — two new fwd-compat lines in `_insert_station` + `_replace_station` (analogous to bitrate_kbps).

</code_context>

<specifics>
## Specific Ideas

- The phase name explicitly references **moOde Audio's** convention. Researcher should link the canonical moOde criteria doc (or the JAS "Hi-Res Audio" criteria summary) in `70-RESEARCH.md` so the tier rules in D-02 trace back to a concrete external source. moOde itself surfaces "Hi-Res" when the negotiated PCM is `> 16-bit OR > 44.1 kHz`; we use `> 48 kHz` as the rate threshold per the broader JAS rule.
- The user picked the **broadest possible visibility scope** — all four surfaces (now-playing, tree row, stream picker, EditStationDialog). The badge is meant to be discoverable both at the moment of playback and during library browsing.
- The user explicitly chose to **add the "Hi-Res only" filter chip** and to **extend `stream_ordering.py`** to prefer higher rate/depth within the same codec. This is more than a display-only phase — it changes failover behavior on stations with multiple FLAC streams at different rates.
- The user accepted the **default-to-Lossless for FLAC-with-unknown-caps** semantics. Practical effect: GBS.FM rows show "LOSSLESS" immediately after first play (or upgrade to "HI-RES" if GBS ever serves 96 kHz). New SomaFM FLAC stations show "LOSSLESS" the first time they're played.
- The user accepted **runtime-only detection** — no manual override checkbox in EditStationDialog. The deferred-ideas section captures the override option as a future affordance if accuracy gaps emerge.
- The user did NOT request a **DSD tier**, a **per-codec breakdown** ("HE-AAC HD"), or a **streaming-protocol-aware** layer (HLS adaptive bitrate caveat).
- `--chain` flag is set; CONTEXT.md is the input to `/gsd-plan-phase 70 --chain` which auto-advances to plan-phase (and then execute-phase per chain mode).

</specifics>

<deferred>
## Deferred Ideas

- **Manual "This is Hi-Res" override checkbox in EditStationDialog** — rejected in this phase (DS-03 trusts runtime caps). Revisit if real-world detection accuracy is wrong for specific stations (e.g., HLS adaptive streams whose first negotiated caps don't reflect the user-tier reality).
- **DSD tier** — out of scope. Internet radio doesn't ship DSD; revisit only if a DSD-over-HTTP source appears in the library.
- **Numeric rate/depth readout on tree row** — only the tier label is on the row. Tooltip on the now-playing badge (planner's discretion) can show "96 kHz / 24-bit"; tree row stays text-only.
- **Bitrate-derived hi-res inference** — explicitly rejected for the GBS.FM `bitrate_kbps=1411` sentinel. Wait for caps to supply real data.
- **Backfill migration that pre-populates rate/depth from a one-shot replay sweep** — out of scope. Cache fills organically on user-driven replay.
- **Cross-codec hi-res promotion** (e.g., 320 kbps AAC outranks 64 kbps FLAC) — rejected (S-02). Lossless-over-lossy invariant preserved.
- **`Lossless+` filter chip** — only one chip ("Hi-Res only"). Revisit if the user wants to filter to lossless-or-better as a distinct browsing mode.
- **`Gst.Registry` audit at app launch** — Phase 69 owns plugin-presence concerns; Phase 70 trusts the cache once written.
- **Codec auto-correction from caps** — rejected (DS-03). Codec stays user-authored.
- **HE-AAC "HD"-style mid-tier** — rejected (D-04). No badge for lossy.

### Reviewed Todos (not folded)

None — no todos cross-referenced for Phase 70.

</deferred>

---

*Phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria*
*Context gathered: 2026-05-11*
