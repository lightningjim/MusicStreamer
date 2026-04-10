---
phase: 34-implement-deferred-items-from-phase-33
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/test_twitch_playback.py
  - .planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md
autonomous: true
requirements:
  - PHASE-33-DEFERRED
must_haves:
  truths:
    - "tests/test_twitch_playback.py::test_streamlink_called_with_correct_args passes regardless of whether a local ~/.local/share/musicstreamer/twitch-token.txt exists"
    - "The exact-list assertion `call_args[0][0] == ['streamlink', '--stream-url', url, 'best']` remains unchanged"
    - "tests/test_cookies.py still passes (no regression)"
    - "deferred-items.md cookies bullet is annotated as resolved in 33-02 (commit b3e066b), preserved for audit trail"
  artifacts:
    - path: "tests/test_twitch_playback.py"
      provides: "Deterministic no-token-branch twitch streamlink args test"
      contains: "monkeypatch.setattr(\"musicstreamer.player.TWITCH_TOKEN_PATH\""
    - path: ".planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md"
      provides: "Audit trail with cookies item marked resolved"
      contains: "RESOLVED in 33-02"
  key_links:
    - from: "tests/test_twitch_playback.py::test_streamlink_called_with_correct_args"
      to: "musicstreamer/player.py:_play_twitch no-token branch (line 321, 329-330)"
      via: "monkeypatch TWITCH_TOKEN_PATH to nonexistent tmp_path file → open() raises OSError → except OSError: pass → bare cmd"
      pattern: "monkeypatch\\.setattr\\(\"musicstreamer\\.player\\.TWITCH_TOKEN_PATH\""
---

<objective>
Fix the one remaining failing test deferred from phase 33 and clean up the stale deferred-items.md entry.

Purpose: `tests/test_twitch_playback.py::test_streamlink_called_with_correct_args` currently fails in dev environments where a Twitch OAuth token file exists at `TWITCH_TOKEN_PATH` (added in phase 32). The test's exact-list assertion expects the bare `["streamlink", "--stream-url", url, "best"]` command, but `_play_twitch` now prepends `--twitch-api-header` when a token is present. Fix is to deterministically force the no-token branch via monkeypatch. The cookies test referenced alongside it in deferred-items.md was already fixed in commit b3e066b during phase 33-02 — that entry needs a resolved annotation only.

Output:
- Patched `tests/test_twitch_playback.py::test_streamlink_called_with_correct_args`
- Annotated `.planning/phases/33-.../deferred-items.md`
- Green `uv run pytest tests/test_twitch_playback.py tests/test_cookies.py`
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/34-implement-deferred-items-from-phase-33/34-CONTEXT.md
@.planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md
@musicstreamer/player.py
@tests/test_twitch_playback.py

<interfaces>
<!-- Relevant production code: musicstreamer/player.py:312-340 _play_twitch -->

```python
def _play_twitch(self, url: str):
    """Resolve Twitch URL via streamlink, then play HLS URI via GStreamer."""
    self._pipeline.set_state(Gst.State.NULL)
    env = os.environ.copy()
    local_bin = os.path.expanduser("~/.local/bin")
    if local_bin not in env.get("PATH", "").split(os.pathsep):
        env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")

    def _resolve():
        cmd = ["streamlink", "--stream-url", url, "best"]
        try:
            with open(TWITCH_TOKEN_PATH) as fh:
                token = fh.read().strip()
            if token:
                cmd = ["streamlink",
                       "--twitch-api-header", f"Authorization=OAuth {token}",
                       "--stream-url", url, "best"]
        except OSError:
            pass
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        ...
```

Key: setting `TWITCH_TOKEN_PATH` to a path that does not exist causes `open()` to raise `FileNotFoundError` (a subclass of `OSError`), hits the `except OSError: pass`, and the bare `cmd` is used.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Fix test_streamlink_called_with_correct_args to force no-token branch</name>
  <files>tests/test_twitch_playback.py</files>
  <read_first>
    - tests/test_twitch_playback.py (lines 106-142 — the test under repair plus adjacent subprocess-test patterns)
    - musicstreamer/player.py (lines 312-340 — _play_twitch, specifically the TWITCH_TOKEN_PATH open() and OSError branch)
  </read_first>
  <behavior>
    - After patch: test passes whether or not `~/.local/share/musicstreamer/twitch-token.txt` exists on the developer's machine
    - The assertion at line 139 (`call_args[0][0] == ["streamlink", "--stream-url", url, "best"]`) remains byte-for-byte identical
    - `mock_run.assert_called_once()` and the `capture_output` / `text` kwarg assertions still pass
    - No new test is added — this is a single existing-test fix
  </behavior>
  <action>
