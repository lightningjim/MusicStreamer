---
phase: 89c-provider-brand-avatar-cover-slot-fallback
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - musicstreamer/brand_avatars.py
  - musicstreamer/ui_qt/brand-avatars/.gitkeep
  - tests/test_brand_avatars.py
  - tests/test_cover_art_avatar.py
  - musicstreamer/ui_qt/now_playing_panel.py
  - packaging/windows/MusicStreamer.spec
autonomous: true
requirements: [ART-AVATAR-11, ART-AVATAR-12]

must_haves:
  truths:
    - "ART-AVATAR-11/D-01: brand_avatars.lookup() recognizes the 7 exact provider_name strings (SomaFM + 6 AudioAddict networks) and returns None for GBS.FM"
    - "ART-AVATAR-11/D-04: a registered provider_name whose PNG file is absent returns None (graceful missing-asset, no crash, current behavior preserved)"
    - "ART-AVATAR-12/D-07: the brand-avatar lookup fires ONLY from the _on_cover_art_ready `if not path:` branch, never from fetch_cover_art dispatch nor bind_station icy_disabled path"
    - "ART-AVATAR-12/D-08: cover-resolution-exhausted resolves user-override (provider_avatar_path) -> bundled registry -> _show_station_logo_in_cover_slot, in that order"
    - "ART-AVATAR-12/D-10: real cover art still wins — _set_cover_pixmap path unchanged; brand avatar is transient per cover-resolution"
    - "D-11: _last_brand_avatar tier-replay var participates in _apply_art_tier (4th branch between _last_avatar_path and the logo else) and is reset in bind_station"
    - "ART-AVATAR-12/D-04 (frozen build): the brand-avatars dir is bundled via PyInstaller datas so importlib.resources resolves it in frozen builds"
  artifacts:
    - path: "musicstreamer/brand_avatars.py"
      provides: "Provider brand-avatar registry; lookup(provider_name) -> Optional[str]"
      contains: "def lookup"
      min_lines: 20
    - path: "musicstreamer/ui_qt/brand-avatars/.gitkeep"
      provides: "Git-tracked loose-PNG asset dir (D-05); PNGs arrive from user later"
    - path: "tests/test_brand_avatars.py"
      provides: "Registry unit tests + D-11 source-grep drift-guards"
      contains: "def test_lookup_registered_providers"
    - path: "musicstreamer/ui_qt/now_playing_panel.py"
      provides: "_resolve_brand_avatar_fallback, _set_brand_avatar_pixmap, _last_brand_avatar, _apply_art_tier 4th branch, bind_station reset"
      contains: "_resolve_brand_avatar_fallback"
    - path: "packaging/windows/MusicStreamer.spec"
      provides: "brand-avatars datas entry for frozen builds"
      contains: "brand-avatars"
  key_links:
    - from: "musicstreamer/ui_qt/now_playing_panel.py::_on_cover_art_ready (if not path:)"
      to: "_resolve_brand_avatar_fallback"
      via: "direct call replacing _show_station_logo_in_cover_slot at L2183"
      pattern: "_resolve_brand_avatar_fallback"
    - from: "musicstreamer/ui_qt/now_playing_panel.py::_resolve_brand_avatar_fallback"
      to: "musicstreamer.brand_avatars.lookup"
      via: "registry lookup on station.provider_name (D-08 step 2)"
      pattern: "brand_avatars\\.lookup"
    - from: "musicstreamer/brand_avatars.py::lookup"
      to: "musicstreamer/ui_qt/brand-avatars/<key>.png"
      via: "importlib.resources.files + os.path.isfile guard"
      pattern: "importlib.resources|_res\\.files"
---

<objective>
Ship the full plumbing for provider brand-avatar cover-slot fallback: the registry module, the loose-PNG asset dir, the now_playing_panel render path (state var + render method + three-tier resolver + tier-replay branch + stale-station reset), the source-grep drift-guards, and the PyInstaller bundling entry.

Purpose: When per-track cover-art resolution is exhausted for an ICY provider whose art frequently misses (SomaFM, AudioAddict), the cover slot shows a distinct provider brand mark instead of duplicating the station logo (the Drone Zone duplicate-logo complaint). Delivers ART-AVATAR-11 and ART-AVATAR-12. The 7 PNGs arrive from the user later (D-04) — until then, missing asset === current station-logo behavior, a fully tested path.

