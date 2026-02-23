"""Features tab: text, timestamp, stamp, and security feature groups."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLineEdit,
    QPushButton, QRadioButton, QGridLayout, QScrollArea,
    QSizePolicy, QTextEdit, QButtonGroup, QCheckBox, QFrame,
    QFileDialog,
)
from PySide6.QtCore import Qt

from core.constants import (
    TIMESTAMP_FORMATS, TEXT_INPUT_HEIGHT, PASSWORD_TOGGLE_WIDTH,
    STAMP_IMAGE_FILTERS, DEBOUNCE_DELAY_MS,
)
from widgets.substitution_picker import SubstitutionPickerButton

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def setup_features_tab(win: MainWindow) -> None:
    """Create the Features tab with all 4 feature groups."""
    tab = QWidget()
    tab_layout = QVBoxLayout(tab)
    tab_layout.setContentsMargins(0, 0, 0, 1)

    win.feature_scroll_area = QScrollArea()
    win.feature_scroll_area.setWidgetResizable(True)
    win.feature_scroll_area.setFrameShape(QFrame.NoFrame)
    win.feature_scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")

    win.feature_scroll_content = QWidget()
    win.feature_scroll_content.setObjectName("scroll_content_widget")
    win.feature_scroll_content.setStyleSheet(
        "#scroll_content_widget { background-color: transparent; }"
    )

    content_layout = QVBoxLayout(win.feature_scroll_content)

    # --- 1. Text Insertion Group ---
    win.group_text_insertion = QGroupBox("Text Insertion")
    win.group_text_insertion.setCheckable(True)
    win.group_text_insertion.setChecked(False)
    text_group_layout = QVBoxLayout(win.group_text_insertion)

    text_input_group = QGroupBox("Text to Insert")
    text_input_layout = QVBoxLayout(text_input_group)
    win.text_input_box = QTextEdit()
    win.text_input_box.setFixedHeight(TEXT_INPUT_HEIGHT)
    win.text_input_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    win.text_input_box.setPlaceholderText("Enter text to insert...")
    win.btn_substitution_picker = SubstitutionPickerButton(win.text_input_box)
    text_input_layout.addWidget(win.text_input_box)
    text_input_layout.addWidget(win.btn_substitution_picker)
    text_group_layout.addWidget(text_input_group)

    win.btn_text_config = QPushButton("Text Configuration")
    text_group_layout.addWidget(win.btn_text_config)
    content_layout.addWidget(win.group_text_insertion)

    # --- 2. Timestamp Insertion Group ---
    win.group_timestamp_insertion = QGroupBox("Timestamp Insertion")
    win.group_timestamp_insertion.setCheckable(True)
    win.group_timestamp_insertion.setChecked(False)
    ts_group_layout = QVBoxLayout(win.group_timestamp_insertion)

    ts_prefix_group = QGroupBox("Prefix")
    ts_prefix_layout = QVBoxLayout(ts_prefix_group)
    win.ts_prefix_edit = QLineEdit()
    win.ts_prefix_edit.setPlaceholderText("e.g. Printed on: ")
    ts_prefix_layout.addWidget(win.ts_prefix_edit)
    ts_group_layout.addWidget(ts_prefix_group)

    ts_format_group = QGroupBox("Formats")
    ts_format_layout = QVBoxLayout(ts_format_group)
    win.ts_format_btn_group = QButtonGroup(win)
    now = datetime.now()
    first_fmt = True
    for _, fmt_str in TIMESTAMP_FORMATS:
        label_text = now.strftime(fmt_str)
        rb = QRadioButton(label_text)
        rb.setProperty("fmt_str", fmt_str)
        if first_fmt:
            rb.setChecked(True)
            first_fmt = False
        win.ts_format_btn_group.addButton(rb)
        ts_format_layout.addWidget(rb)
    ts_group_layout.addWidget(ts_format_group)

    win.btn_timestamp_config = QPushButton("Timestamp Configuration")
    ts_group_layout.addWidget(win.btn_timestamp_config)
    content_layout.addWidget(win.group_timestamp_insertion)

    # --- 3. Stamp Insertion Group ---
    win.group_stamp_insertion = QGroupBox("Stamp Insertion (Experimental)")
    win.group_stamp_insertion.setCheckable(True)
    win.group_stamp_insertion.setChecked(False)
    stamp_group_layout = QVBoxLayout(win.group_stamp_insertion)

    stamp_file_group = QGroupBox("Stamp File")
    stamp_file_layout = QHBoxLayout(stamp_file_group)
    win.stamp_path_entry = QLineEdit()
    win.stamp_path_entry.setPlaceholderText("Select stamp file...")
    win.stamp_path_entry.setReadOnly(True)
    win.btn_browse_stamp = QPushButton("Browse")
    win.btn_browse_stamp.clicked.connect(lambda: select_stamp_file(win))
    stamp_file_layout.addWidget(win.stamp_path_entry)
    stamp_file_layout.addWidget(win.btn_browse_stamp)
    stamp_group_layout.addWidget(stamp_file_group)

    win.btn_stamp_config = QPushButton("Stamp Configuration")
    win.btn_stamp_config.setEnabled(False)
    stamp_group_layout.addWidget(win.btn_stamp_config)
    content_layout.addWidget(win.group_stamp_insertion)

    # --- 4. PDF Security Group ---
    win.security_group = QGroupBox("PDF Security")
    win.security_group.setCheckable(True)
    win.security_group.setChecked(False)
    security_layout = QVBoxLayout(win.security_group)

    pass_group = QGroupBox("Master Password")
    pass_layout = QHBoxLayout(pass_group)
    win.security_password = QLineEdit()
    win.security_password.setEchoMode(QLineEdit.Password)
    win.security_password.setPlaceholderText("Required to enable permissions...")
    pass_layout.addWidget(win.security_password)

    win._password_visible = False
    win.btn_toggle_password = QPushButton("Show")
    win.btn_toggle_password.setFixedWidth(PASSWORD_TOGGLE_WIDTH)
    win.btn_toggle_password.clicked.connect(lambda: _toggle_password_visibility(win))
    pass_layout.addWidget(win.btn_toggle_password)
    security_layout.addWidget(pass_group)

    perms_group = QGroupBox("Allow User To")
    perms_grid = QGridLayout(perms_group)
    win.chk_perm_print = QCheckBox("Print Document")
    win.chk_perm_modify = QCheckBox("Modify Document")
    win.chk_perm_copy = QCheckBox("Copy Content")
    win.chk_perm_annotate = QCheckBox("Annotations")
    win.chk_perm_form = QCheckBox("Fill Forms")
    win.chk_perm_assemble = QCheckBox("Assemble Document")
    perms_grid.addWidget(win.chk_perm_print, 0, 0)
    perms_grid.addWidget(win.chk_perm_modify, 0, 1)
    perms_grid.addWidget(win.chk_perm_copy, 1, 0)
    perms_grid.addWidget(win.chk_perm_annotate, 1, 1)
    perms_grid.addWidget(win.chk_perm_form, 2, 0)
    perms_grid.addWidget(win.chk_perm_assemble, 2, 1)
    security_layout.addWidget(perms_group)

    content_layout.addWidget(win.security_group)

    content_layout.addStretch()

    win.feature_scroll_area.setWidget(win.feature_scroll_content)
    tab_layout.addWidget(win.feature_scroll_area)

    win.right_tabs.addTab(tab, "Features")


def select_stamp_file(win: MainWindow) -> None:
    """Open file dialog to select a stamp image."""
    import os

    file_path, _ = QFileDialog.getOpenFileName(
        win, "Select Stamp File", "", STAMP_IMAGE_FILTERS,
    )

    if not file_path:
        return

    win.current_stamp_path = file_path
    win.stamp_path_entry.setText(file_path)
    win.btn_stamp_config.setEnabled(True)

    if os.path.exists(file_path):
        w_pts, h_pts = win.pdf_ops.get_stamp_dimensions(file_path, 1.0)

        if w_pts > 0 and h_pts > 0:
            native_ratio = w_pts / h_pts

            def sync_aspect(cfg):
                if cfg.get("maintain_aspect", True):
                    current_w = cfg.get("stamp_width_mm", 50.0)
                    current_h = cfg.get("stamp_height_mm", 50.0)
                    if current_w >= current_h:
                        cfg["stamp_height_mm"] = current_w / native_ratio
                    else:
                        cfg["stamp_width_mm"] = current_h * native_ratio

            for cfg in win.stamp_configs_by_size.values():
                sync_aspect(cfg)

            sync_aspect(win.default_stamp_config)

    win.render_current_page()


def _toggle_password_visibility(win: MainWindow) -> None:
    """Toggle password visibility between shown and hidden."""
    win._password_visible = not win._password_visible
    if win._password_visible:
        win.security_password.setEchoMode(QLineEdit.Normal)
        win.btn_toggle_password.setText("Hide")
    else:
        win.security_password.setEchoMode(QLineEdit.Password)
        win.btn_toggle_password.setText("Show")


def on_text_content_changed(win: MainWindow) -> None:
    """Handle text input box changes with debounce."""
    win.live_input_text = win.text_input_box.toPlainText()
    win._preview_debounce_timer.stop()
    win._preview_debounce_timer.start(DEBOUNCE_DELAY_MS)


def on_timestamp_content_changed(win: MainWindow) -> None:
    """Handle timestamp prefix or format changes with debounce."""
    win.live_timestamp_prefix = win.ts_prefix_edit.text()
    btn = win.ts_format_btn_group.checkedButton()
    if btn:
        win.selected_timestamp_format = btn.property("fmt_str")
    win._preview_debounce_timer.stop()
    win._preview_debounce_timer.start(DEBOUNCE_DELAY_MS)


def update_timestamp_labels(win: MainWindow) -> None:
    """Timer callback: update timestamp format radio button labels with current time."""
    if not win.group_timestamp_insertion.isChecked():
        return

    now = datetime.now()
    for btn in win.ts_format_btn_group.buttons():
        fmt = btn.property("fmt_str")
        if fmt:
            btn.setText(now.strftime(fmt))
