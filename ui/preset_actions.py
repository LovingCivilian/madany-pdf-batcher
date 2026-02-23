"""Preset load/save/manage and configuration dialog launchers."""
from __future__ import annotations

import os
from typing import Dict, TYPE_CHECKING

from core.constants import (
    DEFAULT_TEXT_CONFIG, DEFAULT_TIMESTAMP_CONFIG, DEFAULT_STAMP_CONFIG,
    ALL_PAPER_KEYS,
)
from core.preset_manager import (
    Preset,
    TextInsertionSettings,
    TimestampInsertionSettings,
    StampInsertionSettings,
    PDFSecuritySettings,
)
from dialogs.text_configuration_dialog import TextConfigurationDialog
from dialogs.timestamp_configuration_dialog import TimestampConfigurationDialog
from dialogs.stamp_configuration_dialog import StampConfigurationDialog
from dialogs.preset_dialogs import (
    SavePresetDialog,
    LoadPresetDialog,
    ManagePresetsDialog,
)

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def load_preset(win: MainWindow) -> None:
    """Open the Load Preset dialog and apply the selected preset."""
    dialog = LoadPresetDialog(win.preset_manager, win)
    if dialog.exec():
        preset_name = dialog.get_selected_preset()
        if preset_name:
            apply_preset_to_ui(win, preset_name)


def save_preset(win: MainWindow) -> None:
    """Open the Save Preset dialog and save the current state."""
    dialog = SavePresetDialog(win.preset_manager, win)
    if dialog.exec():
        name, description = dialog.get_preset_info()
        if name:
            _gather_state_and_save_preset(win, name, description)


def manage_presets(win: MainWindow) -> None:
    """Open the Manage Presets dialog."""
    from ui.config_manager import get_default_preset_name, set_default_preset_name

    current_state = build_current_preset_object(win)
    default_preset_name = get_default_preset_name(win)

    dialog = ManagePresetsDialog(
        win.preset_manager,
        parent=win,
        current_preset=current_state,
        default_preset_name=default_preset_name,
        on_default_change=lambda name: set_default_preset_name(win, name),
    )
    dialog.exec()


def load_default_preset_on_startup(win: MainWindow) -> None:
    """Auto-load the default preset on application startup."""
    from ui.config_manager import get_default_preset_name
    from ui.log_panel import append_log

    default_name = get_default_preset_name(win)
    if default_name and win.preset_manager.preset_exists(default_name):
        apply_preset_to_ui(win, default_name)
        append_log(win, f"Auto-loaded default preset: {default_name}")


def build_current_preset_object(win: MainWindow, name: str = "Temp", description: str = "") -> Preset:
    """Gather UI state into a Preset object."""
    text_settings = TextInsertionSettings(
        enabled=win.group_text_insertion.isChecked(),
        text=win.live_input_text,
        configs_by_size=win.text_configs_by_size.copy(),
    )

    checked_btn = win.ts_format_btn_group.checkedButton()
    fmt_str = checked_btn.property("fmt_str") if checked_btn else "%Y-%m-%d"

    ts_settings = TimestampInsertionSettings(
        enabled=win.group_timestamp_insertion.isChecked(),
        format_string=fmt_str,
        prefix=win.ts_prefix_edit.text(),
        configs_by_size=win.timestamp_configs_by_size.copy(),
    )

    stamp_settings = StampInsertionSettings(
        enabled=win.group_stamp_insertion.isChecked(),
        stamp_path=win.current_stamp_path,
        configs_by_size=win.stamp_configs_by_size.copy(),
    )

    security_settings = PDFSecuritySettings(
        enabled=win.security_group.isChecked(),
        master_password=win.security_password.text(),
        allow_print=win.chk_perm_print.isChecked(),
        allow_modify=win.chk_perm_modify.isChecked(),
        allow_copy=win.chk_perm_copy.isChecked(),
        allow_annotate=win.chk_perm_annotate.isChecked(),
        allow_form_fill=win.chk_perm_form.isChecked(),
        allow_assemble=win.chk_perm_assemble.isChecked(),
    )

    return Preset(
        name=name, description=description,
        text_insertion=text_settings,
        timestamp_insertion=ts_settings,
        stamp_insertion=stamp_settings,
        pdf_security=security_settings,
    )


def _gather_state_and_save_preset(win: MainWindow, name: str, description: str = "") -> None:
    """Build preset from UI state and save it."""
    from ui.log_panel import show_info, show_warning, append_log

    preset = build_current_preset_object(win, name, description)
    overwrite = win.preset_manager.preset_exists(name)

    success, msg = win.preset_manager.save_preset(preset, overwrite=overwrite)
    if success:
        show_info(win, "Preset Saved", msg)
        append_log(win, f"Preset saved: {name}")
    else:
        show_warning(win, "Save Failed", msg)


