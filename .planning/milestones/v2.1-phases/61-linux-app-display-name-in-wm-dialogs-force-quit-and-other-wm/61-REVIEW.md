---
phase: 61-linux-app-display-name-in-wm-dialogs-force-quit-and-other-wm
reviewed: 2026-05-05T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - Makefile
  - musicstreamer/__main__.py
  - musicstreamer/constants.py
  - musicstreamer/desktop_install.py
  - musicstreamer/media_keys/mpris2.py
  - musicstreamer/subprocess_utils.py
  - packaging/linux/org.lightningjim.MusicStreamer.desktop
  - scripts/dev-launch.sh
  - tests/test_activation_token_strip.py
  - tests/test_constants_drift.py
  - tests/test_desktop_install.py
  - tests/test_main_run_gui_ordering.py
findings:
  critical: 0
  warning: 6
  info: 7
  total: 13
status: issues_found
---

# Phase 61: Code Review Report

**Reviewed:** 2026-05-05
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 61 migrates the Linux app id from `org.example.MusicStreamer` to
`org.lightningjim.MusicStreamer`, ships a first-launch XDG self-installer
for `.desktop` + icon, and adds two defensive measures for terminal-launched
dev runs (an env-strip helper and a systemd-scope wrapper script).

Overall the implementation is careful: atomic writes via `tempfile` +
`os.replace`, list-form subprocess args (no shell), Linux-only gates, marker
files for idempotency, and a dedicated drift-guard test. There are no
**Critical** findings — no shell injection, no symlink-traversal hole I can
prove exploitable in a single-user `~/.local/share` context, no crash paths
in the non-error code path.

The **Warning**-level findings cluster around subprocess timeout handling
in `desktop_install._best_effort`, an order-of-operations bug in `dev-launch.sh`
(systemd-run check fails fast, but the `--collect` flag is incompatible with
some older systemd-run releases without `--scope` semantics it might
silently swallow), and weak test coverage for the **subprocess-injection
attack surface** of `_best_effort` when `XDG_DATA_HOME` is attacker-influenced.

The most consequential **Warning** is **WR-01**: `_do_install` writes the
marker even when only the **icon** install actually succeeded — if the
`.desktop` write raises an exception the existing-file branch swallows
without re-raising. Wait, re-traced — the existing-file branch is
`_needs_install()` returning False (gracefully skip), not an exception.
Re-classified as **WR-04** below: the marker semantics conflate "install
succeeded" with "install was skipped because user file already exists."
On second launch with a present-but-different user file, the marker is
written and the missing icon install is permanently masked.

## Warnings

### WR-01: `_best_effort` swallows non-`FileNotFoundError`/`TimeoutExpired` `OSError`s silently at `debug` level

**File:** `musicstreamer/desktop_install.py:196-221`

**Issue:** The catch-all `except Exception` at line 220 logs at `_log.debug`,
which is below the default `WARNING` level set in `__main__.main()` (line
222: `logging.basicConfig(level=logging.WARNING)`). Real failures of
`update-desktop-database` or `gtk-update-icon-cache` — for example permission
errors writing the `mimeinfo.cache` file when `~/.local/share/applications`
is owned by root from a botched prior `sudo make install` — will be totally
invisible to the user and to support, but the marker still gets written, so
the next launch won't retry. The non-zero exit-code branch (line 211) also
logs at `_log.debug` for the same reason.

The hooks are explicitly "best-effort," but **silently** invisible is
different from **best-effort**. At minimum, log non-zero exits and unexpected
exceptions at `_log.warning` so a user complaint about "the icon never
shows up" can be diagnosed from a log.

**Fix:**
```python
def _best_effort(cmd: list[str]) -> None:
    try:
        result = subprocess_utils._run(
            cmd, capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            _log.warning(
                "%s exit %d: %s",
                cmd[0], result.returncode, result.stderr.strip()
            )
    except FileNotFoundError:
        _log.debug("%s not found on PATH -- skipping cache refresh", cmd[0])
    except subprocess.TimeoutExpired:
        _log.warning("%s timed out after 10s -- skipping", cmd[0])
    except Exception as exc:  # noqa: BLE001
        _log.warning("%s raised %s -- skipping", cmd[0], exc)
```

