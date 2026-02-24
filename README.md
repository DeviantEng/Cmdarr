# Cmdarr

> *Running commands, hoping for exit code 0*

A modular music automation platform that bridges services for your self-hosted media setup. Cmdarr connects Lidarr to various music services like Last.fm, MusicBrainz, ListenBrainz, Plex, and Jellyfin to discover, organize, and enhance your music library with intelligent automation.

## What Cmdarr Does For You

### 🎵 **Automatic Music Discovery**
- **Find Similar Artists**: Automatically discovers new artists similar to those in your Lidarr library using Last.fm
- **Playlist-Based Discovery**: Discovers artists from synced playlists and adds them directly to Lidarr
- **New Releases Discovery**: Find Spotify releases from your Lidarr artists that are missing from MusicBrainz—add them via Harmony with one click
- **Smart Filtering**: Automatically excludes artists you already have and those on your exclusion lists
- **Quality Control**: Uses MusicBrainz fuzzy matching to ensure high-quality artist data

### 🎶 **Intelligent Playlist Management**
- **Multi-Source Support**: Sync playlists from Spotify and ListenBrainz to Plex and Jellyfin
- **Modular Command System**: Create unlimited playlist sync commands with custom schedules
- **Direct Lidarr Integration**: Artists from playlists are automatically added to Lidarr for monitoring
- **Automatic Cleanup**: Removes old playlists based on your retention preferences
- **Duplicate Prevention**: Prevents creating duplicate playlists with the same tracks
- **Performance Optimized**: Library cache reduces sync time from 3+ minutes to ~30 seconds

### 🚀 **Performance & Reliability**
- **Library Cache System**: Dramatically improves playlist operations (6x faster)
- **Intelligent Rate Limiting**: Handles API limits gracefully with retry logic
- **Modern Web Interface**: Clean, responsive dashboard for monitoring and configuration
- **Scheduled Automation**: Set it and forget it with configurable schedules
- **Docker Native**: Designed for easy deployment and management

## Quick Start

### Docker Compose (Recommended)

```yaml
version: '3.8'
services:
  cmdarr:
    image: ghcr.io/devianteng/cmdarr:develop
    container_name: cmdarr
    ports:
      - "8080:8080"
    volumes:
      - ./cmdarr-data:/app/data
    environment:
      - TZ=America/New_York
      - PUID=1000  # Optional: User ID
      - PGID=1000  # Optional: Group ID
      # Required API Keys
      - LIDARR_URL=http://lidarr:8686
      - LIDARR_API_KEY=your_lidarr_api_key
      - LASTFM_API_KEY=your_lastfm_api_key
      - MUSICBRAINZ_CONTACT=your-email@example.com
      # Optional: Additional services
      - LISTENBRAINZ_TOKEN=your_listenbrainz_token
      - LISTENBRAINZ_USERNAME=your_username
      - PLEX_URL=http://plex:32400
      - PLEX_TOKEN=your_plex_token
      - JELLYFIN_URL=http://jellyfin:8096
      - JELLYFIN_TOKEN=your_jellyfin_token
      - SPOTIFY_CLIENT_ID=your_spotify_client_id
      - SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
      - JELLYFIN_USER_ID=your_jellyfin_user_id
      # Library cache optimization
      - LIBRARY_CACHE_TTL_DAYS=30
      - LIBRARY_CACHE_MEMORY_LIMIT_MB=512
      - LIBRARY_CACHE_PLEX_ENABLED=true
      - LIBRARY_CACHE_JELLYFIN_ENABLED=true
    restart: unless-stopped
    stop_grace_period: 320s  # Allow running commands (e.g. playlist syncs) to finish before force-kill
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Docker Run

```bash
# Run with environment variables
docker run -d \
  --name cmdarr \
  -p 8080:8080 \
  -v ./cmdarr-data:/app/data \
  -e TZ=America/New_York \
  -e PUID=1000 \
  -e PGID=1000 \
  -e LIDARR_URL=http://lidarr:8686 \
  -e LIDARR_API_KEY=your_lidarr_api_key \
  -e LASTFM_API_KEY=your_lastfm_api_key \
  -e MUSICBRAINZ_CONTACT=your-email@example.com \
  --restart unless-stopped \
  ghcr.io/devianteng/cmdarr:develop
