# Phase 56: Windows DI.fm + SMTC Start Menu - Research

**Researched:** 2026-05-02
**Domain:** URL boundary rewrite + Windows shell AUMID/SMTC binding
**Confidence:** HIGH

## Summary

This phase has two halves with very different research profiles. The DI.fm half (WIN-01) is a small, well-understood pure-string transform — every relevant constraint is already documented in CONTEXT.md, the spike-findings skill, and existing `url_helpers.py` patterns; research confirms the design decisions are sound and identifies the exact test surfaces to extend. The SMTC half (WIN-02) is shell-mediated and inherently empirical: the in-process AUMID and shortcut AUMID wiring are known-correct in code yet "Unknown app" still appears in practice, so the deliverable is a tight diagnostic procedure that runs on the Win11 VM rather than a code refactor. Research confirmed Microsoft's canonical Get-StartApps + Shell.Application AppsFolder pattern (overrides the original D-08 step 1 `ExtendedProperty` snippet), surfaced the existence of `AppUserModelToastActivatorCLSID` as a *separate* property that does NOT need adding, and located the registry path Windows actually consults for AUMID display name resolution.

**Primary recommendation:** Ship the DI.fm rewrite first (small, fully testable on Linux CI, near-zero risk). Then run the SMTC diagnostic on the Win11 VM in the order in CONTEXT.md D-08 — but substitute Microsoft's documented `Get-StartApps` cmdlet for the brittle `ExtendedProperty('System.AppUserModel.ID')` snippet in step 1, and use the `Shell.Application.NameSpace('shell:::{4234d49b-...}')` AppsFolder pattern as the authoritative AUMID readback source. If the diagnostic reveals an environmental cause (D-09 #1 or #2), no code change ships — only a README update + UAT confirmation. If it reveals a wiring bug, patch the offending file. Both halves close the phase together via UAT on the Win11 VM.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| URL classification (`_aa_slug_from_url`) | Module: `musicstreamer/url_helpers.py` (pure logic) | — | Established convention — every URL classifier is a pure free function in this module with zero Qt/GLib coupling |
| URL normalization (`aa_normalize_stream_url`) | Module: `musicstreamer/url_helpers.py` (pure logic) | — | Same convention as above; planner should NOT push this into player.py or aa_import.py |
| URI-boundary rewrite invocation | Backend: `musicstreamer/player.py::_set_uri` | — | D-01 "single funnel" — every URL handed to playbin3 already passes through here, so the helper call lives at the funnel, not at each upstream call site |
| Windows AUMID process registration | OS-API: `musicstreamer/__main__.py::_set_windows_aumid` (ctypes → shell32) | — | Already correct, verified by Phase 43.1 readback; this phase only verifies, does not refactor |
| Start Menu shortcut AUMID property | Installer: `packaging/windows/MusicStreamer.iss [Icons]` | — | Inno Setup `AppUserModelID:` directive is the only supported way to set this property at install time; declared at line 71 |
| SMTC overlay binding (display name resolution) | OS-shell: Windows Explorer (consumes shortcut + process AUMID) | — | Shell-mediated — neither Python nor the installer can force this; the only lever is "is the shortcut registered with the matching AUMID" |
| Diagnostic readback (PowerShell) | OS-tooling: PowerShell + `Get-StartApps` / `Shell.Application` AppsFolder | — | Microsoft's documented method; project never ships any of this code — it's UAT instrumentation only |

**Interpretation:** No tier crossings are introduced this phase. WIN-01 is one new pure function in an existing module + one one-line call from `_set_uri`. WIN-02 is diagnose-only on the OS-shell tier; if a fix is needed it's in either `__main__.py` (process AUMID) or `MusicStreamer.iss` (shortcut AUMID) — both are already-claimed responsibilities of those files.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**WIN-01 (DI.fm HTTPS→HTTP rewrite):**
- **D-01:** Fix site = `_set_uri()` in `musicstreamer/player.py`. Every URL handed to `playbin3` is normalized at this single funnel. No DB schema change. No `aa_import.py` change. No migration step.
- **D-02:** Detection via existing `musicstreamer/url_helpers.py::_aa_slug_from_url(url) == "di"`. Reuse — single-source `NETWORKS` table.
- **D-03:** Always rewrite, regardless of platform. Unconditional `https://` → `http://` swap when slug check fires. NO `sys.platform == "win32"` guard.
- **D-04:** New helper `aa_normalize_stream_url(url: str) -> str` lives in `musicstreamer/url_helpers.py` next to `_aa_slug_from_url` / `_is_aa_url`. Pure string transform. `_set_uri` becomes one line: `uri = aa_normalize_stream_url(uri)`.

