# Phase 18: YouTube Thumbnail 16:9 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-04-05
**Phase:** 18-youtube-thumbnail-16-9
**Mode:** discuss
**Areas analyzed:** 16:9 Detection, Logo Slot behavior

## Assumptions Going In

### Art Slot Architecture
| Assumption | Confidence | Evidence |
|------------|-----------|----------|
| Both logo and cover slots use GdkPixbuf.new_from_file_at_scale(160,160,False) — squashes 16:9 | Confident | main_window.py lines ~692, ~707 |
| Slot size stays 160×160 (no widening) | Confident | STATE.md pre-decision |
| YouTube stations have no ICY, so cover slot stays on station_art_path throughout playback | Confident | main_window.py _on_cover_art gated on ICY title |

## Gray Areas Discussed

### 16:9 Detection
- **Question:** URL pattern vs. image aspect ratio inspection
- **User choice:** URL pattern (youtube.com / youtu.be check)
- **Reason:** Simpler, no file I/O, consistent with existing YT checks in codebase

### Logo Slot
- **Question:** Apply CONTAIN to left logo slot too, or only right cover slot?
- **User choice:** Both slots — symmetric treatment
- **Reason:** Both slots show the same station_art_path for YouTube stations

## Corrections Made

No corrections — both choices matched recommended options.
