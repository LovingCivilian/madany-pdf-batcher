from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final

# Note: In a standalone run, these imports might fail if 'core' is missing.
# Preserving them as requested based on your project structure.
from core.utils import resolve_path
from core.constants import TIMESTAMP_FORMATS

# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_PRESETS_FOLDER: Final[str] = "presets"


# ============================================================
# SETTINGS DATACLASSES
# ============================================================

@dataclass
class TextInsertionSettings:
    """Configuration for the Text Insertion feature."""
    enabled: bool = False
    text: str = ""
    
    # Internal storage uses tuples: ("A4", "portrait") -> config dict
    # Each config dict now includes "page_selection" and "custom_pages" per paper size
    configs_by_size: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "text": self.text,
            "configs_by_size": configs_to_nested_structure(self.configs_by_size),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextInsertionSettings:
        raw_configs = data.get("configs_by_size", {})
        configs = nested_structure_to_configs(raw_configs)
        
        # Handle backward compatibility: migrate global page_selection to per-size configs
        legacy_page_selection = data.get("page_selection", "all")
        legacy_custom_pages = data.get("custom_pages", "")
        
        for key in configs:
            if "page_selection" not in configs[key]:
                configs[key]["page_selection"] = legacy_page_selection
            if "custom_pages" not in configs[key]:
                configs[key]["custom_pages"] = legacy_custom_pages

        return cls(
            enabled=data.get("enabled", False),
            text=data.get("text", ""),
            configs_by_size=configs,
        )


@dataclass
class StampInsertionSettings:
    """Configuration for the Stamp Insertion feature."""
    enabled: bool = False
    stamp_path: str = ""
    
    # Internal storage uses tuples: ("A4", "portrait") -> config dict
    # Each config dict now includes "page_selection" and "custom_pages" per paper size
    configs_by_size: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "stamp_path": self.stamp_path,
            "configs_by_size": configs_to_nested_structure(self.configs_by_size),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StampInsertionSettings:
        raw_configs = data.get("configs_by_size", {})
        configs = nested_structure_to_configs(raw_configs)
        
        # Handle backward compatibility: migrate global page_selection to per-size configs
        legacy_page_selection = data.get("page_selection", "all")
        legacy_custom_pages = data.get("custom_pages", "")
        
        for key in configs:
            if "page_selection" not in configs[key]:
                configs[key]["page_selection"] = legacy_page_selection
            if "custom_pages" not in configs[key]:
                configs[key]["custom_pages"] = legacy_custom_pages

        return cls(
            enabled=data.get("enabled", False),
            stamp_path=data.get("stamp_path", ""),
            configs_by_size=configs,
        )


@dataclass
class TimestampInsertionSettings:
    """Configuration for the Timestamp feature."""
    enabled: bool = False
    
    # Format string for strftime (e.g. "%Y-%m-%d")
    format_string: str = "%Y-%m-%d"
    prefix: str = ""

    # Internal storage uses tuples: ("A4", "portrait") -> config dict
    # Each config dict now includes "page_selection" and "custom_pages" per paper size
    configs_by_size: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "format_string": self.format_string,
            "prefix": self.prefix,
            "configs_by_size": configs_to_nested_structure(self.configs_by_size),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimestampInsertionSettings:
        raw_configs = data.get("configs_by_size", {})
        configs = nested_structure_to_configs(raw_configs)
        
        default_fmt = TIMESTAMP_FORMATS[0][1] if TIMESTAMP_FORMATS else "%Y-%m-%d"
        
        # Handle backward compatibility: migrate global page_selection to per-size configs
        legacy_page_selection = data.get("page_selection", "all")
        legacy_custom_pages = data.get("custom_pages", "")
        
        for key in configs:
            if "page_selection" not in configs[key]:
                configs[key]["page_selection"] = legacy_page_selection
            if "custom_pages" not in configs[key]:
                configs[key]["custom_pages"] = legacy_custom_pages

        return cls(
            enabled=data.get("enabled", False),
            format_string=data.get("format_string", default_fmt),
            prefix=data.get("prefix", ""),
            configs_by_size=configs,
        )


@dataclass
class PDFSecuritySettings:
    """Configuration for PDF Security options."""
    enabled: bool = False
    master_password: str = ""
    
    # Permissions
    allow_print: bool = False
    allow_modify: bool = False
    allow_copy: bool = False
    allow_annotate: bool = False
    allow_form_fill: bool = False
    allow_assemble: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "master_password": self.master_password,
            "allow_print": self.allow_print,
            "allow_modify": self.allow_modify,
            "allow_copy": self.allow_copy,
            "allow_annotate": self.allow_annotate,
            "allow_form_fill": self.allow_form_fill,
            "allow_assemble": self.allow_assemble,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PDFSecuritySettings:
        return cls(
            enabled=data.get("enabled", False),
            master_password=data.get("master_password", ""),
            allow_print=data.get("allow_print", False),
            allow_modify=data.get("allow_modify", False),
            allow_copy=data.get("allow_copy", False),
            allow_annotate=data.get("allow_annotate", False),
            allow_form_fill=data.get("allow_form_fill", False),
            allow_assemble=data.get("allow_assemble", False),
        )


