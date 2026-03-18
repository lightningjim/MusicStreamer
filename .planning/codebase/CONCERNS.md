# Codebase Concerns

**Analysis Date:** 2026-03-18

## Tech Debt

**Monolithic application structure:**
- Issue: All code (database, UI, playback, file handling) is in a single 511-line file (`main.py`)
- Files: `main.py`
- Impact: Hard to test individual components, difficult to reuse code, difficult to maintain. No separation of concerns between data layer, business logic, and UI presentation
- Fix approach: Extract Repo class to `repo.py`, create separate `models.py` for dataclasses, move playback logic to `player.py`, UI components to `ui.py`

**Tags stored as comma-separated strings:**
- Issue: Tags are stored as plain comma-separated strings in the database (line 52 comment: "comma-separated for now (simple step)")
- Files: `main.py` (database schema at lines 47-58, parsing at lines 123, 155, 460-461)
- Impact: Cannot efficiently query by tag, cannot handle tags with commas, no normalization (whitespace inconsistency), searching/filtering requires string manipulation
- Fix approach: Create a separate `tags` table with a junction table `station_tags` for proper M:M relationships. Implement tag normalization and validation

**No validation on user input:**
- Issue: URL input is not validated before storage or playback (line 337). Station names can be empty (line 336 has fallback to "Unnamed" but accepts any string). Provider names not validated
- Files: `main.py` (EditStationDialog._save at lines 335-351)
- Impact: Invalid URLs fail silently during playback with only generic error messages. Can create stations with no meaningful data. No guidance for users on expected URL formats
- Fix approach: Add URL format validation (regex for http/https/streaming protocols), check URL accessibility before saving, add constraints to database schema (NOT NULL where appropriate)

**Broad exception handling masks real issues:**
- Issue: Line 432-434 catches all exceptions with `except Exception as e` and only prints to console, converting to generic UI message "yt-dlp error"
- Files: `main.py` (MainWindow._play_station at lines 427-435)
- Impact: Network errors, authentication failures, format errors, and bugs are all treated the same. Users cannot distinguish between invalid URL, network timeout, or yt-dlp failure. Error is printed to console (may not be visible to end user)
- Fix approach: Catch specific exceptions (HTTPError, Timeout, ExtractorError), provide targeted error messages to user, log with structured logging instead of print

**File dialog error handling:**
- Issue: Line 318-319 catches GLib.Error silently with no feedback to user
- Files: `main.py` (EditStationDialog._choose_file at lines 311-319)
- Impact: User doesn't know if file dialog failed or was cancelled, silent failures make troubleshooting difficult
- Fix approach: Log the error, show error dialog to user if it's a real error (not cancellation)

## Known Bugs

**Database connection never closes:**
- Symptom: Database connection created in App.do_activate (line 501) is never closed, held open for lifetime of application
- Files: `main.py` (App.do_activate at lines 499-506, db_connect at lines 32-36)
- Trigger: Run the application normally - connection leaks immediately on startup
- Workaround: None; connection eventually closes when app terminates
- Impact: Memory leak (small), database file may be locked if app crashes ungracefully, violates resource management best practices

**Stream resolution can block UI:**
- Symptom: YouTube stream resolution via yt-dlp (line 428-429) runs synchronously on main thread
- Files: `main.py` (MainWindow._play_station at lines 411-447)
- Trigger: Double-click a YouTube station URL
- Workaround: Wait for operation to complete
- Impact: UI freezes during yt-dlp extraction (can take 5-10 seconds for YouTube), poor user experience. No indication that operation is in progress

**Asset file extension handling not robust:**
- Symptom: Line 188 extracts file extension with os.path.splitext but defaults to .png if extension is missing, with no validation of whether the result is an actual image format
- Files: `main.py` (copy_asset_for_station at lines 182-197)
- Trigger: User chooses file with no extension (e.g., "photo" instead of "photo.png")
- Impact: May copy non-image files with .png extension, leading to display errors. No validation that copied file is actually an image

