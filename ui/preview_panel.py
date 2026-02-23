"""Preview tab: file/page navigation controls and preview widget."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QAbstractSpinBox, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette

from core.constants import (
    NAV_SPINBOX_WIDTH, PAGE_INFO_LABEL_WIDTH,
    ZOOM_BTN_WIDTH, ZOOM_LABEL_WIDTH, ZOOM_FIT_BTN_WIDTH, TOGGLE_BTN_WIDTH,
)
from widgets.preview_widget import PDFPreviewWidget, PreviewScrollArea

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def setup_preview_tab(win: MainWindow) -> None:
    """Create the Preview tab with file controls, preview widget, and page controls."""
    tab = QWidget()
    layout = QVBoxLayout(tab)

    # --- File navigation controls ---
    file_controls = QWidget()
    file_layout = QHBoxLayout(file_controls)
    file_layout.setContentsMargins(0, 0, 0, 0)

    win.btn_prev_file = QPushButton("PREVIOUS")
    win.file_input = QSpinBox()
    win.file_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
    win.file_input.setMinimum(0)
    win.file_input.setMaximum(0)
    win.file_input.setFixedWidth(NAV_SPINBOX_WIDTH)
    win.file_input.setAlignment(Qt.AlignCenter)
    win.file_input.setKeyboardTracking(False)
    win.file_input.setSuffix(" / 0")
    win.btn_next_file = QPushButton("NEXT")
    win.file_status_entry = QLineEdit("No file selected")
    win.file_status_entry.setFocusPolicy(Qt.NoFocus)
    win.file_status_entry.setEnabled(False)

    file_layout.addWidget(win.btn_prev_file, 0, Qt.AlignVCenter)
    file_layout.addWidget(win.file_input, 0, Qt.AlignVCenter)
    file_layout.addWidget(win.btn_next_file, 0, Qt.AlignVCenter)
    file_layout.addWidget(win.file_status_entry, 1)

    layout.addWidget(file_controls)

    # --- Zoom/Toggle controls bar ---
    zoom_controls = QWidget()
    zoom_layout = QHBoxLayout(zoom_controls)
    zoom_layout.setContentsMargins(0, 0, 0, 0)

    win.btn_toggle_overlay = QPushButton("Original")
    win.btn_toggle_overlay.setCheckable(True)
    win.btn_toggle_overlay.setFixedWidth(TOGGLE_BTN_WIDTH)

    win.btn_zoom_out = QPushButton("-")
    win.btn_zoom_out.setFixedWidth(ZOOM_BTN_WIDTH)

    win.zoom_label = QLabel("100%")
    win.zoom_label.setAlignment(Qt.AlignCenter)
    win.zoom_label.setFixedWidth(ZOOM_LABEL_WIDTH)

    win.btn_zoom_in = QPushButton("+")
    win.btn_zoom_in.setFixedWidth(ZOOM_BTN_WIDTH)

    win.btn_zoom_fit = QPushButton("Fit")
    win.btn_zoom_fit.setFixedWidth(ZOOM_FIT_BTN_WIDTH)

    zoom_layout.addWidget(win.btn_toggle_overlay)
    zoom_layout.addStretch(1)
    zoom_layout.addWidget(win.btn_zoom_out)
    zoom_layout.addWidget(win.zoom_label)
    zoom_layout.addWidget(win.btn_zoom_in)
    zoom_layout.addWidget(win.btn_zoom_fit)

    layout.addWidget(zoom_controls)

    # --- Preview widget in scroll area ---
    win.preview_widget = PDFPreviewWidget()
    win.preview_scroll = PreviewScrollArea()
    win.preview_scroll.setWidgetResizable(False)
    win.preview_scroll.setAlignment(Qt.AlignCenter)
    win.preview_scroll.setFrameShape(QFrame.NoFrame)
    win.preview_scroll.setStyleSheet("QScrollArea { background: transparent; }")
    win.preview_scroll.viewport().setAutoFillBackground(False)
    win.preview_scroll.setWidget(win.preview_widget)

    layout.addWidget(win.preview_scroll, stretch=1)

    # --- Page navigation controls ---
    page_controls = QWidget()
    page_layout = QHBoxLayout(page_controls)
    page_layout.setContentsMargins(0, 0, 0, 0)

    win.page_info_label = QLabel("Page Info")
    win.page_info_label.setAlignment(Qt.AlignCenter)
    win.page_info_label.setFocusPolicy(Qt.NoFocus)
    win.page_info_label.setEnabled(False)
    win.page_info_label.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
    win.page_info_label.setAutoFillBackground(True)
    win.page_info_label.setBackgroundRole(QPalette.Base)
    win.page_info_label.setFixedWidth(PAGE_INFO_LABEL_WIDTH)
    win.page_info_label.setTextInteractionFlags(
        Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
    )

    nav_container = QWidget()
    nav_layout = QHBoxLayout(nav_container)
    nav_layout.setContentsMargins(0, 0, 0, 0)
    nav_layout.setAlignment(Qt.AlignCenter)

    win.btn_prev_page = QPushButton("PREVIOUS")
    win.page_input = QSpinBox()
    win.page_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
    win.page_input.setMinimum(0)
    win.page_input.setMaximum(0)
    win.page_input.setFixedWidth(NAV_SPINBOX_WIDTH)
    win.page_input.setAlignment(Qt.AlignCenter)
    win.page_input.setKeyboardTracking(False)
    win.page_input.setSuffix(" / 0")
    win.btn_next_page = QPushButton("NEXT")

    nav_layout.addWidget(win.btn_prev_page)
    nav_layout.addWidget(win.page_input)
    nav_layout.addWidget(win.btn_next_page)

    win.active_features_label = QLabel("Active Features")
    win.active_features_label.setAlignment(Qt.AlignCenter)
    win.active_features_label.setFocusPolicy(Qt.NoFocus)
    win.active_features_label.setEnabled(False)
    win.active_features_label.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
    win.active_features_label.setAutoFillBackground(True)
    win.active_features_label.setBackgroundRole(QPalette.Base)
    win.active_features_label.setFixedWidth(PAGE_INFO_LABEL_WIDTH)
    win.active_features_label.setTextInteractionFlags(
        Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
    )

    page_layout.addWidget(win.page_info_label, 1)
    page_layout.addStretch(0)
    page_layout.addWidget(nav_container)
    page_layout.addStretch(0)
    page_layout.addWidget(win.active_features_label, 1)

    layout.addWidget(page_controls)
    win.left_tabs.addTab(tab, "Preview")
