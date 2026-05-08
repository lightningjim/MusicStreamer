# Phase 63: Auto-Bump pyproject Version on Phase Completion - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 7 (4 NEW, 3 MODIFIED)
**Analogs found:** 6 / 7 (one file — `.claude/hooks/bump-version-hook.sh` — has no in-repo bash analog; planner falls back to RESEARCH.md §Pattern 2 + §Code Examples 4–5)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tools/bump_version.py` | utility (CLI helper) | transform (file-I/O: read PROJECT.md / pyproject.toml, write pyproject.toml) | `tools/check_subprocess_guard.py` | exact (same role + same I/O pattern) |
| `tests/test_bump_version.py` | test (unit + drift-guard) | request-response (subprocess-driven CLI test + static drift checks) | `tests/test_constants_drift.py` (drift-guard half) + `tests/test_media_keys_smtc.py:140-167` (`tomllib`-based pyproject inspection) | exact (drift-guard); good (tomllib usage) |
| `.claude/settings.json` | config (Claude Code project hook registration) | event-driven (PreToolUse / PostToolUseFailure dispatch) | None in repo — `.claude/settings.local.json` is a different schema (permissions allowlist, no `hooks` block) | no analog → use RESEARCH.md §Pattern 2 verbatim |
| `.claude/hooks/bump-version-hook.sh` | utility (bash wrapper for hook protocol) | event-driven (stdin JSON payload → stdout JSON response) | `scripts/dev-launch.sh` (only for shell idiom: shebang, `set -euo pipefail`, `$REPO_ROOT` resolution) | partial (shape only, not content) → RESEARCH.md §Code Example 4–5 |
| `pyproject.toml` | config (build metadata) | CRUD (line-targeted regex rewrite by the helper itself) | n/a (modified by `bump_version.py` at runtime, not hand-edited) | n/a |
| `.planning/config.json` | config (workflow flag) | CRUD (direct JSON edit — `gsd-sdk` rejects unknown keys per Pitfall 3) | Existing `.planning/config.json:7-14` (`workflow` block — extend in place) | exact (same file, just adds a key) |
| `PROJECT.md` (`.planning/PROJECT.md`) | doc (versioning schema reference) | append-only (insert `## Versioning` section above `## Constraints` at line 223) | Existing section structure of `PROJECT.md` itself (`## Constraints` block at line 223; `## Phase History` at line 230) | exact (same file) |

---

## Pattern Assignments

### `tools/bump_version.py` (utility, file-I/O transform)

**Analog:** `tools/check_subprocess_guard.py`
**Why this analog:** Both helpers are `tools/`-resident CLI scripts that (a) read project files relative to the repo root, (b) report a result via stdout/stderr, and (c) `sys.exit(N)` with role-specific codes. `check_subprocess_guard.py` is closer to `bump_version.py` than `check_spec_entry.py` because the former actually walks/edits content with regex; the latter is a single literal substring check.

**Module docstring + exit-code documentation pattern** (`tools/check_subprocess_guard.py:1-13`):
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
**Apply to `bump_version.py`:** Same shape — top-line summary, what-it-does paragraph, **exit codes block**, then the `Callable as ...` line. Per RESEARCH.md §Standard Stack (Pattern 1) the exit-code set for `bump_version.py` is `0=success, 1=parse error (PROJECT.md or pyproject.toml), 2=regex no-match, 3=config disabled (D-11 short-circuit)`.

**Imports + `from __future__` pattern** (`tools/check_subprocess_guard.py:14-18`):
```python
from __future__ import annotations

import re
import sys
from pathlib import Path
```
**Apply to `bump_version.py`:** Identical block plus `import argparse` (D-03 mandates explicit args) and `import subprocess` (for the `gsd-sdk query config-get` call).

**Repo-root resolution helper** (`tools/check_subprocess_guard.py:23-25`):
```python
def _repo_root() -> Path:
    # tools/check_subprocess_guard.py → repo root is parent.parent.
    return Path(__file__).resolve().parent.parent
```
**Apply to `bump_version.py`:** Verbatim — same anchor (`__file__`), same `parent.parent` resolution. Project convention.

