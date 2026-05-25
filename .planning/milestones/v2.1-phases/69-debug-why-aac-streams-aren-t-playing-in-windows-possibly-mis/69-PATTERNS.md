# Phase 69: Debug why AAC streams aren't playing in Windows — Pattern Map

**Mapped:** 2026-05-11
**Files analyzed:** 7 (2 NEW, 5 MODIFY)
**Analogs found:** 7 / 7 (all have exact or strong role-match analogs in-tree)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tools/check_bundle_plugins.py` (NEW) | build-time guard (CLI tool) | file-I/O + exit-code signaling | `tools/check_subprocess_guard.py` | exact (same role, same data flow, same exit-code convention) |
| `packaging/windows/build.ps1` post-bundle plugin guard block (MODIFY — NEW BLOCK after line 283) | PowerShell driver step (calls Python guard) | request-response (`Invoke-Native` + `$LASTEXITCODE`) | `packaging/windows/build.ps1:111-121` (PKG-03 invocation) + `build.ps1:203-283` (post-bundle dist-info assertion structural slot) | exact (two complementary analogs: invocation shape from PKG-03 line 111-121; structural slot from post-bundle assertion 203-283) |
| `packaging/windows/build.ps1:5-6` exit-code header (MODIFY — add code 10) | config/header comment | docstring/literal text | `packaging/windows/build.ps1:4-6` itself (extend existing list) | self-analog (same file, append-in-place) |
| `packaging/windows/README.md:18-22` conda recipe (MODIFY — add 5 plugin packages) | config recipe (PowerShell fenced block in markdown) | static documentation | `packaging/windows/README.md:14-28` itself (extend existing PowerShell fence) | self-analog (same file, edit-in-place) |
| `tests/test_packaging_spec.py` drift-guard extensions (MODIFY — 2 new test functions) | unit test (drift guard) | file-read + literal substring assertions | `tests/test_packaging_spec.py::test_build_ps1_post_bundle_dist_info_assertion_present` (build.ps1 drift guard) + `tests/test_constants_drift.py::test_dev_launch_script_app_id_matches_constants` (cross-file literal parity) | exact (same file, same fixture pattern, same `Path(__file__).resolve().parent.parent` idiom) |
| `.planning/codebase/CONCERNS.md:56-59` (MODIFY — DOC-01 reconciliation) | static documentation | edit-in-place | `CONCERNS.md` itself (preserve section structure) | self-analog |
| `.planning/REQUIREMENTS.md` (MODIFY — add WIN-05 row to Windows Polish + Traceability) | static documentation | edit-in-place | `REQUIREMENTS.md:26-33` (Windows Polish section) + `REQUIREMENTS.md:79-104` (Traceability table) | self-analog (extend existing list + table) |
| `69-UAT-LOG.md` (NEW) | operator-driven attestation log | manual narrative + PASS/FAIL stanzas | `.planning/phases/56-windows-di-fm-smtc-start-menu/56-05-UAT-LOG.md` | exact (Phase 56 D-08 force-fresh-install single-pass pattern is the explicit referent per CONTEXT V-01) |

---

## Pattern Assignments

### `tools/check_bundle_plugins.py` (NEW — build-time guard, file-I/O + exit-code)

**Analog:** `tools/check_subprocess_guard.py` (the closest structural match in-tree). Secondary cross-reference: `tools/check_spec_entry.py` (same shape, simpler logic — proves the pattern generalizes).

**Module docstring + exit code convention** (analog: `tools/check_subprocess_guard.py:1-13`):
```python
"""Build-time PKG-03 guard (Phase 44, D-22).

Walks musicstreamer/ and fails if any bare subprocess.{Popen,run,call} call
appears outside the single legitimate site (subprocess_utils.py). Mirrors
the build.ps1 ripgrep guard semantically; runs cross-platform (Linux dev,
Windows build VM) so the same check works in both contexts.

Exit codes:
    0 — clean (zero bare subprocess.* calls)
    4 — violations found (matches build.ps1 exit code convention, D-22)

Callable as ``python tools/check_subprocess_guard.py`` from the repo root.
"""
```

**Imports + repo-root resolver** (analog: `tools/check_subprocess_guard.py:14-25`):
```python
from __future__ import annotations

import re
import sys
from pathlib import Path

_FORBIDDEN = re.compile(r"\bsubprocess\.(Popen|run|call)\b")


