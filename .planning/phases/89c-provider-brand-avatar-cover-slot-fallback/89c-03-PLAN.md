---
phase: 89c-provider-brand-avatar-cover-slot-fallback
plan: 03
type: execute
wave: 1
depends_on: [89c-01, 89c-02]
files_modified:
  - musicstreamer/ui_qt/edit_station_dialog.py
  - tests/test_brand_avatars.py
autonomous: true
gap_closure: true
requirements: [ART-AVATAR-05]

must_haves:
  truths:
    - "Reopening EditStationDialog for a station with a persisted provider brand image shows that image in the avatar preview on open (reuse-on-open, Phase 89.1 D-07 — closes UAT Test 5 gap)"
  artifacts:
    - path: "musicstreamer/ui_qt/edit_station_dialog.py"
      provides: "_populate() invokes _refresh_avatar_preview() so a persisted provider_avatar_path renders on dialog open"
      contains: "_refresh_avatar_preview"
    - path: "tests/test_brand_avatars.py"
      provides: "Source-grep drift-guard asserting _refresh_avatar_preview is called within _populate body"
      contains: "def test_populate_refreshes_avatar_preview"
  key_links:
    - from: "musicstreamer/ui_qt/edit_station_dialog.py::_populate"
      to: "musicstreamer/ui_qt/edit_station_dialog.py::_refresh_avatar_preview"
      via: "direct method call alongside _refresh_logo_preview"
      pattern: "self\\._refresh_avatar_preview\\(\\)"
---

<objective>
Close the single MINOR gap from 89c UAT Test 5: reopening EditStationDialog for a
station with a persisted provider brand image does NOT render that image in the
dialog's avatar preview, even though the image is persisted and renders correctly
in the now-playing cover slot. This violates the Phase 89.1 D-07 reuse-on-open
contract for the dialog preview.

Purpose: A one-line fix — `_populate()` already refreshes the logo preview but
omits the parallel avatar-preview refresh. `_refresh_avatar_preview()` already
resolves and renders the persisted `provider_avatar_path` correctly; it is simply
never invoked at construction/populate time (only on fetch/pick paths). Add the
call to mirror the existing logo-preview-on-open pattern.

Output: Avatar preview populates from `self._station.provider_avatar_path` on
dialog open, plus a source-grep drift-guard pinning the call inside `_populate`.
</objective>

<execution_context>
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.5.0/workflows/execute-plan.md
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.5.0/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/89c-provider-brand-avatar-cover-slot-fallback/89C-HUMAN-UAT.md

<interfaces>
<!-- Extracted from live source. Use directly — no exploration needed. -->

musicstreamer/ui_qt/edit_station_dialog.py:
- `_populate(self) -> None` (L628): populates all dialog widgets from
  `self._station`. At L677 it calls `self._refresh_logo_preview()` (the sibling
  logo-preview-on-open pattern). It does NOT call `_refresh_avatar_preview()`.
- `_refresh_avatar_preview(self) -> None` (L1603): resolves
  `self._station.provider_avatar_path` (Phase 89.1 D-05) via `paths.data_dir()`,
  clears the `_avatar_preview` label on missing/null/null-pixmap, else sets a
  64×64 KeepAspectRatio pixmap. Already correct — only ever invoked from
  fetch/pick paths (L1346/1434/1551), never at populate time.

