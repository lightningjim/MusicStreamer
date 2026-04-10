# Phase 34: Implement deferred items from phase 33 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-10
**Phase:** 34-implement-deferred-items-from-phase-33
**Areas discussed:** Fix approach, Scope

---

## Pre-discussion scope audit

Before presenting gray areas, ran the two deferred tests to verify current state:

```
uv run pytest tests/test_twitch_playback.py::test_streamlink_called_with_correct_args \
              tests/test_cookies.py::test_mpv_retry_without_cookies_on_fast_exit
→ 1 failed, 1 passed
```

**Finding:** `test_mpv_retry_without_cookies_on_fast_exit` already passes — fixed in commit b3e066b during phase 33-02 ("extend test_cookies monotonic iterator for YT watchdog"). The deferred-items.md bullet is stale.

**Remaining work:** Only `test_streamlink_called_with_correct_args` is failing. Cause: `_play_twitch` (musicstreamer/player.py:321-328) prepends `--twitch-api-header` when a Twitch OAuth token file exists (added in phase 32), but the test predates this and asserts on the bare arg list.

---

## Fix approach

| Option | Description | Selected |
|--------|-------------|----------|
| Force no-token branch | Monkeypatch TWITCH_TOKEN_PATH (or open()) to raise OSError so `_play_twitch` takes the no-token branch. Keeps the existing precise assertion and becomes deterministic regardless of local dev state. | ✓ |
| Assert on both forms | Update assertion to accept either the bare cmd or the token-prefixed cmd. Weakens the test's precision. | |
| Split into two tests | One for no-token path, one for token-present path. Adds coverage but expands scope. | |

**User's choice:** Force no-token branch (Recommended)
**Notes:** Keeps assertion precise and makes the test deterministic across dev environments. No new coverage added — phase 32 already covers OAuth behavior.

---

## Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Test fix + stale-entry cleanup | Fix twitch test, annotate deferred-items.md noting cookies test was already fixed in 33-02, commit. | ✓ |
| Add broader pytest audit | Run full pytest suite, file newly discovered failures as additional items in this phase. | |

**User's choice:** Test fix + stale-entry cleanup (Recommended)
**Notes:** Tight scope — no scope creep.

---

## Claude's Discretion

None — all decisions locked by user.

## Deferred Ideas

None — discussion stayed within phase scope.
