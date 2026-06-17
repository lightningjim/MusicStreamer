---
phase: 89B-twitch-channel-avatar-fetch
plan: 03
type: execute
wave: 1
depends_on: [89B-02]
files_modified:
  - musicstreamer/ui_qt/edit_station_dialog.py
  - tests/test_twitch_provider_assign.py
autonomous: true
gap_closure: true
requirements: [ART-AVATAR-04]
must_haves:
  truths:
    - "Adding a NEW Twitch station with a valid twitch.tv URL fetches and persists the streamer avatar on the FIRST save (no re-edit required)"
    - "After ensure_provider in _on_save, self._station.provider_id and self._station.provider_name reflect the derived provider (in-memory consistency, D-04/D-02)"
    - "Adding a Twitch station under an EXISTING provider that already has an avatar does NOT trigger a network fetch (D-07 reuse gate)"
    - "Edit-path avatar fetch (debounced _on_url_timer_timeout) still works unchanged"
    - "A user-typed (manual) provider is never overwritten by Twitch login derivation (D-04 blank-provider guard at line 1699 preserved)"
  artifacts:
    - path: "musicstreamer/ui_qt/edit_station_dialog.py"
      provides: "Synchronous fetch-and-persist of the Twitch avatar in _on_save before accept(), plus in-memory provider_id/provider_name refresh"
      contains: "self._station.provider_id = provider_id"
    - path: "tests/test_twitch_provider_assign.py"
      provides: "Add-path coverage: first-save fetch+persist, existing-provider-with-avatar no-refetch, in-memory provider refresh"
      contains: "def test_save_add_path_fetches_avatar"
  key_links:
    - from: "musicstreamer/ui_qt/edit_station_dialog.py:_on_save"
      to: "repo.update_provider_avatar_path"
      via: "synchronous persist of fetched avatar bytes before accept()"
      pattern: "update_provider_avatar_path"
    - from: "musicstreamer/ui_qt/edit_station_dialog.py:_on_save"
      to: "yt_import.get_avatar_fetcher / assets.write_provider_avatar"
      via: "synchronous fetch dispatch on the add path"
      pattern: "write_provider_avatar"
---

<objective>
Close the UAT add-path gap: adding a NEW Twitch station with a valid `twitch.tv` URL must fetch and persist the streamer avatar on the FIRST save, identical to the edit path.

Root cause (confirmed, see debug session): on new-station add, `self._station.provider_id` is `None` (placeholder from `repo.create_station()` with no provider) and is never refreshed in-memory. The debounced avatar fetch in `_on_url_timer_timeout` is gated on `provider_id is None` (Pitfall-7 guard at line 1331), so it is skipped on the add path. `_on_save` derives and persists `provider_id` (line 1706 via `repo.ensure_provider`) but never refreshes `self._station.provider_id` and never triggers a fetch before `accept()`. On re-edit, `get_station()` rehydrates `provider_id` from the DB so the gate passes and the fetch fires.

Purpose: deliver ART-AVATAR-04's promise on the primary add flow (the common case for manually-added Twitch stations).
Output: a refreshed in-memory provider plus a synchronous fetch-and-persist in `_on_save`, with add-path test coverage.
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
@.planning/phases/89B-twitch-channel-avatar-fetch/89B-HUMAN-UAT.md
@.planning/debug/twitch-avatar-fails-on-new-add.md

# The file to fix and the existing async path being mirrored synchronously
@musicstreamer/ui_qt/edit_station_dialog.py

# Existing add-path test harness to mirror (mocked repo + qtbot fixtures)
@tests/test_twitch_provider_assign.py

<interfaces>
<!-- Contracts the executor needs. Already exist; do not redefine. -->

The async worker body to mirror SYNCHRONOUSLY — musicstreamer/ui_qt/edit_station_dialog.py:169-192 (`_AvatarFetchWorker.run`):
- dispatch: `lower = url.lower(); provider_key = "twitch" if "twitch.tv" in lower else "youtube"`
- `fetcher = yt_import.get_avatar_fetcher(provider_key)`  (returns Callable[[str], bytes] | None)
- twitch call: `data = fetcher(url)`  (NO node_runtime kwarg for twitch)
- youtube call: `data = fetcher(url, node_runtime=self._node_runtime)`
- persist bytes: `rel_path = assets.write_provider_avatar(provider_id, data)` (atomic, returns relative path str)
- DB persist: `repo.update_provider_avatar_path(provider_id, rel_path)` (main thread, D-09 non-silent-reset)