Output: brand_avatars.py registry, brand-avatars/ asset dir, test_brand_avatars.py, now_playing_panel wiring, a new source-grep drift-guard in test_cover_art_avatar.py, and the MusicStreamer.spec datas entry.
</objective>

<execution_context>
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.5.0/workflows/execute-plan.md
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.5.0/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/89c-provider-brand-avatar-cover-slot-fallback/89C-CONTEXT.md
@.planning/phases/89c-provider-brand-avatar-cover-slot-fallback/89C-RESEARCH.md
@.planning/phases/89c-provider-brand-avatar-cover-slot-fallback/89C-PATTERNS.md
@.planning/phases/89c-provider-brand-avatar-cover-slot-fallback/89C-VALIDATION.md

<notes>
- Run tests via .venv/bin/python (memory: run-tests-with-venv-python). system python3 lacks PySide6.QtWidgets → false failures. Full suite >600s — scope to the two named test files.
- Source-grep over behavioral mocks (feedback_gstreamer_mock_blind_spot). No GStreamer/Qt behavioral mocks for the drift-guards.
- Live source line numbers confirmed 2026-06-17: _make_circular_pixmap L219, _last_avatar_path L347, bind_station L909 (reset block L935-936), _apply_art_tier L2087 (3-branch L2127-2132), _on_cover_art_ready L2173 (the `if not path:` trigger L2183), _set_avatar_pixmap_from_path L2205, _show_station_logo_in_cover_slot L2267. MusicStreamer.spec datas L122-123.
- frozen-build-env-missing-runtime-components memory: make the spec datas entry explicit; the destination MUST be the full namespace path so importlib.resources resolves in frozen builds.
</notes>

<interfaces>
<!-- Contracts the executor needs. Extracted from live source + PATTERNS.md. Use directly — no exploration. -->

The 7 EXACT provider_name dict keys (verbatim — these are what land in station.provider_name):
  "SomaFM"          (soma_import.py:306 — CamelCase, no space, no period)
  "DI.fm"           (aa_import.py:106)
  "RadioTunes"      (aa_import.py:107)
  "JazzRadio"       (aa_import.py:108)
  "RockRadio"       (aa_import.py:109)
  "ClassicalRadio"  (aa_import.py:110)
  "ZenRadio"        (aa_import.py:111)
  GBS.FM is NOT a key (D-01 exclusion).

brand_avatars.lookup contract: lookup(provider_name: str) -> Optional[str]. Returns absolute filesystem path to the bundled PNG ONLY if the registry has the key AND os.path.isfile() is true; otherwise None. Never raises (mirrors yt_import.get_avatar_fetcher never-raise contract).

Existing now_playing_panel render contracts (do not modify their behavior):
  _make_circular_pixmap(source: QPixmap, size: int) -> QPixmap  (L219, module-level, reuse unmodified)
  _set_avatar_pixmap_from_path(self, rel_path: str) -> None     (L2205, joins paths.data_dir(); sets _last_avatar_path; isNull→clear+logo fallback)
  _show_station_logo_in_cover_slot(self) -> None                (L2267, final fallback; sets _last_cover_path=None)
  self._current_art_tier or 180                                 (tier size idiom used by both render methods)

