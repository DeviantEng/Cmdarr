# Database Split Plan

## Current Issue
- Single database (`data/cmdarr.db`) contains both configuration and cache data
- Users can't easily "reset cache" without losing all configuration
- Database recreation requires reconfiguring everything

## Proposed Solution: Split Database Architecture

### Database 1: Configuration Database (`data/cmdarr_config.db`)
**Purpose**: Store application configuration and settings
**Tables**:
- `config_settings` - Application configuration
- `command_configs` - Command configurations and scheduling
- `command_executions` - Command execution history
- `api_cache` - API response cache (optional, could move to cache DB)

**Benefits**:
- Configuration persists across cache resets
- Easy to backup/restore just configuration
- Users can reset cache without losing settings

### Database 2: Cache Database (`data/cmdarr_cache.db`)
**Purpose**: Store runtime cache and temporary data
**Tables**:
- `library_cache` - Music library caches (Plex, Jellyfin)
- `api_cache` - API response cache (if moved from config DB)
- Any future cache tables

**Benefits**:
- Easy to delete/reset without affecting configuration
- Can be safely deleted for "fresh start"
- Separate optimization for cache vs config access patterns

## Implementation Plan

### Phase 1: Database Manager Updates
1. Update `DatabaseManager` to support multiple databases
2. Add methods for config vs cache database access
3. Update all models to specify which database they belong to

### Phase 2: Model Migration
1. Create separate database managers for config and cache
2. Update all queries to use appropriate database
3. Add migration logic to split existing database

### Phase 3: Client Updates
1. Update all clients to use cache database for library caches
2. Update config service to use config database
3. Update command executor to use config database

### Phase 4: User Experience
1. Add "Reset Cache" button that only deletes cache database
2. Add "Reset All" button that deletes both databases
3. Update documentation and error messages

## Migration Strategy
1. Create new database structure
2. Copy config tables to config database
3. Copy cache tables to cache database
4. Update all code to use new structure
5. Remove old single database support

## Benefits
- ✅ Easy cache reset without losing configuration
- ✅ Better separation of concerns
- ✅ Easier backup/restore strategies
- ✅ Better performance (smaller, focused databases)
- ✅ Future-proof for additional cache types

## Considerations
- More complex database management
- Need to handle cross-database transactions carefully
- Migration path for existing users
- Documentation updates needed
