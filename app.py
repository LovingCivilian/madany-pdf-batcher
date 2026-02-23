from __future__ import annotations
import sys
import os
import platform
import configparser
import copy  # Needed for deep copying configs to thread
import time  # Added for thread yielding
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set

import fitz  # PyMuPDF

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSplitter, QTabWidget, QTextEdit, QFileDialog,
    QGroupBox, QRadioButton, QGridLayout, QScrollArea, QStyleFactory,
    QTreeWidget, QTreeWidgetItem, QSizePolicy, QFileIconProvider,
    QProgressDialog, QMessageBox, QProgressBar, QDialog, QHeaderView, QMenu,
    QButtonGroup, QCheckBox, QToolBar, QSpinBox, QAbstractSpinBox, QFrame
)
from PySide6.QtCore import Qt, QFileInfo, QTimer, QEvent, QThread, Signal
from PySide6.QtGui import QAction, QPalette, QColor

# Custom Dialogs & Widgets
from dialogs.text_configuration_dialog import TextConfigurationDialog
from dialogs.timestamp_configuration_dialog import TimestampConfigurationDialog
from dialogs.stamp_configuration_dialog import StampConfigurationDialog
from widgets.substitution_picker import SubstitutionPickerButton
from widgets.preview_widget import PDFPreviewWidget
from dialogs.preset_dialogs import (
    SavePresetDialog,
    LoadPresetDialog,
    ManagePresetsDialog,
)

# Core Logic
from core.pdf_operations import PDFOperations, PreparedStamp
from core.anchor import compute_anchor_for_pdf
from core.substitution_engine import SubstitutionEngine
from core.preset_manager import (
    PresetManager,
    Preset,
    TextInsertionSettings,
    TimestampInsertionSettings,
    StampInsertionSettings,
    PDFSecuritySettings,
    configs_to_nested_structure,
    nested_structure_to_configs,
)
from core.constants import (
    PAPER_DEFINITIONS,
    ALL_PAPER_KEYS,
    KEY_TO_LABEL,
    LABEL_TO_KEY,
    DEFAULT_TEXT_CONFIG,
    DEFAULT_TIMESTAMP_CONFIG,
    DEFAULT_STAMP_CONFIG,
    DEFAULT_APP_CONFIG,
    TIMESTAMP_FORMATS,
    get_font_families,
    detect_paper_key,
    DEBOUNCE_DELAY_MS,
)
from core.utils import resolve_path
from core.themes import get_light_palette, get_dark_palette


# =====================================================================
# WORKER THREAD
# =====================================================================
class PDFProcessingThread(QThread):
    progress_update = Signal(int, str)
    log_message = Signal(str)
    finished_processing = Signal(bool, int, int, list)  # (canceled, success_count, error_count, error_list)

    def __init__(self, 
                 files: List[str], 
                 output_dir: str, 
                 input_root: str,
                 features: Dict,
                 security_settings: Dict,
                 text_settings: Dict,
                 timestamp_settings: Dict,
                 stamp_settings: Dict,
                 pdf_ops_instance: PDFOperations,
                 substitution_engine: SubstitutionEngine,
                 font_families: Dict):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.input_root = input_root
        self.features = features
        self.security_settings = security_settings
        self.text_settings = text_settings
        self.timestamp_settings = timestamp_settings
        self.stamp_settings = stamp_settings
        self.pdf_ops = pdf_ops_instance
        self.substitution_engine = substitution_engine
        self.font_families = font_families
        self._is_canceled = False

    def run(self):
        # Set thread priority to low to ensure UI stays responsive
        self.setPriority(QThread.LowPriority)

        success_count = 0
        error_count = 0
        errors = []

        local_pdf_ops = PDFOperations()
        
        # Prepare stamp if needed
        prepared_stamp = None
        if self.features["Stamp Insertion"] and self.stamp_settings.get("path"):
            if os.path.exists(self.stamp_settings["path"]):
                prepared_stamp = PreparedStamp(self.stamp_settings["path"], local_pdf_ops)

        ts_full_str = self.timestamp_settings.get("full_string", "")

        for idx, pdf_path in enumerate(self.files):
            # Check cancellation
            if self.isInterruptionRequested():
                self._is_canceled = True
                break

            # 2. UPDATE EVERY SINGLE TIME (No skipping)
            filename = os.path.basename(pdf_path)
            self.progress_update.emit(idx, f"Processing: {filename}")

            # 3. SAFETY SLEEP
            time.sleep(0.01)

            try:
                doc = fitz.open(pdf_path)
                page_count = len(doc)

                # Resolve text substitution for this file
                final_text_content = ""
                if self.features["Text Insertion"]:
                    raw_text = self.text_settings.get("raw_text", "")
                    final_text_content, _ = self.substitution_engine.apply(raw_text, pdf_path)

                for i in range(page_count):
                    # Every 1 page, pause for 1ms to let the UI breathe.
                    # This prevents the UI from freezing on large documents.
                    time.sleep(0.001)

                    page = doc.load_page(i)
                    
                    # --- APPLY TEXT ---
                    if self.features["Text Insertion"]:
                        cfg = self._get_config(page, self.text_settings["configs"], self.text_settings["default"])
                        if self._check_selection(i, page_count, cfg):
                            # Delegated to PDFOperations shared logic
                            self.pdf_ops.apply_text_to_page(
                                page, final_text_content, cfg, self.font_families
                            )

                    # --- APPLY TIMESTAMP ---
                    if self.features["Timestamp Insertion"]:
                        cfg = self._get_config(page, self.timestamp_settings["configs"], self.timestamp_settings["default"])
                        if self._check_selection(i, page_count, cfg):
                            # Delegated to PDFOperations shared logic
                            self.pdf_ops.apply_text_to_page(
                                page, ts_full_str, cfg, self.font_families
                            )

                    # --- APPLY STAMP ---
                    if self.features["Stamp Insertion"] and prepared_stamp:
                        cfg = self._get_config(page, self.stamp_settings["configs"], self.stamp_settings["default"])
                        if self._check_selection(i, page_count, cfg):
                            self._apply_stamp_logic(page, cfg, prepared_stamp)

                # Save Logic
                if self.input_root:
                    rel_path = os.path.relpath(pdf_path, self.input_root)
                    save_path = os.path.join(self.output_dir, rel_path)
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                else:
                    save_path = os.path.join(self.output_dir, filename)

                save_args = {"garbage": 0, "deflate": True, "clean": True}
                
                if self.features["PDF Security"]:
                    save_args.update({
                        "encryption": fitz.PDF_ENCRYPT_AES_256,
                        "owner_pw": self.security_settings["password"],
                        "permissions": self.security_settings["permissions"]
                    })

                doc.save(save_path, **save_args)
                doc.close()
                success_count += 1

            except Exception as e:
                msg = f"Failed {filename}: {e}"
                self.log_message.emit(msg)
                errors.append(msg)
                error_count += 1

        self.finished_processing.emit(self._is_canceled, success_count, error_count, errors)

    # --- Thread Helpers ---
    def _get_page_dim_corrected(self, page):
        rect = page.rect
        if page.rotation in (90, 270): return rect.height, rect.width
        return rect.width, rect.height

    def _get_config(self, page, configs, default):
        w, h = self._get_page_dim_corrected(page)
        key = detect_paper_key(w, h)
        if key is None:
            mode = "portrait" if h >= w else "landscape"
            key = ("Unknown", mode)
        return configs.get(key, default)

    def _check_selection(self, idx, total, cfg):
        mode = cfg.get("page_selection", "all")
        custom_str = cfg.get("custom_pages", "")
        pno = idx + 1
        if mode == "all": return True
        if mode == "first": return pno == 1
        if mode == "last": return pno == total
        if mode == "odd": return (pno % 2) == 1
        if mode == "even": return (pno % 2) == 0
        if mode == "custom":
            pages = set()
            for part in custom_str.split(","):
                part = part.strip()
                if "-" in part:
                    try:
                        s, e = map(int, part.split("-", 1))
                        if s > e: s, e = e, s
                        pages.update(range(s, e + 1))
                    except: continue
                else:
                    try: pages.add(int(part))
                    except: continue
            return pno in pages
        return False

    def _apply_stamp_logic(self, page, cfg, prepared_stamp):
        page_w, page_h = self._get_page_dim_corrected(page)
        pts_per_mm = 72 / 25.4
        w_mm = cfg.get("stamp_width_mm", 50.0)
        h_mm = cfg.get("stamp_height_mm", 50.0)
        stamp_w_pts = w_mm * pts_per_mm
        stamp_h_pts = h_mm * pts_per_mm
        stamp_rotation = cfg.get("stamp_rotation", 0)
        stamp_opacity = cfg.get("stamp_opacity", 100) / 100.0

        if int(stamp_rotation) % 180 == 90:
            visual_w, visual_h = stamp_h_pts, stamp_w_pts
        else:
            visual_w, visual_h = stamp_w_pts, stamp_h_pts

        block_x, block_y = compute_anchor_for_pdf(
            page_w, page_h, visual_w, visual_h, cfg
        )

        self.pdf_ops.insert_stamp_bytes(
            page,
            prepared_stamp.get_bytes(stamp_opacity),
            block_x, block_y,
            visual_w, visual_h,
            stamp_rotation
        )

# =====================================================================
# CUSTOM PROGRESS DIALOG
# =====================================================================
class ProgressDialog(QDialog):
    """Custom progress dialog with fixed size and centered cancel button."""
    
    def __init__(self, title: str, label_text: str, max_value: int = 0, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 130)
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self._is_canceled = False
        self._max_value = max_value
        
        main_layout = QVBoxLayout(self)
        
        self.status_label = QLabel(label_text)
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.status_label.setMinimumHeight(35)
        main_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(max_value)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(100)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)
    
    def _on_cancel_clicked(self) -> None:
        self._is_canceled = True
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling...")
    
    def was_canceled(self) -> bool:
        return self._is_canceled
    
    def set_value(self, value: int) -> None:
        self.progress_bar.setValue(value)
    
    def set_label_text(self, text: str) -> None:
        if len(text) > 50:
            text = text[:47] + "..."
        self.status_label.setText(text)
    
    def set_maximum(self, max_value: int) -> None:
        self._max_value = max_value
        self.progress_bar.setMaximum(max_value)