@dataclass
class Preset:
    """
    Represents a complete application preset.
    """
    name: str
    created: float = 0.0
    modified: float | None = None
    description: str = ""

    text_insertion: TextInsertionSettings = field(default_factory=TextInsertionSettings)
    stamp_insertion: StampInsertionSettings = field(default_factory=StampInsertionSettings)
    timestamp_insertion: TimestampInsertionSettings = field(default_factory=TimestampInsertionSettings)
    pdf_security: PDFSecuritySettings = field(default_factory=PDFSecuritySettings)

    def __post_init__(self) -> None:
        if not self.created:
            self.created = datetime.now().timestamp()
        # NOTE: 'modified' is intentionally left as None on creation

    def update_modified(self) -> None:
        self.modified = datetime.now().timestamp()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "created": self.created,
            "modified": self.modified,
            "description": self.description,
            "text_insertion": self.text_insertion.to_dict(),
            "stamp_insertion": self.stamp_insertion.to_dict(),
            "timestamp_insertion": self.timestamp_insertion.to_dict(),
            "pdf_security": self.pdf_security.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Preset:
        # Handle backward compatibility: "watermark" -> "stamp_insertion"
        stamp_data = data.get("stamp_insertion", data.get("watermark", {}))
        
        # Helper to safely get float or 0.0/None
        created_val = data.get("created", 0.0)
        modified_val = data.get("modified", None)

        # Basic type safety if loading legacy files with strings
        if isinstance(created_val, str):
            created_val = 0.0 # Or parse ISO if migration needed
        if isinstance(modified_val, str):
            modified_val = None

        return cls(
            name=data.get("name", "Unnamed"),
            created=created_val,
            modified=modified_val,
            description=data.get("description", ""),
            text_insertion=TextInsertionSettings.from_dict(data.get("text_insertion", {})),
            stamp_insertion=StampInsertionSettings.from_dict(stamp_data),
            timestamp_insertion=TimestampInsertionSettings.from_dict(data.get("timestamp_insertion", {})),
            pdf_security=PDFSecuritySettings.from_dict(data.get("pdf_security", {})),
        )


# ============================================================
# PRESET MANAGER
# ============================================================

