from __future__ import annotations

from core.utils import resolve_path


# Debounce delay in milliseconds for preview updates
DEBOUNCE_DELAY_MS = 150

# ============================================================
# PAPER DEFINITIONS
# ============================================================

PAPER_DEFINITIONS = {
    "A3": {
        "portrait": {
            "w": 842,
            "h": 1191,
            "label": "A3 × Portrait",
        },
        "landscape": {
            "w": 1191,
            "h": 842,
            "label": "A3 × Landscape",
        },
    },
    "A4": {
        "portrait": {
            "w": 595,
            "h": 842,
            "label": "A4 × Portrait",
        },
        "landscape": {
            "w": 842,
            "h": 595,
            "label": "A4 × Landscape",
        },
    },
    "A5": {
        "portrait": {
            "w": 420,
            "h": 595,
            "label": "A5 × Portrait",
        },
        "landscape": {
            "w": 595,
            "h": 420,
            "label": "A5 × Landscape",
        },
    },
    "US Letter": {
        "portrait": {
            "w": 612,
            "h": 792,
            "label": "US Letter × Portrait",
        },
        "landscape": {
            "w": 792,
            "h": 612,
            "label": "US Letter × Landscape",
        },
    },
    "US Legal": {
        "portrait": {
            "w": 612,
            "h": 1008,
            "label": "US Legal × Portrait",
        },
        "landscape": {
            "w": 1008,
            "h": 612,
            "label": "US Legal × Landscape",
        },
    },
    "Tabloid": {
        "portrait": {
            "w": 792,
            "h": 1224,
            "label": "Tabloid × Portrait",
        },
        "landscape": {
            "w": 1224,
            "h": 792,
            "label": "Tabloid × Landscape",
        },
    },
    # Generic catch-all for unknown sizes.
    # Dimensions match A4 for visualization purposes in the config dialog.
    "Unknown": {
        "portrait": {
            "w": 595,
            "h": 842,
            "label": "Generic × Portrait",
        },
        "landscape": {
            "w": 842,
            "h": 595,
            "label": "Generic × Landscape",
        },
    },
}

# Tolerance in points when comparing PDF page sizes
DIMENSION_TOLERANCE = 10

# ============================================================
# DERIVED PAPER STRUCTURES
# ============================================================

ALL_PAPER_KEYS: list[tuple[str, str]] = []
KEY_TO_LABEL: dict[tuple[str, str], str] = {}
LABEL_TO_KEY: dict[str, tuple[str, str]] = {}

for family, modes in PAPER_DEFINITIONS.items():
    for mode, info in modes.items():
        key = (family, mode)
        label = info["label"]
        ALL_PAPER_KEYS.append(key)
        KEY_TO_LABEL[key] = label
        LABEL_TO_KEY[label] = key

ALL_PAPER_LABELS = [KEY_TO_LABEL[k] for k in ALL_PAPER_KEYS]

# ============================================================
# POSITION PRESETS
# ============================================================

POSITION_PRESETS = [
    "Top Left", "Top Center", "Top Right",
    "Center Left", "Center", "Center Right",
    "Bottom Left", "Bottom Center", "Bottom Right",
]

# ============================================================
# DEFAULTS
# ============================================================

DEFAULT_TEXT_CONFIG = {
    "font_family": "Arial",
    "bold": False,
    "italic": False,
    "underline": False,
    "strike": False,
    "font_size": 12,
    "pad_x": 3,
    "pad_y": 3,
    "line_gap": 0,
    "text_color": "#000000",
    "text_opacity": 100,
    "bg_color": "#ffff00",
    "bg_opacity": 0,
    "h_margin": 10,
    "v_margin": 10,
    "position": "Top Left",
}

# Timestamp defaults: Explicit definition (not using .copy())
DEFAULT_TIMESTAMP_CONFIG = {
    "font_family": "Arial",
    "bold": False,
    "italic": False,
    "underline": False,
    "strike": False,
    "font_size": 10,
    "pad_x": 3,
    "pad_y": 3,
    "line_gap": 0,
    "text_color": "#000000",
    "text_opacity": 100,
    "bg_color": "#ffff00",
    "bg_opacity": 0,
    "h_margin": 10,
    "v_margin": 10,
    "position": "Bottom Right",
}