def _repo_root() -> Path:
    # tools/check_subprocess_guard.py → repo root is parent.parent.
    return Path(__file__).resolve().parent.parent
```

**Main entry point + exit code branching** (analog: `tools/check_subprocess_guard.py:28-63`):
```python
def main() -> int:
    root = _repo_root() / "musicstreamer"
    if not root.is_dir():
        print(f"PKG-03 FAIL: musicstreamer/ not found at {root}", file=sys.stderr)
        return 4

    offenders: list[str] = []
    # ... build offenders list ...

    if offenders:
        print("PKG-03 FAIL: bare subprocess.{Popen,run,call} found outside subprocess_utils.py")
        for hit in offenders:
            print(f"  {hit}")
        sys.exit(4)

    print("PKG-03 OK: zero bare subprocess.* calls in musicstreamer/")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

**Pattern to copy verbatim:**
1. Module docstring with `Exit codes:` block listing 0=clean and the file's specific failure code (Phase 69 uses 10 per G-04).
2. `from __future__ import annotations`, `import sys`, `from pathlib import Path` triplet.
3. Module-level constant for the "what's required" mapping (analog has `_FORBIDDEN` regex; Phase 69 has `REQUIRED_PLUGIN_DLLS` dict per RESEARCH §"Plugin → conda-forge package map" and CONTEXT G-02).
4. `_repo_root()` helper using `Path(__file__).resolve().parent.parent` (drop-in copy from analog).
5. `def main() -> int:` returning int (NOTE: analog uses `sys.exit(N)` inside main; new file follows RESEARCH Pattern 2 which uses `return N` + `sys.exit(main())` in `__main__` — both shapes acceptable but RESEARCH Pattern 2 is the cleaner shape for argparse use).
6. `if __name__ == "__main__":` guard at bottom.

**Differences from analog (intentional):**
- Phase 69 helper takes `--bundle <path>` argparse arg (analog has no args — scans hardcoded `musicstreamer/`). Argparse import is required.
- Phase 69 helper scans a *directory of DLL files* (output of PyInstaller), not Python source — `is_file()` checks on filenames in a dict, not regex scans of source text.
- Phase 69 exit code is 10 (not 4) — matches build.ps1 exit code convention extension per G-04.

---

### `packaging/windows/build.ps1` post-bundle plugin-presence guard (MODIFY — NEW BLOCK after line 283)

**Two complementary analogs:**

**Analog A — Invocation shape** (`packaging/windows/build.ps1:111-121`, the PKG-03 guard):
```powershell
    # --- 3a. PKG-03 compliance guard (D-22) -----------------------------
    # SINGLE SOURCE OF TRUTH: tools/check_subprocess_guard.py (Plan 01).
    # This step invokes the Python tool — NOT a duplicated PowerShell Select-String regex
    # (per checker issue 6, eliminates drift between regex implementations).
    Write-Host "=== PKG-03 GUARD: subprocess.* usage scan (python tools/check_subprocess_guard.py) ==="
    Invoke-Native { python ..\..\tools\check_subprocess_guard.py 2>&1 | Out-Host }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "BUILD_FAIL reason=pkg03_guard hint='bare subprocess.* call detected; route through musicstreamer/subprocess_utils.py'" -ForegroundColor Red
        exit 4
    }
    Write-Host "PKG-03 OK"
```

**Analog B — Post-bundle structural slot** (`packaging/windows/build.ps1:198-283`, the post-bundle dist-info assertion):
```powershell
    # DO NOT REMOVE without first updating both:
    #   - tests/test_packaging_spec.py (drift-guard test)
    #   - .planning/phases/65-.../65-04-PLAN.md (this plan's rationale)
    Write-Host "=== POST-BUNDLE ASSERTION: musicstreamer dist-info singleton + version match ==="

    # ... ~80 lines of PowerShell asserting bundled dist-info shape ...
    # All BUILD_FAIL paths use Write-Host -ForegroundColor Red + exit 9 (per WR-01)

    Write-Host "POST-BUNDLE ASSERTION OK -- dist-info singleton: ..."
```