### WR-02: `_do_install` writes marker even when `.desktop` install was skipped due to user-modified file

**File:** `musicstreamer/desktop_install.py:95-123` and `70-92`

**Issue:** `ensure_installed` writes the marker iff `_do_install()` returns
without raising (line 91). `_do_install` calls `_needs_install(desktop_dst)`;
if that returns False (existing world-readable file present, e.g. user
modified or pre-installed via `make install`), the bundled write is
**silently skipped** but the marker is still written on the same launch.

Concretely: a user runs `make install` first (system path: `~/.local/share/applications/org.lightningjim.MusicStreamer.desktop` exists, mode 0644). Then on first GUI launch, `_needs_install` says "no install needed," `_do_install` returns clean, marker is written. Now suppose the user's pre-existing `.desktop` references a different `Exec=` (e.g., the old PyInstaller dev path); the icon install ALSO ran (separately gated), so they get our icon but their stale `Exec=`, and the marker locks this in forever. There is no correction path.

This is the inverse failure of `_needs_install`'s mode-broken-repair: that branch covers the **0600** stale case, but the **0644 stale-content** case (user did `make install` from main before the Phase 61 cut, then upgraded) is not addressed.

**Fix:** Either (a) compare bundled bytes vs existing bytes (cheap; `read_bytes`) and overwrite when they differ AND the file's content matches a known-prior-bundled hash list, OR (b) bump the marker version (`.desktop-installed-v2`) on every meaningful change to the bundled file, as the docstring at line 19-21 already promises. Document that path (b) is the operational mechanism. As written today, no version-bump policy is encoded — the `v1` suffix is a string in one place, with nothing wired up to re-trigger.

### WR-03: `_write_marker` does not match its docstring claim — `migration._write_marker` uses `Path.write_text`, not tempfile+rename

**File:** `musicstreamer/desktop_install.py:224-238`

**Issue:** The docstring at line 225 says `"mirrors migration._write_marker"`. Inspection of `musicstreamer/migration.py:65-66` shows `migration._write_marker` is a one-liner: `Path(path).write_text("platformdirs migration complete\n")`. The desktop_install version uses a tempfile + atomic-rename dance.

This is not a bug per se — atomic-rename is *better* — but the comment is misleading and will confuse the next reader who diff-checks the two and finds them different. Either align the implementations or update the comment.

A subtler issue: `_write_marker` does NOT clean up `tmp_path` on failure (no try/except), unlike `_atomic_copy`. If `os.replace` fails (e.g., cross-filesystem `paths.data_dir()` vs tempfile dir — unlikely but possible if `paths.data_dir()` is a bind-mount), a `.{marker.name}.XXXXXX` turd is left behind in the data dir.

**Fix:**
```python
def _write_marker(marker: Path) -> None:
    marker.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=str(marker.parent),
        prefix=f".{marker.name}.",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(
            f"desktop install v1 complete; app_id={constants.APP_ID}\n"
        )
        tmp_path = Path(tmp.name)
    try:
        os.replace(tmp_path, marker)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
```

And update the docstring to "Atomically write the install marker (atomic
rename; stricter than ``migration._write_marker``)."

### WR-04: `dev-launch.sh` `--collect` is a systemd 236+ flag; older targets fail without a useful message

**File:** `scripts/dev-launch.sh:50-52`

**Issue:** `systemd-run --collect` was added in systemd v236 (December 2017). For dev rigs on older distros (Debian 9 stable was systemd 232, RHEL 7 was systemd 219), the script will exit with a generic systemd-run usage error that does not match the script's own error-message style ("Run 'uv sync' first." / "This wrapper only works on systemd-managed Linux.").

