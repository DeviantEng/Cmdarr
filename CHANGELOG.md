# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
