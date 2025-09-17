#!/usr/bin/env python3
"""
Startup script for Cmdarr FastAPI application
"""

import os
import sys
import uvicorn
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up logging
from utils.logger import setup_application_logging, get_logger

# Create a minimal config for logging setup
class MinimalConfig:
    def __init__(self):
        # Get log level from environment or default to INFO
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.LOG_FILE = 'data/logs/cmdarr.log'
        self.LOG_RETENTION_DAYS = 7

# Setup logging with environment variable support
config = MinimalConfig()
setup_application_logging(config)
logger = get_logger('cmdarr.startup')

def main():
    """Main startup function"""
    global logger
    try:
        logger.info("Starting Cmdarr FastAPI application")
        
        # Ensure data directory exists
        os.makedirs('data', exist_ok=True)
        os.makedirs('data/logs', exist_ok=True)
        
        # Create database tables
        from database.database import get_database_manager
        db_manager = get_database_manager()
        # Tables are created automatically in DatabaseManager.__init__
        
        # Reinitialize logging with database configuration
        from services.config_service import ConfigService
        db_config = ConfigService()
        
        # Create a proper config object for logging
        class DatabaseConfig:
            def __init__(self, config_service):
                self.config_service = config_service
            
            @property
            def LOG_LEVEL(self):
                return self.config_service.get('LOG_LEVEL')
            
            @property
            def LOG_FILE(self):
                return self.config_service.get('LOG_FILE')
            
            @property
            def LOG_RETENTION_DAYS(self):
                return self.config_service.get('LOG_RETENTION_DAYS')
        
        # Reinitialize logging with database configuration
        db_logging_config = DatabaseConfig(db_config)
        
        # Force reconfiguration by setting the reconfiguring flag
        from utils.logger import CmdarrLogger
        CmdarrLogger._reconfiguring = True
        setup_application_logging(db_logging_config)
        CmdarrLogger._reconfiguring = False
        
        # Get updated logger
        logger = get_logger('cmdarr.startup')
        logger.info("Logging reinitialized with database configuration")
        
        # Start FastAPI application
        host = os.getenv("WEB_HOST", "0.0.0.0")
        port = int(os.getenv("WEB_PORT", "8080"))
        log_level = os.getenv("LOG_LEVEL", "info").lower()
        
        # Configure Uvicorn logging with custom access log filter
        import copy
        uvicorn_log_config = copy.deepcopy(uvicorn.config.LOGGING_CONFIG)
        
        # Add custom filter to downgrade health checks to DEBUG
        uvicorn_log_config["filters"] = uvicorn_log_config.get("filters", {})
        uvicorn_log_config["filters"]["health_check_filter"] = {
            "()": "utils.logger.UvicornHealthCheckFilter"
        }
        
        # Apply filter to uvicorn.access logger
        uvicorn_log_config["loggers"]["uvicorn.access"]["filters"] = ["health_check_filter"]
        
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=False,  # Disable auto-reload in production
            log_level=log_level,
            log_config=uvicorn_log_config
        )
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