Modify `tests/test_twitch_playback.py` ONLY — do not touch `musicstreamer/player.py`.

1. Change the test function signature from:
   ```python
   def test_streamlink_called_with_correct_args():
   ```
   to:
   ```python
   def test_streamlink_called_with_correct_args(tmp_path, monkeypatch):
   ```

2. Immediately after the docstring (and before `p = make_player()`), add the monkeypatch that forces the no-token branch in `_play_twitch`:
   ```python
   # Force no-token branch: point TWITCH_TOKEN_PATH at a file that does not exist
   # so open() raises FileNotFoundError (subclass of OSError) and _play_twitch
   # falls through to the bare `["streamlink", "--stream-url", url, "best"]` cmd.
   # Without this, a dev-local ~/.local/share/musicstreamer/twitch-token.txt would
   # cause streamlink to be invoked with --twitch-api-header (phase 32 behavior).
   monkeypatch.setattr(
       "musicstreamer.player.TWITCH_TOKEN_PATH",
       str(tmp_path / "nonexistent-twitch-token.txt"),
   )
   ```

3. Leave EVERYTHING ELSE in the test body unchanged. In particular:
   - The exact assertion `assert call_args[0][0] == ["streamlink", "--stream-url", url, "best"]` on line 139 must remain EXACTLY as-is (per D-02 — no weakening to partial matching).
   - The `mock_run.assert_called_once()` and `capture_output`/`text` kwarg assertions stay.
   - The `patch("musicstreamer.player.subprocess.run", ...)`, `patch("musicstreamer.player.threading.Thread", ...)`, and `patch("musicstreamer.player.GLib")` block is preserved.
   - The `capture_thread` helper stays.

4. Do NOT add a second test for the token-present branch (D-03 — out of scope).
5. Do NOT modify any other test in the file.
  </action>
  <verify>
    <automated>uv run pytest tests/test_twitch_playback.py::test_streamlink_called_with_correct_args -x -v</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "def test_streamlink_called_with_correct_args(tmp_path, monkeypatch):" tests/test_twitch_playback.py` returns exactly one match
    - `grep -n 'monkeypatch.setattr("musicstreamer.player.TWITCH_TOKEN_PATH"' tests/test_twitch_playback.py` returns exactly one match
    - `grep -n 'assert call_args\[0\]\[0\] == \["streamlink", "--stream-url", url, "best"\]' tests/test_twitch_playback.py` returns exactly one match (assertion unchanged)
    - `uv run pytest tests/test_twitch_playback.py::test_streamlink_called_with_correct_args -x` exits 0
  </acceptance_criteria>
  <done>The previously failing twitch streamlink args test passes deterministically, independent of any local Twitch token file, with the original exact-list assertion intact.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Annotate stale cookies entry in phase 33 deferred-items.md</name>
  <files>.planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md</files>
  <read_first>
    - .planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md (current contents)
  </read_first>
  <action>
Edit `.planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md`.

1. Leave the twitch-test bullet (the first bullet) unchanged — it is being addressed by Task 1 of this phase and will be closed out in the phase SUMMARY.

2. For the `tests/test_cookies.py::test_mpv_retry_without_cookies_on_fast_exit` bullet (the second bullet), prepend `**RESOLVED in 33-02 (commit b3e066b):**` to the start of the bullet and append a trailing sentence noting the resolution. The bullet should read (preserving the original rationale for audit trail):

   ```
   - **RESOLVED in 33-02 (commit b3e066b):** `tests/test_cookies.py::test_mpv_retry_without_cookies_on_fast_exit` fails after 33-01 due to the new `time.monotonic()` call inside `_yt_poll_cb` (FIX-07 gate). The test's `monkeypatch.setattr("time.monotonic", ...)` provides an iterator with only 2 values; the gate now consumes more, raising `StopIteration`. Discovered during 33-02 verification. Root cause is a test fixture that needs to be widened (e.g., `itertools.count(0.0, 1.0)` or include additional values). Not a regression in production code — 33-01's 4 new tests in `tests/test_player_failover.py` cover the gate behavior correctly. Fixed in commit b3e066b by widening the monotonic iterator to `itertools.count(start=0.0, step=1.0)`.
   ```

3. Also fix the stray `/gs` prefix on line 1 (the file currently starts with `/gs# Deferred items — Phase 33`) — correct it to `# Deferred items — Phase 33`.

