# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Madany's PDF Batcher — a PySide6 desktop application for batch processing PDFs. Features include text insertion, timestamps, image stamps/watermarks, and PDF security (AES-256 encryption). v12 focuses on image stamp speed optimization.

## Running

```bash
python app.py
```

Dependencies: PySide6, PyMuPDF (`fitz`), Pillow. No requirements.txt exists — dependencies are inferred from imports.

## Architecture

**Entry point:** `app.py` — contains `MainWindow` (QMainWindow, ~2000 lines) and `PDFProcessingThread` (QThread worker). The main thread handles UI; the worker thread processes files asynchronously with progress signals.

**Core modules (`core/`):**
- `pdf_operations.py` — `PDFOperations` class: shared PDF manipulation used by both preview and batch processing. `PreparedStamp` caches processed stamps by opacity.
- `preset_manager.py` — Dataclass models (`Preset`, `TextInsertionSettings`, `StampInsertionSettings`, etc.) and `PresetManager` for JSON serialization to `presets/`.
- `constants.py` — Paper sizes (with 10-point tolerance), position presets (9-position grid), default configs, font family mappings, substitution regex patterns.
- `anchor.py` — `compute_anchor_for_pdf()` calculates (x, y) placement from a 9-position grid + margins (mm → points).
- `substitution_engine.py` — Extracts metadata from filenames via regex, substitutes `$Placeholder` variables in text. Drops lines where all placeholders are missing; inline missing placeholders become empty strings.
- `themes.py` — Light/dark QPalette definitions with custom accent (188, 82, 97).
- `utils.py` — `resolve_path()` handles PyInstaller `_MEIPASS` vs source paths.

**Dialogs (`dialogs/`):**
- `base_configuration_dialog.py` — Abstract base with paper-size list, preview widget, and page selection UI. All config dialogs inherit from this.
- `text_configuration_dialog.py`, `timestamp_configuration_dialog.py`, `stamp_configuration_dialog.py` — Feature-specific settings panels.
- `preset_dialogs.py` — Save/Load/Manage presets UI.

**Widgets (`widgets/`):**
- `preview_widget.py` — `PDFPreviewWidget`: renders PDF pages with debounced updates (150ms), theme-aware backgrounds.
- `substitution_picker.py` — Button with dropdown menu for inserting `$Placeholder` tokens.

## Key Design Patterns

- **Per-paper-size configs:** Feature settings are stored by paper key tuple `(family, mode)` (e.g., `("A4", "portrait")`). Legacy flat configs are auto-migrated.
- **Shared render logic:** `PDFOperations` methods are used identically by both preview rendering and batch processing to ensure WYSIWYG consistency.
- **Stamp caching:** `PreparedStamp` pre-processes images once and caches by opacity value to avoid redundant work during batch runs.
- **Stamp speed optimizations (v12 focus):** Smart resizing (3x upscale only for images < 1000px), fast PNG compression (`compress_level=1`), premultiplied alpha for clean resizing, selective sharpening.
- **Thread yielding:** Small sleeps (0.01s/file, 0.001s/page) in the worker thread keep UI responsive.
- **PyInstaller-compatible:** All asset paths go through `resolve_path()` to handle frozen builds.

## Configuration

- `config.ini` — App-level settings (e.g., `default_preset` under `[General]`).
- `presets/*.json` — Full preset serialization including all feature settings and timestamps.
- `fonts/` — Embedded TTF fonts: Arial, SpaceMono, Sakkal Majalla (each with regular/bold/italic/bolditalic variants).

## Processing Flow

`process_all_pdfs()` → validates folders → spawns `PDFProcessingThread` → for each PDF page: apply text → timestamp → stamp (if enabled) → save with optional encryption → emit progress signals.
