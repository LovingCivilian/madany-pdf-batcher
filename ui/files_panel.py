"""Files tab: input/output folders, PDF tree, tree context menu, batch check ops."""
from __future__ import annotations

import os
from typing import Dict, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLineEdit,
    QPushButton, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QFileDialog, QApplication, QMenu, QFileIconProvider,
)
from PySide6.QtCore import Qt, QFileInfo

from core.constants import TREE_SIZE_COLUMN_WIDTH

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def setup_files_tab(win: MainWindow) -> None:
    """Create the Files tab with input/output folder controls and PDF tree."""
    tab = QWidget()
    layout = QVBoxLayout(tab)

    input_group = QGroupBox("Input Folder")
    input_layout = QHBoxLayout(input_group)
    win.input_path_entry = QLineEdit()
    win.input_path_entry.setReadOnly(True)
    win.btn_browse_input = QPushButton("Browse")
    input_layout.addWidget(win.input_path_entry)
    input_layout.addWidget(win.btn_browse_input)
    layout.addWidget(input_group)

    tree_group = QGroupBox("Found PDFs")
    tree_layout = QVBoxLayout(tree_group)
    win.pdf_tree = QTreeWidget()
    win.pdf_tree.setHeaderHidden(False)
    win.pdf_tree.setHeaderLabels(["Name", "Size"])
    header = win.pdf_tree.header()
    header.setSectionResizeMode(0, QHeaderView.Stretch)
    header.setSectionResizeMode(1, QHeaderView.Fixed)
    header.resizeSection(1, TREE_SIZE_COLUMN_WIDTH)
    header.setStretchLastSection(False)
    win.pdf_tree.setSelectionMode(QTreeWidget.ExtendedSelection)
    win.pdf_tree.setContextMenuPolicy(Qt.CustomContextMenu)
    win.pdf_tree.customContextMenuRequested.connect(
        lambda pos: show_tree_context_menu(win, pos)
    )
    win.pdf_tree.itemDoubleClicked.connect(
        lambda item, col: on_tree_item_double_clicked(win, item, col)
    )
    win.pdf_tree.setAnimated(True)
    tree_layout.addWidget(win.pdf_tree)
    layout.addWidget(tree_group, 1)

    output_group = QGroupBox("Output Folder")
    output_layout = QHBoxLayout(output_group)
    win.output_path_entry = QLineEdit()
    win.output_path_entry.setReadOnly(True)
    win.btn_browse_output = QPushButton("Browse")
    output_layout.addWidget(win.output_path_entry)
    output_layout.addWidget(win.btn_browse_output)
    layout.addWidget(output_group)

    win.btn_process_all = QPushButton("Process All PDFs")
    layout.addWidget(win.btn_process_all)

    win.right_tabs.addTab(tab, "Files")


def pick_input_folder(win: MainWindow) -> None:
    """Open folder dialog and populate PDF tree."""
    folder = QFileDialog.getExistingDirectory(win, "Select Input Folder")
    if folder:
        win.input_path_entry.setText(folder)
        populate_pdf_tree(win, folder)
        win.selected_pdf_paths = []
        win.current_file_index = -1
        win.close_current_doc()
        win.update_navigation_ui()


def pick_output_folder(win: MainWindow) -> None:
    """Open folder dialog for output selection."""
    folder = QFileDialog.getExistingDirectory(win, "Select Output Folder")
    if folder:
        win.output_path_entry.setText(folder)


def _prune_empty_folders(item: QTreeWidgetItem) -> bool:
    """Recursively remove tree items that contain no PDFs."""
    full_path = getattr(item, "full_path", "")
    if full_path.lower().endswith(".pdf"):
        return True
    children_to_remove = []
    has_pdfs = False
    for i in range(item.childCount()):
        child = item.child(i)
        if _prune_empty_folders(child):
            has_pdfs = True
        else:
            children_to_remove.append(child)
    for child in reversed(children_to_remove):
        index = item.indexOfChild(child)
        if index >= 0:
            item.takeChild(index)
    return has_pdfs