**Pattern to copy verbatim:**
1. Section header comment naming the phase + decision-ID (`# --- 4b. Post-bundle plugin-presence guard (Phase 69 / G-01) -------`).
2. **"DO NOT REMOVE without first updating both: tests/test_packaging_spec.py ... and the plan's rationale"** rationale block — exact pattern at `build.ps1:200-202` (the post-bundle assertion preserves this exact comment shape). Phase 69 G-01 cites the same files (tests + plan).
3. `Write-Host "=== POST-BUNDLE PLUGIN GUARD: ..."` step header (mirrors the `=== POST-BUNDLE ASSERTION:` header style at line 203 and `=== PKG-03 GUARD:` at line 115).
4. `Invoke-Native { python ..\..\tools\check_bundle_plugins.py --bundle ..\..\dist\MusicStreamer\_internal 2>&1 | Out-Host }` — exact clone of line 116 (PKG-03 invocation) with the bundle path arg added.
5. `if ($LASTEXITCODE -ne 0) { Write-Host "BUILD_FAIL reason=plugin_missing hint='...'" -ForegroundColor Red; exit 10 }` — exact clone of lines 117-120 with reason=`plugin_missing` (per RESEARCH "BUILD_FAIL reason=plugin_missing") and exit 10.
6. `Write-Host "POST-BUNDLE PLUGIN GUARD OK"` success-path mirror of line 121 `Write-Host "PKG-03 OK"`.

**Placement:** AFTER line 283 (`Write-Host "POST-BUNDLE ASSERTION OK ..."`) and BEFORE line 285 (`# --- 5. Smoke test ----`). The block is logically step `4b` (extends step 4 the way 3a/3b extend step 3).

**Critical conventions (Phase 65 WR-01) — MUST be preserved:**
- BUILD_FAIL diagnostics use `Write-Host ... -ForegroundColor Red` NOT `Write-Error`. Documented at `build.ps1:18-27` and locked by the drift-guard pytest at `test_packaging_spec.py:236-260`.
- The `exit N` line must immediately follow the diagnostic Write-Host inside the same `if` block — never bare-fall-through.
- Use `Invoke-Native { ... 2>&1 | Out-Host }` wrapper for the python invocation (handles PowerShell 5.1 stderr-trap; rationale at `build.ps1:29-49`).

---

### `packaging/windows/build.ps1:5-6` exit-code header (MODIFY — add exit code 10)

**Analog:** the existing comment block itself at `packaging/windows/build.ps1:1-6`:
```powershell
#Requires -Version 5.1
# Phase 44 MusicStreamer Windows build driver. Idempotent, snapshot-safe.
# Adapted from .planning/phases/43-gstreamer-windows-spike/build.ps1.
# Exit codes: 0=ok, 1=env missing, 2=pyinstaller failed, 3=smoke test failed,
#             4=PKG-03 guard fail, 5=version parse fail, 6=iscc fail, 7=spec entry guard fail,
#             8=pre-bundle clean fail, 9=post-bundle dist-info assertion fail
```

**Pattern to copy:** append `, 10=post-bundle plugin-presence guard fail` to the existing list (per RESEARCH §"Example 3: Updated exit-code header comment"). The exact form (from RESEARCH line 605-609):
```powershell
# Exit codes: 0=ok, 1=env missing, 2=pyinstaller failed, 3=smoke test failed,
#             4=PKG-03 guard fail, 5=version parse fail, 6=iscc fail, 7=spec entry guard fail,
#             8=pre-bundle clean fail, 9=post-bundle dist-info assertion fail,
#             10=post-bundle plugin-presence guard fail (Phase 69)
```

The trailing `(Phase 69)` annotation matches the existing line 2 convention (`Phase 44 MusicStreamer Windows build driver`) — orient future readers to the phase that introduced the code.

---

### `packaging/windows/README.md:14-28` conda recipe (MODIFY — DOC-02)

**Analog:** the existing PowerShell fenced block at `packaging/windows/README.md:14-28`:
```markdown
1. **Miniforge / conda-forge environment** — create once on the build VM:
   ```powershell
   conda create -n musicstreamer-build -c conda-forge `
       python=3.12 pygobject gstreamer=1.28 pyinstaller `
       "pyinstaller-hooks-contrib>=2026.2"
   conda activate musicstreamer-build
   ```
   The conda-forge GStreamer package ships the MSVC build with
   ...
```

**Pattern to copy (per RESEARCH lines 178-187):**
```markdown
1. **Miniforge / conda-forge environment** — create once on the build VM:
   ```powershell
   conda create -n musicstreamer-build -c conda-forge `
       python=3.12 pygobject gstreamer=1.28 `
       gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly `
       gst-libav `
       pyinstaller "pyinstaller-hooks-contrib>=2026.2"
   conda activate musicstreamer-build
   # AAC playback requires gst-libav (Phase 69 — provides avdec_aac in gstlibav.dll).
   # aacparse ships with gst-plugins-good's audioparsers plugin (gstaudioparsers.dll).
   ```
```