```

## Web Interface

Access Cmdarr at `http://localhost:8080` for:

- **📊 Commands Dashboard**: Main interface with card/list view toggle, filtering, and sorting
- **⚙️ Configuration**: Web-based configuration interface with validation
- **🎛️ Command Management**: Enable/disable commands, view execution status, trigger manual runs
- **📈 System Status**: Detailed system information, health metrics, and cache status
- **🆕 New Releases**: Discover Spotify releases missing from MusicBrainz; open Lidarr, MusicBrainz, or Harmony with one click

### Key Features
- **Card/List View Toggle**: Switch between card view and sortable table view with localStorage persistence
- **Advanced Filtering**: Filter commands by status (enabled/disabled) and type (discovery/playlist sync)
- **Sortable Columns**: Sort by name, schedule, last run, or next run with visual indicators
- **Real-time Updates**: Live status updates and command execution monitoring
- **Manual Cache Refresh**: UI buttons for on-demand cache rebuilding
- **Execution Tracking**: See whether commands were triggered manually or by scheduler
- **Configuration Validation**: Dropdown support with current value display
- **Enhanced Actions**: Improved action dropdowns with Execute Now and Edit options

## Available Commands

### Discovery Commands

#### `discovery_lastfm`
**What it does**: Discovers similar artists by querying Last.fm for each artist in your Lidarr library  
**Benefits**:
- Uses MusicBrainz fuzzy matching as fallback for artists missing MBIDs
- Intelligent caching with 7-day TTL for optimal performance
- Real-time filtering against current Lidarr library state
- Comprehensive deduplication and quality-based output limiting
- Generates JSON import list for Lidarr integration

**Configuration**:
- `DISCOVERY_LASTFM_ENABLED=true`
- `DISCOVERY_LASTFM_SCHEDULE_HOURS=24`
- `DISCOVERY_LASTFM_LIMIT=5`

#### `playlist_sync_discovery_maintenance`
**What it does**: Maintains the unified discovery import list by removing stale entries  
**Benefits**:
- Automatically cleans up old discovery entries based on configurable age threshold
- Prevents import list bloat and improves Lidarr performance
- Runs automatically as a scheduled maintenance task

### New Releases Discovery

**What it does**: Scans your Lidarr artists for releases on Spotify that are missing from MusicBrainz  
**Access**: Web UI → New Releases (`/new-releases`)

**Benefits**:
- Uses Lidarr's Spotify links when available (avoids name collisions like Emmure vs emmurée)
- 1 MusicBrainz API call per artist (release groups), no per-album lookups
- Filters out live recordings, compilations, and guest appearances
- One-click links to Lidarr, MusicBrainz artist page, or Harmony to add the album

**Requirements**: Lidarr, Spotify credentials, MusicBrainz contact  
**Configuration**: `NEW_RELEASES_CACHE_DAYS` (default 14) in Configuration → Music Sources → Spotify

### Playlist Sync Commands

#### Dynamic Playlist Sync Commands
**What it does**: Create unlimited playlist sync commands through the web interface  
**Benefits**:
- **ListenBrainz Curated Playlists**: Sync Weekly Exploration, Weekly Jams, Daily Jams
- **External Playlist Support**: Sync playlists from Spotify, Deezer, and other sources
- **Multi-Target Support**: Sync to Plex, Jellyfin, or both simultaneously
- **Library Cache Optimization**: 3+ minutes → 30 seconds sync time
- **Smart Playlist Management**: Automatic cleanup, retention policies, and duplicate prevention
- **Direct Lidarr Integration**: Artists from playlists are automatically added to Lidarr for monitoring

**Configuration**: Create and manage playlist sync commands through the web interface under Commands → New...

## Library Cache Optimization

Cmdarr includes an advanced library caching system that dramatically improves playlist sync performance:

### **Performance Benefits**
- **3+ minutes → 30 seconds** playlist sync time
- **400+ API calls → 1 initial library fetch** per batch
- **No timeouts** from excessive API usage
- **~50MB memory usage** during operations (cleared after)

### **How It Works**
The library cache system fetches your complete music library once and stores it with optimized search indexes:

```
Traditional Approach:  50 tracks × 8 searches each = 400+ API calls = 3+ minutes + timeouts
With Library Cache:    1 library fetch + instant memory searches = ~30 seconds
```