def populate_pdf_tree(win: MainWindow, folder_path: str) -> None:
    """Scan folder_path and build the PDF tree widget."""
    from ui.processing import create_progress_dialog

    win.pdf_tree.clear()

    total_items = 0
    for _, dirs, files in os.walk(folder_path):
        total_items += len([f for f in files if f.lower().endswith(".pdf")])
        total_items += len(dirs)

    progress = create_progress_dialog(
        win, "Loading Files", "Scanning folder...",
        total_items if total_items > 0 else 0,
    )
    progress.show()
    QApplication.processEvents()

    icon_provider = QFileIconProvider()
    stats = {"processed": 0, "pdf_count": 0, "valid_pdf_count": 0, "unknown_pdf_count": 0}

    root_item = QTreeWidgetItem([os.path.basename(folder_path) or folder_path, ""])
    root_item.full_path = folder_path
    root_item.setFlags(root_item.flags() | Qt.ItemIsUserCheckable)
    root_item.setCheckState(0, Qt.Unchecked)
    root_item.setIcon(0, icon_provider.icon(QFileInfo(folder_path)))
    root_item.setExpanded(True)
    win.pdf_tree.addTopLevelItem(root_item)

    def recursive_add(parent_item, current_path):
        try:
            entries = os.listdir(current_path)
        except PermissionError:
            return

        entries.sort(key=lambda x: (not os.path.isdir(os.path.join(current_path, x)), x.lower()))

        for entry in entries:
            if progress.was_canceled():
                return

            full_entry_path = os.path.join(current_path, entry)
            info = QFileInfo(full_entry_path)

            if os.path.isdir(full_entry_path):
                item = QTreeWidgetItem([entry, ""])
                item.full_path = full_entry_path
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Unchecked)
                item.setIcon(0, icon_provider.icon(info))
                item.setExpanded(True)
                parent_item.addChild(item)

                stats["processed"] += 1
                progress.set_value(stats["processed"])
                progress.set_label_text(f"Scanning: {entry}")
                QApplication.processEvents()
                recursive_add(item, full_entry_path)

            elif entry.lower().endswith(".pdf"):
                stats["pdf_count"] += 1
                size_str = format_size(info.size())
                item = QTreeWidgetItem([entry, size_str])
                item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                item.full_path = full_entry_path
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                progress.set_label_text(f"Checking PDF: {entry}")
                QApplication.processEvents()

                from ui.pdf_viewer import is_pdf_standard_size
                is_standard = is_pdf_standard_size(full_entry_path)

                item.setFlags(item.flags() | Qt.ItemIsEnabled)
                item.setCheckState(0, Qt.Unchecked)

                if is_standard:
                    stats["valid_pdf_count"] += 1
                else:
                    stats["unknown_pdf_count"] += 1

                item.setIcon(0, icon_provider.icon(info))
                parent_item.addChild(item)
                stats["processed"] += 1
                progress.set_value(stats["processed"])
                QApplication.processEvents()

    recursive_add(root_item, folder_path)
    was_canceled = progress.was_canceled()
    progress.close()

    _prune_empty_folders(root_item)
    win.pdf_tree.expandAll()

    _show_scan_summary(win, was_canceled, stats, folder_path)


def _show_scan_summary(win: MainWindow, canceled: bool, stats: Dict[str, int], folder_path: str) -> None:
    """Display scan results in a dialog."""
    from ui.log_panel import show_info, show_warning

    valid = stats["valid_pdf_count"]
    unknown = stats["unknown_pdf_count"]
    total = stats["pdf_count"]

    if canceled:
        title = "Scan Interrupted"
        body = (
            f"The scanning process was stopped by the user.\n\n"
            f"Partial Results:\n"
            f"\u2022 Scanned items: {stats['processed']}\n"
            f"\u2022 Found PDF files: {total}"
        )
        show_info(win, title, body)
        return

    if total == 0:
        show_warning(win, "No PDFs Found",
                     f"No PDF files were found in:\n{folder_path}\n\nPlease check the folder path and try again.")
        return

    title = "Scan Completed Successfully"
    body = (
        f"Folder scan complete!\n\n"
        f"Location: {folder_path}\n\n"
        f"Summary:\n"
        f"\u2022 Total PDFs Found: {total}\n"
        f"\u2022 Standard Sizes: {valid}\n"
        f"\u2022 Unknown/Custom Sizes: {unknown} (RED)\n\n"
        f"All files are ready to be processed."
    )
    show_info(win, title, body)


def on_tree_item_changed(win: MainWindow, item: QTreeWidgetItem, column: int) -> None:
    """Handle checkbox state changes with parent/child propagation."""
    if column != 0:
        return
    win.pdf_tree.blockSignals(True)
    state = item.checkState(0)

    def set_descendants(parent, s):
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.flags() & Qt.ItemIsEnabled:
                child.setCheckState(0, s)
                set_descendants(child, s)

    if item.childCount() > 0:
        set_descendants(item, state)

    def update_parents(child):
        parent = child.parent()
        while parent:
            children = [parent.child(i) for i in range(parent.childCount())
                        if (parent.child(i).flags() & Qt.ItemIsEnabled)]
            total = len(children)
            checked = sum(ch.checkState(0) == Qt.Checked for ch in children)
            unchecked = sum(ch.checkState(0) == Qt.Unchecked for ch in children)

            if checked == total:
                parent.setCheckState(0, Qt.Checked)
            elif unchecked == total:
                parent.setCheckState(0, Qt.Unchecked)
            else:
                parent.setCheckState(0, Qt.PartiallyChecked)
            child = parent
            parent = parent.parent()

    update_parents(item)
    win.pdf_tree.blockSignals(False)

    if not win._suppress_list_update:
        refresh_selected_files_list(win)


