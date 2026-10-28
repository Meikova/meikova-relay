"""OS Engine Factory & Auto-Dispatcher for Meikova Relay Host Agent.

Automatically detects the host operating system (Windows, macOS, or Linux)
and initializes the dedicated native engine without runtime platform clutter.
"""

import sys
from typing import Optional
from .base_engine import BaseOSEngine
from .windows_engine import WindowsEngine
from .macos_engine import MacOSEngine
from .linux_engine import LinuxEngine

_ACTIVE_ENGINE: Optional[BaseOSEngine] = None


def create_platform_engine(platform_override: Optional[str] = None) -> BaseOSEngine:
    """Instantiates the dedicated OS Engine matching the current or specified platform."""
    plat = (platform_override or sys.platform).lower()
    if plat.startswith("win"):
        return WindowsEngine()
    elif plat == "darwin" or plat.startswith("mac"):
        return MacOSEngine()
    else:
        return LinuxEngine()


def get_active_os_engine() -> BaseOSEngine:
    """Returns the singleton active OS Engine for the running Host Agent process."""
    global _ACTIVE_ENGINE
    if _ACTIVE_ENGINE is None:
        _ACTIVE_ENGINE = create_platform_engine()
    return _ACTIVE_ENGINE


__all__ = [
    "BaseOSEngine",
    "WindowsEngine",
    "MacOSEngine",
    "LinuxEngine",
    "create_platform_engine",
    "get_active_os_engine",
]
