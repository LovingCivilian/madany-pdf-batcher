"""Dialog for managing substitution definitions."""
from __future__ import annotations

import re
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QWidget, QAbstractItemView,
)
from PySide6.QtCore import Qt

from core.constants import SUBSTITUTION_DEFINITIONS
from core.substitution_loader import save_substitution_definitions


class ManageSubstitutionsDialog(QDialog):
    """Dialog to add, edit, remove, and restore substitution definitions."""

    def __init__(
        self,
        definitions: list[dict],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Manage Substitutions")
        self.setMinimumSize(700, 450)
        self.setModal(True)

        # Work on a deep copy so Cancel discards changes
        self._definitions = [d.copy() for d in definitions]
        self._saved = False

        self._setup_ui()
        self._populate_table()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Description", "Regex"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.table)

        # Row action buttons
        row_btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add")
        self.btn_add.clicked.connect(self._on_add)
        row_btn_layout.addWidget(self.btn_add)

        self.btn_remove = QPushButton("Remove")
        self.btn_remove.clicked.connect(self._on_remove)
        row_btn_layout.addWidget(self.btn_remove)

        self.btn_restore = QPushButton("Restore Defaults")
        self.btn_restore.clicked.connect(self._on_restore_defaults)
        row_btn_layout.addWidget(self.btn_restore)

        row_btn_layout.addStretch()
        layout.addLayout(row_btn_layout)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self._on_save)
        bottom_layout.addWidget(self.btn_save)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(self.btn_cancel)

        layout.addLayout(bottom_layout)

    # ----------------------------------------------------------- helpers
    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        for d in self._definitions:
            self._add_row(d["name"], d["description"], d["regex"])

    def _add_row(self, name: str = "", desc: str = "", regex: str = "") -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(desc))
        self.table.setItem(row, 2, QTableWidgetItem(regex))

    def _read_table(self) -> list[dict]:
        result: list[dict] = []
        for row in range(self.table.rowCount()):
            name = (self.table.item(row, 0).text() or "").strip()
            desc = (self.table.item(row, 1).text() or "").strip()
            regex = (self.table.item(row, 2).text() or "").strip()
            result.append({"name": name, "description": desc, "regex": regex})
        return result

    # ----------------------------------------------------------- slots
    def _on_add(self) -> None:
        self._add_row()
        new_row = self.table.rowCount() - 1
        self.table.setCurrentCell(new_row, 0)
        self.table.editItem(self.table.item(new_row, 0))

    def _on_remove(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        name = (self.table.item(row, 0).text() or "").strip() or "(unnamed)"
        reply = QMessageBox.question(
            self,
            "Confirm Remove",
            f"Remove substitution '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.table.removeRow(row)

    def _on_restore_defaults(self) -> None:
        reply = QMessageBox.question(
            self,
            "Restore Defaults",
            "Reset all substitutions to the built-in defaults?\n\nThis will discard your current entries.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._definitions = [d.copy() for d in SUBSTITUTION_DEFINITIONS]
            self._populate_table()

    def _on_save(self) -> None:
        entries = self._read_table()
        errors: list[str] = []

        for i, entry in enumerate(entries, start=1):
            if not entry["name"]:
                errors.append(f"Row {i}: Name is empty.")
            try:
                re.compile(entry["regex"])
            except re.error as exc:
                errors.append(f"Row {i} ({entry['name'] or '?'}): Invalid regex — {exc}")

        if errors:
            QMessageBox.warning(
                self,
                "Validation Errors",
                "\n".join(errors),
            )
            return

        self._definitions = entries
        save_substitution_definitions(entries)
        self._saved = True
        self.accept()

    # -------------------------------------------------------- public API
    def get_definitions(self) -> list[dict]:
        """Return the final definitions (meaningful only after accept)."""
        return self._definitions

    def was_saved(self) -> bool:
        return self._saved