**Compiled module-level regex** (`tools/check_subprocess_guard.py:20`):
```python
_FORBIDDEN = re.compile(r"\bsubprocess\.(Popen|run|call)\b")
```
**Apply to `bump_version.py`:** Three module-level regexes (verified live in RESEARCH.md §Pattern 3 + §Pattern 4):
```python
_PROJECT_TABLE_RE = re.compile(r'^\[project\]\s*$', re.MULTILINE)
_NEXT_TABLE_RE = re.compile(r'^\[', re.MULTILINE)
_VERSION_LINE_RE = re.compile(r'^(version\s*=\s*)"[^"]*"(\s*)$', re.MULTILINE)
_MILESTONE_RE = re.compile(r'^##\s+Current Milestone:\s*v(\d+)\.(\d+)', re.MULTILINE)
```

**`main()` shape with explicit `sys.exit(N)`** (`tools/check_subprocess_guard.py:28-59`):
```python
def main() -> int:
    root = _repo_root() / "musicstreamer"
    if not root.is_dir():
        print(f"PKG-03 FAIL: musicstreamer/ not found at {root}", file=sys.stderr)
        return 4

    offenders: list[str] = []
    # ... main work loop ...

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
**Apply to `bump_version.py`:** Same shape — `def main() -> int`, status messages with a phase tag (e.g. `[bump] OK: ...` / `[bump] FAIL: ...`), `sys.exit(N)` with the documented codes, `if __name__ == "__main__": main()` at the bottom. Note the existing convention prints failures to **`stderr`** with `file=sys.stderr` (line 31, 43); follow it for `bump_version.py`'s error paths.

**Argparse surface** (no in-repo `tools/` analog has argparse, so use the canonical Python idiom from RESEARCH.md §Pattern 1):
```python
parser = argparse.ArgumentParser()
parser.add_argument("--phase", type=int, required=True)
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--pyproject", type=Path, default=None,
                    help="Override pyproject.toml path (test-only).")
parser.add_argument("--project-md", type=Path, default=None,
                    help="Override PROJECT.md path (test-only).")
args = parser.parse_args()
```
**Why explicit `--pyproject` / `--project-md` overrides:** RESEARCH.md §Pitfall 7 (helper invocation surface vs. test surface drift). Tests invoke via `subprocess.run([sys.executable, "tools/bump_version.py", "--phase", "42", "--pyproject", str(pyproject), "--project-md", str(project_md)], ...)` — same interface as the hook, with file-target overrides for `tmp_path` isolation.

**Subprocess call to `gsd-sdk query config-get`** (no in-repo helper makes a `gsd-sdk` subprocess call from Python; the canonical idiom is in RESEARCH.md §Code Example 3):
```python
result = subprocess.run(
    ["gsd-sdk", "query", "config-get", "workflow.auto_version_bump", "--raw"],
    cwd=repo_root,
    capture_output=True,
    text=True,
)
if result.returncode != 0:
    return True  # key not found → default true (D-10)
return result.stdout.strip() == "true"
```
**Project-style match:** Existing `subprocess.run(..., capture_output=True, text=True)` invocations in the codebase (e.g. `tests/test_media_keys_mpris2.py:221-224`) follow exactly this argument shape. `text=True` (not `encoding="utf-8"`) is the project convention.

---

### `tests/test_bump_version.py` (test, drift-guard + subprocess CLI)

**Analog A (drift-guard half):** `tests/test_constants_drift.py`
**Why this analog:** RESEARCH.md §Pitfall 2 explicitly cross-references `tests/test_constants_drift.py` as the established drift-guard pattern. The new test module needs a drift-guard for the `## Current Milestone:` heading regex (Pitfall 2), for the presence of `.claude/settings.json` and `.claude/hooks/bump-version-hook.sh` files (Pitfall 8), and for the presence of the `## Versioning` section in PROJECT.md (SC #4). All three mirror the assertion style in `test_constants_drift.py`.

