"""PDF open/close/render, config resolution, and page selection helpers."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, Optional, TYPE_CHECKING

import fitz

from core.constants import DEFAULT_PAPER_KEY, PREVIEW_ZOOM_BASE
from core.pdf_operations import (
    PreparedStamp,
    get_page_dim_corrected,
    resolve_config_for_page,
    check_page_selection,
)

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def close_current_doc(win: MainWindow) -> None:
    """Close the current PDF document and reset preview state."""
    if win.current_doc:
        try:
            win.current_doc.close()
        except Exception:
            pass
    win.current_doc = None
    win.current_page_index = 0
    win.current_page_count = 0
    win.preview_widget.clear_preview()
    win.file_status_entry.setText("No file selected")
    win.file_status_entry.setEnabled(False)
    win.page_info_label.setText("Page Info")
    win.page_info_label.setEnabled(False)
    win.active_features_label.setText("Active Features")
    win.active_features_label.setEnabled(False)

    if win._current_bold_item:
        try:
            font = win._current_bold_item.font(0)
            font.setBold(False)
            win._current_bold_item.setFont(0, font)
        except RuntimeError:
            pass
        win._current_bold_item = None


def open_pdf_at_index(win: MainWindow, index: int) -> None:
    """Open a PDF from the selected list by index."""
    from ui.navigation import sync_tree_selection

    if not (0 <= index < len(win.selected_pdf_paths)):
        return

    path = win.selected_pdf_paths[index]
    close_current_doc(win)

    try:
        doc = fitz.open(path)
    except Exception as e:
        win.file_status_entry.setText(f"Error: {e}")
        win.file_status_entry.setEnabled(True)
        return

    win.current_doc = doc
    win.current_file_index = index
    win.current_page_index = 0
    win.current_page_count = len(doc)

    sync_tree_selection(win, path)
    win.update_navigation_ui()
    win.render_current_page()


def render_current_page(win: MainWindow) -> None:
    """Render the current page with all enabled feature overlays."""
    if win.current_doc is None or win.current_page_count == 0:
        return
    if not (0 <= win.current_page_index < win.current_page_count):
        return

    try:
        page = win.current_doc.load_page(win.current_page_index)

        # If features are toggled off, render the raw page only
        if not win._show_features:
            win.preview_widget.set_page(page, zoom=PREVIEW_ZOOM_BASE)
            from ui.navigation import update_page_info
            update_page_info(win)
            return

        text_enabled = win.group_text_insertion.isChecked()
        final_text_content = ""
        if text_enabled:
            if 0 <= win.current_file_index < len(win.selected_pdf_paths):
                filename = win.selected_pdf_paths[win.current_file_index]
                final_text_content, _ = win.substitution_engine.apply(win.live_input_text, filename)
            else:
                final_text_content = win.live_input_text

        should_draw_text = (
            text_enabled and bool(final_text_content)
            and is_page_in_selection(win, win.current_page_index, win.current_page_count, "text", page)
        )

        ts_enabled = win.group_timestamp_insertion.isChecked()
        timestamp_str = ""
        if ts_enabled:
            timestamp_str = build_timestamp_string(win, win.selected_timestamp_format)

        should_draw_ts = (
            ts_enabled and bool(timestamp_str)
            and is_page_in_selection(win, win.current_page_index, win.current_page_count, "timestamp", page)
        )

        stamp_enabled = win.group_stamp_insertion.isChecked()
        should_draw_stamp = (
            stamp_enabled
            and win.current_stamp_path
            and os.path.exists(win.current_stamp_path)
            and is_page_in_selection(win, win.current_page_index, win.current_page_count, "stamp", page)
        )

        if should_draw_text or should_draw_ts or should_draw_stamp:
            doc_copy = fitz.open(stream=win.current_doc.tobytes(), filetype="pdf")
            try:
                temp_page = doc_copy.load_page(win.current_page_index)

                if should_draw_text:
                    cfg = get_config_for_page_size(win, temp_page, "text")
                    win.pdf_ops.apply_text_to_page(temp_page, final_text_content, cfg, win.font_families)

                if should_draw_ts:
                    cfg = get_config_for_page_size(win, temp_page, "timestamp")
                    win.pdf_ops.apply_text_to_page(temp_page, timestamp_str, cfg, win.font_families)

                if should_draw_stamp:
                    cfg = get_config_for_page_size(win, temp_page, "stamp")
                    _apply_stamp_to_page(win, temp_page, cfg)

                win.preview_widget.set_page(temp_page, zoom=PREVIEW_ZOOM_BASE)
            finally:
                doc_copy.close()
        else:
            win.preview_widget.set_page(page, zoom=PREVIEW_ZOOM_BASE)

        from ui.navigation import update_page_info
        update_page_info(win)

    except Exception as e:
        print(f"Render Error: {e}")


def _apply_stamp_to_page(
    win: MainWindow,
    page: fitz.Page,
    cfg: Dict,
    prepared_stamp: Optional[PreparedStamp] = None,
) -> None:
    """Insert a stamp image onto a PDF page."""
    if not win.current_stamp_path or not os.path.exists(win.current_stamp_path):
        return
    win.pdf_ops.apply_stamp_to_page(page, cfg, win.current_stamp_path, prepared_stamp)


def get_config_for_page_size(win: MainWindow, page: fitz.Page, config_type: str) -> Dict:
    """Look up the per-paper-size config for a given page, with fallback."""
    if config_type == "timestamp":
        configs, default = win.timestamp_configs_by_size, win.default_timestamp_config
    elif config_type == "stamp":
        configs, default = win.stamp_configs_by_size, win.default_stamp_config
    else:
        configs, default = win.text_configs_by_size, win.default_text_config
    return resolve_config_for_page(page, configs, default)


def is_pdf_standard_size(path: str) -> bool:
    """Check if the first page of a PDF is a standard paper size."""
    try:
        with fitz.open(path) as doc:
            page = doc.load_page(0)
            w, h = get_page_dim_corrected(page)
            return detect_paper_key(w, h) is not None
    except Exception:
        return False


def is_page_in_selection(
    win: MainWindow,
    idx_zero_based: int,
    total_pages: int,
    feature: str,
    page=None,
) -> bool:
    """Check if a given page index is included in the feature's page selection."""
    if page is not None:
        cfg = get_config_for_page_size(win, page, feature)
    else:
        key = DEFAULT_PAPER_KEY
        if feature == "timestamp":
            cfg = win.timestamp_configs_by_size.get(key, win.default_timestamp_config)
        elif feature == "stamp":
            cfg = win.stamp_configs_by_size.get(key, win.default_stamp_config)
        else:
            cfg = win.text_configs_by_size.get(key, win.default_text_config)
    return check_page_selection(cfg, idx_zero_based, total_pages)


def build_timestamp_string(win: MainWindow, fmt: str) -> str:
    """Build the full timestamp string with optional prefix."""
    dt = datetime.now()
    date_part = dt.strftime(fmt)
    prefix = win.ts_prefix_edit.text()

    if prefix:
        return f"{prefix} {date_part}"
    return date_part


def select_font_file(win: MainWindow, cfg: Dict) -> Optional[str]:
    """Resolve font file path from config and font families."""
    family = cfg.get("font_family")
    bold = cfg.get("bold", False)
    italic = cfg.get("italic", False)
    fam_map = win.font_families.get(family)
    if not fam_map:
        return None

    if bold and italic:
        return fam_map.get("bolditalic") or fam_map.get("bold") or fam_map.get("italic") or fam_map.get("regular")
    if bold:
        return fam_map.get("bold") or fam_map.get("regular")
    if italic:
        return fam_map.get("italic") or fam_map.get("regular")
    return fam_map.get("regular")
