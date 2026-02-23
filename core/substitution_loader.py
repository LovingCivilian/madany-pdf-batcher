"""Load and save substitution definitions from/to substitutions.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.constants import SUBSTITUTION_DEFINITIONS
from core.utils import resolve_path


def _get_substitutions_path() -> Path:
    return resolve_path("substitutions.json")


def load_substitution_definitions() -> list[dict]:
    """Load substitution definitions from substitutions.json.

    If the file doesn't exist or is invalid, creates it from the hardcoded
    defaults in constants.py and returns those defaults.
    """
    path = _get_substitutions_path()

    if not path.exists():
        save_substitution_definitions(SUBSTITUTION_DEFINITIONS)
        return [d.copy() for d in SUBSTITUTION_DEFINITIONS]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        save_substitution_definitions(SUBSTITUTION_DEFINITIONS)
        return [d.copy() for d in SUBSTITUTION_DEFINITIONS]

    if not isinstance(data, list):
        save_substitution_definitions(SUBSTITUTION_DEFINITIONS)
        return [d.copy() for d in SUBSTITUTION_DEFINITIONS]

    valid: list[dict] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        if not all(k in entry for k in ("name", "description", "regex")):
            continue
        try:
            re.compile(entry["regex"])
        except re.error:
            continue
        valid.append(entry)

    if not valid:
        save_substitution_definitions(SUBSTITUTION_DEFINITIONS)
        return [d.copy() for d in SUBSTITUTION_DEFINITIONS]

    return valid


def save_substitution_definitions(definitions: list[dict]) -> None:
    """Write definitions to substitutions.json."""
    path = _get_substitutions_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(definitions, f, indent=2, ensure_ascii=False)