**WIN-01 silent rewrite (Claude's discretion in CONTEXT but treated as locked):**
- **D-05:** Silent rewrite — single `logging.debug` line at the rewrite site, no toast, no INFO log spam.
- **D-06:** Idempotent — already-`http://` DI.fm URLs pass through unchanged. Non-DI.fm URLs pass through unchanged. Empty/malformed URLs pass through.

**WIN-02 (SMTC Start Menu shortcut + AUMID):**
- **D-07:** Diagnose before changing code. Wiring already exists (`__main__.py:99-125` + `MusicStreamer.iss:71`). First action: Win11 VM diagnostic, NOT speculative refactoring.
- **D-08:** Diagnostic checklist (run on the VM, in order):
  1. Read shortcut AUMID property
  2. Launch via Start Menu, read in-process AUMID via `GetCurrentProcessExplicitAppUserModelID`, confirm match
  3. Inspect live SMTC binding via Settings → Notifications & actions OR `Get-StartApps`
  4. Force fresh install (uninstall → delete `%LOCALAPPDATA%\Programs\MusicStreamer` → delete `%APPDATA%\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk` → reinstall)
- **D-09:** Likely root-cause shortlist: (1) stale shortcut from earlier installer iteration, (2) launching via `python -m musicstreamer` or post-install Run checkbox bypasses AUMID binding, (3) AUMID-string drift between `__main__.py` and `MusicStreamer.iss`.
- **D-10:** Code change scope decided post-diagnostic. Environmental cause → docs only. Wiring bug → patch + re-UAT. Phase gated on overlay reading "MusicStreamer".

**Verification:**
- **D-11:** Win11 VM UAT, no automated SMTC tests. URL helper + `_set_uri` integration get pytest unit + player-level tests on Linux CI.
- **D-12:** DI.fm UAT trial set: at least one DI.fm channel (DI.fm Lounge) plays from fresh AA import + at least one plays from settings-import ZIP roundtrip (Phase 42). Both must reach audible audio + ICY title display.

### Claude's Discretion

- Helper name (`aa_normalize_stream_url` proposed; planner can adjust to `normalize_aa_stream_url` for symmetry with other `aa_*` helpers).
- Whether helper is also called from `aa_import.py` insert site (defensive belt-and-suspenders) vs. only `_set_uri` (single source of truth) — lean strongly toward `_set_uri` only.
- Phrasing of README / packaging note about "launch via Start Menu shortcut" path.
- Whether build-time AUMID-string drift guard ships (pytest reading `.iss` vs. `build.ps1` ripgrep vs. YAGNI). Probably YAGNI for a single-author project; planner may include or skip.

### Deferred Ideas (OUT OF SCOPE)

- Per-network HTTPS workarounds for non-DI.fm AA networks (RadioTunes, JazzRadio, ClassicalRadio, RockRadio, ZenRadio). Only DI.fm is known-broken (Phase 43).
- Try-then-fallback retry logic preserving HTTPS in case DI.fm fixes their server. Overkill given Phase 43's stable finding.
- Migrating existing DB rows (rewriting stored `https://` URLs). Rewrite happens at the play-time URI boundary; stored data is irrelevant.
- Code signing / MSIX / auto-update. Still deferred to v2.1+ per Phase 44.
- WIN-03 (audio pause/resume glitch + ignored volume) — Phase 57.
- WIN-04 (`test_thumbnail_from_in_memory_stream` AsyncMock fix) — Phase 57.
- BUG-08 (Linux WM display name) — Phase 61.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WIN-01 | DI.fm premium streams play on Windows via a chosen HTTPS-fallback policy | New helper `aa_normalize_stream_url` in `url_helpers.py` + one-line wire-in at `player.py::_set_uri` line 484. Detection helper (`_aa_slug_from_url`) and pattern (pure helper + boundary funnel) both exist. Test surface (`test_player_failover.py` + `test_aa_url_detection.py`) accommodates both layers without new fixtures. |
| WIN-02 | SMTC overlay shows "MusicStreamer" via Start Menu shortcut carrying matching AUMID | Wiring already exists (`__main__.py::_set_windows_aumid` at line 99 + `MusicStreamer.iss:71` `AppUserModelID` directive). Diagnostic procedure ships as part of phase deliverable; root cause identified on VM determines whether code change is needed. Microsoft `Get-StartApps` is the authoritative readback. |

## Standard Stack

This phase introduces **no new dependencies**. All work uses libraries already pinned in `pyproject.toml`.

### Core (already pinned)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `urllib.parse` | 3.10+ | URL parsing in `_aa_slug_from_url` and the new helper if needed | Already used throughout `url_helpers.py` for path/scheme manipulation |
| Python stdlib `logging` | 3.10+ | `logging.debug` at the rewrite site (D-05) | Project convention — `_log = logging.getLogger(__name__)` already in `aa_import.py`, `player.py`, etc. |
| Python stdlib `ctypes` | 3.10+ | Already in use in `__main__.py:115` for `SetCurrentProcessExplicitAppUserModelID`. Required for any in-process AUMID readback if a Python smoke test is preferred over PowerShell. | Phase 43.1 already established the explicit `LPCWSTR` argtype pattern; the readback variant uses the same idiom. [VERIFIED: musicstreamer/__main__.py:115-125] |
| pytest 9+ + pytest-qt 4+ | per pyproject.toml [project.optional-dependencies].test | Unit + player integration tests | Already in use across all `tests/test_player_*.py` files |

### Supporting (Windows-only diagnostic surface)
| Tool | Source | Purpose | When to Use |
|------|--------|---------|-------------|
| PowerShell `Get-StartApps` | Built into Windows 10/11 (StartLayout module) | Authoritative AUMID readback for ALL Start Menu shortcuts | D-08 step 1 — preferred over `ExtendedProperty('System.AppUserModel.ID')` because Microsoft documents this as THE method [CITED: learn.microsoft.com/en-us/windows/configuration/store/find-aumid] |
| PowerShell `Shell.Application` AppsFolder COM | `(New-Object -ComObject Shell.Application).NameSpace('shell:::{4234d49b-0245-4df3-b780-3893943456e1}').Items()` | Per-app AUMID lookup (filterable by friendly name) | D-08 step 3 — the canonical Microsoft sample. Returns `name` (display name shell will use) and `path` (the AUMID itself). [CITED: learn.microsoft.com/en-us/windows/configuration/store/find-aumid] |
| PowerShell + .NET `Marshal.PtrToStringUni` | Built into PowerShell + .NET runtime | In-process AUMID readback via `GetCurrentProcessExplicitAppUserModelID` from a separate console | D-08 step 2 — confirms the running process AUMID matches the shortcut AUMID |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `Get-StartApps` for AUMID readback | `(New-Object -ComObject Shell.Application).Namespace($startMenuPath).ParseName('MusicStreamer.lnk').ExtendedProperty('System.AppUserModel.ID')` (CONTEXT.md D-08 step 1) | Original snippet works but is brittle on per-user installs (path may differ; LNK file may not be findable by name; Windows shell-property cache may return stale value). `Get-StartApps` queries the live registry/cache the shell ACTUALLY uses for SMTC binding, so it's the single source of truth. **Recommend swapping the D-08 step 1 snippet to `Get-StartApps \| Where-Object Name -like 'MusicStreamer*'`**. |
| Pure-Python ctypes readback (D-08 step 2) | PowerShell + Marshal.PtrToStringUni inline | Either works. PowerShell version is one-liner-able; Python version is a 6-line script using `shell32.GetCurrentProcessExplicitAppUserModelID(byref(ptr))` + `ctypes.wstring_at(ptr.value)` + `ole32.CoTaskMemFree(ptr)`. Lean PowerShell — fewer files, no need to ship a one-shot diagnostic into the repo. |
| Inno Setup `AppUserModelToastActivatorCLSID` (D-09 #3 contingency) | Add to `[Icons]` block | **NOT applicable to this phase.** This Inno Setup property is for *toast notification activator CLSID*, NOT for SMTC display name. SMTC display name resolves from the shortcut's name + matching AUMID alone. Adding this would be cargo-culting. [VERIFIED: jrsoftware.org/files/is6.1-whatsnew.htm] |

**No `pip install` or `npm install` needed.** Phase ships zero new third-party dependencies.

**Version verification (performed 2026-05-02):**
- `python --version` → 3.10+ already required (pyproject `requires-python = ">=3.10"`).
- `pytest`/`pytest-qt` → already pinned in `[project.optional-dependencies].test`.
- All Windows tooling is OS-built-in.

## Architecture Patterns

### System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          WIN-01: DI.fm Rewrite Path                       │
│                                                                          │
│  Stream sources                                                          │
│  ─────────────                                                           │
│  AA import (aa_import.py)  ─┐                                            │
│  Settings ZIP import       ─┤                                            │
│  Manual edit (EditDialog)  ─┼──► SQLite DB (stations + station_streams)  │
│  PLS auto-resolve (Phase58)─┘     │                                      │
│                                    │                                      │
│  Playback request                  │                                      │
│  ────────────────                  ▼                                      │
│  MainWindow → Player.play(station) ─► _try_next_stream                   │
│                                            │                              │
│                                            ▼                              │
│        ┌──── url contains 'youtube.com' / 'youtu.be' ──► _play_youtube ─►│
│        ├──── url contains 'twitch.tv' ────────────────► _play_twitch  ─►│
│        └──── else ────────────────────────────────────► _set_uri(url)   │
│                                                              │            │
│  YT/Twitch resolved (worker thread → queued signal) ────────┤            │
│                                                              │            │
│              ┌───────────────────────────────────────────────▼─────────┐ │
│              │  _set_uri(uri):                                         │ │
│              │    uri = aa_normalize_stream_url(uri)  ◄── NEW (D-04)  │ │
│              │    pipeline.set_state(NULL)                             │ │
│              │    pipeline.set_property("uri", uri)                    │ │
│              │    pipeline.set_state(PLAYING)                          │ │
│              └─────────────────────────┬───────────────────────────────┘ │
│                                        │                                  │
│                                        ▼                                  │
│                                  GStreamer playbin3                       │
│                                                                          │
│  aa_normalize_stream_url(url):                                           │
│    slug = _aa_slug_from_url(url)                                         │
│    if slug == "di" and url.startswith("https://"):                       │
│        return "http://" + url[len("https://"):]   # log.debug only       │
│    return url                                                            │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                       WIN-02: SMTC AUMID Binding                          │
│                                                                          │
│  Install time (Inno Setup)                                               │
│  ─────────────────────────                                                │
│  iscc MusicStreamer.iss                                                  │
│      │                                                                   │
│      ▼                                                                   │
│  [Icons] line 68-71:                                                     │
│    Name: {userprograms}\MusicStreamer  ◄─── DISPLAY NAME source for SMTC│
│    Filename: {app}\MusicStreamer.exe                                     │
│    AppUserModelID: org.lightningjim.MusicStreamer  ◄── AUMID property    │
│      │                                                                   │
│      ▼                                                                   │
│  Shortcut written to:                                                    │
│    %APPDATA%\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk     │
│      │                                                                   │
│      ▼                                                                   │
│  Windows shell indexes shortcut → registers AUMID + display name in      │
│  AppsFolder (queryable via Shell.Application + 'shell:::{4234d49b-...}') │
│                                                                          │
│  Runtime (process startup)                                               │
│  ──────────────────────────                                              │
│  __main__.py::_run_gui (line 130)                                        │
│      │                                                                   │
│      ▼                                                                   │
│  _set_windows_aumid("org.lightningjim.MusicStreamer")  ◄── BEFORE QApp! │
│      │                                                                   │
│      ▼                                                                   │
│  shell32.SetCurrentProcessExplicitAppUserModelID(LPCWSTR aumid)         │
│      │                                                                   │
│      ▼                                                                   │
│  QApplication() → MainWindow.show() → first window creation              │
│      │                                                                   │
│      ▼                                                                   │
│  Windows binds process AUMID to all windows                              │
│                                                                          │
│  Playback                                                                │
│  ────────                                                                │
│  Player.play() → SMTC backend (smtc.py via media_keys factory)           │
│      │                                                                   │
│      ▼                                                                   │
│  smtc.publish_metadata() → SystemMediaTransportControls.DisplayUpdater   │
│      │                                                                   │
│      ▼                                                                   │
│  Windows Shell looks up app friendly name by process AUMID               │
│      │                                                                   │
│      ▼                                                                   │
│  ┌───────────── if AUMID matches a registered Start Menu shortcut ────┐ │
│  │   → SMTC overlay shows shortcut's friendly name ("MusicStreamer")  │ │
│  │ else                                                               │ │
│  │   → SMTC overlay shows "Unknown app"  ◄── current symptom          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### Recommended File Layout (no new files)

```
musicstreamer/
├── url_helpers.py        # ADD: aa_normalize_stream_url() free function
├── player.py             # MODIFY (1 line): _set_uri prepends aa_normalize_stream_url
├── __main__.py           # NO CHANGE (verify only)
└── ...

packaging/windows/
├── MusicStreamer.iss     # NO CHANGE expected (verify only)
└── README.md             # POSSIBLE: append "launch via Start Menu shortcut" reminder

tests/
├── test_aa_url_detection.py   # ADD: 6-8 tests for aa_normalize_stream_url
└── test_player_failover.py    # ADD: 1-2 tests asserting _set_uri normalizes
                                #      (extends existing test_player_failover.py
                                #       harness — uses make_player + patch.object)
```

### Pattern 1: Pure URL Helper in `url_helpers.py`
**What:** New free function with same shape as `_aa_slug_from_url`, `_is_aa_url`, `_aa_channel_key_from_url`.
**When to use:** ALL URL classification + transformation work in this codebase.
**Example (proposed implementation):**
```python
# Source: extending musicstreamer/url_helpers.py established convention

import logging
_log = logging.getLogger(__name__)

def aa_normalize_stream_url(url: str) -> str:
    """Phase 56 / WIN-01: rewrite DI.fm 'https://' URLs to 'http://'.

    DI.fm rejects HTTPS server-side (TLS handshake succeeds, then
    souphttpsrc returns 'streaming stopped, reason error (-5)'). Confirmed
    in Phase 43. Workaround applied at the player URI boundary so every
    set_uri call (manual edit, AA import, settings ZIP, multi-stream
    failover, YouTube/Twitch resolved) is normalized.

    Idempotent (D-06): non-DI.fm URLs, already-http URLs, empty/malformed
    inputs all pass through unchanged. Cross-platform (D-03): no
    sys.platform branch — DI.fm rejects HTTPS for everyone.

    Returns the input unchanged when no rewrite is needed.
    """
    if not url:
        return url
    # Cheap prefix check first — avoid urlparse cost on the common path.
    if not url.startswith("https://"):
        return url
    # Slug check uses the same canonical NETWORKS table everything else does.
    if _aa_slug_from_url(url) != "di":
        return url
    rewritten = "http://" + url[len("https://"):]
    _log.debug("aa_normalize_stream_url: rewrote DI.fm HTTPS to HTTP: %s -> %s", url, rewritten)
    return rewritten
```

**Idempotency proof (recommended pytest assertion):**
```python
def test_aa_normalize_idempotent():
    url = "https://prem1.di.fm/lounge?listen_key=abc"
    once = aa_normalize_stream_url(url)
    twice = aa_normalize_stream_url(once)
    assert twice == once  # second call must be a no-op
```

### Pattern 2: One-Line Boundary Funnel in `_set_uri`
**What:** Single transform at the URI boundary; matches Phase 47-01's "transform once at the boundary" pattern.
**When to use:** Whenever the same URL would otherwise have to be rewritten at every upstream call site.
**Example:**
```python
# Source: musicstreamer/player.py line 484 (proposed minimal-diff)

def _set_uri(self, uri: str) -> None:
    uri = aa_normalize_stream_url(uri)  # Phase 56 / WIN-01 (D-01)
    self._pipeline.set_state(Gst.State.NULL)
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
    self._pipeline.set_property("uri", uri)
    self._pipeline.set_state(Gst.State.PLAYING)
```

Import added at top of `player.py`: `from musicstreamer.url_helpers import aa_normalize_stream_url`.

### Pattern 3: Existing Test Harness for `_set_uri` Mocking
**What:** All player tests already mock `_set_uri` via `patch.object(player, "_set_uri")` — see `tests/test_player_failover.py:66, 83, 94, 118, 137, 180, 214, 231, 262, 351, 373, 404, 414, 432, 435`.
**When to use:** Existing failover/play tests stay GREEN unchanged because they mock `_set_uri` AND THE MOCK INTERCEPTS BEFORE THE NEW NORMALIZATION RUNS. The new test for normalization MUST avoid this mock and instead assert on `pipeline.set_property("uri", ...)` calls OR call `_set_uri` directly with mocked pipeline.

**Recommended new test pattern (player-level integration):**
```python
# tests/test_player_failover.py (or new tests/test_player_di_normalization.py)

def test_set_uri_normalizes_difm_https_to_http(qtbot):
    """WIN-01: _set_uri rewrites DI.fm https:// to http:// before
    handing the URL to playbin3 (D-01)."""
    p = make_player(qtbot)
    # Don't patch _set_uri — exercise it for real, but watch the
    # underlying pipeline.set_property call.
    p._set_uri("https://prem1.di.fm/lounge?listen_key=abc")
    # The MagicMock pipeline records calls.
    p._pipeline.set_property.assert_any_call(
        "uri", "http://prem1.di.fm/lounge?listen_key=abc"
    )

def test_set_uri_passes_through_non_difm(qtbot):
    """Non-DI.fm URLs must pass through _set_uri unchanged (D-06 idempotency)."""
    p = make_player(qtbot)
    p._set_uri("https://ice4.somafm.com/dronezone-256-mp3")
    p._pipeline.set_property.assert_any_call(
        "uri", "https://ice4.somafm.com/dronezone-256-mp3"
    )
```

The existing `make_player` helper in `test_player_failover.py:16-27` constructs a player whose pipeline is a `MagicMock` — `set_property` calls are captured but execute no real GStreamer state changes. No new fixture needed.

### Anti-Patterns to Avoid

- **Branching the rewrite on `sys.platform == "win32"`.** Phase 43 finding is server-side: DI.fm rejects HTTPS for everyone. A platform branch creates "works on my Linux" surprises and a phantom code path that never executes on CI. CONTEXT.md D-03 locks this; planner must not introduce a guard.
- **Calling the helper at every upstream call site (`play()`, `_on_youtube_resolved`, `_on_twitch_resolved`, `_try_next_stream`) instead of at `_set_uri`.** D-01 explicitly chose the funnel; redundant call sites multiply the surface for future regressions where someone adds a fifth caller and forgets the helper.
- **Adding a DB migration to rewrite stored DI.fm URLs.** Out of scope per CONTEXT.md `<domain>` "Out of scope". Stored URLs stay `https://` so a future user who exports the DB sees the original; only `playbin3` ever sees `http://`.
- **Adding `AppUserModelToastActivatorCLSID` to the `[Icons]` block as a "fix" for Unknown app.** That property is for toast notification activator CLSID, NOT for SMTC display name. Adding it is cargo-culting and won't help. [VERIFIED: jrsoftware.org/files/is6.1-whatsnew.htm — explicit statement that this parameter is for toast notifications]
- **Setting `System.AppUserModel.RelaunchDisplayNameResource` on the shortcut.** That property controls the *taskbar pin / Jump List relaunch* display name, NOT the SMTC overlay name. Out of scope and won't address WIN-02. [VERIFIED: learn.microsoft.com/en-us/windows/win32/properties/props-system-appusermodel-relaunchdisplaynameresource]
- **Refactoring `_set_windows_aumid` "to be safer".** It's already correct per Phase 43.1 verification. CONTEXT.md D-07 explicitly says diagnose first; speculative refactoring would be deviation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL slug detection | A new regex over DI.fm hostnames | `_aa_slug_from_url(url) == "di"` (already in `url_helpers.py:123`) | NETWORKS table is the single source of truth; a parallel regex would drift |
| URL parse for `https://` → `http://` swap | A regex like `re.sub(r'^https://', 'http://', url)` | Plain `if url.startswith("https://"): return "http://" + url[len("https://"):]` | One-line stdlib, no regex compile cost, no accidental greedy match |
| AUMID readback on Windows | A new ctypes script that reads the registry | `Get-StartApps` PowerShell cmdlet | Microsoft documents this as THE method [CITED: learn.microsoft.com/en-us/windows/configuration/store/find-aumid]; querying the registry directly is undocumented and may miss desktop-app AUMIDs |
| AUMID-string drift detection | Custom build-time script reading both files | Either skip (YAGNI for single-author project) OR a 5-line pytest that reads `__main__.py` + `MusicStreamer.iss` and asserts the literal matches | Inno Setup has no direct support for shared constants between `.iss` and Python; YAGNI is the lowest-risk option |
| In-process AUMID readback | New Python module | One-line PowerShell using `[System.Runtime.InteropServices.Marshal]::PtrToStringUni` over `GetCurrentProcessExplicitAppUserModelID` | Diagnostic-only, never shipped — adding a Python module would commit code for one-off VM use |

**Key insight:** This phase is mostly about NOT building things — the wiring exists, the helpers exist, the Microsoft tooling exists. The deliverable is mostly verification work + one tiny pure function.

## Runtime State Inventory

(Required because this phase can be characterized as "string rewrite + verification of OS-level registration." Most categories are negative — nothing stored — but the discipline of explicit answers prevents missing the one thing that matters.)

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | DI.fm URLs in SQLite (`station_streams.url`) — many will be `https://...di.fm/...` from prior AA imports. **ZIP exports (Phase 42) carry the same URLs verbatim.** | **None — by design.** D-01 rewrites at play time only. Stored data stays `https://` so DB inspection / cross-machine ZIP transfer / future Linux usage all see the original URL. The rewrite is server-bug workaround, not data correctness. |
| Live service config | None — no external service holds DI.fm URL config for MusicStreamer. AA listen_key lives in DB but is unaffected by HTTP/HTTPS rewrite. | None — verified by reviewing `aa_import.py` (no external service registration). |
| OS-registered state | (1) Windows Start Menu shortcut at `%APPDATA%\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk` — embeds `AppUserModelID="org.lightningjim.MusicStreamer"` written by Inno Setup. (2) Windows Shell AppsFolder index — derived from the shortcut on registration. (3) Process explicit AUMID — set at runtime by `_set_windows_aumid`. | **WIN-02 entire focus.** D-08 step 4 force-deletes the LNK + reinstalls precisely because Windows caches the shortcut's AUMID property and "reinstall over the top" doesn't always re-read it. After a fresh install the shortcut is recreated; on Windows shell launch, the new AUMID + display name register. |
| Secrets / env vars | None — the AUMID literal `org.lightningjim.MusicStreamer` is hardcoded in two places: `__main__.py:99` (default param of `_set_windows_aumid`) and `MusicStreamer.iss:71`. Not a secret, not env-driven. | If D-09 #3 (string drift) materializes, both files must be updated in lockstep. Optional discretionary smoke-test guard (Claude's discretion in CONTEXT.md). |
| Build artifacts | (1) `dist/MusicStreamer/` PyInstaller onedir bundle. (2) `dist/installer/MusicStreamer-*.exe` Inno Setup output. Neither carries a stale DI.fm URL or stale AUMID — both are rebuilt fresh on every `build.ps1` run from current source. | None unless D-08 step 4 reveals that Inno Setup's reinstall-over-top doesn't refresh the LNK file's `AppUserModelID` property — in which case force-delete-then-reinstall (already in D-08 step 4) is the workaround. |

**Canonical question:** *After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered?*
**Answer:** The Windows Start Menu shortcut (LNK file) and the AppsFolder shell cache. These survive a "reinstall over top" and require either an `iscc` re-emit (which Inno Setup does on every install) OR a manual delete-then-reinstall to be sure. D-08 step 4 already prescribes the manual path. WIN-01 has no equivalent caching — DB rows are intentionally not migrated.

## Common Pitfalls

### Pitfall 1: Existing tests that mock `_set_uri` won't catch the new normalization
**What goes wrong:** All 14+ tests in `test_player_failover.py` use `with patch.object(p, "_set_uri")` — the mock intercepts the call BEFORE the new normalization line runs. A buggy `aa_normalize_stream_url` (e.g., always returns the input unchanged) would not be caught by any existing test.
**Why it happens:** The mock replaces the entire method body; the line `uri = aa_normalize_stream_url(uri)` never executes when `_set_uri` is mocked.
**How to avoid:** New player-level tests must NOT mock `_set_uri`. Instead, they should call `_set_uri` directly (or trigger a code path that invokes the real `_set_uri`) and assert on the underlying `_pipeline.set_property("uri", ...)` MagicMock call. The conftest autouse `_stub_bus_bridge` already prevents real GLib threads, and `make_player` already replaces `_pipeline` with a MagicMock, so this is safe.
**Warning signs:** A new pytest case passes when `aa_normalize_stream_url` is stubbed to `return url`.

### Pitfall 2: Adding the helper to `aa_import.py` insert path "for safety" creates two normalization sites
**What goes wrong:** A future contributor sees the helper in `aa_import.py` and copies the call to `settings_export.py` import path "for symmetry," then someone modifies the rewrite logic in `aa_import.py` only and the two sites diverge.
**Why it happens:** Defense-in-depth instinct. Looks safer; actually harder to maintain.
**How to avoid:** CONTEXT.md Claude's Discretion explicitly recommends "single source of truth" — only `_set_uri` calls the helper. Document at the helper site that this is the only call site and any other call site is YAGNI.
**Warning signs:** Anyone proposing a `aa_normalize_stream_url` call outside `player.py::_set_uri`.

### Pitfall 3: PowerShell `ExtendedProperty('System.AppUserModel.ID')` returns null on per-user installs
**What goes wrong:** CONTEXT.md D-08 step 1 prescribes `(New-Object -ComObject Shell.Application).Namespace("$env:APPDATA\Microsoft\Windows\Start Menu\Programs").ParseName('MusicStreamer.lnk').ExtendedProperty('System.AppUserModel.ID')`. On Windows 11, this can return `$null` even when the property IS set on the LNK, because the Shell.Application property bag exposes a different property name set than the underlying IShellLink IPropertyStore.
**Why it happens:** Shell.Application's property store is a façade over a subset of NTFS extended properties; `System.AppUserModel.ID` may be in the underlying IPropertyStore but not exposed by `ExtendedProperty`.
**How to avoid:** Use `Get-StartApps | Where-Object Name -like 'MusicStreamer*'` instead — Microsoft's documented method, returns the AUMID Windows actually uses for shell binding. [CITED: learn.microsoft.com/en-us/powershell/module/startlayout/get-startapps]. If `Get-StartApps` doesn't list the app at all, that's the smoking gun: the shortcut isn't registered as a Start Menu app and SMTC will never see it.
**Warning signs:** The original snippet returns `$null` while `Get-StartApps` shows the app correctly.

### Pitfall 4: Bare `python -m musicstreamer` on the VM during UAT yields false negative
**What goes wrong:** Tester launches via Miniforge Prompt or the IDE during VM UAT, sees "Unknown app," concludes the fix didn't work — but `python -m musicstreamer` deliberately bypasses the shortcut-AUMID binding (no registered Start Menu shortcut for `python.exe`).
**Why it happens:** Phase 43.1 finding documents this. Easy to forget mid-UAT.
**How to avoid:** UAT script MUST include "Launch via Start Menu shortcut, NOT via `python -m musicstreamer`" as the very first step. Re-state this in the README diff (CONTEXT.md Claude's Discretion item).
**Warning signs:** Test output says "still Unknown app" but the launch command shows `python -m` rather than the Start Menu invocation.

### Pitfall 5: Reinstall over top doesn't always rewrite the LNK file's AUMID property
**What goes wrong:** A previous installer version (or hand-modified shortcut) wrote the LNK file with no `AppUserModelID` property. Reinstalling the new installer over top sees the file already exists, may skip the rewrite, and the SMTC continues to read no AUMID → falls back to "Unknown app".
**Why it happens:** Inno Setup's `[Icons]` section uses `flags: ignoreversion recursesubdirs` — which preserves shortcuts unless they need updating. The detection of "needs updating" is fragile for LNK property bags.
**How to avoid:** D-08 step 4 force-deletes the LNK (`Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk"`) before reinstalling. This is the canonical fix; no installer change should be the first response.
**Warning signs:** `Get-StartApps` shows MusicStreamer with empty AppID, or with an old AUMID, after a fresh installer run.

### Pitfall 6: AUMID-string drift between `__main__.py` and `MusicStreamer.iss` is silent until UAT
**What goes wrong:** Future copy-paste typo in either file. SetCurrentProcessExplicitAppUserModelID succeeds with the new string; shortcut still has the old string; SMTC sees mismatch and falls back to "Unknown app". No build-time error, no test failure on Linux.
**Why it happens:** Two literal strings in two different files with no shared source.
**How to avoid:** CONTEXT.md Claude's Discretion suggests an optional pytest guard. If shipped, the test pattern is:
```python
# tests/test_aumid_string_parity.py (optional)
import re
from pathlib import Path

def test_aumid_string_parity():
    """D-09 #3: __main__.py and MusicStreamer.iss must declare the same AUMID."""
    main_py = Path("musicstreamer/__main__.py").read_text()
    iss = Path("packaging/windows/MusicStreamer.iss").read_text()
    main_match = re.search(r'app_id:\s*str\s*=\s*"([^"]+)"', main_py)
    iss_match = re.search(r'AppUserModelID:\s*"([^"]+)"', iss)
    assert main_match and iss_match
    assert main_match.group(1) == iss_match.group(1), (
        f"AUMID drift: __main__.py='{main_match.group(1)}' "
        f"iss='{iss_match.group(1)}'"
    )
```
This is a 10-line test, runs on Linux CI, has no Windows dependency. **Recommendation: include it.** The risk is real (the strings are visible across files but unlinked) and the mitigation cost is minimal.
**Warning signs:** Manual edit to either AUMID literal without immediate manual edit to the other.

## Code Examples

### Example 1: The complete helper (verbatim drop-in for `url_helpers.py`)

```python
# Source: extending musicstreamer/url_helpers.py, follows _aa_slug_from_url convention

import logging
_log = logging.getLogger(__name__)

def aa_normalize_stream_url(url: str) -> str:
    """Phase 56 / WIN-01 / D-04: rewrite DI.fm 'https://' URLs to 'http://'.

    DI.fm rejects HTTPS server-side (Phase 43 finding: TLS handshake
    succeeds, then souphttpsrc returns 'streaming stopped, reason error
    (-5)'). Workaround applied at the Player URI boundary so every
    set_uri call goes through normalization regardless of source.

    Idempotent (D-06):
    - Empty/None-ish input → returns input unchanged
    - Non-https:// input → returns input unchanged (already http://, file://, etc.)
    - Non-DI.fm input → returns input unchanged
    - DI.fm https:// → returns http:// equivalent

    Cross-platform (D-03): no sys.platform branch — DI.fm rejects HTTPS
    for everyone, not just Windows.
    """
    if not url:
        return url
    if not url.startswith("https://"):
        return url
    if _aa_slug_from_url(url) != "di":
        return url
    rewritten = "http://" + url[len("https://"):]
    _log.debug("aa_normalize_stream_url: DI.fm https→http: %s -> %s", url, rewritten)
    return rewritten
```

### Example 2: Wire-in at `player.py::_set_uri` (minimal-diff)

```python
# Source: musicstreamer/player.py line 484, current state:
def _set_uri(self, uri: str) -> None:
    self._pipeline.set_state(Gst.State.NULL)
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
    self._pipeline.set_property("uri", uri)
    self._pipeline.set_state(Gst.State.PLAYING)

# Becomes (one-line addition):
def _set_uri(self, uri: str) -> None:
    uri = aa_normalize_stream_url(uri)  # WIN-01 / D-01: DI.fm HTTPS→HTTP at URI funnel
    self._pipeline.set_state(Gst.State.NULL)
    self._pipeline.get_state(Gst.CLOCK_TIME_NONE)
    self._pipeline.set_property("uri", uri)
    self._pipeline.set_state(Gst.State.PLAYING)
```

Plus one import at the top of `player.py`:
```python
from musicstreamer.url_helpers import aa_normalize_stream_url
```

### Example 3: Win11 VM diagnostic procedure (concretized from D-08)

```powershell
# === Step 1: Read the AUMID Windows actually sees on the Start Menu shortcut. ===
# CANONICAL Microsoft method (supersedes the ExtendedProperty snippet in CONTEXT.md
# which can return null on per-user installs — see Pitfall #3).
Get-StartApps | Where-Object Name -like 'MusicStreamer*'

# Expected output:
#   Name           AppID
#   ----           -----
#   MusicStreamer  org.lightningjim.MusicStreamer
#
# Failure modes:
#   - Empty result → shortcut not registered as Start Menu app. Check
#     %APPDATA%\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk exists.
#   - AppID is empty → LNK file lacks AppUserModelID property (Pitfall #5).
#     Force-delete LNK + reinstall (D-08 step 4).
#   - AppID is wrong string → AUMID drift (D-09 #3).

# === Step 2: Launch via Start Menu shortcut, then read the in-process AUMID. ===
# In a SEPARATE PowerShell window after launching MusicStreamer via Start Menu:
$proc = Get-Process MusicStreamer | Select-Object -First 1
"PID: $($proc.Id)"
# Microsoft GetCurrentProcessExplicitAppUserModelID requires running INSIDE the
# target process — for a cross-process readback the simplest method is to read
# the same shell32 export from a thin C# inline (or just trust the in-process
# log line that __main__.py emits — see "Recommended: simpler alternative" below).

# === Step 2 (alternative — recommended): one-line debug log on startup. ===
# Patch __main__.py::_set_windows_aumid (TEMPORARY for diagnostic — revert after) to
# also log the readback. Saves all the cross-process IPC dancing.
#
# At the end of _set_windows_aumid, add:
#   readback = ctypes.c_wchar_p()
#   shell32.GetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.POINTER(ctypes.c_wchar_p)]
#   shell32.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(readback))
#   logging.info(f"AUMID readback: {readback.value!r}")
#
# Then launch via Start Menu, check the log file. Phase 43.1 already verified
# this readback works; we're using it as a one-off diagnostic.

# === Step 3: Inspect live SMTC binding via Settings UI + Get-StartApps cross-check. ===
# Settings UI: Settings → System → Notifications → look for "MusicStreamer".
# If listed: name is bound correctly. If absent: AUMID isn't being seen by
# the notification subsystem (which shares the same AppsFolder index as SMTC).

Get-StartApps | Format-Table   # confirms AppID column populated for MusicStreamer

# === Step 4: Force-fresh install procedure. ===
# Run from elevated PowerShell:
# 1. Uninstall via Settings → Apps → MusicStreamer → Uninstall
# 2. Force-clean install dir if it lingers:
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Programs\MusicStreamer" -ErrorAction SilentlyContinue
# 3. Force-clean stale shortcut (the critical step — Inno Setup may not rewrite
#    the LNK property bag on reinstall-over-top, Pitfall #5):
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk" -ErrorAction SilentlyContinue
# 4. Run the freshly-built installer:
& "$PWD\dist\installer\MusicStreamer-2.1.56-win64-setup.exe"
# 5. Re-run step 1 to confirm AppID populated.
# 6. Launch via Start Menu, play a stream, observe SMTC overlay.
```

### Example 4: Optional AUMID drift guard pytest

See Pitfall #6 above — the 10-line `test_aumid_string_parity.py`.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9+ + pytest-qt 4+ (per `pyproject.toml [project.optional-dependencies].test`) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` — `testpaths = ["tests"]`, `markers: integration` |
| Quick run command | `pytest tests/test_aa_url_detection.py tests/test_player_failover.py -x` |
| Full suite command | `pytest` (uses pyproject testpaths) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WIN-01 | `aa_normalize_stream_url` rewrites DI.fm `https://` → `http://` | unit | `pytest tests/test_aa_url_detection.py::test_aa_normalize_difm_https_to_http -x` | ❌ Wave 0 (file exists; new tests must be added) |
| WIN-01 | `aa_normalize_stream_url` is idempotent on already-`http://` DI.fm | unit | `pytest tests/test_aa_url_detection.py::test_aa_normalize_difm_http_passthrough -x` | ❌ Wave 0 |
| WIN-01 | `aa_normalize_stream_url` passes non-DI.fm URLs through unchanged | unit | `pytest tests/test_aa_url_detection.py::test_aa_normalize_non_difm_passthrough -x` | ❌ Wave 0 |
| WIN-01 | `aa_normalize_stream_url` handles empty/None gracefully | unit | `pytest tests/test_aa_url_detection.py::test_aa_normalize_empty -x` | ❌ Wave 0 |
| WIN-01 | `_set_uri` invokes the helper before handing URL to playbin3 | integration | `pytest tests/test_player_failover.py::test_set_uri_normalizes_difm_https_to_http -x` | ❌ Wave 0 (file exists; new test) |
| WIN-01 | YouTube/Twitch resolved URLs (HLS) are NOT incorrectly rewritten | integration | `pytest tests/test_player_failover.py::test_set_uri_passes_through_hls -x` | ❌ Wave 0 |
| WIN-01 | DI.fm channel plays end-to-end on Win11 VM (fresh AA import) | UAT (manual) | manual UAT script | n/a — CONTEXT.md D-12 |
| WIN-01 | DI.fm channel plays end-to-end on Win11 VM (Phase 42 settings-import roundtrip) | UAT (manual) | manual UAT script | n/a — CONTEXT.md D-12 |
| WIN-02 | Start Menu shortcut carries `org.lightningjim.MusicStreamer` AUMID | UAT (manual via PowerShell) | `Get-StartApps \| Where-Object Name -like 'MusicStreamer*'` returns AppID match | n/a — CONTEXT.md D-08 step 1 |
| WIN-02 | In-process AUMID matches shortcut AUMID | UAT (manual) | startup log line OR cross-process ctypes readback | n/a — CONTEXT.md D-08 step 2 |
| WIN-02 | SMTC overlay reads "MusicStreamer" (not "Unknown app") on fresh-install Start Menu launch with playing stream | UAT (manual) | open Win+K media flyout while playing | n/a — CONTEXT.md D-08 step 3 + ROADMAP SC #3 |
| WIN-02 (optional) | AUMID literal parity between `__main__.py` and `MusicStreamer.iss` | unit | `pytest tests/test_aumid_string_parity.py -x` | ❌ Wave 0 if shipped |

### Sampling Rate

- **Per task commit:** `pytest tests/test_aa_url_detection.py tests/test_player_failover.py -x` (~5s)
- **Per wave merge:** `pytest` full suite (~30-60s on dev box)
- **Phase gate:** Full suite green + Win11 VM UAT signoff per CONTEXT.md D-08/D-12 before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_aa_url_detection.py` — extend with 6-8 new tests for `aa_normalize_stream_url` (file exists; just add tests at end)
- [ ] `tests/test_player_failover.py` — extend with 2 new tests asserting `_set_uri` normalization (file exists; uses existing `make_player` harness — no new fixture needed)
- [ ] (Optional) `tests/test_aumid_string_parity.py` — new file, ~10 lines, ships if planner adopts the discretionary AUMID-drift guard
- [ ] No framework install needed — pytest + pytest-qt + qtbot fixture all in current `pyproject.toml`

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | All work | ✓ (per pyproject `requires-python = ">=3.10"`) | 3.12 (conda-forge build env) | — |
| pytest 9+ + pytest-qt 4+ | Wave 0 + 1 unit/integration tests | ✓ (per `[project.optional-dependencies].test`) | per pyproject pin | — |
| Linux dev box | URL helper unit tests + player integration tests | ✓ (CI / dev) | — | — |
| Windows 11 VM | WIN-01 UAT (DI.fm playback) + WIN-02 entire half | ✓ (Phase 43 / 44 spike rig) | Win11 | — |
| Inno Setup 6.3+ | Rebuild installer if WIN-02 requires `.iss` change | ✓ on VM (per Phase 44 README) | 6.3+ | — |
| `iscc.exe` | Build pipeline | ✓ on VM | — | — |
| Conda-forge env | Building MusicStreamer.exe via PyInstaller | ✓ on VM | per Phase 43 README | — |
| Node.js | YouTube playback (NOT this phase) | not required for WIN-01/02 | — | — |
| `Get-StartApps` cmdlet | WIN-02 diagnostic | ✓ (built into Windows 10/11 — `StartLayout` module) | n/a | `(New-Object -ComObject Shell.Application).NameSpace('shell:::{4234d49b-0245-4df3-b780-3893943456e1}').Items()` per Microsoft docs |
| DI.fm premium account + listen_key | WIN-01 UAT (DI.fm Lounge playback test) | ✓ (per Phase 43 / 44 UAT history) | — | None — UAT cannot proceed without |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `(New-Object -ComObject Shell.Application).Namespace($path).ParseName('lnk').ExtendedProperty('System.AppUserModel.ID')` | `Get-StartApps \| Where-Object Name -like 'MusicStreamer*'` | Win10 1709+ (StartLayout module GA) | Microsoft documents `Get-StartApps` as THE method for AUMID lookup; `ExtendedProperty` is fragile on per-user installs (Pitfall #3). **Recommend swapping CONTEXT.md D-08 step 1 to `Get-StartApps`.** |
| Setting `AppUserModelToastActivatorCLSID` on shortcut "for SMTC" | NOT setting it | n/a — never required | This Inno Setup property is for toast activator CLSID; SMTC display name resolves from AUMID + shortcut name alone. Cargo-culting risk if added. [VERIFIED: jrsoftware.org/files/is6.1-whatsnew.htm] |
| GnuTLS-based `souphttpsrc` | OpenSSL `gioopenssl.dll` | GStreamer 1.28.x (Phase 43 D-03 amendment) | DI.fm HTTPS rejection is server-side regardless — TLS backend swap doesn't help. The HTTPS→HTTP rewrite remains the right fix. |

**Deprecated/outdated:**
- The `ExtendedProperty('System.AppUserModel.ID')` snippet (CONTEXT.md D-08 step 1) — works sometimes, fragile in general. Replace with `Get-StartApps`.

## Project Constraints (from CLAUDE.md)

CLAUDE.md is minimal — only routes spike-findings work to `Skill("spike-findings-musicstreamer")`. No additional security, coding-convention, or testing rules to enforce.

**MEMORY.md notes (relevant to this phase):**
- `gsd-sdk` wrapper at `~/.local/bin/gsd-sdk` (operational, not relevant to phase content)
- Deployment target: Linux X11 DPR=1.0 — no HiDPI/Retina/Wayland-fractional rig. **Not relevant to this phase** (DI.fm + SMTC are both downstream of audio output and Windows shell respectively, neither involves DPI scaling).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `_set_uri` is the ONLY funnel handing URLs to `playbin3` | Architecture / D-01 | If a code path bypasses `_set_uri` (e.g., a future contributor adds direct `pipeline.set_property("uri", ...)`), DI.fm rewrite is silently skipped. **Mitigation:** the new player-level test asserts on `_pipeline.set_property("uri", ...)` for the rewritten URL — this catches the explicit wire path; future bypasses would need their own tests. [VERIFIED: grep `set_property("uri"` in player.py shows only one site at line 487] |
| A2 | `Get-StartApps` returns `org.lightningjim.MusicStreamer` for the installed Start Menu shortcut on Win11 22H2+ | WIN-02 diagnostic | If `Get-StartApps` returns empty, the shortcut isn't registered AS a Start Menu app. **This is exactly the diagnostic outcome we want** — D-09 #1 (stale/non-AUMID shortcut). The phase explicitly handles this via D-08 step 4. |
| A3 | "Unknown app" symptom is environmental (D-09 #1 or #2), not a code bug | WIN-02 entire half | If diagnostic reveals D-09 #3 (string drift) or unknown root cause, planner pivots to code-change scope per D-10. Phase scope flexes to accommodate. |
| A4 | Windows shell SMTC overlay name resolves from the matching shortcut's `Name` property (not from `RelaunchDisplayNameResource` or any other property) | WIN-02 mechanism | Empirically confirmed: `MusicStreamer.iss:68` uses `Name: "{userprograms}\MusicStreamer"` — the `MusicStreamer` segment IS the display name source. If WIN-02 UAT reveals SMTC reads a different string (e.g., "MusicStreamer.exe"), Microsoft's resolution path needs deeper investigation — but this is a low-probability edge case [CITED: learn.microsoft.com/en-us/windows/win32/shell/appids "Other window and shortcut properties... display name and icon used for it in the taskbar"]. |
| A5 | Phase 43 finding (DI.fm rejects HTTPS) is still current as of 2026-05-02 | WIN-01 entire half | If DI.fm fixed their HTTPS server in the interim, the rewrite is a no-op (still safe — HTTP still works) but the workaround is unnecessary. **Mitigation:** unchanged stored DB rows mean a future revert is a one-line helper deletion. No data impact. |

## Open Questions (RESOLVED)

1. **Should the AUMID-drift pytest guard ship?**
   - What we know: CONTEXT.md flags it as Claude's discretion. Risk is real (two unlinked literals); fix cost is ~10 lines of regex + assert.
   - What's unclear: whether the planner views the YAGNI cost as material in a single-author project.
   - **Recommendation:** ship it. The test runs on Linux CI, has zero runtime cost, and addresses a real silent-failure mode. 10 minutes of work for permanent regression protection.

2. **Should `_set_uri` log the rewrite at INFO level the FIRST time it fires per session, then DEBUG thereafter?**
   - What we know: CONTEXT.md D-05 specifies pure DEBUG log. Rationale: it's a stable workaround, not a user-visible event.
   - What's unclear: whether forensic visibility benefits from one INFO line per session ("DI.fm HTTPS workaround active").
   - **Recommendation:** stick with D-05 as locked. DEBUG-only matches the spirit of "silent rewrite." If a regression suspect later needs forensic log analysis, `LOG_LEVEL=DEBUG` flips it on without code change.

3. **Does the post-install `Run` checkbox (`MusicStreamer.iss:79` `Flags: ... unchecked`) currently bypass AUMID binding, contributing to the "Unknown app" symptom?**
   - What we know: D-09 #2 explicitly calls this out. The checkbox is `unchecked` by default (correct), but a user who manually checks it during install launches via the installer process tree, NOT via the Start Menu shortcut.
   - What's unclear: whether this scenario is the actual root cause OR whether D-09 #1 (stale shortcut) is. Diagnostic order: D-08 reveals which.
   - **Recommendation:** D-08 step 4 (force fresh install + relaunch via Start Menu only) eliminates both possibilities in one motion. No need to disambiguate before running the diagnostic.

## Sources

### Primary (HIGH confidence)
- **`musicstreamer/url_helpers.py:123` (`_aa_slug_from_url`)** — the existing predicate that the new helper composes with. Pure function, no Qt/GLib. [Read]
- **`musicstreamer/player.py:484` (`_set_uri`)** — the funnel where the helper wires in. [Read]
- **`musicstreamer/__main__.py:99-125` (`_set_windows_aumid`)** — the in-process AUMID call path; already correct per Phase 43.1. [Read]
- **`packaging/windows/MusicStreamer.iss:64-71` ([Icons] Start Menu shortcut)** — already declares `AppUserModelID:` per Phase 44 D-04. [Read]
- **`tests/test_aa_url_detection.py`** — the convention for unit-testing `url_helpers.py` functions. [Read]
- **`tests/test_player_failover.py`** — the harness pattern (`make_player` + `MagicMock` pipeline + `patch.object(p, "_set_uri")`) that new player-level tests must adapt around. [Read]
- **`tests/conftest.py`** — autouse `_stub_bus_bridge` fixture that prevents real GLib threads in unit tests. [Read]
- **`.claude/skills/spike-findings-musicstreamer/references/windows-gstreamer-bundling.md`** — DI.fm HTTPS landmine documented (Landmines section, "DI.fm premium URLs reject HTTPS"). [Read]
- **`.planning/milestones/v2.0-phases/43.1-windows-media-keys-smtc/43.1-CONTEXT.md`** — AUMID before QApplication, LPCWSTR argtypes, readback verification. [Read]
- **`.planning/milestones/v2.0-phases/44-windows-packaging-installer/44-CONTEXT.md`** — D-04 Start Menu shortcut + AUMID, D-15 DI.fm "accept server-side" policy this phase reverses, D-21 step 7 SMTC UAT criterion. [Read]

### Secondary (MEDIUM confidence)
- [Find the Application User Model ID of an installed app | Microsoft Learn](https://learn.microsoft.com/en-us/windows/configuration/store/find-aumid) — canonical `Get-StartApps` + `Shell.Application` AppsFolder method [WebFetch]
- [Get-StartApps (StartLayout) | Microsoft Learn](https://learn.microsoft.com/en-us/powershell/module/startlayout/get-startapps) — cmdlet docs, output format [WebFetch]
- [System.AppUserModel.ID - Win32 apps | Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/properties/props-system-appusermodel-id) — property formal definition [WebSearch result]
- [System.AppUserModel.RelaunchDisplayNameResource - Win32 apps | Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/properties/props-system-appusermodel-relaunchdisplaynameresource) — confirmed NOT relevant to SMTC overlay [WebFetch]
- [How to discover display name and icon location for a Windows Notification AppUserModelId — Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/821564/how-to-discover-display-name-and-icon-location-for) — confirmed undocumented interfaces involved; `Get-StartApps` is the safe documented path [WebFetch]
- [Inno Setup [Icons] section](https://jrsoftware.org/ishelp/topic_iconssection.htm) — `AppUserModelID` and `AppUserModelToastActivatorCLSID` are separate parameters; latter is for toast notifications, not SMTC [WebFetch]
- [Inno Setup 6.1 Revision History](https://jrsoftware.org/files/is6.1-whatsnew.htm) — `AppUserModelToastActivatorCLSID` introduction context [WebSearch result]
- [Application User Model IDs - Win32 apps | Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/shell/appids) — friendly name + grouping mechanics [WebSearch result]

### Tertiary (LOW confidence — flagged for VM verification)
- "Reinstall over top doesn't always rewrite the LNK property bag" (Pitfall #5) — empirical pattern from Inno Setup community forums; NOT confirmed against Microsoft docs. **Mitigation:** D-08 step 4 force-deletes the LNK before reinstalling, which sidesteps the issue regardless. Risk is contained.

## Metadata

**Confidence breakdown:**
- DI.fm helper design + tests: **HIGH** — every input file is read, every existing pattern is established, the helper is ~10 lines of pure stdlib code with a known idempotency contract.
- DI.fm cross-platform stability: **HIGH** — Phase 43 finding stands; even if DI.fm fixed HTTPS, the rewrite remains safe.
- SMTC diagnostic procedure: **HIGH** — Microsoft documents `Get-StartApps` as the canonical AUMID lookup; the only LOW-confidence claim is "which D-09 root cause is the actual one," and that's the explicit purpose of running D-08 on the VM.
- AUMID literal parity guard: **MEDIUM** — recommended as YAGNI-borderline; planner makes the call.
- Pitfall #5 LNK rewrite-on-reinstall behavior: **LOW** but materially mitigated by D-08 step 4.

**Research date:** 2026-05-02
**Valid until:** 2026-06-02 (DI.fm + Microsoft docs are stable; if more than 30 days elapse before execution, re-verify Phase 43 DI.fm finding still holds via a quick `curl -v https://prem1.di.fm/lounge?listen_key=...` smoke test — no need to re-run full research)
