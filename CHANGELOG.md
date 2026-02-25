# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.2] - 2026-02-23

### 🗑️ Alpine.js Frontend Removed
- **Legacy UI Removed**: All Jinja2/Alpine.js templates and static assets removed
- **React Only**: Application now requires `frontend/dist`; run `cd frontend && npm run build` before starting
- **Clear Error**: App fails fast with instructions if frontend not built

### 🕐 Cron-Only Scheduler
- **Replaced Interval Model**: Removed `schedule_hours`; all commands now use cron expressions
- **Global Default**: `DEFAULT_SCHEDULE_CRON` (default `0 3 * * *` = 3 AM daily) in Config → Scheduler
- **Timezone**: `SCHEDULER_TIMEZONE` config (or `TZ` env) for cron interpretation (e.g. `America/New_York`)
- **Per-Command Override**: Toggle "Override default schedule" in command edit dialog with custom cron
- **Queue by ID**: When multiple commands are due, queued in order by command id
- **Concurrency**: `MAX_PARALLEL_COMMANDS` default 1 (configurable); multiple workers process queue

### 🎨 Dark Theme
- **Softer Dark Mode**: Background changed from black to dark blue (`oklch(18% 0.03 255)`)

### 🔒 Config & Security
- **Secrets Obfuscation**: API returns `***` for sensitive config values; Config page masks by default
- **Show Key Button**: Eye icon to reveal sensitive values for verification (e.g. copy/paste errors)

### 🔌 WebSocket Removed
- **Streaming Logs Dropped**: WebSocket endpoint and client removed (never fully implemented)
- **Commands Page**: Manual refresh after run; no real-time updates

### 🎵 MusicBrainz Rate Limiting
- **MUSICBRAINZ_RATE_LIMIT**: Default 0.8 req/sec (~1.25s between requests); MusicBrainz allows 1/sec per IP
- **Don't add on rate limit**: When MB API returns 503 (rate limit), skip artist instead of adding to New Releases pending
- **get_artist_release_groups**: Returns `None` on error so callers can distinguish "fetch failed" from "not in MB"
- **Hardcoded User-Agent**: `Cmdarr/{version} (https://github.com/DeviantEng/Cmdarr)`; removed `MUSICBRAINZ_USER_AGENT` and `MUSICBRAINZ_CONTACT` config

### 🎵 Plex Large Library Support
- **PLEX_LIBRARY_SEARCH_TIMEOUT**: Configurable timeout (default 180s) for library search/fetch; increase for 500k+ track libraries
- **PLEX_TIMEOUT**: General API timeout (default 60s) remains configurable
- **Retry with backoff**: Search retries with 1.5× timeout on first failure

### 🛠️ Fixes & Improvements
- **Uptime Widget**: Fixed status page uptime (was always &lt;1m); now tracks app start time correctly
- **Command Queue**: When at capacity, new commands are queued instead of failing
- **Toast Display Names**: Run/queue toasts show friendly names (e.g. `[Deezer] Hard Rock Now -> Plex`) not backend IDs
- **Kill Execution**: Implemented `kill_execution`; cancels asyncio task (DB shows cancelled; thread may run to completion)
- **Timezone Handling**: TZ env priority, `tzdata` in requirements for minimal Linux/Docker; fallback to UTC when ZoneInfo fails
- **Maintenance First**: `playlist_sync_discovery_maintenance` is id 1; runs before playlist syncs if not run in 24h
- **Job History Refresh**: Manually triggered commands appear in history immediately without page refresh

### ⚙️ Other
- **README**: Prominent note that `npm run build` is required when running from source

## [0.3.1] - 2026-02-23

### 🔒 Security Fixes
- **ReDoS**: Fixed regex denial-of-service in Deezer URL parser (`utils/playlist_parser.py`)
- **XSS**: Escaped user input in Spotify OAuth callback template
- **Exception Exposure**: API handlers now return generic error messages instead of raw exception details

### 🆕 New Releases Discovery
- **Dismiss, Recheck, Ignore**: Three distinct actions with square icon buttons and tooltips
  - **Dismiss**: Clear from pending; will reappear on next rescan
  - **Recheck**: Verify in MusicBrainz; remove if album found
  - **Ignore**: Never show again (adds to dismissed table)
- **Link vs Action Separation**: Visual distinction between external links (Lidarr, MusicBrainz, Spotify, Add to MB) and action buttons
- **Backend Endpoints**: `/clear`, `/ignore`, `/recheck` with correct semantics
- **Clear All**: Button to clear entire pending list (items reappear on next scan)
- **Recheck Cache Fix**: Bypass MusicBrainz cache when rechecking so Harmony-added releases are found immediately

### 🎵 Last.fm Discovery
- **Configurable Sampling**: Query X Lidarr artists (default 3) instead of all—major performance fix for large libraries
- **Similar Per Artist**: Configurable Y similar artists per request (default 1)
- **Time-Based Cooldown**: Don't re-query an artist for N days (default 30); persists to `discovery_lastfm_queried.json`
- **Min Match Score**: Configurable 0–1 threshold (default 0.9) in command settings
- **Commands UI**: Editable `artists_to_query`, `similar_per_artist`, `artist_cooldown_days`, `limit`, `min_match_score`