class PresetManager:
    """Manages the lifecycle of Preset files."""

    def __init__(self, presets_folder: str | None = None) -> None:
        if presets_folder:
            self.presets_folder = presets_folder
        else:
            self.presets_folder = str(resolve_path(DEFAULT_PRESETS_FOLDER))

        self._ensure_presets_folder()

    def _ensure_presets_folder(self) -> None:
        if not os.path.exists(self.presets_folder):
            os.makedirs(self.presets_folder)

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """
        Sanitizes the preset name for use as a filename.
        Illegal characters are replaced with their full-width unicode equivalents
        to preserve readability and prevent filename collisions.
        """
        # Create a mapping of illegal characters to full-width versions
        full_width_map = str.maketrans({
            '<': '＜', '>': '＞', ':': '：', '"': '＂',
            '/': '／', '\\': '＼', '|': '｜', '?': '？', '*': '＊'
        })
        
        # 1. Translate illegal characters and strip outer whitespace
        safe = name.translate(full_width_map).strip()
        
        # 2. Collapse multiple spaces/underscores into a single underscore
        safe = re.sub(r'[\s_]+', '_', safe)
        
        # 3. Truncate to 200 chars and remove leading/trailing underscores
        safe = safe[:200]
        safe = safe.strip('_')
        
        return safe or "unnamed"

    def get_preset_path(self, name: str) -> str:
        filename = self.sanitize_filename(name) + ".json"
        return os.path.join(self.presets_folder, filename)

    def preset_exists(self, name: str) -> bool:
        return os.path.exists(self.get_preset_path(name))

    def save_preset(self, preset: Preset, overwrite: bool = False) -> tuple[bool, str]:
        if not preset.name.strip():
            return False, "Preset name cannot be empty."

        filepath = self.get_preset_path(preset.name)
        file_exists = os.path.exists(filepath)

        if file_exists and not overwrite:
            return False, f"Preset '{preset.name}' already exists."

        try:
            # Only update the modified timestamp if we are updating an existing file.
            if file_exists:
                preset.update_modified()
            
            data = preset.to_dict()
            with open(filepath, 'w', encoding='utf-8') as file_handle:
                json.dump(data, file_handle, indent=2, ensure_ascii=False)
            return True, f"Preset '{preset.name}' saved successfully."
        except Exception as e:
            return False, f"Failed to save preset: {e}"

    def load_preset(self, name: str) -> tuple[Preset | None, str]:
        filepath = self.get_preset_path(name)
        if not os.path.exists(filepath):
            return None, f"Preset '{name}' not found."
        return self._load_from_file(filepath, name)

    def load_preset_from_path(self, filepath: str) -> tuple[Preset | None, str]:
        if not os.path.exists(filepath):
            return None, f"File not found: {filepath}"
        return self._load_from_file(filepath, os.path.basename(filepath))

    def _load_from_file(self, filepath: str, display_name: str) -> tuple[Preset | None, str]:
        try:
            with open(filepath, 'r', encoding='utf-8') as file_handle:
                data = json.load(file_handle)
            preset = Preset.from_dict(data)
            return preset, f"Preset '{display_name}' loaded successfully."
        except json.JSONDecodeError as e:
            return None, f"Invalid preset file format: {e}"
        except Exception as e:
            return None, f"Failed to load preset: {e}"

    def delete_preset(self, name: str) -> tuple[bool, str]:
        filepath = self.get_preset_path(name)
        if not os.path.exists(filepath):
            return False, f"Preset '{name}' not found."
        try:
            os.remove(filepath)
            return True, f"Preset '{name}' deleted."
        except Exception as e:
            return False, f"Failed to delete preset: {e}"

    def rename_preset(self, old_name: str, new_name: str) -> tuple[bool, str]:
        if not new_name.strip():
            return False, "New name cannot be empty."
        if old_name == new_name:
            return True, "Name unchanged."

        old_path = self.get_preset_path(old_name)
        new_path = self.get_preset_path(new_name)

        if not os.path.exists(old_path):
            return False, f"Preset '{old_name}' not found."
        if os.path.exists(new_path):
            return False, f"Preset '{new_name}' already exists."

        preset, load_msg = self.load_preset(old_name)
        if preset is None:
            return False, f"Failed to load preset '{old_name}': {load_msg}"

        preset.name = new_name
        save_success, save_msg = self.save_preset(preset)
        if not save_success:
            return False, save_msg

        try:
            os.remove(old_path)
            return True, f"Preset renamed to '{new_name}'."
        except OSError as e:
            return True, f"Preset renamed, but failed to remove old file: {e}"

    def list_presets(self) -> list[dict[str, Any]]:
        presets = []
        if not os.path.exists(self.presets_folder):
            return presets

        for filename in os.listdir(self.presets_folder):
            if not filename.lower().endswith('.json'):
                continue
            
            filepath = os.path.join(self.presets_folder, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                presets.append({
                    "name": data.get("name", filename[:-5]),
                    "created": data.get("created", 0.0),
                    "modified": data.get("modified", None),
                    "description": data.get("description", ""),
                    "filepath": filepath,
                    "is_valid": True,
                })
            except (json.JSONDecodeError, KeyError):
                presets.append({
                    "name": filename[:-5],
                    "created": 0.0,
                    "modified": None,
                    "description": "(Invalid preset file)",
                    "filepath": filepath,
                    "is_valid": False,
                })
        
        # Sort by modified (if exists), else created, else 0. 
        # We need to handle None for modified.
        presets.sort(key=lambda p: (p.get("modified") or p.get("created") or 0), reverse=True)
        return presets

    def export_preset(self, name: str, export_path: str) -> tuple[bool, str]:
        preset, msg = self.load_preset(name)
        if preset is None:
            return False, msg
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(preset.to_dict(), f, indent=2, ensure_ascii=False)
            return True, f"Preset exported to {export_path}"
        except Exception as e:
            return False, f"Failed to export: {e}"

    def import_preset(self, import_path: str, new_name: str | None = None) -> tuple[bool, str]:
        preset, msg = self.load_preset_from_path(import_path)
        if preset is None:
            return False, msg
        if new_name:
            preset.name = new_name
        if self.preset_exists(preset.name):
            return False, f"Preset '{preset.name}' already exists."
        return self.save_preset(preset)


# ============================================================
# HELPER FUNCTIONS: UI <-> JSON CONVERSION
# ============================================================

def configs_to_nested_structure(configs: dict[Any, dict]) -> dict[str, dict]:
    result = {}
    for key, config in configs.items():
        if isinstance(key, tuple) and len(key) == 2:
            family, mode = key
            if family not in result: 
                result[family] = {}
            result[family][mode] = config.copy()
    return result

def nested_structure_to_configs(
    data: dict[str, Any]
) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for key, val in data.items():
        if isinstance(val, dict) and "|" not in key:
            family = key
            for mode, config in val.items():
                if isinstance(config, dict):
                    result[(family, mode)] = config
        elif "|" in key and isinstance(val, dict):
            parts = key.split("|")
            if len(parts) == 2:
                result[(parts[0], parts[1])] = val
    return result


def page_selection_to_string(
    is_all: bool, is_first: bool, is_last: bool, 
    is_odd: bool, is_even: bool, is_custom: bool
) -> str:
    if is_first: return "first"
    if is_last: return "last"
    if is_odd: return "odd"
    if is_even: return "even"
    if is_custom: return "custom"
    return "all"


def page_selection_from_string(selection: str) -> dict[str, bool]:
    states = {
        "all": False, "first": False, "last": False,
        "odd": False, "even": False, "custom": False,
    }
    key = selection.lower() if selection else "all"
    states[key] = True if key in states else False
    if not any(states.values()):
        states["all"] = True
    return states