#!/usr/bin/env python3
"""
FastAPI application for Cmdarr configuration and management
"""

from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import os
import time
from datetime import datetime
from __version__ import __version__

from database.database import get_config_db, get_database_manager
from services.config_service import config_service
from utils.logger import CmdarrLogger, setup_application_logging, get_logger
from app.websocket import websocket_endpoint

# Ensure logging is configured when app is loaded (e.g. via uvicorn app.main:app)
# run_fastapi.py also calls this; CmdarrLogger handles re-init safely
if not CmdarrLogger._configured:
    _minimal_config = type('Config', (), {
        'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO').upper(),
        'LOG_FILE': 'data/logs/cmdarr.log',
        'LOG_RETENTION_DAYS': 7,
    })()
    setup_application_logging(_minimal_config)


# Lazy-load logger to avoid initialization issues
def get_app_logger():
    return get_logger('cmdarr.app')


def auto_enable_library_cache():
    """Auto-enable library cache when clients are enabled"""
    try:
        db_manager = get_database_manager()
        session = db_manager.get_session_sync()
        
        try:
            # Check Plex
            plex_enabled = config_service.get('PLEX_CLIENT_ENABLED', False)
            plex_url = config_service.get('PLEX_URL', '')
            plex_token = config_service.get('PLEX_TOKEN', '')
            cache_plex_user_disabled = config_service.get('LIBRARY_CACHE_PLEX_USER_DISABLED', False)
            
            if plex_enabled and plex_url and plex_token:
                # Always enable cache when client is enabled
                config_service.set('LIBRARY_CACHE_PLEX_ENABLED', True)
                
                # Only disable if user explicitly disabled
                if cache_plex_user_disabled:
                    config_service.set('LIBRARY_CACHE_PLEX_ENABLED', False)
                    get_app_logger().info("Plex library cache disabled by user preference")
                else:
                    get_app_logger().info("Auto-enabled Plex library cache")
            else:
                # Disable cache if Plex client is disabled
                config_service.set('LIBRARY_CACHE_PLEX_ENABLED', False)
                get_app_logger().info("Plex library cache disabled (Plex client not enabled)")
                
            # Check Jellyfin
            jellyfin_enabled = config_service.get('JELLYFIN_CLIENT_ENABLED', False)
            jellyfin_url = config_service.get('JELLYFIN_URL', '')
            jellyfin_token = config_service.get('JELLYFIN_TOKEN', '')
            cache_jellyfin_user_disabled = config_service.get('LIBRARY_CACHE_JELLYFIN_USER_DISABLED', False)
            
            if jellyfin_enabled and jellyfin_url and jellyfin_token:
                # Always enable cache when client is enabled
                config_service.set('LIBRARY_CACHE_JELLYFIN_ENABLED', True)
                
                # Only disable if user explicitly disabled
                if cache_jellyfin_user_disabled:
                    config_service.set('LIBRARY_CACHE_JELLYFIN_ENABLED', False)
                    get_app_logger().info("Jellyfin library cache disabled by user preference")
                else:
                    get_app_logger().info("Auto-enabled Jellyfin library cache")
            else:
                # Disable cache if Jellyfin client is disabled
                config_service.set('LIBRARY_CACHE_JELLYFIN_ENABLED', False)
                get_app_logger().info("Jellyfin library cache disabled (Jellyfin client not enabled)")
            
            # Enable cache builder command if any cache is enabled
            any_cache_enabled = (
                config_service.get('LIBRARY_CACHE_PLEX_ENABLED', False) or
                config_service.get('LIBRARY_CACHE_JELLYFIN_ENABLED', False)
            )
            
            if any_cache_enabled:
                from database.config_models import CommandConfig
                cache_builder_cmd = session.query(CommandConfig).filter(
                    CommandConfig.command_name == 'library_cache_builder'
                ).first()
                
                if cache_builder_cmd and not cache_builder_cmd.enabled:
                    cache_builder_cmd.enabled = True
                    session.commit()
                    get_app_logger().info("Auto-enabled library_cache_builder command")
                    
                    # Trigger immediate cache build (non-blocking)
                    trigger_immediate_cache_build()
                    
        finally:
            session.close()
            
    except Exception as e:
        get_app_logger().error(f"Error in auto-enable library cache: {e}")
        # Non-fatal, continue startup


