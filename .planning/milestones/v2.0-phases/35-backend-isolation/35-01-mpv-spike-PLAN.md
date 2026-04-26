---
phase: 35-backend-isolation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - .planning/phases/35-backend-isolation/35-SPIKE-MPV.md
  - .planning/phases/35-backend-isolation/spike/spike_mpv_drop.py
autonomous: true
requirements: [PORT-09]
must_haves:
  truths:
    - "Phase 35 deps (PySide6 6.11, yt-dlp, streamlink, platformdirs, pytest-qt) are installed and importable"
    - "The spike script runs end-to-end and classifies each of the four D-20 cases as PASS or FAIL"
    - "A decision about mpv retention is committed to 35-SPIKE-MPV.md before any player.py work begins"
  artifacts:
    - path: "pyproject.toml"
      provides: "Phase 35 runtime + test dependencies"
      contains: "PySide6"
    - path: ".planning/phases/35-backend-isolation/spike/spike_mpv_drop.py"
      provides: "Executable spike harness that exercises playbin3 against yt-dlp-resolved URLs"
      min_lines: 60
    - path: ".planning/phases/35-backend-isolation/35-SPIKE-MPV.md"
      provides: "Decision record: keep or drop mpv, with per-case PASS/FAIL notes"
      contains: "Decision:"
  key_links:
    - from: "spike/spike_mpv_drop.py"
      to: "yt_dlp.YoutubeDL"
      via: "library import, extract_info(url, download=False)"
      pattern: "yt_dlp\\.YoutubeDL"
    - from: "spike/spike_mpv_drop.py"
      to: "Gst.ElementFactory.make(\"playbin3\")"
      via: "GStreamer pipeline construction"
      pattern: "playbin3"
---

<objective>
Install Phase 35 dependencies and run the mpv-drop spike (D-20..D-23) that decides whether `player._play_youtube()` can collapse into a `playbin3` URI assignment or must retain the mpv subprocess fallback. This plan runs FIRST per D-04 because its outcome determines the shape of Plan 35-04's player.py rewrite.

Purpose: De-risk the yt-dlp library-API port by proving (or disproving) that GStreamer `playbin3` can consume yt-dlp library-resolved URLs across the four D-20 cases before touching production code.

Output:
- `pyproject.toml` updated with `PySide6>=6.11`, `yt-dlp`, `streamlink>=8.3`, `platformdirs>=4.3`, and test extra `pytest-qt>=4`.
- Dependencies installed in the active environment (verified via `python -c "import ..."`).
- `.planning/phases/35-backend-isolation/spike/spike_mpv_drop.py` — standalone script runnable as `python -m musicstreamer ... ` replacement.
- `.planning/phases/35-backend-isolation/35-SPIKE-MPV.md` — committed decision record.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/35-backend-isolation/35-CONTEXT.md
@.planning/phases/35-backend-isolation/35-RESEARCH.md
@musicstreamer/player.py
@pyproject.toml

<interfaces>
<!-- yt-dlp library shape — extracted from RESEARCH.md Pattern 6 -->
```python
import yt_dlp
opts = {
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'format': 'best[protocol^=m3u8]/best',
    # 'cookiefile': '/path/to/cookies.txt',  # optional
}
with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info(url, download=False)
# For live: info['url'] is the direct HLS/progressive URL
```