def show_tree_context_menu(win: MainWindow, position) -> None:
    """Show right-click context menu for the PDF tree."""
    from PySide6.QtGui import QAction

    menu = QMenu()
    has_selection = bool(win.pdf_tree.selectedItems())
    has_items = win.pdf_tree.topLevelItemCount() > 0

    check_action = QAction("Check Selected", win)
    uncheck_action = QAction("Uncheck Selected", win)
    check_action.triggered.connect(lambda: _batch_set_check_state(win, Qt.Checked))
    uncheck_action.triggered.connect(lambda: _batch_set_check_state(win, Qt.Unchecked))
    check_action.setEnabled(has_selection)
    uncheck_action.setEnabled(has_selection)
    menu.addAction(check_action)
    menu.addAction(uncheck_action)

    menu.addSeparator()

    select_all_action = QAction("Check All", win)
    unselect_all_action = QAction("Uncheck All", win)
    select_all_action.triggered.connect(lambda: _set_all_check_state(win, Qt.Checked))
    unselect_all_action.triggered.connect(lambda: _set_all_check_state(win, Qt.Unchecked))
    select_all_action.setEnabled(has_items)
    unselect_all_action.setEnabled(has_items)
    menu.addAction(select_all_action)
    menu.addAction(unselect_all_action)

    menu.addSeparator()

    reverse_action = QAction("Reverse Checked", win)
    reverse_action.triggered.connect(lambda: _reverse_selection(win))
    reverse_action.setEnabled(has_items)
    menu.addAction(reverse_action)

    menu.exec(win.pdf_tree.viewport().mapToGlobal(position))


def on_tree_item_double_clicked(win: MainWindow, item: QTreeWidgetItem, column: int) -> None:
    """Open PDF on double-click if it's checked and selected."""
    full_path = getattr(item, "full_path", None)
    if not full_path or not full_path.lower().endswith(".pdf"):
        return

    if item.checkState(0) == Qt.Checked:
        if full_path in win.selected_pdf_paths:
            index = win.selected_pdf_paths.index(full_path)
            if index != win.current_file_index:
                win.open_pdf_at_index(index)


def _batch_set_check_state(win: MainWindow, state) -> None:
    """Set check state for all selected tree items."""
    items = win.pdf_tree.selectedItems()
    if not items:
        return
    win._suppress_list_update = True
    try:
        for item in items:
            if item.flags() & Qt.ItemIsUserCheckable:
                if item.checkState(0) != state:
                    item.setCheckState(0, state)
    finally:
        win._suppress_list_update = False
    refresh_selected_files_list(win)


def _set_all_check_state(win: MainWindow, state) -> None:
    """Set check state for all leaf items in the tree."""
    win._suppress_list_update = True
    try:
        def apply_to_leaves(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.childCount() > 0:
                    apply_to_leaves(child)
                elif child.flags() & Qt.ItemIsUserCheckable:
                    if child.checkState(0) != state:
                        child.setCheckState(0, state)
        for i in range(win.pdf_tree.topLevelItemCount()):
            apply_to_leaves(win.pdf_tree.topLevelItem(i))
    finally:
        win._suppress_list_update = False
    refresh_selected_files_list(win)


def _reverse_selection(win: MainWindow) -> None:
    """Toggle check state for all leaf items in the tree."""
    win._suppress_list_update = True
    try:
        def flip_leaves(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.childCount() > 0:
                    flip_leaves(child)
                elif child.flags() & Qt.ItemIsUserCheckable:
                    current = child.checkState(0)
                    if current == Qt.Checked:
                        child.setCheckState(0, Qt.Unchecked)
                    elif current == Qt.Unchecked:
                        child.setCheckState(0, Qt.Checked)
        for i in range(win.pdf_tree.topLevelItemCount()):
            flip_leaves(win.pdf_tree.topLevelItem(i))
    finally:
        win._suppress_list_update = False
    refresh_selected_files_list(win)


def refresh_selected_files_list(win: MainWindow) -> None:
    """Rebuild the selected PDF paths list from checked tree items."""
    new_list = []

    def traverse(item):
        for i in range(item.childCount()):
            child = item.child(i)
            full_path = getattr(child, "full_path", None)
            if full_path and full_path.lower().endswith(".pdf"):
                if child.checkState(0) == Qt.Checked:
                    new_list.append(full_path)
            traverse(child)

    for i in range(win.pdf_tree.topLevelItemCount()):
        traverse(win.pdf_tree.topLevelItem(i))

    old_list = win.selected_pdf_paths
    old_index = win.current_file_index

    win.selected_pdf_paths = new_list

    if not win.selected_pdf_paths:
        win.current_file_index = -1
        win.close_current_doc()
        win.update_navigation_ui()
        return

    if 0 <= old_index < len(old_list):
        old_path = old_list[old_index]
        if old_path in win.selected_pdf_paths:
            win.current_file_index = win.selected_pdf_paths.index(old_path)
            win.update_navigation_ui()
            return

    nearest_index = max(0, min(old_index, len(win.selected_pdf_paths) - 1))
    win.current_file_index = nearest_index
    win.open_pdf_at_index(win.current_file_index)


def format_size(size_bytes: int) -> str:
    """Format a byte count into a human-readable string."""
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
