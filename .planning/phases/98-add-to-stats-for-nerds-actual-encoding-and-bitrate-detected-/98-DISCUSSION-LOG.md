# Phase 98: Add to Stats for Nerds — Actual Encoding & Bitrate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-24
**Phase:** 98-add-to-stats-for-nerds-actual-encoding-and-bitrate-detected
**Areas discussed:** Detected vs expected, Which fields to show, Bitrate liveness, Unknown / fallback states

---

## Detected vs expected

| Option | Description | Selected |
|--------|-------------|----------|
| Detected + expected, flag mismatch | Show both, visually flag when they differ | ✓ |
| Detected only | Just show actual detected values, no comparison | |
| Detected, expected only on mismatch | Append expected inline only when it differs | |

**User's choice:** Detected + expected, flag mismatch
**Notes:** Best fulfills the roadmap goal "validate you are playing what you expect." Expected sourced from declared `Stream.codec` / `Stream.bitrate_kbps` (locked without asking — only available source).

### Mismatch flagging (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Color the value (amber) | Warning color on the detected value when mismatched | ✓ |
| Warning icon + tooltip | ⚠ icon + tooltip explaining detected vs expected | |
| Both color + icon | Amber value AND ⚠ icon | |

**User's choice:** Color the value (amber)
**Notes:** Fits the existing plain muted-label stats aesthetic; color only.

---

## Which fields to show

| Option | Description | Selected |
|--------|-------------|----------|
| Encoding + bitrate only | Literal roadmap scope, two rows | |
| Encoding, bitrate, sample-rate, bit-depth | Full actual-format block (4 rows) | ✓ |
| Encoding + bitrate + sample-rate | Three rows, skip bit-depth | |

**User's choice:** Encoding, bitrate, sample-rate, bit-depth
**Notes:** Sample-rate/bit-depth already detected (Phase 70) so cheap to surface. Clarified that sample-rate/bit-depth become detected-only rows (no independent declared source to compare); only encoding/bitrate get the comparison + amber flag.

---

## Bitrate liveness

| Option | Description | Selected |
|--------|-------------|----------|
| One-shot snapshot at preroll | Capture once when stream stabilizes (Phase 70 pattern) | ✓ |
| Live-update as tags arrive | Update row on every bitrate tag (VBR jitter) | |
| Snapshot, prefer nominal bitrate | One-shot preferring nominal/average tag | |

**User's choice:** One-shot snapshot at preroll
**Notes:** Matches existing one-shot caps detection; avoids jitter. Nominal-vs-instantaneous left as soft discretion (user chose plain one-shot, not the prefer-nominal variant).

---

## Unknown / fallback states

| Option | Description | Selected |
|--------|-------------|----------|
| Show em-dash placeholder | Row always present, value '—' when undetected | ✓ |
| Hide the row entirely | Only show rows when a value was detected | |
| 'detecting…' then dash | Transient state then '—' | |

**User's choice:** Show em-dash placeholder
**Notes:** Stable panel layout across stations; no mismatch flag when expected also unknown.

---

## Claude's Discretion

- GStreamer detection mechanism for codec/bitrate (tags vs caps) — researcher/planner.
- VBR nominal-vs-instantaneous bitrate choice for the snapshot.
- Bitrate mismatch tolerance (avoid flagging 320 vs 319 kbps false positives).
- Exact row labels, ordering, and detected+expected formatting within the cell.

## Deferred Ideas

- Live/continuous VBR bitrate updating — rejected in favor of one-shot snapshot; revisit if a real-time telemetry feature is wanted.
- Reviewed todo `pls-codec-bitrate-url-fallback` (score 0.9) — already resolved as FIX-PLS-01 (Phase 92), concerns declared (not detected) values. Not folded.