Existing test pattern (tests/test_cover_art_avatar.py L15/L23-38): COVER_ART_SRC.read_text(); find("def <anchor>"); positional assertion.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Registry module, asset dir, and registry unit tests (Wave 0)</name>
  <files>musicstreamer/brand_avatars.py, musicstreamer/ui_qt/brand-avatars/.gitkeep, tests/test_brand_avatars.py</files>
  <read_first>
    - .planning/phases/89c-provider-brand-avatar-cover-slot-fallback/89C-PATTERNS.md (§brand_avatars.py analog, §test_brand_avatars.py analog)
    - musicstreamer/yt_import.py (register_avatar_fetcher/get_avatar_fetcher registry shape, ~L263-284)
    - tests/test_cover_art_avatar.py (source-grep + unit test style, L1-80)
  </read_first>
  <behavior>
    - lookup("SomaFM") returns a path ending in the SomaFM PNG when the stub file exists (tested via tmp_path + monkeypatched _res.files)
    - lookup() returns the correct path for all 7 keys: SomaFM, DI.fm, RadioTunes, JazzRadio, RockRadio, ClassicalRadio, ZenRadio
    - lookup("GBS.FM") returns None (D-01 exclusion — key absent)
    - lookup("SomaFM") returns None when the registered PNG file is absent (D-04 graceful missing-asset)
    - lookup("totally unknown provider") returns None (unknown key)
    - lookup() never raises for any string input
  </behavior>
  <action>
    Create musicstreamer/brand_avatars.py mirroring the yt_import registry shape but as a static module-level dict `_REGISTRY: dict[str, str]` mapping each of the 7 exact provider_name strings to a PNG filename, plus a single `lookup(provider_name: str) -> Optional[str]`. Use the provider_name verbatim as the filename stem (D-09a §Open-Question-3: keep "DI.fm.png", "RadioTunes.png", etc. — the dict is the single normalization point; no runtime slug transform). lookup() does `_REGISTRY.get(provider_name)`; if None return None; else resolve `importlib.resources.files("musicstreamer.ui_qt") / "brand-avatars" / filename`, stringify, and return it ONLY if os.path.isfile() is true (D-04 missing-asset guard), else None. Import importlib.resources as `_res`, plus os and typing.Optional. lookup() must never raise (Pitfall 4). GBS.FM must NOT be a dict key (D-01).

    Create the loose-PNG asset dir musicstreamer/ui_qt/brand-avatars/ with a .gitkeep file so setuptools VCS discovery tracks it (D-05; PNGs arrive from the user later per D-04). git add the dir.

    Create tests/test_brand_avatars.py mirroring tests/test_cover_art_avatar.py style. Unit tests use tmp_path + monkeypatch to stub `brand_avatars._res.files` to return tmp_path-rooted package data (analog in PATTERNS.md §test_brand_avatars.py). Implement: test_lookup_registered_providers (all 7 keys resolve when stub PNG present), test_lookup_gbs_returns_none, test_lookup_missing_file_returns_none, and an unknown-key test. The source-grep drift-guards (test_apply_art_tier_has_brand_avatar_branch, test_bind_station_resets_brand_avatar) also live in this file but will go RED until Task 2 — write them now per Nyquist (Wave 0 scaffold) reading NOW_PLAYING_SRC = Path(__file__).parent.parent / "musicstreamer" / "ui_qt" / "now_playing_panel.py".
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_brand_avatars.py -x -k "lookup" </automated>
  </verify>
  <acceptance_criteria>
    - source: `grep -c '"SomaFM"\|"DI.fm"\|"RadioTunes"\|"JazzRadio"\|"RockRadio"\|"ClassicalRadio"\|"ZenRadio"' musicstreamer/brand_avatars.py` reports the 7 keys present (filter comments: `grep -v '^#'` first)
    - source: `grep -c 'GBS' musicstreamer/brand_avatars.py` returns 0 (GBS.FM not registered — D-01)
    - source: `grep -q 'def lookup' musicstreamer/brand_avatars.py` and `grep -q 'os.path.isfile' musicstreamer/brand_avatars.py` (D-04 missing-asset guard)
    - file exists: musicstreamer/ui_qt/brand-avatars/.gitkeep is git-tracked (`git ls-files musicstreamer/ui_qt/brand-avatars/.gitkeep` non-empty)
    - test: `.venv/bin/python -m pytest tests/test_brand_avatars.py -x -k "lookup"` — all registry unit tests GREEN
  </acceptance_criteria>
  <done>brand_avatars.py registry resolves all 7 provider_name keys (file-present → path, file-absent → None), GBS.FM and unknown keys → None; asset dir git-tracked with .gitkeep; registry unit tests GREEN; source-grep drift-guard tests present (RED until Task 2).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: now_playing_panel wiring, drift-guards, and PyInstaller datas</name>
  <files>musicstreamer/ui_qt/now_playing_panel.py, tests/test_cover_art_avatar.py, tests/test_brand_avatars.py, packaging/windows/MusicStreamer.spec</files>
  <read_first>
    - .planning/phases/89c-provider-brand-avatar-cover-slot-fallback/89C-PATTERNS.md (§now_playing_panel.py MODIFY, §MusicStreamer.spec MODIFY)
    - musicstreamer/ui_qt/now_playing_panel.py (L219 _make_circular_pixmap, L347 _last_avatar_path, L909/935-936 bind_station reset, L2087/2127-2132 _apply_art_tier, L2173/2183 _on_cover_art_ready trigger, L2205 _set_avatar_pixmap_from_path, L2267 _show_station_logo_in_cover_slot)
    - tests/test_cover_art_avatar.py (L23-38 test_mb_caa_runs_before_channel_avatar — the source-grep pattern to mirror)
    - packaging/windows/MusicStreamer.spec (L122-125 datas list)
  </read_first>
  <behavior>
    - source-grep test_brand_lookup_only_in_cover_exhausted_branch (in test_cover_art_avatar.py): `_resolve_brand_avatar_fallback` appears within _on_cover_art_ready body (after `def _on_cover_art_ready`, before the next top-level `def `), and does NOT appear inside bind_station; `brand_avatars.lookup` does not appear in cover_art.py / fetch_cover_art
    - source-grep test_apply_art_tier_has_brand_avatar_branch (in test_brand_avatars.py): `_last_brand_avatar` appears within the _apply_art_tier body, ordered AFTER the `_last_avatar_path` branch and BEFORE the `else` logo fallback
    - source-grep test_bind_station_resets_brand_avatar (in test_brand_avatars.py): `_last_brand_avatar = None` appears within the bind_station body
  </behavior>
  <action>
    Edit musicstreamer/ui_qt/now_playing_panel.py:
    1. __init__ (after L347): declare `self._last_brand_avatar: Optional[str] = None  # Phase 89c D-11`.
    2. bind_station reset block (alongside `self._last_avatar_path = None` at L936): add `self._last_brand_avatar = None  # Phase 89c D-11: stale-station bleed guard` (Pitfall 3).
    3. _apply_art_tier (L2127-2132): insert a 4th branch BETWEEN the `elif self._last_avatar_path is not None` branch and the final `else` — `elif self._last_brand_avatar is not None: self._set_brand_avatar_pixmap(self._last_brand_avatar)` (D-11; precedence order MUST be real cover > _last_avatar_path > _last_brand_avatar > logo — Pitfall 8).
    4. _on_cover_art_ready `if not path:` branch (L2183): replace the `self._show_station_logo_in_cover_slot()` call with `self._resolve_brand_avatar_fallback()` (D-07 — this is THE single hook point; the existing `return` stays).
    5. Add new method `_resolve_brand_avatar_fallback(self) -> None` (place near _set_avatar_pixmap_from_path) implementing D-08 three-tier resolution: step 1 — if self._station and a truthy `provider_avatar_path` whose `os.path.join(paths.data_dir(), rel)` is a file, call `_set_avatar_pixmap_from_path(rel)` and return (reuses _last_avatar_path safely — these non-icy_disabled stations have _last_avatar_path None, Collision Analysis confirms no clash); step 2 — `abs_path = brand_avatars.lookup(self._station.provider_name or "")`, if truthy call `_set_brand_avatar_pixmap(abs_path)` and return (D-08 step 2); step 3 — `_show_station_logo_in_cover_slot()` (D-08 step 3 fallback). Import brand_avatars and paths locally inside the method (mirror existing local-import idiom in _set_avatar_pixmap_from_path).
    6. Add new method `_set_brand_avatar_pixmap(self, abs_path: str) -> None` copying _set_avatar_pixmap_from_path's shape EXACTLY but: takes an already-ABSOLUTE path (do NOT join paths.data_dir() — Pitfall 1); on QPixmap.isNull() set `self._last_brand_avatar = None` BEFORE `_show_station_logo_in_cover_slot()` (isNull+clear-before-fallback, Pitfall 4); on success use `n = self._current_art_tier or 180`, `_make_circular_pixmap(pix, n)` (D-06), `self.cover_label.setPixmap(circ)`, then `self._last_brand_avatar = abs_path`. Do NOT touch _last_cover_path or _last_avatar_path.

    Add source-grep drift-guard test_brand_lookup_only_in_cover_exhausted_branch to tests/test_cover_art_avatar.py mirroring test_mb_caa_runs_before_channel_avatar (read now_playing_panel.py + cover_art.py as text; positional asserts per the behavior block).

    Edit packaging/windows/MusicStreamer.spec: add the datas tuple `("../../musicstreamer/ui_qt/brand-avatars", "musicstreamer/ui_qt/brand-avatars")` immediately after the icons entry at L123 (Pitfall 9 — destination MUST be the full namespace path; frozen-build-env-missing-runtime-components memory).
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_brand_avatars.py tests/test_cover_art_avatar.py -x</automated>
  </verify>
  <acceptance_criteria>
    - source: `grep -c '_resolve_brand_avatar_fallback' musicstreamer/ui_qt/now_playing_panel.py` is >= 2 (the call site in _on_cover_art_ready + the def)
    - source: `grep -q 'self._last_brand_avatar = None' musicstreamer/ui_qt/now_playing_panel.py` (bind_station reset + isNull clear)
    - source: `grep -q 'def _set_brand_avatar_pixmap' musicstreamer/ui_qt/now_playing_panel.py` and the method does NOT contain `data_dir()` (Pitfall 1 — verify by reading the method body)
    - source: `grep -q 'brand_avatars.lookup' musicstreamer/ui_qt/now_playing_panel.py` and `grep -L 'brand_avatars' musicstreamer/cover_art.py` confirms cover_art.py is untouched (D-12)
    - source: `grep -q 'brand-avatars' packaging/windows/MusicStreamer.spec` with destination `musicstreamer/ui_qt/brand-avatars` (Pitfall 9)
    - test: `.venv/bin/python -m pytest tests/test_brand_avatars.py tests/test_cover_art_avatar.py -x` — all GREEN including the 3 source-grep drift-guards and the existing test_mb_caa_runs_before_channel_avatar
  </acceptance_criteria>
  <done>The `if not path:` branch calls _resolve_brand_avatar_fallback; three-tier resolution (override → registry → logo) wired; _set_brand_avatar_pixmap renders bundled PNGs from absolute paths via _make_circular_pixmap without joining data_dir; _last_brand_avatar tracked in __init__, reset in bind_station, replayed as the 4th _apply_art_tier branch; spec datas entry added; all drift-guard + registry tests GREEN.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| bundled package data → process | brand-avatars/*.png loaded read-only from importlib.resources (trusted, ships in repo/bundle) |
| filesystem → QPixmap decoder | brand PNG bytes decoded by Qt's image decoder (framework-level surface; same exposure as every existing logo/avatar render) |
| DB providers.avatar_path → render | provider_avatar_path read for D-08 step-1; written only by the Phase 89.1 non-silent-reset path (no new write in this plan) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-89c-01 | Tampering | brand-avatars/*.png (bundled asset) | accept | Assets ship in the repo/PyInstaller bundle; same trust level as icons/. No user-writable path feeds this in Plan 01. Tampering requires write access to the install tree (out of scope). |
| T-89c-02 | Denial of Service | QPixmap decode of bundled PNG | mitigate | lookup() gates on os.path.isfile and _set_brand_avatar_pixmap guards on QPixmap.isNull() → malformed/absent PNG falls back to station logo, never crashes (Pitfall 4). |
| T-89c-03 | Information Disclosure | brand_avatars.lookup path resolution | accept | Filename derived from a fixed static dict keyed on provider_name (no user input in the path); no traversal possible — the dict is the single normalization point. |
| T-89c-04 | Tampering | provider_avatar_path read (D-08 step-1) | accept | Plan 01 only READS this column; the value originates from the Phase 89.1 atomic write path. Write-side validation is covered in Plan 02 (the upload override). |
| T-89c-SC | Tampering | npm/pip/cargo installs | accept | No new packages (RESEARCH §Package Legitimacy Audit: not applicable — stdlib + existing project code only). No install task in this plan. |

No HIGH-severity threats. The attack surface is bundled read-only assets plus an existing DB column read; all decode failures degrade gracefully to current station-logo behavior.
</threat_model>

<verification>
- `.venv/bin/python -m pytest tests/test_brand_avatars.py tests/test_cover_art_avatar.py -x` — registry unit tests + all source-grep drift-guards GREEN.
- Source-grep confirms _resolve_brand_avatar_fallback fires only in _on_cover_art_ready (D-12), cover_art.py untouched (D-07), brand-avatars datas entry present in the spec (D-05).
- After wave merge (scoped): `.venv/bin/python -m pytest tests/ -x -k "not integration"`.
</verification>

<success_criteria>
- ART-AVATAR-11: registry keyed on the 7 exact provider_name strings; GBS.FM excluded; missing PNG → None (current behavior).
- ART-AVATAR-12: resolution-exhausted `if not path:` branch resolves override → registry → logo with circular crop; cover_art.py precedence chain unchanged (no MB-CAA short-circuit, SC5); unregistered providers reach _show_station_logo_in_cover_slot (no regression, SC4).
- D-11 tier-replay wired; D-05 frozen-build bundling explicit.
</success_criteria>

<output>
Create `.planning/phases/89c-provider-brand-avatar-cover-slot-fallback/89c-01-SUMMARY.md` when done.
</output>