TIMESTAMP_FORMATS = [
    ("Full Date", "%A, %B %d, %Y"),                 # Tuesday, December 02, 2025
    ("Full Date Time", "%A, %B %d, %Y %I:%M %p"),   # Tuesday, December 02, 2025 9:36 AM
    ("Long Date Time", "%A, %B %d, %Y %I:%M:%S %p"),# Tuesday, December 02, 2025 9:36:16 AM
    ("Short Date Time", "%m/%d/%Y %I:%M %p"),       # 12/02/2025 9:36 AM
    ("Month Year", "%B %Y"),                        # December 2025
]

DEFAULT_STAMP_CONFIG = {
    "stamp_width_mm": 150.0,
    "stamp_height_mm": 150.0,
    "maintain_aspect": True,
    "stamp_rotation": 90,     # Requested rotation
    "stamp_opacity": 100,
    "h_margin": 10,
    "v_margin": 10,
    "position": "Center Right", # Requested position
}

# ============================================================
# FONT FAMILY DEFINITIONS
# ============================================================

def get_font_families() -> dict[str, dict[str, str]]:
    fonts_dir = resolve_path("fonts")

    return {
        "Arial": {
            "regular":    str(fonts_dir / "Arial-Regular.ttf"),
            "bold":       str(fonts_dir / "Arial-Bold.ttf"),
            "italic":     str(fonts_dir / "Arial-Italic.ttf"),
            "bolditalic": str(fonts_dir / "Arial-BoldItalic.ttf"),
        },
        "SpaceMono": {
            "regular":    str(fonts_dir / "SpaceMono-Regular.ttf"),
            "bold":       str(fonts_dir / "SpaceMono-Bold.ttf"),
            "italic":     str(fonts_dir / "SpaceMono-Italic.ttf"),
            "bolditalic": str(fonts_dir / "SpaceMono-BoldItalic.ttf"),
        },
        "Sakkal Majalla": {
            "regular":    str(fonts_dir / "SakkalMajalla-Regular.ttf"),
            "bold":       str(fonts_dir / "SakkalMajalla-Bold.ttf"),
        }
    }

# ============================================================
# DEFAULT APP CONFIGURATION
# ============================================================

# These defaults are used when creating a new config.ini file
# or when values are missing from an existing config.
DEFAULT_APP_CONFIG = {
    "General": {
        "default_preset": "",  # Name of preset to auto-load on startup
        # Placeholder for future settings
        # "theme": "system",
        # "language": "en",
        # "auto_save": "false",
    },
    # Placeholder sections for future expansion
    # "Paths": {
    #     "last_input_folder": "",
    #     "last_output_folder": "",
    # },
    # "UI": {
    #     "window_width": "1500",
    #     "window_height": "900",
    #     "splitter_position": "1000",
    # },
}

# ============================================================
# HELPERS
# ============================================================

def detect_paper_key(width: float, height: float, tol: float = DIMENSION_TOLERANCE) -> tuple[str, str] | None:
    """
    Detects standard paper keys. 
    Explicitly ignores the 'Unknown' family so it is never returned 
    as a detected standard size.
    """
    for family, modes in PAPER_DEFINITIONS.items():
        if family == "Unknown":
            continue
            
        for mode, info in modes.items():
            w = info["w"]
            h = info["h"]
            if abs(width - w) < tol and abs(height - h) < tol:
                return (family, mode)
    return None

# ============================================================
# SUBSTITUTION DEFINITIONS
# ============================================================

SUBSTITUTION_DEFINITIONS = [
    {
        "name": "PartNumber",
        "description": "7-digit Part Identifier",
        "regex": r"(?<!\d)(?P<PartNumber>\d{7})(?=[-\s]|$)",
    },
    {
        "name": "Version",
        "description": "4-Digit Part Version",
        "regex": r"(?<=-)\s*(?P<Version>\d{4})(?=[-\s]|$)",
    },
    {
        "name": "DocType",
        "description": "3-Digit Document Type",
        "regex": r"(?<=-)\s*(?P<DocType>\d{3})(?=[-\s]|$)",
    },
    {
        "name": "TabNumber",
        "description": "2-Digit Tab Number",
        "regex": r"(?<=-)\s*(?P<TabNumber>\d{2})(?=\s|$)",
    },
    {
        "name": "Revision",
        "description": "2-Character Document Revision",
        "regex": r"REV\s+(?P<Revision>[A-Z]{2})(?=\s|$)",
    },
    {
        "name": "Title",
        "description": "Full Part Name",
        "regex": r"REV\s+[A-Z]{2}\s+(?P<Title>.+)$",
    },
    {
        "name": "DocNumber",
        "description": "Full Document Number",
        "regex": r"(?P<DocNumber>\d{7}[-\d]*\s+REV\s+[A-Z]{2})",
    },
]