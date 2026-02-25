"""File/page navigation logic and UI state updates."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QTreeWidgetItem

from core.constants import detect_paper_key, KEY_TO_LABEL

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def goto_prev_file(win: MainWindow) -> None:
    """Navigate to the previous file in the selected list."""
    if win.current_file_index > 0:
        win.open_pdf_at_index(win.current_file_index - 1)


def goto_next_file(win: MainWindow) -> None:
    """Navigate to the next file in the selected list."""
    if win.current_file_index < len(win.selected_pdf_paths) - 1:
        win.open_pdf_at_index(win.current_file_index + 1)


def goto_prev_page(win: MainWindow) -> None:
    """Navigate to the previous page of the current document."""
    if win.current_page_index > 0:
        win.current_page_index -= 1
        win.render_current_page()
        win.update_navigation_ui()


def goto_next_page(win: MainWindow) -> None:
    """Navigate to the next page of the current document."""
    if win.current_page_index < win.current_page_count - 1:
        win.current_page_index += 1
        win.render_current_page()
        win.update_navigation_ui()


def update_navigation_ui(win: MainWindow) -> None:
    """Update all navigation buttons, spinboxes, and labels to match current state."""
    total_files = len(win.selected_pdf_paths)
    has_files = total_files > 0
    has_doc = win.current_doc is not None

    win.btn_prev_file.setEnabled(has_files and win.current_file_index > 0)
    win.btn_next_file.setEnabled(has_files and 0 <= win.current_file_index < total_files - 1)

    win.file_input.blockSignals(True)

    if has_files:
        win.file_input.setMaximum(total_files)
        win.file_input.setValue(win.current_file_index + 1)
        win.file_input.setSuffix(f" / {total_files}")
        win.file_input.setEnabled(True)

        if 0 <= win.current_file_index < total_files:
            path = win.selected_pdf_paths[win.current_file_index]
            display_text = get_formatted_file_name(win, path)

            win.file_status_entry.setText(display_text)
            win.file_status_entry.setToolTip(path)
            win.file_status_entry.setEnabled(True)
    else:
        win.file_input.setMaximum(0)
        win.file_input.setValue(0)
        win.file_input.setSuffix(" / 0")
        win.file_input.setEnabled(False)
        win.file_status_entry.setText("No file selected")
        win.file_status_entry.setToolTip("")
        win.file_status_entry.setEnabled(False)

    win.file_input.blockSignals(False)

    win.btn_prev_page.setEnabled(has_doc and win.current_page_index > 0)
    win.btn_next_page.setEnabled(has_doc and win.current_page_index < win.current_page_count - 1)

    win.page_input.blockSignals(True)

    if has_doc:
        win.page_input.setMinimum(1)
        win.page_input.setMaximum(win.current_page_count)
        win.page_input.setValue(win.current_page_index + 1)
        win.page_input.setSuffix(f" / {win.current_page_count}")
        win.page_input.setEnabled(True)
    else:
        win.page_input.setMinimum(0)
        win.page_input.setMaximum(0)
        win.page_input.setValue(0)
        win.page_input.setSuffix(" / 0")
        win.page_input.setEnabled(False)

    win.page_input.blockSignals(False)

    win.btn_zoom_in.setEnabled(has_doc)
    win.btn_zoom_out.setEnabled(has_doc)
    win.btn_zoom_fit.setEnabled(has_doc)
    win.btn_toggle_overlay.setEnabled(has_doc)

    update_page_info(win)


def update_page_info(win: MainWindow) -> None:
    """Update page info label and active features label."""
    from core.pdf_operations import get_page_dim_corrected
    from ui.pdf_viewer import is_page_in_selection

    if win.current_doc is None or win.current_page_count == 0:
        win.page_info_label.setText("Page Info")
        win.page_info_label.setEnabled(False)
        win.active_features_label.setText("Active Features")
        win.active_features_label.setEnabled(False)
        return

    page = None
    try:
        page = win.current_doc.load_page(win.current_page_index)
        w, h = get_page_dim_corrected(page)
        rotation = page.rotation

        key = detect_paper_key(w, h)
        w_mm = w * 25.4 / 72
        h_mm = h * 25.4 / 72
        dim_str = f"{w_mm:.0f}x{h_mm:.0f} mm"

        if key:
            name = KEY_TO_LABEL.get(key, "Unknown")
            if "(" in name:
                name = name.split("(")[0].strip()
            win.page_info_label.setText(f"{name} ({dim_str}, Rot: {rotation}\u00b0)")
            win.page_info_label.setEnabled(True)
        else:
            mode = "Portrait" if h >= w else "Landscape"
            win.page_info_label.setText(f"Unknown - {mode} ({dim_str}, Rot: {rotation}\u00b0)")
            win.page_info_label.setEnabled(True)
    except Exception:
        win.page_info_label.setText("Error")
        win.page_info_label.setEnabled(True)

    features = []

    def format_feature(name, is_on):
        symbol = "\u2713" if is_on else "\u2717"
        color = "green" if is_on else "red"
        return f"{name} <span style='color:{color}; font-weight:bold;'>{symbol}</span>"

    text_on = False
    if win.group_text_insertion.isChecked():
        text_on = is_page_in_selection(
            win, win.current_page_index, win.current_page_count, "text", page
        )
    features.append(format_feature("Text", text_on))

    ts_on = False
    if win.group_timestamp_insertion.isChecked():
        ts_on = is_page_in_selection(
            win, win.current_page_index, win.current_page_count, "timestamp", page
        )
    features.append(format_feature("Time", ts_on))

    stamp_on = False
    if win.group_stamp_insertion.isChecked():
        valid_file = bool(win.current_stamp_path and os.path.exists(win.current_stamp_path))
        stamp_on = valid_file and is_page_in_selection(
            win, win.current_page_index, win.current_page_count, "stamp", page
        )
    features.append(format_feature("Stamp", stamp_on))

    win.active_features_label.setText(" | ".join(features))
    win.active_features_label.setEnabled(True)


def on_page_input_changed(win: MainWindow, value: int) -> None:
    """Handle page spinbox value changes."""
    clamped = max(1, min(value, win.current_page_count))
    if clamped != value:
        win.page_input.blockSignals(True)
        win.page_input.setValue(clamped)
        win.page_input.blockSignals(False)

    new_index = clamped - 1
    if 0 <= new_index < win.current_page_count and new_index != win.current_page_index:
        win.current_page_index = new_index
        win.render_current_page()
        win.update_navigation_ui()


def on_file_input_changed(win: MainWindow, value: int) -> None:
    """Handle file spinbox value changes."""
    total_files = len(win.selected_pdf_paths)
    if total_files == 0:
        return

    clamped = max(1, min(value, total_files))
    if clamped != value:
        win.file_input.blockSignals(True)
        win.file_input.setValue(clamped)
        win.file_input.blockSignals(False)

    new_index = clamped - 1
    if new_index != win.current_file_index:
        win.open_pdf_at_index(new_index)


def get_formatted_file_name(win: MainWindow, path: str) -> str:
    """Format a file path for display, showing relative path if possible."""
    input_root = win.input_path_entry.text().strip()
    display_text = os.path.basename(path)
    if input_root:
        try:
            if os.path.commonpath([input_root, path]) == os.path.normpath(input_root):
                display_text = os.path.relpath(path, input_root)
        except (ValueError, Exception):
            pass
    if os.sep in display_text:
        display_text = display_text.replace(os.sep, " / ")
    return display_text


def sync_tree_selection(win: MainWindow, path: str) -> None:
    """Bold the tree item matching the given path and scroll to it."""
    if win._current_bold_item:
        try:
            font = win._current_bold_item.font(0)
            font.setBold(False)
            win._current_bold_item.setFont(0, font)
        except RuntimeError:
            pass
        win._current_bold_item = None

    def search_item(item):
        if getattr(item, "full_path", None) == path:
            return item
        for i in range(item.childCount()):
            found = search_item(item.child(i))
            if found:
                return found
        return None

    target = None
    for i in range(win.pdf_tree.topLevelItemCount()):
        target = search_item(win.pdf_tree.topLevelItem(i))
        if target:
            break

    if target:
        font = target.font(0)
        font.setBold(True)
        target.setFont(0, font)
        win.pdf_tree.scrollToItem(target)
        win._current_bold_item = target
