# Madany's PDF Batcher

A desktop application for batch processing PDFs. Add text, timestamps, image stamps, and AES-256 encryption across entire folders in a single operation.

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-6.x-41CD52?logo=qt&logoColor=white)
![PyMuPDF](https://img.shields.io/badge/PyMuPDF-fitz-orange)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)

## Features

- **Text Insertion** - Custom text with full font control, positioning, and per-paper-size configuration
- **Timestamp Insertion** - Formatted date/time stamps with optional prefix
- **Image Stamps & Watermarks** - Overlay images with configurable size, rotation, opacity, and placement
- **PDF Security** - AES-256 encryption
- **Batch Processing** - Process entire folders with multi-threaded progress tracking
- **Live Preview** - WYSIWYG preview with zoom (25%-400%) and Ctrl+Scroll support
- **Presets** - Save and load full configuration presets as JSON
- **Per-Paper-Size Configs** - Separate settings for A3, A4, Letter, and more in portrait and landscape
- **9-Position Placement** - Place content at any corner, edge, or center with millimeter margin offsets
- **Substitution Variables** - Use `$Filename`, `$Date`, and other placeholders that resolve per-file
- **File Search & Stats** - Search/filter the PDF tree by filename with a live checked/total file count
- **Dark / Light Theme** - Toggle themes with immediate preview updates

## Installation

### From Source

```bash
pip install PySide6 PyMuPDF Pillow
python app.py
```

### Pre-built Release

Download the latest release from the [Releases](https://github.com/LovingCivilian/madany-pdf-batcher/releases) page. No Python installation required.

## Quick Start

1. **Select Input Folder** - Choose a folder containing your PDF files
2. **Select Output Folder** - Choose where processed files will be saved
3. **Configure Features** - Enable text, timestamp, and/or stamp insertion
4. **Preview** - Verify placement and styling with the live preview
5. **Process** - Click "Process All" and let it run

## Project Structure

```
madany-pdf-batcher
├── app.py                      # Entry point
├── MadanyPDFBatcher.spec       # PyInstaller build config
│
├── core/                       # Business logic
│   ├── constants.py            # Paper sizes, positions, defaults
│   ├── pdf_operations.py       # PDF manipulation engine
│   ├── anchor.py               # 9-position placement math
│   ├── substitution_engine.py  # $Placeholder resolution
│   ├── preset_manager.py       # Preset serialization
│   ├── themes.py               # Light/dark palettes
│   └── utils.py                # PyInstaller path resolution
│
├── ui/                         # UI modules
│   ├── main_window.py          # MainWindow shell and state
│   ├── preview_panel.py        # Preview tab and zoom controls
│   ├── pdf_viewer.py           # PDF rendering and overlays
│   ├── features_panel.py       # Feature configuration controls
│   ├── files_panel.py          # File/folder selection and PDF tree
│   ├── navigation.py           # File/page navigation
│   ├── processing.py           # Batch processing orchestration
│   └── ...                     # toolbar, log, presets, config
│
├── dialogs/                    # Configuration dialogs
│   ├── base_configuration_dialog.py
│   ├── text_configuration_dialog.py
│   ├── timestamp_configuration_dialog.py
│   ├── stamp_configuration_dialog.py
│   └── preset_dialogs.py
│
├── widgets/                    # Reusable widgets
│   ├── preview_widget.py       # PDF preview with zoom and scroll
│   └── substitution_picker.py  # $Placeholder dropdown
│
└── fonts/                      # Embedded TTF fonts
    ├── Arial
    ├── SpaceMono
    └── Sakkal Majalla
```

## Building

Build a standalone Windows executable:

```bash
pyinstaller MadanyPDFBatcher.spec
```

Output goes to `dist/MadanyPDFBatcher/`. Distribute the entire folder.

## Built With

- **Python** - Core language
- **PySide6 (Qt)** - GUI framework
- **PyMuPDF** - PDF rendering and manipulation
- **Pillow** - Image processing for stamps and watermarks