4. Do not add any other entries, do not delete either bullet.
  </action>
  <verify>
    <automated>grep -q "RESOLVED in 33-02 (commit b3e066b)" .planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md &amp;&amp; head -1 .planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md | grep -qx "# Deferred items — Phase 33"</automated>
  </verify>
  <acceptance_criteria>
    - First line of file is exactly `# Deferred items — Phase 33` (no `/gs` prefix)
    - File contains the literal string `**RESOLVED in 33-02 (commit b3e066b):**`
    - File contains the literal string `tests/test_cookies.py::test_mpv_retry_without_cookies_on_fast_exit` (preserved)
    - File still contains the twitch bullet referencing `tests/test_twitch_playback.py::test_streamlink_called_with_correct_args`
    - File has exactly 2 bullet items (both preserved for audit)
  </acceptance_criteria>
  <done>Cookies bullet is annotated as resolved with commit reference; twitch bullet preserved; stray `/gs` prefix removed; both bullets remain for audit trail.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Full regression verification</name>
  <files></files>
  <read_first>
    - tests/test_twitch_playback.py (post-Task-1)
    - tests/test_cookies.py
  </read_first>
  <action>
Run the verification command specified in CONTEXT.md D-06:

```bash
uv run pytest tests/test_twitch_playback.py tests/test_cookies.py -v
```

All tests in both files must pass. If any test fails:
1. If it is `test_streamlink_called_with_correct_args` → Task 1 is incomplete, revisit the monkeypatch.
2. If it is a test in `tests/test_cookies.py` → STOP. This would indicate a regression outside phase 34 scope; report the failure and do not attempt to fix it within this phase.
3. If it is an unrelated test in `tests/test_twitch_playback.py` → STOP and report; Task 1 was scoped to a single test and should not have touched others.

No code changes in this task — it is a pure verification gate.
  </action>
  <verify>
    <automated>uv run pytest tests/test_twitch_playback.py tests/test_cookies.py</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest tests/test_twitch_playback.py tests/test_cookies.py` exits 0
    - `test_streamlink_called_with_correct_args` is in the passed list
    - `test_mpv_retry_without_cookies_on_fast_exit` is in the passed list
    - Zero failures, zero errors across both files
  </acceptance_criteria>
  <done>Both test files are fully green; phase 34 scope is fully closed.</done>
</task>

</tasks>

<verification>
- `uv run pytest tests/test_twitch_playback.py tests/test_cookies.py` exits 0 (D-06)
- `grep -c "^- " .planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md` returns 2 (both bullets preserved)
- `grep "RESOLVED in 33-02" .planning/phases/33-fix-yt-video-playback-delay-until-all-streams-failed-toast/deferred-items.md` matches
- `musicstreamer/player.py` is unchanged (`git diff --stat musicstreamer/player.py` is empty)
</verification>

<success_criteria>
- `test_streamlink_called_with_correct_args` passes deterministically regardless of local Twitch token file presence
- Exact-list assertion at line 139 is unchanged
- `tests/test_cookies.py` still fully passes
- deferred-items.md has cookies bullet annotated as resolved in 33-02 with commit b3e066b reference
- No production code changes
- No new tests added; no other tests modified
</success_criteria>

<output>
After completion, create `.planning/phases/34-implement-deferred-items-from-phase-33/34-01-SUMMARY.md` documenting:
- Before/after of the patched test (signature + monkeypatch line)
- Before/after of the deferred-items.md cookies bullet
- Full pytest output for `tests/test_twitch_playback.py tests/test_cookies.py`
- Confirmation that musicstreamer/player.py is untouched
</output>