<!-- GStreamer playbin3 invocation (existing codebase pattern, player.py lines 24-34) -->
```python
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib
Gst.init(None)
pipeline = Gst.ElementFactory.make("playbin3", "player")
pipeline.set_property("video-sink", Gst.ElementFactory.make("fakesink", "fake-video"))
pipeline.set_property("uri", resolved_url)
pipeline.set_state(Gst.State.PLAYING)
# Bus wiring — see player.py lines 33-36
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Install Phase 35 dependencies and update pyproject.toml</name>
  <files>pyproject.toml</files>
  <read_first>pyproject.toml, .planning/phases/35-backend-isolation/35-RESEARCH.md (Standard Stack + Installation sections)</read_first>
  <action>
Add `PySide6>=6.11`, `yt-dlp`, `streamlink>=8.3`, `platformdirs>=4.3` to `[project] dependencies` in `pyproject.toml`. Add `pytest-qt>=4` to `[project.optional-dependencies] test` (create the section if missing; keep any existing `pytest>=9` entry). Do NOT remove `PyGObject` / `dbus-python` / `pycairo` — GStreamer gi bindings and GTK UI both remain alive this phase (D-10, Pattern 8 rationale from RESEARCH.md).

After editing, run `pip install -e .[test]` to install the new deps into the active environment. If `pip install -e` is not used by this project, run `pip install PySide6>=6.11 yt-dlp "streamlink>=8.3" "platformdirs>=4.3" "pytest-qt>=4"` directly.

Verify each import succeeds:
```
python -c "import PySide6.QtCore; import yt_dlp; import streamlink; import platformdirs; import pytestqt; print('ok')"
```
(Note: `pytest-qt` imports as `pytestqt`.)

Per D-12 rationale: the spike does NOT yet use `paths.py` — that's Plan 35-02. This task only installs deps and the spike in Task 2 uses hard-coded `~/.local/share/musicstreamer/cookies.txt` for the cookie-protected case.
  </action>
  <verify>
    <automated>python -c "import PySide6.QtCore, yt_dlp, streamlink, platformdirs, pytestqt; print('ok')"</automated>
  </verify>
  <acceptance_criteria>
- `grep -E '^\s*"?PySide6' pyproject.toml` returns a line
- `grep -E '^\s*"?yt-dlp' pyproject.toml` returns a line
- `grep -E '^\s*"?streamlink' pyproject.toml` returns a line
- `grep -E '^\s*"?platformdirs' pyproject.toml` returns a line
- `grep -E '^\s*"?pytest-qt' pyproject.toml` returns a line
- `python -c "import PySide6.QtCore, yt_dlp, streamlink, platformdirs, pytestqt"` exits 0
  </acceptance_criteria>
  <done>All five packages import cleanly; pyproject.toml updated and committed.</done>
</task>

<task type="auto">
  <name>Task 2: Write and run mpv-drop spike harness; record decision</name>
  <files>.planning/phases/35-backend-isolation/spike/spike_mpv_drop.py, .planning/phases/35-backend-isolation/35-SPIKE-MPV.md</files>
  <read_first>musicstreamer/player.py (lines 251-305, current mpv path), .planning/phases/35-backend-isolation/35-RESEARCH.md (Pattern 6 + D-20 case list)</read_first>
  <action>
Create `.planning/phases/35-backend-isolation/spike/spike_mpv_drop.py` — a standalone Python script (no package imports from `musicstreamer/`) that evaluates all four D-20 cases:

```
CASES = [
    ("a_live",      "https://www.youtube.com/@lofigirl/live",        None,   "best[protocol^=m3u8]/best"),
    ("b_hls",       "<24/7 HLS live URL>",                           None,   "best[protocol^=m3u8]/best"),
    ("c_cookies",   "<cookie-gated / age-restricted URL>",           "~/.local/share/musicstreamer/cookies.txt", "best"),
    ("d_format",    "<720p HLS live URL>",                           None,   "best[height<=720][protocol^=m3u8]"),
]
```

For each case, the script must:
1. Call `yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'skip_download': True, 'format': fmt, 'cookiefile': cookies_or_None}).extract_info(url, download=False)` on a worker thread (per RESEARCH.md pitfall — never block the main thread).
2. Extract `info['url']` (or fall back to `info['formats'][-1]['url']` for non-live).
3. Create a `playbin3` pipeline, set the resolved URL, attach `message::error` and `message::tag` handlers to a `GLib.MainLoop`, set state to `PLAYING`.
4. Wait up to 15 seconds. PASS if at least one `message::tag` OR `message::state-changed` to `PLAYING` is received with no prior `message::error`. FAIL if any `message::error` OR timeout with no state-changed-to-PLAYING.
5. Print `CASE {id}: PASS|FAIL — {one-line note}` and clean up (`pipeline.set_state(Gst.State.NULL)`, `loop.quit()`).

The script accepts URLs via CLI args (e.g. `python spike_mpv_drop.py <a_url> <b_url> <c_url> <d_url>`) — do NOT hard-code URLs; the operator (Claude) supplies working URLs at execution time based on current availability of LoFi Girl / Chillhop / etc. If any case's URL is unavailable at execution time, mark it SKIPPED and document that as a FAIL for mpv-removal purposes (skipped == insufficient evidence == retain mpv).

Run the spike. Capture stdout. Create `.planning/phases/35-backend-isolation/35-SPIKE-MPV.md` with this exact structure:

```markdown
# Phase 35 — mpv Drop Spike Result

