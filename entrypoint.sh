#!/bin/bash
set -e

# Default values
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Function to log messages
log() {
    echo "[entrypoint] $1"
}

# Function to check if configuration is ready
check_config_ready() {
    # Check if we have required environment variables
    if [ -n "$LIDARR_API_KEY" ] && [ -n "$LASTFM_API_KEY" ]; then
        log "Required environment variables detected, configuration ready"
        return 0
    fi
    
    # Check if database exists and has configuration
    if [ -f "/app/data/cmdarr.db" ]; then
        log "Database exists, checking configuration..."
        # Try to check if required settings are configured
        gosu appuser python -c "
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path('/app')
sys.path.insert(0, str(project_root))

# Set up minimal logging first
from utils.logger import CmdarrLogger

class MinimalConfig:
    def __init__(self):
        self.LOG_LEVEL = 'INFO'
        self.LOG_FILE = '/app/data/logs/cmdarr.log'
        self.LOG_RETENTION_DAYS = 7

# Setup logging
config = MinimalConfig()
CmdarrLogger.setup_logging(config)

# Now import and check config service
from services.config_service import config_service
try:
    missing = config_service.validate_required_settings()
    if not missing:
        print('Configuration is ready')
        exit(0)
    else:
        print(f'Missing required settings: {missing}')
        exit(1)
except Exception as e:
    print(f'Error checking configuration: {e}')
    exit(1)
" && return 0
    fi
    
    return 1
}

# Function to wait for configuration
wait_for_config() {
    local max_attempts=5
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        log "Checking configuration readiness (attempt $attempt/$max_attempts)..."
        
        # Check if configuration is ready
        if check_config_ready; then
            log "Configuration is ready, starting application..."
            return 0
        fi
        
        # Show helpful message
        if [ $attempt -eq 1 ]; then
            log "Configuration not ready. Please either:"
            log "  1. Set environment variables: LIDARR_API_KEY, LASTFM_API_KEY, etc."
            log "  2. Access the web interface at http://localhost:8080/config to configure"
            log ""
            log "Will check again in 60 seconds..."
        else
            log "Configuration still not ready, waiting 60 seconds... (attempt $attempt/$max_attempts)"
        fi
        
        # Wait before next attempt
        sleep 60
        attempt=$((attempt + 1))
    done
    
    # If we've exhausted attempts, provide final guidance
    log "Configuration not ready after $max_attempts attempts."
    log "Container will continue checking every 60 seconds."
    log "Set environment variables or access the web interface to configure."
    
    # Continue infinite wait with longer intervals
    while true; do
        sleep 60
        if check_config_ready; then
            log "Configuration is now ready, starting application..."
            return 0
        fi
        log "Still waiting for configuration... (checking every 60 seconds)"
    done
}

# Check if we need to modify user/group
if [ "$PUID" != "1000" ] || [ "$PGID" != "1000" ]; then
    log "Changing appuser UID to $PUID and GID to $PGID"
    
    # Change group ID if different
    if [ "$PGID" != "1000" ]; then
        groupmod -g "$PGID" appuser
    fi
    
    # Change user ID if different
    if [ "$PUID" != "1000" ]; then
        usermod -u "$PUID" appuser
    fi
    
    # Update ownership of app directory and data directory
    log "Updating file ownership..."
    chown -R appuser:appuser /app/data
    
    # Only chown app files if they're not owned by the right user already
    # This avoids slow chown on large codebases in development
    if [ "$(stat -c %u /app)" != "$PUID" ]; then
        chown appuser:appuser /app
    fi
else
    log "Using default UID:GID (1000:1000)"
fi

# Wait for configuration to be ready before starting the application
wait_for_config

# Execute the command as the appuser
log "Starting application as appuser (UID:$PUID GID:$PGID)"
exec gosu appuser "$@"