### **Smart Features**
- **SQLite Persistence**: 30-day cache with automatic expiration
- **Memory Optimization**: Loads only during active playlist operations
- **Automatic Refresh**: Detects stale data and rebuilds cache when needed
- **Configurable Limits**: Memory usage limits with graceful fallback
- **Multi-Client Support**: Plex and Jellyfin support with extensible architecture
- **Manual Cache Refresh**: UI buttons for on-demand cache rebuilding
- **Cache Status Monitoring**: Real-time cache health and performance metrics

## Configuration

### Required API Keys

- **Lidarr API Key**: Found in Lidarr Settings → General → Security
- **Last.fm API Key**: Register at [Last.fm API](https://www.last.fm/api/account/create)
- **MusicBrainz Contact**: Your email address (required by MusicBrainz API)
- **ListenBrainz Token**: Get from [ListenBrainz Profile](https://listenbrainz.org/profile/) (for playlist features)
- **Plex Token**: Get from [Plex Support Guide](https://support.plex.tv/articles/204059436/) (for playlist sync)
- **Jellyfin Token**: Get from [Jellyfin API Documentation](https://jellyfin.org/docs/general/administration/access-tokens/) (for playlist sync)
- **Jellyfin User ID**: Found in Jellyfin Dashboard → Users → Select User → User ID
- **Spotify Client ID & Secret**: Get from [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) (for playlist sync)

### Lidarr Integration

Add Cmdarr as a Custom List in Lidarr:
1. Go to Settings → Import Lists
2. Add a new "Custom List" 
3. Set URL to: `http://cmdarr:8080/import_lists/discovery_lastfm` or `http://cmdarr:8080/import_lists/discovery_listenbrainz`
4. Configure sync interval as desired (recommend 24-48 hours)

### Performance Optimization

When Plex or Jellyfin client is enabled, library cache building is automatically enabled for optimal performance.

### Environment Variables

All configuration can be set via environment variables:

```bash
# Required API Configuration
LIDARR_URL=http://lidarr:8686
LIDARR_API_KEY=your_lidarr_api_key
LASTFM_API_KEY=your_lastfm_api_key
MUSICBRAINZ_CONTACT=your-email@example.com

# Optional Services
LISTENBRAINZ_TOKEN=your_listenbrainz_token
LISTENBRAINZ_USERNAME=your_username
PLEX_URL=http://plex:32400
PLEX_TOKEN=your_plex_token
JELLYFIN_URL=http://jellyfin:8096
JELLYFIN_TOKEN=your_jellyfin_token
JELLYFIN_USER_ID=your_jellyfin_user_id
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

# Library cache optimization
LIBRARY_CACHE_TTL_DAYS=30
LIBRARY_CACHE_MEMORY_LIMIT_MB=512
LIBRARY_CACHE_PLEX_ENABLED=true
LIBRARY_CACHE_JELLYFIN_ENABLED=true
LIBRARY_CACHE_SCHEDULE_HOURS=24

# Restart retry: auto-retry commands interrupted by restart (default: true)
RESTART_RETRY_ENABLED=true

# Graceful shutdown (wait for running commands before exit)
SHUTDOWN_GRACEFUL_TIMEOUT_SECONDS=300

# Rate limiting optimization
LASTFM_RATE_LIMIT=8.0
MUSICBRAINZ_RATE_LIMIT=1.0
MUSICBRAINZ_MAX_RETRIES=3
MUSICBRAINZ_RETRY_DELAY=2.0

# Web Server Configuration
WEB_HOST=0.0.0.0
WEB_PORT=8080

# Logging Configuration
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=7
```

## Troubleshooting

### Common Issues

**No artists discovered**: Check Lidarr connectivity and API key
```bash
docker logs cmdarr | grep -i "lidarr"
```

**Playlist sync timeouts**: Enable library cache optimization
```bash
# Check if library cache is enabled
curl http://localhost:8080/api/config/ | grep -i "library_cache"

# Monitor library cache performance
docker logs cmdarr | grep -i "cache"

# Manual cache refresh via UI or API
curl -X POST http://localhost:8080/api/commands/library_cache_builder/execute \
  -H "Content-Type: application/json" \
  -d '{"target": "plex", "force_refresh": true}'
```

**Configuration not loading**: Check environment variables and web interface
```bash
curl http://localhost:8080/api/config/
```

**"Command was running when application restarted"**: Commands (e.g. playlist syncs) were interrupted by a restart. Cmdarr handles this by:
- **Restart retry**: On next startup, interrupted commands are automatically re-queued and run as soon as possible (configurable via `RESTART_RETRY_ENABLED`)
- **Graceful shutdown** (optional): Add `stop_grace_period: 320s` to docker-compose so Docker waits for running commands to finish before SIGKILL

### Performance Monitoring
Monitor command execution and web server performance:
- **Health endpoint**: `http://localhost:8080/health`
- **Status dashboard**: `http://localhost:8080/status`
- **Container stats**: `docker stats cmdarr`
- **Library cache stats**: Check status dashboard for cache hit rates and memory usage
- **Execution tracking**: See whether commands were triggered manually or by scheduler
- **Rate limit monitoring**: Check logs for API rate limit handling and retry attempts


## Technical Architecture (For Developers)

### Architecture Overview

Cmdarr uses a modern FastAPI-based architecture with SQLAlchemy ORM:

```
cmdarr/
├── run_fastapi.py          # FastAPI application entry point
├── app/                    # FastAPI application
│   ├── main.py            # Main FastAPI app with routes
│   └── api/               # API endpoints
│       ├── config.py      # Configuration management API
│       ├── commands.py    # Command management API
│       ├── status.py      # Status and health API
│       └── import_lists.py # Import list serving API
├── database/              # Database layer
│   ├── models.py          # SQLAlchemy models
│   ├── database.py        # Database connection management
│   └── init_commands.py   # Default command initialization
├── services/              # Business logic services
│   ├── config_service.py  # Configuration management
│   └── command_executor.py # Command execution service
├── cache_manager.py       # SQLAlchemy-based API response caching
├── utils/                 # Shared utilities and common functionality
│   ├── logger.py          # Centralized logging with rotation
│   ├── library_cache_manager.py  # Library cache optimization system
│   ├── status_tracker.py  # Application status monitoring
│   ├── discovery.py       # Discovery utilities and filtering
│   └── http_client.py     # Common HTTP client utilities
├── commands/              # Modular command system
│   ├── command_base.py    # Abstract base class
│   ├── config_adapter.py  # Configuration adapter for commands
│   ├── discovery_lastfm.py
│   ├── discovery_listenbrainz.py
│   └── playlist_sync_listenbrainz_curated.py
├── clients/               # Service API clients with shared base class
│   ├── client_base.py     # Base class with common functionality
│   ├── client_lidarr.py
│   ├── client_lastfm.py
│   ├── client_listenbrainz.py
│   ├── client_musicbrainz.py
│   ├── client_plex.py     # Enhanced with library cache support
│   └── client_jellyfin.py # Jellyfin API client with playlist support
└── templates/             # Jinja2 templates for web interface
    ├── base.html          # Base template with Alpine.js and Tailwind
    ├── index.html         # Main dashboard
    ├── config/            # Configuration pages
    ├── commands/          # Command management pages
    └── status/            # Status pages
```

### Modern Architecture Features
- **FastAPI**: High-performance async web framework
- **SQLAlchemy ORM**: Database abstraction with SQLite backend
- **Alpine.js**: Lightweight JavaScript framework for interactivity
- **Tailwind CSS**: Utility-first CSS framework for styling
- **Jinja2**: Template engine for server-side rendering
- **Thread-Pool Execution**: Commands run in isolation without blocking the web server
- **Database-Driven Config**: All configuration stored in SQLite with environment variable override
- **RESTful APIs**: Clean API design for all functionality

### Library Cache Architecture
- **LibraryCacheManager**: Centralized cache orchestrator
- **Client Integration**: Music clients implement cache interface
- **Memory Management**: Smart loading with configurable limits
- **Multi-Service**: Plex and Jellyfin support with extensible architecture
- **Helper Commands**: Separate cache building from playlist operations
- **Manual Refresh**: UI controls for on-demand cache rebuilding

### Data Flow

#### Similar Artist Discovery
```
Lidarr Artists → Last.fm Similar Artists → MusicBrainz Fuzzy Match → SQLite Cache → Output Limiting → Lidarr Import JSON
```

#### ListenBrainz Discovery
```
ListenBrainz Weekly Playlist → Extract Artists → Filter Against Lidarr → MusicBrainz Lookup → Lidarr Import JSON
```

#### Playlist Sync (Optimized)
```
ListenBrainz Curated Playlists → Extract Tracks → Library Cache Lookup → Create/Update Playlists → Smart Naming → Retention Cleanup
```

#### Library Cache Building
```
Scheduled/Manual Trigger → Fetch Complete Library → Build Search Indexes → Store in SQLite → Memory Cache → Performance Optimization
```

Cmdarr maintains high success rates through multi-service fallback strategies, comprehensive caching (70-90% API reduction), intelligent retry logic with exponential backoff, and quality-based filtering for optimal library expansion. The library cache system provides additional 6x performance improvements for playlist operations.

### Docker Configuration

#### User Permissions
Use `PUID` and `PGID` environment variables to match your host user:
```bash
# Find your user/group IDs
id

# Set in docker-compose.yml or docker run
PUID=1001
PGID=1001
```

#### Available Tags
- `ghcr.io/devianteng/cmdarr:latest` - Stable releases
- `ghcr.io/devianteng/cmdarr:develop` - Bleeding edge development builds

### Logging

Cmdarr implements professional log management:

- **Daily rotation**: Logs rotate automatically at midnight
- **Configurable retention**: Keep N days of logs (default 7)
- **File structure**: `cmdarr.log` (current) + `cmdarr.log-YYYYMMDD` (rotated)
- **Component logging**: Each service has its own logger namespace
- **Automatic cleanup**: Old logs removed based on retention policy
- **Smart filtering**: Health check requests logged at DEBUG level

Configure logging via environment variables:
```bash
LOG_LEVEL=INFO
LOG_RETENTION_DAYS=7
```

### Volume Mounts

Mount `/app/data` to persist:
- **Database**: `cmdarr.db` (SQLite database with all data)
- **Import Lists**: `import_lists/discovery_lastfm.json`, `import_lists/discovery_listenbrainz.json`
- **Logs**: `logs/cmdarr.log` and rotated files

### Manual Commands

While designed for Docker automation, individual commands can be triggered through the web interface or API:

```bash
# Execute commands via API
curl -X POST http://localhost:8080/api/commands/discovery_lastfm/execute
curl -X POST http://localhost:8080/api/commands/discovery_listenbrainz/execute
curl -X POST http://localhost:8080/api/commands/playlist_sync_listenbrainz_curated/execute

# Check configuration and status
curl http://localhost:8080/api/config/
curl http://localhost:8080/api/status/

# View logs
docker logs cmdarr --tail 50
```

### Local Python Environment

For development or direct Python execution:

```bash
# Clone the repository
git clone https://github.com/DeviantEng/cmdarr.git
cd cmdarr

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set required environment variables
export LIDARR_URL=http://localhost:8686
export LIDARR_API_KEY=your_lidarr_api_key
export LASTFM_API_KEY=your_lastfm_api_key
export MUSICBRAINZ_CONTACT=your-email@example.com

# Run the FastAPI application
python run_fastapi.py
```

### API Endpoints
- **Import Lists**: 
  - `/import_lists/discovery_lastfm` - JSON endpoint for Lidarr similar artist imports
  - `/import_lists/discovery_listenbrainz` - JSON endpoint for ListenBrainz Weekly Discovery artists
  - `/import_lists/metrics` - Metrics for import list files
- **New Releases**: `/api/new-releases` - Scan for Spotify releases missing from MusicBrainz (query params: `artist_limit`, `album_types`)
- **Health Check**: `/health` - Service health status (200/503) for Docker health checks
- **Configuration API**: `/api/config/` - RESTful configuration management
- **Commands API**: `/api/commands/` - Command management and execution

### Debug Mode
Set log level to DEBUG via environment variable:
```bash
LOG_LEVEL=DEBUG
```

## Contributing

Cmdarr is designed to be extended. The modular architecture makes it straightforward to add new commands for different music services and automation tasks.

## License

MIT License - See LICENSE file for details

---

*Because sometimes the best solutions are the ones that execute reliably, even if the code looks questionable.*
