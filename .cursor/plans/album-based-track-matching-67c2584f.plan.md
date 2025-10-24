<!-- 67c2584f-db9a-438c-9ffe-2f45cc4df9d7 7c51858f-f765-489d-aab8-e5904eed398d -->
# Improve Playlist Sync Track Matching with Album Support

## Problem

Currently, playlist sync only matches tracks based on **title + artist**, which causes incorrect matches when artists have multiple versions of the same track (original, remix, acoustic, live, etc.). Source playlists already include album data, and target libraries have album info cached, but it's not being used.

## Solution

Add album-based matching as a **scoring bonus** to improve match accuracy. Album matching will act as a tiebreaker when multiple tracks match on title+artist, helping select the correct version.

## Implementation Changes

### 1. Update Plex Client - Cached Search (`client_plex.py`)

**File**: `clients/client_plex.py`

Modify `_score_track_match_optimized` (lines ~318-345) to accept and score album matches:

- Add optional `target_album` parameter
- Add album scoring logic (exact match: +50, partial match: +30, fuzzy match: +20)
- Update `search_cached_library` to pass album info from source tracks

### 2. Update Plex Client - Live Search (`client_plex.py`)

Modify `_score_track_match` (lines ~849-889) to accept and score album matches:

- Add optional `target_album_name` parameter
- Add album scoring logic matching the cached search approach
- Update `_search_for_track_live` to accept and pass album parameter

### 3. Update Jellyfin Client - Cached Search (`client_jellyfin.py`)

**File**: `clients/client_jellyfin.py`

Update `search_cached_library` method to incorporate album matching in the scoring logic.

### 4. Update Jellyfin Client - Live Search (`client_jellyfin.py`)

Modify matching methods:

- `_find_best_match` (lines ~543-592)
- `_find_best_match_relaxed` (lines ~594-633)

Add album similarity scoring to the combined score calculation.

### 5. Update Playlist Sync Command (`commands/playlist_sync.py`)

**File**: `commands/playlist_sync.py`

Update `_sync_additive` method (lines ~490-505) to pass album info:

- Extract album from track dict: `track.get('album', '')`
- Pass album to `search_for_track` method

Update method signatures to support album parameter throughout the call chain.

### 6. Update Target Client Interface

Both Plex and Jellyfin `sync_playlist` methods already receive full track dictionaries with album info, so they can extract and use it internally.

## Key Design Decisions

1. **Album as bonus, not requirement**: Album match adds points but doesn't block matches. This handles cases where:

- Album names vary slightly between services
- Album metadata is missing
- Generic singles/compilations have different album names

2. **Scoring weights**:

- Title: 100 (exact), 70 (partial), 50 (fuzzy)
- Artist: 100 (exact), 70 (partial), 50 (fuzzy)
- **Album: 50 (exact), 30 (partial), 20 (fuzzy)** ← NEW
- Total possible: 250 points (was 200)

3. **Backward compatibility**: Album parameter is optional - existing code without album data continues to work.

## Benefits

- **Improved accuracy**: Correctly distinguishes between original, remix, acoustic, and live versions
- **Minimal changes**: Leverages existing data already present in both source and target systems
- **Safe defaults**: Won't break existing matches; only improves disambiguation
- **Performance neutral**: No additional API calls needed

### To-dos

- [ ] Update Plex _score_track_match_optimized to include album matching logic
- [ ] Update Plex _score_track_match to include album matching logic
- [ ] Update Plex search methods to pass album parameter through call chain
- [ ] Update Jellyfin matching methods (_find_best_match, _find_best_match_relaxed) to include album scoring
- [ ] Update Jellyfin search_cached_library and find_track_by_artist_and_title_sync to use album data
- [ ] Update playlist_sync.py to extract and pass album data to target client search methods
- [ ] Test with playlists containing multiple track versions to verify improved matching