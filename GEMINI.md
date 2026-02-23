# GEMINI.md

## Project Overview
**Madany's PDF Batcher (v1.1.3)** is a high-performance desktop application built with Python and PySide6 for batch processing PDF files. It allows users to overlay text, timestamps, and image stamps/watermarks across hundreds of PDFs with a single click.

### Main Technologies
- **Language:** Python 3.8+
- **GUI Framework:** PySide6 (Qt 6)
- **PDF Engine:** PyMuPDF (`fitz`) for fast rendering and manipulation.
- **Image Processing:** Pillow for stamp/watermark handling.
- **Packaging:** PyInstaller for standalone Windows executables.

### Key Features
- **Live WYSIWYG Preview:** Interactive preview with 25%–400% zoom and Ctrl+Scroll support.
- **Batch Processing:** Multi-threaded orchestration for high-speed document handling.
- **Substitution Engine:** Dynamic variable resolution (e.g., `$Filename`, `$Date`, `$PartNumber`) using regex-based extraction.
- **Per-Paper-Size Configuration:** Adaptive settings for A3, A4, Letter, etc., supporting both portrait and landscape modes.
- **Security:** AES-256 PDF encryption support.
- **Preset System:** JSON-based configuration management.

---

## Building and Running

### Development Setup
1. **Install Dependencies:**
   ```bash
   pip install PySide6 PyMuPDF Pillow
   ```
2. **Run Application:**
   ```bash
   python app.py
   ```

### Building Executable
The project uses PyInstaller with a custom `.spec` file that excludes unnecessary heavy libraries (matplotlib, pandas, etc.) to keep the binary size optimized.
```bash
pyinstaller MadanyPDFBatcher.spec
```
- **Output:** `dist/MadanyPDFBatcher/`
- **Note:** The entire folder must be distributed as it contains the executable and required DLLs/assets.

---

## Project Architecture

### Directory Structure
- `app.py`: Minimal entry point initializing `QApplication` and `MainWindow`.
- `core/`: Business logic and PDF engine.
  - `pdf_operations.py`: Core `PDFOperations` class for shared rendering and processing logic.
  - `substitution_engine.py`: Regex-based logic for resolving placeholders.
  - `constants.py`: Centralized app constants, paper definitions, and default configs.
  - `anchor.py`: Mathematical calculations for 9-position grid placement.
- `ui/`: Modular UI components.
  - `main_window.py`: Orchestrates state and wires signals between panels.
  - `processing.py`: Manages the background processing thread and progress tracking.
  - `preview_panel.py` & `pdf_viewer.py`: Handle the live preview logic.
- `dialogs/`: Configuration dialogs for features (Text, Stamp, Timestamp) and Presets.
- `widgets/`: Reusable components like the custom `PDFPreviewWidget` and `SubstitutionPicker`.
- `fonts/`: Embedded TTF fonts (Arial, SpaceMono, Sakkal Majalla) to ensure visual consistency across machines.

### Development Conventions
- **Asset Resolution:** Always use `core.utils.resolve_path()` to handle both source-run and PyInstaller `_MEIPASS` environments.
- **UI Decoupling:** Keep business logic in `core/` and UI-specific state/wiring in `ui/`.
- **Shared Rendering:** Preview and Batch Processing MUST use the same methods in `PDFOperations` to ensure "What You See Is What You Get" consistency.
- **Performance:** 
  - Use `paintEvent` for preview rendering to keep the UI responsive during zoom/scroll.
  - Use the `_rendering` guard flag in the preview widget to prevent recursive render loops.
  - Stamp images are cached via `PreparedStamp` to avoid redundant processing.

---

## Configuration & Data
- `config.ini`: Stores application-level persistence (e.g., the default preset name).
- `presets/*.json`: Full state of all features, serialized for easy sharing and backup.
- `substitution_definitions`: Defined in `core/constants.py`, these regex patterns drive the dynamic text replacement system.
