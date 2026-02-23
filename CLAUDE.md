# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Madany's PDF Batcher 1.1.3 — a PySide6 desktop application for batch processing PDFs. Features include text insertion, timestamps, image stamps/watermarks, and PDF security (AES-256 encryption).

## Running

```bash
python app.py
```

Dependencies: PySide6, PyMuPDF (`fitz`), Pillow.

## Building

```bash
pyinstaller MadanyPDFBatcher.spec
```

Output goes to `dist/MadanyPDFBatcher/`. The spec file has exclusions for unused packages (matplotlib, pandas, numpy, etc.).

## Architecture

**Entry point:** `app.py` — minimal launcher that creates `QApplication` and `MainWindow`.

**UI modules (`ui/`):** MainWindow is a thin shell; logic lives in focused modules:
- `main_window.py` — MainWindow class: state, UI assembly, signal wiring, zoom/toggle methods
- `preview_panel.py` — Preview tab with file/page navigation, zoom controls, scroll area
- `pdf_viewer.py` — PDF open/close/render, config resolution, page selection helpers
- `navigation.py` — File/page navigation, UI state updates
- `features_panel.py` — Text, timestamp, stamp feature controls
- `files_panel.py` — File/folder selection and PDF tree
- `processing.py` — Batch processing orchestration with `PDFProcessingThread`
- `toolbar.py`, `log_panel.py`, `preset_actions.py`, `config_manager.py`

**Core modules (`core/`):**
- `pdf_operations.py` — `PDFOperations` class: shared PDF manipulation used by both preview and batch processing. `PreparedStamp` caches processed stamps by opacity.
- `constants.py` — Paper sizes (with 10-point tolerance), position presets (9-position grid), default configs, font mappings, zoom constants.
- `anchor.py` — `compute_anchor_for_pdf()` calculates (x, y) placement from a 9-position grid + margins (mm → points).
- `substitution_engine.py` — Extracts metadata from filenames via regex, substitutes `$Placeholder` variables in text.
- `preset_manager.py` — Dataclass models and `PresetManager` for JSON serialization to `presets/`.
- `themes.py` — Light/dark QPalette definitions.
- `utils.py` — `resolve_path()` handles PyInstaller `_MEIPASS` vs source paths.

**Widgets (`widgets/`):**
- `preview_widget.py` — `PDFPreviewWidget` (QWidget with paintEvent for efficient rendering), `PreviewScrollArea` (handles viewport sizing and Ctrl+Scroll zoom).
- `substitution_picker.py` — Button with dropdown menu for inserting `$Placeholder` tokens.

**Dialogs (`dialogs/`):**
- `base_configuration_dialog.py` — Abstract base with paper-size list, preview widget, and page selection UI.
- `text_configuration_dialog.py`, `timestamp_configuration_dialog.py`, `stamp_configuration_dialog.py` — Feature-specific settings panels.
- `preset_dialogs.py` — Save/Load/Manage presets UI.

## Key Design Patterns

- **Per-paper-size configs:** Feature settings stored by paper key tuple `(family, mode)` (e.g., `("A4", "portrait")`).
- **Shared render logic:** `PDFOperations` methods used identically by preview and batch processing for WYSIWYG consistency.
- **paintEvent rendering:** Preview widget uses `painter.drawPixmap(destRect, sourcePixmap)` — Qt only processes visible pixels, keeping zoom responsive at any level.
- **Viewport oscillation prevention:** `PreviewScrollArea` reports actual viewport size but provides scrollbar margin to the widget, which snaps canvas sizes that barely overflow to prevent scrollbar toggle loops.
- **Ctrl+Scroll anchor zoom:** Zoom anchored on mouse cursor position by computing document coordinates before zoom and adjusting scrollbars after.
- **Re-entrance guard:** `_rendering` flag in `PDFPreviewWidget._render()` prevents recursive render loops from resize/viewport cascades.
- **Stamp caching:** `PreparedStamp` pre-processes images once, caches by opacity.
- **PyInstaller-compatible:** All asset paths go through `resolve_path()`.

## Git Commits

Do NOT include `Co-Authored-By` lines in commit messages. All commits should be attributed solely to the repository owner.

## Configuration

- `config.ini` — App-level settings (e.g., `default_preset` under `[General]`).
- `presets/*.json` — Full preset serialization including all feature settings.
- `fonts/` — Embedded TTF fonts: Arial, SpaceMono, Sakkal Majalla.
- `MadanyPDFBatcher.spec` — PyInstaller build configuration.
