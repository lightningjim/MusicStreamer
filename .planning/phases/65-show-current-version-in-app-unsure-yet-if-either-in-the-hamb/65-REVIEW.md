---
phase: 65-show-current-version-in-app-unsure-yet-if-either-in-the-hamb
reviewed: 2026-05-08T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - packaging/windows/build.ps1
  - packaging/windows/MusicStreamer.spec
  - musicstreamer/__main__.py
  - musicstreamer/ui_qt/main_window.py
  - tests/test_main_run_gui_ordering.py
  - tests/test_main_window_integration.py
  - tests/test_packaging_spec.py
  - tests/test_version.py
findings:
  blocker: 1
  warning: 4
  info: 4
  total: 9
status: issues_found
---

# Phase 65: Code Review Report

**Reviewed:** 2026-05-08
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

The Phase 65 implementation is largely sound: the runtime version-display
wiring (`importlib.metadata.version("musicstreamer")` in `__main__._run_gui`
and `MainWindow.__init__`) is correct, the spec edit (`copy_metadata` +
`_ms_datas` concatenation) follows the existing `_cn_datas`/`_sl_datas`
convention, and the new build-script defenses (pre-bundle uninstall+reinstall,
post-bundle dist-info singleton/version assertion) are well-motivated and
documented.

However, the review surfaces:

- **1 BLOCKER** — a regression-guard test in `tests/test_main_run_gui_ordering.py`
  is structurally vacuous: it compares `find()` positions of two strings that
  appear in two different functions, so the assertion always passes regardless
  of the ordering it is meant to police.
- **4 WARNINGs** — one is the long-standing `Write-Error ... ; exit N` pattern
  in `build.ps1` which (with `$ErrorActionPreference = "Stop"`) does not actually
  emit the documented exit codes; the others are a fragile multi-line regex,
  a permissive substring check that under-constrains the importlib.metadata
  contract, and a `Get-ChildItem -Filter` that would over-match siblings of
  the dist-info.
- **4 INFOs** — minor terminology, dead-code-after-redirection, and one
  edge-case where `$LASTEXITCODE` can be stale after a "command not found"
  scenario.

## Blocker Issues

### BLK-01: `test_ensure_installed_runs_after_gst_init` is a vacuous assertion (false-pass invariant)

**File:** `tests/test_main_run_gui_ordering.py:45-52`

**Issue:** The test asserts that `Gst.init(None)` precedes
`desktop_install.ensure_installed(...)` by comparing `str.find()` positions:

```python
gst = _index(main_source, "Gst.init(None)")
ensure = _index(main_source, "desktop_install.ensure_installed(")
assert gst < ensure
```

`_index` (line 29) wraps `str.find`, which returns the **first** occurrence.
But `Gst.init(None)` appears in `__main__.py` at **line 33 inside `_run_smoke`**
(the headless harness) AND at line 167 inside `_run_gui`. The test docstring
and intent are about ordering inside `_run_gui` only. Because the
`_run_smoke` occurrence at line 33 wins the `find()`, the test compares
"`Gst.init` in `_run_smoke`" against "`ensure_installed` in `_run_gui`" —
two unrelated functions. The assertion is **always satisfied** regardless of
the order of those calls inside `_run_gui`.

A future refactor that deletes `Gst.init(None)` from `_run_gui` (or moves it
*after* `desktop_install.ensure_installed()` inside `_run_gui`) would still
pass this test, defeating its stated purpose.

The companion test `test_ensure_installed_runs_before_qapplication`
(line 35-42) is **safe** today by accident: `QApplication(` first appears at
line 185 inside `_run_gui` (line 106 says "QApplication is" without a paren,
and the `from PySide6.QtWidgets import QApplication` line 179 also has no
paren). If a future edit ever calls `QApplication(...)` somewhere earlier
in the file (e.g. another harness, a docstring example with a paren, or a
reordered import block), it would silently regress the same way.

**Fix:** Restrict the search window to the `_run_gui` function body so the
test asserts what its docstring claims.