def trigger_immediate_cache_build():
    """Trigger immediate cache build when auto-enabled"""
    try:
        import asyncio
        from services.command_executor import command_executor
        
        # Queue cache builder for immediate execution
        asyncio.create_task(
            command_executor.execute_command(
                'library_cache_builder',
                triggered_by='auto_enable'
            )
        )
        get_app_logger().info("Queued library_cache_builder for immediate execution")
    except Exception as e:
        get_app_logger().error(f"Failed to trigger cache build: {e}")
        # Non-fatal, log and continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    get_app_logger().info("Starting Cmdarr FastAPI application")
    
    # Initialize database
    try:
        db_manager = get_database_manager()
        get_app_logger().info("Database initialized successfully")
    except Exception as e:
        get_app_logger().error(f"Failed to initialize database: {e}")
        raise
    
    # Run version-based database migrations
    try:
        from database.version_migrations import run_version_migrations
        run_version_migrations()
        get_app_logger().info("Version-based migrations completed successfully")
    except Exception as e:
        get_app_logger().error(f"Failed to run version-based migrations: {e}")
        # Don't raise here as the app might still work with old schema
    
    # Initialize default commands
    try:
        from database.init_commands import init_default_commands
        init_default_commands()
        get_app_logger().info("Default commands initialized successfully")
    except Exception as e:
        get_app_logger().error(f"Failed to initialize default commands: {e}")
        # Don't raise here as commands can be added later via API
    
    # Auto-enable library cache for configured clients
    try:
        auto_enable_library_cache()
        get_app_logger().info("Auto-enable library cache check completed")
    except Exception as e:
        get_app_logger().error(f"Failed to auto-enable library cache: {e}")
        # Don't raise here as the app can still work
    
    
    # Clean up stuck commands from previous runs and queue retries for interrupted commands
    try:
        from services.command_cleanup import command_cleanup
        import asyncio
        commands_to_retry = await command_cleanup.cleanup_startup_stuck_commands()
        get_app_logger().info("Startup command cleanup completed")
        if commands_to_retry:
            asyncio.create_task(command_cleanup.run_restart_retries(commands_to_retry))
            get_app_logger().info(f"Queued {len(commands_to_retry)} command(s) for restart retry")
    except Exception as e:
        get_app_logger().error(f"Failed to cleanup startup stuck commands: {e}")
        # Don't raise here as the app can still work

    # Start command cleanup service
    try:
        from services.command_cleanup import command_cleanup
        await command_cleanup.start_cleanup_task()
        get_app_logger().info("Command cleanup service started")
    except Exception as e:
        get_app_logger().error(f"Failed to start command cleanup service: {e}")
        # Don't raise here as the app can still work
    
    # Start command scheduler
    try:
        from services.scheduler import scheduler
        await scheduler.start()
        get_app_logger().info("Command scheduler started successfully")
    except Exception as e:
        get_app_logger().error(f"Failed to start command scheduler: {e}")
        # Don't raise here as manual execution still works
    
    # Validate required configuration
    missing_config = config_service.validate_required_settings()
    if missing_config:
        get_app_logger().warning(f"Missing required configuration: {missing_config}")
    
    # Import and include commands router after logging is configured
    try:
        from app.api import commands
        app.include_router(commands.router, prefix="/api/commands", tags=["commands"])
        get_app_logger().info("Commands API router loaded successfully")
    except Exception as e:
        get_app_logger().error(f"Failed to load commands API router: {e}")
        # Don't raise here as other APIs still work
    
    yield
    
    # Shutdown
    get_app_logger().info("Shutting down Cmdarr FastAPI application")

    # Stop command scheduler (prevents new commands from starting)
    try:
        from services.scheduler import scheduler
        await scheduler.stop()
        get_app_logger().info("Command scheduler stopped successfully")
    except Exception as e:
        get_app_logger().error(f"Failed to stop command scheduler: {e}")

    # Graceful shutdown: wait for running commands to complete (e.g. playlist syncs)
    try:
        from services.command_executor import command_executor
        timeout = float(config_service.get("SHUTDOWN_GRACEFUL_TIMEOUT_SECONDS", 300))
        await command_executor.wait_for_running_commands(timeout_seconds=timeout)
    except Exception as e:
        get_app_logger().error(f"Failed during graceful command shutdown: {e}")

    # Stop command cleanup service
    try:
        from services.command_cleanup import command_cleanup
        await command_cleanup.stop_cleanup_task()
        get_app_logger().info("Command cleanup service stopped")
    except Exception as e:
        get_app_logger().error(f"Failed to stop command cleanup service: {e}")


