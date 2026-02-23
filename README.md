# 📄 Madany's PDF Batcher v1.1.3

> 🚀 A powerful desktop application for batch processing PDFs — add text, timestamps, image stamps, and encryption to hundreds of files in one click.

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-6.x-41CD52?logo=qt&logoColor=white)
![PyMuPDF](https://img.shields.io/badge/PyMuPDF-fitz-orange)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| ✏️ **Text Insertion** | Add custom text with full font control, positioning, and per-paper-size configuration |
| 🕐 **Timestamp Insertion** | Stamp pages with formatted date/time and optional prefix |
| 🖼️ **Image Stamps & Watermarks** | Overlay images with configurable size, rotation, opacity, and placement |
| 🔒 **PDF Security** | Protect files with AES-256 encryption |
| ⚡ **Batch Processing** | Process entire folders with multi-threaded progress tracking |
| 🔍 **Live Preview** | WYSIWYG preview with zoom (25%–400%) and Ctrl+Scroll wheel support |
| 💾 **Presets** | Save and load full configuration presets as JSON |
| 📐 **Per-Paper-Size Configs** | Separate settings for A3, A4, Letter, and more — portrait & landscape |
| 🎯 **9-Position Placement** | Place content at any corner, edge, or center with mm margin offsets |
| 🔤 **Substitution Variables** | Use `$Filename`, `$Date`, and other placeholders that resolve per-file |
| 🌗 **Dark / Light Theme** | Toggle themes with immediate preview updates |

---

## 📥 Installation

### From Source

```bash
# Install dependencies
pip install PySide6 PyMuPDF Pillow

# Run the app
python app.py
```

### 💿 Pre-built Release

Download the latest release from the [Releases](https://github.com/LovingCivilian/madany-pdf-batcher/releases) page — no Python installation required.

---

## 🎯 Quick Start

1. 📂 **Select Input Folder** — Choose a folder containing your PDF files
2. 📁 **Select Output Folder** — Choose where processed files will be saved
3. ⚙️ **Configure Features** — Enable text, timestamp, and/or stamp insertion
4. 👁️ **Preview** — Use the live preview to verify placement and styling
5. ▶️ **Process** — Click "Process All" and watch it go!

---

## 🏗️ Project Structure

```
📦 madany-pdf-batcher
├── 🚀 app.py                 # Entry point
├── 📋 MadanyPDFBatcher.spec   # PyInstaller build config
│
├── 🧠 core/                   # Business logic
│   ├── constants.py           # Paper sizes, positions, defaults
│   ├── pdf_operations.py      # PDF manipulation engine
│   ├── anchor.py              # 9-position placement math
│   ├── substitution_engine.py # $Placeholder resolution
│   ├── preset_manager.py      # Preset serialization
│   ├── themes.py              # Light/dark palettes
│   └── utils.py               # PyInstaller path resolution
│
├── 🖥️ ui/                     # UI modules
│   ├── main_window.py         # MainWindow shell & state
│   ├── preview_panel.py       # Preview tab & zoom controls
│   ├── pdf_viewer.py          # PDF rendering & overlays
│   ├── features_panel.py      # Feature configuration controls
│   ├── files_panel.py         # File/folder selection
│   ├── navigation.py          # File/page navigation
│   ├── processing.py          # Batch processing orchestration
│   └── ...                    # toolbar, log, presets, config
│
├── 💬 dialogs/                # Configuration dialogs
│   ├── base_configuration_dialog.py
│   ├── text_configuration_dialog.py
│   ├── timestamp_configuration_dialog.py
│   ├── stamp_configuration_dialog.py
│   └── preset_dialogs.py
│
├── 🧩 widgets/                # Reusable widgets
│   ├── preview_widget.py      # PDF preview with zoom & scroll
│   └── substitution_picker.py # $Placeholder dropdown
│
└── 🔤 fonts/                  # Embedded TTF fonts
    ├── Arial (Regular/Bold/Italic/BoldItalic)
    ├── SpaceMono (Regular/Bold/Italic/BoldItalic)
    └── Sakkal Majalla (Regular/Bold)
```

---

## 🔨 Building

Build a standalone Windows executable:

```bash
pyinstaller MadanyPDFBatcher.spec
```

Output goes to `dist/MadanyPDFBatcher/` — distribute the entire folder.

---

## 📋 About

**Madany's PDF Batcher** was built to solve a real-world need: applying consistent text, timestamps, and stamps across large batches of PDF documents — something that's tedious and error-prone when done manually.

Whether you're stamping hundreds of engineering drawings, adding dates to legal documents, or watermarking reports, PDF Batcher handles it all with a live preview so you see exactly what you'll get before processing.

**Built with:**
- 🐍 **Python** — Core language
- 🖼️ **PySide6 (Qt)** — Cross-platform GUI framework
- 📄 **PyMuPDF** — Fast PDF rendering and manipulation
- 🎨 **Pillow** — Image processing for stamps and watermarks

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/LovingCivilian">LovingCivilian</a>
</p>
