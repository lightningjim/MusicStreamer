# Phase 34: Implement deferred items from phase 33 - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Resolve the two test items deferred from phase 33. Scope audit during discuss revealed:
- `tests/test_cookies.py::test_mpv_retry_without_cookies_on_fast_exit` — **already fixed** in commit b3e066b during phase 33-02 (monotonic iterator widened to `itertools.count(start=0.0, step=1.0)`). Deferred-items.md entry is stale.
- `tests/test_twitch_playback.py::test_streamlink_called_with_correct_args` — **still failing**. Test predates phase 32's OAuth header addition; `_play_twitch` now prepends `--twitch-api-header` when a Twitch token file exists (`musicstreamer/player.py:321-328`).

Phase delivers: (1) fix the twitch test, (2) clean up the stale deferred-items.md entry. Nothing else.

</domain>

<decisions>
## Implementation Decisions

### Test Fix Approach
- **D-01:** Fix `test_streamlink_called_with_correct_args` by forcing the no-token branch in `_play_twitch`. Monkeypatch so that opening `TWITCH_TOKEN_PATH` raises `OSError` (e.g., point `musicstreamer.player.TWITCH_TOKEN_PATH` to a nonexistent path under `tmp_path`, or patch `builtins.open` for that path). Test then deterministically hits the bare `["streamlink", "--stream-url", url, "best"]` command path regardless of the developer's local token file.
- **D-02:** Keep the existing assertion (`call_args[0][0] == ["streamlink", "--stream-url", url, "best"]`). Do not weaken it to partial matching.
- **D-03:** Do not add a second test for the token-present branch. Out of scope — phase 32 already covers OAuth behavior.

### Scope
- **D-04:** Scope is tight: one test fix + deferred-items.md cleanup. No broader pytest audit.
- **D-05:** Update `.planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md`: strike/annotate the cookies-test bullet as resolved in 33-02 (commit b3e066b). Leave for historical audit trail.

### Verification
- **D-06:** `uv run pytest tests/test_twitch_playback.py tests/test_cookies.py` must pass after the fix. No other regression targets.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Deferred items source
- `.planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md` — Original deferred list from phase 33. Cookies bullet is stale; twitch bullet is the real work.

### Production code under test
- `musicstreamer/player.py:312-330` — `_play_twitch` implementation. The branch at lines 321-328 (no token → bare cmd; token present → prepend `--twitch-api-header`) is what the test must deterministically target.

### Test under repair
- `tests/test_twitch_playback.py:110-142` — `test_streamlink_called_with_correct_args`. Current assertion at line 139 fails because local `~/.config/musicstreamer/twitch_token` (or whatever `TWITCH_TOKEN_PATH` resolves to) exists in dev env.

### Related phase contexts (background only)
- `.planning/phases/31-integrate-twitch-streaming-via-streamlink/31-CONTEXT.md` — original Twitch integration
- `.planning/phases/32-add-twitch-authentication-via-streamlink-oauth-token/32-CONTEXT.md` — added the `--twitch-api-header` prepending that broke this test

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/test_twitch_playback.py` already has `make_player()` helper and `monkeypatch` fixture patterns in adjacent tests — no new helpers needed.
- `monkeypatch.setattr("musicstreamer.player.TWITCH_TOKEN_PATH", str(tmp_path / "nonexistent"))` is the cleanest no-token forcing — the `except OSError: pass` branch at `player.py:329-330` will handle the missing file.

### Established Patterns
- Other tests in the file already use `patch("musicstreamer.player.subprocess.run", ...)` and `patch("musicstreamer.player.threading.Thread", ...)` with target capture — fix should preserve that pattern exactly.

### Integration Points
- Fix is localized to `tests/test_twitch_playback.py`. No production code touched.

</code_context>

<specifics>
## Specific Ideas

- User-confirmed preferred approach: force the no-token branch (not partial matching, not test splitting). Rationale: keeps assertion precise and makes the test deterministic across dev environments.
- Developer profile: tight scope, no scope creep — this is a ~10-line test patch plus a deferred-items.md annotation.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. User explicitly rejected broadening to a full pytest audit.

</deferred>

---

*Phase: 34-implement-deferred-items-from-phase-33*
*Context gathered: 2026-04-10*
