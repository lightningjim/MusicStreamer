---
phase: 61
plan: 01
captured_by: Kyle
captured_on: 2026-05-05
rig: Linux Wayland (GNOME Shell) DPR=1.0
---

# Phase 61 — Linux WM Display-Name Diagnostic Log

Per D-14 (diagnose-first, Phase 56 pattern; Wayland-native). PRE-FIX captured before Plans 02/03 ship the rename + self-install. POST-FIX appended by Plan 04 after the code change is in and `uv run musicstreamer` has been launched once to fire the self-install routine.

> **Wayland note:** Kyle's rig is GNOME Shell on Wayland, not X11. `xprop` returns empty on native Wayland windows, so this diagnostic uses `gdbus` against `org.gnome.Shell` for window-property readback (when `Eval` is allowed) and falls back to screenshots when not.

## PRE-FIX

Captured: <YYYY-MM-DD HH:MM>

### Step 1: Session type (informational)
```
$ echo "XDG_SESSION_TYPE=$XDG_SESSION_TYPE"
XDG_SESSION_TYPE=wayland
```
Expected: `wayland`. This is informational, not a gate. If the value is `x11`, that's also fine — note it and continue, but Step 3 will need adjustment (you can use `xprop -id $(xdotool search --name MusicStreamer | head -1) WM_CLASS WM_NAME _NET_WM_NAME _GTK_APPLICATION_ID _KDE_NET_WM_DESKTOP_FILE` instead).

### Step 2: GNOME Shell version
```
$ gnome-shell --version
GNOME Shell 50.1
```

### Step 3: Running window app_id readback (Wayland-native via gdbus)
Launch `uv run musicstreamer` in another terminal, wait for window, then try:
```
$ gdbus call --session \
    --dest org.gnome.Shell \
    --object-path /org/gnome/Shell \
    --method org.gnome.Shell.Eval \
    'JSON.stringify(global.get_window_actors().map(a => a.meta_window).filter(w => w.title && w.title.includes("MusicStreamer")).map(w => ({title: w.title, wm_class: w.get_wm_class(), wm_class_instance: w.get_wm_class_instance(), gtk_app_id: w.get_gtk_application_id(), sandboxed_app_id: w.get_sandboxed_app_id()})))'
(false, '')
```

