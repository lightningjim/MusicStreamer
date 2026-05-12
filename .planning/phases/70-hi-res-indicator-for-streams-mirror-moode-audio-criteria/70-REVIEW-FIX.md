---
phase: 70-hi-res-indicator-for-streams-mirror-moode-audio-criteria
fixed_at: 2026-05-12T00:00:00Z
review_path: .planning/phases/70-hi-res-indicator-for-streams-mirror-moode-audio-criteria/70-REVIEW.md
iteration: 2
fix_scope: all
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 70: Code Review Fix Report

**Fixed at:** 2026-05-12
**Source review:** `.planning/phases/70-hi-res-indicator-for-streams-mirror-moode-audio-criteria/70-REVIEW.md`
**Iteration:** 2

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### IN-01: Tooltip kHz display truncates 44.1 kHz to "44 kHz"

**Files modified:** `musicstreamer/ui_qt/now_playing_panel.py`, `tests/test_now_playing_panel.py`
**Commit:** efed9b7
**Applied fix:** Replaced `rate // 1000` (integer floor division) with
`rate / 1000:g` (float with trailing-zero suppression via the `:g` format
specifier) in both tooltip branches of `_refresh_quality_badge` (the
full-caps branch and the rate-only branch). For 44100 Hz streams the
tooltip now reads "44.1 kHz" instead of "44 kHz". Standard hi-res rates
(48/96/192 kHz) are unaffected as those divide evenly.

Also added `test_quality_badge_tooltip_when_caps_known_at_cd_quality` to
`tests/test_now_playing_panel.py`, which pins `"Lossless — 44.1 kHz /
16-bit"` for a 44100 Hz / 16-bit FLAC stream. This is the exact edge
case the `:g` format is needed for; the pre-existing 96 kHz test would
pass even with the broken `// 1000` path.

### IN-02: Relative path in test makes it CWD-sensitive

**Files modified:** `tests/test_main_window_integration.py`
**Commit:** 5402027
**Applied fix:** Replaced bare `pathlib.Path("musicstreamer/player.py")`
with `(pathlib.Path(__file__).parent.parent / "musicstreamer" / "player.py")`
at line 932 of `test_main_window_integration.py`. The path is now anchored
to the test file's own location and resolves correctly regardless of the
working directory when pytest is invoked (e.g., `cd tests && pytest`, IDE
with non-standard cwd, CI runner).

---

_Fixed: 2026-05-12_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
