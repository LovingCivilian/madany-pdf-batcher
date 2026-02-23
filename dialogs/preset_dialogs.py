"""
Preset Dialogs for PDF Batch Text Inserter.

Provides UI dialogs for:
- SavePresetDialog: Save current settings as a new preset
- LoadPresetDialog: Browse and load existing presets
- ManagePresetsDialog: Rename, delete, update, import/export presets
"""

from __future__ import annotations
import os
import platform
import subprocess
from datetime import datetime
from typing import Optional, Tuple, Callable

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox,
    QMessageBox, QFileDialog, QSplitter, QWidget,
    QAbstractItemView, QInputDialog, QLayout,
    QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

from core.preset_manager import PresetManager, Preset

BLACK_CIRCLE = "●"


# ============================================================
# SHARED HELPER: NATIVE PRESET DETAILS WIDGET
# ============================================================


class PresetDetailsWidget(QTreeWidget):
    """
    Native QTreeWidget-based preset details viewer.
    Automatically follows system theme.
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setIndentation(20)
        self.setAnimated(True)
        self.setExpandsOnDoubleClick(True)
        
        # Password visibility state
        self._password_visible = False
        self._password_item = None
        self._actual_password = ""
        
        # Allow text selection/copy
        self.setSelectionMode(QAbstractItemView.NoSelection)
        
        # Three columns: label, value, action button
        self.setColumnCount(3)
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setVisible(False)
    
    def clear_details(self):
        """Clear all items."""
        self.clear()
        self._password_visible = False
        self._password_item = None
        self._actual_password = ""
    
    def show_error(self, message: str):
        """Display an error message."""
        self.clear_details()
        item = QTreeWidgetItem(["Error", message])
        item.setForeground(0, QColor("#c62828"))
        self.addTopLevelItem(item)
    
    def _toggle_password_visibility(self):
        """Toggle password visibility."""
        if not self._password_item:
            return
        
        self._password_visible = not self._password_visible
        
        if self._password_visible:
            self._password_item.setText(1, self._actual_password)
            # Update button text
            btn = self.itemWidget(self._password_item, 2)
            if btn:
                btn.setText("Hide")
        else:
            self._password_item.setText(1, BLACK_CIRCLE * len(self._actual_password))
            btn = self.itemWidget(self._password_item, 2)
            if btn:
                btn.setText("Show")
    
    def show_preset(self, preset: Preset, filepath: str = ""):
        """Populate the tree with preset details."""
        self.clear_details()
        
        # Colors for status
        color_enabled = QColor("#2e7d32")   # Green
        color_disabled = QColor("#c62828")  # Red
        color_muted = QColor("#7f8c8d")     # Gray
        
        # Bold font for section headers
        bold_font = QFont()
        bold_font.setBold(True)
        
        def format_date(timestamp: float | None) -> str:
            if not timestamp:
                return "—"
            try:
                return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError, TypeError):
                return "Invalid Date"
        
        def add_section(title: str) -> QTreeWidgetItem:
            section = QTreeWidgetItem([title])
            section.setFont(0, bold_font)
            section.setExpanded(True)
            self.addTopLevelItem(section)
            return section
        
        def add_row(parent: QTreeWidgetItem, label: str, value: str, 
                    value_color: QColor = None, is_muted: bool = False):
            item = QTreeWidgetItem([label, value])
            if value_color:
                item.setForeground(1, value_color)
            elif is_muted:
                item.setForeground(1, color_muted)
            parent.addChild(item)
            return item
        
        def add_status_row(parent: QTreeWidgetItem, label: str, enabled: bool):
            status_text = "ENABLED" if enabled else "DISABLED"
            color = color_enabled if enabled else color_disabled
            item = QTreeWidgetItem([label, status_text])
            item.setForeground(1, color)
            font = item.font(1)
            font.setBold(True)
            item.setFont(1, font)
            parent.addChild(item)
            return item
        
        # ==========================
        # 1. METADATA SECTION
        # ==========================
        metadata_section = add_section("Metadata")
        
        if filepath:
            add_row(metadata_section, "File", os.path.basename(filepath))
        add_row(metadata_section, "Name", preset.name)
        add_row(metadata_section, "Created", format_date(preset.created))
        add_row(metadata_section, "Modified", format_date(preset.modified), 
                is_muted=(preset.modified is None))
        
        desc = preset.description if preset.description else "—"
        add_row(metadata_section, "Description", desc, 
                is_muted=(not preset.description))
        
        # ==========================
        # 2. FEATURES STATUS
        # ==========================
        features_section = add_section("Features Status")
        
        add_status_row(features_section, "Text Insertion", preset.text_insertion.enabled)
        add_status_row(features_section, "Timestamp Insertion", preset.timestamp_insertion.enabled)
        add_status_row(features_section, "Stamp Insertion", preset.stamp_insertion.enabled)
        add_status_row(features_section, "PDF Security", preset.pdf_security.enabled)
        
        # ==========================
        # 3. PDF SECURITY (if enabled)
        # ==========================
        sec = preset.pdf_security
        if sec.enabled:
            security_section = add_section("PDF Security Configuration")
            
            # Master password with show/hide toggle
            self._actual_password = sec.master_password
            masked_password = BLACK_CIRCLE * len(sec.master_password)
            self._password_item = QTreeWidgetItem(["Master Password", masked_password])
            security_section.addChild(self._password_item)
            
            # Add show/hide button
            btn_toggle = QPushButton("Show")
            btn_toggle.setFixedWidth(45)
            btn_toggle.clicked.connect(self._toggle_password_visibility)
            self.setItemWidget(self._password_item, 2, btn_toggle)
            
            # Permissions as a sub-section
            perms_item = QTreeWidgetItem(["Permissions"])
            perms_item.setExpanded(True)
            security_section.addChild(perms_item)
            
            permissions = [
                ("Print Document", sec.allow_print),
                ("Modify Document", sec.allow_modify),
                ("Copy Content", sec.allow_copy),
                ("Annotations", sec.allow_annotate),
                ("Fill Forms", sec.allow_form_fill),
                ("Assemble Document", sec.allow_assemble),
            ]
            
            for perm_label, allowed in permissions:
                status_text = "ENABLED" if allowed else "DISABLED"
                color = color_enabled if allowed else color_disabled
                perm_item = QTreeWidgetItem([perm_label, status_text])
                perm_item.setForeground(1, color)
                font = perm_item.font(1)
                font.setBold(True)
                perm_item.setFont(1, font)
                perms_item.addChild(perm_item)
        
        # Expand all by default
        self.expandAll()


# ============================================================
# DIALOGS
# ============================================================

class SavePresetDialog(QDialog):
    """
    Dialog for saving current settings as a preset.
    
    Allows user to enter:
    - Preset name (required)
    - Description (optional)
    """
    
    presetSaved = Signal(str)  # Emits preset name

    def __init__(self, preset_manager: PresetManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.preset_manager = preset_manager
        
        # Output attributes
        self.final_name: str = ""
        self.final_description: str = ""

        self.setWindowTitle("Save Preset")
        self.setModal(True)
        
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        # Forces the dialog to resize to fit its contents exactly and prevents manual resizing
        main_layout.setSizeConstraint(QLayout.SetFixedSize)
        
        # --- Group: Preset Information ---
        info_group = QGroupBox("Preset Information")
        info_layout = QVBoxLayout(info_group)
        
        # Name Input
        name_input_layout = QHBoxLayout()
        name_input_layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter a unique name...")
        self.name_edit.textChanged.connect(self._validate_name)
        self.name_edit.setMinimumWidth(300)
        name_input_layout.addWidget(self.name_edit)
        
        info_layout.addLayout(name_input_layout)
        
        # Validation Feedback
        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("color: #cc0000; font-size: 11px;")
        info_layout.addWidget(self.validation_label)
        
        # Description Input
        info_layout.addWidget(QLabel("Description (optional):"))
        self.description_edit = QTextEdit()
        self.description_edit.setMinimumHeight(100)
        self.description_edit.setPlaceholderText("Enter an optional description...")
        info_layout.addWidget(self.description_edit)
        
        main_layout.addWidget(info_group)
        
        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.save_button = QPushButton("Save")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._on_save_clicked)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def _validate_name(self, text: str):
        """Validate preset name and update UI accordingly."""
        name = text.strip()
        
        if not name:
            self.validation_label.setText("")
            self.save_button.setEnabled(False)
            return
        
        if self.preset_manager.preset_exists(name):
            # Block duplicate names
            self.validation_label.setText(f"⚠ Preset '{name}' already exists. Please choose a different name.")
            self.save_button.setEnabled(False)
        else:
            self.validation_label.setText("")
            self.save_button.setEnabled(True)

    def _on_save_clicked(self):
        """Handle save button click."""
        name = self.name_edit.text().strip()
        if not name:
            return
            
        self.final_name = name
        self.final_description = self.description_edit.toPlainText().strip()
        self.accept()

    def get_preset_info(self) -> Tuple[str, str]:
        """Return (name, description) after dialog is accepted."""
        return self.final_name, self.final_description


class LoadPresetDialog(QDialog):
    """
    Dialog for loading a preset.
    
    Shows list of available presets with preview of settings.
    Allows loading from presets folder or importing from file.
    """
    
    presetSelected = Signal(str)  # Emits preset name

    def __init__(self, preset_manager: PresetManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.preset_manager = preset_manager
        self.selected_preset_name: Optional[str] = None
        
        self.setWindowTitle("Load Preset")
        # Unified Size
        self.setFixedSize(850, 600)
        self.setModal(True)
        
        self._setup_ui()
        self._load_preset_list()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- Main Splitter ---
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left Group: Available Presets
        left_group = QGroupBox("Available Presets")
        left_layout = QVBoxLayout(left_group)
        
        self.preset_list_widget = QListWidget()
        self.preset_list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.preset_list_widget.currentItemChanged.connect(self._on_selection_changed)
        self.preset_list_widget.itemDoubleClicked.connect(self._on_load_clicked)
        left_layout.addWidget(self.preset_list_widget)
        
        main_splitter.addWidget(left_group)
        
        # Right Group: Details
        right_group = QGroupBox("Preset Details")
        right_layout = QVBoxLayout(right_group)
        
        self.preview_widget = PresetDetailsWidget()
        right_layout.addWidget(self.preview_widget)
        
        main_splitter.addWidget(right_group)
        main_splitter.setSizes([300, 550])
        
        main_layout.addWidget(main_splitter)
        
        # --- Bottom Buttons ---
        bottom_button_layout = QHBoxLayout()
        bottom_button_layout.addStretch()
        
        # Action Buttons (Right)
        self.load_button = QPushButton("Load")
        self.load_button.setEnabled(False)
        self.load_button.clicked.connect(self._on_load_clicked)
        bottom_button_layout.addWidget(self.load_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        bottom_button_layout.addWidget(cancel_button)
        
        main_layout.addLayout(bottom_button_layout)

    def _load_preset_list(self):
        """Refresh the list of available presets."""
        self.preset_list_widget.clear()
        self.preview_widget.clear_details()
        
        presets = self.preset_manager.list_presets()
        
        if not presets:
            item = QListWidgetItem("(No presets found)")
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.preset_list_widget.addItem(item)
            return
        
        for preset_info in presets:
            item = QListWidgetItem(preset_info["name"])
            item.setData(Qt.UserRole, preset_info)
            
            # Use 'is_valid' flag instead of version check
            if not preset_info.get("is_valid", True):
                item.setForeground(Qt.red)
                item.setToolTip("Invalid or corrupted preset file")
            
            self.preset_list_widget.addItem(item)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Handle preset selection change."""
        if not current:
            self.load_button.setEnabled(False)
            self.preview_widget.clear_details()
            return
        
        preset_info = current.data(Qt.UserRole)
        if not preset_info:
            self.load_button.setEnabled(False)
            return
        
        # Use 'is_valid' flag instead of version check
        if not preset_info.get("is_valid", True):
            self.load_button.setEnabled(False)
            self.preview_widget.show_error("Invalid preset file.\n\nThis file may be corrupted or not a valid preset.")
            return
        
        self.load_button.setEnabled(True)
        self.selected_preset_name = preset_info["name"]
        self._show_preset_preview(preset_info)

    def _show_preset_preview(self, preset_info: dict):
        """Display preset details in preview area."""
        preset, msg = self.preset_manager.load_preset(preset_info["name"])
        
        if preset is None:
            self.preview_widget.show_error(f"Error loading preview:\n{msg}")
            return
        
        self.preview_widget.show_preset(preset, preset_info.get('filepath', ''))

    def _on_load_clicked(self):
        """Handle load button click or double-click."""
        if self.selected_preset_name:
            self.accept()
            
    def get_selected_preset(self) -> Optional[str]:
        """Return selected preset name after dialog is accepted."""
        return self.selected_preset_name


