from typing import Dict, Tuple, Optional
import os
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QGroupBox, QComboBox, QCheckBox, QSlider, QDoubleSpinBox,
    QLabel, QPushButton, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QFormLayout, QSpinBox, QButtonGroup, 
    QRadioButton, QSizePolicy, QWidget
)

import fitz

from .base_configuration_dialog import BaseConfigurationDialog
from core.constants import DEFAULT_STAMP_CONFIG, ALL_PAPER_KEYS
from core.anchor import compute_anchor_for_pdf

# Constants for dimension limits
MAX_STAMP_WIDTH = 1000.0
MAX_STAMP_HEIGHT = 1000.0
PREVIEW_MAX_PX = 800  # Max pixel size for the preview image optimization

class StampConfigurationDialog(BaseConfigurationDialog):
    """Stamp Configuration Dialog inheriting from Base."""

    def __init__(self, parent: Optional[QWidget] = None, stamp_path: str = ""):
        super().__init__(parent, title="Stamp Configuration")
        
        self.placeholder_path = os.path.join("assets", "teststamp.bmp")
        self._temp_preview_file = None  # Handle for cleanup later
        
        # Logic: Use the user's stamp if it exists; otherwise fallback to placeholder
        if stamp_path and os.path.exists(stamp_path):
            self.active_stamp_path = stamp_path
        else:
            self.active_stamp_path = self.placeholder_path

        # --- OPTIMIZATION: Create Scaled Preview Image ---
        # We default the preview path to the active path
        self.preview_stamp_path = self.active_stamp_path
        
        if os.path.exists(self.active_stamp_path):
            # Load into QImage to check dimensions
            img = QImage(self.active_stamp_path)
            if not img.isNull():
                # If image is very large, create a smaller temp version for the GUI preview
                if img.width() > PREVIEW_MAX_PX or img.height() > PREVIEW_MAX_PX:
                    scaled_img = img.scaled(
                        PREVIEW_MAX_PX, PREVIEW_MAX_PX, 
                        Qt.KeepAspectRatio, 
                        Qt.SmoothTransformation
                    )
                    
                    # Create a temp file (closed so other processes/libraries can open it)
                    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                    tf.close()

                    if scaled_img.save(tf.name):
                        self.preview_stamp_path = tf.name
                        self._temp_preview_file = tf.name
                    else:
                        os.unlink(tf.name)

        # --- RATIO CALCULATION ---
        # vital: Calculate ratio based on the ORIGINAL active stamp (High Res), 
        # not the downscaled preview. This ensures width/height math remains accurate.
        self.native_ratio = 1.0
        if os.path.exists(self.active_stamp_path):
            w, h = self.pdf_ops.get_stamp_dimensions(self.active_stamp_path, 1.0)
            if h > 0: 
                self.native_ratio = w / h

        # Config storage
        default_cfg = DEFAULT_STAMP_CONFIG.copy()
        self.all_configs = {key: default_cfg.copy() for key in ALL_PAPER_KEYS}

        # UI References for rotation (initialized in _init_properties_section)
        self.rot_btn_group: Optional[QButtonGroup] = None

        self._init_base_ui()

        item = self.paper_list.currentItem()
        if item:
            self._current_key = tuple(item.data(Qt.UserRole))
            self._load_config_into_ui_no_preview(self._current_key)
            self.current_config = self.all_configs[self._current_key].copy()
            
        self.update_margin_controls_state()
        self.render_preview()

    def closeEvent(self, event):
        """Cleanup temporary preview file on close."""
        if self._temp_preview_file and os.path.exists(self._temp_preview_file):
            try:
                os.remove(self._temp_preview_file)
            except OSError:
                pass
        super().closeEvent(event)

    def _init_right_settings(self, parent_layout: QHBoxLayout) -> None:
        settings_panel = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_panel)

        self._init_properties_section(settings_layout)
        self._init_position_section(settings_layout)
        self._init_margins_section(settings_layout)
        
        # Add Page Selection Section here
        self._init_page_selection_section(settings_layout)

        self.apply_all_btn = QPushButton("Apply Visuals to All Sizes")
        self.apply_all_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.apply_all_btn.clicked.connect(self.apply_to_all_sizes)
        settings_layout.addWidget(self.apply_all_btn)

        settings_layout.addStretch()
        parent_layout.addWidget(settings_panel, stretch=0)

    # --- Section Inits ---

    def _init_properties_section(self, layout: QVBoxLayout):
        group = QGroupBox("Properties")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignLeft)

        # Dimensions Row (Single row for Width and Height spinboxes)
        dim_row = QHBoxLayout()

        # Width
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(1.0, MAX_STAMP_WIDTH)
        self.width_spin.setValue(50.0)
        self.width_spin.setFixedWidth(70)
        self.width_spin.setSingleStep(1.0)
        self.width_spin.valueChanged.connect(self.on_width_changed)
        
        dim_row.addWidget(QLabel("Width (mm):"))
        dim_row.addWidget(self.width_spin)
        
        dim_row.addSpacing(15) 

        # Height
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(1.0, MAX_STAMP_HEIGHT)
        self.height_spin.setValue(30.0)
        self.height_spin.setFixedWidth(70)
        self.height_spin.setSingleStep(1.0)
        self.height_spin.valueChanged.connect(self.on_height_changed)

        dim_row.addWidget(QLabel("Height (mm):"))
        dim_row.addWidget(self.height_spin)
        
        dim_row.addStretch()
        form.addRow(dim_row)

        self.aspect_ratio_chk = QCheckBox("Maintain Aspect Ratio")
        self.aspect_ratio_chk.setChecked(True)
        self.aspect_ratio_chk.toggled.connect(self.on_aspect_toggled)
        form.addRow(self.aspect_ratio_chk)

        # Rotation (Distributed Radio Buttons)
        self.rot_btn_group = QButtonGroup(self)
        self.rot_btn_group.buttonClicked.connect(self.render_preview)
        
        rot_layout = QHBoxLayout()
        # Removing default spacing allows the stretches to handle the distribution precisely
        rot_layout.setSpacing(0) 
        rot_layout.setContentsMargins(0, 0, 0, 0)
        
        angles = [0, 90, 180, 270]
        for i, angle in enumerate(angles):
            rb = QRadioButton(f"{angle}")
            self.rot_btn_group.addButton(rb, angle)
            rot_layout.addWidget(rb)
            
            # Add a stretchable spring after every item EXCEPT the last one
            if i < len(angles) - 1:
                rot_layout.addStretch()
        
        # Default check 0
        self.rot_btn_group.button(0).setChecked(True)
        
        form.addRow("Rotation (°):", rot_layout)

        # Opacity
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_spin = QSpinBox()
        row, _ = self._create_styled_slider_row("Opacity (%):", self.opacity_slider, self.opacity_spin, 0, 100, 100, spin_width=60)
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
            ("Center Left", 1, 0), ("Center", 1, 1), ("Center Right", 1, 2),
            ("Bottom Left", 2, 0), ("Bottom Center", 2, 1), ("Bottom Right", 2, 2),
        ]

        for text, row, col in positions:
            rb = QRadioButton(text)
            grid.addWidget(rb, row, col)
            self.position_btn_group.addButton(rb)

        # Fallback default
        for btn in self.position_btn_group.buttons():
            if btn.text() == "Center Right":
                btn.setChecked(True)
                break

        layout.addWidget(group)

    def _init_margins_section(self, layout: QVBoxLayout):
        group = QGroupBox("Margins")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignLeft)

        self.h_margin_slider = QSlider(Qt.Horizontal)
        self.h_margin_spin = QSpinBox()
        row, self.h_margin_label = self._create_styled_slider_row("Horizontal (mm):", self.h_margin_slider, self.h_margin_spin, 0, 100, 10, spin_width=60)
        form.addRow(row)

        self.v_margin_slider = QSlider(Qt.Horizontal)
        self.v_margin_spin = QSpinBox()
        row, self.v_margin_label = self._create_styled_slider_row("Vertical (mm):", self.v_margin_slider, self.v_margin_spin, 0, 100, 10, spin_width=60)
        form.addRow(row)

        layout.addWidget(group)

    # --- Specific Logic (Aspect Ratio) ---

    def on_width_changed(self, new_width: float) -> None:
        if self.aspect_ratio_chk.isChecked() and self.native_ratio > 0:
            # Calculate potential height
            new_h = new_width / self.native_ratio
            
            # If height exceeds max, clamp it and correct the width back
            if new_h > MAX_STAMP_HEIGHT:
                new_h = MAX_STAMP_HEIGHT
                corrected_w = MAX_STAMP_HEIGHT * self.native_ratio
                
                # Update width spinbox to the clamped value
                self.width_spin.blockSignals(True)
                self.width_spin.setValue(corrected_w)
                self.width_spin.blockSignals(False)

            self.height_spin.blockSignals(True)
            self.height_spin.setValue(new_h)
            self.height_spin.blockSignals(False)
        self.render_preview()

    def on_height_changed(self, new_height: float) -> None:
        if self.aspect_ratio_chk.isChecked() and self.native_ratio > 0:
            # Calculate potential width
            new_w = new_height * self.native_ratio
            
            # If width exceeds max, clamp it and correct the height back
            if new_w > MAX_STAMP_WIDTH:
                new_w = MAX_STAMP_WIDTH
                corrected_h = MAX_STAMP_WIDTH / self.native_ratio
                
                # Update height spinbox to the clamped value
                self.height_spin.blockSignals(True)
                self.height_spin.setValue(corrected_h)
                self.height_spin.blockSignals(False)
            
            self.width_spin.blockSignals(True)
            self.width_spin.setValue(new_w)
            self.width_spin.blockSignals(False)
        self.render_preview()
        
    def on_aspect_toggled(self, checked: bool) -> None:
        if checked and self.native_ratio > 0:
            current_w = self.width_spin.value()
            new_h = current_w / self.native_ratio
            self.height_spin.setValue(new_h)
        self.render_preview()

    # --- State ---

    def _load_config_into_ui_no_preview(self, key: Tuple[str, str]) -> None:
        cfg = self.all_configs.get(key)
        if not cfg: return

        # Block signals for bulk update
        widgets = [
            self.width_spin, self.height_spin,
            self.aspect_ratio_chk, self.opacity_spin, self.opacity_slider,
            self.h_margin_spin, self.h_margin_slider, self.v_margin_spin, self.v_margin_slider
        ]
        
        # Block group signals
        self.rot_btn_group.blockSignals(True)
        for w in widgets: w.blockSignals(True)

        w_val = cfg.get("stamp_width_mm", 50.0)
        self.width_spin.setValue(w_val)
        
        h_val = cfg.get("stamp_height_mm", 30.0)
        self.height_spin.setValue(h_val)

        self.aspect_ratio_chk.setChecked(cfg.get("maintain_aspect", True))
        
        # Rotation logic (check based on ID)
        rot = cfg.get("stamp_rotation", 0)
        btn = self.rot_btn_group.button(rot)
        if btn:
            btn.setChecked(True)
        else:
            self.rot_btn_group.button(0).setChecked(True)
            
        self.opacity_spin.setValue(cfg.get("stamp_opacity", 100))
        self.opacity_slider.setValue(cfg.get("stamp_opacity", 100))
        
        self.h_margin_spin.setValue(cfg.get("h_margin", 10))
        self.h_margin_slider.setValue(cfg.get("h_margin", 10))
        self.v_margin_spin.setValue(cfg.get("v_margin", 10))
        self.v_margin_slider.setValue(cfg.get("v_margin", 10))

        target_pos = cfg.get("position", "Top Right")
        found = False
        for btn in self.position_btn_group.buttons():
            if btn.text() == target_pos:
                btn.setChecked(True)
                found = True
                break
        if not found:
            for btn in self.position_btn_group.buttons():
                if btn.text() == "Center Right":
                    btn.setChecked(True)
                    break

        for w in widgets: w.blockSignals(False)
        self.rot_btn_group.blockSignals(False)

        # Force aspect sync after load if checked
        if self.aspect_ratio_chk.isChecked() and self.native_ratio > 0:
            current_w = self.width_spin.value()
            self.height_spin.blockSignals(True)
            new_h = current_w / self.native_ratio
            self.height_spin.setValue(new_h)
            self.height_spin.blockSignals(False)

        # Load page selection settings from this paper size's config
        self._load_page_selection_into_ui(cfg)

        self.update_margin_controls_state()

    def _get_current_ui_config(self) -> Dict:
        checked_btn = self.position_btn_group.checkedButton()
        pos_text = checked_btn.text() if checked_btn else "Top Right"
        
        # Retrieve rotation from checked button ID (defaults to 0 if none checked)
        rot = self.rot_btn_group.checkedId()
        if rot == -1:
            rot = 0
        
        # Get page selection settings
        page_settings = self._get_page_selection_from_ui()
        
        return {
            "stamp_width_mm": self.width_spin.value(),
            "stamp_height_mm": self.height_spin.value(),
            "maintain_aspect": self.aspect_ratio_chk.isChecked(),
            "stamp_rotation": rot,
            "stamp_opacity": self.opacity_spin.value(),
            "h_margin": self.h_margin_spin.value(),
            "v_margin": self.v_margin_spin.value(),
            "position": pos_text,
            "page_selection": page_settings["page_selection"],
            "custom_pages": page_settings["custom_pages"],
        }

    # --- Render ---

    def _draw_preview_content(self, page: fitz.Page, page_w: float, page_h: float, config: Dict) -> None:
        """Draw stamp content onto the preview page."""
        stamp_drawn = False
        
        # USE preview_stamp_path HERE (Performance optimized image)
        if os.path.exists(self.preview_stamp_path):
            try:
                pts_per_mm = 72 / 25.4
                target_w = config["stamp_width_mm"] * pts_per_mm
                target_h = config["stamp_height_mm"] * pts_per_mm
                rot = config.get("stamp_rotation", 0)
                
                # Anchor Calculation
                aw, ah = (target_h, target_w) if int(rot) % 180 == 90 else (target_w, target_h)
                bx, by = compute_anchor_for_pdf(page_w, page_h, aw, ah, config)
                
                self.pdf_ops.insert_stamp(
                    page, self.preview_stamp_path, bx, by, aw, ah, rot, 
                    config.get("stamp_opacity", 100) / 100.0
                )
                stamp_drawn = True
            except Exception:
                pass

        if not stamp_drawn:
            # Fallback Vector Box
            pts_per_mm = 72 / 25.4
            target_w = config["stamp_width_mm"] * pts_per_mm
            target_h = config["stamp_height_mm"] * pts_per_mm
            rot = config.get("stamp_rotation", 0)
            aw, ah = (target_h, target_w) if int(rot) % 180 == 90 else (target_w, target_h)
            bx, by = compute_anchor_for_pdf(page_w, page_h, aw, ah, config)
            
            shape = page.new_shape()
            shape.draw_rect(fitz.Rect(bx, by, bx + aw, by + ah))
            shape.finish(color=(0.2, 0.4, 0.8), fill=(0.9, 0.9, 0.95), fill_opacity=config["stamp_opacity"] / 100.0)
            shape.insert_text(fitz.Point(bx + aw / 2 - 20, by + ah / 2), "NO ASSET", fontsize=10)
            shape.commit()