```python
def _slice_run_gui(source: str) -> tuple[str, int]:
    """Return (run_gui_body, offset_into_source) — base-offset matters for
    accurate error messages and so byte positions within the slice can be
    re-mapped to the original file if needed."""
    start = source.find("def _run_gui(")
    assert start != -1, "could not locate _run_gui definition"
    # Slice ends at the next top-level def/class or EOF — _run_gui is
    # followed by `def main(`.
    end = source.find("\ndef ", start + 1)
    if end == -1:
        end = len(source)
    return source[start:end], start


def test_ensure_installed_runs_after_gst_init(main_source: str) -> None:
    body, base = _slice_run_gui(main_source)
    gst = body.find("Gst.init(None)")
    ensure = body.find("desktop_install.ensure_installed(")
    assert gst != -1, "Gst.init(None) missing from _run_gui"
    assert ensure != -1, "desktop_install.ensure_installed missing from _run_gui"
    assert gst < ensure, (
        "Gst.init(None) must precede desktop_install.ensure_installed() "
        "inside _run_gui. "
        f"Got Gst.init @ offset {gst}, ensure_installed @ offset {ensure}."
    )


def test_ensure_installed_runs_before_qapplication(main_source: str) -> None:
    body, _ = _slice_run_gui(main_source)
    ensure = body.find("desktop_install.ensure_installed(")
    qapp = body.find("QApplication(")
    assert ensure != -1 and qapp != -1
    assert ensure < qapp, ...


def test_set_application_version_in_run_gui(main_source: str) -> None:
    body, _ = _slice_run_gui(main_source)
    qapp = body.find("QApplication(argv)")
    setver = body.find("setApplicationVersion(")
    ...
```

This is a BLOCKER (not WARNING) because the test was added/updated in this
phase as the regression guard for the `setApplicationVersion` ordering
contract (D-07), and ships providing false confidence: any future
re-ordering that *should* trip it can slip through.

## Warning Issues

### WR-01: `Write-Error ... ; exit N` does not emit the documented exit code

**File:** `packaging/windows/build.ps1:51-52, 56-57, 62-63, 67-68, 107-109, 116-118, 148-150, 196-198, 205-207, 211-214, 219-222, 231-234, 236-243, 270-272, 277-280`

**Issue:** The script sets `$ErrorActionPreference = "Stop"` at line 15 and
documents an exit-code mapping in the header (`0=ok, 1=env missing,
2=pyinstaller failed, ...8=pre-bundle clean fail, 9=post-bundle dist-info
assertion fail`). All failure paths use the pattern:

```powershell
Write-Error "BUILD_FAIL reason=..."
exit N
```

In Windows PowerShell 5.1 with `$ErrorActionPreference = "Stop"`,
`Write-Error` is escalated to a **terminating** error. The error propagates
out of the surrounding `try { ... } finally { Pop-Location }` block (line
80-292) as an unhandled exception, after which PowerShell exits the script.
The numeric `exit N` line that follows `Write-Error` is **never executed** —
the script's final `$LASTEXITCODE` is `1` (PowerShell's default for an
unhandled terminating error), not the `8` or `9` that the comments and
header advertise.

