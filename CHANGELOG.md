# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.13-dev] - TBA

### Fixes
- **Playlist generators (freshness)**: Local Discovery uses per-run randomness (no calendar-day RNG seed). Daylist seeding favors plays in the current time period when enough history exists (fallback to full lookback). Sonically similar candidates skip tracks in the recent-play exclude window and honor `lastViewedAt` / `viewedAt` when Plex includes them.
- **Daylist**: Default **historical ratio** is **0.3** (was 0.4), closer to Meloday’s blend toward sonic neighbors. Fill-loop sonic expansion uses a **wider, bounded** reference pool (scales with `max_tracks`, capped to limit Plex API fan-out) instead of a flat 50-track sample. **At most two tracks per artist** per playlist; the fill step **reuses** the same artist/genre dedupe state so that cap applies to the whole list (fixes extra same-artist picks after fill).
- **Local Discovery**: Default **historical ratio** **0.3** for consistency with Daylist.
- **Playlist naming**: Fixed issue where music target was showing in playlist name in Plex/Jellyfin
- **Playlist match tuning**: Minor tweaks to improve fuzzy match success; Centralized logic now better shared across Plex and Jellyfin
- **Workflow updates**: Bumped docker/login-action from v3 to v4, setup-node from v4 to v6; Unit test for track matching

### Security
- **NPM/Vite Vuln**: Update npm vite package to 7.3.2 to resolve recent CVE
- **Docker pinning**: Update Dockerfile SHA for python:3.14-slim-trixie image
- **Trivy**: `.trivyignore` entries for outstanding Debian slim-image CVEs, each with an **exp:** review date so CI surfaces them again for reassessment

## [0.3.12] - 2026-03-26

### Housekeeping
- **Security updates**: Bump python base digest; update npm flatted to address CVE-2026-33228; addressed codeql finding in new_release.py; Bump trivy scanner version (migrate to SHA instead of version tag due to recent supply chain attack)
- **CICD cleanup**: Dependabot tracking for trivy image; Additions to .dockerignore to decrease image size

### Features
- Command-spec: create dialog refactor for types that skip Common Settings; XMPlaylist uses its own form block.
- XMPlaylist: register target client for library cache; split playlist title vs command display name; multi-Plex create/edit like playlist sync; cleanup matches multi-user config.
- Security: pip-audit ignore for Pygments CVE-2026-4539 until PyPI has a fix; `docs/security-audit-followups.md` to revisit.
- API: `except (ValueError, IndexError)` in command creation routes (Python 3).
- Docs: `docs/testing_unit_spec.md` for unit test conventions.
- UI: `docs/create_command_plex_playlist_target_spec.md` and shared `PlexPlaylistTargetSection` for XMPlaylist and external playlist sync (no Plex user dropdown); shorter XMPlaylist station list with scroll.
- UI: Command edit dialog uses TypeScript spec (`command-spec` copy + `getCommandEditSectionOrder`) with `CommandEditFormBody` and per-type section components; shared artist-discovery copy and `ArtistDiscoveryFields`; XMPlaylist playlist mode and targets read-only on edit; top tracks target read-only on edit; enabled state shown as a header badge (removed large Enabled card).
- UI: Phase 2 command-spec — `CompoundFieldDef`, `getFieldsForContext` / `isCompoundFieldVisible`, shared `PlaylistSyncArtistDiscoveryControl` for create+edit; create wizard imports `PLAYLIST_TYPES_SKIP_COMMON_CREATE_SETTINGS` from spec; Plex target + artist discovery visibility driven by `resolveContextForCreate` / `resolveContextForEditCommand`.
- UI: Create XMPlaylist — artist discovery block no longer wrapped in an extra bordered card (matches edit + external playlist create).

## [0.3.11] - 2026-03-17

### Housekeeping
- **Security updates**: Debian 13.4 released on Mar-14, has fix for CVE-2026-0861, and addresses some other lower severity CVEs
- **Base image pinning**: Dockerfile updates to pin base image to digest; enablement of dependabot to monitor for digest changes and open PRs