def apply_preset_to_ui(win: MainWindow, name: str) -> None:
    """Load a preset by name and apply its settings to the UI."""
    from ui.log_panel import show_warning

    preset, msg = win.preset_manager.load_preset(name)
    if preset is None:
        show_warning(win, "Load Failed", msg)
        return

    ti = preset.text_insertion
    win.group_text_insertion.setChecked(ti.enabled)
    win.text_input_box.setPlainText(ti.text)

    for key, config in ti.configs_by_size.items():
        if key in win.text_configs_by_size:
            win.text_configs_by_size[key] = config.copy()

    win.default_text_config = determine_default_config(win.text_configs_by_size, DEFAULT_TEXT_CONFIG)

    ts = preset.timestamp_insertion
    win.group_timestamp_insertion.setChecked(ts.enabled)
    win.ts_prefix_edit.setText(ts.prefix)

    found_fmt = False
    for btn in win.ts_format_btn_group.buttons():
        if btn.property("fmt_str") == ts.format_string:
            btn.setChecked(True)
            found_fmt = True
            break
    if not found_fmt:
        win.ts_format_btn_group.buttons()[0].setChecked(True)

    for key, config in ts.configs_by_size.items():
        if key in win.timestamp_configs_by_size:
            win.timestamp_configs_by_size[key] = config.copy()

    win.default_timestamp_config = determine_default_config(win.timestamp_configs_by_size, DEFAULT_TIMESTAMP_CONFIG)

    si = preset.stamp_insertion
    win.group_stamp_insertion.setChecked(si.enabled)
    win.current_stamp_path = si.stamp_path
    win.stamp_path_entry.setText(win.current_stamp_path if win.current_stamp_path else "")

    if win.current_stamp_path and os.path.exists(win.current_stamp_path):
        win.btn_stamp_config.setEnabled(True)
    else:
        win.btn_stamp_config.setEnabled(False)

    for key, config in si.configs_by_size.items():
        if key in win.stamp_configs_by_size:
            win.stamp_configs_by_size[key] = config.copy()

    win.default_stamp_config = determine_default_config(win.stamp_configs_by_size, DEFAULT_STAMP_CONFIG)

    sec = preset.pdf_security
    win.security_group.setChecked(sec.enabled)
    win.security_password.setText(sec.master_password)
    win.chk_perm_print.setChecked(sec.allow_print)
    win.chk_perm_modify.setChecked(sec.allow_modify)
    win.chk_perm_copy.setChecked(sec.allow_copy)
    win.chk_perm_annotate.setChecked(sec.allow_annotate)
    win.chk_perm_form.setChecked(sec.allow_form_fill)
    win.chk_perm_assemble.setChecked(sec.allow_assemble)

    win.render_current_page()


def determine_default_config(configs: Dict, fallback: Dict) -> Dict:
    """Select the default config, preferring A4 portrait."""
    key_a4_portrait = ("A4", "portrait")
    if key_a4_portrait in configs:
        return configs[key_a4_portrait].copy()
    elif configs:
        first_key = next(iter(configs))
        return configs[first_key].copy()
    return fallback.copy()


def open_text_configuration(win: MainWindow) -> None:
    """Open the text configuration dialog."""
    win._text_config_dialog = TextConfigurationDialog(win, win.font_families)
    win._text_config_dialog.set_all_configs(win.text_configs_by_size)

    win._text_config_dialog.configApplied.connect(lambda: on_textconfig_applied(win))
    if win._text_config_dialog.exec():
        win.text_configs_by_size = {k: v.copy() for k, v in win._text_config_dialog.all_configs.items()}
        win.default_text_config = determine_default_config(win.text_configs_by_size, DEFAULT_TEXT_CONFIG)
        win.render_current_page()
    win._text_config_dialog = None


def open_timestamp_configuration(win: MainWindow) -> None:
    """Open the timestamp configuration dialog."""
    win._timestamp_config_dialog = TimestampConfigurationDialog(win, win.font_families)
    win._timestamp_config_dialog.set_all_configs(win.timestamp_configs_by_size)

    win._timestamp_config_dialog.configApplied.connect(lambda: on_timestampconfig_applied(win))
    if win._timestamp_config_dialog.exec():
        win.timestamp_configs_by_size = {k: v.copy() for k, v in win._timestamp_config_dialog.all_configs.items()}
        win.default_timestamp_config = determine_default_config(win.timestamp_configs_by_size, DEFAULT_TIMESTAMP_CONFIG)
        win.render_current_page()
    win._timestamp_config_dialog = None


def open_stamp_configuration(win: MainWindow) -> None:
    """Open the stamp configuration dialog."""
    win._stamp_config_dialog = StampConfigurationDialog(win, win.current_stamp_path)
    win._stamp_config_dialog.set_all_configs(win.stamp_configs_by_size)
    win._stamp_config_dialog.configApplied.connect(lambda: on_stampconfig_applied(win))

    if win._stamp_config_dialog.exec():
        win.stamp_configs_by_size = {k: v.copy() for k, v in win._stamp_config_dialog.all_configs.items()}
        win.default_stamp_config = determine_default_config(win.stamp_configs_by_size, DEFAULT_STAMP_CONFIG)
        win.render_current_page()

    win._stamp_config_dialog = None


def on_textconfig_applied(win: MainWindow) -> None:
    """Handle live-apply from text config dialog."""
    if win._text_config_dialog:
        win.text_configs_by_size = {k: v.copy() for k, v in win._text_config_dialog.all_configs.items()}
        win.default_text_config = determine_default_config(win.text_configs_by_size, DEFAULT_TEXT_CONFIG)
        win.render_current_page()


def on_timestampconfig_applied(win: MainWindow) -> None:
    """Handle live-apply from timestamp config dialog."""
    if win._timestamp_config_dialog:
        win.timestamp_configs_by_size = {k: v.copy() for k, v in win._timestamp_config_dialog.all_configs.items()}
        win.default_timestamp_config = determine_default_config(win.timestamp_configs_by_size, DEFAULT_TIMESTAMP_CONFIG)
        win.render_current_page()


def on_stampconfig_applied(win: MainWindow) -> None:
    """Handle live-apply from stamp config dialog."""
    if win._stamp_config_dialog:
        win.stamp_configs_by_size = {k: v.copy() for k, v in win._stamp_config_dialog.all_configs.items()}
        win.default_stamp_config = determine_default_config(win.stamp_configs_by_size, DEFAULT_STAMP_CONFIG)
        win.render_current_page()
