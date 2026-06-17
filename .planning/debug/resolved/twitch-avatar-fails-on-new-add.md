---
status: diagnosed
trigger: "New Twitch station avatar fails to fetch on first add; works on re-edit. add vs edit flow differs."
created: 2026-06-17T13:45:04Z
updated: 2026-06-17T13:45:04Z
---

## Current Focus

hypothesis: CONFIRMED — on new-add, self._station.provider_id is None and stays None through accept(); the avatar fetch is gated on provider_id != None (line 1331), so it is skipped. On re-edit, get_station() rehydrates provider_id from DB so the gate passes.
test: code trace of new-add vs edit flow
expecting: confirmed
next_action: report root cause (diagnosis only, no edits)

## Symptoms

expected: Adding a new Twitch station with a valid twitch.tv URL resolves and renders the channel avatar on first save.
actual: New-add path shows "No avatar found" / no avatar. Re-opening the same station in EDIT mode and saving again fetches and renders the avatar correctly.
errors: none (silent — avatar status shows "No channel avatar (station has no provider)" on the add path)
reproduction: New Station -> paste twitch.tv URL -> Save. Avatar absent. Re-open in Edit -> Save. Avatar appears.
started: Phase 89B (Twitch avatar support)

## Eliminated

(none — first hypothesis confirmed)

## Evidence

- timestamp: 2026-06-17T13:45:04Z
  checked: main_window.py:1230-1236 _on_new_station_clicked
  found: New station created via repo.create_station() which INSERTs only name (repo.py:675-680). The Station passed to EditStationDialog has provider_id=None.
  implication: On add, self._station.provider_id is None at dialog open.

- timestamp: 2026-06-17T13:45:04Z
  checked: edit_station_dialog.py:1320-1356 _on_url_timer_timeout avatar branch
  found: After is_avatar_url detection, line 1331 guards `if self._station.provider_id is None: ... return` — skips fetch entirely with status "No channel avatar (station has no provider)".
  implication: On add (provider_id None), the auto-fetch never runs. This is the Pitfall-7 single provider_id guard.

- timestamp: 2026-06-17T13:45:04Z
  checked: edit_station_dialog.py grep of self._station.provider_id
  found: provider_id is only READ (lines 1331, 1353, 1514) — never assigned anywhere in the dialog.
  implication: Even though _on_save derives provider_id, self._station.provider_id is never refreshed in-memory.

- timestamp: 2026-06-17T13:45:04Z
  checked: edit_station_dialog.py:1699-1717 _on_save provider derivation
  found: _on_save derives provider_name = "Twitch: <login>" for blank-provider twitch URLs (D-04 guard at line 1699 `if not provider_name`), then provider_id = repo.ensure_provider(provider_name) (line 1706) and writes it to DB via repo.update_station. It does NOT assign self._station.provider_id, does NOT trigger an avatar fetch, and calls self.accept() at line 1788 which closes the dialog.
  implication: The newly-created provider_id exists in the DB after first save, but no avatar fetch is ever launched during the add flow.

- timestamp: 2026-06-17T13:45:04Z
  checked: main_window.py:1251-1258 _on_edit_requested + repo.py:682-697 get_station
  found: Edit path re-fetches via repo.get_station() which LEFT JOINs providers and sets provider_id from the DB row (repo.py:697). After the first save created the provider, the re-edited Station now has a non-None provider_id.
  implication: On re-edit the guard at line 1331 passes, so the debounced fetch fires and the avatar resolves — explaining why edit works but first-add does not.

## Resolution

root_cause: On a new-station add, self._station.provider_id is None (placeholder created by repo.create_station with no provider) and is never updated in-memory. The debounced avatar auto-fetch in _on_url_timer_timeout is gated on provider_id != None (edit_station_dialog.py:1331), so it is skipped on the add path. _on_save derives and persists a provider_id but neither refreshes self._station.provider_id nor triggers an avatar fetch before accept() — so the first add never fetches. On re-edit, get_station rehydrates provider_id from the DB, the gate passes, and the fetch fires.
fix: (diagnosis only — see report) In _on_save, after `provider_id = repo.ensure_provider(provider_name)` (line 1706), assign `self._station.provider_id = provider_id` and `self._station.provider_name = provider_name`, then trigger the avatar fetch path before accept() when the URL is an avatar URL and no provider_avatar_path exists yet. Keeps the D-04 blank-provider guard and the single Pitfall-7 provider_id guard intact.
verification: (pending implementer)
files_changed: []
