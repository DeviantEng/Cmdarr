#!/usr/bin/env python3
"""
FastAPI application for Cmdarr configuration and management
"""

from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import os
import time
from datetime import datetime
from __version__ import __version__

from database.database import get_db, get_database_manager
from services.config_service import config_service
from utils.logger import get_logger
from app.websocket import websocket_endpoint


# Initialize logger
logger = get_logger('cmdarr.app')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Cmdarr FastAPI application")
    
    # Initialize database
    try:
        db_manager = get_database_manager()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Run database migrations
    try:
        from database.migrate import run_migrations
        run_migrations()
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Failed to run database migrations: {e}")
        # Don't raise here as the app might still work with old schema
    
    # Initialize default commands
    try:
        from database.init_commands import init_default_commands
        init_default_commands()
        logger.info("Default commands initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize default commands: {e}")
        # Don't raise here as commands can be added later via API
    
    
    # Clean up stuck commands from previous runs
    try:
        from services.command_cleanup import command_cleanup
        await command_cleanup.cleanup_startup_stuck_commands()
        logger.info("Startup command cleanup completed")
    except Exception as e:
        logger.error(f"Failed to cleanup startup stuck commands: {e}")
        # Don't raise here as the app can still work
    
    # Start command cleanup service
    try:
        from services.command_cleanup import command_cleanup
        await command_cleanup.start_cleanup_task()
        logger.info("Command cleanup service started")
    except Exception as e:
        logger.error(f"Failed to start command cleanup service: {e}")
        # Don't raise here as the app can still work
    
    # Start command scheduler
    try:
        from services.scheduler import scheduler
        await scheduler.start()
        logger.info("Command scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start command scheduler: {e}")
        # Don't raise here as manual execution still works
    
    # Validate required configuration
    missing_config = config_service.validate_required_settings()
    if missing_config:
        logger.warning(f"Missing required configuration: {missing_config}")
    
    # Import and include commands router after logging is configured
    try:
        from app.api import commands
        app.include_router(commands.router, prefix="/api/commands", tags=["commands"])
        logger.info("Commands API router loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load commands API router: {e}")
        # Don't raise here as other APIs still work
    
    yield
    
    # Shutdown
    logger.info("Shutting down Cmdarr FastAPI application")
    
    # Stop command cleanup service
    try:
        from services.command_cleanup import command_cleanup
        await command_cleanup.stop_cleanup_task()
        logger.info("Command cleanup service stopped")
    except Exception as e:
        logger.error(f"Failed to stop command cleanup service: {e}")
    
    # Stop command scheduler
    try:
        from services.scheduler import scheduler
        await scheduler.stop()
        logger.info("Command scheduler stopped successfully")
    except Exception as e:
        logger.error(f"Failed to stop command scheduler: {e}")


# Create FastAPI application
app = FastAPI(
    title="Cmdarr",
    description="Modular music automation platform",
    version=__version__,
    lifespan=lifespan
)

# Mount static files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")


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
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "message": f"Health check failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
        )


# Status endpoint (detailed information)
@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """Status page with comprehensive system information"""
    return templates.TemplateResponse("status/index.html", {
        "request": request,
        "app_name": "Cmdarr"
    })

# API endpoint for raw status data
@app.get("/api/status/raw")
async def detailed_status_api(db: Session = Depends(get_db)):
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
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


# Main index page (now serves commands)
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main index page - now serves commands page"""
    return templates.TemplateResponse("commands/index.html", {
        "request": request,
        "app_name": "Cmdarr"
    })


# Configuration page
@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Configuration management page"""
    return templates.TemplateResponse("config/index.html", {
        "request": request,
        "app_name": "Cmdarr"
    })


# Commands page
@app.get("/commands", response_class=HTMLResponse)
async def commands_page(request: Request):
    """Command management page"""
    return templates.TemplateResponse("commands/index.html", {
        "request": request,
        "app_name": "Cmdarr"
    })


@app.get("/import-lists", response_class=HTMLResponse)
async def import_lists_page(request: Request):
    """Import lists page"""
    return templates.TemplateResponse("import_lists.html", {
        "request": request,
        "app_name": "Cmdarr"
    })


# API Routes - Import after logging is configured
from app.api import config, status, import_lists, test_connectivity

# Include API routers
app.include_router(config.router, prefix="/api/config", tags=["configuration"])
app.include_router(status.router, prefix="/api/status", tags=["status"])
app.include_router(import_lists.router, prefix="/import_lists", tags=["import_lists"])
app.include_router(test_connectivity.router, prefix="/api/config", tags=["configuration"])


# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_route(websocket: WebSocket, client_id: str = None):
    """WebSocket endpoint for real-time command updates"""
    await websocket_endpoint(websocket, client_id)




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