**Module docstring + import pattern** (`tests/test_constants_drift.py:1-10`):
```python
"""Phase 61 D-02 drift guard: constants.APP_ID is the single source of truth.

These tests fail loud if the .desktop file basename or icon basename ever
drifts away from constants.APP_ID, or if the org.example.MusicStreamer
placeholder leaks back into musicstreamer/ Python sources. Runs in <100ms;
addresses the silent-failure mode flagged by RESEARCH.md §Pitfall 6.
"""
from pathlib import Path

from musicstreamer import constants
```
**Apply to `test_bump_version.py`:** Same shape — phase tag in title, "fail loud if X drifts" framing, runtime budget callout. Replace `from musicstreamer import constants` with `from pathlib import Path` + `import re` + `import subprocess` + `import sys` (since the helper isn't in the runtime package).

**Drift-guard assertion style** (`tests/test_constants_drift.py:18-27`):
```python
def test_bundled_desktop_basename_matches_app_id():
    """packaging/linux/<APP_ID>.desktop must exist."""
    pkg_dir = Path(__file__).parent.parent / "packaging" / "linux"
    expected = pkg_dir / f"{constants.APP_ID}.desktop"
    assert expected.exists(), (
        f"Bundled .desktop name must match constants.APP_ID. "
        f"Looked for: {expected}. "
        f"Found .desktop files in {pkg_dir}: "
        f"{sorted(p.name for p in pkg_dir.glob('*.desktop'))}"
    )
```
**Apply to `test_bump_version.py`:** Mirror this idiom for three tests:
1. `test_project_md_milestone_heading_present` — assert `re.search(r'^##\s+Current Milestone:\s*v\d+\.\d+', PROJECT.md, re.MULTILINE)` matches.
2. `test_hook_files_committed` — assert `Path(".claude/settings.json").exists()` and `Path(".claude/hooks/bump-version-hook.sh").exists()` (Pitfall 8 guard).
3. `test_project_md_has_versioning_section` — assert PROJECT.md contains `## Versioning` heading (SC #4).

**Path resolution from a test file** (`tests/test_constants_drift.py:20`, `tests/test_constants_drift.py:39`):
```python
pkg_dir = Path(__file__).parent.parent / "packaging" / "linux"
pkg_root = Path(__file__).parent.parent / "musicstreamer"
```
**Apply to `test_bump_version.py`:** Same `Path(__file__).parent.parent / <name>` idiom. Repo root from a test is `Path(__file__).resolve().parent.parent`.

---

**Analog B (`tomllib` half):** `tests/test_media_keys_smtc.py:140-167`
**Why this analog:** CONTEXT canonical_refs explicitly names this module as the `tomllib` reference (`tests/test_media_keys_smtc.py:9,148`). Verifying that the post-bump pyproject.toml is *parseable as TOML* (not just regex-matched) is a useful belt-and-braces check.

**`tomllib` usage** (`tests/test_media_keys_smtc.py:140-156`):
```python
def test_pyproject_has_windows_optional_deps():
    """D-05: [project.optional-dependencies].windows lists the four pywinrt packages."""
    repo_root = Path(__file__).resolve().parent.parent
    pyproject = repo_root / "pyproject.toml"
    assert pyproject.is_file(), f"expected pyproject.toml at {pyproject}"

    with open(pyproject, "rb") as f:
        data = tomllib.load(f)

    optional = data["project"]["optional-dependencies"]
    assert "windows" in optional, "expected [project.optional-dependencies].windows group (D-05)"
```
**Apply to `test_bump_version.py`:** Use the same `with open(pyproject, "rb") as f: data = tomllib.load(f)` shape in `test_bump_rewrites_version_within_project_block` to verify the bumped string parses cleanly **and** `data["project"]["version"] == "3.7.42"`. Note: open the file in **binary mode** (`"rb"`) — `tomllib.load` requires binary, never text-mode. Do NOT add `tomllib` writes; per D-06 it's read-only.

---

**Analog C (subprocess-CLI test half):** `tests/test_media_keys_mpris2.py:221-224`
**Why this analog:** Only existing test in the suite that invokes a subprocess CLI tool with `subprocess.run(..., capture_output=True, text=True)` and asserts on stdout content. Pattern matches the way `test_bump_version.py` will invoke `python tools/bump_version.py` (per RESEARCH.md §Pitfall 7 — same surface as the hook).

**Subprocess invocation pattern** (`tests/test_media_keys_mpris2.py:221-227`):
```python
result = subprocess.run(
    ["playerctl", "--list-all"],
    capture_output=True, text=True, timeout=2,
)
assert "musicstreamer" in result.stdout, (
    f"Expected 'musicstreamer' in playerctl output, got: {result.stdout!r}"
)
```
**Apply to `test_bump_version.py`:** Identical shape; substitute `[sys.executable, str(repo_root / "tools" / "bump_version.py"), "--phase", "42", "--pyproject", str(pyproject), "--project-md", str(project_md)]` for the command vector. Keep `capture_output=True, text=True`. Add `timeout=10` (file I/O + a `gsd-sdk` subprocess; 10s is generous). Assert on `result.returncode` first (per RESEARCH.md §Code Example 6: `assert result.returncode == 0, result.stderr`), then on file content.

**`tmp_path` + write fake pyproject + write fake PROJECT.md** (no exact in-repo analog for "synthesize a pyproject under tmp_path"; closest shape is `tests/test_desktop_install.py:33-38`):
```python
bundled_desktop = tmp_path / "bundled.desktop"
bundled_desktop.write_text(
    "[Desktop Entry]\nName=MusicStreamer\nType=Application\n"
)
```
**Apply to `test_bump_version.py`:** Same `tmp_path / "name"` + `.write_text(..., encoding="utf-8")` pattern. RESEARCH.md §Code Example 6 already shows the full idiom verbatim — copy it.

**`monkeypatch.setenv("PATH", ...)` for stub `gsd-sdk`** (`tests/test_desktop_install.py:18-26` shows the `monkeypatch` style for env overrides):
```python
@pytest.fixture(autouse=True)
def _redirect_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg_data"))
    saved = paths._root_override
    paths._root_override = str(tmp_path / "data")
    try:
        yield
    finally:
        paths._root_override = saved
```
**Apply to `test_bump_version.py`:** For the "flag disabled" test (RESEARCH.md §Code Example 6, `test_bump_skipped_when_flag_disabled`), use `monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")` to inject a stub `gsd-sdk` shell script that returns `false`. Note: the existing project pattern uses `monkeypatch` (not raw `os.environ`); that's the right tool here.

---

### `.claude/settings.json` (config, Claude Code hook registration)

**Analog:** None in this repo — `.claude/settings.local.json` is a permissions-allowlist file with no `hooks` block. The skill at `.claude/skills/spike-findings-musicstreamer/` is a skill definition, not a hook config.

**Use RESEARCH.md verbatim:** §Pattern 2 worked example (verified live against `code.claude.com/docs/en/hooks` in this session):
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(gsd-sdk query commit *)",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/bump-version-hook.sh",
            "timeout": 30
          }
        ]
      }
    ],
    "PostToolUseFailure": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(gsd-sdk query commit *)",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/bump-rollback-hook.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```
