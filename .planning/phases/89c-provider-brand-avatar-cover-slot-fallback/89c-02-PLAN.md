---
phase: 89c-provider-brand-avatar-cover-slot-fallback
plan: 02
type: execute
wave: 2
depends_on: ["89c-01"]
files_modified:
  - musicstreamer/ui_qt/edit_station_dialog.py
  - tests/test_brand_avatars.py
autonomous: true
requirements: [ART-AVATAR-11, ART-AVATAR-12]

must_haves:
  truths:
    - "D-09: EditStationDialog exposes a 'Choose brand image…' picker (any provider) that writes the chosen image to the provider-keyed avatar file and persists providers.avatar_path"
    - "D-09: the write goes through assets.write_provider_avatar + repo.update_provider_avatar_path (non-silent-reset single-column UPDATE, Pitfall 5) — no broad save"
    - "D-09a: the manual brand-image pick is a synchronous QFileDialog path, NOT _AvatarFetchWorker; it does not touch the YouTube/Twitch auto-fetch (_refresh_avatar_btn stays YT/Twitch-only and is unaffected)"
    - "D-09 (Pitfall 7): when station.provider_id is None (new/unsaved station) the picker no-ops with a 'save station first' status, never writing None.png"
    - "ART-AVATAR-11/D-08 step-1: a user-supplied brand image overrides the bundled mark because provider_avatar_path is checked first in _resolve_brand_avatar_fallback (wired in 89c-01)"
  artifacts:
    - path: "musicstreamer/ui_qt/edit_station_dialog.py"
      provides: "_on_choose_brand_image handler + _choose_brand_image_btn in the avatar row"
      contains: "_on_choose_brand_image"
  key_links:
    - from: "musicstreamer/ui_qt/edit_station_dialog.py::_on_choose_brand_image"
      to: "musicstreamer.assets.write_provider_avatar"
      via: "synchronous file read → provider-keyed atomic write"
      pattern: "write_provider_avatar"
    - from: "musicstreamer/ui_qt/edit_station_dialog.py::_on_choose_brand_image"
      to: "repo.update_provider_avatar_path"
      via: "non-silent-reset single-column persist"
      pattern: "update_provider_avatar_path"
---

<objective>
Add the EditStationDialog "Choose brand image…" upload override (D-09): a synchronous file picker, for ANY provider, that writes the chosen image to the provider-keyed avatar file and persists providers.avatar_path via the non-silent-reset path. This overrides the bundled mark (D-08 step 1, wired in 89c-01) and also covers providers with no bundled asset.

Purpose: Lets the user supply or override a provider brand image without waiting for a bundled PNG, completing the D-04 "wiring lands now, images land as the user provides them" story. Closes D-09a: the manual pick is structurally disjoint from the YouTube/Twitch auto-fetch (different URL gate, no _AvatarFetchWorker), so the two semantics never clobber each other.

Output: _on_choose_brand_image handler + the picker button in edit_station_dialog.py, plus a source-grep drift-guard test.
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

<notes>
- Run tests via .venv/bin/python (memory: run-tests-with-venv-python). system python3 lacks PySide6.QtWidgets.
- D-09a is RESOLVED (RESEARCH §D-09a Resolution): SomaFM/AA URLs do NOT match the is_avatar_url gate ("youtube.com"/"youtu.be"/"twitch.tv"), so the auto-fetch _AvatarFetchWorker never fires for ICY providers, and the manual picker (this plan) operates in a disjoint code path. The existing _refresh_avatar_btn stays YouTube/Twitch-only — do NOT change its gating.
- This plan depends on 89c-01: _resolve_brand_avatar_fallback D-08 step-1 already reads provider_avatar_path, so the uploaded override renders on the next cover-miss with zero additional render code here.
</notes>

<interfaces>
<!-- Contracts the executor needs. Extracted from live source + PATTERNS.md §edit_station_dialog.py MODIFY. -->

Avatar row layout (edit_station_dialog.py ~L498-516): existing QHBoxLayout `avatar_row` with _avatar_preview (QLabel 64x64), _avatar_status (QLabel), addStretch(), _refresh_avatar_btn (QPushButton "Refresh avatar", default disabled). The new "Choose brand image…" button appends here.

_on_choose_logo (~L1384) — the EXACT shape to mirror (synchronous QFileDialog.getOpenFileName → asset write → preview refresh). The brand picker copies this shape but swaps the write for the provider-keyed path.

