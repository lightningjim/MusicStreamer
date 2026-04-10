# Deferred items — Phase 33

- `tests/test_twitch_playback.py::test_streamlink_called_with_correct_args` is pre-existing failure (unrelated to FIX-07; `_play_twitch` now passes `--twitch-api-header` which this test predates). Discovered during 33-01 verification. Out of scope for this plan.
