# Phase 70: Hi-res indicator for streams (mirror moOde audio criteria) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria
**Areas discussed:** Hi-res criteria definition, Source of truth, Display surfaces, Filter & sort integration

---

## Hi-res criteria definition

### Q1 — How many badge tiers should the indicator support?

| Option | Description | Selected |
|--------|-------------|----------|
| Two tiers: Lossless + Hi-Res | 'Lossless' = any lossless codec at ≤16-bit/48 kHz; 'Hi-Res' = lossless + (>48 kHz OR >16-bit). Mirrors moOde's visual distinction. | ✓ |
| Three tiers: Lossless + Hi-Res + DSD | Adds DSD; internet radio essentially never carries DSD. | |
| One tier: Hi-Res only (strict moOde) | Single badge gated on >48 kHz OR >16-bit. CD-quality FLAC would not light up. | |
| One tier: Lossless only | Single 'Lossless' badge for any FLAC/ALAC. Diverges from moOde vocabulary. | |

**Notes:** Two-tier picks up GBS.FM/SomaFM FLAC as Lossless while keeping room for a higher-rate FLAC to upgrade to Hi-Res.

### Q2 — When codec is lossless (FLAC) but sample-rate/bit-depth are unknown, what does the badge show?

| Option | Description | Selected |
|--------|-------------|----------|
| Default to 'Lossless' | Safe default; first replay caps can upgrade to Hi-Res. | ✓ |
| Show nothing until sample-rate is known | Conservative; FLAC stations show blank pre-cache. | |
| Default to 'Hi-Res' (optimistic) | Risks over-claiming. | |

**Notes:** Default-to-Lossless plus runtime upgrade gives immediate visibility on FLAC stations and avoids over-claiming Hi-Res.

### Q3 — Badge visual style

| Option | Description | Selected |
|--------|-------------|----------|
| Text label, theme-colored | Plain text 'LOSSLESS' / 'HI-RES' on palette(highlight) bg — Phase 68 LIVE badge pattern. | ✓ |
| Text label + tier-specific colors | Different colors for the two tiers; introduces a non-theme color token. | |
| Tiny icon + tooltip | Glyph + tooltip; compact but lower scan-ability. | |

**Notes:** Reuse of the LIVE-badge QSS gives free Phase 66 theme compatibility.

---

## Source of truth

### Q1 — Where does the sample-rate / bit-depth data come from?

| Option | Description | Selected |
|--------|-------------|----------|
| Runtime GStreamer caps only | Read live caps after PLAYING; no schema change; badge only-while-playing. | |
| Runtime caps + persistent cache (per-stream) | Caps + new sample_rate_hz / bit_depth columns on station_streams. Tree row badge after first replay. | ✓ |
| Codec-only inference (no rate/depth) | FLAC → Lossless; never reaches Hi-Res. | |
| User checkbox in EditStationDialog | Manual per-stream flag. Rejected pattern. | |

**Notes:** Persistent cache is needed for the tree-row badge and the 'Hi-Res only' filter chip to work without playback.

### Q2 — When does the player extract caps and write them to the cache?

| Option | Description | Selected |
|--------|-------------|----------|
| First buffer on audio sink, write-once per stream | Hook audio-sink pad; first negotiated caps after PLAYING; persist if empty OR differs. | ✓ |
| Every playback — always re-read and overwrite | Catches HLS adaptive downgrades; adds DB writes per play. | |
| First buffer, in-memory only — no DB write | Loses cross-session cache benefit. | |

**Notes:** Idempotent if cache already matches.

### Q3 — Settings export/import ZIP round-trip

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — include in export, forward-compat parse on import | Mirrors Phase 47.3 bitrate_kbps pattern. | ✓ |
| No — cache is local-only, re-detected on first play in new install | Loses cache on fresh install. | |

**Notes:** Forward-compat `int(stream.get(KEY, 0) or 0)` idiom keeps old ZIPs compatible.

### Q4 — Codec drift when runtime caps disagree with the user-set `codec`

| Option | Description | Selected |
|--------|-------------|----------|
| Leave codec alone, only update rate/depth | Codec stays user/import-authored; rate/depth are runtime-only. | ✓ |
| Update codec to match caps | Risk: stream picker labels and sort order shift unexpectedly. | |
| Update only if codec field is empty | Fill-when-missing middle ground. | |