**Critical:**
- The `conda create -n musicstreamer-build` literal is the regex anchor for the new drift-guard pytest (P-01) per RESEARCH "Pitfall 5". Do NOT rename, rephrase, or move outside the fenced PowerShell block.
- Trailing comments inside the PowerShell fence are valid PowerShell and serve as the human-readable rationale linking back to the phase.
- Preserve the backtick-continuation (`` ` ``) shape (PowerShell line continuation) — drift-guard regex tolerates additional continuation lines but renaming the fence language to `bash` would break it.

---

### `tests/test_packaging_spec.py` drift-guard extensions (MODIFY — add 2 new test functions)

**Primary analog — same file:** `tests/test_packaging_spec.py::test_build_ps1_post_bundle_dist_info_assertion_present` at lines 295-401. This is the closest pattern in-tree for the new `test_build_ps1_invokes_plugin_guard_with_exit_10` test.

**Secondary analog — cross-file literal parity:** `tests/test_constants_drift.py::test_dev_launch_script_app_id_matches_constants` at lines 52-68 (reads a file, extracts a literal, asserts presence) — this is the closest pattern for the new `test_readme_conda_recipe_lists_every_required_plugin_package` drift guard.

**Module-level fixture pattern** (analog: `tests/test_packaging_spec.py:31-55`):
```python
from __future__ import annotations

from pathlib import Path

import pytest

_SPEC = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "MusicStreamer.spec"
)

_BUILD_PS1 = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "build.ps1"
)


@pytest.fixture(scope="module")
def spec_source() -> str:
    assert _SPEC.is_file(), f"expected MusicStreamer.spec at {_SPEC}"
    return _SPEC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def build_ps1_source() -> str:
    assert _BUILD_PS1.is_file(), f"expected build.ps1 at {_BUILD_PS1}"
    return _BUILD_PS1.read_text(encoding="utf-8")
```

**Pattern to copy — add new module-level path constant + fixture for README** (mirrors the `_BUILD_PS1` shape):
```python
_README = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "README.md"
)


@pytest.fixture(scope="module")
def readme_source() -> str:
    assert _README.is_file(), f"expected README.md at {_README}"
    return _README.read_text(encoding="utf-8")
```

**Drift-guard test pattern 1 — README↔required-plugin-list parity** (analog: `tests/test_constants_drift.py:52-68` cross-file literal parity + RESEARCH Pattern 3 example):
```python
def test_readme_conda_recipe_lists_every_required_plugin_package(
    readme_source: str,
) -> None:
    """Phase 69 / P-01: packaging/windows/README.md conda recipe must
    mention every conda-forge package referenced in
    tools/check_bundle_plugins.py REQUIRED_PLUGIN_DLLS values."""
    from tools.check_bundle_plugins import REQUIRED_PLUGIN_DLLS

    import re
    block_match = re.search(
        r"conda create -n musicstreamer-build[^\n]*\n((?:[^\n]*\n)+?)```",
        readme_source,
    )
    assert block_match, (
        "packaging/windows/README.md must contain a fenced PowerShell "
        "code block starting with `conda create -n musicstreamer-build`."
    )
    recipe_block = block_match.group(0)

    required_packages = {pkg for (_, pkg) in REQUIRED_PLUGIN_DLLS.values()}
    missing = [pkg for pkg in required_packages if pkg not in recipe_block]
    assert not missing, (
        f"Phase 69 / P-01 drift-guard FAIL: {missing} "
        "in REQUIRED_PLUGIN_DLLS but absent from README conda recipe."
    )