This means CI / wrapper scripts that branch on `$LASTEXITCODE` (e.g.
"exit 9 → re-run with `--SkipPipInstall:$false`" or "exit 8 → check
`uv pip` install logs") cannot do so today. Phase 65 Plan 04 explicitly
introduces codes 8 and 9 with this pattern (`exit 8` at 150, `exit 9` at
214/222/234/243), and the post-bundle assertion test
(`tests/test_packaging_spec.py:188, 252-256`) asserts the literal `"exit 8"`
/ `"exit 9"` substrings are present in the script — but neither test
verifies those codes are actually emitted on failure.

**Fix:** Use `throw` + a top-level `try/catch` that maps the message to
`exit N`, OR `Write-Host "BUILD_FAIL reason=..."` (so the message still
prints) followed by `exit N` (so the documented code is actually returned).
The latter is the smaller change:

```powershell
# Replace
Write-Error "BUILD_FAIL reason=post_bundle_distinfo_not_singleton ..."
exit 9

# With (use Write-Host so it is not promoted to terminating under Stop)
Write-Host "BUILD_FAIL reason=post_bundle_distinfo_not_singleton ..." -ForegroundColor Red
exit 9
```

Or, if the loud red Write-Error rendering is wanted, override the preference
locally:

```powershell
$ErrorActionPreference = "Continue"
Write-Error "BUILD_FAIL reason=..."
exit 9
```

If you adopt the `Write-Host` form, also extend the test_packaging_spec.py
assertions to grep for the `BUILD_FAIL reason=...` rationale strings, not
just `exit 9`, so the failure-path semantics are pinned (today the test
does not catch a future edit that prints a Write-Error and reaches the exit
in a different code path).

### WR-02: pyproject.toml `version` regex is fragile to ordering of TOML sections

**File:** `packaging/windows/build.ps1:192-198`

**Issue:** `$pyproject -match '(?ms)^\[project\].*?^version\s*=\s*"([^"]+)"'`
uses multiline + singleline mode and a lazy `.*?` to find the first
`^version` line **after** `^[project]`. This works today because pyproject
.toml has `version = "2.1.65"` on line 7 immediately after `[project]` on
line 5. However:

1. If a future edit moves a `[project.optional-dependencies]` table or any
   other key with a sub-key named `version` between `[project]` and the
   actual version line (e.g. `[project.urls] homepage = "..."` followed by
   a typo'd `version = ...`), the regex matches the **wrong** line because
   `.*?` is lazy and picks the first `^version` it finds.
2. The regex does NOT enforce that the `version =` line is still inside the
   `[project]` table — it would match a `version = "..."` in any
   subsequent table if `[project]` had no `version` key at all.

A second, related concern: TOML allows the version to be specified with
single quotes (`version = '2.1.65'`) or as a triple-quoted basic string,
which the `"([^"]+)"` capture would silently fail to match — exit 5 fires
("version_not_found_in_pyproject") even though the file is well-formed.

**Fix:** Anchor the match more tightly so it must immediately follow
`[project]` (no other keys/tables between), and emit a clearer diagnostic
on miss. Use a TOML-aware match if possible:

```powershell
# Stricter — version must be in the contiguous block of `[project]` keys
# (i.e. before any other `^[...]` table header).
if ($pyproject -match '(?ms)^\[project\][^\[]*?^version\s*=\s*"([^"]+)"') {
    $appVersion = $matches[1]
} else {
    Write-Host "BUILD_FAIL reason=version_not_found_in_pyproject hint='expected ^version = \"...\" inside [project] before any subsequent table'" -ForegroundColor Red
    exit 5
}
```

The `[^\[]*?` (lazy non-`[`) ensures the lazy match cannot cross into a
sibling table. If single-quoted TOML strings need to be supported, add a
second regex branch.

### WR-03: `setApplicationVersion` source-of-truth check matches any `version(` call

**File:** `tests/test_main_run_gui_ordering.py:75-80`

**Issue:** The D-07 contract test allows the importlib import-and-call to
appear under either of two tokens:

```python
nearby = main_source[setver : setver + 200]
assert "_pkg_version(" in nearby or "version(" in nearby, ...
```

The bare token `version(` is a strict subset of MANY plausible non-importlib
calls. For example, a regression that imports a stub from elsewhere:

```python
from packaging.version import version  # imports a different `version` fn
...
app.setApplicationVersion(version("1.0"))
```

would still match `"version("` in the 200-byte window — the test passes
even though pyproject.toml is no longer the source of truth. (`packaging` is
already an indirect dependency of pip and is commonly available in the venv.)

The earlier assertion `"from importlib.metadata import" in main_source`
(line 71) does not bind that import to the call site — any unrelated future
import like `from importlib.metadata import distributions` would satisfy it.

**Fix:** Either (a) tighten the `nearby` check to require the importlib
helper specifically, or (b) parse the AST and walk the call site:

```python
# (a) tighter substring check
assert "_pkg_version(" in nearby or "metadata.version(" in nearby, (
    "setApplicationVersion(...) must read via importlib.metadata.version "
    "(not a literal string or a different `version` symbol). Got setter "
    f"context: {nearby!r}"
)

# Pin the import to the specific symbol we use, not the module:
assert (
    "from importlib.metadata import version" in main_source
    or "from importlib.metadata import version as _pkg_version" in main_source
), "musicstreamer/__main__.py must import `version` from importlib.metadata"
```

### WR-04: `Get-ChildItem -Filter "musicstreamer-*.dist-info"` over-matches subpackages

**File:** `packaging/windows/build.ps1:209`

**Issue:** The post-bundle singleton check uses a wildcard:

```powershell
$msDistInfos = @(Get-ChildItem -Path $bundleInternal -Filter "musicstreamer-*.dist-info" -Directory -ErrorAction SilentlyContinue)
```

The wildcard `musicstreamer-*` matches the version-suffixed dist-info dir
the build expects (`musicstreamer-2.1.65.dist-info`) but **also** matches
any future sibling like `musicstreamer-extras-1.0.0.dist-info`,
`musicstreamer-cli-...dist-info`, or a stale rename like
`musicstreamer-old.dist-info`. Today there is no such sibling, but the
check's failure mode if one ever appears is a hard `exit 9`
("not_singleton") even when the canonical `musicstreamer-X.Y.Z.dist-info`
is present and correct — i.e. a false-positive build break.

The matching dist-info filename pattern PEP 376 specifies is
`<name>-<version>.dist-info` where `<name>` may legitimately contain
letters/digits/dots/underscores/dashes (post-PEP 503 normalization). A
sibling distribution named `musicstreamer_extras` would normalize to
`musicstreamer-extras` for the dist-info dir name and trip this filter.

**Fix:** Filter on a tighter pattern — exact normalized name plus a
version-shaped suffix — and verify the bundled name matches the version
the script just read from pyproject.toml:

```powershell
# Either: tighter wildcard restricting the suffix to the version we expect
$expectedDistInfoName = "musicstreamer-$appVersion.dist-info"
$msDistInfos = @(Get-ChildItem -Path $bundleInternal -Filter $expectedDistInfoName -Directory -ErrorAction SilentlyContinue)

# Or: enumerate all `musicstreamer-*.dist-info` and reject names that
# contain an extra `-` segment (e.g. `musicstreamer-extras-1.0.0`):
$msDistInfos = @(Get-ChildItem -Path $bundleInternal -Filter "musicstreamer-*.dist-info" -Directory -ErrorAction SilentlyContinue) |
    Where-Object { $_.Name -match '^musicstreamer-\d+\.\d+\.\d+\.dist-info$' }
```

The first form is preferable — it doubles as the version-match check and
collapses two assertions (singleton + version-match) into one filename
comparison.

## Info

### IN-01: `_index()` docstring/error message mislabels character offsets as "byte" positions

**File:** `tests/test_main_run_gui_ordering.py:38-42, 48-52, 62-66`

**Issue:** Error messages say "Got ensure_installed @ byte {ensure}". `find()`
on a `str` returns a **character** offset, not a byte offset. The file
contains multi-byte UTF-8 codepoints (`—` em-dash on lines 25, 117, 197,
etc.; `…` ellipsis), so the character offset and byte offset diverge in any
realistic regression-message debug session.

**Fix:** Replace "byte" with "char" in the assertion messages. No code
change needed beyond the message strings.

### IN-02: `Invoke-Native` ErrorRecord-stringification is dead code when callers use `2>&1 | Out-Host`

**File:** `packaging/windows/build.ps1:28-38, 70, 86, 91-97, 105, 114, 141, 146, 155, 274-276`

**Issue:** The `Invoke-Native` wrapper documents (lines 22-27) that it
stringifies `ErrorRecord` objects to plain strings to avoid the red "command :
message / At ... char:NN" host rendering. The callers, however, all pipe
their output through `2>&1 | Out-Host` **inside** the script block (e.g.
line 86: `Invoke-Native { python -c "..." 2>&1 | Out-Host }`). By the time
the outer `& $Block | ForEach-Object { ... }` pipeline sees output,
`Out-Host` has already consumed and rendered it — the `ForEach-Object`
receives nothing, and the ErrorRecord stringification branch never fires.

This isn't a bug (the desired clean output is obtained because the inner
`2>&1` redirects stderr to the success stream before Out-Host renders it),
but the wrapper's stringification logic is then load-bearing only for the
two callers that DON'T do `2>&1 | Out-Host` (line 70 `gst-inspect-1.0.exe
--version | Select-String "version"`, and lines 274-276 `iscc.exe ... |
Tee-Object`). Worth either documenting that subset or simplifying the
wrapper to a plain `try/finally` ErrorAction-toggle.

**Fix:** Add a comment to `Invoke-Native` clarifying that the
ErrorRecord-stringification branch only matters for callers that do **not**
pre-render via `Out-Host` inside their block, OR remove the
ForEach-Object branch and rely on the caller-side `2>&1 | Out-Host` pattern
uniformly.

### IN-03: `$LASTEXITCODE` may be stale if a native command is "command not found" inside `Invoke-Native`

**File:** `packaging/windows/build.ps1:140-150`

**Issue:** Inside `Invoke-Native { uv pip install -e ..\.. 2>&1 | Out-Host }`
(line 146), if `uv` is not on PATH the call fails before ever launching a
process. With `$ErrorActionPreference = "Continue"` (set inside
Invoke-Native), the resulting CommandNotFoundException is captured by
`2>&1` and rendered, but `$LASTEXITCODE` is **not** updated — it retains
the value from the previous native command (line 141's `uv pip uninstall
musicstreamer -y`, which the script has explicitly noted may legitimately
return non-zero on a fresh env). If uninstall happens to have returned 0,
the install-side check at line 147 (`if ($LASTEXITCODE -ne 0)`) sees 0 and
proceeds to PyInstaller — which then fails at step 4a because no fresh
dist-info was materialized. Diagnostics for the operator would be
"post_bundle_distinfo_not_singleton" with no hint that uv was missing.

This is unlikely on a real build VM but worth a sanity check.

**Fix:** Verify uv before the install line, or wrap in a try/catch that
distinguishes "command not found" from "non-zero exit":

```powershell
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "BUILD_FAIL reason=uv_missing hint='install uv (https://docs.astral.sh/uv/) before running build.ps1'" -ForegroundColor Red
    exit 8
}
```

### IN-04: `Set-StrictMode -Version Latest` + `$msDistInfos[0]` after `@()` is fine, but `_act_node_missing` field is conditionally created

**File:** `musicstreamer/ui_qt/main_window.py:225-230`

**Issue:** The `_act_node_missing` attribute is only assigned inside the
`if self._node_runtime is not None and not self._node_runtime.available`
branch. Any code path that later does `self._act_node_missing` — including
test introspection or future code that wants to update the indicator — will
hit `AttributeError` when Node IS available. There are no current readers,
so this is purely a forward-compat hazard and an inconsistency with
self.\_act\_stats / self.\_act\_export / etc., all of which are
unconditionally assigned.

**Fix:** Initialize `self._act_node_missing = None` outside the `if`, and
gate any future logic on `is not None`. No behavior change today; cheap
hygiene.

```python
self._act_node_missing = None
if self._node_runtime is not None and not self._node_runtime.available:
    self._menu.addSeparator()
    self._act_node_missing = self._menu.addAction(
        "⚠ Node.js: Missing (click to install)"
    )
    self._act_node_missing.triggered.connect(self._on_node_install_clicked)
```

---

_Reviewed: 2026-05-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
