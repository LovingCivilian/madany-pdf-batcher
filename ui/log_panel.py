"""Log tab setup and message helpers."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QMessageBox,
)

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def setup_log_tab(win: MainWindow) -> None:
    """Create the Log tab with a read-only text viewer."""
    tab = QWidget()
    layout = QVBoxLayout(tab)
    win.log_viewer = QTextEdit()
    win.log_viewer.setReadOnly(True)
    layout.addWidget(win.log_viewer)
    win.left_tabs.addTab(tab, "Log")


def append_log(win: MainWindow, msg: str) -> None:
    """Append a message to the log viewer with auto-scroll."""
    if win.log_viewer:
        win.log_viewer.append(msg)
    else:
        print(msg)


def show_info(win: MainWindow, title: str, message: str) -> None:
    """Show an information message box."""
    QMessageBox.information(win, title, message)


def show_warning(win: MainWindow, title: str, message: str) -> None:
    """Show a warning message box."""
    QMessageBox.warning(win, title, message)


def show_error(win: MainWindow, title: str, message: str) -> None:
    """Show a critical error message box."""
    QMessageBox.critical(win, title, message)