**Project-specific note:** Top-level `.claude/` is gitignored (`.gitignore:23`). The plan task that adds this file MUST use `git add -f .claude/settings.json` (Pitfall 8). Mirror what was done previously for `.claude/skills/spike-findings-musicstreamer/SKILL.md` etc. (which appear in `git ls-files .claude/`).

---

### `.claude/hooks/bump-version-hook.sh` (utility, bash hook wrapper)

**Analog (shape only):** `scripts/dev-launch.sh`
**Why this analog:** Only checked-in bash script in the repo with the canonical project shebang + safety-flags + repo-root resolution. The script's *content* is unrelated (systemd-scope wrapping for GNOME mutter), but the *shape* — shebang, header comment, `set -euo pipefail`, `REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"` — is the in-repo bash convention.

**Shebang + header comment + safety flags** (`scripts/dev-launch.sh:1-30`):
```bash
#!/usr/bin/env bash
# Phase 61 Plan 05 dev launcher.
#
# Wraps the dev-venv musicstreamer invocation in a transient systemd user
# scope named after our app id, ...
# ...

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
```
**Apply to `bump-version-hook.sh`:**
- Same shebang `#!/usr/bin/env bash`
- Header comment in the same style: phase tag + 2-3 sentence what/why summary
- `set -euo pipefail` immediately after the header
- For repo root: prefer the Claude Code-supplied `$CLAUDE_PROJECT_DIR` env var (verified in RESEARCH.md §Pattern 2) over a `$(cd ... && pwd)` derivation, since Claude Code provides it and this script lives at `.claude/hooks/` not `scripts/`. Fall back to `"$(cd "$(dirname "$0")/../.." && pwd)"` only if `$CLAUDE_PROJECT_DIR` is unset.

