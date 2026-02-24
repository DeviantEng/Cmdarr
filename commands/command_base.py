#!/usr/bin/env python3
"""
Base command class for modular application architecture
"""

from abc import ABC, abstractmethod
from .config_adapter import Config
from utils.logger import get_logger


class BaseCommand(ABC):
    """Abstract base class for all commands"""
    
    def __init__(self, config: Config = None):
        # Use provided config or create new one
        self.config = config if config else Config()
        self.logger = get_logger(self.get_logger_name())
    
    @abstractmethod
    async def execute(self) -> bool:
        """Execute the command. Return True if successful."""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Return command description for help text."""
        pass
    
    @abstractmethod
    def get_logger_name(self) -> str:
        """Return logger name for this command."""
        pass
    
    def get_config_summary(self) -> dict:
        """Get configuration summary (excluding sensitive data)"""
        return self.config.get_config_summary()
    
    def print_config(self):
        """Print configuration summary"""
        self.config.print_config()
    
    def is_helper_command(self) -> bool:
        """Return True if this is a helper command (not shown in UI commands list)"""
        return False