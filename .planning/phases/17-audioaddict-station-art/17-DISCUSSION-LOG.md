# Phase 17: AudioAddict Station Art - Discussion Log

**Session:** 2026-04-03
**Areas discussed:** Logo download timing, Editor AA URL detection, repo.insert_station art wiring

---

## Logo Download Timing

**Q:** How should logo downloads happen during bulk AA import?
**Options:** Concurrent in import loop / Sequential in import loop / Post-import background pass
**Selected:** Concurrent in import loop

**Q:** Should the import dialog wait for all logos before showing "done"?
**Options:** Wait for logos / Don't wait — logos in background
**Selected:** Wait for logos — progress shows "Fetching logos…" phase before "Done"

---

## Editor AA URL Detection

**Q:** When a user pastes an AA stream URL in the station editor, how should logo fetch be triggered?
**Options:** URL pattern match / Only after API key is stored / Dedicated fetch-from-AA button
**Selected:** URL pattern match — detect known AA domains on focus-out, same hook as YouTube

**Q:** Where does the editor get the API key?
**Options:** Read from DB / Prompt user for key
**Selected:** Prompt user for key (via "Fetch from URL" button popover when no stored key)

**Q:** Where should the API key prompt appear?
**Options:** Inline below URL field / In the Fetch button popover / Reuse AA import flow
**Selected:** In the Fetch button popover

---

## repo.insert_station Art Wiring

**Q:** How should downloaded logos flow into the station record during bulk import?
**Options:** Mirror YouTube thumbnail pattern / Download directly to station art dir
**Selected:** Mirror YouTube thumbnail pattern — temp file → copy_asset_for_station() → path

**Q:** How to attach art when station is already inserted (concurrent model)?
**Options:** Insert station ID first, update art after / Buffer logo then single insert
**Selected:** Insert station ID first, update art after — requires adding repo.update_station_art()

---

*Log generated: 2026-04-03*
