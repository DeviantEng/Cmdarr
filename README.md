# Cmdarr

> *Running commands, hoping for exit code 0*

A modular music automation platform that bridges services for your self-hosted media setup. Cmdarr connects Lidarr to Last.fm, MusicBrainz, ListenBrainz, Plex, and Jellyfin to discover, organize, and enhance your music library with intelligent automation.

## What Cmdarr Does

- **Automatic Music Discovery** – Similar artists (Last.fm), playlist-based discovery, new releases from Deezer/Spotify missing in MusicBrainz, scan artist by URL
- **Playlist Management** – Sync playlists from Spotify and ListenBrainz to Plex and Jellyfin; add discovered artists to Lidarr
- **Daylist** – Time-of-day playlist generator using Plex Sonic Analysis and listening history (inspired by Meloday); configurable periods (dawn, morning, afternoon, evening, night, etc.)
- **Performance** – Library cache (6x faster syncs), rate limiting, cron scheduling, Docker-native deployment

For detailed command descriptions, configuration, architecture, and troubleshooting, see **[readme-extended.md](readme-extended.md)**.

## Quick Start

### Docker Compose (Recommended)

```yaml
version: '3.8'
services:
  cmdarr:
    image: ghcr.io/devianteng/cmdarr:latest
    container_name: cmdarr
    ports:
      - "8080:8080"
    volumes:
      - ./cmdarr-data:/app/data
    environment:
      - TZ=America/New_York
      - PUID=1000
      - PGID=1000
      - LIDARR_URL=http://lidarr:8686
      - LIDARR_API_KEY=your_lidarr_api_key
      - LASTFM_API_KEY=your_lastfm_api_key
      # Optional: Plex, Jellyfin, ListenBrainz, Spotify for full features
      - PLEX_URL=http://plex:32400
      - PLEX_TOKEN=your_plex_token
    restart: unless-stopped
    stop_grace_period: 320s
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Docker Run

```bash
docker run -d \
  --name cmdarr \
  -p 8080:8080 \
  -v ./cmdarr-data:/app/data \
  -e TZ=America/New_York \
  -e LIDARR_URL=http://lidarr:8686 \
  -e LIDARR_API_KEY=your_lidarr_api_key \
  -e LASTFM_API_KEY=your_lastfm_api_key \
  --restart unless-stopped \
  ghcr.io/devianteng/cmdarr:latest
```

### Local Python Environment

For development or running without Docker:

> **Important:** Build the React frontend before starting. The app will not start without it.
>
> **Requirements:** Python 3.14, Node 24 (see `.python-version` and `.nvmrc`)

```bash
git clone https://github.com/DeviantEng/cmdarr.git
cd cmdarr

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

python -m pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..

export LIDARR_URL=http://localhost:8686
export LIDARR_API_KEY=your_lidarr_api_key
export LASTFM_API_KEY=your_lastfm_api_key

python run_fastapi.py
```

Visit `http://localhost:8080`. For frontend dev with hot reload: `npm run dev` in `frontend/` and use `http://localhost:5173`.

## Web Interface

Access `http://localhost:8080` for:

- **Commands** – Dashboard, enable/disable, manual run, edit
- **Config** – Web-based configuration with validation
- **Status** – Health, cache status, system info
- **New Releases** – Deezer/Spotify releases missing from MusicBrainz; scan artist by URL
- **Daylist** – Time-of-day playlist generator (Plex)

## Lidarr Integration

Add Cmdarr as a Custom List in Lidarr (Settings → Import Lists):

- `http://cmdarr:8080/import_lists/discovery_lastfm` – similar artists
- `http://cmdarr:8080/import_lists/discovery_playlistsync` – playlist sync artists

## Contributing

Cmdarr is designed to be extended. The modular architecture makes it straightforward to add new commands for different music services and automation tasks.

## License

MIT License – See LICENSE file for details

---

*Because sometimes the best solutions are the ones that execute reliably, even if the code looks questionable.*
