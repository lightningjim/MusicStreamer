# Phase 79: Fix YouTube 'stream exhausted' when launched via desktop app (works via pipx/dev script) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-16
**Phase:** 79-fix-youtube-stream-exhausted-when-launched-via-desktop-app-w
**Areas discussed:** Root cause, Fix mechanism, Plumbing route, yt_import parity, Error visibility

---

## Root cause confirmation

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — that matches | Symptom is YouTube-only failure under .desktop; HTTP/Twitch streams work fine; pipx-from-terminal works fine. | ✓ |
| Symptom matches, root cause not confirmed yet | I've seen 'Stream exhausted' on YT under .desktop, but I haven't bisected — phase should start with a diagnostic step to confirm before shipping a fix. | |
| Different symptom — let me describe | The bug surface or repro isn't what was described. | |

**User's choice:** Yes — that matches.
**Notes:** Root cause confirmed: .desktop-launched MusicStreamer can't find Node via PATH; `_which_node_version_manager_fallback` finds it for the warning dialog but the resolved path is never threaded to yt-dlp, which passes `{"path": None}` and does its own (failing) PATH lookup.

---

## Fix mechanism — Q1: which mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Pass resolved path into yt-dlp opts | Change `js_runtimes={'node':{'path': None}}` to `{'node':{'path': node_runtime.path}}`. Surgical, single-call-site change, no side effects on process env. | ✓ |
| Augment os.environ['PATH'] at startup | Prepend node's bin dir to PATH after check_node(). Fixes yt-dlp AND any other subprocess (streamlink, oauth_helper). Broader blast radius. | |
| Both — explicit path + PATH augmentation | Belt-and-braces: pass path into opts AND prepend to PATH. Most defensive, hardest to reason about. | |

**User's choice:** Pass resolved path into yt-dlp opts.
**Notes:** Surgical fix preferred over process-env mutation.

---

## Fix mechanism — Q2: behavior when Node is absent

| Option | Description | Selected |
|--------|-------------|----------|
| Pass `{'path': None}` as today — let yt-dlp try | yt-dlp does its own PATH lookup. JS-requiring streams fail (as today); JS-free streams still resolve. No regression on absent branch. | ✓ |
| Omit js_runtimes entirely when path is None | Don't tell yt-dlp about node at all. May behave differently from `{'path': None}`. | |
| Investigate both in research, pick later | Researcher confirms what yt-dlp does with `{'path': None}` vs omitted js_runtimes when Node is absent. | |

**User's choice:** Pass `{'path': None}` as today.
**Notes:** User pointed out (correctly) that yt-dlp doesn't always need the JS runtime — some YouTube paths resolve without n-challenge solving. Short-circuiting on absent-Node would regress those cases. Preserve current absent-Node behavior.

---

## Fix mechanism — Q3: platform scope

| Option | Description | Selected |
|--------|-------------|----------|
| Both — same behavior on Linux and Windows | NodeRuntime.path is already platform-aware. Single code path. | ✓ |
| Linux only — gate behind sys.platform.startswith('linux') | Reported bug is Linux .desktop. Windows path lookup already works. | |
| Investigate Windows behavior in research first | Researcher checks yt-dlp on Windows. | |

**User's choice:** Both — same behavior on Linux and Windows.

---

## Fix mechanism — Q4: regression test bar

| Option | Description | Selected |
|--------|-------------|----------|
| Unit test: `opts['js_runtimes']['node']['path']` equals the resolved abs path | Monkeypatch `yt_dlp.YoutubeDL` to record opts; pure unit, no network. | ✓ |
| Add the unit test PLUS an env-PATH integration test | Also test with stripped PATH. Belt-and-braces. | |
| Live UAT only | Manual UAT step in phase verification, no unit test. | |

**User's choice:** Unit test.

---

## Plumbing route — Q1: how does Player learn node_runtime.path

| Option | Description | Selected |
|--------|-------------|----------|
| Player ctor kwarg — `Player(node_runtime=...)` | Mirror MainWindow's existing kwarg. Explicit, testable, DI-friendly. | ✓ |
| Module-level cache in `runtime_check` | `runtime_check.get_node_path()` returns memoized. Hidden global state. | |
| Player calls `check_node()` itself in `_youtube_resolve_worker` | Lazy detection. Duplicates startup probe. | |