Reused as-is (no changes):
  assets.write_provider_avatar(provider_id: int, data: bytes) -> str   (assets.py L63 — atomic mkstemp+os.replace; returns data_dir()-relative path; keys by provider_id, Pitfall 6)
  repo.update_provider_avatar_path(provider_id: int, path: Optional[str]) -> None   (repo.py L965 — non-silent-reset single-column UPDATE)
  self._refresh_avatar_preview() (~L1558 — already reads provider_avatar_path; no change needed)

Pitfall-7 guard idiom (~L1331): `if self._station.provider_id is None: self._avatar_status.setText("…"); return`
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: "Choose brand image…" picker + provider-keyed persist (D-09/D-09a)</name>
  <files>musicstreamer/ui_qt/edit_station_dialog.py, tests/test_brand_avatars.py</files>
  <read_first>
    - .planning/phases/89c-provider-brand-avatar-cover-slot-fallback/89C-PATTERNS.md (§edit_station_dialog.py MODIFY — avatar row, _on_choose_logo analog, persist pattern)
    - .planning/phases/89c-provider-brand-avatar-cover-slot-fallback/89C-RESEARCH.md (§D-09a Resolution, §Pitfalls 5/6/7)
    - musicstreamer/ui_qt/edit_station_dialog.py (avatar_row ~L498-516, _on_choose_logo ~L1384, Pitfall-7 guard ~L1331, _on_avatar_fetched persist ~L1501-1514, _refresh_avatar_preview ~L1558)
    - musicstreamer/assets.py (write_provider_avatar ~L63)
    - musicstreamer/repo.py (update_provider_avatar_path ~L965)
  </read_first>
  <behavior>
    - source-grep test_choose_brand_image_uses_provider_keyed_persist (in test_brand_avatars.py): edit_station_dialog.py defines `_on_choose_brand_image`; its body references `write_provider_avatar` and `update_provider_avatar_path` and does NOT reference `_AvatarFetchWorker` (D-09a — synchronous, not the network worker, Pitfall 5)
    - source-grep: `_on_choose_brand_image` body contains a `provider_id is None` guard (Pitfall 7) before any write
  </behavior>
  <action>
    Edit musicstreamer/ui_qt/edit_station_dialog.py:
    1. In the avatar_row setup (~L498-516), after the existing `self._refresh_avatar_btn.clicked.connect(self._on_refresh_avatar_clicked)` line, add a new `self._choose_brand_image_btn = QPushButton("Choose brand image…", self)`, append it to `avatar_row`, and connect its `clicked` signal to `self._on_choose_brand_image`. Visible for ALL providers (NOT URL-gated — D-09a). Do NOT alter _refresh_avatar_btn's existing YouTube/Twitch-only enable gating.
    2. Add method `_on_choose_brand_image(self) -> None` copying the _on_choose_logo shape: FIRST guard `if self._station.provider_id is None:` → set _avatar_status text "Save station first to set a brand image" and return (Pitfall 7 — never write None.png). Then `QFileDialog.getOpenFileName(self, "Choose brand image", "", "Images (*.png *.jpg *.jpeg *.webp)")`; if no path, return. Read the file bytes, call `assets.write_provider_avatar(self._station.provider_id, data)` (provider-keyed, Pitfall 6), assign the returned rel path to `self._station.provider_avatar_path`, call `self._refresh_avatar_preview()`, set a "Brand image saved" status, then persist via `self._repo.update_provider_avatar_path(self._station.provider_id, rel_path)` (non-silent-reset, Pitfall 5 — NOT a broad save). Match the exact in-memory→preview→persist 3-step sequence from _on_avatar_fetched. Use a synchronous file read — NO _AvatarFetchWorker (D-09a).

    Add a source-grep drift-guard test_choose_brand_image_uses_provider_keyed_persist to tests/test_brand_avatars.py reading edit_station_dialog.py as text: find `def _on_choose_brand_image`, assert its body (up to the next top-level `def `) contains "write_provider_avatar" and "update_provider_avatar_path" and "provider_id is None", and does NOT contain "_AvatarFetchWorker".
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_brand_avatars.py -x -k "choose_brand_image"</automated>
  </verify>
  <acceptance_criteria>
    - source: `grep -c 'def _on_choose_brand_image' musicstreamer/ui_qt/edit_station_dialog.py` returns 1
    - source: `grep -c 'Choose brand image' musicstreamer/ui_qt/edit_station_dialog.py` >= 1 (button label + dialog title)
    - source: the _on_choose_brand_image body references write_provider_avatar AND update_provider_avatar_path AND a `provider_id is None` guard, and does NOT reference _AvatarFetchWorker (verified by the new source-grep test)
    - test: `.venv/bin/python -m pytest tests/test_brand_avatars.py -x -k "choose_brand_image"` GREEN
    - regression: `.venv/bin/python -m pytest tests/test_brand_avatars.py tests/test_cover_art_avatar.py -x` all GREEN (89c-01 guards still pass)
  </acceptance_criteria>
  <done>A "Choose brand image…" picker appears in the avatar row for any provider; clicking it (when provider_id is set) writes the chosen image to the provider-keyed avatar file and persists providers.avatar_path via the non-silent-reset update; new-station guard no-ops cleanly; no _AvatarFetchWorker involvement; source-grep drift-guard GREEN.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| user → QFileDialog file path | user picks an arbitrary image file path (untrusted selection) |