twitch_helix.fetch_channel_avatar(url) raises on failure (ValueError / RuntimeError / urllib errors) — the worker wraps it in try/except and emits "" on failure. A synchronous caller MUST replicate that swallow-and-fallback (D-07: failures are non-blocking, Save always succeeds).

D-07 reuse gate already in _on_url_timer_timeout:1336-1342:
- skip network fetch if `provider_avatar_path` is set AND not `_force_avatar_refresh`.

Pitfall-7 guard already in _on_url_timer_timeout:1331:
- `if self._station.provider_id is None: ...; return`  (MUST remain untouched and not be duplicated)

D-04 blank-provider guard already in _on_save:1699:
- `if not provider_name:` … derive `provider_name = f"Twitch: {_login}"` (assignment MUST stay inside this branch)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add-path RED tests (first-save fetch+persist, no-refetch, in-memory refresh)</name>
  <files>tests/test_twitch_provider_assign.py</files>
  <behavior>
    Extend the existing mocked-repo + qtbot harness in tests/test_twitch_provider_assign.py. All tests run headless against MagicMock repo (no live token, no network). Mirror the existing fixtures (`station_blank_provider`, `repo`, `player`).

    - test_save_add_path_fetches_avatar:
      - Station with provider_id=None, provider_avatar_path=None, twitch.tv URL, blank provider combo.
      - repo.ensure_provider.return_value = 9.
      - Patch yt_import.get_avatar_fetcher to return a stub fetcher that returns b"PNGDATA"; patch assets.write_provider_avatar to return "assets/channel-avatars/9.png".
      - After button_box.accepted.emit(): assert assets.write_provider_avatar was called with provider_id=9 and the bytes; assert repo.update_provider_avatar_path was called with (9, "assets/channel-avatars/9.png").
    - test_save_add_path_refreshes_in_memory_provider:
      - Same setup. After save: assert d._station.provider_id == 9 and d._station.provider_name == "Twitch: twitchdev".
    - test_save_existing_provider_with_avatar_no_refetch:
      - Station with provider_id=7, provider_avatar_path="assets/channel-avatars/7.png" (D-07 reuse), manual provider "Twitch: existing" or matching combo so ensure_provider returns 7.
      - Patch get_avatar_fetcher with a stub whose call asserts it is NOT invoked (or assert mock not called). After save: assert the fetcher was NOT called and update_provider_avatar_path was NOT called (avatar already present, D-07).
    - test_save_manual_provider_not_overwritten_still_holds (regression, may reuse existing test_save_preserves_manual_provider_for_twitch — add an assertion that, given a manual provider with provider_avatar_path=None and twitch URL, the fetch still keys on the MANUAL provider_id, never the derived "Twitch:" name).
    - test_save_fetch_failure_is_nonblocking:
      - Patch the stub fetcher to raise RuntimeError("no token"). After save: assert no exception propagates, d._save_succeeded is True, accept() ran (button_box.accepted handling completed), update_provider_avatar_path NOT called.

    Add a source-grep drift-guard test (filter comment lines to avoid self-invalidation):
    - test_on_save_has_inmemory_provider_assignment: read edit_station_dialog.py source, strip lines starting with '#', assert it contains both `self._station.provider_id = provider_id` and `self._station.provider_name = provider_name` in non-comment text, and that they appear after the `repo.ensure_provider(` call site.
  </behavior>
  <action>
    Append the new tests to tests/test_twitch_provider_assign.py. Reuse the existing module-level fixtures; do not duplicate qtbot/player/repo. Use unittest.mock.patch on `musicstreamer.yt_import.get_avatar_fetcher` and `musicstreamer.assets.write_provider_avatar` (patch at the import site actually used by _on_save — match how Task 2 imports them; coordinate the patch target with the import form chosen in Task 2). Trigger save via `d.button_box.accepted.emit()` exactly as the existing tests do.

    These tests MUST fail initially (RED): the in-memory assignment and synchronous fetch-and-persist do not exist yet. Run them, confirm red, then proceed to Task 2.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_twitch_provider_assign.py -q 2>&1 | tail -20</automated>
  </verify>
  <done>New add-path tests exist and FAIL against the current (unfixed) _on_save, confirming the gap. Existing tests in the file still pass.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Refresh in-memory provider + synchronous fetch-and-persist in _on_save before accept()</name>
  <files>musicstreamer/ui_qt/edit_station_dialog.py</files>
  <behavior>
    Make the Task 1 RED tests pass without breaking the existing 89B suite.
  </behavior>
  <action>
    Edit `_on_save` (musicstreamer/ui_qt/edit_station_dialog.py, around lines 1699-1717).

    Step A — refresh in-memory provider (gap.missing item 1):
    Immediately AFTER `provider_id = repo.ensure_provider(provider_name)` (line 1706), assign:
      `self._station.provider_id = provider_id`
      `self._station.provider_name = provider_name`
    This keeps the in-memory Station consistent so the Pitfall-7 guard at line 1331 would pass AND so downstream consumers / _refresh_avatar_preview resolve correctly. Place these two lines outside the `if not provider_name:` block (they must run for both the derived-Twitch case and the manual-provider case) but AFTER ensure_provider. Do NOT touch the D-04 `if not provider_name:` block (line 1699) — the `f"Twitch: {_login}"` assignment stays inside it.

    Step B — synchronous fetch-and-persist on the add path (gap.missing item 2):
    After `repo.update_station(...)` (line 1708-1717) and the `station.station_art_path = self._logo_path` line, add a synchronous avatar fetch-and-persist block. Do NOT call the async `_on_url_timer_timeout()` and do NOT spin up `_AvatarFetchWorker` — per the diagnosis, accept()'s `_shutdown_avatar_fetch_worker()` does a bounded wait that does NOT pump the queued `finished->_on_avatar_fetched` slot, so an async fetch kicked right before accept() may never persist. Run it synchronously instead.

    Implement a small private helper, e.g. `_maybe_fetch_avatar_sync(self, url, provider_id)`, and call it from _on_save before `self.accept()`. The helper MUST:
      1. Return immediately (no-op) if `provider_id is None` — mirrors the Pitfall-7 intent without duplicating the line-1331 guard (this is a separate save-path call site, not a second copy of the debounce guard).
      2. Sniff the URL: only proceed when it is an avatar URL (`"youtube.com" in lower or "youtu.be" in lower or "twitch.tv" in lower`). Reuse the same predicate the debounce path uses. For this gap the live case is twitch.tv; keep the predicate general so the add path matches the debounce path.
      3. Honor the D-07 reuse gate: if `getattr(self._station, "provider_avatar_path", None)` is truthy AND not `getattr(self, "_force_avatar_refresh", False)`, return without fetching (existing-provider-with-avatar adds must NOT refetch — invariant 3).
      4. Dispatch through the registry exactly like _AvatarFetchWorker.run(): `provider_key = "twitch" if "twitch.tv" in lower else "youtube"`; `fetcher = yt_import.get_avatar_fetcher(provider_key)`; if None, return. Call `data = fetcher(url)` for twitch, `data = fetcher(url, node_runtime=self._node_runtime)` for youtube.
      5. Persist: `rel_path = assets.write_provider_avatar(provider_id, data)`; then `self._repo.update_provider_avatar_path(provider_id, rel_path)`; set `self._station.provider_avatar_path = rel_path`.
      6. Wrap the fetch+persist in try/except Exception that swallows and sets a non-blocking status (e.g. `self._avatar_status.setText("No avatar found — cover will use the station thumbnail")`) — failures are NON-blocking, Save always succeeds (D-07). Never re-raise; `_on_save` must still reach `self._save_succeeded = True` and `self.accept()`.
      7. Wrap the network portion in a wait cursor (`QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))` / `restoreOverrideCursor()` in a finally) to signal the brief block. UI-block is bounded by the urllib/socket timeouts inside twitch_helix (≈10s worst case) — acceptable and consistent with the existing teardown `worker.wait(2000)`-then-`worker.wait()` discipline.

    Import discipline: mirror the existing late-import style used in the worker (`from musicstreamer import yt_import, assets as _assets`) and twitch_helix usage already present in _on_save. Coordinate the patch target in Task 1 with whatever import form you choose here.

    Invariants to preserve (verify by inspection):
      - D-04 blank-provider guard at line 1699 untouched; the `f"Twitch: {_login}"` derivation stays inside `if not provider_name:`.
      - Pitfall-7 single provider_id guard at line 1331 untouched and not duplicated (the helper's own provider_id None-check is a distinct save-path call site).
      - Per-provider keying ({provider_id}.png) unchanged — write_provider_avatar(provider_id, data) reuses the existing storage path; an add under an existing provider with an avatar reuses it (Step 3 gate), it does not refetch.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_twitch_provider_assign.py tests/test_edit_station_dialog_avatar.py -q 2>&1 | tail -25</automated>
  </verify>
  <done>All Task 1 add-path tests pass (GREEN). The in-memory provider is refreshed and a synchronous fetch-and-persist runs in _on_save before accept(). D-04 and Pitfall-7 guards verified untouched by grep.</done>
</task>

<task type="auto">
  <name>Task 3: Regression sweep — edit path + avatar dialog + provider-assign suites</name>
  <files>tests/test_edit_station_dialog.py, tests/test_edit_station_dialog_avatar.py, tests/test_twitch_provider_assign.py, tests/test_twitch_helix.py</files>
  <action>
    Run the focused regression set with `.venv/bin/python` (system python3 lacks PySide6.QtWidgets and yields false failures — see MEMORY). Do NOT run the full >600s suite; scope to the avatar/edit-station/twitch surface.

    Confirm:
      - Edit-path debounced fetch behavior is unchanged (test_edit_station_dialog_avatar.py: dispatch + refresh-button tests still pass).
      - Provider derivation D-04 still holds (test_twitch_provider_assign.py existing tests).
      - twitch_helix fetch contract unchanged (test_twitch_helix.py).
      - No new failures introduced in test_edit_station_dialog.py.

    Two pre-existing known failures may appear in the broader edit-station suite (per MEMORY: "two known pre-existing failures"); confirm any failure is one of those pre-existing ones and NOT newly introduced by this change. If a NEW failure appears, fix it before marking done.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_edit_station_dialog_avatar.py tests/test_twitch_provider_assign.py tests/test_twitch_helix.py -q 2>&1 | tail -15</automated>
  </verify>
  <done>Edit-path, avatar-dispatch, provider-assign, and twitch_helix suites pass (modulo the two documented pre-existing failures, none newly introduced). The add-path gap is closed and no regression is introduced.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| dialog → gql.twitch.tv | Twitch login (from URL) crosses to the GQL endpoint; auth-token cookie sent |
| network response → disk | fetched image bytes written via assets.write_provider_avatar |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-89B-03-01 | Tampering | login derivation feeding ensure_provider / fetch | mitigate | Reuse `twitch_helix._parse_login` which clamps to `[a-z0-9_]+` (T-89b-02 already enforced); add path calls the SAME derivation, no new parse |
| T-89B-03-02 | Denial of Service | synchronous fetch blocks the UI thread in _on_save | accept | Bounded by twitch_helix urllib/socket timeouts (~10s worst case), wrapped in a wait cursor; consistent with existing teardown `worker.wait(2000)` discipline; failure is swallowed non-blocking (D-07) |
| T-89B-03-03 | Information disclosure | auth-token cookie sent on Helix/GQL request | mitigate | No change to transport — reuses twitch_helix.fetch_channel_avatar whose Authorization header is scoped to the single Request object (T-89b-01); no new global opener/header |
| T-89B-03-SC | Tampering | npm/pip/cargo installs | mitigate | No new package installs in this gap-closure plan — N/A; no install tasks present |
</threat_model>

<verification>
- Add a new Twitch station with a valid twitch.tv URL and a blank Provider → first Save fetches and persists `{provider_id}.png`; avatar resolves in the now-playing cover slot WITHOUT re-editing.
- Add a Twitch station under an existing provider that already has an avatar → no network fetch, existing avatar reused (D-07).
- Edit an existing Twitch station → debounced fetch still works (unchanged).
- Manual provider + twitch URL → manual provider preserved, fetch keyed on manual provider_id (D-04).
- No-token / GQL failure on the add path → inline non-blocking note, Save succeeds, cover falls back to station thumbnail.
- grep confirms line-1331 Pitfall-7 guard and line-1699 D-04 guard are untouched and not duplicated.
</verification>

<success_criteria>
- Adding a NEW Twitch station fetches + persists the streamer avatar on FIRST save (gap closed).
- `self._station.provider_id` / `provider_name` refreshed in-memory after ensure_provider.
- Existing-provider-with-avatar add does NOT refetch (D-07).
- D-04 blank-provider guard and Pitfall-7 single provider_id guard preserved (untouched, not duplicated).
- Per-provider {provider_id}.png keying unchanged.
- Edit-path and twitch_helix suites pass; no new test failures.
</success_criteria>

<output>
Create `.planning/phases/89B-twitch-channel-avatar-fetch/89B-03-SUMMARY.md` when done.
</output>