**User's choice:** Player ctor kwarg.

---

## Plumbing route — Q2: default value

| Option | Description | Selected |
|--------|-------------|----------|
| `node_runtime=None` default; opts uses `{'path': None}` fallback | Backwards-compat for _run_smoke + existing tests. | ✓ |
| Required kwarg | Forces every caller to think about Node. Breaks tests + smoke. | |
| Default to `runtime_check.check_node()` if None | Auto-detect on init. Hidden state objection. | |

**User's choice:** None default with fallback.

---

## yt_import parity — Q1: fix scope

| Option | Description | Selected |
|--------|-------------|----------|
| Fix in this phase — share the opts builder | Extract opts dict construction into shared helper. Both call sites use it. | ✓ |
| Fix in this phase, inline at both call sites | Duplicate fix; risk of drift. | |
| Leave for a follow-up phase | Ship known bug on the playlist-import path. | |

**User's choice:** Share the opts builder.

---

## yt_import parity — Q2: helper location

| Option | Description | Selected |
|--------|-------------|----------|
| New `musicstreamer/yt_dlp_opts.py` module | Single-purpose; matches focused-tiny-module pattern. | ✓ |
| Add to `musicstreamer/yt_import.py` | Reuse existing module. Import asymmetry. | |
| Inline at both sites (no extraction) | Revert helper premise. | |

**User's choice:** New module.

---

## yt_import parity — Q3: helper scope

| Option | Description | Selected |
|--------|-------------|----------|
| Strictly js_runtimes — minimal helper | Helper only owns js_runtimes; other opts stay at call sites. | ✓ |
| Full opts dict — helper returns complete opts | Centralize everything; couples scan and resolve. | |
| Two helpers — build_resolve_opts + build_scan_opts | Cleanest separation; small duplication. | |

**User's choice:** Strictly js_runtimes.

---

## yt_import parity — Q4: scan_playlist API

| Option | Description | Selected |
|--------|-------------|----------|
| `scan_playlist` grows a `node_runtime` kwarg | Mirror Player. ImportDialog threads through. | ✓ |
| `scan_playlist` calls `check_node()` internally | Encapsulates detail; couples to runtime_check. | |
| Module-level cache in `yt_dlp_opts.py` | Lazily reads runtime_check. Hidden state. | |

**User's choice:** node_runtime kwarg.

---

## Error visibility — Q1: toast behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Keep current toast machinery; no new branch | After fix, the "found via fallback but yt-dlp rejected it" case shouldn't happen. Existing "Install Node.js" toast covers the absent case. | ✓ |
| Add a new toast for "Node resolved but yt-dlp rejected it" | Defensive future-regression catcher. | |
| Log-only enhancement — INFO line on YT play attempts | No new toast. Future debugging easier. | |

**User's choice:** Keep current toast machinery. (User also confirmed they want the INFO log addition separately in Q2 below.)

---

## Error visibility — Q2: INFO log

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — add one INFO line per YT play | `_youtube_resolve_worker` logs `youtube resolve: node_path=<abs\|None>`. | ✓ |
| Log at DEBUG only | Available with -v; not in default log. | |
| No logging change | Behavior fix only. | |

**User's choice:** INFO line per YT play.

---

## Claude's Discretion

- Helper function name (`build_js_runtimes` is the working name; planner may pick a variant).
- Where the import dialog threads `node_runtime` (constructor kwarg vs parent attribute access).
- Test fixture for `NodeRuntime` (inline literals vs `@pytest.fixture`).
- Whether to add a source-grep drift-guard test for `"path": None` inside `js_runtimes` literals.

## Deferred Ideas

- `os.environ['PATH']` augmentation at startup — revisit if a parallel bug surfaces for streamlink under .desktop.
- `yt_dlp_opts.py` expansion to own more opts — revisit when a third yt-dlp call site appears.
- Drift-guard test for `"path": None` inside `js_runtimes` literals — preemptive add at Claude's Discretion or revisit if the bug recurs.
- Parallel env-diff investigation for other "works in pipx but not via .desktop" bugs — file a generic audit phase if/when they surface.
- PyInstaller / Windows installer changes — out of scope; Phase 47 already bundles Node on Windows. Revisit if Windows installer layout changes break NodeRuntime.path resolution.