| picked file bytes → QPixmap / atomic write | untrusted image bytes decoded by Qt and written to the provider-keyed avatar file |
| user → providers.avatar_path DB write | the picked image triggers a single-column DB UPDATE keyed on provider_id |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-89c-05 | Tampering | provider-keyed avatar file write | mitigate | Filename is derived from `provider_id` (an int from the DB), NOT from user input — no path traversal from the picked file name. Write goes through assets.write_provider_avatar's atomic mkstemp+os.replace (no partial/corrupt file on failure). |
| T-89c-06 | Denial of Service | QPixmap decode of user-picked image | mitigate | Decode failure surfaces as a cleared preview (existing _refresh_avatar_preview QPixmap.isNull guard); a malformed file does not crash the dialog. Cover-slot render is separately guarded in 89c-01 (_set_avatar_pixmap_from_path isNull → logo fallback). |
| T-89c-07 | Tampering | providers.avatar_path UPDATE | mitigate | Persist uses the dedicated non-silent-reset single-column UPDATE (Pitfall 5) — cannot zero out unrelated provider columns; scoped by provider_id WHERE clause. |
| T-89c-08 | Elevation of Privilege | new/unsaved station (provider_id None) | mitigate | Pitfall-7 guard returns early before any write, so write_provider_avatar(None) / update_provider_avatar_path(None) (a silent 0-row UPDATE) never executes. |
| T-89c-09 | Information Disclosure | Qt image decoder (framework surface) | accept | Same decoder exposure as every existing logo/avatar picker (_on_choose_logo). No new attack surface beyond the established pattern; risk accepted at framework level (ASVS L1 — local desktop app, no remote attacker on the file picker). |
| T-89c-SC | Tampering | npm/pip/cargo installs | accept | No new packages (RESEARCH §Package Legitimacy Audit: not applicable). No install task. |

No HIGH-severity threats. The user-supplied image is the only untrusted input; the provider-keyed filename (derived from an int provider_id, never from user input) eliminates path traversal, atomic write prevents corruption, and the non-silent-reset persist prevents collateral column damage.
</threat_model>

<verification>
- `.venv/bin/python -m pytest tests/test_brand_avatars.py -x -k "choose_brand_image"` — the D-09/D-09a drift-guard GREEN.
- `.venv/bin/python -m pytest tests/test_brand_avatars.py tests/test_cover_art_avatar.py -x` — 89c-01 guards still pass.
- Manual UAT (needs Qt display, per VALIDATION §Manual-Only): EditStationDialog "Choose brand image…" for a SomaFM station → pick a PNG → preview updates, providers.avatar_path set in DB, cover slot shows the upload on the next cover-miss.
- After wave merge (scoped): `.venv/bin/python -m pytest tests/ -x -k "not integration"`.
</verification>

<success_criteria>
- D-09: user can supply/override a provider brand image for any provider via EditStationDialog; persisted through the non-silent-reset path; overrides the bundled mark (D-08 step 1).
- D-09a: manual pick and YouTube/Twitch auto-fetch are disjoint — no clobber; no _AvatarFetchWorker in the brand-pick path.
- Pitfall 7: new-station picker no-ops with a clear status, never writing None.png.
</success_criteria>

<output>
Create `.planning/phases/89c-provider-brand-avatar-cover-slot-fallback/89c-02-SUMMARY.md` when done.
</output>
