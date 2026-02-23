"""
Utility functions for the PDF Batch Text Inserter application.

This module provides common utilities used across the project, including
path resolution for PyInstaller compatibility.
"""

from __future__ import annotations
import sys
from pathlib import Path


def resolve_path(relative_path: str) -> Path:
    """
    Resolve a resource path both when running from source
    and when running as a PyInstaller executable.
    
    When running from source, paths are resolved relative to the project root.
    When running as a frozen executable, paths are resolved relative to the
    _MEIPASS directory (PyInstaller's temporary extraction folder).
    
    Args:
        relative_path: Path relative to project root (e.g., "fonts/Arial.ttf",
                      "presets", "config.json").
    
    Returns:
        Absolute Path object to the resource.
    
    Example:
        >>> fonts_dir = resolve_path("fonts")
        >>> preset_file = resolve_path("presets/default.json")
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Running from compiled EXE (PyInstaller)
        base_dir = Path(sys._MEIPASS)
    else:
        # Running from source (Python)
        # utils.py is inside core/, so go one level up to project root
        base_dir = Path(__file__).resolve().parent.parent
    
    return base_dir / relative_path


def get_base_dir() -> Path:
    """
    Get the base directory of the application.
    
    Returns the project root when running from source, or the _MEIPASS
    directory when running as a frozen executable.
    
    Returns:
        Absolute Path to the base directory.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    """
    Check if the application is running as a frozen executable.
    
    Returns:
        True if running from PyInstaller executable, False if running from source.
    """
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")