**Hook-specific content (no in-repo analog):** Use RESEARCH.md §Pattern 2 (lines 197-231) verbatim for the bump-version-hook.sh body:
- Read JSON payload from stdin via `PAYLOAD=$(cat)` + `jq -r '.tool_input.command' <<< "$PAYLOAD"`
- Regex-extract phase number with `grep -oP 'docs\(phase-\K[0-9]+(?=\): complete phase execution)'`
- If no match: `exit 0` (let unrelated `gsd-sdk query commit *` calls through unmodified)
- If match: invoke `python "${CLAUDE_PROJECT_DIR}/tools/bump_version.py" --phase "$PHASE_NUM"`; on failure, log to stderr and `exit 0` (do not block the commit per D-09)
- On success: emit `hookSpecificOutput` JSON via `jq -n` with `permissionDecision: "allow"` + `updatedInput.command` appending `pyproject.toml` to the `--files` list

**Companion rollback script (`bump-rollback-hook.sh`):** Use RESEARCH.md §Code Example 4 verbatim — single-command rollback `git -C "$CLAUDE_PROJECT_DIR" checkout HEAD -- pyproject.toml` (NOT D-08's literal `git checkout -- pyproject.toml`, per Pitfall 4).

---

### `pyproject.toml` (config, regex-rewritten by helper)

**Analog:** n/a (the helper is the only thing that should write this file).

**Current state to preserve** (`pyproject.toml:5-7`):
```toml
[project]
name = "musicstreamer"
version = "2.1.60"
```
**After Phase 63 self-bump:** `version = "2.1.63"`. All other lines (1-54) byte-identical. Live verification in RESEARCH.md §Pattern 3 confirmed: exactly 1 line changes; comments at lines 17-22, 33-35, 50-54 are preserved.

**Plan task note:** No edit needed in the phase plan itself — the helper does it on its own first invocation as part of phase-completion-commit. The current `2.1.60` value is two phases stale (Phases 61, 62 completed without bumps); Phase 63 self-completion will jump to `2.1.63` as expected (CONTEXT specifics line 111).

---

### `.planning/config.json` (config, direct JSON edit)

**Analog:** Itself — extend the existing `workflow` block.

**Current shape** (`.planning/config.json:1-15`, full file):
```json
{
  "mode": "yolo",
  "granularity": "standard",
  "parallelization": true,
  "commit_docs": true,
  "model_profile": "balanced",
  "workflow": {
    "research": true,
    "plan_check": true,
    "verifier": true,
    "nyquist_validation": true,
    "_auto_chain_active": true,
    "auto_advance": false
  }
}
```
**Target shape after this phase:**
```json
{
  "mode": "yolo",
  "granularity": "standard",
  "parallelization": true,
  "commit_docs": true,
  "model_profile": "balanced",
  "workflow": {
    "research": true,
    "plan_check": true,
    "verifier": true,
    "nyquist_validation": true,
    "_auto_chain_active": true,
    "auto_advance": false,
    "auto_version_bump": true
  }
}
```
**Plan task note:** Edit by **direct JSON read+write** (`json.load` → mutate dict → `json.dumps(..., indent=2)`). Per RESEARCH.md §Pitfall 3, `gsd-sdk query config-set workflow.auto_version_bump true` will fail with `Error: Unknown config key` (exit code 10) — the SDK has a hardcoded `VALID_CONFIG_KEYS` allowlist that does NOT include `auto_version_bump`. Use Python or `jq -r` for the rewrite; don't attempt `config-set`.

---

### `.planning/PROJECT.md` (doc, append `## Versioning` section)

**Analog:** Itself — match the existing section style.

**Existing `## Constraints` section to anchor against** (`.planning/PROJECT.md:223-228`):
```markdown
## Constraints

- **Tech stack:** Python + GTK4/Libadwaita — no framework changes
- **Platform:** Linux GNOME desktop only
- **No network auth:** API keys only where required by service (AudioAddict)
- **Test runner:** pytest via `uv run --with pytest` (no system pip)
```
**Note:** `## Constraints` is at line 223. `## Phase History` immediately follows at line 230. Per RESEARCH.md Open Question 3 recommendation, place the new `## Versioning` section **above** `## Constraints` (after the last `## Previous Milestone:` block at line 222 — actually the table at line 222 is a `## Key Decisions` table row; the `## Constraints` heading at 223 is the right anchor).

**Target shape (worked example from CONTEXT.md specifics line 112):**
```markdown
## Versioning

The `pyproject.toml` `version` field follows `{major}.{minor}.{phase}`, where `{major}.{minor}` is sourced from the `## Current Milestone: vX.Y` heading above and `{phase}` is the most recently completed phase number. The bump is automated by `tools/bump_version.py` via the `.claude/settings.json` PreToolUse hook on `gsd-sdk query commit "docs(phase-NN): complete phase execution"` — gated by the `workflow.auto_version_bump` flag in `.planning/config.json` (default: true).

**Worked example:** Closing Phase 50 of v2.1 yields `version = "2.1.50"`; closing Phase 63 yields `2.1.63`. The leading `2.1` comes from `## Current Milestone: v2.1` in this file.

## Constraints
```
**Section style:** Markdown H2 heading (`##`), one paragraph of prose, **Worked example** as a bold inline label followed by the example. Matches the prose-paragraph + bold-inline-label idiom seen in `## Core Value` (line 7-9) and `## Current Milestone` (line 11-13).

---

## Shared Patterns

### Repo-Root Path Resolution (Python)
**Source:** `tools/check_subprocess_guard.py:23-25`
**Apply to:** `tools/bump_version.py`
```python
def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent
```
The helper anchors all file targets (`pyproject.toml`, `PROJECT.md`, `.planning/config.json`) off this. Tests use the same idiom from a one-deeper level (`Path(__file__).resolve().parent.parent` from `tests/test_bump_version.py` also resolves to repo root since `tests/` is a sibling of `tools/`).

### `from __future__ import annotations` + Stdlib-Only Imports
**Source:** `tools/check_subprocess_guard.py:14-18`, `tools/check_spec_entry.py:14-17`
**Apply to:** `tools/bump_version.py`
```python
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
```
Per `.planning/codebase/CONVENTIONS.md` (cited in RESEARCH.md §Project Constraints): `from __future__ import annotations` for forward references, `X | Y` union syntax (Python 3.10+), no third-party deps for `tools/` helpers. D-06 explicitly rejects adding `tomlkit`.

### Stderr for Failures, Stdout for Success Messages
**Source:** `tools/check_subprocess_guard.py:31, 43, 53` (stderr); `:34, 58` (stdout)
**Apply to:** `tools/bump_version.py` and `.claude/hooks/bump-version-hook.sh`
```python
# Failure path → stderr
print(f"PKG-03 FAIL: ...", file=sys.stderr)
# Success path → stdout
print(f"PKG-03 OK: ...")
```
Project-wide convention. The hook script's "[bump] disabled via flag" message (D-11) goes to stderr (informational, not output the agent harness should consume); the `hookSpecificOutput` JSON goes to stdout (agent consumes it).

### Documenting Exit Codes in the Module Docstring
**Source:** `tools/check_subprocess_guard.py:8-11`, `tools/check_spec_entry.py:8-10`
**Apply to:** `tools/bump_version.py`
```python
"""...

Exit codes:
    0 — success (or no-op short-circuit when flag is false)
    1 — parse error (PROJECT.md milestone heading not found OR pyproject.toml missing [project] table)
    2 — regex no-match (pyproject.toml had [project] but no parseable version line)
    3 — config disabled (D-11 short-circuit; not a failure)

Callable as ``python tools/bump_version.py --phase NN`` from the repo root.
"""
```
The exit codes vocabulary is established by Phase 44 (PKG-01: 7, PKG-03: 4). New helpers pick the next-available small integers; codes used must be documented in the docstring. Per RESEARCH.md, code 3 ("config disabled") is informational, not a hard failure — the hook treats it as "exit 0, log warning, proceed unmodified."

### Pytest `tmp_path` + `monkeypatch` Fixture Style
**Source:** `tests/test_desktop_install.py:18-26`, `tests/test_paths.py:10-16`
**Apply to:** `tests/test_bump_version.py`
```python
@pytest.fixture
def fake_pyproject(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text(
        '[project]\n'
        'name = "test"\n'
        'version = "0.0.0"\n',
        encoding="utf-8",
    )
    return p
```
Project test convention: synthesize fixture files under `tmp_path`, write with explicit `encoding="utf-8"`, return the `Path`. For env-var injection (e.g., stub `gsd-sdk` on `PATH`), use `monkeypatch.setenv(...)` per `tests/test_desktop_install.py:20`.

### Subprocess CLI Test Invocation
**Source:** `tests/test_media_keys_mpris2.py:221-227`
**Apply to:** `tests/test_bump_version.py` (every helper-invocation test)
```python
result = subprocess.run(
    [sys.executable, str(repo_root / "tools" / "bump_version.py"),
     "--phase", "42",
     "--pyproject", str(pyproject),
     "--project-md", str(project_md)],
    capture_output=True, text=True, timeout=10,
)
assert result.returncode == 0, result.stderr
```
Project convention: `capture_output=True, text=True` (NOT `encoding="utf-8"`), explicit `timeout=` argument, assert on `returncode` first with `result.stderr` as the failure-mode message. Per RESEARCH.md §Pitfall 7, this surface MUST match what the hook calls — same args, same interface — to prevent test/prod drift.

### Drift-Guard Test Style
**Source:** `tests/test_constants_drift.py:18-27, 30-34, 52-68`
**Apply to:** `tests/test_bump_version.py` (the static-check tests: `test_project_md_milestone_heading_present`, `test_hook_files_committed`, `test_project_md_has_versioning_section`)
```python
def test_<thing>_present():
    """One-line failure-mode description."""
    target = Path(__file__).parent.parent / "<path>"
    assert target.exists(), (
        f"Phase NN drift: expected {target}; "
        f"found: {sorted(p.name for p in target.parent.glob('*'))}"
    )
```
Project convention: assertion message gives the path it looked for AND a hint about what it found (so the failure message tells you what to fix, not just that something failed).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.claude/settings.json` (`hooks` block) | config | event-driven (Claude Code agent harness) | This is the first project-local Claude Code hook in the repo. `.claude/settings.local.json` exists but is a different schema (permissions allowlist, not hooks). The skill at `.claude/skills/spike-findings-musicstreamer/SKILL.md` is a skill, not a hook config. **Use RESEARCH.md §Pattern 2 verbatim** (verified live against `code.claude.com/docs/en/hooks` 2026-05-08). |
| `.claude/hooks/bump-version-hook.sh` (hook protocol body) | utility | event-driven (stdin JSON → stdout JSON) | The repo has bash scripts (`scripts/dev-launch.sh`, `install.sh`, `scripts/gbs_capture_fixtures.sh`) but none use the Claude Code hook stdin/stdout JSON protocol. The shape (shebang, `set -euo pipefail`, `$CLAUDE_PROJECT_DIR` resolution) follows `scripts/dev-launch.sh`; the **content** (`jq` extraction, `hookSpecificOutput` emission) is from RESEARCH.md §Pattern 2 + §Code Examples 4 + 5, all verified live. |

For both: the planner should treat RESEARCH.md §Pattern 2 + §Code Examples as the authoritative pattern source — the research already verified them live against the official Claude Code docs and against this repo's `pyproject.toml` / `PROJECT.md` content.

---

## Metadata

**Analog search scope:**
- `tools/` (3 files: `__init__.py`, `check_spec_entry.py`, `check_subprocess_guard.py`)
- `tests/` (drift-guard, tomllib, subprocess CLI test files)
- `scripts/` (only checked-in bash scripts in the repo)
- `.claude/` (existing settings.local.json + skills/ subtree)
- `.planning/config.json` (config-flag analog target)
- `.planning/PROJECT.md` (section-anchor target)
- `pyproject.toml` (regex-target verification)

**Files scanned:** 9 source files read in full or in targeted ranges, ~6 additional files inspected via `ls`/`grep`.

**Key patterns identified:**
- All `tools/` helpers follow the same `from __future__ import annotations` + stdlib-only + `_repo_root()` + `def main() -> int` + `sys.exit(N)` + `if __name__ == "__main__"` shape. `bump_version.py` will be the third file in that pattern.
- All drift-guard tests follow the `tests/test_constants_drift.py` shape: H2 docstring with phase tag, `Path(__file__).parent.parent / "<target>"` resolution, `assert ... .exists(), <helpful failure message>`.
- The existing project has zero in-repo analog for Claude Code hooks; rely on RESEARCH.md's live-verified patterns.
- The existing `.planning/config.json` workflow block already has 6 keys; adding a 7th requires direct JSON edit (NOT `gsd-sdk query config-set`, which rejects unknown keys per Pitfall 3).

**Pattern extraction date:** 2026-05-08
