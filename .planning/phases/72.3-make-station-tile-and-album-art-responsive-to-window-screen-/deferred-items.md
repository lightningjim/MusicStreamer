# Phase 72.3 — Deferred Items

## Pre-existing test collateral from Plan 02 cover-default bump (out-of-scope for Plan 03)

The Plan 02 D-05 invariant bumped `cover_label.setFixedSize(160, 160) -> (180, 180)`
at construction time. The `tests/test_phase72_now_playing_panel.py` /
`tests/test_phase72_1_stream_picker_reflow.py` / `tests/test_phase72_integration.py`
sibling suites were updated alongside Plan 02 (all 22 pass), but the older
`tests/test_now_playing_panel.py` was NOT updated and now has 3 stale assertions
hard-coding the old `QSize(160, 160)` cover default:

- `tests/test_now_playing_panel.py:152` — `assert panel.cover_label.size() == QSize(160, 160)` (test_panel_construction)
- `tests/test_now_playing_panel.py:335` — `assert panel.cover_label.size() == QSize(160, 160)` (test_cover_art_ready_signal_missing_path_falls_back)
- `tests/test_now_playing_panel.py:348` — `assert panel.cover_label.size() == QSize(160, 160), "cover slot must stay 160x160"` (test_youtube_thumbnail_letterbox)

Plus a logo size assertion that already matched the new default (180,180) — no
change needed.

These three asserts were broken by Plan 02's deliberate cover-default bump
(72.3-CONTEXT.md D-05 equal-at-every-tier). They are out-of-scope for Plan 03
per executor Rule "Only auto-fix issues DIRECTLY caused by the current task's
changes. Pre-existing warnings... in unrelated files are out of scope."

**Suggested follow-up:** Update the three asserts to `QSize(180, 180)` (the new
medium-tier default). All four sibling test files that the Plan 03 success
criteria explicitly named — `tests/test_phase72_3_responsive_art.py`,
`tests/test_phase72_1_stream_picker_reflow.py`,
`tests/test_phase72_now_playing_panel.py`, `tests/test_phase72_integration.py` —
ALL PASS at Plan 03 completion (35/35).

## Pre-existing environment errors

Multiple `tests/test_player_*.py`, `tests/test_twitch_*.py`,
`tests/test_windows_palette.py`, `tests/test_activation_token_strip.py`,
`tests/test_cookies.py` fail with `ModuleNotFoundError: No module named 'gi'`.
This is a worktree `.venv` issue (PyGObject / GStreamer Python bindings not
installed in this Claude Code worktree environment); pre-existing and unrelated
to Phase 72.3.