class ManagePresetsDialog(QDialog):
    """
    Dialog for managing presets: rename, delete, update, import/export.
    """
    
    presetsChanged = Signal()  # Emitted when presets are modified

    # UPDATED: Swapped arguments back (parent before current_preset) to fix legacy calls
    def __init__(self, preset_manager: PresetManager, parent: Optional[QWidget] = None, 
                 current_preset: Optional[Preset] = None, 
                 default_preset_name: str | None = None,
                 on_default_change: Callable[[str | None], None] = None):
        super().__init__(parent)
        self.preset_manager = preset_manager
        self.current_preset = current_preset
        self.default_preset_name = default_preset_name
        self.on_default_change = on_default_change
        
        self.setWindowTitle("Manage Presets")
        # Unified Size
        self.setFixedSize(850, 600)
        self.setModal(True)
        
        self._setup_ui()
        self._load_preset_list()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- Main Splitter ---
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left Group: Available Presets
        left_group = QGroupBox("Available Presets")
        left_layout = QVBoxLayout(left_group)
        
        self.preset_list_widget = QListWidget()
        self.preset_list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.preset_list_widget.currentItemChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.preset_list_widget)
        
        # Open Folder button under the list
        open_folder_button = QPushButton("Open Presets Folder")
        open_folder_button.clicked.connect(self._on_open_folder_clicked)
        left_layout.addWidget(open_folder_button)
        
        main_splitter.addWidget(left_group)
        
        # Right Side Container (Holds multiple groups)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Group 1: Actions
        actions_group = QGroupBox("Actions")
        actions_grid = QGridLayout(actions_group)
        
        self.rename_button = QPushButton("Rename")
        self.rename_button.clicked.connect(self._on_rename_clicked)
        self.rename_button.setEnabled(False)
        actions_grid.addWidget(self.rename_button, 0, 0)
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._on_delete_clicked)
        self.delete_button.setEnabled(False)
        actions_grid.addWidget(self.delete_button, 0, 1)
        
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self._on_export_clicked)
        self.export_button.setEnabled(False)
        actions_grid.addWidget(self.export_button, 1, 0)
        
        self.duplicate_button = QPushButton("Duplicate")
        self.duplicate_button.clicked.connect(self._on_duplicate_clicked)
        self.duplicate_button.setEnabled(False)
        actions_grid.addWidget(self.duplicate_button, 1, 1)
        
        self.update_button = QPushButton("Update")
        self.update_button.clicked.connect(self._on_update_clicked)
        self.update_button.setEnabled(False)
        actions_grid.addWidget(self.update_button, 2, 0)

        # NEW BUTTON: Set as Default
        self.set_default_button = QPushButton("Set as Default")
        self.set_default_button.clicked.connect(self._on_set_default_clicked)
        self.set_default_button.setEnabled(False)
        actions_grid.addWidget(self.set_default_button, 2, 1)
        
        right_layout.addWidget(actions_group)
        
        # Group 2: Import
        import_group = QGroupBox("Import")
        import_layout = QHBoxLayout(import_group)
        
        import_button = QPushButton("Import from File")
        import_button.clicked.connect(self._on_import_clicked)
        import_layout.addWidget(import_button)
        
        right_layout.addWidget(import_group)
        
        # Group 3: Details
        details_group = QGroupBox("Preset Details")
        details_layout = QVBoxLayout(details_group)
        
        self.details_widget = PresetDetailsWidget()
        details_layout.addWidget(self.details_widget)
        
        right_layout.addWidget(details_group)
        
        main_splitter.addWidget(right_container)
        main_splitter.setSizes([300, 550])
        
        main_layout.addWidget(main_splitter)
        
        # --- Bottom Buttons ---
        bottom_button_layout = QHBoxLayout()
        bottom_button_layout.addStretch()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._load_preset_list)
        bottom_button_layout.addWidget(self.refresh_button)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        bottom_button_layout.addWidget(close_button)
        
        main_layout.addLayout(bottom_button_layout)

    def _load_preset_list(self):
        """Refresh the list of presets."""
        self.preset_list_widget.clear()
        self.details_widget.clear_details()
        self._update_action_buttons(enabled=False)
        
        presets = self.preset_manager.list_presets()
        
        if not presets:
            item = QListWidgetItem("(No presets found)")
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.preset_list_widget.addItem(item)
            return
        
        for preset_info in presets:
            name = preset_info["name"]
            display_text = name
            
            # Check if this is the default preset
            if name == self.default_preset_name:
                display_text += " (Default)"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, preset_info)
            
            # Use 'is_valid' flag instead of version check
            if not preset_info.get("is_valid", True):
                item.setForeground(Qt.red)
                item.setToolTip("Invalid or corrupted preset file")
            
            self.preset_list_widget.addItem(item)

    def _update_action_buttons(self, enabled: bool):
        """Batch enable/disable action buttons."""
        self.rename_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)
        self.export_button.setEnabled(enabled)
        self.duplicate_button.setEnabled(enabled)
        self.update_button.setEnabled(enabled and self.current_preset is not None)
        
        # Logic for Set/Remove Default button:
        # Always enable if item selected, but change text based on default status
        selected_name = self._get_selected_name()
        is_current_default = (selected_name == self.default_preset_name) if selected_name else False
        
        self.set_default_button.setEnabled(enabled)
        if is_current_default:
            self.set_default_button.setText("Remove Default")
        else:
            self.set_default_button.setText("Set as Default")

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Handle preset selection change."""
        if not current:
            self._update_action_buttons(enabled=False)
            self.details_widget.clear_details()
            return
        
        preset_info = current.data(Qt.UserRole)
        if not preset_info:
            self._update_action_buttons(enabled=False)
            return
        
        # Use 'is_valid' flag instead of version check
        if not preset_info.get("is_valid", True):
            self._update_action_buttons(enabled=False)
            return
        
        self._update_action_buttons(enabled=True)
        self._show_details(preset_info)

    def _show_details(self, preset_info: dict):
        """Show preset details in the details widget."""
        preset, msg = self.preset_manager.load_preset(preset_info["name"])
        
        if preset is None:
            self.details_widget.show_error(f"Error loading preset:\n{msg}")
            return
        
        self.details_widget.show_preset(preset, preset_info.get('filepath', ''))

    def _get_selected_name(self) -> Optional[str]:
        """Get currently selected preset name."""
        item = self.preset_list_widget.currentItem()
        if not item:
            return None
        
        preset_info = item.data(Qt.UserRole)
        if not preset_info:
            return None
        
        return preset_info.get("name")

    def _on_rename_clicked(self):
        """Rename selected preset."""
        old_name = self._get_selected_name()
        if not old_name:
            return
        
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Preset",
            "Enter new name:",
            text=old_name
        )
        
        if not ok or not new_name.strip():
            return
        
        new_name = new_name.strip()
        if new_name == old_name:
            return
        
        success, msg = self.preset_manager.rename_preset(old_name, new_name)
        
        if success:
            # If renamed preset was default, update local default name
            if self.default_preset_name == old_name:
                self.default_preset_name = new_name
                # Notify main app
                if self.on_default_change:
                    self.on_default_change(new_name)
            
            QMessageBox.information(self, "Renamed", msg)
            self._load_preset_list()
            self.presetsChanged.emit()
        else:
            QMessageBox.warning(self, "Rename Failed", msg)

    def _on_delete_clicked(self):
        """Delete selected preset."""
        name = self._get_selected_name()
        if not name:
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete preset '{name}'?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        success, msg = self.preset_manager.delete_preset(name)
        
        if success:
            # If deleted preset was default, clear local default
            if self.default_preset_name == name:
                self.default_preset_name = None
                # Notify main app
                if self.on_default_change:
                    self.on_default_change(None)
            
            self._load_preset_list()
            self.presetsChanged.emit()
        else:
            QMessageBox.warning(self, "Delete Failed", msg)

    def _on_export_clicked(self):
        """Export selected preset to file."""
        name = self._get_selected_name()
        if not name:
            return
        
        default_filename = self.preset_manager.sanitize_filename(name) + ".json"
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Preset",
            default_filename,
            "Preset Files (*.json);;All Files (*)"
        )
        
        if not filepath:
            return
        
        success, msg = self.preset_manager.export_preset(name, filepath)
        
        if success:
            QMessageBox.information(self, "Export Successful", msg)
        else:
            QMessageBox.warning(self, "Export Failed", msg)

    def _on_duplicate_clicked(self):
        """Duplicate selected preset with new name."""
        name = self._get_selected_name()
        if not name:
            return
        
        new_name, ok = QInputDialog.getText(
            self,
            "Duplicate Preset",
            "Enter name for the copy:",
            text=f"{name} (Copy)"
        )
        
        if not ok or not new_name.strip():
            return
        
        new_name = new_name.strip()
        
        if self.preset_manager.preset_exists(new_name):
            QMessageBox.warning(
                self,
                "Name Exists",
                f"Preset '{new_name}' already exists. Choose a different name."
            )
            return
        
        # Load original, change name, save as new
        preset, msg = self.preset_manager.load_preset(name)
        if preset is None:
            QMessageBox.warning(self, "Error", msg)
            return
        
        preset.name = new_name
        # UPDATE: Correctly initialize timestamps for new copy
        preset.created = datetime.now().timestamp()
        preset.modified = None
        
        success, msg = self.preset_manager.save_preset(preset)
        
        if success:
            QMessageBox.information(self, "Duplicated", f"Created '{new_name}'")
            self._load_preset_list()
            self.presetsChanged.emit()
        else:
            QMessageBox.warning(self, "Duplicate Failed", msg)

    def _on_update_clicked(self):
        """Update selected preset with current settings."""
        name = self._get_selected_name()
        if not name or not self.current_preset:
            return

        # 1. Ask for confirmation
        reply = QMessageBox.question(
            self,
            "Confirm Update",
            f"Are you sure you want to update preset '{name}' with the current settings?\n\nThis will overwrite the existing configuration.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return

        # 2. Perform Update
        # Load existing to get original creation date
        old_preset, _ = self.preset_manager.load_preset(name)
        original_created = old_preset.created if old_preset else 0.0

        # Clone current settings
        new_preset = Preset.from_dict(self.current_preset.to_dict())
        new_preset.name = name
        new_preset.created = original_created
        # Note: Modified timestamp is handled automatically by save_preset when overwriting

        success, msg = self.preset_manager.save_preset(new_preset, overwrite=True)
        
        if success:
             # 3. Show Success Confirmation
             QMessageBox.information(self, "Updated", f"Preset '{name}' updated successfully.")
             self._load_preset_list()
             self.presetsChanged.emit()
        else:
             QMessageBox.warning(self, "Update Failed", msg)

    def _on_set_default_clicked(self):
        """Toggle default status for the selected preset."""
        name = self._get_selected_name()
        if not name:
            return
        
        is_current_default = (name == self.default_preset_name)
        
        if is_current_default:
            # Remove default
            if self.on_default_change:
                self.on_default_change(None)
            self.default_preset_name = None
            self._load_preset_list()
            QMessageBox.information(self, "Default Removed", "No preset will be loaded on startup.")
        else:
            # Set as default
            if self.on_default_change:
                self.on_default_change(name)
            self.default_preset_name = name
            self._load_preset_list()
            QMessageBox.information(self, "Default Set", f"'{name}' will now load on startup.")

    def _on_import_clicked(self):
        """Import preset from file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import Preset",
            "",
            "Preset Files (*.json);;All Files (*)"
        )
        
        if not filepath:
            return
        
        success, msg = self.preset_manager.import_preset(filepath)
        
        if success:
            QMessageBox.information(self, "Import Successful", msg)
            self._load_preset_list()
            self.presetsChanged.emit()
        else:
            QMessageBox.warning(self, "Import Failed", msg)

    def _on_open_folder_clicked(self):
        """Open presets folder in file manager."""
        folder = self.preset_manager.presets_folder
        
        if not os.path.exists(folder):
            os.makedirs(folder)
        
        current_platform = platform.system()
        
        try:
            if current_platform == "Windows":
                os.startfile(folder)
            elif current_platform == "Darwin":
                subprocess.run(["open", folder], check=True)
            else:
                subprocess.run(["xdg-open", folder], check=True)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open folder:\n{folder}\n\nError: {e}"
            )