```

**Drift-guard test pattern 2 — build.ps1 invokes the new guard** (analog: `tests/test_packaging_spec.py:295-401` — clone the assertion shape exactly):

Key elements to clone from the analog (line-by-line):
1. **Rationale tag check** (analog line 314: `assert build_ps1_source.count("VER-02-J") >= 2`) → Phase 69 should assert the new step references its decision ID, e.g. `assert "G-01" in build_ps1_source` or `assert "plugin_missing" in build_ps1_source`.
2. **Tool invocation substring check** (analog has implicit through context; explicit shape: `assert "python ..\\..\\tools\\check_bundle_plugins.py" in build_ps1_source`).
3. **Exit code substring check** (analog line 353: `assert "exit 9" in build_ps1_source`) → Phase 69: `assert "exit 10" in build_ps1_source`.
4. **BUILD_FAIL reason substring** (analog line 368-374 lists `fail_reasons` tuple) → Phase 69: `assert "BUILD_FAIL reason=plugin_missing" in build_ps1_source`.
5. **WR-01 Write-Host adjacency check** (analog lines 380-393, the most subtle assertion):
   ```python
   idx = build_ps1_source.find("BUILD_FAIL reason=plugin_missing")
   assert idx != -1
   before = build_ps1_source[max(0, idx - 120) : idx + 50]
   assert "Write-Host" in before, (
       "must be emitted via `Write-Host ... -ForegroundColor Red` (NOT `Write-Error`)..."
   )
   after = build_ps1_source[idx : idx + 400]
   assert "exit 10" in after, (
       "`exit 10` must appear within the same failure block..."
   )
   ```

**Critical conventions (drift-guard test discipline):**
- Use `@pytest.fixture(scope="module")` (not function-scope) — analog precedent at line 46. Avoids re-reading the file for every test in the module.
- Module-level `_README = Path(__file__).resolve().parent.parent / ...` constant matches `_SPEC` and `_BUILD_PS1` at lines 31-43 verbatim.
- Test function naming: `test_<artifact>_<assertion>` shape (analog: `test_build_ps1_pre_bundle_clean_present`, `test_build_ps1_post_bundle_dist_info_assertion_present`) → Phase 69 uses `test_readme_conda_recipe_lists_every_required_plugin_package` and `test_build_ps1_invokes_plugin_guard_with_exit_10`.
- Assertion failure messages cite the phase + decision ID inline (analog line 174: `"build.ps1 must reference VER-02-J ..."`). Phase 69 cites WIN-05 / G-01 / P-01.

---

### `.planning/codebase/CONCERNS.md:56-59` (MODIFY — DOC-01 reconciliation)

**Analog:** the existing `CONCERNS.md` section at lines 55-59 itself. The file uses a `**Subject:**` + `- Issue: ...` + `- Files: ...` + `- Impact: ...` + `- Fix approach: ...` markdown-list shape per concern entry.

**Pattern to copy — preserve structure, replace the "Fix approach" line:**

Current (line 59):
```markdown
- Fix approach: Phase 44 bundling confirmed gst-libav is present in conda-forge build. Smoke test in PyInstaller build validates HLS playback. Before shipping any Windows release, always verify gst-libav presence in the bundle (conda list gst-libav or py -m pip list | grep gst-libav). Consider adding runtime check in runtime_check.py to warn user if expected GStreamer plugins are missing at startup.
```

Replacement (per CONTEXT DOC-01):
```markdown
- Fix approach: Phase 69 confirmed gst-libav was missing from the conda recipe shipped through v2.0–v2.1.0; the production conda-forge `gstreamer` meta-package does not pull in any `gst-plugins-*` subpackages. README recipe now explicitly lists `gst-libav gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly`; a post-bundle plugin-presence guard (`tools/check_bundle_plugins.py` invoked from `build.ps1` exit code 10) prevents future regressions, and a drift-guard pytest (`tests/test_packaging_spec.py::test_readme_conda_recipe_lists_every_required_plugin_package`) catches recipe↔required-list divergence on Linux dev CI before any Windows build is attempted.
```

**Why preserve structure:** the `- Issue / - Files / - Impact / - Fix approach` shape recurs throughout `CONCERNS.md` (every concern entry uses it). Drift-guard expectation: future maintainers reading the file expect each concern to have a "Fix approach" line documenting the current state.

---

### `.planning/REQUIREMENTS.md` (MODIFY — DOC-04, add WIN-05)

**Two edit sites:**

**Site 1 — Windows Polish section** (analog: `REQUIREMENTS.md:26-33`, the existing WIN-01..WIN-04 entries):
```markdown
### Windows Polish (WIN)

Phase 44 carry-forward — items deferred from the v2.0 ship line.

