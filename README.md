# Madany's PDF Batcher v1.1.2

A desktop application for batch processing PDFs, built with PySide6 and PyMuPDF.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.x-green)
![License](https://img.shields.io/badge/License-Proprietary-red)

## Features

- **Text Insertion** — Add custom text to PDF pages with full font control, positioning, and per-paper-size configuration
- **Timestamp Insertion** — Stamp pages with formatted date/time and optional prefix
- **Image Stamps / Watermarks** — Overlay images with configurable size, rotation, opacity, and placement
- **PDF Security** — AES-256 encryption for processed files
- **Batch Processing** — Process entire folders of PDFs with progress tracking
- **Live Preview** — WYSIWYG preview with zoom (25%–400%), Ctrl+Scroll wheel support, and Original/Features toggle
- **Presets** — Save and load full configuration presets as JSON
- **Per-Paper-Size Configs** — Separate settings for A3, A4, Letter, etc. in portrait and landscape
- **9-Position Placement Grid** — Place text and stamps at any corner, edge, or center with margin offsets
- **Substitution Variables** — Use `$Filename`, `$Date`, and other placeholders in text that resolve per-file
- **Dark / Light Theme** — Toggle between themes with immediate preview updates

## Installation

### Requirements

- Python 3.8+
- PySide6
- PyMuPDF (`fitz`)
- Pillow

```bash
pip install PySide6 PyMuPDF Pillow
```

### Run

```bash
python app.py
```

## Project Structure

```
app.py                  # Entry point
core/
    constants.py        # Paper sizes, positions, defaults, font mappings
    pdf_operations.py   # Shared PDF manipulation (preview + batch)
    anchor.py           # 9-position placement calculations
    substitution_engine.py  # $Placeholder variable resolution
    preset_manager.py   # Preset serialization/deserialization
    themes.py           # Light/dark QPalette definitions
    utils.py            # PyInstaller-compatible path resolution
ui/
    main_window.py      # MainWindow shell, state, signal wiring
    preview_panel.py    # Preview tab with zoom controls
    features_panel.py   # Text, timestamp, stamp feature controls
    files_panel.py      # File/folder selection and PDF tree
    pdf_viewer.py       # PDF rendering and overlay logic
    navigation.py       # File/page navigation
    processing.py       # Batch processing orchestration
    toolbar.py          # Toolbar setup
    log_panel.py        # Log output panel
    preset_actions.py   # Preset load/save/manage actions
    config_manager.py   # Config file handling
dialogs/
    base_configuration_dialog.py    # Abstract base for config dialogs
    text_configuration_dialog.py    # Text feature settings
    timestamp_configuration_dialog.py # Timestamp feature settings
    stamp_configuration_dialog.py   # Stamp feature settings
    preset_dialogs.py               # Preset management dialogs
widgets/
    preview_widget.py       # PDFPreviewWidget with paintEvent rendering
    substitution_picker.py  # $Placeholder dropdown picker
fonts/                  # Embedded TTF fonts (Arial, SpaceMono, Sakkal Majalla)
presets/                # Saved preset JSON files
```

## Usage

1. **Select Input Folder** — Choose a folder containing PDF files
2. **Select Output Folder** — Choose where processed files will be saved
3. **Configure Features** — Enable and configure text, timestamp, and/or stamp insertion
4. **Preview** — Use the live preview to verify placement and styling
5. **Process** — Click "Process All" to batch process selected PDFs
