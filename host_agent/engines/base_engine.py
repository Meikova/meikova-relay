"""Base abstract interface for OS-Specific Host Engines (Windows, macOS, Linux)."""

import os
import sys
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple


class BaseOSEngine(ABC):
    """Abstract base class defining the contract for WindowsEngine, MacOSEngine, and LinuxEngine."""

    engine_name: str = "BaseEngine"
    platform_key: str = sys.platform

    @abstractmethod
    def initialize_runtime(self) -> None:
        """Applies OS-specific process optimizations (e.g., 1ms timer resolution, DPI awareness, display server init)."""
        pass

    @abstractmethod
    def get_os_display_name(self) -> str:
        """Returns accurate human-readable OS name & architecture (e.g., 'Windows 11 Pro 64-bit')."""
        pass

    @abstractmethod
    def is_admin(self) -> bool:
        """Returns True if the current process runs with Administrator / root privileges."""
        pass

    @abstractmethod
    def get_turbojpeg_candidates(self) -> List[str]:
        """Returns ordered list of native libturbojpeg shared library paths for this OS."""
        pass

    @abstractmethod
    def detect_monitors(self, sct_instance: Any = None) -> List[Dict[str, Any]]:
        """Detects physical and virtual monitors on this OS."""
        pass

    @abstractmethod
    def grab_frame_raw(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
        monitor_id: int = 0,
        native_cap: Any = None,
        sct_instance: Any = None,
        dxcam_instance: Any = None,
    ) -> Tuple[Optional[Tuple[int, int]], Any, bool]:
        """Grabs raw BGRA/BGRX buffer from the OS display server.
        Returns ((width, height), raw_buffer, cursor_changed).
        """
        pass

    @abstractmethod
    def get_shell_command(self) -> List[str]:
        """Returns the interactive shell startup command for TerminalManager on this OS."""
        pass