- [x] **WIN-01**: DI.fm premium streams play on Windows ...
- [ ] **WIN-02**: SMTC overlay shows "MusicStreamer" ...
- [x] **WIN-03**: Audio pause/resume on Windows produces no audible glitch; ...
- [x] **WIN-04**: `test_thumbnail_from_in_memory_stream` passes on Windows ...
```

**Pattern to copy — append new WIN-05 row to the list:**
```markdown
- [ ] **WIN-05**: AAC-encoded streams play on Windows — DI.fm AAC tier + SomaFM HE-AAC fixtures verified post-bundle-fix *(Phase 69)*
```

Use `[ ]` (unchecked) until phase complete; checkbox flips to `[x]` at `/gsd-complete-phase` time. Markdown list item shape matches WIN-01..WIN-04 verbatim. The trailing `*(Phase 69)*` italic-annotated phase reference matches the convention used at e.g. BUG-08 line 23 (`*(surfaced during Phase 50 UAT 2026-04-28)*`) and ACCENT-02 line 40 (`*(harvest: SEED-006)*`).

**Site 2 — Traceability table** (analog: `REQUIREMENTS.md:79-104`, the existing table):
```markdown
| Requirement | Phase | Status |
|-------------|-------|--------|
| BUG-07 | Phase 49 | ✓ Complete (no code change) |
...
| THEME-01 | Phase 66 | Complete |
```

**Pattern to copy — append new row after THEME-01:**
```markdown
| WIN-05 | Phase 69 | Pending |
```

Status string `Pending` matches the existing `Pending` row at line 93 (`| WIN-02 | Phase 56 | Pending |`); update to `Complete` at `/gsd-complete-phase` time.

Also update the Coverage tally at lines 106-110:
```markdown
**Coverage:**
- v2.1 requirements: 20 total       # was 19
- Mapped to phases: 20 ✓            # was 19
- Unmapped: 0 ✓
- Complete: 18
- Pending: 2 (WIN-02, WIN-05)       # was 1
```

---

### `69-UAT-LOG.md` (NEW — operator-driven attestation)

**Analog:** `.planning/phases/56-windows-di-fm-smtc-start-menu/56-05-UAT-LOG.md` (the explicit referent per CONTEXT V-01 / R-03 — "Phase 56 D-08 force-fresh-install single-pass UAT pattern").

**Top-of-file metadata header** (analog: `56-05-UAT-LOG.md:1-12`):
```markdown
# Phase 56 / Plan 05 — UAT Log

**Started:** 2026-05-02
**Path chosen:** **Path C** (python-m direct from current source) — operator decision per discussion in chat. Skips installer rebuild + force-fresh-install since:
- WIN-02 SMTC overlay is already PASS-attested in `56-03-DIAGNOSTIC-LOG.md` Step 3 ...

**Trade-off accepted:** Path C runs MusicStreamer outside the Start-Menu launch ...
```

**Pattern to copy** — start with the same metadata block, naming Phase 69's chosen path (single-pass installer-only per V-02):
```markdown
# Phase 69 — UAT Log

**Started:** <date when operator begins UAT>
**Path chosen:** Single-pass installer + force-fresh-install (Phase 56 D-08 pattern; CONTEXT V-01 / V-02).

**Pre-flight requirement:** Two AAC fixture URLs supplied at plan-check time (R-01):
- `FIXTURE_DI_FM_AAC = <paste>`
- `FIXTURE_SOMA_HE_AAC = <paste>`
```

**PASS/FAIL stanza shape per requirement** (analog: `56-05-UAT-LOG.md:14-31`, the WIN-02 attestation block):
```markdown
## WIN-02: SMTC overlay reads "MusicStreamer"

**Status:** **PASS** (cited from 56-03)

**Source of attestation:**
- `56-03-DIAGNOSTIC-LOG.md` § "D-08 Step 3 ..." — the SMTC overlay read literally `MusicStreamer` ...