# Create FastAPI application
app = FastAPI(
    title="Cmdarr",
    description="Modular music automation platform",
    version=__version__,
    lifespan=lifespan
)

# Add CORS middleware for development
# In production with same origin, this won't be needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# React frontend (required - build with: cd frontend && npm run build)
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
frontend_assets = os.path.join(frontend_dist, "assets")
if not os.path.exists(frontend_dist) or not os.path.exists(frontend_assets):
    raise RuntimeError(
        "React frontend not built. Run: cd frontend && npm install && npm run build"
    )
app.mount("/assets", StaticFiles(directory=frontend_assets), name="frontend-assets")


# Health check endpoint (for Docker health checks)
@app.get("/health")
async def health_check():
    """Health check endpoint for Docker health checks"""
    try:
        # Check database connectivity
        db_manager = get_database_manager()
        session = db_manager.get_session_sync()
        try:
            # Simple query to test database
            from sqlalchemy import text
            session.execute(text("SELECT 1"))
        finally:
            session.close()
        
        # Check required configuration
        missing_config = config_service.validate_required_settings()
        
        if missing_config:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "message": "Missing required configuration",
                    "missing_config": missing_config,
                    "timestamp": datetime.utcnow().isoformat() + 'Z'
                }
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "message": "All systems operational",
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
        )
    except Exception as e:
        get_app_logger().error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "message": "Health check failed",
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
        )


# API endpoint for raw status data
@app.get("/api/status/raw")
async def detailed_status_api(db: Session = Depends(get_config_db)):
    """Detailed status API endpoint with comprehensive information"""
    try:
        # Get system information
        system_info = {
            "app_name": "Cmdarr",
            "version": __version__,
            "uptime_seconds": time.time() - getattr(app.state, 'start_time', time.time()),
            "database_status": "connected",
            "configuration_status": "valid" if not config_service.validate_required_settings() else "incomplete",
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }
        
        # Get configuration summary (non-sensitive)
        config_summary = {}
        all_settings = config_service.get_all_settings()
        for key, value in all_settings.items():
            # Skip sensitive settings
            if key.upper().endswith(('_KEY', '_TOKEN', '_SECRET')):
                config_summary[key] = "***" if value else None
            else:
                config_summary[key] = value
        
        return JSONResponse(content={
            "system": system_info,
            "configuration": config_summary,
            "endpoints": {
                "health": "/health",
                "status": "/status",
                "config": "/config",
                "commands": "/commands",
                "api": "/api"
            }
        })
    except Exception as e:
        get_app_logger().error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail="Status check failed")


# Serve React app for frontend routes
@app.get("/", response_class=HTMLResponse)
async def react_app(request: Request):
    """Serve React app"""
    return FileResponse(os.path.join(frontend_dist, "index.html"))


@app.get("/config", response_class=HTMLResponse)
async def react_config(request: Request):
    """Serve React app for config route"""
    return FileResponse(os.path.join(frontend_dist, "index.html"))


@app.get("/status", response_class=HTMLResponse)
async def react_status(request: Request):
    """Serve React app for status route"""
    return FileResponse(os.path.join(frontend_dist, "index.html"))


@app.get("/import-lists", response_class=HTMLResponse)
async def react_import_lists(request: Request):
    """Serve React app for import-lists route"""
    return FileResponse(os.path.join(frontend_dist, "index.html"))


@app.get("/new-releases", response_class=HTMLResponse)
async def react_new_releases(request: Request):
    """Serve React app for new-releases route"""
    return FileResponse(os.path.join(frontend_dist, "index.html"))


# API Routes - Import after logging is configured
from app.api import config, status, import_lists, test_connectivity, new_releases

# Include API routers
app.include_router(config.router, prefix="/api/config", tags=["configuration"])
app.include_router(status.router, prefix="/api/status", tags=["status"])
app.include_router(import_lists.router, prefix="/import_lists", tags=["import_lists"])
app.include_router(test_connectivity.router, prefix="/api/config", tags=["configuration"])
app.include_router(new_releases.router, prefix="/api", tags=["new_releases"])


# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_route(websocket: WebSocket, client_id: str = None):
    """WebSocket endpoint for real-time command updates"""
    await websocket_endpoint(websocket, client_id)




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