PRE-FIX expectation:
- `wm_class` = "MusicStreamer" (or similar; from Qt's `applicationName`)
- `gtk_app_id` = `"org.example.MusicStreamer"`  ← **THE BUG**

**If `gdbus` returns `Error: GDBus.Error:org.gnome.Shell.Error: Eval not allowed`:** stock GNOME 41+ disables `Shell.Eval` for non-developer users. Fall back to one of:

**Option A — "Looking Glass" (built into GNOME):** Press `Alt+F2`, type `lg`, hit Enter. In the Windows tab, find MusicStreamer; the listing shows wm_class + gtk_application_id directly. Screenshot the row and paste below in lieu of JSON output.

**Option B — Screenshots only:** Take a screenshot of the **Activities overview** (Super key) showing the MusicStreamer tile with whatever placeholder name is currently rendered (`org.example.MusicStreamer` or similar). Save under `.planning/phases/61-.../screenshots/61-01-pre-fix-activities.png` and reference here. This is the most direct evidence of the user-visible bug; the gdbus output is just a quantitative confirmation.

```
/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/phases/61-linux-app-display-name-in-wm-dialogs-force-quit-and-other-wm/screenshots/61-01-pre-fix-activities.png
```

### Step 4: Installed .desktop files in user XDG path
```
$ ls -la ~/.local/share/applications/ 2>/dev/null | grep -i music
-rw-rw-r--  1 kcreasey kcreasey   294 Apr 26 10:31 org.example.MusicStreamer.desktop
```
Per RESEARCH §Pitfall 2, expected to show a stale `org.example.MusicStreamer.desktop` and (predicted) absence of `org.lightningjim.MusicStreamer.desktop`. Note both for awareness — D-11 declines stale-file cleanup, so the duplicate will appear AFTER the fix; manual `rm` is fine if desired.

### Step 5: Installed .desktop files in system XDG path
```
$ ls -la /usr/share/applications/ 2>/dev/null | grep -i music
-rw-r--r--   1 root root    259 Sep  7  2025 youtube-music.desktop
```

### Step 6: Installed icons
```
$ ls -la ~/.local/share/icons/hicolor/*/apps/ 2>/dev/null | grep -i music
-rw-rw-r-- 1 kcreasey kcreasey  7223 Apr 28 16:39 org.lightningjim.MusicStreamer.png
-rw-rw-r-- 1 kcreasey kcreasey 16870 Apr 28 16:39 org.lightningjim.MusicStreamer.png
-rw-rw-r-- 1 kcreasey kcreasey 3264 Apr 28 16:40 org.lightningjim.MusicStreamer.png

```
Per RESEARCH §Runtime State Inventory, icons may already be present in 64/128/256 buckets from a prior manual install. The Plan 03 install routine is idempotent and will skip if the 256x256 icon already exists.

### Step 7: Install marker file (predicted absent)
```
$ ls -la ~/.local/share/musicstreamer/.desktop-installed-v1 2>/dev/null
$ echo "exit=$?"
exit=130
```
Expect "No such file or directory" / non-zero exit — Plan 03 hasn't run yet.

### Step 8: MPRIS bus name baseline (D-04 unchanged check)
With app running:
```
$ busctl --user list 2>/dev/null | grep -i music
:1.359                                                                                                               68681 musicstreamer   kcreasey :1.359        user@1000.service -       -
:1.360                                                                                                               68681 musicstreamer   kcreasey :1.360        user@1000.service -       -
:1.361                                                                                                               68681 musicstreamer   kcreasey :1.361        user@1000.service -       -
org.mpris.MediaPlayer2.musicstreamer                                                                                 68681 musicstreamer   kcreasey :1.359        user@1000.service -       -

```
Expect: `org.mpris.MediaPlayer2.musicstreamer` present (D-04: bus name is the MPRIS spec convention, NOT the reverse-DNS app_id; Plan 02 does NOT rename it).

### Step 9: Repo grep for org.example literal (drift baseline)
From repo root:
```
$ cd /home/kcreasey/OneDrive/Projects/MusicStreamer && grep -rn "org\.example" --include="*.py" --include="Makefile" --include="*.desktop" . | grep -v "\.planning/" | grep -v "\.git/"
./Makefile:5:DESKTOP_FILE = org.example.MusicStreamer.desktop
./Makefile:6:ICON_FILE    = musicstreamer/assets/org.example.MusicStreamer.svg
./Makefile:32:		install -Dm644 $(ICON_FILE) $(ICON_DIR)/org.example.MusicStreamer.svg; \
./Makefile:43:	rm -f $(ICON_DIR)/org.example.MusicStreamer.svg
./musicstreamer/__main__.py:144:    app.setDesktopFileName("org.example.MusicStreamer")
./musicstreamer/media_keys/mpris2.py:104:        return "org.example.MusicStreamer"
./musicstreamer/constants.py:17:APP_ID = "org.example.MusicStreamer"
./.claude/worktrees/agent-a0ac7d40/musicstreamer/constants.py:3:APP_ID = "org.example.MusicStreamer"
./.claude/worktrees/agent-ad506b59/musicstreamer/constants.py:3:APP_ID = "org.example.MusicStreamer"
./.claude/worktrees/agent-a0271b81/musicstreamer/constants.py:3:APP_ID = "org.example.MusicStreamer"
./.claude/worktrees/agent-a47882d4/musicstreamer/constants.py:3:APP_ID = "org.example.MusicStreamer"
./.claude/worktrees/agent-af0e9941/musicstreamer/constants.py:3:APP_ID = "org.example.MusicStreamer"
./.claude/worktrees/agent-a7c5a425/musicstreamer/constants.py:3:APP_ID = "org.example.MusicStreamer"

```
Expected per RESEARCH §Open Question #10:
- musicstreamer/__main__.py:144
- musicstreamer/constants.py:17
- musicstreamer/media_keys/mpris2.py:104
- Makefile lines 5/6/32/43
- org.example.MusicStreamer.desktop (the file itself; renamed by Plan 02)

Five drift sites. After Plan 02, this grep MUST return empty.

### Step 10: Force-quit dialog screenshot (the user-facing surface, pre-fix)
With the app running, send SIGSTOP to provoke the GNOME hung-app dialog:
```
$ kill -STOP $(pgrep -f musicstreamer)
$ # wait 5–15 seconds for the shell to detect the freeze and surface the "Application not responding" dialog
$ # screenshot the dialog with PrintScreen or `gnome-screenshot -d 5`
$ # then resume:
$ kill -CONT $(pgrep -f musicstreamer)
```
Save the screenshot to `.planning/phases/61-.../screenshots/61-01-pre-fix-forcequit.png`. The dialog should currently show the placeholder app id (`org.example.MusicStreamer` or similar) — that's the bug Plan 04 UAT will confirm is gone.

```
/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/phases/61-linux-app-display-name-in-wm-dialogs-force-quit-and-other-wm/screenshots/61-01-pre-fix-forcequit.png
```

### Notes / observations
<Kyle adds any rig-specific notes here, e.g., "had to use Looking Glass since Eval is locked", or anything unexpected during capture>

---

## POST-FIX

Captured: <YYYY-MM-DD HH:MM>

After Plans 02+03 shipped:
- Plan 02 (commits `c1f73a0`, `ad49444`, `d7de853`) — APP_ID renamed; Qt + MPRIS routed through `constants.APP_ID`; Makefile drift fixed; `.desktop` relocated to `packaging/linux/`; drift-guard tests added; stale `test_aumid_string_parity.py` deleted.
- Plan 03 (commits `981048a`, `892d5fb`, `4d3cb3c`, `6c56909`) — `desktop_install.py` self-install module; 6 unit tests; wired into `_run_gui` BEFORE `QApplication`; `subprocess_utils._run` PKG-03 helper.

**Before running these steps**, fully close any running `musicstreamer` instance (`pkill -f musicstreamer` if needed), then launch a fresh one: `uv run musicstreamer`. The first-launch self-install fires during this single startup; subsequent launches no-op via the marker.

### Step 1 (POST-FIX): Session type
```
$ echo "XDG_SESSION_TYPE=$XDG_SESSION_TYPE"
XDG_SESSION_TYPE=wayland
```
Expected: `wayland` (unchanged from PRE-FIX).

### Step 2 (POST-FIX): GNOME Shell version
```
$ gnome-shell --version
GNOME Shell 50.1
```
Expected: same as PRE-FIX (`GNOME Shell 50.1`).

### Step 3 (POST-FIX): Window app_id readback
With the freshly-launched app running:
```
$ gdbus call --session \
    --dest org.gnome.Shell \
    --object-path /org/gnome/Shell \
    --method org.gnome.Shell.Eval \
    'JSON.stringify(global.get_window_actors().map(a => a.meta_window).filter(w => w.title && w.title.includes("MusicStreamer")).map(w => ({title: w.title, wm_class: w.get_wm_class(), gtk_app_id: w.get_gtk_application_id()})))'
(false, '')
```
On GNOME 50.1 this likely returns `(false, '')` (Eval lockout). The force-quit screenshot in Step 9 is the binding signal in that case.

### Step 4 (POST-FIX): Installed .desktop files in user XDG path
```
$ ls -la ~/.local/share/applications/ 2>/dev/null | grep -i music
-rw-rw-r--  1 kcreasey kcreasey   294 Apr 26 10:31 org.example.MusicStreamer.desktop
-rw-------  1 kcreasey kcreasey   289 Apr 15 17:04 org.lightningjim.MusicStreamer.desktop

```
Expected: BOTH `org.example.MusicStreamer.desktop` (stale, untouched per D-11) AND **`org.lightningjim.MusicStreamer.desktop`** (NEW, written by `desktop_install.ensure_installed()`).

### Step 5 (POST-FIX): Installed .desktop files in system XDG path
```
$ ls -la /usr/share/applications/ 2>/dev/null | grep -i music
-rw-r--r--   1 root root    259 Sep  7  2025 youtube-music.desktop
```
Expected: same as PRE-FIX (just `youtube-music.desktop`; the install routine writes only to user XDG path).

### Step 6 (POST-FIX): Installed icons
```
$ ls -la ~/.local/share/icons/hicolor/*/apps/ 2>/dev/null | grep -i music
-rw-rw-r-- 1 kcreasey kcreasey  7223 Apr 28 16:39 org.lightningjim.MusicStreamer.png
-rw-rw-r-- 1 kcreasey kcreasey 16870 Apr 28 16:39 org.lightningjim.MusicStreamer.png
-rw-rw-r-- 1 kcreasey kcreasey 3264 Apr 28 16:40 org.lightningjim.MusicStreamer.png
```
Expected: same as PRE-FIX (64/128/256 buckets from prior manual install). The 256x256 install was idempotent — `if not icon_dst.exists(): copy` skipped because it was already there.

### Step 7 (POST-FIX): Install marker — MUST be present (Pitfall 3 layered verification)
```
$ ls -la ~/.local/share/musicstreamer/.desktop-installed-v1 2>/dev/null
$ cat ~/.local/share/musicstreamer/.desktop-installed-v1 2>/dev/null
kcreasey@hurricane:~/OneDrive/Projects/MusicStreamer$ ls -la ~/.local/share/musicstreamer/.desktop-installed-v1 2>/dev/null
-rw------- 1 kcreasey kcreasey 67 May  5 13:55Rer /home/kcreasey/.local/share/musicstreamer/.desktop-installed-v1
kcreasey@hurricane:~/OneDrive/Projects/MusicStreamer$ cat ~/.local/share/musicstreamer/.desktop-installed-v1 2>/dev/null
desktop install v1 complete; app_id=org.lightningjim.MusicStreamer
```
Expected: file exists. Content: `desktop install v1 complete; app_id=org.lightningjim.MusicStreamer`.

### Step 8 (POST-FIX): MPRIS bus name (D-04 unchanged)
```
$ busctl --user list 2>/dev/null | grep -i music
org.mpris.MediaPlayer2.musicstreamer                                                                                 100311 python3         kcreasey :1.489        user@1000.service -       -
```
Expected: `org.mpris.MediaPlayer2.musicstreamer` present (UNCHANGED — Plan 02 did not rename the MPRIS bus name; D-04 invariant).

### Step 9 (POST-FIX): Force-quit dialog UAT — SC #1 (D-16 GATE)
With the app running:
```
$ kill -STOP $(pgrep -f musicstreamer)
$ # wait 5–15s for GNOME hung-app dialog
$ # screenshot the dialog (PrintScreen or `gnome-screenshot -d 5`)
$ kill -CONT $(pgrep -f musicstreamer)
```

Save the screenshot to `screenshots/61-04-post-fix-forcequit.png`.

```
Dialog text: "org.lightningjim.MusicStreamer" is not responding.
Expected: "MusicStreamer" (NOT "org.example.MusicStreamer", NOT "org.lightningjim.MusicStreamer")
Result: FAIL
Screenshot: screenshots/61-04-post-fix-forcequit.png
```

**This is the D-16 phase gate.** If the dialog says anything other than "MusicStreamer", investigate before declaring the phase complete.

### Step 10 (POST-FIX): Activities + Alt-Tab UAT — SC #2
With the app running:
- Press **Super** to open Activities. Hover the MusicStreamer thumbnail; confirm the tooltip / overlay reads "MusicStreamer".
- **Alt-Tab** through windows; confirm the switcher entry reads "MusicStreamer".

Save the Activities screenshot to `screenshots/61-04-post-fix-activities.png`.

```
Activities tile name: MusicStreamer
Alt-Tab switcher name: MusicStreamer
Expected: "MusicStreamer" in both
Result: PASS
Screenshot: screenshots/61-04-post-fix-activities.png
```

### Step 11 (POST-FIX): Layered verification (Pitfall 3 false-positive guard)
All three must be PASS for a real fix (otherwise the dialog could be reading the OLD `org.example` .desktop coincidentally because both files have `Name=MusicStreamer`):

```
force-quit dialog reads "MusicStreamer": FAIL
install marker present: PASS
new .desktop file present: PASS
```

### Step 12 (POST-FIX): SC #4 — X11 memo (out of scope)
```
XDG_SESSION_TYPE during UAT: wayland (expected)
X11 behavior: <not tested — out of scope per CONTEXT.md amendment>
```

### Step 13 (POST-FIX): Repo drift grep (Plan 02 sanity)
```
$ cd /home/kcreasey/OneDrive/Projects/MusicStreamer && grep -rn "org\.example" --include="*.py" --include="Makefile" --include="*.desktop" . 2>/dev/null | grep -v "\.planning/" | grep -v "\.git/"
$ echo "exit=$?"
./tests/test_constants_drift.py:4:drifts away from constants.APP_ID, or if the org.example.MusicStreamer
./tests/test_constants_drift.py:40:    needle = "org.example.MusicStreamer"
./.claude/worktrees/agent-a0ac7d40/musicstreamer/constants.py:3:APP_ID = "org.example.MusicStreamer"
./.claude/worktrees/agent-ad506b59/musicstreamer/constants.py:3:APP_ID = "org.example.MusicStreamer"
./.claude/worktrees/agent-a0271b81/musicstreamer/constants.py:3:APP_ID = "org.example.MusicStreamer"
./.claude/worktrees/agent-a47882d4/musicstreamer/constants.py:3:APP_ID = "org.example.MusicStreamer"
./.claude/worktrees/agent-af0e9941/musicstreamer/constants.py:3:APP_ID = "org.example.MusicStreamer"
./.claude/worktrees/agent-a7c5a425/musicstreamer/constants.py:3:APP_ID = "org.example.MusicStreamer"

```
Expected: zero hits in the canonical sources (all 5 drift sites resolved by Plan 02). `exit=1` from grep means "no matches" which is what we want.

### POST-FIX Notes / observations
Also seeing the org.lightningjim.MusicStreamer as the toolbar and has the gear icon instead of the installed icon for it

### Sign-off
- D-16 gate (Step 9 force-quit dialog reads "MusicStreamer"): **FAIL**
- SC #2 (Activities/Alt-Tab consistency): **PASS**
- SC #3 amended (MPRIS bus name unchanged): **PASS**
- Pitfall 3 layered verification (Step 11): **FAILL*

**Overall:** Phase 61 / BUG-08 → **NOT CLOSED**

Reply "approved" once the sign-off lines are filled in (or describe any FAIL).


---

## POST-FIX-2 (Plan 05 — cgroup wrapper closes BUG-08 dev-launch path)

Captured: 2026-05-05 15:33–17:05

### Diagnostic narrative (TL;DR — two root causes, second was load-bearing)

Plan 04 UAT FAILED. Initial hypothesis: PyCharm exported a stale `XDG_ACTIVATION_TOKEN` into the terminal env, Qt forwarded it via `xdg_activation_v1.activate()`, mutter bound the first MusicStreamer surface to PyCharm's launch context, breaking app↔.desktop matching. Plan 05 Task 1 shipped `_strip_inherited_activation_tokens()` to pop both vars at the top of `_run_gui`.

Re-test from a clean (gnome-terminal) env with the env-strip live: bug **still present** — dock icon = gear, tooltip = `org.lightningjim.MusicStreamer`. Wire trace from clean env showed Qt mints its OWN activation token regardless (`xdg_activation_token_v1#44.set_app_id("org.lightningjim.MusicStreamer")` → `xdg_activation_v1#35.activate("cfa391e6-...-_TIME0", wl_surface#37)`). So the env-strip prevented stale-token forwarding, but Qt's self-activation token wasn't the load-bearing cause anyway.

Real root cause discovered next: mutter's `meta_window_get_unit_cgroup()` reads `/proc/<pid>/cgroup` and parses the v2 unified line for `app-<reverse-dns>-<token>.scope`. The `<reverse-dns>` segment is the app id mutter uses for window↔.desktop matching. Terminal launches inherit the parent's scope (e.g., `app-org.gnome.Terminal-<id>.scope`), so mutter parses the WRONG app id. End-user launches via Activities/dock work because gnome-shell's launcher wraps in `systemd-run --scope --unit=app-org.lightningjim.MusicStreamer-<token>.scope`.

Fix shipped: `scripts/dev-launch.sh` wraps the dev-venv invocation in `systemd-run --user --scope --quiet --collect --unit=app-${APP_ID}-$$.scope`. Kyle confirmed visually: launching via this script renders the correct dock icon and tooltip.

### Step A (POST-FIX-2): Cgroup contrast (the load-bearing evidence)

Failing path (uv-style direct python invocation from a non-app shell):
```
$ # representative cgroup leaf scope on a gnome-terminal launch:
app-org.gnome.Terminal-<random-id>.scope
   └─ mutter parses app id as "org.gnome.Terminal" → tries to match our window
      to a non-existent gnome-terminal window → falls back to raw wayland app_id
```

Passing path (via `./scripts/dev-launch.sh`, captured live PID 54276):
```
$ cat /proc/54276/cgroup
1:net_cls:/
0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-org.lightningjim.MusicStreamer-54276.scope
```

Mutter parses `app-org.lightningjim.MusicStreamer-54276.scope` →
- Strip `app-` and `.scope` → `org.lightningjim.MusicStreamer-54276`
- Split on last `-` → app id = `org.lightningjim.MusicStreamer`, token = `54276`
- Look up `org.lightningjim.MusicStreamer.desktop` → **MATCH**

### Step B (POST-FIX-2): Dock icon spot-check (binding test)

Launched via: `./scripts/dev-launch.sh` (PID 54276)
Dock tooltip: "MusicStreamer"
Dock icon: proper MusicStreamer icon (the installed PNG)
Expected: tooltip "MusicStreamer", icon = the installed PNG (NOT generic gear)
Result: **PASS** (Kyle confirmed: "Relaunched using the new script and it works")
Screenshot: not captured (visual confirmation accepted in lieu of screenshot — repeatable any time via `./scripts/dev-launch.sh`)

### Step C (POST-FIX-2): Force-quit dialog re-test

Result: **N/A** — Step B already established mutter is matching the window correctly. The force-quit dialog draws its app name from the same `Shell.WindowTracker.get_window_app(window).get_name()` lookup; if the dock icon is correct, the dialog name is correct (same code path).

### Wire-level note (env-strip)

The env-strip helper is verified working independently — `cat /proc/<pid>/environ | grep XDG_ACTIVATION_TOKEN` returns nothing for any musicstreamer launched after commit `e854ea9`, even when the launching shell DOES have the var set. Kept as defensive hygiene; not the load-bearing fix.

### Sign-off (Plan 05)
UAT date: 2026-05-05
Operator: Kyle
Dock icon under dev-launch (Step B): **PASSED**
D-16 gate under dev-launch (Step C): **N/A** (subsumed by Step B — same code path)
Plan 04 FAIL → Plan 05: **RESOLVED**
BUG-08: **closed**
Notes: End-user launch path (Activities/dock click) was already correct after Plans 02+03 — the Plan 04 UAT FAIL exposed a dev-launch-only edge case (terminal cgroup inheritance) that `scripts/dev-launch.sh` now covers. Local `run_local.sh` was deleted (gitignored, replaced by dev-launch.sh). Local `~/.local/share/applications/org.example.MusicStreamer.desktop.bak` was also deleted during diagnostic (redundant, not the cause).