**ROADMAP SC coverage:**
- ✓ SC #2: ...
- ✓ SC #3: ...
```

**Pattern to copy — Phase 69 stanzas** (R-01 / R-03 / V-01 sequencing per CONTEXT):
1. **WIN-05 Pre-fix baseline** (R-03): `**Status:** FAIL (baseline)` with the two fixture URLs and the observed "Playback error: ..." toast text.
2. **WIN-05 Build attestation**: `**Status:** BUILD_OK` with the `build.ps1` exit code, the post-bundle plugin guard PASS line (`POST-BUNDLE PLUGIN GUARD OK`), and the conda env audit (`conda list -n musicstreamer-build | findstr gst-` per RESEARCH Pitfall 2).
3. **WIN-05 Force-fresh-install attestation** (V-01): `**Status:** INSTALL_OK` with the uninstall + delete `%LOCALAPPDATA%\Programs\MusicStreamer` + delete LNK + reinstall (Run UNCHECKED) sequence per `56-05-UAT-LOG.md:102-113`.
4. **WIN-05 Post-install playback** (R-02): `**Status:** PASS` with two PASS lines (one per fixture URL), time-to-first-audio, observed ICY title.

**Release-Grade Re-attestation block** (analog: `56-05-UAT-LOG.md:102-113`, the force-fresh-install verbatim pattern):
```markdown
## Release-Grade Re-attestation (post `build.ps1` rebuild)

After the operator rebuilt the installer via `build.ps1` and force-fresh-installed (uninstall → delete `%LOCALAPPDATA%\Programs\MusicStreamer` + LNK → reinstall with Run checkbox UNCHECKED, preserving `%APPDATA%\musicstreamer` and `%LOCALAPPDATA%\musicstreamer`), the operator confirmed ...
```

This block name + structure is the exact V-01 referent. Phase 69 reuses verbatim with WIN-05 substituted for WIN-02.

**Phase Completion Decision block** (analog: `56-05-UAT-LOG.md:117-130`):
```markdown
## Phase Completion Decision

**Decision:** **ship-phase**

