"""Toolbar setup for the main window."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QToolBar
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def setup_toolbar(win: MainWindow) -> None:
    """Create the main toolbar with preset, help, and theme actions."""
    toolbar = QToolBar("Main Toolbar")
    toolbar.setMovable(False)
    toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
    win.addToolBar(Qt.TopToolBarArea, toolbar)

    win.action_load_preset = QAction("Load Preset", win)
    win.action_load_preset.setStatusTip("Load a saved configuration")
    win.action_load_preset.triggered.connect(lambda: win.load_preset())
    toolbar.addAction(win.action_load_preset)

    win.action_save_preset = QAction("Save Preset", win)
    win.action_save_preset.setStatusTip("Save current configuration")
    win.action_save_preset.triggered.connect(lambda: win.save_preset())
    toolbar.addAction(win.action_save_preset)

    win.action_manage_presets = QAction("Manage Presets", win)
    win.action_manage_presets.setStatusTip("Manage existing presets")
    win.action_manage_presets.triggered.connect(lambda: win.manage_presets())
    toolbar.addAction(win.action_manage_presets)

    win.action_manage_substitutions = QAction("Manage Substitutions", win)
    win.action_manage_substitutions.setStatusTip("Manage substitution definitions")
    win.action_manage_substitutions.triggered.connect(lambda: win.manage_substitutions())
    toolbar.addAction(win.action_manage_substitutions)

    toolbar.addSeparator()

    win.action_documentation = QAction("Documentation", win)
    win.action_documentation.setStatusTip("Help Documentation")
    toolbar.addAction(win.action_documentation)

    win.action_about = QAction("About", win)
    win.action_about.setStatusTip("About")
    toolbar.addAction(win.action_about)

    toolbar.addSeparator()

    win.action_toggle_theme = QAction("Dark Mode", win)
    win.action_toggle_theme.setStatusTip("Toggle between Light and Dark themes")
    win.action_toggle_theme.triggered.connect(lambda: win.toggle_theme())
