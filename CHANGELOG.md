# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.4] - 2025-01-18

### 🔧 Command Configuration Fixes
- **Fixed Command-Specific Settings**: Resolved issue where command-level configuration settings (like limit, min_match_score) were not taking effect
- **Improved Configuration Fallback**: Commands now properly use command-specific config with graceful fallback to global settings

## [0.1.3] - 2025-01-17

### 🔧 URL Structure Improvements
- **Clean Import List URLs**: Moved import list endpoints from `/api/import_lists/` to `/import_lists/` for better clarity and Lidarr compatibility
- **Fixed Lidarr Integration**: Resolved redirect issues that prevented Lidarr from properly consuming import list feeds
- **Simplified URL Structure**: Import lists now follow the clean pattern `/import_lists/<command_category>_<client_name>`

### Technical Details
- Updated router prefix from `/api/import_lists` to `/import_lists` in main application
- Removed legacy redirect endpoints that were causing Lidarr compatibility issues
- Updated UI to display correct working URLs without redirects
- Updated documentation with new endpoint URLs

## [0.1.2] - 2025-01-17

### 🔧 Bug Fixes & Improvements
- **Connectivity Test**: Added "Test All Connectivity" button on config page to verify service connections (Lidarr, Last.fm, Plex, Jellyfin, ListenBrainz, MusicBrainz)
- **Scheduler & UI Fixes**: Fixed command scheduling reliability, clipboard copy functionality, and character encoding issues

### Technical Details
- Fixed scheduler `last_run` timestamp management and stable "Next run" calculations
- Resolved clipboard copy issues in Docker/HTTP environments with robust fallback mechanism
- Improved UTF-8 character handling in log file processing for international artist names
- Reduced default command timeouts from 120 to 30 minutes for discovery and playlist sync commands
- Improved newly enabled commands to execute after 5 minutes instead of waiting for full schedule cycle

## [0.1.1] - 2025-01-15

### 🔧 Stability & Performance Improvements
- **Enhanced cache management**: Added client-specific cache refresh/rebuild options with improved UI dropdown controls
- **Improved track matching**: Fixed Jellyfin search parameters and URL encoding for 100% playlist sync success rate
- **Performance optimizations**: Resolved async/sync execution conflicts and implemented centralized cache utility for 5x faster sync operations

## [0.1.0] - 2025-01-10

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