**Ran:** <YYYY-MM-DD>
**Environment:** GStreamer <version>, yt-dlp <version>, Python <version>

## Case Results

| Case | URL | Format selector | Result | Note |
|------|-----|-----------------|--------|------|
| a — YouTube live | ... | ... | PASS/FAIL | ... |
| b — HLS manifest | ... | ... | PASS/FAIL | ... |
| c — Cookie-protected | ... | ... | PASS/FAIL | ... |
| d — Specific format | ... | ... | PASS/FAIL | ... |

## Decision

**Decision:** <DROP_MPV | KEEP_MPV>

**Rationale:** <one paragraph>

**Consequences for Plan 35-04:**
- If DROP_MPV: `_play_youtube()` is deleted. `_try_next_stream()` routes YouTube URLs through the same yt-dlp-resolve-then-`_set_uri()` path as regular HTTP streams. `PKG-05` retired (note in REQUIREMENTS.md — separate commit). Plan 35-04 does not introduce `_popen()`.
- If KEEP_MPV: `_play_youtube()` retained using `subprocess.Popen`; Plan 35-04 introduces a minimal `musicstreamer/_popen.py` helper for future PKG-03 Windows work. Failing case(s) documented above are the retention reason.
```

Commit both files (`spike_mpv_drop.py` and `35-SPIKE-MPV.md`) as the first artifacts of Phase 35 per D-23.

**Claude's discretion:** The spike is a manual/local task (not CI). Run interactively and fill in the table with real results. If the environment is genuinely unable to reach YouTube (no network, etc.), the decision MUST default to KEEP_MPV with "network unavailable, cannot validate" as the rationale.
  </action>
  <verify>
    <automated>test -f .planning/phases/35-backend-isolation/35-SPIKE-MPV.md && grep -q "^\*\*Decision:\*\* " .planning/phases/35-backend-isolation/35-SPIKE-MPV.md && test -f .planning/phases/35-backend-isolation/spike/spike_mpv_drop.py</automated>
  </verify>
  <acceptance_criteria>
- `test -f .planning/phases/35-backend-isolation/spike/spike_mpv_drop.py` exits 0
- `grep -q "yt_dlp.YoutubeDL" .planning/phases/35-backend-isolation/spike/spike_mpv_drop.py` matches
- `grep -q "playbin3" .planning/phases/35-backend-isolation/spike/spike_mpv_drop.py` matches
- `grep -q "GLib.MainLoop" .planning/phases/35-backend-isolation/spike/spike_mpv_drop.py` matches
- `grep -qE "\*\*Decision:\*\* (DROP_MPV|KEEP_MPV)" .planning/phases/35-backend-isolation/35-SPIKE-MPV.md` matches
- `grep -c "PASS\|FAIL\|SKIPPED" .planning/phases/35-backend-isolation/35-SPIKE-MPV.md` returns ≥ 4
  </acceptance_criteria>
  <done>Spike run, decision recorded in 35-SPIKE-MPV.md with explicit DROP_MPV or KEEP_MPV directive; spike script committed for reproducibility.</done>
</task>

</tasks>

<verification>
Decision gate: after this plan, `35-SPIKE-MPV.md` MUST contain an unambiguous `**Decision:** DROP_MPV` or `**Decision:** KEEP_MPV` line. Plans 35-02, 35-03 proceed regardless; Plan 35-04's player.py rewrite branches on this decision.
</verification>

<success_criteria>
1. Phase 35 dependencies (PySide6, yt-dlp, streamlink, platformdirs, pytest-qt) installed and importable.
2. `pyproject.toml` declares all five dependencies.
3. `35-SPIKE-MPV.md` committed with four case results and a binding `**Decision:**` line.
4. Spike harness script committed so the decision is reproducible.
</success_criteria>

<output>
After completion, create `.planning/phases/35-backend-isolation/35-01-SUMMARY.md` recording the spike outcome and which branch (DROP_MPV / KEEP_MPV) Plan 35-04 will take.
</output>