Today's deployment target (per CLAUDE.md memory: "Wayland (GNOME Shell)") implies modern systemd, so this is unlikely to bite in practice — but the failure mode is a confusing wall of text from systemd-run instead of a clear "your systemd is too old" hint.

Additionally, `--unit="app-${APP_ID}-$$.scope"` uses the literal `app-org.lightningjim.MusicStreamer-12345.scope` as a unit name. Systemd unit names containing dots are accepted but escape weirdly under `systemctl status`. Mutter's parser splits on the *last* dash, so the comment at lines 21-25 is correct — but the dots in the reverse-DNS portion mean any future tooling that splits on `.` will misbehave. Worth a comment that the dots are intentional and parsed-by-position, not by-delimiter.

**Fix:** Add a feature-probe early-exit for `--collect`:
```bash
if ! systemd-run --user --scope --collect --help 2>&1 | grep -q -- '--collect'; then
  echo "dev-launch: systemd-run lacks --collect (need systemd 236+)" >&2
  exit 1
fi
```
Or accept the failure mode as acceptable given the deployment target.

### WR-05: `_atomic_copy` does not handle the case where `dst.parent` is a symlink to a directory the user does not own

**File:** `musicstreamer/desktop_install.py:176-193`

**Issue:** The defensive comment at line 183 says `os.replace` does not follow symlinks at the destination. True for the *destination file*, but the **destination directory** (`dst.parent`) is opened as the `dir=` argument to `NamedTemporaryFile`. If `~/.local/share/applications` is a symlink (e.g., to a flatpak overlay, a containerized home, or a user experiment), `tempfile` will resolve through the symlink and write into the resolved location. Subsequent `os.replace` will rename within that resolved directory.

This is not a *vulnerability* in single-user mode (the user owns whatever the symlink points at). But if `XDG_DATA_HOME` is set to a path containing a symlink the user does not control (e.g., a sandboxed dev environment using a `/srv/shared/xdg` mount), the temp file will be created in that shared location and may leak read-mode bits to other users until the chmod runs.

Lower-likelihood scenario: a hostile user-local process races `tempfile.NamedTemporaryFile`'s 0600-mode default by exploiting the predictable `f".{dst.name}."` prefix to pre-create a same-named symlink. `NamedTemporaryFile` uses `O_EXCL` internally and will get `FileExistsError`, so this race is closed — but the **rename** path still depends on `dst.parent` being a directory the user owns.

**Fix:** Add a `_log.debug("install dir resolved to: %s", dst.parent.resolve())` so symlink resolution is at least visible in diagnostics. Additionally consider opening the parent with `os.O_NOFOLLOW | os.O_DIRECTORY` and using `tempfile.mkstemp(dir=fd)` for paranoia, but for the single-user threat model documented in the docstring, current behavior is acceptable.

### WR-06: `test_existing_files_preserved` and `test_first_launch_installs_files` rely on `sys.platform.startswith("linux")` but `test_no_op_off_linux` monkeypatches `desktop_install.sys.platform` — inconsistent test guards

**File:** `tests/test_desktop_install.py:44-89` and `92-100`

**Issue:** Three test paths have three different platform-guard styles:

1. `test_first_launch_installs_files` (line 48): hard `assert sys.platform.startswith("linux")` — fails the test on non-Linux instead of skipping.
2. `test_idempotent_via_marker` (line 69-70): `if not sys.platform.startswith("linux"): pytest.skip(...)`.
3. `test_no_op_off_linux` (line 94): monkeypatches `desktop_install.sys.platform = "win32"` — this only works because `desktop_install.py` does `import sys` at module level, then `sys.platform.startswith("linux")` reads the *re-bound* attribute. If anyone changes `desktop_install.py` to `from sys import platform` (which is idiomatic in some style guides), this test silently breaks because the import binds the *value*, not the module.