# =====================================================================
# MAIN WINDOW
# =====================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Madany's PDF Batcher 1.1.2")
        self.resize(1500, 900)  # Slightly increased height for new UI

        # -----------------------------------------------------------------
        # 1. State Initialization
        # -----------------------------------------------------------------
        self.selected_pdf_paths: List[str] = []
        self.current_file_index: int = -1
        self.current_doc: Optional[fitz.Document] = None
        self.current_page_index: int = 0
        self.current_page_count: int = 0

        self._current_bold_item: Optional[QTreeWidgetItem] = None
        
        self.live_input_text: str = ""
        self.live_timestamp_prefix: str = ""
        self.selected_timestamp_format: str = TIMESTAMP_FORMATS[0][1]

        self._suppress_list_update = False
        
        self.pdf_ops = PDFOperations()
        self.substitution_engine = SubstitutionEngine()
        self.preset_manager = PresetManager()
        self.font_families: Dict[str, Dict[str, str]] = get_font_families()
        self._is_dark_theme = False  # Default to Light
        
        self._worker_thread = None # Keep reference to thread
        self._progress_dialog = None # Keep reference to dialog

        # Configuration Handling
        self.config_path = resolve_path("config.ini")
        self._init_config()  # Load or create config.ini immediately

        self._preview_debounce_timer = QTimer()
        self._preview_debounce_timer.setSingleShot(True)
        self._preview_debounce_timer.timeout.connect(self._perform_delayed_render)

        # -----------------------------------------------------------------
        # 2. Configuration State
        # -----------------------------------------------------------------
        default_family = DEFAULT_TEXT_CONFIG.get("font_family", "Arial")
        if default_family not in self.font_families and self.font_families:
            default_family = next(iter(self.font_families.keys()))

        # -- Text Config --
        self.default_text_config = DEFAULT_TEXT_CONFIG.copy()
        self.default_text_config["font_family"] = default_family
        self.default_text_config["page_selection"] = "all"
        self.default_text_config["custom_pages"] = ""
        self.text_configs_by_size: Dict[Tuple[str, str], Dict] = {
            key: self.default_text_config.copy() for key in ALL_PAPER_KEYS
        }
        self._text_config_dialog: Optional[TextConfigurationDialog] = None

        # -- Timestamp Config --
        self.default_timestamp_config = DEFAULT_TIMESTAMP_CONFIG.copy()
        if self.default_timestamp_config.get("font_family") not in self.font_families:
             self.default_timestamp_config["font_family"] = default_family
        self.default_timestamp_config["page_selection"] = "all"
        self.default_timestamp_config["custom_pages"] = ""
        self.timestamp_configs_by_size: Dict[Tuple[str, str], Dict] = {
            key: self.default_timestamp_config.copy() for key in ALL_PAPER_KEYS
        }
        self._timestamp_config_dialog: Optional[TimestampConfigurationDialog] = None

        # -- Stamp Config --
        self.default_stamp_config = DEFAULT_STAMP_CONFIG.copy()
        self.default_stamp_config["page_selection"] = "all"
        self.default_stamp_config["custom_pages"] = ""
        self.stamp_configs_by_size: Dict[Tuple[str, str], Dict] = {
            key: self.default_stamp_config.copy() for key in ALL_PAPER_KEYS
        }
        self.current_stamp_path: str = ""
        self._stamp_config_dialog: Optional[StampConfigurationDialog] = None

        # -----------------------------------------------------------------
        # 3. UI Construction
        # -----------------------------------------------------------------
        self.setMenuBar(None)
        self._setup_toolbar()
        self._setup_ui()
        self._connect_signals()
        
        self.update_navigation_ui()

        # -----------------------------------------------------------------
        # 4. Live Label Updates
        # -----------------------------------------------------------------
        self._timestamp_label_timer = QTimer(self)
        self._timestamp_label_timer.timeout.connect(self._update_timestamp_labels)
        self._timestamp_label_timer.start(1000)  # Update labels every second

        # -----------------------------------------------------------------
        # 5. Startup Logic
        # -----------------------------------------------------------------
        self._load_default_preset_on_startup()

    # =================================================================
    # Config Helpers
    # =================================================================
    def _init_config(self) -> None:
        config = configparser.ConfigParser()
        
        if os.path.exists(self.config_path):
            try:
                config.read(self.config_path, encoding='utf-8')
            except Exception as e:
                print(f"Warning: Could not read config.ini, creating new one: {e}")
                config = configparser.ConfigParser()
        
        modified = False
        for section, options in DEFAULT_APP_CONFIG.items():
            if not config.has_section(section):
                config.add_section(section)
                modified = True
            for key, default_value in options.items():
                if not config.has_option(section, key):
                    config.set(section, key, str(default_value))
                    modified = True
        
        if modified or not os.path.exists(self.config_path):
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    config.write(f)
            except Exception as e:
                print(f"Warning: Could not save config.ini: {e}")
        
        self._config = config

    def _get_default_preset_name(self) -> Optional[str]:
        if hasattr(self, '_config') and self._config:
            return self._config.get("General", "default_preset", fallback=None) or None
        
        config = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            try:
                config.read(self.config_path, encoding='utf-8')
                value = config.get("General", "default_preset", fallback=None)
                return value if value else None
            except Exception as e:
                print(f"Error reading config: {e}")
        return None

    def _set_default_preset_name(self, name: Optional[str]) -> None:
        config = configparser.ConfigParser()
        if os.path.exists(self.config_path):
            try:
                config.read(self.config_path, encoding='utf-8')
            except Exception:
                pass
        
        if not config.has_section("General"):
            config.add_section("General")
        
        if name:
            config.set("General", "default_preset", name)
        else:
            config.set("General", "default_preset", "")
        
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                config.write(f)
            self._config = config
        except Exception as e:
            self.show_error("Configuration Error", f"Could not save config file:\n{e}")

    # =================================================================
    # UI Setup Methods
    # =================================================================
    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        self.action_load_preset = QAction("Load Preset", self)
        self.action_load_preset.setStatusTip("Load a saved configuration")
        self.action_load_preset.triggered.connect(self.load_preset)
        toolbar.addAction(self.action_load_preset)

        self.action_save_preset = QAction("Save Preset", self)
        self.action_save_preset.setStatusTip("Save current configuration")
        self.action_save_preset.triggered.connect(self.save_preset)
        toolbar.addAction(self.action_save_preset)

        self.action_manage_presets = QAction("Manage Presets", self)
        self.action_manage_presets.setStatusTip("Manage existing presets")
        self.action_manage_presets.triggered.connect(self.manage_presets)
        toolbar.addAction(self.action_manage_presets)

        toolbar.addSeparator()

        self.action_documentation = QAction("Documentation", self)
        self.action_documentation.setStatusTip("Help Documentation")
        toolbar.addAction(self.action_documentation)

        self.action_about = QAction("About", self)
        self.action_about.setStatusTip("About")
        toolbar.addAction(self.action_about)

        toolbar.addSeparator()

        self.action_toggle_theme = QAction("Dark Mode", self)
        self.action_toggle_theme.setStatusTip("Toggle between Light and Dark themes")
        self.action_toggle_theme.triggered.connect(self.toggle_theme)

    def _setup_ui(self) -> None:
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        self.setCentralWidget(central_widget)

        self.main_splitter = QSplitter(Qt.Horizontal)
        central_layout.addWidget(self.main_splitter)

        self._init_left_panel()
        self._init_right_panel()

        self.main_splitter.setSizes([1000, 400])
        self.main_splitter.splitterMoved.connect(self._on_splitter_moved)

    def _init_left_panel(self) -> None:
        container = QWidget()
        container.setMinimumWidth(300)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.left_tabs = QTabWidget()
        layout.addWidget(self.left_tabs)

        self._setup_preview_tab()
        self._setup_log_tab()

        self.main_splitter.addWidget(container)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setCollapsible(0, False)

    def _setup_preview_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        file_controls = QWidget()
        file_layout = QHBoxLayout(file_controls)
        file_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_prev_file = QPushButton("PREVIOUS")
        self.file_input = QSpinBox()
        self.file_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.file_input.setMinimum(0)
        self.file_input.setMaximum(0)
        self.file_input.setFixedWidth(65)
        self.file_input.setAlignment(Qt.AlignCenter)
        self.file_input.setKeyboardTracking(False)
        self.file_input.setSuffix(" / 0")
        self.btn_next_file = QPushButton("NEXT")
        self.file_status_entry = QLineEdit("No file selected")
        self.file_status_entry.setFocusPolicy(Qt.NoFocus)
        self.file_status_entry.setEnabled(False)
        
        file_layout.addWidget(self.btn_prev_file, 0, Qt.AlignVCenter)
        file_layout.addWidget(self.file_input, 0, Qt.AlignVCenter)
        file_layout.addWidget(self.btn_next_file, 0, Qt.AlignVCenter)
        file_layout.addWidget(self.file_status_entry, 1)

        layout.addWidget(file_controls)

        self.preview_widget = PDFPreviewWidget()
        layout.addWidget(self.preview_widget, stretch=1)

        page_controls = QWidget()
        page_layout = QHBoxLayout(page_controls)
        page_layout.setContentsMargins(0, 0, 0, 0)

        self.page_info_label = QLabel("Page Info")
        self.page_info_label.setAlignment(Qt.AlignCenter)
        self.page_info_label.setFocusPolicy(Qt.NoFocus)
        self.page_info_label.setEnabled(False)
        self.page_info_label.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.page_info_label.setAutoFillBackground(True)
        self.page_info_label.setBackgroundRole(QPalette.Base)
        self.page_info_label.setFixedWidth(250)
        self.page_info_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)

        nav_container = QWidget()
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setAlignment(Qt.AlignCenter)

        self.btn_prev_page = QPushButton("PREVIOUS")
        self.page_input = QSpinBox()
        self.page_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.page_input.setMinimum(0)
        self.page_input.setMaximum(0)
        self.page_input.setFixedWidth(65)
        self.page_input.setAlignment(Qt.AlignCenter)
        self.page_input.setKeyboardTracking(False)
        self.page_input.setSuffix(" / 0")
        self.btn_next_page = QPushButton("NEXT")
        
        nav_layout.addWidget(self.btn_prev_page)
        nav_layout.addWidget(self.page_input)
        nav_layout.addWidget(self.btn_next_page)

        self.active_features_label = QLabel("Active Features")
        self.active_features_label.setAlignment(Qt.AlignCenter)
        self.active_features_label.setFocusPolicy(Qt.NoFocus)
        self.active_features_label.setEnabled(False)
        self.active_features_label.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.active_features_label.setAutoFillBackground(True)
        self.active_features_label.setBackgroundRole(QPalette.Base)
        self.active_features_label.setFixedWidth(250)
        self.active_features_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)

        page_layout.addWidget(self.page_info_label, 1) 
        page_layout.addStretch(0)
        page_layout.addWidget(nav_container)
        page_layout.addStretch(0)
        page_layout.addWidget(self.active_features_label, 1) 
        
        layout.addWidget(page_controls)
        self.left_tabs.addTab(tab, "Preview")

    def _setup_log_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        layout.addWidget(self.log_viewer)
        self.left_tabs.addTab(tab, "Log")

    def _init_right_panel(self) -> None:
        container = QWidget()
        container.setMinimumWidth(400)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.right_tabs = QTabWidget()
        layout.addWidget(self.right_tabs)

        self._setup_options_tab() # Files & General
        self._setup_features_tab() # Consolidated Features

        self.main_splitter.addWidget(container)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.setCollapsible(1, False)

    def _setup_options_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        input_group = QGroupBox("Input Folder")
        input_layout = QHBoxLayout(input_group)
        self.input_path_entry = QLineEdit()
        self.input_path_entry.setReadOnly(True)
        self.btn_browse_input = QPushButton("Browse")
        input_layout.addWidget(self.input_path_entry)
        input_layout.addWidget(self.btn_browse_input)
        layout.addWidget(input_group)

        tree_group = QGroupBox("Found PDFs")
        tree_layout = QVBoxLayout(tree_group)
        self.pdf_tree = QTreeWidget()
        self.pdf_tree.setHeaderHidden(False)
        self.pdf_tree.setHeaderLabels(["Name", "Size"])
        header = self.pdf_tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 60)
        header.setStretchLastSection(False)
        self.pdf_tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.pdf_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pdf_tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.pdf_tree.itemDoubleClicked.connect(self.on_tree_item_double_clicked)
        self.pdf_tree.setAnimated(True)
        tree_layout.addWidget(self.pdf_tree)
        layout.addWidget(tree_group, 1)

        output_group = QGroupBox("Output Folder")
        output_layout = QHBoxLayout(output_group)
        self.output_path_entry = QLineEdit()
        self.output_path_entry.setReadOnly(True)
        self.btn_browse_output = QPushButton("Browse")
        output_layout.addWidget(self.output_path_entry)
        output_layout.addWidget(self.btn_browse_output)
        layout.addWidget(output_group)

        self.btn_process_all = QPushButton("Process All PDFs")
        layout.addWidget(self.btn_process_all)
        
        self.right_tabs.addTab(tab, "Files")

    def _setup_features_tab(self) -> None:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 1)

        self.feature_scroll_area = QScrollArea()
        self.feature_scroll_area.setWidgetResizable(True)
        self.feature_scroll_area.setFrameShape(QFrame.NoFrame)
        self.feature_scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")

        self.feature_scroll_content = QWidget()
        self.feature_scroll_content.setObjectName("scroll_content_widget")
        self.feature_scroll_content.setStyleSheet("#scroll_content_widget { background-color: transparent; }")

        content_layout = QVBoxLayout(self.feature_scroll_content)

        # --- 1. Text Insertion Group ---
        self.group_text_insertion = QGroupBox("Text Insertion")
        self.group_text_insertion.setCheckable(True)
        self.group_text_insertion.setChecked(False)
        text_group_layout = QVBoxLayout(self.group_text_insertion)

        text_input_group = QGroupBox("Text to Insert")
        text_input_layout = QVBoxLayout(text_input_group)
        self.text_input_box = QTextEdit()
        self.text_input_box.setFixedHeight(80)
        self.text_input_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.text_input_box.setPlaceholderText("Enter text to insert...")
        self.btn_substitution_picker = SubstitutionPickerButton(self.text_input_box)
        text_input_layout.addWidget(self.text_input_box)
        text_input_layout.addWidget(self.btn_substitution_picker)
        text_group_layout.addWidget(text_input_group)

        self.btn_text_config = QPushButton("Text Configuration")
        text_group_layout.addWidget(self.btn_text_config)
        content_layout.addWidget(self.group_text_insertion)

        # --- 2. Timestamp Insertion Group ---
        self.group_timestamp_insertion = QGroupBox("Timestamp Insertion")
        self.group_timestamp_insertion.setCheckable(True)
        self.group_timestamp_insertion.setChecked(False)
        ts_group_layout = QVBoxLayout(self.group_timestamp_insertion)

        ts_prefix_group = QGroupBox("Prefix")
        ts_prefix_layout = QVBoxLayout(ts_prefix_group)
        self.ts_prefix_edit = QLineEdit()
        self.ts_prefix_edit.setPlaceholderText("e.g. Printed on: ")
        ts_prefix_layout.addWidget(self.ts_prefix_edit)
        ts_group_layout.addWidget(ts_prefix_group)

        ts_format_group = QGroupBox("Formats")
        ts_format_layout = QVBoxLayout(ts_format_group)
        self.ts_format_btn_group = QButtonGroup(self)
        now = datetime.now()
        first_fmt = True
        for _, fmt_str in TIMESTAMP_FORMATS:
            label_text = now.strftime(fmt_str)
            rb = QRadioButton(label_text)
            rb.setProperty("fmt_str", fmt_str)
            if first_fmt:
                rb.setChecked(True)
                first_fmt = False
            self.ts_format_btn_group.addButton(rb)
            ts_format_layout.addWidget(rb)
        ts_group_layout.addWidget(ts_format_group)

        self.btn_timestamp_config = QPushButton("Timestamp Configuration")
        ts_group_layout.addWidget(self.btn_timestamp_config)
        content_layout.addWidget(self.group_timestamp_insertion)

        # --- 3. Stamp Insertion Group ---
        self.group_stamp_insertion = QGroupBox("Stamp Insertion (Experimental)")
        self.group_stamp_insertion.setCheckable(True)
        self.group_stamp_insertion.setChecked(False)
        stamp_group_layout = QVBoxLayout(self.group_stamp_insertion)

        stamp_file_group = QGroupBox("Stamp File")
        stamp_file_layout = QHBoxLayout(stamp_file_group)
        self.stamp_path_entry = QLineEdit()
        self.stamp_path_entry.setPlaceholderText("Select stamp file...")
        self.stamp_path_entry.setReadOnly(True)
        self.btn_browse_stamp = QPushButton("Browse")
        self.btn_browse_stamp.clicked.connect(self.select_stamp_file)
        stamp_file_layout.addWidget(self.stamp_path_entry)
        stamp_file_layout.addWidget(self.btn_browse_stamp)
        stamp_group_layout.addWidget(stamp_file_group)

        self.btn_stamp_config = QPushButton("Stamp Configuration")
        self.btn_stamp_config.setEnabled(False) 
        stamp_group_layout.addWidget(self.btn_stamp_config)
        content_layout.addWidget(self.group_stamp_insertion)

        # --- 4. PDF Security Group ---
        self.security_group = QGroupBox("PDF Security")
        self.security_group.setCheckable(True)
        self.security_group.setChecked(False)
        security_layout = QVBoxLayout(self.security_group)

        pass_group = QGroupBox("Master Password")
        pass_layout = QHBoxLayout(pass_group)
        self.security_password = QLineEdit()
        self.security_password.setEchoMode(QLineEdit.Password)
        self.security_password.setPlaceholderText("Required to enable permissions...")
        pass_layout.addWidget(self.security_password)
        
        self._password_visible = False
        self.btn_toggle_password = QPushButton("Show")
        self.btn_toggle_password.setFixedWidth(45)
        self.btn_toggle_password.clicked.connect(self._toggle_password_visibility)
        pass_layout.addWidget(self.btn_toggle_password)
        security_layout.addWidget(pass_group)

        perms_group = QGroupBox("Allow User To")
        perms_grid = QGridLayout(perms_group)
        self.chk_perm_print = QCheckBox("Print Document")
        self.chk_perm_modify = QCheckBox("Modify Document")
        self.chk_perm_copy = QCheckBox("Copy Content")
        self.chk_perm_annotate = QCheckBox("Annotations")
        self.chk_perm_form = QCheckBox("Fill Forms")
        self.chk_perm_assemble = QCheckBox("Assemble Document")
        perms_grid.addWidget(self.chk_perm_print, 0, 0)
        perms_grid.addWidget(self.chk_perm_modify, 0, 1)
        perms_grid.addWidget(self.chk_perm_copy, 1, 0)
        perms_grid.addWidget(self.chk_perm_annotate, 1, 1)
        perms_grid.addWidget(self.chk_perm_form, 2, 0)
        perms_grid.addWidget(self.chk_perm_assemble, 2, 1)
        security_layout.addWidget(perms_group)

        content_layout.addWidget(self.security_group)

        content_layout.addStretch()
        
        self.feature_scroll_area.setWidget(self.feature_scroll_content)
        tab_layout.addWidget(self.feature_scroll_area)
        
        self.right_tabs.addTab(tab, "Features")

    def _connect_signals(self) -> None:
        self.btn_prev_file.clicked.connect(self.goto_prev_file)
        self.btn_next_file.clicked.connect(self.goto_next_file)
        self.file_input.valueChanged.connect(self.on_file_input_changed)
        
        self.btn_prev_page.clicked.connect(self.goto_prev_page)
        self.btn_next_page.clicked.connect(self.goto_next_page)
        self.page_input.valueChanged.connect(self.on_page_input_changed)

        self.btn_browse_input.clicked.connect(self.pick_input_folder)
        self.btn_browse_output.clicked.connect(self.pick_output_folder)
        self.pdf_tree.itemChanged.connect(self.on_tree_item_changed)
        
        self.btn_process_all.clicked.connect(self.process_all_pdfs)

        self.text_input_box.textChanged.connect(self.on_text_content_changed)
        self.btn_text_config.clicked.connect(self.open_text_configuration)
        self.group_text_insertion.toggled.connect(self.render_current_page)

        self.group_timestamp_insertion.toggled.connect(self.render_current_page)
        self.ts_prefix_edit.textChanged.connect(self.on_timestamp_content_changed)
        self.ts_format_btn_group.buttonClicked.connect(self.on_timestamp_content_changed)
        self.btn_timestamp_config.clicked.connect(self.open_timestamp_configuration)

        self.group_stamp_insertion.toggled.connect(self.render_current_page)
        self.btn_stamp_config.clicked.connect(self.open_stamp_configuration)

    # =================================================================
    # Helper: Rendering Debounce & Live Updates
    # =================================================================
    def _perform_delayed_render(self) -> None:
        self.render_current_page()

    def _update_timestamp_labels(self) -> None:
        if not self.group_timestamp_insertion.isChecked():
            return

        now = datetime.now()
        for btn in self.ts_format_btn_group.buttons():
            fmt = btn.property("fmt_str")
            if fmt:
                btn.setText(now.strftime(fmt))

    # =================================================================
    # Preset Management
    # =================================================================
    def load_preset(self) -> None:
        dialog = LoadPresetDialog(self.preset_manager, self)
        if dialog.exec():
            preset_name = dialog.get_selected_preset()
            if preset_name:
                self._apply_preset_to_ui(preset_name)

    def save_preset(self) -> None:
        dialog = SavePresetDialog(self.preset_manager, self)
        if dialog.exec():
            name, description = dialog.get_preset_info()
            if name:
                self._gather_state_and_save_preset(name, description)

    def manage_presets(self) -> None:
        current_state = self._build_current_preset_object()
        default_preset_name = self._get_default_preset_name()
        
        dialog = ManagePresetsDialog(
            self.preset_manager, 
            parent=self, 
            current_preset=current_state,
            default_preset_name=default_preset_name,
            on_default_change=self._set_default_preset_name
        )
        dialog.exec()

    def _load_default_preset_on_startup(self) -> None:
        default_name = self._get_default_preset_name()
        if default_name and self.preset_manager.preset_exists(default_name):
            self._apply_preset_to_ui(default_name)
            self.append_log(f"Auto-loaded default preset: {default_name}")

    def _build_current_preset_object(self, name: str = "Temp", description: str = "") -> Preset:
        text_settings = TextInsertionSettings(
            enabled=self.group_text_insertion.isChecked(),
            text=self.live_input_text,
            configs_by_size=self.text_configs_by_size.copy(),
        )

        checked_btn = self.ts_format_btn_group.checkedButton()
        fmt_str = checked_btn.property("fmt_str") if checked_btn else "%Y-%m-%d"

        ts_settings = TimestampInsertionSettings(
            enabled=self.group_timestamp_insertion.isChecked(),
            format_string=fmt_str,
            prefix=self.ts_prefix_edit.text(),
            configs_by_size=self.timestamp_configs_by_size.copy()
        )
        
        stamp_settings = StampInsertionSettings(
            enabled=self.group_stamp_insertion.isChecked(),
            stamp_path=self.current_stamp_path,
            configs_by_size=self.stamp_configs_by_size.copy()
        )
        
        security_settings = PDFSecuritySettings(
            enabled=self.security_group.isChecked(),
            master_password=self.security_password.text(),
            allow_print=self.chk_perm_print.isChecked(),
            allow_modify=self.chk_perm_modify.isChecked(),
            allow_copy=self.chk_perm_copy.isChecked(),
            allow_annotate=self.chk_perm_annotate.isChecked(),
            allow_form_fill=self.chk_perm_form.isChecked(),
            allow_assemble=self.chk_perm_assemble.isChecked(),
        )

        return Preset(
            name=name, description=description, 
            text_insertion=text_settings,
            timestamp_insertion=ts_settings,
            stamp_insertion=stamp_settings,
            pdf_security=security_settings
        )

    def _gather_state_and_save_preset(self, name: str, description: str = "") -> None:
        preset = self._build_current_preset_object(name, description)
        overwrite = self.preset_manager.preset_exists(name)
        
        success, msg = self.preset_manager.save_preset(preset, overwrite=overwrite)
        if success:
            self.show_info("Preset Saved", msg)
            self.append_log(f"Preset saved: {name}")
        else:
            self.show_warning("Save Failed", msg)

    def _apply_preset_to_ui(self, name: str) -> None:
        preset, msg = self.preset_manager.load_preset(name)
        if preset is None:
            self.show_warning("Load Failed", msg)
            return
        
        ti = preset.text_insertion
        self.group_text_insertion.setChecked(ti.enabled)
        self.text_input_box.setPlainText(ti.text)
        
        for key, config in ti.configs_by_size.items():
            if key in self.text_configs_by_size:
                self.text_configs_by_size[key] = config.copy()
        
        self.default_text_config = self._determine_default_config(self.text_configs_by_size, DEFAULT_TEXT_CONFIG)

        ts = preset.timestamp_insertion
        self.group_timestamp_insertion.setChecked(ts.enabled)
        self.ts_prefix_edit.setText(ts.prefix)
        
        found_fmt = False
        for btn in self.ts_format_btn_group.buttons():
            if btn.property("fmt_str") == ts.format_string:
                btn.setChecked(True)
                found_fmt = True
                break
        if not found_fmt:
            self.ts_format_btn_group.buttons()[0].setChecked(True)

        for key, config in ts.configs_by_size.items():
            if key in self.timestamp_configs_by_size:
                self.timestamp_configs_by_size[key] = config.copy()
        
        self.default_timestamp_config = self._determine_default_config(self.timestamp_configs_by_size, DEFAULT_TIMESTAMP_CONFIG)

        si = preset.stamp_insertion
        self.group_stamp_insertion.setChecked(si.enabled)
        self.current_stamp_path = si.stamp_path
        self.stamp_path_entry.setText(self.current_stamp_path if self.current_stamp_path else "")
        
        if self.current_stamp_path and os.path.exists(self.current_stamp_path):
            self.btn_stamp_config.setEnabled(True)
        else:
            self.btn_stamp_config.setEnabled(False)

        for key, config in si.configs_by_size.items():
            if key in self.stamp_configs_by_size:
                self.stamp_configs_by_size[key] = config.copy()
        
        self.default_stamp_config = self._determine_default_config(self.stamp_configs_by_size, DEFAULT_STAMP_CONFIG)

        sec = preset.pdf_security
        self.security_group.setChecked(sec.enabled)
        self.security_password.setText(sec.master_password)
        self.chk_perm_print.setChecked(sec.allow_print)
        self.chk_perm_modify.setChecked(sec.allow_modify)
        self.chk_perm_copy.setChecked(sec.allow_copy)
        self.chk_perm_annotate.setChecked(sec.allow_annotate)
        self.chk_perm_form.setChecked(sec.allow_form_fill)
        self.chk_perm_assemble.setChecked(sec.allow_assemble)

        self.render_current_page()

    # =================================================================
    # Logging & Feedback
    # =================================================================
    def append_log(self, msg: str) -> None:
        if self.log_viewer:
            self.log_viewer.append(msg)
        else:
            print(msg)

    def show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def create_progress_dialog(self, title: str, label: str, maximum: int = 0) -> ProgressDialog:
        dialog = ProgressDialog(title, label, maximum, self)
        return dialog

    # =================================================================
    # File & Folder Logic
    # =================================================================
    def pick_input_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            self.input_path_entry.setText(folder)
            self.populate_pdf_tree(folder)
            self.selected_pdf_paths = []
            self.current_file_index = -1
            self.close_current_doc()
            self.update_navigation_ui()

    def pick_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_path_entry.setText(folder)

    def _prune_empty_folders(self, item: QTreeWidgetItem) -> bool:
        full_path = getattr(item, "full_path", "")
        if full_path.lower().endswith(".pdf"):
            return True
        children_to_remove = []
        has_pdfs = False
        for i in range(item.childCount()):
            child = item.child(i)
            if self._prune_empty_folders(child):
                has_pdfs = True
            else:
                children_to_remove.append(child)
        for child in reversed(children_to_remove):
            index = item.indexOfChild(child)
            if index >= 0:
                item.takeChild(index)
        return has_pdfs

    def populate_pdf_tree(self, folder_path: str) -> None:
        self.pdf_tree.clear()
        
        total_items = 0
        for _, dirs, files in os.walk(folder_path):
            total_items += len([f for f in files if f.lower().endswith(".pdf")])
            total_items += len(dirs)

        progress = self.create_progress_dialog(
            "Loading Files", "Scanning folder...", total_items if total_items > 0 else 0
        )
        progress.show()
        QApplication.processEvents()

        icon_provider = QFileIconProvider()
        stats = {"processed": 0, "pdf_count": 0, "valid_pdf_count": 0, "unknown_pdf_count": 0}

        root_item = QTreeWidgetItem([os.path.basename(folder_path) or folder_path, ""])
        root_item.full_path = folder_path
        root_item.setFlags(root_item.flags() | Qt.ItemIsUserCheckable)
        root_item.setCheckState(0, Qt.Unchecked)
        root_item.setIcon(0, icon_provider.icon(QFileInfo(folder_path)))
        root_item.setExpanded(True)
        self.pdf_tree.addTopLevelItem(root_item)

        def recursive_add(parent_item, current_path):
            try:
                entries = os.listdir(current_path)
            except PermissionError:
                return
            
            entries.sort(key=lambda x: (not os.path.isdir(os.path.join(current_path, x)), x.lower()))

            for entry in entries:
                if progress.was_canceled():
                    return
                
                full_entry_path = os.path.join(current_path, entry)
                info = QFileInfo(full_entry_path)

                if os.path.isdir(full_entry_path):
                    item = QTreeWidgetItem([entry, ""])
                    item.full_path = full_entry_path
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.Unchecked)
                    item.setIcon(0, icon_provider.icon(info))
                    item.setExpanded(True)
                    parent_item.addChild(item)
                    
                    stats["processed"] += 1
                    progress.set_value(stats["processed"])
                    progress.set_label_text(f"Scanning: {entry}")
                    QApplication.processEvents()
                    recursive_add(item, full_entry_path)

                elif entry.lower().endswith(".pdf"):
                    stats["pdf_count"] += 1
                    size_str = self._format_size(info.size())
                    item = QTreeWidgetItem([entry, size_str])
                    item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                    item.full_path = full_entry_path
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    progress.set_label_text(f"Checking PDF: {entry}")
                    QApplication.processEvents()
                    
                    is_standard = self._is_pdf_standard_size(full_entry_path)
                    
                    item.setFlags(item.flags() | Qt.ItemIsEnabled)
                    item.setCheckState(0, Qt.Unchecked)
                    
                    if is_standard:
                        stats["valid_pdf_count"] += 1
                    else:
                        stats["unknown_pdf_count"] += 1

                    item.setIcon(0, icon_provider.icon(info))
                    parent_item.addChild(item)
                    stats["processed"] += 1
                    progress.set_value(stats["processed"])
                    QApplication.processEvents()

        recursive_add(root_item, folder_path)
        was_canceled = progress.was_canceled()
        progress.close()
        
        self._prune_empty_folders(root_item)
        self.pdf_tree.expandAll()
        
        self._show_scan_summary(was_canceled, stats, folder_path)

    def _show_scan_summary(self, canceled: bool, stats: Dict[str, int], folder_path: str) -> None:
        valid = stats["valid_pdf_count"]
        unknown = stats["unknown_pdf_count"]
        total = stats["pdf_count"]
        
        if canceled:
            title = "Scan Interrupted"
            body = (
                f"The scanning process was stopped by the user.\n\n"
                f"Partial Results:\n"
                f"• Scanned items: {stats['processed']}\n"
                f"• Found PDF files: {total}"
            )
            self.show_info(title, body)
            return

        if total == 0:
            self.show_warning("No PDFs Found", f"No PDF files were found in:\n{folder_path}\n\nPlease check the folder path and try again.")
            return

        title = "Scan Completed Successfully"
        body = (
            f"Folder scan complete!\n\n"
            f"Location: {folder_path}\n\n"
            f"Summary:\n"
            f"• Total PDFs Found: {total}\n"
            f"• Standard Sizes: {valid}\n"
            f"• Unknown/Custom Sizes: {unknown} (RED)\n\n"
            f"All files are ready to be processed."
        )
        self.show_info(title, body)

    def on_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0:
            return
        self.pdf_tree.blockSignals(True)
        state = item.checkState(0)

        def set_descendants(parent, s):
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.flags() & Qt.ItemIsEnabled:
                    child.setCheckState(0, s)
                    set_descendants(child, s)

        if item.childCount() > 0:
            set_descendants(item, state)

        def update_parents(child):
            parent = child.parent()
            while parent:
                children = [parent.child(i) for i in range(parent.childCount()) 
                            if (parent.child(i).flags() & Qt.ItemIsEnabled)]
                total = len(children)
                checked = sum(ch.checkState(0) == Qt.Checked for ch in children)
                unchecked = sum(ch.checkState(0) == Qt.Unchecked for ch in children)

                if checked == total:
                    parent.setCheckState(0, Qt.Checked)
                elif unchecked == total:
                    parent.setCheckState(0, Qt.Unchecked)
                else:
                    parent.setCheckState(0, Qt.PartiallyChecked)
                child = parent
                parent = parent.parent()

        update_parents(item)
        self.pdf_tree.blockSignals(False)
        
        if not self._suppress_list_update:
            self._refresh_selected_files_list()

    def _show_tree_context_menu(self, position) -> None:
        menu = QMenu()
        has_selection = bool(self.pdf_tree.selectedItems())
        has_items = self.pdf_tree.topLevelItemCount() > 0

        check_action = QAction("Check Selected", self)
        uncheck_action = QAction("Uncheck Selected", self)
        check_action.triggered.connect(lambda: self._batch_set_check_state(Qt.Checked))
        uncheck_action.triggered.connect(lambda: self._batch_set_check_state(Qt.Unchecked))
        check_action.setEnabled(has_selection)
        uncheck_action.setEnabled(has_selection)
        menu.addAction(check_action)
        menu.addAction(uncheck_action)

        menu.addSeparator()

        select_all_action = QAction("Check All", self)
        unselect_all_action = QAction("Uncheck All", self)
        select_all_action.triggered.connect(lambda: self._set_all_check_state(Qt.Checked))
        unselect_all_action.triggered.connect(lambda: self._set_all_check_state(Qt.Unchecked))
        select_all_action.setEnabled(has_items)
        unselect_all_action.setEnabled(has_items)
        menu.addAction(select_all_action)
        menu.addAction(unselect_all_action)

        menu.addSeparator()

        reverse_action = QAction("Reverse Checked", self)
        reverse_action.triggered.connect(self._reverse_selection)
        reverse_action.setEnabled(has_items)
        menu.addAction(reverse_action)

        menu.exec(self.pdf_tree.viewport().mapToGlobal(position))

    def on_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        full_path = getattr(item, "full_path", None)
        if not full_path or not full_path.lower().endswith(".pdf"):
            return

        if item.checkState(0) == Qt.Checked:
            if full_path in self.selected_pdf_paths:
                index = self.selected_pdf_paths.index(full_path)
                if index != self.current_file_index:
                    self.open_pdf_at_index(index)

    def _batch_set_check_state(self, state: Qt.CheckState) -> None:
        items = self.pdf_tree.selectedItems()
        if not items:
            return
        self._suppress_list_update = True
        try:
            for item in items:
                if item.flags() & Qt.ItemIsUserCheckable:
                    if item.checkState(0) != state:
                        item.setCheckState(0, state)
        finally:
            self._suppress_list_update = False
        self._refresh_selected_files_list()

    def _set_all_check_state(self, state: Qt.CheckState) -> None:
        self._suppress_list_update = True
        try:
            def apply_to_leaves(parent):
                for i in range(parent.childCount()):
                    child = parent.child(i)
                    if child.childCount() > 0:
                        apply_to_leaves(child)
                    elif child.flags() & Qt.ItemIsUserCheckable:
                        if child.checkState(0) != state:
                            child.setCheckState(0, state)
            for i in range(self.pdf_tree.topLevelItemCount()):
                apply_to_leaves(self.pdf_tree.topLevelItem(i))
        finally:
            self._suppress_list_update = False
        self._refresh_selected_files_list()

    def _reverse_selection(self) -> None:
        self._suppress_list_update = True
        try:
            def flip_leaves(parent):
                for i in range(parent.childCount()):
                    child = parent.child(i)
                    if child.childCount() > 0:
                        flip_leaves(child)
                    elif child.flags() & Qt.ItemIsUserCheckable:
                        current = child.checkState(0)
                        if current == Qt.Checked:
                            child.setCheckState(0, Qt.Unchecked)
                        elif current == Qt.Unchecked:
                            child.setCheckState(0, Qt.Checked)
            for i in range(self.pdf_tree.topLevelItemCount()):
                flip_leaves(self.pdf_tree.topLevelItem(i))
        finally:
            self._suppress_list_update = False
        self._refresh_selected_files_list()

    def _refresh_selected_files_list(self) -> None:
        new_list = []
        def traverse(item):
            for i in range(item.childCount()):
                child = item.child(i)
                full_path = getattr(child, "full_path", None)
                if full_path and full_path.lower().endswith(".pdf"):
                    if child.checkState(0) == Qt.Checked:
                        new_list.append(full_path)
                traverse(child)

        for i in range(self.pdf_tree.topLevelItemCount()):
            traverse(self.pdf_tree.topLevelItem(i))

        old_list = self.selected_pdf_paths
        old_index = self.current_file_index
        
        self.selected_pdf_paths = new_list

        if not self.selected_pdf_paths:
            self.current_file_index = -1
            self.close_current_doc()
            self.update_navigation_ui()
            return

        if 0 <= old_index < len(old_list):
            old_path = old_list[old_index]
            if old_path in self.selected_pdf_paths:
                self.current_file_index = self.selected_pdf_paths.index(old_path)
                self.update_navigation_ui()
                return

        nearest_index = max(0, min(old_index, len(self.selected_pdf_paths) - 1))
        self.current_file_index = nearest_index
        self.open_pdf_at_index(self.current_file_index)

    # =================================================================
    # Text & Timestamp Config Logic
    # =================================================================
    def open_text_configuration(self) -> None:
        self._text_config_dialog = TextConfigurationDialog(self, self.font_families)
        self._text_config_dialog.set_all_configs(self.text_configs_by_size)
        
        self._text_config_dialog.configApplied.connect(self.on_textconfig_applied)
        if self._text_config_dialog.exec():
            self.text_configs_by_size = {k: v.copy() for k, v in self._text_config_dialog.all_configs.items()}
            self.default_text_config = self._determine_default_config(self.text_configs_by_size, DEFAULT_TEXT_CONFIG)
            
            self.render_current_page()
        self._text_config_dialog = None

    def open_timestamp_configuration(self) -> None:
        self._timestamp_config_dialog = TimestampConfigurationDialog(self, self.font_families)
        self._timestamp_config_dialog.set_all_configs(self.timestamp_configs_by_size)
        
        self._timestamp_config_dialog.configApplied.connect(self.on_timestampconfig_applied)
        if self._timestamp_config_dialog.exec():
            self.timestamp_configs_by_size = {k: v.copy() for k, v in self._timestamp_config_dialog.all_configs.items()}
            self.default_timestamp_config = self._determine_default_config(self.timestamp_configs_by_size, DEFAULT_TIMESTAMP_CONFIG)
            
            self.render_current_page()
        self._timestamp_config_dialog = None

    def _determine_default_config(self, configs: Dict, fallback: Dict) -> Dict:
        key_a4_portrait = ("A4", "portrait")
        if key_a4_portrait in configs:
            return configs[key_a4_portrait].copy()
        elif configs:
            first_key = next(iter(configs))
            return configs[first_key].copy()
        return fallback.copy()

    def on_textconfig_applied(self) -> None:
        if self._text_config_dialog:
            self.text_configs_by_size = {k: v.copy() for k, v in self._text_config_dialog.all_configs.items()}
            self.default_text_config = self._determine_default_config(self.text_configs_by_size, DEFAULT_TEXT_CONFIG)
            self.render_current_page()

    def on_timestampconfig_applied(self) -> None:
        if self._timestamp_config_dialog:
            self.timestamp_configs_by_size = {k: v.copy() for k, v in self._timestamp_config_dialog.all_configs.items()}
            self.default_timestamp_config = self._determine_default_config(self.timestamp_configs_by_size, DEFAULT_TIMESTAMP_CONFIG)
            self.render_current_page()

    def open_stamp_configuration(self) -> None:
        self._stamp_config_dialog = StampConfigurationDialog(self, self.current_stamp_path)
        self._stamp_config_dialog.set_all_configs(self.stamp_configs_by_size)
        self._stamp_config_dialog.configApplied.connect(self.on_stampconfig_applied)
        
        if self._stamp_config_dialog.exec():
            self.stamp_configs_by_size = {k: v.copy() for k, v in self._stamp_config_dialog.all_configs.items()}
            self.default_stamp_config = self._determine_default_config(self.stamp_configs_by_size, DEFAULT_STAMP_CONFIG)
            self.render_current_page()
            
        self._stamp_config_dialog = None

    def on_stampconfig_applied(self) -> None:
        if self._stamp_config_dialog:
            self.stamp_configs_by_size = {k: v.copy() for k, v in self._stamp_config_dialog.all_configs.items()}
            self.default_stamp_config = self._determine_default_config(self.stamp_configs_by_size, DEFAULT_STAMP_CONFIG)
            self.render_current_page()

    def toggle_custom_page_input(self, checked: bool) -> None:
        self.label_custom_pages.setEnabled(checked)
        self.entry_custom_pages.setEnabled(checked)

    def toggle_ts_custom_page_input(self, checked: bool) -> None:
        self.ts_label_custom.setEnabled(checked)
        self.ts_entry_custom.setEnabled(checked)

    def toggle_stamp_custom_page_input(self, checked: bool) -> None:
        self.stamp_label_custom.setEnabled(checked)
        self.stamp_entry_custom.setEnabled(checked)

    def _toggle_password_visibility(self) -> None:
        self._password_visible = not self._password_visible
        if self._password_visible:
            self.security_password.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_password.setText("Hide")
        else:
            self.security_password.setEchoMode(QLineEdit.Password)
            self.btn_toggle_password.setText("Show")

    def on_text_content_changed(self) -> None:
        self.live_input_text = self.text_input_box.toPlainText()
        self._preview_debounce_timer.stop()
        self._preview_debounce_timer.start(DEBOUNCE_DELAY_MS)

    def on_timestamp_content_changed(self) -> None:
        self.live_timestamp_prefix = self.ts_prefix_edit.text()
        btn = self.ts_format_btn_group.checkedButton()
        if btn:
            self.selected_timestamp_format = btn.property("fmt_str")
        self._preview_debounce_timer.stop()
        self._preview_debounce_timer.start(DEBOUNCE_DELAY_MS)

    def select_stamp_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Stamp File",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*.*)"
        )
        
        if not file_path:
            return

        self.current_stamp_path = file_path
        self.stamp_path_entry.setText(file_path)
        self.btn_stamp_config.setEnabled(True) 
        
        if os.path.exists(file_path):
            w_pts, h_pts = self.pdf_ops.get_stamp_dimensions(file_path, 1.0)
            
            if w_pts > 0 and h_pts > 0:
                native_ratio = w_pts / h_pts
                def sync_aspect(cfg: Dict):
                    if cfg.get("maintain_aspect", True):
                        current_w = cfg.get("stamp_width_mm", 50.0)
                        current_h = cfg.get("stamp_height_mm", 50.0)
                        if current_w >= current_h:
                            cfg["stamp_height_mm"] = current_w / native_ratio
                        else:
                            cfg["stamp_width_mm"] = current_h * native_ratio

                for cfg in self.stamp_configs_by_size.values():
                    sync_aspect(cfg)
                
                sync_aspect(self.default_stamp_config)

        self.render_current_page()

    def _on_inputs_edited(self) -> None:
        self._preview_debounce_timer.stop()
        self._preview_debounce_timer.start(DEBOUNCE_DELAY_MS)

    # =================================================================
    # PDF Rendering & Navigation
    # =================================================================
    def close_current_doc(self) -> None:
        if self.current_doc:
            try:
                self.current_doc.close()
            except Exception:
                pass
        self.current_doc = None
        self.current_page_index = 0
        self.current_page_count = 0
        self.preview_widget.clear_preview()
        self.file_status_entry.setText("No file selected")
        self.file_status_entry.setEnabled(False)
        self.page_info_label.setText("Page Info")
        self.page_info_label.setEnabled(False)
        self.active_features_label.setText("Active Features")
        self.active_features_label.setEnabled(False)

    def open_pdf_at_index(self, index: int) -> None:
        if not (0 <= index < len(self.selected_pdf_paths)):
            return

        path = self.selected_pdf_paths[index]
        self.close_current_doc()

        try:
            doc = fitz.open(path)
        except Exception as e:
            self.file_status_entry.setText(f"Error: {e}")
            self.file_status_entry.setEnabled(True)
            return

        self.current_doc = doc
        self.current_file_index = index
        self.current_page_index = 0
        self.current_page_count = len(doc)
        
        self._sync_tree_selection(path)
        self.update_navigation_ui()
        self.render_current_page()

    def _get_page_dim_corrected(self, page: fitz.Page) -> Tuple[float, float]:
        rect = page.rect
        w, h = rect.width, rect.height
        if page.rotation in (90, 270):
            return h, w
        return w, h

    def render_current_page(self) -> None:
        if self.current_doc is None or self.current_page_count == 0:
            return
        if not (0 <= self.current_page_index < self.current_page_count):
            return

        try:
            page = self.current_doc.load_page(self.current_page_index)
            
            text_enabled = self.group_text_insertion.isChecked()
            final_text_content = ""
            if text_enabled:
                if 0 <= self.current_file_index < len(self.selected_pdf_paths):
                    filename = self.selected_pdf_paths[self.current_file_index]
                    final_text_content, _ = self.substitution_engine.apply(self.live_input_text, filename)
                else:
                    final_text_content = self.live_input_text

            should_draw_text = (
                text_enabled and bool(final_text_content) and 
                self._is_page_in_selection(self.current_page_index, self.current_page_count, "text", page)
            )

            ts_enabled = self.group_timestamp_insertion.isChecked()
            timestamp_str = ""
            if ts_enabled:
                timestamp_str = self._build_timestamp_string(self.selected_timestamp_format)

            should_draw_ts = (
                ts_enabled and bool(timestamp_str) and
                self._is_page_in_selection(self.current_page_index, self.current_page_count, "timestamp", page)
            )

            stamp_enabled = self.group_stamp_insertion.isChecked()
            should_draw_stamp = (
                stamp_enabled and 
                self.current_stamp_path and 
                os.path.exists(self.current_stamp_path) and
                self._is_page_in_selection(self.current_page_index, self.current_page_count, "stamp", page)
            )

            if should_draw_text or should_draw_ts or should_draw_stamp:
                doc_copy = fitz.open(stream=self.current_doc.tobytes(), filetype="pdf")
                temp_page = doc_copy.load_page(self.current_page_index)

                if should_draw_text:
                    cfg = self._get_config_for_page_size(temp_page, "text")
                    self._apply_text_to_page(temp_page, final_text_content, cfg)

                if should_draw_ts:
                    cfg = self._get_config_for_page_size(temp_page, "timestamp")
                    self._apply_text_to_page(temp_page, timestamp_str, cfg)

                if should_draw_stamp:
                    cfg = self._get_config_for_page_size(temp_page, "stamp")
                    self._apply_stamp_to_page(temp_page, cfg)
                
                self.preview_widget.set_page(temp_page, zoom=1.5)
                doc_copy.close()
            else:
                self.preview_widget.set_page(page, zoom=1.5)
                
            self._update_page_info()

        except Exception as e:
            print(f"Render Error: {e}")

    def _apply_text_to_page(self, page: fitz.Page, text: str, cfg: Dict) -> None:
        """DEPRECATED: Delegates to Shared PDFOperations logic."""
        self.pdf_ops.apply_text_to_page(page, text, cfg, self.font_families)

    def _apply_stamp_to_page(
        self, 
        page: fitz.Page, 
        cfg: Dict, 
        prepared_stamp: Optional[PreparedStamp] = None
    ) -> None:
        if not self.current_stamp_path or not os.path.exists(self.current_stamp_path):
            return

        page_w, page_h = self._get_page_dim_corrected(page)
        
        pts_per_mm = 72 / 25.4
        w_mm = cfg.get("stamp_width_mm", 50.0)
        h_mm = cfg.get("stamp_height_mm", 50.0)
        stamp_w_pts = w_mm * pts_per_mm
        stamp_h_pts = h_mm * pts_per_mm
        stamp_rotation = cfg.get("stamp_rotation", 0)
        stamp_opacity = cfg.get("stamp_opacity", 100) / 100.0

        if int(stamp_rotation) % 180 == 90:
            visual_w, visual_h = stamp_h_pts, stamp_w_pts
        else:
            visual_w, visual_h = stamp_w_pts, stamp_h_pts

        block_x, block_y = compute_anchor_for_pdf(
            page_w, page_h, visual_w, visual_h, cfg
        )

        if prepared_stamp:
            self.pdf_ops.insert_stamp_bytes(
                page,
                prepared_stamp.get_bytes(stamp_opacity),
                block_x, block_y,
                visual_w, visual_h,
                stamp_rotation
            )
        else:
            self.pdf_ops.insert_stamp(
                page, self.current_stamp_path,
                block_x, block_y,
                visual_w, visual_h,
                stamp_rotation,
                stamp_opacity
            )

    def _on_splitter_moved(self, pos: int, index: int) -> None:
        pass

    # =================================================================
    # Logic Helpers
    # =================================================================
    def _get_formatted_file_name(self, path):
        input_root = self.input_path_entry.text().strip()
        display_text = os.path.basename(path)
        if input_root:
            try:
                if os.path.commonpath([input_root, path]) == os.path.normpath(input_root):
                    display_text = os.path.relpath(path, input_root)
            except (ValueError, Exception):
                pass
        if os.sep in display_text:
            display_text = display_text.replace(os.sep, " / ")
        return display_text

    def _sync_tree_selection(self, path: str) -> None:
        if self._current_bold_item:
            try:
                font = self._current_bold_item.font(0)
                font.setBold(False)
                self._current_bold_item.setFont(0, font)
            except RuntimeError:
                pass
            self._current_bold_item = None

        def search_item(item):
            if getattr(item, "full_path", None) == path:
                return item
            for i in range(item.childCount()):
                found = search_item(item.child(i))
                if found:
                    return found
            return None

        target = None
        for i in range(self.pdf_tree.topLevelItemCount()):
            target = search_item(self.pdf_tree.topLevelItem(i))
            if target:
                break

        if target:
            font = target.font(0)
            font.setBold(True)
            target.setFont(0, font)
            self.pdf_tree.scrollToItem(target)
            self._current_bold_item = target

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.PaletteChange:
            self.repaint()
            if hasattr(self, 'feature_scroll_area'):
                self.feature_scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")
                self.feature_scroll_content.setStyleSheet("#scroll_content_widget { background-color: transparent; }")
                self.feature_scroll_content.style().unpolish(self.feature_scroll_content)
                self.feature_scroll_content.style().polish(self.feature_scroll_content)

        super().changeEvent(event)

    def toggle_theme(self) -> None:
        app = QApplication.instance()
        
        if self._is_dark_theme:
            app.setPalette(get_light_palette())
            self.action_toggle_theme.setText("Dark Mode")
            self._is_dark_theme = False
            self.append_log("Switched to Light Theme")
        else:
            app.setPalette(get_dark_palette())
            self.action_toggle_theme.setText("Light Mode")
            self._is_dark_theme = True
            self.append_log("Switched to Dark Theme")

    def goto_prev_file(self):
        if self.current_file_index > 0:
            self.open_pdf_at_index(self.current_file_index - 1)

    def goto_next_file(self):
        if self.current_file_index < len(self.selected_pdf_paths) - 1:
            self.open_pdf_at_index(self.current_file_index + 1)

    def goto_prev_page(self):
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self.render_current_page()
            self.update_navigation_ui()

    def goto_next_page(self):
        if self.current_page_index < self.current_page_count - 1:
            self.current_page_index += 1
            self.render_current_page()
            self.update_navigation_ui()

    def update_navigation_ui(self):
        total_files = len(self.selected_pdf_paths)
        has_files = total_files > 0
        has_doc = self.current_doc is not None

        self.btn_prev_file.setEnabled(has_files and self.current_file_index > 0)
        self.btn_next_file.setEnabled(has_files and 0 <= self.current_file_index < total_files - 1)

        self.file_input.blockSignals(True)
        
        if has_files:
            self.file_input.setMaximum(total_files)
            self.file_input.setValue(self.current_file_index + 1)
            self.file_input.setSuffix(f" / {total_files}")
            self.file_input.setEnabled(True)

            if 0 <= self.current_file_index < total_files:
                path = self.selected_pdf_paths[self.current_file_index]
                display_text = self._get_formatted_file_name(path)
                
                self.file_status_entry.setText(display_text)
                self.file_status_entry.setToolTip(path)
                self.file_status_entry.setEnabled(True)
        else:
            self.file_input.setMaximum(0)
            self.file_input.setValue(0)
            self.file_input.setSuffix(" / 0")
            self.file_input.setEnabled(False)
            self.file_status_entry.setText("No file selected")
            self.file_status_entry.setToolTip("")
            self.file_status_entry.setEnabled(False)

        self.file_input.blockSignals(False)

        self.btn_prev_page.setEnabled(has_doc and self.current_page_index > 0)
        self.btn_next_page.setEnabled(has_doc and self.current_page_index < self.current_page_count - 1)

        self.page_input.blockSignals(True)
        
        if has_doc:
            self.page_input.setMinimum(1)
            self.page_input.setMaximum(self.current_page_count)
            self.page_input.setValue(self.current_page_index + 1)
            self.page_input.setSuffix(f" / {self.current_page_count}")
            self.page_input.setEnabled(True)
        else:
            self.page_input.setMinimum(0)
            self.page_input.setMaximum(0)
            self.page_input.setValue(0)
            self.page_input.setSuffix(" / 0")
            self.page_input.setEnabled(False)
            
        self.page_input.blockSignals(False)

        self._update_page_info()
    
    def _update_page_info(self) -> None:
        if self.current_doc is None or self.current_page_count == 0:
            self.page_info_label.setText("Page Info")
            self.page_info_label.setEnabled(False)
            self.active_features_label.setText("Active Features")
            self.active_features_label.setEnabled(False)
            return
        
        page = None
        try:
            page = self.current_doc.load_page(self.current_page_index)
            w, h = self._get_page_dim_corrected(page)
            rotation = page.rotation
            
            key = detect_paper_key(w, h)
            w_mm = w * 25.4 / 72
            h_mm = h * 25.4 / 72
            dim_str = f"{w_mm:.0f}x{h_mm:.0f} mm"
            
            if key:
                name = KEY_TO_LABEL.get(key, "Unknown")
                if "(" in name:
                    name = name.split("(")[0].strip()
                self.page_info_label.setText(f"{name} ({dim_str}, Rot: {rotation}°)")
                self.page_info_label.setEnabled(True)
            else:
                mode = "Portrait" if h >= w else "Landscape"
                self.page_info_label.setText(f"Unknown - {mode} ({dim_str}, Rot: {rotation}°)")
                self.page_info_label.setEnabled(True)
        except Exception:
            self.page_info_label.setText("Error")
            self.page_info_label.setEnabled(True)

        features = []
        def format_feature(name, is_on):
            symbol = "✓" if is_on else "✗"
            color = "green" if is_on else "red"
            return f"{name} <span style='color:{color}; font-weight:bold;'>{symbol}</span>"

        text_on = False
        if self.group_text_insertion.isChecked():
            text_on = self._is_page_in_selection(self.current_page_index, self.current_page_count, "text", page)
        features.append(format_feature("Text", text_on))
        
        ts_on = False
        if self.group_timestamp_insertion.isChecked():
            ts_on = self._is_page_in_selection(self.current_page_index, self.current_page_count, "timestamp", page)
        features.append(format_feature("Time", ts_on))
        
        stamp_on = False
        if self.group_stamp_insertion.isChecked():
            valid_file = bool(self.current_stamp_path and os.path.exists(self.current_stamp_path))
            stamp_on = valid_file and self._is_page_in_selection(self.current_page_index, self.current_page_count, "stamp", page)
        features.append(format_feature("Stamp", stamp_on))
        
        self.active_features_label.setText(" | ".join(features))
        self.active_features_label.setEnabled(True)
    
    def on_page_input_changed(self, value: int) -> None:
        clamped = max(1, min(value, self.current_page_count))
        if clamped != value:
            self.page_input.blockSignals(True)
            self.page_input.setValue(clamped)
            self.page_input.blockSignals(False)
        
        new_index = clamped - 1
        if 0 <= new_index < self.current_page_count and new_index != self.current_page_index:
            self.current_page_index = new_index
            self.render_current_page()
            self.update_navigation_ui()

    def on_file_input_changed(self, value: int) -> None:
        total_files = len(self.selected_pdf_paths)
        if total_files == 0:
            return
            
        clamped = max(1, min(value, total_files))
        if clamped != value:
             self.file_input.blockSignals(True)
             self.file_input.setValue(clamped)
             self.file_input.blockSignals(False)
        
        new_index = clamped - 1
        if new_index != self.current_file_index:
            self.open_pdf_at_index(new_index)

    def _is_pdf_standard_size(self, path: str) -> bool:
        try:
            with fitz.open(path) as doc:
                page = doc.load_page(0)
                w, h = self._get_page_dim_corrected(page)
                return detect_paper_key(w, h) is not None
        except Exception:
            return False

    def _get_config_for_page_size(self, page: fitz.Page, config_type: str) -> Dict:
        w, h = self._get_page_dim_corrected(page)
        key = detect_paper_key(w, h)
        
        if key is None:
            mode = "portrait" if h >= w else "landscape"
            key = ("Unknown", mode)

        if config_type == "text":
            target_map = self.text_configs_by_size
            default = self.default_text_config
        elif config_type == "timestamp":
            target_map = self.timestamp_configs_by_size
            default = self.default_timestamp_config
        elif config_type == "stamp":
            target_map = self.stamp_configs_by_size
            default = self.default_stamp_config
        else:
            target_map = self.text_configs_by_size
            default = self.default_text_config

        if key and key in target_map:
            return target_map[key]
        return default

    def _select_font_file(self, cfg: Dict) -> Optional[str]:
        # Helper used by DEPRECATED methods if needed, but new logic handles this internally
        family = cfg.get("font_family")
        bold = cfg.get("bold", False)
        italic = cfg.get("italic", False)
        fam_map = self.font_families.get(family)
        if not fam_map: return None

        if bold and italic:
            return fam_map.get("bolditalic") or fam_map.get("bold") or fam_map.get("italic") or fam_map.get("regular")
        if bold:
            return fam_map.get("bold") or fam_map.get("regular")
        if italic:
            return fam_map.get("italic") or fam_map.get("regular")
        return fam_map.get("regular")

    def _parse_custom_pages(self, input_str: str, total_pages: int) -> Set[int]:
        pages = set()
        for part in input_str.split(","):
            part = part.strip()
            if not part: continue
            if "-" in part:
                try:
                    start, end = map(int, part.split("-", 1))
                    if start > end: start, end = end, start
                    for p in range(start, end + 1):
                        if 1 <= p <= total_pages: pages.add(p)
                except ValueError: continue
            else:
                try:
                    p = int(part)
                    if 1 <= p <= total_pages: pages.add(p)
                except ValueError: continue
        return pages

    def _is_page_in_selection(self, idx_zero_based: int, total_pages: int, feature: str, page: fitz.Page = None) -> bool:
        pno = idx_zero_based + 1
        mode = "all"
        custom_str = ""
        
        if page is not None:
            cfg = self._get_config_for_page_size(page, feature)
            mode = cfg.get("page_selection", "all")
            custom_str = cfg.get("custom_pages", "")
        else:
            key = ("A4", "portrait")
            if feature == "text":
                cfg = self.text_configs_by_size.get(key, self.default_text_config)
            elif feature == "timestamp":
                cfg = self.timestamp_configs_by_size.get(key, self.default_timestamp_config)
            elif feature == "stamp":
                cfg = self.stamp_configs_by_size.get(key, self.default_stamp_config)
            else:
                cfg = {}
            mode = cfg.get("page_selection", "all")
            custom_str = cfg.get("custom_pages", "")
        
        if mode == "all": return True
        if mode == "first": return pno == 1
        if mode == "last": return pno == total_pages
        if mode == "odd": return (pno % 2) == 1
        if mode == "even": return (pno % 2) == 0
        if mode == "custom":
            return pno in self._parse_custom_pages(custom_str, total_pages)

        return False
    
    def _format_size(self, size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024: return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    def _build_timestamp_string(self, fmt: str) -> str:
        dt = datetime.now()
        date_part = dt.strftime(fmt)
        prefix = self.ts_prefix_edit.text()
        
        if prefix:
            return f"{prefix} {date_part}"
        return date_part

    # =================================================================
    # Batch Processing
    # =================================================================
    def _get_existing_output_files(self, out_dir: str) -> List[Tuple[str, str]]:
        """Check which output files already exist.
        Returns list of tuples: (source_path, destination_path) for files that exist."""
        existing = []
        input_root = self.input_path_entry.text().strip()
        
        for pdf_path in self.selected_pdf_paths:
            filename = os.path.basename(pdf_path)
            if input_root:
                rel_path = os.path.relpath(pdf_path, input_root)
                save_path = os.path.join(out_dir, rel_path)
            else:
                save_path = os.path.join(out_dir, filename)
            
            if os.path.exists(save_path):
                existing.append((pdf_path, save_path))
        
        return existing

    def _show_overwrite_warning(self, existing_files: List[Tuple[str, str]]) -> bool:
        """Show warning dialog for existing files with scrollable list. Returns True if user wants to proceed."""
        count = len(existing_files)
        
        # Build the dialog
        dialog = QDialog(self)
        if count == 1:
            dialog.setWindowTitle("File Already Exists")
            message = "The following file already exists in the output folder and will be overwritten:"
        else:
            dialog.setWindowTitle("Files Already Exist")
            message = f"The following {count} files already exist in the output folder and will be overwritten:"
        
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(300)
        
        layout = QVBoxLayout(dialog)
        
        # Message label
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)
        
        # Scrollable file list
        from PySide6.QtWidgets import QListWidget, QListWidgetItem
        file_list = QListWidget()
        file_list.setAlternatingRowColors(True)
        
        for _, dest_path in existing_files:
            item = QListWidgetItem(os.path.basename(dest_path))
            item.setToolTip(dest_path)  # Show full path on hover
            file_list.addItem(item)
        
        layout.addWidget(file_list, 1)  # stretch factor 1 to expand
        
        # Question label
        question_label = QLabel("Do you want to continue and overwrite these files?")
        layout.addWidget(question_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        no_btn = QPushButton("No")
        no_btn.setDefault(True)
        no_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(no_btn)
        
        yes_btn = QPushButton("Yes, Overwrite")
        yes_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(yes_btn)
        
        layout.addLayout(btn_layout)
        
        return dialog.exec() == QDialog.Accepted

    def process_all_pdfs(self) -> None:
        if not self.selected_pdf_paths:
            self.show_warning("No Files", "Please select PDF files to process.")
            return

        out_dir = self.output_path_entry.text().strip()
        if not out_dir:
            self.show_warning("No Output", "Please select an output folder.")
            return
        if not os.path.isdir(out_dir):
            self.show_error("Invalid Output", "The output folder does not exist.")
            return

        # Check for existing files that would be overwritten
        existing_files = self._get_existing_output_files(out_dir)
        if existing_files:
            if not self._show_overwrite_warning(existing_files):
                return  # User chose not to overwrite

        security_enabled = self.security_group.isChecked()
        master_password = self.security_password.text()
        
        if security_enabled and not master_password:
            self.show_warning("Password Required", "You have enabled PDF Security but did not provide a master password.\n\nPlease enter a password or disable security.")
            return

        features = {
            "Text Insertion": self.group_text_insertion.isChecked(),
            "Timestamp Insertion": self.group_timestamp_insertion.isChecked(),
            "Stamp Insertion": self.group_stamp_insertion.isChecked(),
            "PDF Security": security_enabled
        }

        if not any(features.values()):
            self.show_warning("No Features", "Enable at least one feature.")
            return

        # Prepare Data Payloads (Deep Copy to prevent thread race conditions)
        
        text_payload = {
            "raw_text": self.live_input_text,
            "configs": copy.deepcopy(self.text_configs_by_size),
            "default": self.default_text_config.copy()
        }

        timestamp_payload = {
            "full_string": self._build_timestamp_string(self.selected_timestamp_format),
            "configs": copy.deepcopy(self.timestamp_configs_by_size),
            "default": self.default_timestamp_config.copy()
        }

        stamp_payload = {
            "path": self.current_stamp_path,
            "configs": copy.deepcopy(self.stamp_configs_by_size),
            "default": self.default_stamp_config.copy()
        }

        perms = 0
        if self.chk_perm_print.isChecked(): perms |= (fitz.PDF_PERM_PRINT | fitz.PDF_PERM_PRINT_HQ)
        if self.chk_perm_modify.isChecked(): perms |= fitz.PDF_PERM_MODIFY
        if self.chk_perm_copy.isChecked(): perms |= fitz.PDF_PERM_COPY
        if self.chk_perm_annotate.isChecked(): perms |= fitz.PDF_PERM_ANNOTATE
        if self.chk_perm_form.isChecked(): perms |= fitz.PDF_PERM_FORM
        if self.chk_perm_assemble.isChecked(): perms |= fitz.PDF_PERM_ASSEMBLE

        security_payload = {
            "password": master_password,
            "permissions": perms
        }

        # Confirmation
        summary = "\n".join([f"• {k}" for k, v in features.items() if v]) or "None"
        reply = QMessageBox.question(
            self, "Confirm Processing",
            f"Process {len(self.selected_pdf_paths)} files?\n\nFeatures:\n{summary}\n\nOutput:\n{out_dir}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        # Initialize Progress Dialog
        self._progress_dialog = self.create_progress_dialog(
            "Processing", "Initializing...", len(self.selected_pdf_paths)
        )
        self._progress_dialog.show()
        
        # Start Thread
        self._worker_thread = PDFProcessingThread(
            files=self.selected_pdf_paths,
            output_dir=out_dir,
            input_root=self.input_path_entry.text().strip(),
            features=features,
            security_settings=security_payload,
            text_settings=text_payload,
            timestamp_settings=timestamp_payload,
            stamp_settings=stamp_payload,
            pdf_ops_instance=self.pdf_ops,
            substitution_engine=self.substitution_engine,
            font_families=self.font_families # Passing the font map
        )

        # Connect Signals
        self._worker_thread.progress_update.connect(self._on_worker_progress)
        self._worker_thread.log_message.connect(self.append_log)
        self._worker_thread.finished_processing.connect(self._on_worker_finished)
        
        # Connect Cancel Button
        # Disconnect old connections first just in case
        try: self._progress_dialog.cancel_btn.clicked.disconnect() 
        except: pass
        
        self._progress_dialog.cancel_btn.clicked.connect(self._worker_thread.requestInterruption)
        self._progress_dialog.cancel_btn.clicked.connect(lambda: self._progress_dialog.set_label_text("Stopping..."))

        self._worker_thread.start()

    # --- Worker Slots ---
    def _on_worker_progress(self, current_idx, message):
        if self._progress_dialog:
            self._progress_dialog.set_value(current_idx)
            self._progress_dialog.set_label_text(message)

    def _on_worker_finished(self, canceled, success, errors, error_list):
        if self._progress_dialog:
            self._progress_dialog.close()
        
        self._show_processing_result(canceled, success, errors, error_list)
        self._worker_thread = None 

    def _show_processing_result(self, canceled: bool, success: int, errors: int, error_list: List[str]) -> None:
        if canceled:
            self.show_info("Cancelled", f"Stopped by user.\nSuccess: {success}, Errors: {errors}")
        elif errors == 0:
            self.show_info("Complete", f"Successfully processed {success} files.")
        else:
            detail = "\n".join(error_list[:5])
            if len(error_list) > 5: detail += f"\n...and {len(error_list) - 5} more."
            self.show_warning("Completed with Errors", f"Success: {success}\nErrors: {errors}\n\n{detail}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("fusion")
    # app.setPalette(get_light_palette())
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())