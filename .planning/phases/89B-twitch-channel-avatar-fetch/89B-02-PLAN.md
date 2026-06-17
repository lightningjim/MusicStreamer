---
phase: 89B-twitch-channel-avatar-fetch
plan: 02
type: execute
wave: 2
depends_on: ["89B-01"]
files_modified:
  - musicstreamer/ui_qt/edit_station_dialog.py
  - tests/test_edit_station_dialog_avatar.py
  - tests/test_twitch_provider_assign.py
autonomous: true
requirements: [ART-AVATAR-04]
must_haves:
  truths:
    - "A twitch.tv URL enables the Refresh-avatar button and triggers the debounced auto-fetch, just like a YouTube URL (D-08, RESEARCH #5)"
    - "_AvatarFetchWorker.run() dispatches through yt_import.get_avatar_fetcher() — a twitch.tv URL calls the twitch fetcher (not the YouTube fetcher); node_runtime is passed only for YouTube (D-08, RESEARCH #5 / Pitfall 1)"
    - "The Twitch fetch branch carries the same provider_id-is-None guard and reuse-on-open skip as the YouTube branch (Pitfall 7, 89.1 D-07)"
    - "On save, when the Provider field is blank AND the URL is twitch.tv, the login is derived and repo.ensure_provider('Twitch: <login>') sets the station provider_id; a user-typed Provider is NEVER overwritten (D-02, D-03, D-04, Pitfall 3)"
    - "All Twitch fetch failures fall back non-blocking to the station thumbnail and Save is always allowed (D-07); the no-token status text points the user to Accounts"
    - "The stored Twitch avatar renders through the unchanged cover_art/now_playing provider-keyed path — no renderer or cover-slot edits in this phase (D-11)"
    - "The fetched avatar bytes are stored per-provider as assets/channel-avatars/{provider_id}.png via the existing assets.write_provider_avatar(provider_id, data) and persisted with repo.update_provider_avatar_path(provider_id, path) — never per-station {station_id}.png; the roadmap's <station-id>.png wording is superseded (D-01, 89.1 D-09/D-10)"
    - "No staleness TTL or per-bind/per-play refetch is added — the avatar is fetched once when the provider has no avatar and updated only via the manual Refresh button (D-09)"
    - "Refresh re-fetches and overwrites the single per-provider {provider_id}.png so every sibling Twitch station of that streamer updates; the existing 89.1 shared-effect Refresh hint is reused with no Twitch-specific divergence (D-10, 89.1 D-08)"
  artifacts:
    - path: "tests/test_edit_station_dialog_avatar.py"
      provides: "Wave 0 unit tests: twitch.tv URL enables Refresh; worker dispatch picks twitch fetcher"
      min_lines: 40
    - path: "tests/test_twitch_provider_assign.py"
      provides: "Wave 0 unit tests: ensure_provider('Twitch: <login>') on blank-only; manual provider preserved"
      min_lines: 30
  key_links:
    - from: "musicstreamer/ui_qt/edit_station_dialog.py:_AvatarFetchWorker.run"
      to: "yt_import.get_avatar_fetcher"
      via: "registry dispatch by URL sniff"
      pattern: "get_avatar_fetcher"
    - from: "musicstreamer/ui_qt/edit_station_dialog.py:_on_save"
      to: "repo.ensure_provider"
      via: "Twitch: <login> on blank provider"
      pattern: "Twitch: "
---

<objective>
Wire the Twitch avatar fetcher into `EditStationDialog`: add `twitch.tv` to the URL-detection gates so it enables the Refresh button and triggers the debounced auto-fetch, change `_AvatarFetchWorker.run()` to dispatch through the per-provider registry (so twitch.tv URLs hit the Twitch fetcher), and add login→provider derivation on save (`ensure_provider("Twitch: <login>")`) gated to the blank-provider case.

