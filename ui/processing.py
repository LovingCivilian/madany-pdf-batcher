"""Batch processing: PDFProcessingThread, ProgressDialog, and orchestration."""
from __future__ import annotations

import os
import time
import copy
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import fitz

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QDialog, QMessageBox, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt, QThread, Signal

from core.constants import (
    PROGRESS_DIALOG_WIDTH, PROGRESS_DIALOG_HEIGHT, CANCEL_BTN_WIDTH,
    STATUS_LABEL_MIN_HEIGHT, OVERWRITE_DIALOG_MIN_WIDTH, OVERWRITE_DIALOG_MIN_HEIGHT,
    MAX_ERRORS_DISPLAYED, THREAD_SLEEP_PER_FILE, THREAD_SLEEP_PER_PAGE,
    PDF_SAVE_OPTIONS, PTS_PER_MM, detect_paper_key,
)
from core.pdf_operations import PDFOperations, PreparedStamp
from core.anchor import compute_anchor_for_pdf
from core.substitution_engine import SubstitutionEngine

if TYPE_CHECKING:
    from ui.main_window import MainWindow


# =====================================================================
# WORKER THREAD
# =====================================================================
class PDFProcessingThread(QThread):
    """Background thread that processes PDFs with text, timestamps, stamps, and security."""

    progress_update = Signal(int, str)
    log_message = Signal(str)
    finished_processing = Signal(bool, int, int, list)

    def __init__(
        self,
        files: List[str],
        output_dir: str,
        input_root: str,
        features: Dict,
        security_settings: Dict,
        text_settings: Dict,
        timestamp_settings: Dict,
        stamp_settings: Dict,
        pdf_ops_instance: PDFOperations,
        substitution_engine: SubstitutionEngine,
        font_families: Dict,
    ):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.input_root = input_root
        self.features = features
        self.security_settings = security_settings
        self.text_settings = text_settings
        self.timestamp_settings = timestamp_settings
        self.stamp_settings = stamp_settings
        self.pdf_ops = pdf_ops_instance
        self.substitution_engine = substitution_engine
        self.font_families = font_families
        self._is_canceled = False

    def run(self) -> None:
        self.setPriority(QThread.LowPriority)

        success_count = 0
        error_count = 0
        errors: List[str] = []

        local_pdf_ops = PDFOperations()

        prepared_stamp = None
        if self.features["Stamp Insertion"] and self.stamp_settings.get("path"):
            if os.path.exists(self.stamp_settings["path"]):
                prepared_stamp = PreparedStamp(self.stamp_settings["path"], local_pdf_ops)

        ts_full_str = self.timestamp_settings.get("full_string", "")

        for idx, pdf_path in enumerate(self.files):
            if self.isInterruptionRequested():
                self._is_canceled = True
                break

            filename = os.path.basename(pdf_path)
            self.progress_update.emit(idx, f"Processing: {filename}")

            time.sleep(THREAD_SLEEP_PER_FILE)

            doc = None
            try:
                doc = fitz.open(pdf_path)
                page_count = len(doc)

                final_text_content = ""
                if self.features["Text Insertion"]:
                    raw_text = self.text_settings.get("raw_text", "")
                    final_text_content, _ = self.substitution_engine.apply(raw_text, pdf_path)

                for i in range(page_count):
                    time.sleep(THREAD_SLEEP_PER_PAGE)

                    page = doc.load_page(i)

                    # --- APPLY TEXT ---
                    if self.features["Text Insertion"]:
                        cfg = self._get_config(page, self.text_settings["configs"], self.text_settings["default"])
                        if self._check_selection(i, page_count, cfg):
                            self.pdf_ops.apply_text_to_page(
                                page, final_text_content, cfg, self.font_families
                            )

                    # --- APPLY TIMESTAMP ---
                    if self.features["Timestamp Insertion"]:
                        cfg = self._get_config(page, self.timestamp_settings["configs"], self.timestamp_settings["default"])
                        if self._check_selection(i, page_count, cfg):
                            self.pdf_ops.apply_text_to_page(
                                page, ts_full_str, cfg, self.font_families
                            )

                    # --- APPLY STAMP ---
                    if self.features["Stamp Insertion"] and prepared_stamp:
                        cfg = self._get_config(page, self.stamp_settings["configs"], self.stamp_settings["default"])
                        if self._check_selection(i, page_count, cfg):
                            self._apply_stamp_logic(page, cfg, prepared_stamp)

                # Save Logic
                if self.input_root:
                    rel_path = os.path.relpath(pdf_path, self.input_root)
                    save_path = os.path.join(self.output_dir, rel_path)
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                else:
                    save_path = os.path.join(self.output_dir, filename)
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)

                save_args = dict(PDF_SAVE_OPTIONS)

                if self.features["PDF Security"]:
                    save_args.update({
                        "encryption": fitz.PDF_ENCRYPT_AES_256,
                        "owner_pw": self.security_settings["password"],
                        "permissions": self.security_settings["permissions"],
                    })

                doc.save(save_path, **save_args)
                success_count += 1

            except Exception as e:
                msg = f"Failed {filename}: {e}"
                self.log_message.emit(msg)
                errors.append(msg)
                error_count += 1

            finally:
                if doc:
                    doc.close()

        self.finished_processing.emit(self._is_canceled, success_count, error_count, errors)

    # --- Thread Helpers ---
    def _get_page_dim_corrected(self, page):
        rect = page.rect
        if page.rotation in (90, 270):
            return rect.height, rect.width
        return rect.width, rect.height

    def _get_config(self, page, configs, default):
        w, h = self._get_page_dim_corrected(page)
        key = detect_paper_key(w, h)
        if key is None:
            mode = "portrait" if h >= w else "landscape"
            key = ("Unknown", mode)
        return configs.get(key, default)

    def _check_selection(self, idx, total, cfg):
        mode = cfg.get("page_selection", "all")
        custom_str = cfg.get("custom_pages", "")
        pno = idx + 1
        if mode == "all":
            return True
        if mode == "first":
            return pno == 1
        if mode == "last":
            return pno == total
        if mode == "odd":
            return (pno % 2) == 1
        if mode == "even":
            return (pno % 2) == 0
        if mode == "custom":
            pages = set()
            for part in custom_str.split(","):
                part = part.strip()
                if "-" in part:
                    try:
                        s, e = map(int, part.split("-", 1))
                        if s > e:
                            s, e = e, s
                        pages.update(range(s, e + 1))
                    except Exception:
                        continue
                else:
                    try:
                        pages.add(int(part))
                    except Exception:
                        continue
            return pno in pages
        return False

    def _apply_stamp_logic(self, page, cfg, prepared_stamp):
        page_w, page_h = self._get_page_dim_corrected(page)
        w_mm = cfg.get("stamp_width_mm", 50.0)
        h_mm = cfg.get("stamp_height_mm", 50.0)
        stamp_w_pts = w_mm * PTS_PER_MM
        stamp_h_pts = h_mm * PTS_PER_MM
        stamp_rotation = cfg.get("stamp_rotation", 0)
        stamp_opacity = cfg.get("stamp_opacity", 100) / 100.0

        if int(stamp_rotation) % 180 == 90:
            visual_w, visual_h = stamp_h_pts, stamp_w_pts
        else:
            visual_w, visual_h = stamp_w_pts, stamp_h_pts

        block_x, block_y = compute_anchor_for_pdf(
            page_w, page_h, visual_w, visual_h, cfg
        )

        self.pdf_ops.insert_stamp_bytes(
            page,
            prepared_stamp.get_bytes(stamp_opacity),
            block_x, block_y,
            visual_w, visual_h,
            stamp_rotation,
        )


