"""MainWindow shell: init, state, UI assembly, signal wiring."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import fitz

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter, QTabWidget,
    QTreeWidgetItem,
)
from PySide6.QtCore import Qt, QTimer, QEvent

from core.constants import (
    APP_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, SPLITTER_INITIAL_SIZES,
    LEFT_PANEL_MIN_WIDTH, RIGHT_PANEL_MIN_WIDTH,
    TIMESTAMP_FORMATS, TIMESTAMP_UPDATE_INTERVAL_MS, DEBOUNCE_DELAY_MS,
    DEFAULT_TEXT_CONFIG, DEFAULT_TIMESTAMP_CONFIG, DEFAULT_STAMP_CONFIG,
    ALL_PAPER_KEYS, get_font_families,
    PREVIEW_ZOOM_MIN, PREVIEW_ZOOM_MAX, PREVIEW_ZOOM_STEP, PREVIEW_ZOOM_DEFAULT,
)
from core.pdf_operations import PDFOperations
from core.substitution_engine import SubstitutionEngine
from core.substitution_loader import load_substitution_definitions
from core.preset_manager import PresetManager
from core.utils import resolve_path
from core.themes import get_light_palette, get_dark_palette

# UI module imports
from ui.toolbar import setup_toolbar
from ui.preview_panel import setup_preview_tab
from ui.log_panel import setup_log_tab, append_log as _append_log, show_info, show_warning, show_error
from ui.files_panel import setup_files_tab, pick_input_folder, pick_output_folder, on_tree_item_changed
from ui.features_panel import (
    setup_features_tab, on_text_content_changed, on_timestamp_content_changed,
    update_timestamp_labels,
)
from ui.navigation import (
    goto_prev_file, goto_next_file, goto_prev_page, goto_next_page,
    update_navigation_ui as _update_navigation_ui,
    on_page_input_changed, on_file_input_changed,
)
from ui.pdf_viewer import (
    close_current_doc as _close_current_doc,
    open_pdf_at_index as _open_pdf_at_index,
    render_current_page as _render_current_page,
)
from ui.processing import process_all_pdfs
from ui.preset_actions import (
    load_preset as _load_preset, save_preset as _save_preset,
    manage_presets as _manage_presets, load_default_preset_on_startup,
    open_text_configuration, open_timestamp_configuration, open_stamp_configuration,
)
from ui.config_manager import init_config


class MainWindow(QMainWindow):
    """Main application window. Delegates to focused ui/ modules."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(APP_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

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

        self._suppress_list_update: bool = False

        self.pdf_ops = PDFOperations()
        self._substitution_definitions = load_substitution_definitions()
        self.substitution_engine = SubstitutionEngine(definitions=self._substitution_definitions)
        self.preset_manager = PresetManager()
        self.font_families: Dict[str, Dict[str, str]] = get_font_families()
        self._is_dark_theme: bool = False

        self._user_zoom: float = PREVIEW_ZOOM_DEFAULT
        self._show_features: bool = True

        self._worker_thread = None
        self._progress_dialog = None

        # Configuration Handling
        self.config_path = resolve_path("config.ini")
        init_config(self)

        self._preview_debounce_timer = QTimer()
        self._preview_debounce_timer.setSingleShot(True)
        self._preview_debounce_timer.timeout.connect(self.render_current_page)

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
        self._text_config_dialog = None

        # -- Timestamp Config --
        self.default_timestamp_config = DEFAULT_TIMESTAMP_CONFIG.copy()
        if self.default_timestamp_config.get("font_family") not in self.font_families:
            self.default_timestamp_config["font_family"] = default_family
        self.default_timestamp_config["page_selection"] = "all"
        self.default_timestamp_config["custom_pages"] = ""
        self.timestamp_configs_by_size: Dict[Tuple[str, str], Dict] = {
            key: self.default_timestamp_config.copy() for key in ALL_PAPER_KEYS
        }
        self._timestamp_config_dialog = None

        # -- Stamp Config --
        self.default_stamp_config = DEFAULT_STAMP_CONFIG.copy()
        self.default_stamp_config["page_selection"] = "all"
        self.default_stamp_config["custom_pages"] = ""
        self.stamp_configs_by_size: Dict[Tuple[str, str], Dict] = {
            key: self.default_stamp_config.copy() for key in ALL_PAPER_KEYS
        }
        self.current_stamp_path: str = ""
        self._stamp_config_dialog = None

        # -----------------------------------------------------------------
        # 3. UI Construction
        # -----------------------------------------------------------------
        self.setMenuBar(None)
        setup_toolbar(self)
        self._setup_ui()
        self._connect_signals()

        self.update_navigation_ui()

        # -----------------------------------------------------------------
        # 4. Live Label Updates
        # -----------------------------------------------------------------
        self._timestamp_label_timer = QTimer(self)
        self._timestamp_label_timer.timeout.connect(lambda: update_timestamp_labels(self))
        self._timestamp_label_timer.start(TIMESTAMP_UPDATE_INTERVAL_MS)

        # -----------------------------------------------------------------
        # 5. Startup Logic
        # -----------------------------------------------------------------
        load_default_preset_on_startup(self)

    # =================================================================
    # UI Setup
    # =================================================================
    def _setup_ui(self) -> None:
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        self.setCentralWidget(central_widget)

        self.main_splitter = QSplitter(Qt.Horizontal)
        central_layout.addWidget(self.main_splitter)

        self._init_left_panel()
        self._init_right_panel()

        self.main_splitter.setSizes(SPLITTER_INITIAL_SIZES)

    def _init_left_panel(self) -> None:
        container = QWidget()
        container.setMinimumWidth(LEFT_PANEL_MIN_WIDTH)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.left_tabs = QTabWidget()
        layout.addWidget(self.left_tabs)

        setup_preview_tab(self)
        setup_log_tab(self)

        self.main_splitter.addWidget(container)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setCollapsible(0, False)

    def _init_right_panel(self) -> None:
        container = QWidget()
        container.setMinimumWidth(RIGHT_PANEL_MIN_WIDTH)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.right_tabs = QTabWidget()
        layout.addWidget(self.right_tabs)

        setup_files_tab(self)
        setup_features_tab(self)

        self.main_splitter.addWidget(container)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.setCollapsible(1, False)

    # =================================================================
    # Signal Wiring
    # =================================================================
    def _connect_signals(self) -> None:
        self.btn_prev_file.clicked.connect(lambda: goto_prev_file(self))
        self.btn_next_file.clicked.connect(lambda: goto_next_file(self))
        self.file_input.valueChanged.connect(lambda v: on_file_input_changed(self, v))

        self.btn_prev_page.clicked.connect(lambda: goto_prev_page(self))
        self.btn_next_page.clicked.connect(lambda: goto_next_page(self))
        self.page_input.valueChanged.connect(lambda v: on_page_input_changed(self, v))

        self.btn_zoom_in.clicked.connect(self._zoom_in)
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        self.btn_zoom_fit.clicked.connect(self._zoom_fit)
        self.btn_toggle_overlay.clicked.connect(self._toggle_overlay)
        self.preview_scroll.set_zoom_callback(self._on_scroll_zoom)

        self.btn_browse_input.clicked.connect(lambda: pick_input_folder(self))
        self.btn_browse_output.clicked.connect(lambda: pick_output_folder(self))
        self.pdf_tree.itemChanged.connect(lambda item, col: on_tree_item_changed(self, item, col))

        self.btn_process_all.clicked.connect(lambda: process_all_pdfs(self))

        self.text_input_box.textChanged.connect(lambda: on_text_content_changed(self))
        self.btn_text_config.clicked.connect(lambda: open_text_configuration(self))
        self.group_text_insertion.toggled.connect(self.render_current_page)

        self.group_timestamp_insertion.toggled.connect(self.render_current_page)
        self.ts_prefix_edit.textChanged.connect(lambda: on_timestamp_content_changed(self))
        self.ts_format_btn_group.buttonClicked.connect(lambda: on_timestamp_content_changed(self))
        self.btn_timestamp_config.clicked.connect(lambda: open_timestamp_configuration(self))

        self.group_stamp_insertion.toggled.connect(self.render_current_page)
        self.btn_stamp_config.clicked.connect(lambda: open_stamp_configuration(self))

    # =================================================================
    # Delegate Methods
    # =================================================================
    def close_current_doc(self) -> None:
        _close_current_doc(self)

    def open_pdf_at_index(self, index: int) -> None:
        _open_pdf_at_index(self, index)

    def render_current_page(self) -> None:
        _render_current_page(self)

    def update_navigation_ui(self) -> None:
        _update_navigation_ui(self)

    def append_log(self, msg: str) -> None:
        _append_log(self, msg)

    def show_info(self, title: str, message: str) -> None:
        show_info(self, title, message)

    def show_warning(self, title: str, message: str) -> None:
        show_warning(self, title, message)

    def show_error(self, title: str, message: str) -> None:
        show_error(self, title, message)

    def load_preset(self) -> None:
        _load_preset(self)

    def save_preset(self) -> None:
        _save_preset(self)

    def manage_presets(self) -> None:
        _manage_presets(self)

    def manage_substitutions(self) -> None:
        from dialogs.substitution_dialog import ManageSubstitutionsDialog

        dlg = ManageSubstitutionsDialog(self._substitution_definitions, parent=self)
        dlg.exec()
        if dlg.was_saved():
            self._substitution_definitions = dlg.get_definitions()
            self.substitution_engine.update_definitions(self._substitution_definitions)
            self.btn_substitution_picker.update_definitions(self._substitution_definitions)
            self.render_current_page()

    # =================================================================
    # Zoom / Toggle
    # =================================================================
    def _zoom_in(self) -> None:
        self._user_zoom = min(self._user_zoom + PREVIEW_ZOOM_STEP, PREVIEW_ZOOM_MAX)
        self._apply_zoom()

    def _zoom_out(self) -> None:
        self._user_zoom = max(self._user_zoom - PREVIEW_ZOOM_STEP, PREVIEW_ZOOM_MIN)
        self._apply_zoom()

    def _zoom_fit(self) -> None:
        self._user_zoom = PREVIEW_ZOOM_DEFAULT
        self._apply_zoom()

    def _on_scroll_zoom(self, delta: int, mouse_pos) -> None:
        old_zoom = self._user_zoom
        if delta > 0:
            self._user_zoom = min(self._user_zoom + PREVIEW_ZOOM_STEP, PREVIEW_ZOOM_MAX)
        else:
            self._user_zoom = max(self._user_zoom - PREVIEW_ZOOM_STEP, PREVIEW_ZOOM_MIN)
        if self._user_zoom == old_zoom:
            return

        # Anchor point: document coordinate under the mouse before zoom
        sa = self.preview_scroll
        hbar = sa.horizontalScrollBar()
        vbar = sa.verticalScrollBar()
        doc_x = hbar.value() + mouse_pos.x()
        doc_y = vbar.value() + mouse_pos.y()

        ratio = self._user_zoom / old_zoom

        self._apply_zoom()

        # After zoom the widget resized — adjust scrollbars so the same
        # document point stays under the mouse cursor.
        hbar.setValue(int(doc_x * ratio) - mouse_pos.x())
        vbar.setValue(int(doc_y * ratio) - mouse_pos.y())

    def _apply_zoom(self) -> None:
        pct = int(round(self._user_zoom * 100))
        self.zoom_label.setText(f"{pct}%")
        self.preview_widget.set_user_zoom(self._user_zoom, render=True)

    def _toggle_overlay(self) -> None:
        self._show_features = not self._show_features
        self.btn_toggle_overlay.setText("Features" if not self._show_features else "Original")
        self.render_current_page()

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

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.PaletteChange:
            self.repaint()
            if hasattr(self, "feature_scroll_area"):
                self.feature_scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")
                self.feature_scroll_content.setStyleSheet(
                    "#scroll_content_widget { background-color: transparent; }"
                )
                self.feature_scroll_content.style().unpolish(self.feature_scroll_content)
                self.feature_scroll_content.style().polish(self.feature_scroll_content)

        super().changeEvent(event)