tests/test_brand_avatars.py:
- `EDIT_STATION_SRC` (L141) = Path to edit_station_dialog.py.
- Established source-grep drift-guard pattern (e.g. `test_choose_brand_image_*`,
  L144): read EDIT_STATION_SRC, locate `def <method>` with `src.find`, extract the
  method body up to the next `\n    def ` at the same indent, then assert tokens
  appear in that body. Mirror this exactly for `_populate`.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Refresh avatar preview on dialog open + drift-guard</name>
  <files>musicstreamer/ui_qt/edit_station_dialog.py, tests/test_brand_avatars.py</files>
  <read_first>
    - musicstreamer/ui_qt/edit_station_dialog.py L628-689 (`_populate`, including the
      existing `self._refresh_logo_preview()` call at ~L677 and the comment block
      around it)
    - musicstreamer/ui_qt/edit_station_dialog.py L1603-1628 (`_refresh_avatar_preview`)
    - tests/test_brand_avatars.py L141-185 (`EDIT_STATION_SRC` constant and the
      `test_choose_brand_image_uses_provider_keyed_persist` method-body-extraction
      drift-guard to mirror)
  </read_first>
  <action>
    Fix (edit_station_dialog.py): Inside `_populate()`, immediately after the
    existing `self._refresh_logo_preview()` line (~L677, under its "Logo preview"
    comment), add a call to `self._refresh_avatar_preview()`. Place it BEFORE the
    `self._capture_dirty_baseline()` call so the preview render does not perturb the
    dirty-state baseline (mirrors how the logo refresh precedes baseline capture).
    Add a short inline comment noting this is the Phase 89.1 D-07 reuse-on-open
    render for the avatar/brand preview, closing the 89c UAT Test 5 gap. This is a
    single-line addition that mirrors the sibling logo-preview-on-open pattern — do
    NOT add a new method, refactor, or expand scope.

    Drift-guard (tests/test_brand_avatars.py): Add a new test function
    `test_populate_refreshes_avatar_preview` mirroring the established
    method-body-extraction pattern: read `EDIT_STATION_SRC`, locate `def _populate`
    via `src.find`, extract the body up to the next `\n    def ` at the same indent,
    then assert `self._refresh_avatar_preview()` appears in that body (with a message
    citing Phase 89.1 D-07 reuse-on-open / UAT Test 5). The structural source-grep
    approach is required over a Qt behavioral mock per the project convention
    (feedback_gstreamer_mock_blind_spot).

    Note for executor: `.planning/` is gitignored — `git add -f` planning artifacts
    (SUMMARY/STATE/ROADMAP); source and test files commit normally.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_brand_avatars.py::test_populate_refreshes_avatar_preview -x</automated>
  </verify>
  <acceptance_criteria>
    - `_populate()` body in edit_station_dialog.py contains a
      `self._refresh_avatar_preview()` call, positioned after
      `self._refresh_logo_preview()` and before `self._capture_dirty_baseline()`.
    - `tests/test_brand_avatars.py::test_populate_refreshes_avatar_preview` exists
      and passes, asserting the call appears inside the extracted `_populate` body.
    - No new methods added to edit_station_dialog.py; `_refresh_avatar_preview` is
      unchanged. Scope is the single call site + one drift-guard test.
    - `grep -v '^#' musicstreamer/ui_qt/edit_station_dialog.py | grep -c 'self\._refresh_avatar_preview()'`
      returns at least 4 (3 pre-existing fetch/pick call sites + the new populate call site).
  </acceptance_criteria>
  <done>
    Reopening EditStationDialog for a station with a persisted provider_avatar_path
    renders that image in the avatar preview on open (reuse-on-open, Phase 89.1
    D-07), closing UAT Test 5. The drift-guard pins the call inside `_populate`.
  </done>
</task>

</tasks>

<verification>
- `.venv/bin/python -m pytest tests/test_brand_avatars.py -x` passes (existing
  drift-guards plus the new `test_populate_refreshes_avatar_preview`).
- Manual reuse-on-open confirmation is deferred to the next UAT pass on Test 5; the
  source-grep guard provides the structural acceptance gate.
</verification>

<success_criteria>
- `_populate()` calls `_refresh_avatar_preview()` alongside `_refresh_logo_preview()`.
- New drift-guard test passes; full `tests/test_brand_avatars.py` passes.
- UAT Test 5 reuse-on-open gap (Phase 89.1 D-07) is structurally closed.
</success_criteria>

<output>
Create `.planning/phases/89c-provider-brand-avatar-cover-slot-fallback/89c-03-SUMMARY.md` when done.
</output>
