# Target Cache Efficiency Plan

## Problem Statement

Currently, cmdarr users experience a **performance trap** when using Plex or Jellyfin as playlist sync targets:

1. User enables Plex/Jellyfin client ✅
2. User creates playlist sync command targeting Plex/Jellyfin ✅  
3. Command runs and hammers target with thousands of API calls ❌
4. Target times out, command fails ❌
5. User is confused why it's not working ❌

### Root Cause Analysis

**Request Pattern Breakdown**:
- For each track in a playlist (e.g., 238 tracks), cmdarr tries multiple search strategies
- For each search query, it searches every music library in the target
- Each search = 1 HTTP request to `/library/sections/{library_key}/search`

**Math**: If you have 2 music libraries and 8 search queries per track:
- **238 tracks × 2 libraries × 8 queries = 3,808 requests per playlist sync!**

**Current Safeguards** (Not Enough):
- ✅ Rate limiting: 1.0 second between requests
- ✅ Timeout: 30 seconds per request
- ✅ Parallel limit: Max 3 commands running
- ✅ Library cache: Available but **disabled by default**

## Solution Overview

### Auto-Enable Library Cache When Client is Enabled

**For Plex**:
- `PLEX_CLIENT_ENABLED=true` → `LIBRARY_CACHE_PLEX_ENABLED=true`
- `LIBRARY_CACHE_PLEX_ENABLED=true` → `library_cache_builder` command `enabled=true`

**For Jellyfin**:
- `JELLYFIN_CLIENT_ENABLED=true` → `LIBRARY_CACHE_JELLYFIN_ENABLED=true`  
- `LIBRARY_CACHE_JELLYFIN_ENABLED=true` → `library_cache_builder` command `enabled=true`

### Immediate Cache Building

When library cache gets enabled:
- **Trigger immediate cache build** (don't wait for 24h schedule)
- **Run cache builder command** as soon as possible
- **Show progress** to user

### Smart Warnings

**Warning Scenarios**:
- Playlist sync command targets Plex but `LIBRARY_CACHE_PLEX_ENABLED=false`
- Playlist sync command targets Jellyfin but `LIBRARY_CACHE_JELLYFIN_ENABLED=false`
- Library cache enabled but cache builder command is disabled

**Warning Message**:
```
⚠️ Performance Warning: Playlist sync targeting Plex is enabled but library cache is disabled. 
This may cause slow performance and timeouts. Consider enabling library cache for better performance.
```

## Implementation Plan

### Phase 1: Auto-Enable Logic

**Files to Modify**:
- `services/config_service.py` - Add auto-enable logic
- `commands/config_adapter.py` - Update configuration handling
- `database/init_commands.py` - Update default command initialization

**Implementation**:
```python
# In config service or command creation
if plex_client_enabled and not library_cache_plex_enabled:
    # Auto-enable library cache
    # Trigger immediate cache build
    # Show notification to user
```

### Phase 2: Warning System

**Files to Modify**:
- `app/api/commands.py` - Add warnings in playlist sync creation
- `templates/commands/index.html` - Show warnings in UI
- `commands/playlist_sync.py` - Add cache status checks

**Implementation**:
```python
# In playlist sync command creation
if target == 'plex' and not library_cache_plex_enabled:
    # Show warning
    # Suggest enabling cache
    # Offer to auto-enable
```

### Phase 3: Immediate Cache Building

**Files to Modify**:
- `services/scheduler.py` - Add immediate execution capability
- `services/command_executor.py` - Handle immediate cache builds
- `commands/library_cache_builder.py` - Add progress reporting

**Implementation**:
```python
# When library cache gets enabled
if library_cache_just_enabled:
    # Queue cache builder command for immediate execution
    # Show progress to user
    # Disable playlist sync until cache is built
```

## Expected Impact

### Before Implementation
- 3,808 database queries per playlist sync
- 200-500ms per query = 19+ minutes of database load
- High chance of timeouts
- Poor user experience

### After Implementation
- ~50-100 database queries per playlist sync  
- Most searches hit local cache (instant)
- Target database load reduced by 95%+
- Reliable, fast playlist sync out of the box

## User Experience Flow

### Ideal Flow
1. User enables Plex → "Library cache will be enabled automatically"
2. Cache builder runs immediately → "Building Plex library cache..."
3. Cache build completes → "Library cache ready! Playlist sync will be fast."
4. User creates playlist sync → Works perfectly with cached data

### Warning Flow
1. User creates playlist sync targeting Plex
2. System detects cache is disabled
3. Shows warning: "Performance warning: Library cache is disabled"
4. Offers to auto-enable cache
5. User accepts → Cache builds immediately
6. Playlist sync proceeds with cached data

## Configuration Changes

### Default Values
**Current**:
- `LIBRARY_CACHE_PLEX_ENABLED` = `'false'`
- `LIBRARY_CACHE_JELLYFIN_ENABLED` = `'false'`
- `library_cache_builder` command `enabled` = `false`

**Proposed**:
- Auto-enable when respective client is enabled
- `library_cache_builder` command auto-enabled when any library cache is enabled

### New Configuration Options
- `AUTO_ENABLE_LIBRARY_CACHE` = `'true'` (master switch)
- `IMMEDIATE_CACHE_BUILD` = `'true'` (build cache immediately when enabled)
- `CACHE_BUILD_TIMEOUT_MINUTES` = `'180'` (timeout for cache builds)

## Testing Strategy

### Unit Tests
- Test auto-enable logic for Plex and Jellyfin
- Test warning system for disabled cache
- Test immediate cache building

### Integration Tests
- Test full flow: enable client → auto-enable cache → build cache → create playlist sync
- Test warning flow: create playlist sync with disabled cache → show warning → enable cache
- Test performance: compare playlist sync with and without cache

### Performance Tests
- Measure request count reduction (should be 95%+ reduction)
- Measure playlist sync time improvement
- Test with large playlists (500+ tracks)

## Rollout Plan

### Phase 1: Core Logic (v0.2.3)
- Implement auto-enable logic
- Add basic warnings
- Update default configurations

### Phase 2: UI Improvements (v0.2.4)
- Add cache status indicators
- Improve warning messages
- Add progress reporting

### Phase 3: Advanced Features (v0.2.5)
- Immediate cache building
- Advanced warning system
- Performance monitoring

## Success Metrics

### Performance Metrics
- Request count reduction: Target 95%+ reduction
- Playlist sync time: Target 90%+ improvement
- Timeout rate: Target <1% timeout rate

### User Experience Metrics
- Cache auto-enable rate: Target 100% when client enabled
- Warning acknowledgment rate: Target 90%+ users enable cache after warning
- User satisfaction: Target positive feedback on performance

## Risk Mitigation

### Potential Issues
- Cache build failures
- Large library cache sizes
- Memory usage during cache builds
- Cache staleness

### Mitigation Strategies
- Robust error handling for cache builds
- Configurable memory limits
- Cache validation and refresh mechanisms
- Fallback to live API if cache fails

## Conclusion

This plan addresses the core performance issue by ensuring library cache is automatically enabled when music clients are enabled, providing immediate cache building, and warning users about potential performance issues. The implementation will eliminate the current performance trap and provide a reliable, fast playlist sync experience out of the box.
