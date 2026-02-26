#!/usr/bin/env python3
"""
Centralized logging setup with rotation and retention management
"""

import logging
import logging.handlers
import os
import glob
import re
from datetime import datetime, timedelta
from typing import Optional


class HealthCheckFilter(logging.Filter):
    """Filter to suppress routine requests from access logs"""
    
    def filter(self, record):
        # Suppress health check, status endpoint, static assets, and WebSocket connections
        if hasattr(record, 'getMessage'):
            message = record.getMessage()
            if any(endpoint in message for endpoint in ['/health', '/status', '/static/']):
                return False
        return True


class HTTPAccessFilter(logging.Filter):
    """Filter to adjust log levels for HTTP access logs based on status codes and endpoints"""
    
    def filter(self, record):
        if hasattr(record, 'getMessage'):
            message = record.getMessage()
            
            # Check if this is an HTTP access log with status code
            if '" ' in message and ' HTTP/' in message:
                parts = message.split('" ')
                if len(parts) >= 2:
                    try:
                        # Extract status code (should be first number after the quote)
                        status_part = parts[1].split()[0]
                        status_code = int(status_part)
                        
                        # For successful responses (2xx), check if it's a routine request
                        if 200 <= status_code < 300:
                            # Check if this is a routine request that should be DEBUG level
                            if any(routine in message for routine in ['/health', '/status', '/static/', 'GET / ']):
                                record.levelno = logging.DEBUG
                                record.levelname = 'DEBUG'
                            else:
                                # Other successful requests stay at INFO
                                record.levelno = logging.INFO
                                record.levelname = 'INFO'
                        elif 300 <= status_code < 400:
                            # Redirects - INFO level
                            record.levelno = logging.INFO
                            record.levelname = 'INFO'
                        elif 400 <= status_code < 500:
                            # Client errors - WARNING level
                            record.levelno = logging.WARNING
                            record.levelname = 'WARNING'
                        elif status_code >= 500:
                            # Server errors - ERROR level
                            record.levelno = logging.ERROR
                            record.levelname = 'ERROR'
                            
                    except (ValueError, IndexError):
                        # If we can't parse status code, leave as-is
                        pass
        
        return True


class UvicornHealthCheckFilter(logging.Filter):
    """Filter specifically for Uvicorn access logs to downgrade health checks to DEBUG"""
    
    def filter(self, record):
        if hasattr(record, 'getMessage'):
            message = record.getMessage()
            
            # Uvicorn access logs format: "IP:PORT - "METHOD /path HTTP/1.1" STATUS"
            # Example: '127.0.0.1:58232 - "GET /health HTTP/1.1" 200 OK'
            if 'GET /health HTTP/' in message and ' 200 ' in message:
                # Downgrade health check requests to DEBUG
                record.levelno = logging.DEBUG
                record.levelname = 'DEBUG'
            elif any(endpoint in message for endpoint in ['/status HTTP/', '/static/']):
                # Also downgrade other routine endpoints
                record.levelno = logging.DEBUG
                record.levelname = 'DEBUG'
        
        return True


class SafeTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    TimedRotatingFileHandler that recovers from rotation failures.
    When doRollover() fails (e.g. OSError at midnight), the handler can end up
    with a closed stream - file stops writing while console continues.
    This subclass catches emit errors and reopens the file.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._emit_failures = 0
        self._max_emit_failures = 3

    def emit(self, record):
        try:
            super().emit(record)
            self._emit_failures = 0
        except (OSError, IOError) as e:
            self._emit_failures += 1
            if self._emit_failures <= self._max_emit_failures:
                try:
                    if self.stream:
                        self.stream.close()
                        self.stream = None
                    self.stream = self._open()
                    super().emit(record)
                    self._emit_failures = 0
                except Exception:
                    if self._emit_failures == 1:
                        import sys
                        sys.stderr.write(f"Cmdarr log file handler error (will retry): {e}\n")
                    self.handleError(record)
            else:
                self.handleError(record)