The first style is also wrong: a non-Linux dev running `pytest` locally should get a `skip`, not a `fail`. Today this isn't a problem because the project is Linux-targeted, but the asymmetry is a code-smell that will bite cross-platform CI.

**Fix:** Standardize on `pytest.skip` at the top of every Linux-only test, and add a comment in `desktop_install.py` near `import sys` that tests rely on the module-level binding.

```python
# At top of every Linux-only test:
if not sys.platform.startswith("linux"):
    pytest.skip("desktop_install is Linux-only", allow_module_level=False)
```

## Info

### IN-01: `subprocess_utils._popen` and `_run` use single-underscore names, suggesting "module-private" but are imported from other modules

**File:** `musicstreamer/subprocess_utils.py:14, 21` and `musicstreamer/desktop_install.py:208`

**Issue:** Python convention treats `_name` as a soft "private" hint. Both `_popen` and `_run` are explicitly **part of the package API** (PKG-03 mandates their use), so the underscore is misleading. Either drop the underscore (`run`, `popen`) or document why it's there ("underscore signals 'use at your own risk; CREATE_NO_WINDOW only' rather than truly private").

The PKG-03 enforcement test (`test_pkg03_compliance.py`) hardcodes the *forbidden* names (`subprocess.{Popen,run,call}`), not the *allowed* ones, so a rename is safe.

### IN-02: Marker version string `v1` is hardcoded in two places without a constant

**File:** `musicstreamer/desktop_install.py:67` (`.desktop-installed-v1`) and line 235 (`f"desktop install v1 complete; app_id={constants.APP_ID}\n"`)

**Issue:** When the docstring at line 19-21 says to "bump the marker version (`.desktop-installed-v2`) so existing installs re-run," the bumper has to find both literals. Promote to a module-level constant:

```python
_MARKER_VERSION = "v1"

def _install_marker() -> Path:
    return Path(paths.data_dir()) / f".desktop-installed-{_MARKER_VERSION}"
```

This makes the bump policy mechanical instead of documentation-driven.

### IN-03: `_PACKAGE_ROOT` resolution assumes `musicstreamer/` is one directory below repo root

**File:** `musicstreamer/desktop_install.py:47`

**Issue:** `_PACKAGE_ROOT = Path(__file__).parent.parent` assumes the package is at `<repo>/musicstreamer/desktop_install.py`. This is true today, and the docstring (lines 22-29) acknowledges the PyInstaller note. However, when the package is installed as an editable wheel via `pipx install --editable .`, `__file__` may resolve to a path under `~/.local/pipx/venvs/musicstreamer/lib/python3.X/site-packages/musicstreamer/desktop_install.py` (depending on pipx vs editable install mode) — and `parent.parent` then points at `site-packages/`, where there is no `packaging/linux/`.

Today the Linux install path is `make install` + `pipx install --editable . --system-site-packages` (Makefile line 27), and the editable install keeps `__file__` rooted at the repo source — so this is fine. But the assumption is fragile: a switch from pipx editable to a `pip install --user .` (non-editable) would break the bundled-asset lookup, and `ensure_installed` would log a "no such file" warning on every launch.

**Fix:** Either (a) use `importlib.resources.files("musicstreamer")` to read packaged data files (proper Python packaging path), or (b) declare `packaging/linux/` as `package_data` in `pyproject.toml` so the assets ship inside `musicstreamer/_data/`, and resolve via `importlib.resources`. The current path works for `uv run` and editable installs only.

### IN-04: `LinuxMprisBackend.shutdown` `pass`-on-Exception is overly broad

**File:** `musicstreamer/media_keys/mpris2.py:295-302`

**Issue:** Bare `except Exception: pass` at shutdown swallows real bugs (e.g., a `TypeError` from a future API change in `QDBusConnection.unregisterObject`). Narrow to `RuntimeError` / `OSError` and log at `debug` for truly-unexpected types.

(This file's diff was minimal in Phase 61 — only the `DesktopEntry` property at line 104-105 changed to read `constants.APP_ID`. Including the existing pattern as info-level so it's on the radar.)