## [0.3.0] - 2026-02-23

### 🆕 New Releases Discovery
- **New Command**: `new_releases_discovery` scans Lidarr artists for Spotify releases missing from MusicBrainz
- **Round-Robin Scanning**: Prioritizes never-scanned artists, then by last scan time; configurable `artists_per_run` (default 5)
- **Smart Filtering**: Excludes live recordings, compilations, guest appearances; configurable album types (album, EP, single)
- **One-Click Actions**: Open Lidarr, MusicBrainz artist page, or Harmony to add albums; Spotify album links
- **Dismiss & Restore**: Dismiss pending releases with optional restore from Status page
- **Artist Matching**: Lidarr Spotify link validation with fuzzy name matching; skip search for short names (≤4 chars); try all search results for best match instead of first hit only

### 🎨 Frontend Rewrite (Alpine.js → React)
- **React + Vite + TypeScript**: Full rewrite of the web UI with modern tooling
- **Component Library**: Radix UI primitives with Tailwind CSS and shadcn-style components
- **Client-Side Routing**: React Router for Commands, Config, Status, Import Lists, New Releases
- **Theme Support**: Dark/light mode with persistence
- **Improved UX**: Sonner toasts, responsive layout, cleaner forms and dialogs
- **Build Integration**: Frontend built to `frontend/dist`, served by FastAPI; CORS for Vite dev server (localhost:5173)
- **Legacy Fallback**: Jinja2 templates retained for `/status` and import list pages during transition

### 🏗️ Architecture & Database
- **New Models**: `NewReleasePending`, `ArtistScanLog`, `LidarrArtist`, `DismissedArtistAlbum`
- **Version Migrations**: Schema migrations for new tables and `artist_name` on dismissed items
- **Built-in Command Protection**: Delete disabled for discovery_lastfm, library_cache_builder, new_releases_discovery, playlist_sync_discovery_maintenance
- **Command Configuration**: Editable schedule, `artists_per_run`, and album types for new_releases_discovery

### 🔧 Fixes and Improvements
- **Startup Logging**: `setup_application_logging()` called in app lifespan; fixes missing logs on startup
- **MusicBrainz Client**: Wrapped in async context manager to avoid unclosed aiohttp sessions
- **Run Batch**: Clears artist/source/album_type filters before each run to avoid stale scan-artist data
- **Lidarr URLs**: Use MBID-based artist URLs (`/artist/{mbid}`) instead of numeric IDs
- **Playlist Sync**: Symbol-only track matching fix (e.g. †) for improved sync accuracy
- **Import Lists**: Clipboard copy fallback for HTTP/non-secure contexts; note about enable_artist_discovery
- **Plex**: Default timeout 30s→60s for large libraries; retry on search timeout

## [0.2.3] - 2025-11-15

Version 0.2.3 is the last 0.2.x release. Contains various fixes and enhancements, including improved playlist sync matching. Cmdarr is migrating from Alpine.js to a Node-based frontend (React/Vite). v0.2.3 remains stable(-ish) and fully functional(-ish), but no further development will happen in that form.

## [0.2.2] - 2025-10-23

🚀 New Features
- **Deezer Playlist Support**: Added Deezer client integration for syncing public playlists alongside existing Spotify support

🔧 Fixes and Improvements
- **Enhanced External Playlist Editing**: Added missing UI elements to the Edit window, that were previously only available on creation

## [0.2.1] - 2025-10-21

### 🚀 New Features
- **Live Log Streaming**: Real-time command execution monitoring in the UI with execution ID tracking for concurrent commands
- **Client Enablement Controls**: Added `PLEX_CLIENT_ENABLED` and `JELLYFIN_CLIENT_ENABLED` configuration options for granular service management
- **Parallel Command Limits**: Configurable maximum of 3 commands running simultaneously (range: 1-10) to prevent system overload

### 🔧 Fixes and Improvements
- **ListenBrainz Modal Parity**: Fixed create/edit modal inconsistencies for ListenBrainz playlist sync commands with proper retention settings and playlist type configuration
- **Enhanced Configuration Organization**: Moved Plex/Jellyfin cache settings to their respective client categories for better organization

## [0.2.0] - 2025-10-17

### 🎵 Major Playlist Sync Overhaul
- **Modular Playlist Sync Commands**: Completely redesigned playlist sync system with dynamic command creation
- **Spotify Support**: Added Spotify client for playlist synchronization (requires Spotify API tokens)
- **Direct Lidarr Integration**: Artists discovered from playlists are now added directly to Lidarr via API calls
- **Enhanced Execution Tracking**: Detailed statistics and real-time status updates for all playlist sync operations

