---
phase: 89A-channel-avatar-db-migration-storage-layout
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - musicstreamer/paths.py
  - musicstreamer/assets.py
  - tests/test_paths.py
  - tests/test_repo.py
autonomous: true
requirements:
  - ART-AVATAR-02
must_haves:
  truths:
    - "paths.channel_avatars_dir() returns <root>/assets/channel-avatars and honors _root_override"
    - "Calling paths.channel_avatars_dir() does NOT create the directory (pure accessor)"
    - "assets.ensure_dirs() creates the assets/channel-avatars/ directory at startup"
  artifacts:
    - path: "musicstreamer/paths.py"
      provides: "channel_avatars_dir() pure path accessor"
      contains: "def channel_avatars_dir("
    - path: "musicstreamer/assets.py"
      provides: "eager makedirs of channel-avatars/ in ensure_dirs()"
      contains: "channel_avatars_dir"
    - path: "tests/test_paths.py"
      provides: "accessor override + purity tests"
      contains: "test_channel_avatars_dir_honors_root_override"
    - path: "tests/test_repo.py"
      provides: "ensure_dirs creates channel-avatars test"
      contains: "test_ensure_dirs_creates_channel_avatars_dir"
  key_links:
    - from: "musicstreamer/assets.py:ensure_dirs"
      to: "musicstreamer/paths.py:channel_avatars_dir"
      via: "os.makedirs(paths.channel_avatars_dir(), exist_ok=True)"
      pattern: "channel_avatars_dir"
---

<objective>
Establish the on-disk storage location for per-station channel avatars: add a pure
`paths.channel_avatars_dir()` accessor (D-02) and eagerly create the directory at
startup in `assets.ensure_dirs()` (D-01). Delivers ART-AVATAR-02.

Purpose: Phase 89 (YouTube avatar fetch) and Phase 89b (Twitch avatar fetch) need a
guaranteed-existing directory and a single source-of-truth path accessor before they
can write avatar PNGs. This plan provides both with zero behavior change to the rest
of the app.

Output: `channel_avatars_dir()` accessor in paths.py, one new makedirs line in
ensure_dirs(), and 3 tests (2 in test_paths.py, 1 in test_repo.py).
</objective>

<execution_context>
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.4.10/workflows/execute-plan.md
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.4.10/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/89A-channel-avatar-db-migration-storage-layout/89A-CONTEXT.md
@.planning/phases/89A-channel-avatar-db-migration-storage-layout/89A-PATTERNS.md
@.planning/phases/89A-channel-avatar-db-migration-storage-layout/89A-RESEARCH.md

<interfaces>
<!-- Key existing shapes the executor mirrors. Extracted from codebase 2026-06-13. -->

paths.py L24-31 — the _root override hook (inherited automatically by every accessor):
  _root_override: str | None = None
  def _root() -> str: returns _root_override if set, else platformdirs.user_data_dir("musicstreamer")

paths.py L94-101 — eq_profiles_dir(): the EXACT accessor shape to mirror (pure, returns os.path.join(_root(), ...), no mkdir).

assets.py L1-9 — `import os`, `from musicstreamer import paths`, and ensure_dirs() body:
  os.makedirs(paths.data_dir(), exist_ok=True)
  os.makedirs(paths.assets_dir(), exist_ok=True)

test_paths.py — has autouse `_reset_root_override` fixture (L10-17); `import os` and `paths` already imported; eq_profiles_dir tests at L92-102 are the exact template.