class CmdarrLogger:
    """Centralized logger setup for Cmdarr with rotation and retention"""
    
    _configured = False
    
    @classmethod
    def setup_logging(cls, config) -> None:
        """Setup application-wide logging with rotation and retention"""
        # Allow reconfiguration for LOG_LEVEL changes
        if cls._configured and not hasattr(cls, '_reconfiguring'):
            return
        
        # Ensure log directory exists
        log_dir = os.path.dirname(config.LOG_FILE)
        os.makedirs(log_dir, exist_ok=True)
        
        # Clear any existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Setup formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Get the configured log level
        config_level = getattr(logging, config.LOG_LEVEL)
        
        # Setup file handler with daily rotation (SafeTimedRotatingFileHandler
        # recovers from rotation failures that can leave the handler broken)
        file_handler = SafeTimedRotatingFileHandler(
            filename=config.LOG_FILE,
            when='midnight',
            interval=1,
            backupCount=config.LOG_RETENTION_DAYS,
            encoding='utf-8'
        )
        # Custom naming for rotated files: cmdarr.log-20250903
        file_handler.suffix = '-%Y%m%d'
        file_handler.extMatch = re.compile(r"^\d{8}$")
        
        file_handler.setFormatter(detailed_formatter)
        file_handler.setLevel(config_level)  # File handler respects configured level
        
        # Setup console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(config_level)  # Console handler respects configured level
        
        # Configure root logger
        root_logger.setLevel(logging.DEBUG)  # Root accepts all levels, handlers filter
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Configure aiohttp access logger specifically
        aiohttp_access_logger = logging.getLogger('aiohttp.access')
        
        # Set aiohttp access logger to DEBUG level so it can be filtered down
        aiohttp_access_logger.setLevel(logging.DEBUG)
        
        # Add filters to aiohttp access logger
        health_filter = HealthCheckFilter()
        http_filter = HTTPAccessFilter()
        
        # Apply filters to existing handlers
        for handler in aiohttp_access_logger.handlers:
            handler.addFilter(health_filter)
            handler.addFilter(http_filter)
        
        # Also apply to root logger handlers for aiohttp messages
        for handler in root_logger.handlers:
            handler.addFilter(health_filter)
            handler.addFilter(http_filter)
        
        # Set aiohttp access logger to propagate so filters work
        aiohttp_access_logger.propagate = True
        
        # Configure urllib3 logging to reduce verbosity and hide sensitive info
        urllib3_logger = logging.getLogger('urllib3.connectionpool')
        urllib3_logger.setLevel(logging.WARNING)  # Only show warnings and errors, not INFO requests
        
        # Clean up old log files
        cls._cleanup_old_logs(config)
        
        cls._configured = True
        
        # Log startup message
        logger = logging.getLogger('cmdarr')
        logger.info(f"Logging configured - Level: {config.LOG_LEVEL}, Retention: {config.LOG_RETENTION_DAYS} days")
        logger.debug("Debug logging is enabled")
    
    @classmethod
    def _cleanup_old_logs(cls, config) -> None:
        """Clean up log files older than retention period"""
        try:
            log_dir = os.path.dirname(config.LOG_FILE)
            base_name = os.path.basename(config.LOG_FILE)
            
            # Find rotated log files (cmdarr.log.20250903 pattern)
            pattern = f"{base_name}.*"
            log_files = glob.glob(os.path.join(log_dir, pattern))
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=config.LOG_RETENTION_DAYS)
            
            files_removed = 0
            for log_file in log_files:
                try:
                    # Skip the current log file
                    if log_file.endswith(base_name):
                        continue
                    
                    # Get file modification time
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
                    
                    if file_mtime < cutoff_date:
                        os.remove(log_file)
                        files_removed += 1
                        
                except (OSError, ValueError):
                    # Skip files we can't process
                    continue
            
            if files_removed > 0:
                logger = logging.getLogger('cmdarr.logging')
                logger.debug(f"Cleaned up {files_removed} old log files")
                
        except Exception as e:
            # Don't let log cleanup break the application
            logger = logging.getLogger('cmdarr.logging')
            logger.warning(f"Error during log cleanup: {e}")
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get a logger with the specified name"""
        if not cls._configured:
            raise RuntimeError("Logging not configured. Call setup_logging() first.")
        
        return logging.getLogger(name)


def setup_application_logging(config) -> None:
    """Convenience function to setup logging for the entire application"""
    CmdarrLogger.setup_logging(config)


def get_logger(name: str) -> logging.Logger:
    """Convenience function to get a logger"""
    return CmdarrLogger.get_logger(name)
