from typing import Dict, Tuple, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGroupBox, QComboBox, QCheckBox, QSlider, QSpinBox,
    QLineEdit, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QFormLayout, QFrame, QColorDialog, QButtonGroup, 
    QRadioButton, QSizePolicy, QWidget
)

import fitz

from .base_configuration_dialog import BaseConfigurationDialog
from core.constants import DEFAULT_TEXT_CONFIG, ALL_PAPER_KEYS
from core.anchor import compute_anchor_for_pdf

class TextConfigurationDialog(BaseConfigurationDialog):
    """Text Configuration Dialog inheriting from Base."""

    def __init__(self, parent: Optional[QWidget] = None, available_fonts: Optional[Dict] = None):
        super().__init__(parent, title="Text Configuration")
        self.available_fonts = available_fonts or {}
        
        default_cfg = DEFAULT_TEXT_CONFIG.copy()
        if self.available_fonts:
            default_cfg["font_family"] = next(iter(self.available_fonts.keys()))

        self.all_configs = {key: default_cfg.copy() for key in ALL_PAPER_KEYS}

        self._init_base_ui()
        
        item = self.paper_list.currentItem()
        if item:
            self._current_key = tuple(item.data(Qt.UserRole))
            self._load_config_into_ui_no_preview(self._current_key)
            self.current_config = self.all_configs[self._current_key].copy()
            
        self.update_font_style_availability()
        self.update_margin_controls_state()

    def _init_right_settings(self, parent_layout: QHBoxLayout) -> None:
        settings_panel = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_panel)

        self._init_font_section(settings_layout)
        self._init_text_color_section(settings_layout)
        self._init_bg_color_section(settings_layout)
        self._init_position_section(settings_layout)
        self._init_margins_section(settings_layout)
        
        # Add Page Selection Section here
        self._init_page_selection_section(settings_layout)

        # Apply All Button
        self.apply_all_btn = QPushButton("Apply Visuals to All Sizes")
        self.apply_all_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.apply_all_btn.clicked.connect(self.apply_to_all_sizes)
        settings_layout.addWidget(self.apply_all_btn)

        settings_layout.addStretch()
        parent_layout.addWidget(settings_panel, stretch=0)

    # --- Section Inits ---

    def _init_font_section(self, layout: QVBoxLayout):
        group = QGroupBox("Font")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignLeft)

        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(self.available_fonts.keys() if self.available_fonts else ["Arial"])
        self.font_family_combo.currentTextChanged.connect(self.render_preview)
        self.font_family_combo.currentTextChanged.connect(self.update_font_style_availability)
        form.addRow("Font:", self.font_family_combo)

        # Styles (Distributed Checkboxes)
        style_row = QHBoxLayout()
        # Removing default spacing allows the stretches to handle the distribution precisely
        style_row.setSpacing(0)
        style_row.setContentsMargins(0, 0, 0, 0)

        self.bold_checkbox = QCheckBox("Bold")
        self.italic_checkbox = QCheckBox("Italic")
        self.underline_checkbox = QCheckBox("Underline")
        self.strike_checkbox = QCheckBox("Strike")
        
        checkboxes = [self.bold_checkbox, self.italic_checkbox, self.underline_checkbox, self.strike_checkbox]
        
        for i, chk in enumerate(checkboxes):
            style_row.addWidget(chk)
            chk.stateChanged.connect(self.render_preview)
            
            # Add a stretchable spring after every item EXCEPT the last one
            if i < len(checkboxes) - 1:
                style_row.addStretch()

        form.addRow("Styles:", style_row)

        # Sizes & Spacing
        self.font_size_slider = QSlider(Qt.Horizontal)
        self.font_size_spin = QSpinBox()
        row, _ = self._create_styled_slider_row("Font Size (pt):", self.font_size_slider, self.font_size_spin, 8, 72, 12)
        form.addRow(row)

        self.padding_x_slider = QSlider(Qt.Horizontal)
        self.padding_x_spin = QSpinBox()
        row, _ = self._create_styled_slider_row("Padding X (pt):", self.padding_x_slider, self.padding_x_spin, 0, 30, 3)
        form.addRow(row)

        self.padding_y_slider = QSlider(Qt.Horizontal)
        self.padding_y_spin = QSpinBox()
        row, _ = self._create_styled_slider_row("Padding Y (pt):", self.padding_y_slider, self.padding_y_spin, 0, 30, 3)
        form.addRow(row)

        self.line_gap_slider = QSlider(Qt.Horizontal)
        self.line_gap_spin = QSpinBox()
        row, _ = self._create_styled_slider_row("Line Gap (pt):", self.line_gap_slider, self.line_gap_spin, 0, 30, 0)
        form.addRow(row)

        layout.addWidget(group)

    def _init_text_color_section(self, layout: QVBoxLayout):
        group = QGroupBox("Text Color")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignLeft)

        color_row = QHBoxLayout()
        self.text_color_hex = QLineEdit("#000000")
        self.text_color_hex.textChanged.connect(self.render_preview)
        self.text_color_swatch = QLabel()
        self.text_color_swatch.setFixedSize(40, 20)
        self.text_color_swatch.setFrameShape(QFrame.Panel)
        self.text_color_swatch.setStyleSheet("background:#000000;")
        
        btn_pick = QPushButton("Pick")
        btn_pick.clicked.connect(self.pick_text_color)

        color_row.addWidget(self.text_color_hex, stretch=1)
        color_row.addWidget(self.text_color_swatch)
        color_row.addWidget(btn_pick)
        form.addRow("Color:", color_row)

        self.text_opacity_slider = QSlider(Qt.Horizontal)
        self.text_opacity_spin = QSpinBox()
        row, _ = self._create_styled_slider_row("Opacity (%):", self.text_opacity_slider, self.text_opacity_spin, 0, 100, 100)
        form.addRow(row)

        layout.addWidget(group)

    def _init_bg_color_section(self, layout: QVBoxLayout):
        group = QGroupBox("Background Color")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignLeft)

        bg_row = QHBoxLayout()
        self.bg_color_hex = QLineEdit("#ffff00")
        self.bg_color_hex.textChanged.connect(self.render_preview)
        self.bg_color_swatch = QLabel()
        self.bg_color_swatch.setFixedSize(40, 20)
        self.bg_color_swatch.setFrameShape(QFrame.Panel)
        self.bg_color_swatch.setStyleSheet("background:#ffff00;")
        
        btn_pick = QPushButton("Pick")
        btn_pick.clicked.connect(self.pick_bg_color)

        bg_row.addWidget(self.bg_color_hex, stretch=1)
        bg_row.addWidget(self.bg_color_swatch)
        bg_row.addWidget(btn_pick)
        form.addRow("Color:", bg_row)

        self.bg_opacity_slider = QSlider(Qt.Horizontal)
        self.bg_opacity_spin = QSpinBox()
        row, _ = self._create_styled_slider_row("Opacity (%):", self.bg_opacity_slider, self.bg_opacity_spin, 0, 100, 0)
        form.addRow(row)

        layout.addWidget(group)

    def _init_position_section(self, layout: QVBoxLayout):
        group = QGroupBox("Position")
        grid = QGridLayout(group)

        self.position_btn_group = QButtonGroup(self)
        self.position_btn_group.buttonClicked.connect(self.render_preview)
        self.position_btn_group.buttonClicked.connect(self.update_margin_controls_state)
        
        positions = [
            ("Top Left", 0, 0), ("Top Center", 0, 1), ("Top Right", 0, 2),
            ("Left", 1, 0), ("Center", 1, 1), ("Right", 1, 2),
            ("Bottom Left", 2, 0), ("Bottom Center", 2, 1), ("Bottom Right", 2, 2),
        ]

        for text, row, col in positions:
            rb = QRadioButton(text)
            grid.addWidget(rb, row, col)
            self.position_btn_group.addButton(rb)

        self.position_btn_group.buttons()[0].setChecked(True)
        layout.addWidget(group)

    def _init_margins_section(self, layout: QVBoxLayout):
        group = QGroupBox("Margins")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignLeft)

        self.h_margin_slider = QSlider(Qt.Horizontal)
        self.h_margin_spin = QSpinBox()
        row, self.h_margin_label = self._create_styled_slider_row("Horizontal (mm):", self.h_margin_slider, self.h_margin_spin, 0, 100, 10)
        form.addRow(row)

        self.v_margin_slider = QSlider(Qt.Horizontal)
        self.v_margin_spin = QSpinBox()
        row, self.v_margin_label = self._create_styled_slider_row("Vertical (mm):", self.v_margin_slider, self.v_margin_spin, 0, 100, 10)
        form.addRow(row)

        layout.addWidget(group)

    # --- Logic ---

    def update_font_style_availability(self):
        family = self.font_family_combo.currentText()
        fam_map = self.available_fonts.get(family, {})
        
        has_bold = "bold" in fam_map
        has_italic = "italic" in fam_map
        self.bold_checkbox.setEnabled(has_bold)
        self.italic_checkbox.setEnabled(has_italic)

    def pick_text_color(self):
        color = QColorDialog.getColor(QColor(self.text_color_hex.text()), self, "Pick Text Color")
        if color.isValid():
            hex_str = color.name()
            self.text_color_hex.setText(hex_str)
            self.text_color_swatch.setStyleSheet(f"background:{hex_str};")

    def pick_bg_color(self):
        color = QColorDialog.getColor(QColor(self.bg_color_hex.text()), self, "Pick Background Color")
        if color.isValid():
            hex_str = color.name()
            self.bg_color_hex.setText(hex_str)
            self.bg_color_swatch.setStyleSheet(f"background:{hex_str};")

    def _select_fontfile_for_config(self, cfg: Dict) -> Optional[str]:
        family = cfg.get("font_family")
        fam_map = self.available_fonts.get(family, {})
        if not fam_map: return None

        b, i = cfg.get("bold", False), cfg.get("italic", False)
        if b and i: return fam_map.get("bolditalic") or fam_map.get("bold") or fam_map.get("italic") or fam_map.get("regular")
        if b: return fam_map.get("bold") or fam_map.get("regular")
        if i: return fam_map.get("italic") or fam_map.get("regular")
        return fam_map.get("regular")

    # --- State Management ---

    def _load_config_into_ui_no_preview(self, key: Tuple[str, str]) -> None:
        cfg = self.all_configs.get(key)
        if not cfg: return

        # Block signals globally for the load duration if preferred, 
        # or rely on the helper's individual blocking (which is cleaner).
        self.font_family_combo.setCurrentText(cfg["font_family"])
        self.bold_checkbox.setChecked(cfg["bold"])
        self.italic_checkbox.setChecked(cfg["italic"])
        self.underline_checkbox.setChecked(cfg["underline"])
        self.strike_checkbox.setChecked(cfg["strike"])
        
        # Sliders/Spins (Helper handles signal blocking)
        self.font_size_spin.setValue(cfg["font_size"])
        self.text_opacity_spin.setValue(cfg["text_opacity"])
        self.bg_opacity_spin.setValue(cfg["bg_opacity"])
        self.h_margin_spin.setValue(cfg["h_margin"])
        self.v_margin_spin.setValue(cfg["v_margin"])
        self.padding_x_spin.setValue(cfg["pad_x"])
        self.padding_y_spin.setValue(cfg["pad_y"])
        self.line_gap_spin.setValue(cfg["line_gap"])

        self.text_color_hex.setText(cfg["text_color"])
        self.text_color_swatch.setStyleSheet(f"background:{cfg['text_color']}")
        self.bg_color_hex.setText(cfg["bg_color"])
        self.bg_color_swatch.setStyleSheet(f"background:{cfg['bg_color']}")

        target_pos = cfg.get("position", "Top Left")
        for btn in self.position_btn_group.buttons():
            if btn.text() == target_pos:
                btn.setChecked(True)
                break
        
        # Load page selection settings from this paper size's config
        self._load_page_selection_into_ui(cfg)
        
        self.update_margin_controls_state()

    def _get_current_ui_config(self) -> Dict:
        checked_btn = self.position_btn_group.checkedButton()
        pos_text = checked_btn.text() if checked_btn else "Top Left"
        
        # Get page selection settings
        page_settings = self._get_page_selection_from_ui()
        
        return {
            "font_family": self.font_family_combo.currentText(),
            "bold": self.bold_checkbox.isChecked(),
            "italic": self.italic_checkbox.isChecked(),
            "underline": self.underline_checkbox.isChecked(),
            "strike": self.strike_checkbox.isChecked(),
            "font_size": self.font_size_spin.value(),
            "text_color": self.text_color_hex.text(),
            "text_opacity": self.text_opacity_spin.value(),
            "bg_color": self.bg_color_hex.text(),
            "bg_opacity": self.bg_opacity_spin.value(),
            "h_margin": self.h_margin_spin.value(),
            "v_margin": self.v_margin_spin.value(),
            "pad_x": self.padding_x_spin.value(),
            "pad_y": self.padding_y_spin.value(),
            "line_gap": self.line_gap_spin.value(),
            "position": pos_text,
            "page_selection": page_settings["page_selection"],
            "custom_pages": page_settings["custom_pages"],
        }

    # --- Render ---

    def _draw_preview_content(self, page: fitz.Page, page_w: float, page_h: float, config: Dict) -> None:
        """Draw text content onto the preview page."""
        sample_text = "Really long sample text\n2nd line"
        font_path = self._select_fontfile_for_config(config)
        font_key = font_path or "helv"
        font_size = float(config.get("font_size", 12.0))
        
        # Calculate Position
        font_obj = self.pdf_ops.get_font(font_key, fontfile=font_path)
        metrics = self.pdf_ops.compute_text_block_metrics(
            sample_text, font_obj, font_size, 
            pad_x=config["pad_x"], pad_y=config["pad_y"], line_gap=config["line_gap"]
        )
        block_x, block_y = compute_anchor_for_pdf(
            page_w, page_h, metrics["block_width"], metrics["total_h"], config
        )
        
        align_map = {"Left": "left", "Right": "right", "Center": "center"}
        align = "center"
        for k, v in align_map.items():
            if config["position"].endswith(k):
                align = v

        self.pdf_ops.insert_text_with_background(
            page, sample_text, block_x, block_y + config["pad_y"] + metrics["asc"], 
            font_key, font_size,
            config["text_color"], config["text_opacity"] / 100.0,
            config["bg_color"], config["bg_opacity"] / 100.0,
            config["underline"], config["strike"], font_path,
            align, config["pad_x"], config["pad_y"], config["line_gap"]
        )