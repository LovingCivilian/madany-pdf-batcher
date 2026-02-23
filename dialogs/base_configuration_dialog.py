from typing import Dict, Tuple, Optional, Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QListWidget, QListWidgetItem, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGroupBox, QSlider, QSpinBox,
    QDoubleSpinBox, QWidget, QLayout, QMessageBox, QButtonGroup, 
    QRadioButton, QGridLayout, QLineEdit
)

import fitz

from core.constants import ALL_PAPER_KEYS, KEY_TO_LABEL, PAPER_DEFINITIONS
from core.pdf_operations import PDFOperations
from widgets.preview_widget import PDFPreviewWidget

class BaseConfigurationDialog(QDialog):
    """
    Base class for configuration dialogs.
    Handles:
    - Left Panel (Paper List)
    - Center Panel (Preview Canvas foundation)
    - Bottom Buttons (Apply/OK/Cancel)
    - Common State Management (Configs, Current Key)
    - Shared UI Helpers (Sliders, Overlay Guides)
    """
    
    configApplied = Signal()

    def __init__(self, parent: Optional[QWidget] = None, title: str = "Configuration"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1250, 750)

        self.pdf_ops = PDFOperations()

        # Config storage
        self.all_configs: Dict[Tuple[str, str], Dict] = {}
        self._current_key: Optional[Tuple[str, str]] = None
        self.current_config: Dict = {}

        # UI References (to be set by init methods)
        self.paper_list: Optional[QListWidget] = None
        self.preview_canvas: Optional[QLabel] = None
        self.position_btn_group: Optional[QButtonGroup] = None
        
        # Page Selection UI References
        self.page_mode_group: Optional[QButtonGroup] = None
        self.custom_pages_input: Optional[QLineEdit] = None
        self.custom_pages_label: Optional[QLabel] = None
        
        # Margin controls (Subclasses must assign these if they use the default margin logic)
        self.h_margin_slider: Optional[QSlider] = None
        self.h_margin_spin: Optional[QSpinBox] = None
        self.h_margin_label: Optional[QLabel] = None
        self.v_margin_slider: Optional[QSlider] = None
        self.v_margin_spin: Optional[QSpinBox] = None
        self.v_margin_label: Optional[QLabel] = None

    def _init_base_ui(self):
        """Call this from subclass __init__ to setup the skeleton."""
        root_layout = QVBoxLayout(self)

        # Main Layout (Left List | Center Preview | Right Settings)
        main_layout = QHBoxLayout()
        root_layout.addLayout(main_layout, stretch=1)

        self._init_left_panel(main_layout)
        self._init_center_preview(main_layout)
        self._init_right_settings(main_layout)  # Abstract-ish

        # Bottom Buttons
        self._init_bottom_buttons(root_layout)

    # ==============================================================
    # Core UI Sections
    # ==============================================================

    def _init_left_panel(self, parent_layout: QHBoxLayout) -> None:
        self.paper_list = QListWidget()
        for key in ALL_PAPER_KEYS:
            label = KEY_TO_LABEL[key]
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self.paper_list.addItem(item)

        self.paper_list.setCurrentRow(0)
        self.paper_list.currentItemChanged.connect(self.on_paper_changed)

        group = QGroupBox("Paper Sizes")
        layout = QVBoxLayout(group)
        layout.addWidget(self.paper_list)
        group.setFixedWidth(200)

        parent_layout.addWidget(group, stretch=0)

    def _init_center_preview(self, parent_layout: QHBoxLayout) -> None:
        group = QGroupBox("Preview")
        layout = QVBoxLayout(group)

        self.preview_canvas = PDFPreviewWidget()
        layout.addWidget(self.preview_canvas)
        parent_layout.addWidget(group, stretch=1)

    def _init_right_settings(self, parent_layout: QHBoxLayout) -> None:
        """Override in subclass to add specific settings controls."""
        pass
        
    def _init_page_selection_section(self, layout: QVBoxLayout) -> None:
        """Shared Page Selection UI for the settings panel."""
        group = QGroupBox("Page Selection")
        vbox = QVBoxLayout(group)
        
        self.page_mode_group = QButtonGroup(self)
        
        modes = [
            ("All pages", "all"),
            ("First page only", "first"),
            ("Last page only", "last"),
            ("Odd pages", "odd"),
            ("Even pages", "even"),
            ("Custom pages", "custom"),
        ]
        
        grid = QGridLayout()
        for i, (label, key) in enumerate(modes):
            rb = QRadioButton(label)
            rb.setProperty("mode_key", key)
            self.page_mode_group.addButton(rb)
            grid.addWidget(rb, i // 2, i % 2)
            
            if key == "all":
                rb.setChecked(True)
            
            if key == "custom":
                rb.toggled.connect(self._toggle_custom_input)

        vbox.addLayout(grid)
        
        # Custom input
        custom_row = QHBoxLayout()
        self.custom_pages_label = QLabel("Pages (e.g. 1-3, 5):")
        self.custom_pages_input = QLineEdit()
        self.custom_pages_label.setEnabled(False)
        self.custom_pages_input.setEnabled(False)
        
        custom_row.addWidget(self.custom_pages_label)
        custom_row.addWidget(self.custom_pages_input)
        vbox.addLayout(custom_row)
        
        layout.addWidget(group)

    def _toggle_custom_input(self, checked: bool) -> None:
        if self.custom_pages_label and self.custom_pages_input:
            self.custom_pages_label.setEnabled(checked)
            self.custom_pages_input.setEnabled(checked)

    def _init_bottom_buttons(self, root_layout: QVBoxLayout) -> None:
        layout = QHBoxLayout()
        layout.addStretch()

        self.btn_apply = QPushButton("Apply")
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")

        self.btn_apply.clicked.connect(self.on_apply_clicked)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        layout.addWidget(self.btn_apply)
        layout.addWidget(self.btn_ok)
        layout.addWidget(self.btn_cancel)

        root_layout.addLayout(layout)

    # ==============================================================
    # Shared Helpers
    # ==============================================================

    def _create_styled_slider_row(self, label_text: str, slider: QSlider, spin: QWidget, 
                                min_val: float, max_val: float, def_val: float, 
                                spin_width: int = 50) -> Tuple[QHBoxLayout, QLabel]:
        """
        Configures the slider/spin pair (ranges, bindings) AND creates a consistent layout row.
        Returns (row_layout, label_widget) so the label can be stored if needed (e.g. for disabling).
        """
        # 1. Setup Ranges & Logic
        is_double = isinstance(spin, QDoubleSpinBox)
        
        if is_double:
            factor = 10.0
            slider.setRange(int(min_val * factor), int(max_val * factor))
            slider.setValue(int(def_val * factor))
            spin.setRange(min_val, max_val)
            spin.setValue(def_val)
            spin.setSingleStep(1.0)
        else:
            slider.setRange(int(min_val), int(max_val))
            slider.setValue(int(def_val))
            spin.setRange(int(min_val), int(max_val))
            spin.setValue(int(def_val))
            
        self._bind_slider_spin(slider, spin)

        # 2. Create Layout
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setMinimumWidth(100)
        spin.setFixedWidth(spin_width)
        
        row.addWidget(label)
        row.addWidget(slider, stretch=1)
        row.addWidget(spin)
        
        return row, label

    def _bind_slider_spin(self, slider: QSlider, spin: QWidget) -> None:
        """Binds signals between slider and spinbox and connects to render_preview."""
        is_double = isinstance(spin, QDoubleSpinBox)
        factor = 10.0 if is_double else 1.0

        def slider_changed(v):
            spin.blockSignals(True)
            val = v / factor if is_double else v
            spin.setValue(val)
            spin.blockSignals(False)
            self.render_preview()

        def spin_changed(v):
            slider.blockSignals(True)
            val = int(v * factor) if is_double else int(v)
            slider.setValue(val)
            slider.blockSignals(False)
            self.render_preview()

        slider.valueChanged.connect(slider_changed)
        spin.valueChanged.connect(spin_changed)

    def update_margin_controls_state(self) -> None:
        """
        Enables/disables margin controls based on position.
        Requires subclasses to have set self.h_margin_slider, etc.
        """
        if not self.position_btn_group:
            return

        btn = self.position_btn_group.checkedButton()
        if not btn:
            return

        text = btn.text()
        
        h_active = ("Left" in text) or ("Right" in text)
        v_active = ("Top" in text) or ("Bottom" in text)

        if self.h_margin_slider:
            self.h_margin_slider.setEnabled(h_active)
            self.h_margin_spin.setEnabled(h_active)
            self.h_margin_label.setEnabled(h_active)

        if self.v_margin_slider:
            self.v_margin_slider.setEnabled(v_active)
            self.v_margin_spin.setEnabled(v_active)
            self.v_margin_label.setEnabled(v_active)

    # ==============================================================
    # Page Settings API (Now Per Paper Size)
    # ==============================================================
    
    def _load_page_selection_into_ui(self, cfg: Dict) -> None:
        """Load page selection settings from a config dict into the UI."""
        if not self.page_mode_group:
            return
        
        mode = cfg.get("page_selection", "all")
        custom = cfg.get("custom_pages", "")
        
        if self.custom_pages_input:
            self.custom_pages_input.setText(custom)
        
        found = False
        for btn in self.page_mode_group.buttons():
            if btn.property("mode_key") == mode:
                btn.setChecked(True)
                found = True
                break
        if not found:
            # Fallback to all
            for btn in self.page_mode_group.buttons():
                if btn.property("mode_key") == "all":
                    btn.setChecked(True)
                    break
        
        # Update custom input enabled state
        self._toggle_custom_input(mode == "custom")
    
    def _get_page_selection_from_ui(self) -> Dict[str, str]:
        """Get current page selection settings from the UI."""
        if not self.page_mode_group:
            return {"page_selection": "all", "custom_pages": ""}
            
        btn = self.page_mode_group.checkedButton()
        mode = btn.property("mode_key") if btn else "all"
        return {
            "page_selection": mode,
            "custom_pages": self.custom_pages_input.text() if self.custom_pages_input else ""
        }
    
    def set_page_settings(self, settings: Dict[str, str]) -> None:
        """
        DEPRECATED: Page settings are now stored per paper size inside configs_by_size.
        This method is kept for backward compatibility but does nothing.
        """
        pass

    def get_page_settings(self) -> Dict[str, str]:
        """
        DEPRECATED: Page settings are now stored per paper size inside configs_by_size.
        This method is kept for backward compatibility but returns empty dict.
        """
        return {"selection": "all", "custom_pages": ""}

    # ==============================================================
    # Event Handlers & State
    # ==============================================================

    def on_paper_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if previous:
            prev_key = tuple(previous.data(Qt.UserRole))
            self.save_ui_into_config(prev_key)

        if current:
            new_key = tuple(current.data(Qt.UserRole))
            self._current_key = new_key
            self.load_config_into_ui(new_key)
            self.current_config = self.all_configs[new_key].copy()

    def load_config_into_ui(self, key: Tuple[str, str]) -> None:
        self._load_config_into_ui_no_preview(key)
        self.render_preview()

    def _load_config_into_ui_no_preview(self, key: Tuple[str, str]) -> None:
        """Subclasses must implement this to map config dict to UI widgets."""
        raise NotImplementedError

    def save_ui_into_config(self, key: Tuple[str, str]) -> None:
        self.all_configs[key] = self._get_current_ui_config()
        self.current_config = self.all_configs[key].copy()

    def _get_current_ui_config(self) -> Dict:
        """Subclasses must implement this to scrape UI widgets into dict."""
        raise NotImplementedError

    def render_preview(self) -> None:
        """
        Common preview rendering logic.
        Subclasses should override _draw_preview_content() to draw their specific content.
        """
        if not self._current_key:
            return

        config = self._get_current_ui_config()
        family, mode = self._current_key
        paper_info = PAPER_DEFINITIONS.get(family, {}).get(mode)
        if not paper_info:
            return

        page_w_pts, page_h_pts = float(paper_info["w"]), float(paper_info["h"])

        # Create PDF page
        doc = fitz.open()
        page = doc.new_page(width=page_w_pts, height=page_h_pts)

        # Let subclass draw its content
        self._draw_preview_content(page, page_w_pts, page_h_pts, config)

        # Use the preview widget to render with overlay guides
        self.preview_canvas.set_page(page, zoom=1.5, overlay_config=config)
        
        doc.close()

    def _draw_preview_content(self, page: fitz.Page, page_w: float, page_h: float, config: Dict) -> None:
        """
        Override in subclass to draw specific content onto the PDF page.
        
        Args:
            page: The fitz.Page object to draw on
            page_w: Page width in points
            page_h: Page height in points
            config: Current UI configuration dictionary
        """
        raise NotImplementedError("Subclasses must implement _draw_preview_content()")

    def apply_to_all_sizes(self) -> None:
        item = self.paper_list.currentItem()
        if not item:
            return

        label = item.text()
        reply = QMessageBox.question(
            self, "Apply to All Sizes",
            f"Copy visual settings from '{label}' to all paper sizes?\n(Note: 'Page Application' settings are global and will not be affected)",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            key = tuple(item.data(Qt.UserRole))
            self.save_ui_into_config(key)
            base_cfg = self.all_configs[key].copy()

            for k in ALL_PAPER_KEYS:
                self.all_configs[k] = base_cfg.copy()

            self.render_preview()
            QMessageBox.information(self, "Settings Applied", "Applied visual settings to all paper sizes.")

    def on_apply_clicked(self) -> None:
        if self._current_key:
            self.save_ui_into_config(self._current_key)
        self.configApplied.emit()

    def accept(self) -> None:
        if self._current_key:
            self.save_ui_into_config(self._current_key)
        super().accept()

    # Public API
    def set_all_configs(self, configs: Dict) -> None:
        for key in ALL_PAPER_KEYS:
            if key in configs:
                self.all_configs[key] = configs[key].copy()

        item = self.paper_list.currentItem()
        if item:
            key = tuple(item.data(Qt.UserRole))
            self._load_config_into_ui_no_preview(key)
            self.update_margin_controls_state()
            self.render_preview()

    def get_all_configs(self) -> Dict:
        if self._current_key:
            self.save_ui_into_config(self._current_key)
        return self.all_configs.copy()

    # Common Events
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.render_preview()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.render_preview()