### 🎨 UI/UX Enhancements
- **Homepage Redesign**: Root URL (/) now serves the commands page directly, eliminating redundant dashboard
- **Commands Page Redesign**: Added card/list view toggle with localStorage persistence for scalable command management
- **Advanced Filtering**: Added filter dropdown with status (enabled/disabled) and type (discovery/playlist sync) filters
- **Sortable List View**: Sortable table columns for name, schedule, last run, and next run with visual indicators
- **Enhanced Actions**: Improved action dropdowns with proper vertical stacking and better UX
- **Streamlined Navigation**: Removed duplicate navigation links and improved user flow
- **Enhanced Status Page**: Added system uptime display to consolidate all system information
- **Redesigned Config Page**: Replaced cluttered navigation tabs with organized dropdown categories
- **Improved Command Creation**: Streamlined playlist sync command creation with popup menu for source selection
- **Enhanced Execution History**: Detailed statistics display including track success rates and artist discovery results
- **Console Error Fixes**: Resolved Alpine.js template expression errors for cleaner browser console
- **Improved Logging**: Startup logs now show human-friendly command names instead of internal IDs

### 🏗️ Architecture Improvements
- **Command Type System**: Added `command_type` field to database for better command categorization
- **Database Migration Framework**: Enhanced migration system for seamless schema updates
- **Enhanced Error Handling**: Comprehensive error tracking and user feedback
- **Improved Logging**: Detailed execution logs with actionable information
- **Command Status Tracking**: Fixed Last Run status display to show Success/Failed instead of Unknown

### 🔒 Security & Reliability
- **Command Validation**: Enhanced validation prevents execution of non-existent commands
- **Rate Limiting**: Improved API rate limiting across all clients
- **Error Recovery**: Better error handling and recovery mechanisms

## [0.1.4] - 2025-09-18

### 🔧 Command Configuration Fixes
- **Fixed Command-Specific Settings**: Resolved issue where command-level configuration settings (like limit, min_match_score) were not taking effect
- **Improved Configuration Fallback**: Commands now properly use command-specific config with graceful fallback to global settings

## [0.1.3] - 2025-09-17

### 🔧 URL Structure Improvements
- **Clean Import List URLs**: Moved import list endpoints from `/api/import_lists/` to `/import_lists/` for better clarity and Lidarr compatibility
- **Fixed Lidarr Integration**: Resolved redirect issues that prevented Lidarr from properly consuming import list feeds
- **Simplified URL Structure**: Import lists now follow the clean pattern `/import_lists/<command_category>_<client_name>`

### Technical Details
- Updated router prefix from `/api/import_lists` to `/import_lists` in main application
- Removed legacy redirect endpoints that were causing Lidarr compatibility issues
- Updated UI to display correct working URLs without redirects
- Updated documentation with new endpoint URLs

## [0.1.2] - 2025-09-17

### 🔧 Bug Fixes & Improvements
- **Connectivity Test**: Added "Test All Connectivity" button on config page to verify service connections (Lidarr, Last.fm, Plex, Jellyfin, ListenBrainz, MusicBrainz)
- **Scheduler & UI Fixes**: Fixed command scheduling reliability, clipboard copy functionality, and character encoding issues

### Technical Details
- Fixed scheduler `last_run` timestamp management and stable "Next run" calculations
- Resolved clipboard copy issues in Docker/HTTP environments with robust fallback mechanism
- Improved UTF-8 character handling in log file processing for international artist names
- Reduced default command timeouts from 120 to 30 minutes for discovery and playlist sync commands
- Improved newly enabled commands to execute after 5 minutes instead of waiting for full schedule cycle

## [0.1.1] - 2025-09-15

### 🔧 Stability & Performance Improvements
- **Enhanced cache management**: Added client-specific cache refresh/rebuild options with improved UI dropdown controls
- **Improved track matching**: Fixed Jellyfin search parameters and URL encoding for 100% playlist sync success rate
- **Performance optimizations**: Resolved async/sync execution conflicts and implemented centralized cache utility for 5x faster sync operations

## [0.1.0] - 2025-09-10

### 🎉 Major Features
- **Multi-Platform Support**: Full Plex and Jellyfin playlist synchronization
- **Library Cache Optimization**: 6x performance improvement for playlist operations
- **Smart Playlist Management**: Automatic cleanup, retention policies, and duplicate prevention
- **Execution Tracking**: Clear visibility into manual vs scheduled command triggers
- **Rate Limit Management**: Intelligent retry logic with exponential backoff
- **Helper Commands**: Separate cache building from playlist operations

### 🚀 Performance Improvements
- **Last.fm Rate Limit**: Increased from 5.0 to 8.0 requests/second (40% faster)
- **MusicBrainz Retry Logic**: Automatic retry with exponential backoff for 503 errors
- **Library Cache**: 3+ minutes → 30 seconds playlist sync time
- **Memory Optimization**: Configurable limits with graceful fallback

### 🔧 UI/UX Enhancements
- **Manual Cache Refresh**: UI buttons for on-demand cache rebuilding
- **Configuration Validation**: Dropdown support with current value display
- **Execution History**: Track command triggers (manual/scheduler/api)
- **Cache Status Monitoring**: Real-time cache health and performance metrics
