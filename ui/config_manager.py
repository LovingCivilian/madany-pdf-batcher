"""Application config.ini read/write management."""
from __future__ import annotations

import os
import configparser
from typing import Optional, TYPE_CHECKING

from core.constants import DEFAULT_APP_CONFIG

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def init_config(win: MainWindow) -> None:
    """Create or load config.ini, ensuring all default keys exist."""
    config = configparser.ConfigParser()

    if os.path.exists(win.config_path):
        try:
            config.read(win.config_path, encoding="utf-8")
        except Exception as e:
            print(f"Warning: Could not read config.ini, creating new one: {e}")
            config = configparser.ConfigParser()

    modified = False
    for section, options in DEFAULT_APP_CONFIG.items():
        if not config.has_section(section):
            config.add_section(section)
            modified = True
        for key, default_value in options.items():
            if not config.has_option(section, key):
                config.set(section, key, str(default_value))
                modified = True

    if modified or not os.path.exists(win.config_path):
        try:
            with open(win.config_path, "w", encoding="utf-8") as f:
                config.write(f)
        except Exception as e:
            print(f"Warning: Could not save config.ini: {e}")

    win._config = config


def get_default_preset_name(win: MainWindow) -> Optional[str]:
    """Read the default preset name from config.ini."""
    if hasattr(win, "_config") and win._config:
        return win._config.get("General", "default_preset", fallback=None) or None

    config = configparser.ConfigParser()
    if os.path.exists(win.config_path):
        try:
            config.read(win.config_path, encoding="utf-8")
            value = config.get("General", "default_preset", fallback=None)
            return value if value else None
        except Exception as e:
            print(f"Error reading config: {e}")
    return None


def set_default_preset_name(win: MainWindow, name: Optional[str]) -> None:
    """Write the default preset name to config.ini."""
    config = configparser.ConfigParser()
    if os.path.exists(win.config_path):
        try:
            config.read(win.config_path, encoding="utf-8")
        except Exception:
            pass

    if not config.has_section("General"):
        config.add_section("General")

    if name:
        config.set("General", "default_preset", name)
    else:
        config.set("General", "default_preset", "")

    try:
        with open(win.config_path, "w", encoding="utf-8") as f:
            config.write(f)
        win._config = config
    except Exception as e:
        from ui.log_panel import show_error
        show_error(win, "Configuration Error", f"Could not save config file:\n{e}")