## [0.3.10] - 2026-03-16

### 🎵 Daylist & Local Discovery
- **Multiple Instances per User**: Daylist and Local Discovery support multiple instances, each targeting a different Plex account; playlists are created in each user's context using shared user tokens
- **Server Owner in Account List**: Plex account selector now includes the server owner when absent from home users (token owner matching)
- **Display Name Sync**: Editing Daylist or Local Discovery and changing the Plex account updates the command display name (e.g. `[Cmdarr] [Andrea] Daylist`)
- **Expiry Cleanup**: Playlist deletion on command expiry uses the target user's token (admin token only sees admin playlists)

### 🎵 Playlist Sync (External)
- **Multi-User Plex Sync**: One command can sync to multiple Plex users; "Sync to multiple Plex users" checkbox reveals account selection (default: server owner only)
- **Efficient Track Resolution**: Tracks resolved once and reused for all users (e.g. 53/84 found → same 53 for each user, no re-search)
- **Playlist Title**: Same name in Plex for all users (no user suffix); Cmdarr display name shows users (e.g. `[Spotify] [Alice, Bob] Playlist → Plex`)
- **Plex Only**: Multi-user option hidden when target is Jellyfin
- **Expiry Cleanup**: Playlist deletion on expiry uses each user's token (admin token only sees admin playlists)

### 🎨 Create New Command & Inputs
- **Compact Type Selection**: Reordered (Daylist, Local Discovery, ListenBrainz, External, Top Tracks, Mood); smaller cards, single column
- **NumericInput Component**: Blur-only validation so values like "20" can be typed without intermediate clamping; used across create/edit for Daylist, Local Discovery, ListenBrainz, Top Tracks, Mood, Config

### 🔧 Fixes
- **Exception Syntax**: Python 3 `except (X, Y)` syntax across codebase (was invalid `except X, Y`)

### 🔒 Secure Development
- **CI pip-audit**: Install requirements before audit so project dependencies are scanned for vulnerabilities
- **Docker & Logging**: Compose example adds cap_drop and no_new_privileges (OWASP); SensitiveDataFilter redacts tokens/passwords from logs

## [0.3.9] - 2026-03-11

### 🎵 New Releases Discovery
- **Album Type Filter**: Trust API album_type/record_type only (Deezer, Spotify); no track-count heuristic; fixes albums not appearing when only "Album" selected
- **Unified Card & Dismissed Actions**: NRD metrics in New Releases card; Restore All and Reset scan history with confirmation dialogs
- **Edition Matching**: Strip parenthesized suffixes (Deluxe, Remaster, Extended, etc.) when matching MB; prefer base release over variants (e.g. "Album" over "Album (Extended)") for Harmony URL when both missing from MB

### 🔒 Secure Coding & Access Control
- **Single-User Auth**: First-run setup (username/password), session-based login, API key; env override for password reset
- **Error Exposure Fix**: Generic API messages instead of raw exceptions; URL length limits (2048); config validation (regex, min/max)
- **Security Headers**: X-Content-Type-Options, X-Frame-Options, Permissions-Policy, Content-Security-Policy on all responses
- **ZAP DAST**: Baseline scan in docker-publish; full scan (spider + active) in PR checks as merge gate; auth fix for public root/SPA routes

### 🎵 Daylist & Local Discovery
- **Server Owner Play History**: Fix play history for server owner; resolve Plex.tv ID to server account ID via token owner name matching (plex.tv/api/v2/user)

### 🧪 PR Gate & Unit Tests
- **PR Checks**: Unit tests, frontend typecheck, pytest-cov; tests for playlist_parser, text_normalizer, discovery utils, auth, security_headers
- **uv.lock**: Lock file for reproducible Python installs via uv

## [0.3.8] - 2026-03-09

### 🧪 Unit Tests & CI
- **Unit Tests**: pytest-based tests in `tests/`; start with `parse_playlist_url` (Spotify, Deezer, invalid URLs)
- **CI Gate**: `docker-publish` workflow runs unit tests before Docker build; build fails if tests fail
- **Dev Dependencies**: `requirements-dev.txt` adds pytest and pytest-asyncio

