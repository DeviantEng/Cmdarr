#!/usr/bin/env python3
"""
Execution-aware logger that includes execution ID in all log messages
"""

import logging
from typing import Optional
from .logger import get_logger


class ExecutionContextLogger:
    """
    Logger wrapper that automatically includes execution ID in all log messages
    This allows filtering logs by execution ID for live streaming
    """
    
    def __init__(self, base_logger_name: str, execution_id: Optional[int] = None):
        self.base_logger = get_logger(base_logger_name)
        self.execution_id = execution_id
        self._execution_context = f"[EXEC:{execution_id}]" if execution_id else ""
    
    def set_execution_id(self, execution_id: int):
        """Set the execution ID for this logger instance"""
        self.execution_id = execution_id
        self._execution_context = f"[EXEC:{execution_id}]"
    
    def _format_message(self, message: str) -> str:
        """Format message with execution context"""
        if self._execution_context:
            return f"{self._execution_context} {message}"
        return message
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message with execution context"""
        self.base_logger.debug(self._format_message(message), *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message with execution context"""
        self.base_logger.info(self._format_message(message), *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message with execution context"""
        self.base_logger.warning(self._format_message(message), *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message with execution context"""
        self.base_logger.error(self._format_message(message), *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Log critical message with execution context"""
        self.base_logger.critical(self._format_message(message), *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs):
        """Log exception message with execution context"""
        self.base_logger.exception(self._format_message(message), *args, **kwargs)


def get_execution_logger(logger_name: str, execution_id: Optional[int] = None) -> ExecutionContextLogger:
    """
    Get an execution-aware logger instance
    
    Args:
        logger_name: Base logger name (e.g., 'playlist_sync_listenbrainz')
        execution_id: Execution ID to include in all log messages
    
    Returns:
        ExecutionContextLogger instance
    """
    return ExecutionContextLogger(logger_name, execution_id)
