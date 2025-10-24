#!/usr/bin/env python3
"""
SQLAlchemy models for Cmdarr configuration and data management

This file maintains backward compatibility by importing from separate model files.
For new code, import directly from config_models.py or cache_models.py.
"""

# Import all models from separate files for backward compatibility
from .config_models import (
    ConfigBase,
    ConfigSetting,
    CommandConfig, 
    CommandExecution,
    SystemStatus
)

from .cache_models import (
    CacheBase,
    CacheEntry,
    FailedLookup,
    LibraryCache
)

# Maintain backward compatibility with single Base
Base = ConfigBase