**Notes:** Codec ownership stays with the user/import flow.

---

## Display surfaces

### Q1 — Where should the LOSSLESS / HI-RES badge actually show up? (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| Now-playing panel (next to LIVE badge) | Sibling QLabel in icy_row, same QSS as LIVE. | ✓ |
| Station tree row (delegate) | Inline mini pill on each row; tier = best across station's streams. | ✓ |
| Stream picker dropdown (per-stream) | Per-stream tier in the QComboBox. | ✓ |
| EditStationDialog streams table (column) | Read-only 'Quality' column in the streams table. | ✓ |

**Notes:** All four surfaces ship in this phase.

### Q2 — Tree-row badge for multi-stream stations

| Option | Description | Selected |
|--------|-------------|----------|
| Best tier across all streams | If any stream is Hi-Res, show HI-RES; else if any Lossless, show LOSSLESS. | ✓ |
| Tier of the failover-preferred (top-ranked) stream | Could under-represent capability when ordering puts lower tier first. | |
| Tier of the currently-playing stream (only when station active) | Other rows show nothing. | |

**Notes:** Surfaces capability ("this station CAN deliver Hi-Res"), not failover default.

### Q3 — Tree-row badge placement

| Option | Description | Selected |
|--------|-------------|----------|
| Right side, before the star column | Inline mini-badge between station name/logo and the star icon, painted by the delegate. | ✓ |
| Suffix on the station name | ' · HI-RES' on the displayed name; cheaper but less visually distinct. | |
| Below station name as subtitle | Two-row delegate; increases row height. | |

**Notes:** Delegate strategy mirrors the star-paint pattern from Phase 54.

---

## Filter & sort integration

### Q1 — Filter chip

| Option | Description | Selected |
|--------|-------------|----------|
| Add 'Hi-Res only' filter chip (parallel to 'Live now') | New _hi_res_chip near station_list_panel.py:271. Hidden until library has any Hi-Res. | ✓ |
| Two chips: 'Lossless+' and 'Hi-Res only' | More granular; chip-row clutter. | |
| No new filter chip | Display-only. | |

**Notes:** Visibility gate analogous to Phase 68's `audioaddict_listen_key` gate.

### Q2 — Stream ordering

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — add rate/depth as secondary sort within same codec | Within same codec_rank, prefer higher sample-rate / bit-depth. | ✓ |
| Yes — promote ANY hi-res stream above lossless, even cross-codec | Could put hi-res AAC above CD-FLAC. Violates lossless-over-lossy. | |
| No — leave order_streams unchanged | Display-only. | |

**Notes:** Sort key becomes `(-quality_rank, -codec_rank, -bitrate_kbps, -sample_rate_hz, -bit_depth, position)`.

---

## Wrap-up

User selected "I'm ready for context" — no additional gray areas requested before CONTEXT.md write. `--chain` flag is set; the next workflow step auto-advances to `/gsd-plan-phase 70 --chain`.

## Claude's Discretion

- Exact GStreamer API entry point for caps extraction (pad notify::caps vs audio-tags message vs static-pad query).
- Module location of `classify_tier` (new `musicstreamer/hi_res.py` vs extension of `stream_ordering.py`).
- Exact new column names (`sample_rate_hz` / `bit_depth` vs `audio_rate_hz` / `audio_bit_depth`).
- Tree-delegate strategy (extend `station_star_delegate.py` vs new sibling delegate).
- Quality-map shape on the proxy (`dict[int, str]` vs `dict[int, set[str]]`).
- Tooltip on the now-playing badge ("96 kHz / 24-bit") — yes/no.
- EditStationDialog "Quality" column index (last, before existing columns, etc.).

## Deferred Ideas

- Manual "This is Hi-Res" override checkbox in EditStationDialog.
- DSD tier.
- Numeric rate/depth readout on the tree row (tooltip only on now-playing if at all).
- Bitrate-derived hi-res inference (GBS.FM 1411 sentinel stays at face value).
- Backfill migration that pre-populates rate/depth from a one-shot replay sweep.
- Cross-codec hi-res promotion.
- 'Lossless+' filter chip.
- `Gst.Registry` audit at app launch.
- Codec auto-correction from caps.
- HE-AAC "HD" mid-tier.