**No error handling for file copy operation:**
- Symptom: shutil.copy2 (line 194) can fail (permissions, disk full) but exceptions are not caught
- Files: `main.py` (copy_asset_for_station at lines 182-197)
- Trigger: Copy asset when target directory not writable or disk is full
- Workaround: None; user gets Python traceback
- Impact: Application crashes when trying to copy image file. Asset is saved to database even though copy may have failed (database has path but file doesn't exist)

**Station art path not validated before display:**
- Symptom: Lines 286-298 check if file exists before displaying, but paths are user-controlled via database (line 349). Symlinks could point to sensitive files
- Files: `main.py` (EditStationDialog._refresh_pictures at lines 284-298)
- Trigger: Manually edit database to point to files outside assets directory
- Impact: Can display arbitrary files from filesystem within the app
- Fix approach: Validate that stored paths are within `ASSETS_DIR` using os.path.realpath

## Security Considerations

**No authentication/authorization:**
- Risk: Application has no user authentication. Anyone with access to the machine can modify all stations and their associations with providers
- Files: `main.py` (App, MainWindow, EditStationDialog)
- Current mitigation: Database and asset files stored in user's home directory with typical Unix permissions, so OS provides isolation between users
- Recommendations: Add application-level user concept with PIN/password if multi-user on same machine is needed. For now, document that this is single-user local app

**URL handling could enable malicious streaming:**
- Risk: User URLs are set directly in player (line 445) after optional yt-dlp resolution. Malicious URLs could be injected via database tampering
- Files: `main.py` (MainWindow._play_station at lines 411-447)
- Current mitigation: GStreamer playbin performs URL validation before connecting; most invalid URLs fail safely
- Recommendations: Validate URL format before setting on player (whitelist protocols: http, https, file only). Consider sandboxing playback if running untrusted content

**File path traversal vulnerability (low risk):**
- Risk: Asset paths stored in database (line 54: `album_fallback_path TEXT`). If path is not validated, could be set to `../../../etc/passwd` to access files outside assets directory
- Files: `main.py` (copy_asset_for_station lines 182-197, _refresh_pictures lines 284-298)
- Current mitigation: copy_asset_for_station always creates paths under ASSETS_DIR, storing relative paths; _refresh_pictures has os.path.exists check
- Recommendations: Add explicit validation using os.path.realpath to ensure stored paths resolve within ASSETS_DIR. Use pathlib.Path for safer path handling

**yt-dlp version management:**
- Risk: yt-dlp is updated frequently to maintain compatibility with YouTube. Old versions may not work; no version pinning
- Files: `main.py` (line 16 import), requirements not specified
- Current mitigation: None
- Recommendations: Create requirements.txt with pinned version, implement version check and upgrade notifications, handle API changes gracefully

## Performance Bottlenecks

**Synchronous YouTube resolution blocks UI:**
- Problem: yt-dlp.extract_info (line 429) can take 5-15 seconds on slow connections, blocking entire UI thread
- Files: `main.py` (MainWindow._play_station at lines 411-447)
- Cause: No async/threading mechanism; single-threaded Gtk event loop waits for yt-dlp to complete
- Improvement path: Move yt-dlp resolution to background thread using threading or GLib.idle_add, show "Loading..." indicator in UI, queue playback for when resolution completes

**Full station list loaded on startup:**
- Problem: All stations and provider names loaded into memory at app start (Repo.list_stations lines 105-128)
- Files: `main.py` (Repo.list_stations, MainWindow.reload_list)
- Cause: No pagination or lazy loading; as soon as app starts, all data is loaded
- Improvement path: For small datasets (<1000 stations) this is fine. Document limit. For larger datasets, implement lazy loading via scrolling or filtering

**Asset image scaling done in UI thread:**
- Problem: Gtk.Picture.set_filename (lines 289, 296) may load and decode large images on UI thread during refresh
- Files: `main.py` (EditStationDialog._refresh_pictures at lines 284-298)
- Cause: No pre-scaling or caching; every refresh decodes full image resolution for 128x128 display
- Improvement path: Pre-scale images to 128x128 when copying asset, use cached thumbnails for list display

## Fragile Areas

**Repo class tightly coupled to main window:**
- Files: `main.py` (Repo class at lines 88-180, used by MainWindow and EditStationDialog)
- Why fragile: Repo is instantiated once in App.do_activate (line 503) but passed around to multiple window instances. No connection pooling or lifecycle management. If one window's operation fails, entire app's data access is affected
- Safe modification: Extract Repo to separate module with singleton pattern or dependency injection. Add transaction context managers for atomic operations
- Test coverage: No tests exist; repo operations cannot be tested independently

**EditStationDialog manages mutable state:**
- Files: `main.py` (EditStationDialog class at lines 200-355)
- Why fragile: Dialog keeps local copies of art paths (lines 212-213) that diverge from database state. If dialog is cancelled, local state is lost. If user edits same station in another dialog, changes conflict. No locking or optimistic updates
- Safe modification: Use load-save pattern instead of keeping state in dialog. Load full station state into form, then save atomic transaction on dialog close. Add optimistic locking (updated_at timestamp) to detect conflicts
- Test coverage: No tests; UI state mutations cannot be verified

**Playback engine state not synchronized with UI:**
- Files: `main.py` (MainWindow._stop at lines 402-404, _play_station at lines 411-447)
- Why fragile: GStreamer player state (lines 368-374) and UI state (now_label at line 377) are manually synchronized. If playback error occurs mid-stream, UI label isn't updated. Player errors not listened to
- Safe modification: Implement GStreamer bus message handler to listen for EOS (end-of-stream), ERROR, STATE_CHANGED events. Update UI in response to actual player state changes
- Test coverage: No tests; playback state transitions not verified

**Database schema with triggers but no backup:**
- Files: `main.py` (db_init at lines 39-67 defines updated_at trigger)
- Why fragile: Trigger assumes server-side timestamp update works correctly. If someone modifies `updated_at` column manually (data corruption), trigger still fires. No schema versioning - adding columns requires manual migration
- Safe modification: Add schema version to database (PRAGMA user_version), implement migration functions for schema changes. Document that updated_at is managed by trigger
- Test coverage: No tests; trigger behavior not verified

## Scaling Limits

**Single SQLite database file:**
- Current capacity: SQLite handles up to ~100 GB files, but concurrent access limited. Typically fine for <10,000 records per table with single writer
- Limit: If app expands to support multiple users or instances, SQLite's locking becomes bottleneck. Multiple write operations will queue
- Scaling path: For single-user local app, SQLite is appropriate. If multi-device sync needed, migrate to client-server database (PostgreSQL) with conflict resolution

**Assets directory on local filesystem:**
- Current capacity: Filesystem limits apply. Typical ext4 can handle millions of files; practical limit is disk space
- Limit: If storing high-quality images for thousands of stations, disk usage grows (images can be 100KB-1MB each). No cleanup of orphaned assets
- Scaling path: Implement asset cleanup when stations are deleted, add compression/conversion to smaller formats, consider CDN if assets need to be shared

## Dependencies at Risk

**yt-dlp version incompatibility:**
- Risk: yt-dlp requires frequent updates to stay compatible with YouTube. Version pinning without updates means YouTube playback will break within months
- Impact: YouTube station streaming breaks silently or with cryptic yt-dlp errors. Users can't play major streaming source
- Migration plan: Pin version in requirements.txt, set up automated testing/CI to detect breaks, implement version check at startup with upgrade prompt, or migrate to official YouTube API (requires API key)

**GTK 4.0 API stability:**
- Risk: GTK 4.0 is relatively new; API surface may change in minor updates. Adwaita (libadwaita) 1.x API also evolving
- Impact: Dependency updates could break UI, require code changes
- Migration plan: Document tested versions (GTK 4.X, Adw 1.X), use semantic versioning constraints. Monitor upstream deprecation warnings

**GStreamer plugins dependency:**
- Risk: Audio output depends on PulseAudio sink (line 372) or fallback to system default. Not all systems have PulseAudio installed
- Impact: No audio output on systems using ALSA or PipeWire (ALSA case is handled by fallback, but fragile)
- Migration plan: Test on PipeWire systems, consider using PipeWire sink explicitly for newer systems. Graceful fallback if no audio sink available

## Missing Critical Features

**No persistence of playback state:**
- Problem: No memory of what was last playing, where in playlist user was. If app closes, state is lost
- Blocks: Can't resume listening to long streams. No history/recent tracks

**No error logging/diagnostics:**
- Problem: Errors are only printed to stdout (line 434), invisible to end users. No log file for debugging issues
- Blocks: Hard to diagnose playback failures, file copy errors, or database issues after the fact

**No graceful shutdown:**
- Problem: Closing app while GStreamer is playing doesn't stop playback cleanly. Player state may not be cleaned up
- Blocks: Can't verify all resources released. May leave stale state on disk

**No URL format validation:**
- Problem: User can enter any string as URL, playback fails later with generic error
- Blocks: Users don't know what URL formats are valid (HLS, HTTP, YouTube, etc.)

## Test Coverage Gaps

**No unit tests for Repo class:**
- What's not tested: Database queries, provider creation, station CRUD operations, foreign key constraints
- Files: `main.py` (Repo class at lines 88-180)
- Risk: Database logic changes can silently break queries. Duplicate provider handling not verified. Station-provider relationship not tested
- Priority: High - core data access should be tested before UI

**No tests for playback logic:**
- What's not tested: YouTube URL resolution, HLS stream handling, error recovery, state transitions
- Files: `main.py` (MainWindow._play_station at lines 411-447)
- Risk: Playback changes break for specific stream types (YouTube, HLS, HTTP). Error handling regressions go unnoticed
- Priority: High - most critical user-facing feature

**No tests for file operations:**
- What's not tested: Asset copying, path handling, file cleanup, handling of missing files
- Files: `main.py` (copy_asset_for_station at lines 182-197)
- Risk: Image upload fails for some file types, permissions issues not caught, orphaned assets accumulate
- Priority: Medium - secondary to playback but impacts user experience

**No UI/integration tests:**
- What's not tested: Dialog workflows (add/edit/delete stations), image preview loading, list refresh after edits
- Files: `main.py` (EditStationDialog, MainWindow.reload_list)
- Risk: UI state sync issues, dialog bugs, race conditions on rapid edits not detected
- Priority: Medium - manual testing catches these now, but fragile to regression

**No tests for database schema/migrations:**
- What's not tested: Initial schema creation, trigger behavior, updated_at timestamp accuracy
- Files: `main.py` (db_init at lines 39-67)
- Risk: Schema changes or corruption not detected. Trigger misbehavior not caught
- Priority: Low - schema is simple now, but increases as data model grows

---

*Concerns audit: 2026-03-18*