**Rationale:** All <N> ROADMAP success criteria are PASS on a release-grade install:
- ✓ SC #1 ...
```

Phase 69's success criteria are the WIN-05 single requirement (pre-fix FAIL → post-fix PASS for both fixtures) plus the build-time guard (BUILD_OK with exit 0).

---

## Shared Patterns

### Single-source-of-truth Python helper invoked from PowerShell

**Source:** `tools/check_subprocess_guard.py` + `tools/check_spec_entry.py` (the two existing instances) + `packaging/windows/build.ps1:111-129` (the invocation sites).

**Apply to:** the new `tools/check_bundle_plugins.py` + the new step `4b` in `build.ps1`.

**Concrete excerpt — Python side** (`tools/check_subprocess_guard.py:1-26`):
```python
"""Build-time PKG-03 guard (Phase 44, D-22). ...

Exit codes:
    0 — clean
    4 — violations found (matches build.ps1 exit code convention)

Callable as ``python tools/check_subprocess_guard.py`` from the repo root.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_FORBIDDEN = re.compile(r"\bsubprocess\.(Popen|run|call)\b")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent
```

**Concrete excerpt — PowerShell side** (`packaging/windows/build.ps1:115-121`):
```powershell
    Write-Host "=== PKG-03 GUARD: subprocess.* usage scan (python tools/check_subprocess_guard.py) ==="
    Invoke-Native { python ..\..\tools\check_subprocess_guard.py 2>&1 | Out-Host }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "BUILD_FAIL reason=pkg03_guard hint='...'" -ForegroundColor Red
        exit 4
    }
    Write-Host "PKG-03 OK"
```

---

### Write-Host (not Write-Error) for BUILD_FAIL diagnostics — WR-01 discipline

**Source:** `packaging/windows/build.ps1:18-27` (the rationale comment block) + lock test at `tests/test_packaging_spec.py:236-260` and lines 380-393.

**Apply to:** all new BUILD_FAIL paths in the Phase 69 G-01 block.

**Concrete excerpt — rationale** (`build.ps1:18-27`):
```powershell
# Phase 65 WR-01: BUILD_FAIL paths use `Write-Host ... -ForegroundColor Red`
# (NOT `Write-Error`) followed by `exit N`. With $ErrorActionPreference =
# "Stop", `Write-Error` is escalated to a TERMINATING error -- the script
# unwinds through the surrounding try/finally as an unhandled exception and
# PowerShell emits its default exit code 1, never reaching the documented
# `exit N` line that follows.
```

**Concrete excerpt — lock test pattern** (`test_packaging_spec.py:380-393` — clone for Phase 69 plugin_missing assertion):
```python
idx = build_ps1_source.find(reason)
before = build_ps1_source[max(0, idx - 120) : idx + 50]
assert "Write-Host" in before, (
    f"... must be emitted via `Write-Host ... -ForegroundColor Red` "
    "(NOT `Write-Error`). Write-Error escalates to a terminating error..."
)
after = build_ps1_source[idx : idx + 400]
assert "exit 9" in after, (
    "... `exit 9` must appear within the same failure block..."
)
```

---

### Invoke-Native wrapper for native commands under `$ErrorActionPreference = "Stop"`

**Source:** `packaging/windows/build.ps1:39-49` (the function definition).

**Apply to:** the new `python tools/check_bundle_plugins.py` invocation in step 4b.

**Concrete excerpt:**
```powershell
function Invoke-Native {
    param([scriptblock]$Block)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Block | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) { "$($_.Exception.Message)" }
            else { $_ }
        }
    } finally { $ErrorActionPreference = $prev }
}
```

**Why required:** Python's `print(..., file=sys.stderr)` writes to stderr; under `Stop` preference, native-command stderr is escalated to a terminating error. `Invoke-Native` swaps to `Continue`, lets the inner block run, and stringifies any ErrorRecord-shaped output the host would otherwise format red. RESEARCH Pitfall 4 documents the exact failure mode if this wrapper is omitted.

---

### Module-scoped fixture + `_repo_root` constant for file-read tests

**Source:** `tests/test_packaging_spec.py:31-55`.

**Apply to:** the new README reader fixture and the new test functions.

**Concrete excerpt:**
```python
_BUILD_PS1 = (
    Path(__file__).resolve().parent.parent
    / "packaging"
    / "windows"
    / "build.ps1"
)


@pytest.fixture(scope="module")
def build_ps1_source() -> str:
    assert _BUILD_PS1.is_file(), f"expected build.ps1 at {_BUILD_PS1}"
    return _BUILD_PS1.read_text(encoding="utf-8")
```

The `Path(__file__).resolve().parent.parent` idiom resolves the repo root from inside `tests/`. The fixture is `scope="module"` so the file is read once per test-module run, not once per test function. Use `assert _PATH.is_file()` (not `_PATH.exists()`) — analog precedent.

---

## No Analog Found

All 8 file targets have a strong analog in-tree. The closest the project comes to "no analog" is the operator-driven UAT-LOG.md template — which has a precise Phase 56 referent (`56-05-UAT-LOG.md`) named explicitly in CONTEXT V-01 / R-03.

| File | Reason |
|------|--------|
| (none) | All Phase 69 deliverables have exact or strong analogs documented above. |

---

## Metadata

**Analog search scope:**
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/tools/` (check_*.py files — Python build-time guards)
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/packaging/windows/` (build.ps1, README.md)
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/tests/test_packaging_spec.py` + `test_constants_drift.py` (drift-guard pytests)
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/phases/56-windows-di-fm-smtc-start-menu/56-05-UAT-LOG.md` (UAT-LOG analog)
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/codebase/CONCERNS.md` (DOC-01 edit site)
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/REQUIREMENTS.md` (DOC-04 edit site)

**Files scanned:** 9 source files (2 Python guards, 1 PowerShell driver, 1 markdown recipe, 2 test files, 1 UAT-LOG, 1 CONCERNS, 1 REQUIREMENTS).

**Pattern extraction date:** 2026-05-11.

**Key analog selection rationale:**
- `tools/check_subprocess_guard.py` chosen over `tools/check_spec_entry.py` as the primary Python-guard analog because the data flow (multi-item enumeration → set comparison → exit code) matches Phase 69's plugin-list check more closely than the spec-entry guard's single-literal substring check. Both are referenced; `check_subprocess_guard.py` is the closer match.
- `build.ps1:111-121` (PKG-03 invocation) chosen over `build.ps1:124-129` (spec entry guard invocation) for the invocation shape because the PKG-03 block includes a richer hint message and matches the "build-time guard" framing Phase 69 needs. Both are functionally equivalent invocations.
- `tests/test_packaging_spec.py::test_build_ps1_post_bundle_dist_info_assertion_present` chosen as primary test analog because it's in the same file Phase 69 extends AND it asserts on the same artifact (`build.ps1` text) AND it locks the same WR-01 discipline Phase 69 needs to lock. `tests/test_aumid_string_parity.py` was the originally-suggested analog but does not exist; the closest equivalent cross-file literal-parity test is `tests/test_constants_drift.py::test_dev_launch_script_app_id_matches_constants` (lines 52-68), which is now the secondary analog for the README↔required-list drift guard.
- `56-05-UAT-LOG.md` chosen as the UAT-LOG analog by explicit CONTEXT directive (V-01).