### IN-05: `__main__._strip_inherited_activation_tokens` does its own `import os` inside the function

**File:** `musicstreamer/__main__.py:157`

**Issue:** `import os` already happens transitively many times before `_run_gui` is reached. The local import inside the function adds zero benefit (no PyInstaller side-effect avoidance, no defer-cost optimization since `os` is loaded at interpreter startup), and complicates monkeypatching (tests can't `monkeypatch.setattr(__main__, "os", ...)` to swap the env interface). Move `import os` to the module-level import block at line 6-8.

### IN-06: `Makefile` `install` target conditionally installs the icon but unconditionally tries to remove it on `uninstall`

**File:** `Makefile:32-34, 44`

**Issue:** Line 32-34 guards the icon install with `[ -f "$(ICON_FILE)" ]`. Line 44 (`uninstall`) unconditionally `rm -f` the destination. The `-f` flag suppresses the "file not found" error, so this is harmless, but it's an inconsistency that suggests `uninstall` was written without reading `install`. If the icon install is conditional because the icon may not be present in the source tree, the uninstall is also redundant in that case — but harmless.

Lower priority: the `update-desktop-database` call on `uninstall` (line 45) runs *after* the file is removed, but uses `2>/dev/null || true` to suppress errors. If `update-desktop-database` is missing from PATH, `make uninstall` continues silently — same pattern as install. Consistent and acceptable.

### IN-07: `test_constants_drift.py::test_dev_launch_script_app_id_matches_constants` matches the literal `'APP_ID="..."'` substring, which fails on legitimate refactors

**File:** `tests/test_constants_drift.py:62-68`

**Issue:** The test asserts `f'APP_ID="{constants.APP_ID}"' in text`. A future refactor that writes `APP_ID='org.lightningjim.MusicStreamer'` (single quotes, valid bash) or `readonly APP_ID="org.lightningjim.MusicStreamer"` would still satisfy the substring check (the latter does), but `APP_ID=org.lightningjim.MusicStreamer` (no quotes — also valid bash for a no-whitespace value) would not. This is a soft contract.

The test would be more robust as a `bash -c 'source script-fragment; echo "$APP_ID"'` round-trip, but at the cost of running a subshell. The current test is fine for catch-the-typo purposes — flagging only because a more explicit assertion message would help future maintainers ("the script is parsed by substring match; preserve double-quoted form").

---

## Notes on what I did NOT find

A few areas I checked carefully and found clean:

- **Shell injection in `_best_effort`**: `cmd` is a list, no `shell=True`, no untrusted input flows in. XDG paths are user-controlled but only flow as positional args, not as shell-expanded strings. Safe.
- **Path traversal in `_atomic_copy`**: Destination is computed from `_xdg_data_home() / "applications" / f"{constants.APP_ID}.desktop"` — `APP_ID` is a constant literal, no user input. Even if `XDG_DATA_HOME` is malicious, the worst case is writing into a user-influenced directory the user already controls.
- **Race on env-strip in `_run_gui`**: `_strip_inherited_activation_tokens()` runs *before* any Qt import (verified line 164 vs line 178). Qt cannot have read the stale env vars yet. Safe.
- **StartupWMClass alignment**: Bundled `.desktop` declares `StartupWMClass=MusicStreamer`. `__main__._run_gui` calls `app.setApplicationName("MusicStreamer")` (which Qt uses for the wayland app_id and X11 WM_CLASS). Aligned.
- **`__main__._set_windows_aumid` reads `constants.APP_ID` when arg is None**: Confirmed; D-02 single-source-of-truth holds for both Windows and Linux.
- **Test `test_strip_pops_both_tokens`**: Uses `monkeypatch.setenv` properly; test isolation is correct.
- **Test fixtures cleanup**: `_redirect_paths` (autouse=True in `test_desktop_install.py`) saves and restores `paths._root_override` — no leak.

---

_Reviewed: 2026-05-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