Purpose: Closes the dispatch gap (RESEARCH #5 / Pitfall 1) so the Plan 01 fetcher is actually reachable from the dialog, and gives blank-provider Twitch stations a stable `"Twitch: <login>"` dedup anchor (D-02/D-03/D-04) so the per-provider avatar (`{provider_id}.png`) is keyed correctly. Storage, persist, cover-slot swap, and circular-crop render are all reused unchanged (D-11) — this plan adds NO renderer or cover-slot code.

Output: Edits to `edit_station_dialog.py` (three detection/dispatch sites + the save path) and Wave 0 unit tests.
</objective>

<execution_context>
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.5.0/workflows/execute-plan.md
@/home/kcreasey/.claude/plugins/cache/gsd-plugin/gsd/3.5.0/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/89B-twitch-channel-avatar-fetch/89B-CONTEXT.md
@.planning/phases/89B-twitch-channel-avatar-fetch/89B-RESEARCH.md
@.planning/phases/89B-twitch-channel-avatar-fetch/89B-VALIDATION.md
@.planning/phases/89B-twitch-channel-avatar-fetch/89B-01-PLAN.md

<interfaces>
<!-- Verified from codebase. Exact line numbers given. Use directly. -->

From musicstreamer/yt_import.py:
- `get_avatar_fetcher(provider: str) -> Optional[Callable[[str], bytes]]`
- After Plan 01: `get_avatar_fetcher("twitch")` returns `twitch_helix.fetch_channel_avatar`; `get_avatar_fetcher("youtube")` returns the YouTube fetcher.
- NOTE: the YouTube fetcher takes a `node_runtime=` kwarg; the Twitch fetcher takes only `(url)`.

From musicstreamer/ui_qt/edit_station_dialog.py:
- `_AvatarFetchWorker.run()` (L169-180): currently `data = yt_import.fetch_channel_avatar(self._url, node_runtime=self._node_runtime)` then `assets.write_provider_avatar(self._provider_id, data)`; on exception `self.finished.emit("", token)`. Constructor (L159) already carries `url, token, station_id, parent, node_runtime, provider_id`.
- `_on_url_text_changed` (L1263-1275): `is_yt = "youtube.com" in lower or "youtu.be" in lower`; `self._refresh_avatar_btn.setEnabled(is_yt)` at L1275.
- `_on_url_timer_timeout` (L1277-1337): YouTube avatar branch at L1306 `if "youtube.com" in lower or "youtu.be" in lower:` — includes the provider_id-None guard (L1312-1316), the reuse-on-open skip (L1317-1323), and the worker launch (L1325-1337).
- `_on_avatar_fetched` (L1459+): persists via `self._repo.update_provider_avatar_path(self._station.provider_id, rel_path)` (L1495) and calls `_refresh_avatar_preview()` (L1487). REUSED unchanged.
- `_on_refresh_avatar_clicked` (L1565-1583): sets `_force_avatar_refresh = True` in try/finally then calls `_on_url_timer_timeout()`. REUSED unchanged.
- `_on_save` (L1647+): `provider_name = self.provider_combo.currentText().strip()` (L1658); `provider_id = repo.ensure_provider(provider_name)` (L1675); then `repo.update_station(station.id, name, provider_id, ...)` (L1677).

From musicstreamer/repo.py:
- `ensure_provider(name) -> Optional[int]` (L481) — INSERT OR IGNORE; returns None for blank name.

UNCHANGED this phase (D-11): cover_art._channel_avatar_lookup, now_playing_panel.bind_station — they already resolve via station.provider_avatar_path.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Wave 0 — failing tests for dispatch + provider derivation</name>
  <files>tests/test_edit_station_dialog_avatar.py, tests/test_twitch_provider_assign.py</files>
  <read_first>
    - musicstreamer/ui_qt/edit_station_dialog.py (L130-181 worker; L1263-1337 detection; L1647-1690 save)
    - tests/test_edit_station_dialog.py — existing dialog-test harness/fixtures (how it constructs the dialog under PySide6, mocks repo); mirror its setup
    - .planning/phases/89B-twitch-channel-avatar-fetch/89B-VALIDATION.md — exact test names + manual-only carve-outs
  </read_first>
  <behavior>
    Write RED. Run with `.venv/bin/python` (system python3 lacks PySide6.QtWidgets). Mock the network/registry — no live Helix.
    tests/test_edit_station_dialog_avatar.py:
    - test_twitch_url_enables_refresh_btn: after setting url_edit to a twitch.tv URL and triggering _on_url_text_changed, `_refresh_avatar_btn.isEnabled()` is True (and stays True for a youtube URL; False for an unrelated URL).
    - test_avatar_worker_dispatches_twitch: monkeypatch yt_import.get_avatar_fetcher to a spy; construct _AvatarFetchWorker with a twitch.tv URL and run() (or its dispatch logic); assert get_avatar_fetcher was called with "twitch" and the YouTube fetcher was NOT called. (Prefer a source-grep drift-guard ALSO: assert run() source contains `get_avatar_fetcher` and no longer hard-codes `fetch_channel_avatar(self._url`.)
    - test_youtube_dispatch_passes_node_runtime: a youtube URL still routes to the youtube fetcher and node_runtime is forwarded (regression guard for Pitfall 1).
    tests/test_twitch_provider_assign.py:
    - test_save_derives_provider_for_blank_twitch: dialog with blank provider_combo + twitch.tv URL `.../twitchdev`; on save, repo.ensure_provider is called with exactly "Twitch: twitchdev" and the returned id is passed to update_station.
    - test_save_preserves_manual_provider_for_twitch: dialog with provider_combo set to "Live Sports" + twitch.tv URL; on save, ensure_provider is called with "Live Sports" (NOT "Twitch: ...") — manual value respected (D-04 / Pitfall 3).
    - test_save_non_twitch_url_unchanged: blank provider + a non-twitch URL → ensure_provider called with the blank/empty provider_name (no Twitch derivation) — regression guard.
  </behavior>
  <action>
    Create the two test files mirroring the existing tests/test_edit_station_dialog.py harness (QApplication fixture, mocked repo). Use a spy/mock for repo.ensure_provider to capture the exact name argument. For worker dispatch, monkeypatch yt_import.get_avatar_fetcher and assert the provider key. Where ordering/precedence matters (dispatch selection, blank-only gate) ADD source-grep drift-guards (read the edit_station_dialog.py source and assert the presence of `get_avatar_fetcher`, `"Twitch: "`, and a blank-check before the Twitch derivation) per project convention. Do NOT perform live network or live Helix calls. Tests MUST be RED now (dispatch + derivation not yet implemented).
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_edit_station_dialog_avatar.py tests/test_twitch_provider_assign.py -q 2>&1 | grep -E "failed|error|passed"</automated>
  </verify>
  <acceptance_criteria>
    - Both test files exist with the named test functions (test_twitch_url_enables_refresh_btn, test_avatar_worker_dispatches_twitch, test_youtube_dispatch_passes_node_runtime, test_save_derives_provider_for_blank_twitch, test_save_preserves_manual_provider_for_twitch, test_save_non_twitch_url_unchanged).
    - `.venv/bin/python -m pytest tests/test_edit_station_dialog_avatar.py tests/test_twitch_provider_assign.py -q` collects and the new behavioral tests FAIL (RED) — the dispatch/derivation behavior is not yet implemented.
    - No live network call occurs (get_avatar_fetcher / urlopen monkeypatched).
  </acceptance_criteria>
  <done>The six named tests exist and run RED; no live network.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Twitch URL detection + registry dispatch in _AvatarFetchWorker</name>
  <files>musicstreamer/ui_qt/edit_station_dialog.py</files>
  <read_first>
    - musicstreamer/ui_qt/edit_station_dialog.py (L130-181 worker.run; L1263-1337 detection branches)
    - musicstreamer/yt_import.py (L281-287 get_avatar_fetcher + registrations)
    - tests/test_edit_station_dialog_avatar.py — the contract from Task 1
    - .claude/skills/spike-findings-musicstreamer/SKILL.md — Qt-threading notes (run() must not touch widgets / QTimer)
  </read_first>
  <action>
    In `_on_url_text_changed` (~L1272-1275): add `is_twitch = "twitch.tv" in lower`; change the Refresh-button gate to `self._refresh_avatar_btn.setEnabled(is_yt or is_twitch)` (Pitfall 2). In `_on_url_timer_timeout` (~L1306): restructure the avatar-fetch branch so the provider_id-None guard and the reuse-on-open skip (L1312-1323) run for BOTH youtube and twitch.tv URLs — e.g. compute `is_avatar_url = ("youtube.com" in lower or "youtu.be" in lower or "twitch.tv" in lower)` and keep the existing guards/skip and worker launch under that single gate (do not duplicate the guard — Pitfall 7). The worker launch is unchanged (it already passes url/token/station_id/provider_id/node_runtime). In `_AvatarFetchWorker.run()` (~L172-176): replace the hard-coded `yt_import.fetch_channel_avatar(self._url, node_runtime=self._node_runtime)` with registry dispatch — sniff the URL (`lower = (self._url or "").lower()`; provider key = "twitch" if "twitch.tv" in lower else "youtube"), call `fetcher = yt_import.get_avatar_fetcher(provider_key)`, raise if fetcher is None, then call `fetcher(self._url, node_runtime=self._node_runtime)` ONLY for youtube and `fetcher(self._url)` for twitch (the Twitch fetcher has no node_runtime param — Pitfall 1). Keep the existing `write_provider_avatar` + `finished.emit` success path and the `except Exception: self.finished.emit("", token)` WR-04 backstop unchanged. run() MUST NOT touch widgets or call QTimer (spike landmine). Do NOT edit cover_art.py or now_playing_panel.py (D-11).
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_edit_station_dialog_avatar.py -q</automated>
  </verify>
  <acceptance_criteria>
    - `_on_url_text_changed` source contains `twitch.tv` and `setEnabled(is_yt or is_twitch)` (or equivalent boolean enabling Refresh for twitch.tv).
    - `_on_url_timer_timeout`'s avatar branch fires for twitch.tv URLs and retains the provider_id-None guard + reuse-on-open skip (a single shared guard, not duplicated).
    - `_AvatarFetchWorker.run()` no longer hard-codes `fetch_channel_avatar(self._url`; it calls `yt_import.get_avatar_fetcher(...)` and passes node_runtime only on the youtube path.
    - test_twitch_url_enables_refresh_btn, test_avatar_worker_dispatches_twitch, test_youtube_dispatch_passes_node_runtime PASS.
    - cover_art.py and now_playing_panel.py are unmodified (git diff shows no changes to those files).
  </acceptance_criteria>
  <done>Twitch URLs enable Refresh and route through the registry to the twitch fetcher; YouTube dispatch (with node_runtime) is preserved; dispatch tests green.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Login→provider derivation on save (blank-only)</name>
  <files>musicstreamer/ui_qt/edit_station_dialog.py</files>
  <read_first>
    - musicstreamer/ui_qt/edit_station_dialog.py (L1647-1690 _on_save)
    - musicstreamer/twitch_helix.py — reuse its `_parse_login` (or the same idiom) for login derivation
    - musicstreamer/repo.py (L481-488 ensure_provider)
    - tests/test_twitch_provider_assign.py — the contract from Task 1
  </read_first>
  <action>
    In `_on_save` (~L1658-1675): after reading `provider_name = self.provider_combo.currentText().strip()` and BEFORE `provider_id = repo.ensure_provider(provider_name)`, add the Twitch derivation gated to the blank-provider case: if `not provider_name` AND the current URL (`self.url_edit.text().strip().lower()`) contains `"twitch.tv"`, derive the login (reuse `twitch_helix._parse_login(url)` — import twitch_helix; do not re-implement the parse) and set `provider_name = f"Twitch: {login}"` when the login is non-empty. Leave the existing `provider_id = repo.ensure_provider(provider_name)` and `repo.update_station(..., provider_id, ...)` lines unchanged — the derived name flows through them. NEVER overwrite a user-typed provider (the `not provider_name` gate enforces D-04 / Pitfall 3). The `"Twitch: "` prefix and lowercase login satisfy D-03. Do not add a fetch trigger here — the avatar fetch is owned by the debounced/Refresh path (D-08); this task only ensures the provider_id (and thus the `{provider_id}.png` key) exists at save time.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_twitch_provider_assign.py -q</automated>
  </verify>
  <acceptance_criteria>
    - `_on_save` source contains `"Twitch: "` and a blank-provider guard (`not provider_name`) preceding the Twitch derivation; it imports/uses `twitch_helix._parse_login` (no duplicated parse logic).
    - test_save_derives_provider_for_blank_twitch passes: ensure_provider called with exactly `"Twitch: twitchdev"` for a blank-provider twitch.tv station.
    - test_save_preserves_manual_provider_for_twitch passes: a user-typed provider is passed to ensure_provider verbatim (no Twitch override).
    - test_save_non_twitch_url_unchanged passes: non-twitch blank-provider save is unchanged.
    - Full scoped run green: `.venv/bin/python -m pytest tests/test_twitch_helix.py tests/test_edit_station_dialog_avatar.py tests/test_twitch_provider_assign.py -q`.
  </acceptance_criteria>
  <done>Blank-provider twitch.tv stations get a `"Twitch: <login>"` provider on save; manual providers are preserved; provider-assign tests green.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| user URL/provider input → DB | The twitch.tv URL and Provider field are user-typed; the login is derived and used to mint a provider name |
| worker thread → Qt main thread | _AvatarFetchWorker.run() runs off the main thread; results marshalled only via the queued finished Signal |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-89b-02 | Tampering | _on_save login→provider derivation | mitigate | The derived login is used ONLY to build the `"Twitch: <login>"` provider NAME string passed to `ensure_provider` — never as a filesystem path. The avatar file is keyed on the integer provider_id (write_provider_avatar, Plan-01/89.1), so a crafted login cannot traverse the filesystem. Derivation reuses `twitch_helix._parse_login`, which strips query/fragment/path. |
| T-89b-03 | Elevation of Privilege / DoS | _AvatarFetchWorker.run() Qt-threading | mitigate | run() never touches widgets and never calls QTimer (spike landmine); all results marshalled via the queued `finished` Signal; the `except Exception: finished.emit("", token)` WR-04 backstop ensures the worker never raises into Qt and every failure falls back non-blocking to the station thumbnail (D-07). Save is always allowed. |
| T-89b-04 | Spoofing | D-04 provider-overwrite | mitigate | A user-typed Provider is never silently replaced by a Twitch-derived one — the `not provider_name` gate (Pitfall 3) prevents a pasted twitch.tv URL from hijacking a manually-chosen provider identity. |
| T-89b-SC | Tampering | npm/pip/cargo installs | accept | No new packages installed this phase (stdlib + existing project deps only). No install task. |
</threat_model>

<verification>
- `.venv/bin/python -m pytest tests/test_edit_station_dialog_avatar.py tests/test_twitch_provider_assign.py -q` green.
- Scoped suite green: `.venv/bin/python -m pytest tests/test_twitch_helix.py tests/test_edit_station_dialog_avatar.py tests/test_twitch_provider_assign.py tests/test_edit_station_dialog.py -q`.
- git diff shows NO changes to musicstreamer/cover_art.py or musicstreamer/ui_qt/now_playing_panel.py (D-11 — render path unchanged).
- Manual (per VALIDATION.md): live Twitch login → ICY-disabled twitch.tv station renders the streamer avatar circular in the cover slot; no-token station Saves fine and uses the thumbnail.
</verification>

<success_criteria>
- ART-AVATAR-04 (integration half): twitch.tv URLs enable Refresh + trigger the debounced fetch; the worker dispatches to the Twitch fetcher; blank-provider Twitch stations get a `"Twitch: <login>"` provider so the per-provider avatar is keyed; the stored avatar renders through the unchanged cover-slot path.
- D-04 honored: manual providers never overwritten.
- D-07 honored: all failures non-blocking, Save always allowed.
- D-11 honored: zero renderer / cover-slot edits.
</success_criteria>

<output>
Create `.planning/phases/89B-twitch-channel-avatar-fetch/89B-02-SUMMARY.md` when done.
</output>
