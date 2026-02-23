from __future__ import annotations
import os
import re
from typing import Any

# Assumes constants.py is located at core/constants.py based on original import
from core.constants import SUBSTITUTION_DEFINITIONS

class SubstitutionEngine:
    """
    Fully modular substitution system.
    
    Responsibilities:
    1. Extracts named regex groups (metadata) from filenames.
    2. Applies variable substitution to text content using extracted metadata.
    """

    def __init__(self) -> None:
        self.definitions = SUBSTITUTION_DEFINITIONS

    # -----------------------------
    # Extract values from filename
    # -----------------------------
    def extract_values(self, filename: str) -> dict[str, str]:
        """
        Parses a filename to extract metadata based on regex definitions.

        Args:
            filename: The full filename or path.

        Returns:
            A dictionary of extracted values, e.g.:
            { "PartNumber": "1003375", "Revision": "AB", ... }
        """
        # Get base filename without extension
        base_name = os.path.splitext(os.path.basename(filename))[0]
        results: dict[str, str] = {}

        # Run all regex patterns against the filename
        for definition in self.definitions:
            pattern = definition["regex"]
            match = re.search(pattern, base_name, flags=re.IGNORECASE)
            
            if match:
                # Store all non-empty named groups
                for key, value in match.groupdict().items():
                    if value:
                        results[key] = value.strip()
        return results

    # -----------------------------
    # Apply substitutions
    # -----------------------------
    def apply(self, text: str, filename: str) -> tuple[str, dict[str, bool]]:
        """
        Substitutes $Placeholders in the text with values extracted from the filename.

        Special Handling:
        - Lines consisting ONLY of a missing placeholder (e.g., "$UnknownVar") are removed.
        - Inline missing placeholders (e.g., "Item: $UnknownVar") are replaced with empty strings.

        Returns:
            tuple(final_text, missing_placeholders_dict)
        """
        extracted_data = self.extract_values(filename)
        missing_keys: dict[str, bool] = {}

        # -------------------------------------------------
        # Helper: Filter out lines with only missing vars
        # -------------------------------------------------
        def filter_lines(raw_text: str) -> str:
            lines = raw_text.split('\n')
            kept_lines = []
            
            for line in lines:
                stripped = line.strip()
                # Check if line is exactly a placeholder variable
                match = re.fullmatch(r'\$(\w+)', stripped)
                
                if match:
                    key = match.group(1)
                    # If key is missing, drop the entire line
                    if key not in extracted_data:
                        missing_keys[key] = True
                        continue
                
                kept_lines.append(line)
            
            return '\n'.join(kept_lines)

        # -------------------------------------------------
        # Helper: Regex callback for inline replacement
        # -------------------------------------------------
        def replace_token(match: re.Match) -> str:
            key = match.group(1)
            if key in extracted_data:
                return extracted_data[key]
            
            # Record missing key and return empty string
            missing_keys[key] = True
            return ""

        # Step 1: Remove lines that are purely missing placeholders
        processed_text = filter_lines(text)

        # Step 2: Replace remaining inline placeholders
        final_text = re.sub(r"\$(\w+)", replace_token, processed_text)

        return final_text, missing_keys