# =====================================================================
# CUSTOM PROGRESS DIALOG
# =====================================================================
class ProgressDialog(QDialog):
    """Custom progress dialog with fixed size and centered cancel button."""

    def __init__(self, title: str, label_text: str, max_value: int = 0, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(PROGRESS_DIALOG_WIDTH, PROGRESS_DIALOG_HEIGHT)
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._is_canceled = False
        self._max_value = max_value

        main_layout = QVBoxLayout(self)

        self.status_label = QLabel(label_text)
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.status_label.setMinimumHeight(STATUS_LABEL_MIN_HEIGHT)
        main_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(max_value)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(CANCEL_BTN_WIDTH)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

    def _on_cancel_clicked(self) -> None:
        self._is_canceled = True
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling...")

    def was_canceled(self) -> bool:
        return self._is_canceled

    def set_value(self, value: int) -> None:
        self.progress_bar.setValue(value)

    def set_label_text(self, text: str) -> None:
        if len(text) > 50:
            text = text[:47] + "..."
        self.status_label.setText(text)

    def set_maximum(self, max_value: int) -> None:
        self._max_value = max_value
        self.progress_bar.setMaximum(max_value)


# =====================================================================
# BATCH ORCHESTRATION FUNCTIONS
# =====================================================================

def create_progress_dialog(
    win: MainWindow, title: str, label: str, maximum: int = 0
) -> ProgressDialog:
    """Create and return a ProgressDialog parented to win."""
    return ProgressDialog(title, label, maximum, win)


def get_existing_output_files(win: MainWindow, out_dir: str) -> List[Tuple[str, str]]:
    """Check which output files already exist. Returns (source, dest) tuples."""
    existing: List[Tuple[str, str]] = []
    input_root = win.input_path_entry.text().strip()

    for pdf_path in win.selected_pdf_paths:
        filename = os.path.basename(pdf_path)
        if input_root:
            rel_path = os.path.relpath(pdf_path, input_root)
            save_path = os.path.join(out_dir, rel_path)
        else:
            save_path = os.path.join(out_dir, filename)

        if os.path.exists(save_path):
            existing.append((pdf_path, save_path))

    return existing


def show_overwrite_warning(win: MainWindow, existing_files: List[Tuple[str, str]]) -> bool:
    """Show warning dialog for existing files. Returns True if user wants to proceed."""
    count = len(existing_files)

    dialog = QDialog(win)
    if count == 1:
        dialog.setWindowTitle("File Already Exists")
        message = "The following file already exists in the output folder and will be overwritten:"
    else:
        dialog.setWindowTitle("Files Already Exist")
        message = f"The following {count} files already exist in the output folder and will be overwritten:"

    dialog.setMinimumWidth(OVERWRITE_DIALOG_MIN_WIDTH)
    dialog.setMinimumHeight(OVERWRITE_DIALOG_MIN_HEIGHT)

    layout = QVBoxLayout(dialog)

    msg_label = QLabel(message)
    msg_label.setWordWrap(True)
    layout.addWidget(msg_label)

    file_list = QListWidget()
    file_list.setAlternatingRowColors(True)

    for _, dest_path in existing_files:
        item = QListWidgetItem(os.path.basename(dest_path))
        item.setToolTip(dest_path)
        file_list.addItem(item)

    layout.addWidget(file_list, 1)

    question_label = QLabel("Do you want to continue and overwrite these files?")
    layout.addWidget(question_label)

    btn_layout = QHBoxLayout()
    btn_layout.addStretch()

    no_btn = QPushButton("No")
    no_btn.setDefault(True)
    no_btn.clicked.connect(dialog.reject)
    btn_layout.addWidget(no_btn)

    yes_btn = QPushButton("Yes, Overwrite")
    yes_btn.clicked.connect(dialog.accept)
    btn_layout.addWidget(yes_btn)

    layout.addLayout(btn_layout)

    return dialog.exec() == QDialog.Accepted


def process_all_pdfs(win: MainWindow) -> None:
    """Validate inputs and start batch processing."""
    from ui.log_panel import show_warning, show_error, show_info, append_log
    from ui.pdf_viewer import build_timestamp_string

    if not win.selected_pdf_paths:
        show_warning(win, "No Files", "Please select PDF files to process.")
        return

    out_dir = win.output_path_entry.text().strip()
    if not out_dir:
        show_warning(win, "No Output", "Please select an output folder.")
        return
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    # Check for existing files that would be overwritten
    existing_files = get_existing_output_files(win, out_dir)
    if existing_files:
        if not show_overwrite_warning(win, existing_files):
            return

    security_enabled = win.security_group.isChecked()
    master_password = win.security_password.text()

    if security_enabled and not master_password:
        show_warning(
            win, "Password Required",
            "You have enabled PDF Security but did not provide a master password.\n\n"
            "Please enter a password or disable security.",
        )
        return

    features = {
        "Text Insertion": win.group_text_insertion.isChecked(),
        "Timestamp Insertion": win.group_timestamp_insertion.isChecked(),
        "Stamp Insertion": win.group_stamp_insertion.isChecked(),
        "PDF Security": security_enabled,
    }

    if not any(features.values()):
        show_warning(win, "No Features", "Enable at least one feature.")
        return

    # Prepare Data Payloads (Deep Copy to prevent thread race conditions)
    text_payload = {
        "raw_text": win.live_input_text,
        "configs": copy.deepcopy(win.text_configs_by_size),
        "default": win.default_text_config.copy(),
    }

    timestamp_payload = {
        "full_string": build_timestamp_string(win, win.selected_timestamp_format),
        "configs": copy.deepcopy(win.timestamp_configs_by_size),
        "default": win.default_timestamp_config.copy(),
    }

    stamp_payload = {
        "path": win.current_stamp_path,
        "configs": copy.deepcopy(win.stamp_configs_by_size),
        "default": win.default_stamp_config.copy(),
    }

    perms = 0
    if win.chk_perm_print.isChecked():
        perms |= fitz.PDF_PERM_PRINT | fitz.PDF_PERM_PRINT_HQ
    if win.chk_perm_modify.isChecked():
        perms |= fitz.PDF_PERM_MODIFY
    if win.chk_perm_copy.isChecked():
        perms |= fitz.PDF_PERM_COPY
    if win.chk_perm_annotate.isChecked():
        perms |= fitz.PDF_PERM_ANNOTATE
    if win.chk_perm_form.isChecked():
        perms |= fitz.PDF_PERM_FORM
    if win.chk_perm_assemble.isChecked():
        perms |= fitz.PDF_PERM_ASSEMBLE

    security_payload = {
        "password": master_password,
        "permissions": perms,
    }

    # Confirmation
    summary = "\n".join([f"\u2022 {k}" for k, v in features.items() if v]) or "None"
    reply = QMessageBox.question(
        win, "Confirm Processing",
        f"Process {len(win.selected_pdf_paths)} files?\n\nFeatures:\n{summary}\n\nOutput:\n{out_dir}",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
    )
    if reply != QMessageBox.Yes:
        return

    # Initialize Progress Dialog
    win._progress_dialog = create_progress_dialog(
        win, "Processing", "Initializing...", len(win.selected_pdf_paths),
    )
    win._progress_dialog.show()

    # Start Thread
    win._worker_thread = PDFProcessingThread(
        files=win.selected_pdf_paths,
        output_dir=out_dir,
        input_root=win.input_path_entry.text().strip(),
        features=features,
        security_settings=security_payload,
        text_settings=text_payload,
        timestamp_settings=timestamp_payload,
        stamp_settings=stamp_payload,
        pdf_ops_instance=win.pdf_ops,
        substitution_engine=win.substitution_engine,
        font_families=win.font_families,
    )

    # Connect Signals
    win._worker_thread.progress_update.connect(lambda idx, msg: _on_worker_progress(win, idx, msg))
    win._worker_thread.log_message.connect(lambda msg: append_log(win, msg))
    win._worker_thread.finished_processing.connect(
        lambda canceled, success, errors, error_list: _on_worker_finished(win, canceled, success, errors, error_list)
    )

    # Connect Cancel Button
    try:
        win._progress_dialog.cancel_btn.clicked.disconnect()
    except Exception:
        pass

    win._progress_dialog.cancel_btn.clicked.connect(win._worker_thread.requestInterruption)
    win._progress_dialog.cancel_btn.clicked.connect(
        lambda: win._progress_dialog.set_label_text("Stopping...")
    )

    win._worker_thread.start()


def _on_worker_progress(win: MainWindow, current_idx: int, message: str) -> None:
    """Handle progress updates from the worker thread."""
    if win._progress_dialog:
        win._progress_dialog.set_value(current_idx)
        win._progress_dialog.set_label_text(message)


def _on_worker_finished(
    win: MainWindow, canceled: bool, success: int, errors: int, error_list: List[str]
) -> None:
    """Handle worker thread completion."""
    if win._progress_dialog:
        win._progress_dialog.close()

    _show_processing_result(win, canceled, success, errors, error_list)
    win._worker_thread = None


def _show_processing_result(
    win: MainWindow, canceled: bool, success: int, errors: int, error_list: List[str]
) -> None:
    """Show the final processing result dialog."""
    from ui.log_panel import show_info, show_warning

    if canceled:
        show_info(win, "Cancelled", f"Stopped by user.\nSuccess: {success}, Errors: {errors}")
    elif errors == 0:
        show_info(win, "Complete", f"Successfully processed {success} files.")
    else:
        detail = "\n".join(error_list[:MAX_ERRORS_DISPLAYED])
        if len(error_list) > MAX_ERRORS_DISPLAYED:
            detail += f"\n...and {len(error_list) - MAX_ERRORS_DISPLAYED} more."
        show_warning(win, "Completed with Errors", f"Success: {success}\nErrors: {errors}\n\n{detail}")
