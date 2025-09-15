#!/usr/bin/env python3
"""
Application status tracker for monitoring command execution and system health
"""

import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class CommandStatus:
    """Status information for a single command"""
    enabled: bool = False
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    total_runs: int = 0
    total_successes: int = 0
    total_failures: int = 0
    last_run_duration: Optional[float] = None  # seconds
    last_error: Optional[str] = None
    last_result: Optional[Dict[str, Any]] = None


class StatusTracker:
    """Global status tracker for the application"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.app_start_time = datetime.now()
            self.commands: Dict[str, CommandStatus] = {}
            self.system_info: Dict[str, Any] = {}
            self._initialized = True
    
    def register_command(self, command_name: str, enabled: bool = False, schedule_hours: int = 24):
        """Register a command for status tracking"""
        if command_name not in self.commands:
            self.commands[command_name] = CommandStatus(enabled=enabled)
            
        self.commands[command_name].enabled = enabled
        if enabled and self.commands[command_name].last_run:
            # Calculate next run based on last run + schedule
            self.commands[command_name].next_run = (
                self.commands[command_name].last_run + timedelta(hours=schedule_hours)
            )
    
    def command_started(self, command_name: str):
        """Mark a command as started"""
        if command_name not in self.commands:
            self.commands[command_name] = CommandStatus()
        
        self.commands[command_name].last_run = datetime.now()
        self.commands[command_name].total_runs += 1
    
    def command_completed(self, command_name: str, success: bool, duration: float, 
                         result: Dict[str, Any] = None, error: str = None, 
                         schedule_hours: int = 24):
        """Mark a command as completed"""
        if command_name not in self.commands:
            self.commands[command_name] = CommandStatus()
        
        cmd_status = self.commands[command_name]
        cmd_status.last_run_duration = duration
        cmd_status.last_result = result
        
        if success:
            cmd_status.last_success = datetime.now()
            cmd_status.total_successes += 1
            cmd_status.last_error = None
        else:
            cmd_status.last_failure = datetime.now()
            cmd_status.total_failures += 1
            cmd_status.last_error = error
        
        # Calculate next run
        if cmd_status.enabled:
            cmd_status.next_run = datetime.now() + timedelta(hours=schedule_hours)
    
    def update_system_info(self, info: Dict[str, Any]):
        """Update system-level information"""
        self.system_info.update(info)
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status information"""
        now = datetime.now()
        uptime = now - self.app_start_time
        
        # Convert command statuses to serializable format
        commands_status = {}
        for name, status in self.commands.items():
            cmd_dict = asdict(status)
            # Convert datetime objects to ISO strings
            for key, value in cmd_dict.items():
                if isinstance(value, datetime):
                    cmd_dict[key] = value.isoformat()
            commands_status[name] = cmd_dict
        
        return {
            "timestamp": now.isoformat(),
            "app_start_time": self.app_start_time.isoformat(),
            "uptime_seconds": uptime.total_seconds(),
            "uptime_human": self._format_duration(uptime.total_seconds()),
            "commands": commands_status,
            "system": self.system_info,
            "status": "healthy"
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get basic health check information"""
        now = datetime.now()
        
        # Check if any enabled commands have failed recently
        health_issues = []
        for name, status in self.commands.items():
            if status.enabled:
                if status.last_failure and status.last_success:
                    if status.last_failure > status.last_success:
                        health_issues.append(f"{name}: last run failed")
                elif status.last_failure and not status.last_success:
                    health_issues.append(f"{name}: never succeeded")
        
        is_healthy = len(health_issues) == 0
        
        return {
            "status": "healthy" if is_healthy else "degraded",
            "timestamp": now.isoformat(),
            "service": "cmdarr",
            "issues": health_issues if health_issues else None
        }
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        elif seconds < 86400:
            return f"{seconds/3600:.1f}h"
        else:
            return f"{seconds/86400:.1f}d"


# Global status tracker instance
status_tracker = StatusTracker()
