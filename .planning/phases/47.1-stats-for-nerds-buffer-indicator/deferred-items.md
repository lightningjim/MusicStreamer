# Deferred Items — Phase 47.1

## Out-of-scope findings during plan 01 execution

### Pre-existing test failures in tests/test_player_failover.py

- `test_youtube_resolve_success_sets_uri_and_arms_failover` — fails with `ModuleNotFoundError: No module named 'yt_dlp'`
- `test_youtube_resolve_failure_emits_error_and_advances_queue` — same root cause

**Scope:** Environment/dependency issue, not caused by 47.1-01 changes. `yt_dlp` is a runtime dep the test file imports directly inside the test body; absent in this worktree's env.

**Recommended action:** Install `yt-dlp` in dev env, or guard these tests with `pytest.importorskip("yt_dlp")`. Not this phase's concern.