### 🎵 Spotify Scraper Fallback
- **Credential-Based Logic**: Use API when credentials configured; fall back to SpotifyScraper when not configured or API fails (e.g. 403 Premium required)
- **Public Playlists Only**: Scraper and API both support public playlists; no OAuth/private playlist support
- **Feb 2026 API Migration**: Playlist `/items` endpoint, search limit 10, field renames for Development Mode compatibility
- **Execution Failure Fix**: API errors (403, etc.) now correctly mark execution as failed with error message in UI
- **NRD**: Grey out Spotify source when credentials not configured; `new-releases-sources` endpoint for UI
- **NRD Save Validation**: When saving with Spotify source, test API connectivity; reject save if 403 Premium required (prompts use Deezer instead)
- **Test Connectivity**: Spotify "Not configured" shows as warning (orange) instead of error (red)

### 📚 Library Selector – Single Source of Truth
- **Shared Utility**: `utils/library_selector.py` – resolution logic for Plex and Jellyfin; used by all commands
- **Resolution Order**: `PLEX_LIBRARY_NAME` / `JELLYFIN_LIBRARY_NAME` if set; else prefer "Music"; else first by lowest key (type=artist)
- **Cached Keys**: `PLEX_LIBRARY_KEY` and `JELLYFIN_LIBRARY_KEY` (hidden, auto-managed) – resolved on startup and when library cache builder runs
- **Consistent Usage**: Library cache, play history, track/artist search, sonic analysis all use the resolved library
- **No Fallback to Stale**: Commands no longer use stored `target_library_key` from create; always resolve or use cached key

### 🔧 Refactor
- **Clients**: Plex and Jellyfin clients delegate to `resolve_plex_library()` / `resolve_jellyfin_library()`; removed duplicated `_resolve_music_library` and `_first_by_lowest_key`
- **Library Cache Builder**: Uses shared utility; re-resolves and updates cached key on each run
- **Daylist**: Simplified to `get_resolved_library()` instead of direct `_resolve_music_library` call

### 🎵 Artist Discovery Guardrail
- **Max per run**: Per-command limit (default 2) for how many new artists are added to the Playlist Sync Discovery import list per sync run; configurable in create/edit when "Add new artists" is enabled
- **First run**: No artists added on first run—only reports count in execution history; subsequent runs add per limit
- **Always report**: Discovery runs on every successful sync; execution history shows "X new artists detected" regardless of whether adding is enabled
- **UI rename**: Checkbox renamed from "Enable artist discovery" to "Add new artists" with clearer description—discovery always runs to report counts; checkbox controls whether to add to import list

## [0.3.7] - 2026-03-05

### 🎵 New Playlist Generators
- **Artist Essentials** (formerly Top Tracks): Auto-naming from artist list; optional custom name; fuzzy matching
- **Local Discovery**: Top artists from play history + sonically similar tracks; 90-day lookback; Plex only; single instance
- **Mood Playlist**: Selected Plex Sonic moods; multi-mood scoring; optional year filter; Plex only
- **Playlist Naming**: `[Cmdarr]` prefix for all Cmdarr-generated playlists; display name syncs with Plex/Jellyfin

### 🎨 Command UX & Expiration
- **Unified UI**: Schedule override, expiration, enable artist discovery—checkbox + description always visible; bordered sub-box when enabled
- **Command Expiration**: `expires_at` disables command (not delete); optional playlist removal; create/edit for playlist sync, Artist Essentials, daylist, Local Discovery, Mood Playlist
- **Daylist**: `use_primary_mood` option for cover descriptor
- **ListenBrainz Edit**: Retention (weekly/daily jams) and cleanup toggle now editable
- **Free Text Inputs**: Replaced restrictive number inputs across create/edit dialogs

### 🗑️ Soft-Delete & Fixes
- **Soft Delete**: Commands marked `deleted_at`; purged after 7 days; create over deleted restores record (fixes UNIQUE constraint)

## [0.3.6] - 2026-02-23