test_repo.py — header imports ONLY `sqlite3` and `pytest` (NO `import os`). Adding the ensure_dirs test REQUIRES adding `import os` to the header.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add channel_avatars_dir() accessor + override/purity tests (paths.py, test_paths.py)</name>
  <files>musicstreamer/paths.py, tests/test_paths.py</files>
  <read_first>
    - musicstreamer/paths.py L1-15 (purity docstring) and L94-101 (eq_profiles_dir analog to copy)
    - tests/test_paths.py L10-17 (autouse _reset_root_override fixture) and L92-102 (eq_profiles_dir test analogs)
  </read_first>
  <behavior>
    - Test: paths.channel_avatars_dir() == os.path.join(str(tmp_path), "assets", "channel-avatars") when _root_override = tmp_path
    - Test: calling paths.channel_avatars_dir() does NOT create the directory (os.path.exists(result) is False) — purity contract
  </behavior>
  <action>
    In musicstreamer/paths.py, add a new function `channel_avatars_dir() -> str` immediately
    after `eq_profiles_dir()` (after L101), per D-02. It returns
    `os.path.join(_root(), "assets", "channel-avatars")` — TWO path components under _root()
    (it nests under assets/, unlike eq_profiles_dir which is a single component). Mirror the
    eq_profiles_dir docstring style: state it is PURE, does NOT mkdir, callers use
    `os.makedirs(paths.channel_avatars_dir(), exist_ok=True)`, and it respects _root_override
    via _root(). Do NOT add any os.makedirs call inside the function (purity is enforced by
    test_paths_do_no_io_on_import).

    In tests/test_paths.py, append two tests after L102 mirroring the eq_profiles_dir analogs:
    `test_channel_avatars_dir_honors_root_override` (asserts the two-component join under
    _root_override) and `test_channel_avatars_dir_does_not_create_directory` (asserts
    os.path.exists(result) is False). The autouse _reset_root_override fixture and existing
    `import os` / `paths` imports cover these — no new imports needed in test_paths.py.
  </action>
  <verify>
    <automated>uv run --with pytest pytest "tests/test_paths.py::test_channel_avatars_dir_honors_root_override" "tests/test_paths.py::test_channel_avatars_dir_does_not_create_directory" -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "def channel_avatars_dir(" musicstreamer/paths.py` matches exactly one line.
    - `grep -c 'os.makedirs' musicstreamer/paths.py` returns 0 (accessor stays pure).
    - Both new tests in tests/test_paths.py pass via the verify command above.
    - The accessor returns a path ending in `assets/channel-avatars` (two components), confirmed by the override test.
  </acceptance_criteria>
  <done>channel_avatars_dir() exists in paths.py as a pure accessor returning <root>/assets/channel-avatars; both override and purity tests are green.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Eager directory creation in ensure_dirs() + ensure_dirs test (assets.py, test_repo.py)</name>
  <files>musicstreamer/assets.py, tests/test_repo.py</files>
  <read_first>
    - musicstreamer/assets.py L1-9 (imports + current ensure_dirs body — the line to append after)
    - tests/test_repo.py L1-2 (header — confirm `import os` is ABSENT and must be added) and L6-13 (repo fixture / monkeypatch convention)
    - tests/test_paths.py L98-102 (eq_profiles_dir_does_not_create analog — invert to assert directory IS created)
  </read_first>
  <behavior>
    - Test: after monkeypatching paths._root_override to tmp_path and calling assets.ensure_dirs(), os.path.isdir(<tmp_path>/assets/channel-avatars) is True
  </behavior>
  <action>
    In musicstreamer/assets.py, append a third line to `ensure_dirs()` AFTER the existing
    `os.makedirs(paths.assets_dir(), exist_ok=True)` line (D-01):
    `os.makedirs(paths.channel_avatars_dir(), exist_ok=True)`. The line MUST come after the
    assets_dir makedirs since channel-avatars/ nests under assets/. Reference paths via
    `paths.channel_avatars_dir()` only — no hardcoded path string. `exist_ok=True` is mandatory
    (prevents FileExistsError on second startup). No inline comment — match the existing
    comment-free two-line style.

    In tests/test_repo.py, FIRST add `import os` to the header (it currently imports only
    `sqlite3` and `pytest` — PATTERNS note 6). Then append
    `test_ensure_dirs_creates_channel_avatars_dir(tmp_path, monkeypatch)`: import
    musicstreamer.paths and musicstreamer.assets locally, monkeypatch.setattr(paths, "_root_override",
    str(tmp_path)), call assets.ensure_dirs(), and assert
    os.path.isdir(os.path.join(str(tmp_path), "assets", "channel-avatars")). Place it in
    test_repo.py per RESEARCH §Open Questions (no tests/test_assets.py exists).
  </action>
  <verify>
    <automated>uv run --with pytest pytest "tests/test_repo.py::test_ensure_dirs_creates_channel_avatars_dir" -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "channel_avatars_dir" musicstreamer/assets.py` matches the new makedirs line inside ensure_dirs().
    - `grep -n "^import os" tests/test_repo.py` matches (import added to header).
    - The ensure_dirs line appears AFTER the assets_dir makedirs line (verify by reading ensure_dirs body).
    - `test_ensure_dirs_creates_channel_avatars_dir` passes via the verify command above, creating the dir under tmp_path (not the real ~/.local/share).
  </acceptance_criteria>
  <done>ensure_dirs() eagerly creates assets/channel-avatars/ via paths.channel_avatars_dir(); the directory-creation test is green and isolated to tmp_path.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No new trust boundary is crossed in this plan. The accessor returns a path string from a
constant join; `ensure_dirs()` creates a directory under the app's own data root. No network,
no user input, no privileged operation.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-89A-01 | Tampering | assets.ensure_dirs() makedirs | accept | `os.makedirs(..., exist_ok=True)` does NOT alter permissions or contents of an existing directory; no symlink-following beyond stdlib default; path is a fixed constant under the app data root, not user-controlled. No control required (RESEARCH §Security Domain: no applicable ASVS L1 controls). |

No high/medium threats: pure path accessor + idempotent directory creation under the app's own
data dir, no user-controlled data, no network. ASVS L1 finds no applicable controls for this plan.
</threat_model>

<verification>
- `uv run --with pytest pytest tests/test_paths.py tests/test_repo.py -x -q` passes (all new tests green, no regressions).
- `grep -n "def channel_avatars_dir(" musicstreamer/paths.py` returns exactly one match.
- `grep -c 'os.makedirs' musicstreamer/paths.py` returns 0 (accessor purity preserved).
- ensure_dirs() references `paths.channel_avatars_dir()` (no hardcoded path literal in assets.py).
</verification>

<success_criteria>
- ART-AVATAR-02 satisfied: `~/.local/share/musicstreamer/assets/channel-avatars/` is created at startup with the existing assets/ permission model, via a single source-of-truth accessor.
- ROADMAP Success Criterion 3 satisfied: directory exists with appropriate permissions, flat layout per D-03.
- Zero behavior change elsewhere (no models.py / mapper / save_station edits — D-06).
</success_criteria>

<output>
Create `.planning/phases/89A-channel-avatar-db-migration-storage-layout/89A-01-SUMMARY.md` when done.
</output>
