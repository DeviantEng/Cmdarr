#!/usr/bin/env python3
"""
Configuration API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from database.database import get_db
from database.models import ConfigSetting
from services.config_service import config_service
from utils.logger import get_logger

router = APIRouter()
logger = get_logger('cmdarr.api.config')


class ConfigUpdateRequest(BaseModel):
    """Request model for updating configuration"""
    value: Any
    data_type: str = None
    options: Optional[List[str]] = None


class ConfigSettingResponse(BaseModel):
    """Response model for configuration setting"""
    key: str
    value: Any
    default_value: str
    data_type: str
    category: str
    description: str
    is_sensitive: bool
    is_required: bool
    effective_value: Any  # The actual value being used (env > db > default)
    options: Optional[List[str]] = None  # For dropdown data types


@router.get("/", response_model=Dict[str, Any])
async def get_all_config():
    """Get all configuration settings"""
    try:
        settings = config_service.get_all_settings()
        # Filter out hidden settings (cache enable settings)
        hidden_keys = ['LIBRARY_CACHE_PLEX_ENABLED', 'LIBRARY_CACHE_JELLYFIN_ENABLED']
        filtered_settings = {k: v for k, v in settings.items() if k not in hidden_keys}
        return {"settings": filtered_settings}
    except Exception as e:
        logger.error(f"Failed to get all configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration")


@router.get("/category/{category}", response_model=Dict[str, Any])
async def get_config_by_category(category: str):
    """Get configuration settings by category"""
    try:
        settings = config_service.get_all_by_category(category)
        # Filter out hidden settings (cache enable settings)
        hidden_keys = ['LIBRARY_CACHE_PLEX_ENABLED', 'LIBRARY_CACHE_JELLYFIN_ENABLED']
        filtered_settings = {k: v for k, v in settings.items() if k not in hidden_keys}
        return {"category": category, "settings": filtered_settings}
    except Exception as e:
        logger.error(f"Failed to get configuration for category {category}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration")


@router.get("/{key}")
async def get_config_setting(key: str):
    """Get a specific configuration setting"""
    try:
        value = config_service.get(key)
        if value is None:
            raise HTTPException(status_code=404, detail="Configuration setting not found")
        
        return {"key": key, "value": value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get configuration {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration")


@router.put("/{key}")
async def update_config_setting(key: str, request: ConfigUpdateRequest, db: Session = Depends(get_db)):
    """Update a configuration setting"""
    try:
        # Check if setting exists
        setting = db.query(ConfigSetting).filter(ConfigSetting.key == key).first()
        if not setting:
            raise HTTPException(status_code=404, detail="Configuration setting not found")
        
        # Update setting
        success = config_service.set(key, request.value, request.data_type)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update configuration")
        
        # Special handling for LOG_LEVEL changes
        if key == 'LOG_LEVEL':
            try:
                from utils.logger import CmdarrLogger
                # Mark as reconfiguring to allow setup_logging to run again
                CmdarrLogger._reconfiguring = True
                
                # Create a config object with the current values
                class ConfigWrapper:
                    def __init__(self, config_service):
                        self.LOG_LEVEL = config_service.get('LOG_LEVEL', 'INFO')
                        self.LOG_FILE = config_service.get('LOG_FILE', 'data/logs/cmdarr.log')
                        self.LOG_RETENTION_DAYS = config_service.get('LOG_RETENTION_DAYS', 7)
                
                config_wrapper = ConfigWrapper(config_service)
                CmdarrLogger.setup_logging(config_wrapper)
                
                # Clear the reconfiguring flag
                delattr(CmdarrLogger, '_reconfiguring')
                logger.info(f"Logging configuration reloaded with level: {request.value}")
            except Exception as e:
                logger.warning(f"Failed to reload logging configuration: {e}")
                # Clear the reconfiguring flag even if there was an error
                if hasattr(CmdarrLogger, '_reconfiguring'):
                    delattr(CmdarrLogger, '_reconfiguring')
        
        # Special handling for cache user disabled settings - manage the hidden enabled setting
        if key in ['LIBRARY_CACHE_PLEX_USER_DISABLED', 'LIBRARY_CACHE_JELLYFIN_USER_DISABLED']:
            target = 'PLEX' if 'PLEX' in key else 'JELLYFIN'
            enabled_key = f'LIBRARY_CACHE_{target}_ENABLED'
            
            # If user is disabling cache, set enabled to false
            if request.value in [True, 'true', '1']:
                config_service.set(enabled_key, False)
                logger.info(f"User disabled {target} library cache")
            # If user is enabling cache, set enabled to true
            elif request.value in [False, 'false', '0']:
                config_service.set(enabled_key, True)
                logger.info(f"User enabled {target} library cache")
        
        # Update options if provided
        if request.options is not None:
            import json
            setting.options = json.dumps(request.options)
            db.commit()
        
        # Get updated value
        updated_value = config_service.get(key)
        
        return {"key": key, "value": updated_value, "message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update configuration {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update configuration")


@router.get("/details/{key}", response_model=ConfigSettingResponse)
async def get_config_setting_details(key: str, db: Session = Depends(get_db)):
    """Get detailed information about a configuration setting"""
    try:
        setting = db.query(ConfigSetting).filter(ConfigSetting.key == key).first()
        if not setting:
            raise HTTPException(status_code=404, detail="Configuration setting not found")
        
        # Parse options JSON string if present
        options = None
        if setting.options:
            try:
                import json
                options = json.loads(setting.options)
            except (json.JSONDecodeError, TypeError):
                options = None
        
        return ConfigSettingResponse(
            key=setting.key,
            value=setting.value,
            default_value=setting.default_value,
            data_type=setting.data_type,
            category=setting.category,
            description=setting.description,
            is_sensitive=setting.is_sensitive,
            is_required=setting.is_required,
            effective_value=setting.get_effective_value(),
            options=options
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get configuration details for {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration details")


@router.get("/categories/", response_model=List[str])
async def get_config_categories(db: Session = Depends(get_db)):
    """Get all configuration categories"""
    try:
        categories = db.query(ConfigSetting.category).distinct().all()
        return [category[0] for category in categories]
    except Exception as e:
        logger.error(f"Failed to get configuration categories: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration categories")


@router.post("/validate/")
async def validate_configuration():
    """Validate all required configuration settings"""
    try:
        missing = config_service.validate_required_settings()
        return {
            "valid": len(missing) == 0,
            "missing_settings": missing,
            "message": "Configuration is valid" if len(missing) == 0 else f"Missing {len(missing)} required settings"
        }
    except Exception as e:
        logger.error(f"Failed to validate configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate configuration")


@router.post("/refresh/")
async def refresh_configuration():
    """Refresh configuration cache"""
    try:
        config_service.refresh_cache()
        return {"message": "Configuration cache refreshed successfully"}
    except Exception as e:
        logger.error(f"Failed to refresh configuration cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh configuration cache")