### 🐳 Base Images & Runtime
- **Docker**: Node 24 on Debian 13 (Trixie), Python 3.14 on Debian 13 (Trixie)
- **Trivy**: Ignorefile for CVE-2026-0861 (glibc; revisit when Debian ships fix); ignored CVEs shown in job summary
- **Local/CI**: `.nvmrc` (24), `.python-version` (3.14); pr-checks and Ruff use Node 24 and Python 3.14; Ruff target `py314`

### 🛠️ Dev Tooling & CI
- **Prettier**: Frontend formatting with `format` / `format:check` scripts; `eslint-config-prettier` to avoid conflicts
- **Makefile**: `make check` (lint/format without auto-fix), `make fix` (auto-fix)
- **PR Checks**: Workflow for PRs to main—ruff, frontend lint/format, npm-audit, pip-audit
- **Trivy**: Image vulnerability scan in docker-publish; fails on CRITICAL/HIGH; table output in job summary
- **ESLint**: Fixed 48 issues—types, unused vars, theme split into `theme-context`/`use-theme`, badge/button variants

### 🔧 Stability & Bug Fixes
- **Status Page**: Fixed failed execution count (SQLAlchemy `filter(not column)` bug—now uses `.is_(False)`)
- **Sensitive Config**: Treat `null` as "leave unchanged" for masked settings
- **Frontend API**: 30s fetch timeout with `AbortController`; clear timeout error messages
- **Daylist**: Manual/API triggers always execute; only scheduled runs skip when time period unchanged

### ⚡ Efficiency
- **Command Cleanup**: Runs daily at 2am; aggregate stats (`total_execution_count`, `total_success_count`, `total_failure_count`) on Status page
- **Cleanup Service**: `get_running_commands` returns plain dicts instead of detached ORM objects

### 🛡️ Reliability
- **ListenBrainz Playlist Sync**: Replaced `asyncio.run()` in async context with `await asyncio.to_thread()` to avoid event loop conflicts
- **Cancel Endpoint**: `POST /api/commands/{name}/cancel` to cancel running command execution
- **Plex/Jellyfin Clients**: `requests.Session` with retry (3 retries on 429/5xx)
- **HTTP Client**: 429 already retried; no change

### 🎨 UX
- **Validation Errors**: API `detail` array formatted into readable strings in frontend
- **Debug Log**: Removed `console.log` from `getCommands()`
- **Execution Polling**: 10s when running; paused when edit dialog open
- **Error Banners**: Config and Status pages show "Try Again" on load failure
- **Status Page**: Runtime mode (Docker/Standalone) and image tag display
- **Daylist Defaults**: `historical_ratio` 0.4, `sonic_similarity_distance` 0.8, `sonic_similar_limit` 10
- **Daylist Cover**: Smaller mood adjectives; "Cmdarr's Daylist" in dark bar at bottom for readability

## [0.3.5] - 2026-02-23

### 🎵 Daylist – Time-of-Day Playlist Generator
- **New Command**: Daylist builds playlists that evolve throughout the day using Plex Sonic Analysis and listening history (inspired by Meloday)
- **Configurable Periods**: Dawn, Early Morning, Morning, Afternoon, Evening, Night, Late Night with custom start/end hours
- **Account Resolution**: Automatically maps Plex.tv account IDs to server account IDs (owner uses id=1; shared users use Plex.tv ID)
- **Primary/Advanced UI**: Settings split into essential (account, schedule, exclude, lookback, max tracks) and collapsible advanced (sonic params, timezone, time periods)
- **Input Improvements**: Clamp on blur (not onChange) so typing values like 45 works; wider ranges (exclude 1–30, lookback 7–365, max tracks 10–200)
- **Sliders**: Historical ratio and Sonically similar distance use visible track sliders (works in light/dark mode)
- **Cover & Description**: Fixed asset path for cover generation; description set via PUT after playlist creation (Plex create API ignores summary)
- **Edit Dialog**: Scrollable body with fixed Save/Cancel footer when Advanced settings expanded

