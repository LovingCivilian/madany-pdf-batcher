"""
Substitution Picker Widget

A button widget that shows a popup menu of available substitution placeholders.
Uses native Qt components for proper theme integration.
"""

from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import (
    QPushButton, QMenu, QTextEdit, QLineEdit,
)
from PySide6.QtGui import QAction


class SubstitutionPickerButton(QPushButton):
    """
    A button that, when clicked, shows a native popup menu of available
    substitution placeholders. Selected placeholders are inserted
    into the associated text widget at the cursor position.
    """

    def __init__(
        self,
        text_widget: Optional[QTextEdit | QLineEdit] = None,
        definitions: list[dict] | None = None,
        parent=None
    ):
        super().__init__("Insert Substitution", parent)

        self.text_widget = text_widget
        self.setCursor(Qt.PointingHandCursor)

        # Create native menu
        self.menu = QMenu(self)

        if definitions is not None:
            self._definitions = definitions
        else:
            from core.substitution_loader import load_substitution_definitions
            self._definitions = load_substitution_definitions()

        self._build_menu()

        # Connect click to show menu
        self.clicked.connect(self._show_menu)

    def update_definitions(self, definitions: list[dict]) -> None:
        """Rebuild the menu with new definitions."""
        self._definitions = definitions
        self._build_menu()

    def _build_menu(self):
        """Build the menu with all available placeholders using native QActions."""
        self.menu.clear()
        for sub in self._definitions:
            placeholder = f"${sub['name']}"
            description = sub["description"]
            action = QAction(f"{placeholder}  —  {description}", self.menu)
            action.setData(placeholder)
            action.triggered.connect(lambda checked, p=placeholder: self._insert_placeholder(p))
            self.menu.addAction(action)

    def set_text_widget(self, widget: QTextEdit | QLineEdit):
        """Set or update the associated text widget."""
        self.text_widget = widget

    def _show_menu(self):
        """Show the placeholder menu below the button."""
        # Position menu below the button
        pos = self.mapToGlobal(QPoint(0, self.height()))
        self.menu.popup(pos)

    def _insert_placeholder(self, placeholder: str):
        """Insert the selected placeholder into the text widget."""
        if self.text_widget is None:
            return

        if isinstance(self.text_widget, QTextEdit):
            # QTextEdit: insert at cursor
            cursor = self.text_widget.textCursor()
            cursor.insertText(placeholder)
            self.text_widget.setTextCursor(cursor)
            self.text_widget.setFocus()

        elif isinstance(self.text_widget, QLineEdit):
            # QLineEdit: insert at cursor position
            pos = self.text_widget.cursorPosition()
            current_text = self.text_widget.text()
            new_text = current_text[:pos] + placeholder + current_text[pos:]
            self.text_widget.setText(new_text)
            self.text_widget.setCursorPosition(pos + len(placeholder))
            self.text_widget.setFocus()