### 🔧 Fixes & Improvements
- **Import List Reset**: Reset button for Last.fm and Playlist Sync import lists
- **Scan by URL**: Artist/album URL support, MusicBrainz link matching, shared UI; JSX build error fix
- **Access Log Filter**: Use `record.args` for uvicorn path/status filtering
- **Cache Builder**: Use Plex `/recentlyAdded` endpoint; remove `addedAt` filter (rejected for music)
- **Security**: URL hostname parsing instead of substring for release link label (XSS mitigation)
- **Ruff**: Python linting and formatting via Ruff

## [0.3.4] - 2026-02-26

### 🆕 New Releases Discovery
- **Deezer as Release Source**: New Releases Discovery can use Deezer (default) or Spotify; configurable in Commands → Edit → Release source
- **Deezer Default**: No account configuration required—Deezer uses public API; ideal for users without Spotify Premium
- **Spotify Optional**: Set credentials in Config → Music Sources to use Spotify; validation prevents saving Spotify source without creds
- **Lidarr Links**: Uses Deezer artist links when available; falls back to search by name
- **Harmony Support**: Deezer album URLs work with Harmony for MusicBrainz import

### 🔧 Fixes & Improvements
- **Access Log Level**: High-frequency polling endpoints (/health, /api/status/*, /api/commands/*, /static/*) downgraded to DEBUG—visible when LOG_LEVEL=DEBUG, hidden at INFO
- **Error Messages**: API validation errors (e.g. missing Spotify creds) now shown in toast instead of generic "Failed to update"
- **Cache Builder (Plex)**: Use `/recentlyAdded` endpoint instead of `addedAt>=` filter—Plex QueryParser rejects that filter for music and returns the entire library; recentlyAdded returns items most-recent first with no filter params

## [0.3.3] - 2026-02-26

### 🔧 Fixes
- **Status Page**: Fast cache metadata query (no full JSON load); Plex/Jellyfin stats fetched in parallel—fixes ~5s hang when Jellyfin disabled
- **Library Selection**: Config `PLEX_LIBRARY_NAME` / `JELLYFIN_LIBRARY_NAME` to target a specific music library; auto-prefers "Music" over Audiobooks when multiple exist; used for cache, playlist sync, and track search

## [0.3.2] - 2026-02-23

### 🗑️ Alpine.js Frontend Removed
- **React Only**: All Jinja2/Alpine.js templates removed; app requires `frontend/dist` (run `npm run build` in frontend/)
- **Clear Error**: App fails fast with instructions if frontend not built

### 🕐 Cron-Only Scheduler
- **Cron-based**: Replaced `schedule_hours`; all commands use cron expressions with global default (`0 3 * * *`) and per-command override
- **Timezone**: `SCHEDULER_TIMEZONE` or `TZ` env for cron interpretation
- **Queue & Concurrency**: Commands queued by ID when due; `MAX_PARALLEL_COMMANDS` (default 1) configurable

### 🎨 UI & Config
- **Dark Theme**: Softer dark mode (dark blue instead of black)
- **Secrets Obfuscation**: API returns `***` for sensitive config; show-key button to reveal for verification
- **Library Cache Stats**: Status page shows Plex/Jellyfin cache object count, last built, hit rate; Refresh and Force Rebuild buttons
- **Playlist URL**: Read-only playlist URL in command edit dialog for external playlist syncs
- **Commands View**: Card/list view toggle persisted in localStorage

### 🎵 Plex & MusicBrainz
- **Plex API**: Replaced undocumented `/search` with mediaQuery on `/all`; smaller batches (250); cache builder uses `/recentlyAdded` (addedAt filter rejected for music)
- **MusicBrainz**: Rate limit 0.8 req/sec; hardcoded User-Agent; skip artist on 503 instead of adding to pending

### 🔧 Fixes & Improvements
- **Uptime Widget**: Fixed status page uptime (was always &lt;1m)
- **Command Queue**: Queued instead of failing when at capacity
- **Kill Execution**: Implemented `kill_execution`; cancels asyncio task
- **WebSocket Removed**: Streaming logs dropped; manual refresh after run

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
