#!/usr/bin/env python3
"""Contracts for LVGL's process-global keyboard map lifecycle."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(text: str, pattern: str, description: str) -> None:
    if not re.search(pattern, text, re.MULTILINE | re.DOTALL):
        raise AssertionError(f"missing keyboard lifecycle contract: {description}")


helper = source("main/touch_keyboard_maps.c")
header = source("main/touch_keyboard_maps.h")
shell = source("main/bsp_display_7b.c")
logs = source("main/touch_logs_ui.c")
manage = source("main/touch_manage_config_ui.c")
setup = source("main/first_run_setup_ui.c")
maintenance = source("main/touch_maintenance_ui.c")
cmake = source("main/CMakeLists.txt")

assert '"touch_keyboard_maps.c"' in cmake
assert "LVGL 8 stores keyboard maps globally by mode" in header
for mode in (
    "LV_KEYBOARD_MODE_TEXT_LOWER",
    "LV_KEYBOARD_MODE_TEXT_UPPER",
    "LV_KEYBOARD_MODE_SPECIAL",
    "LV_KEYBOARD_MODE_NUMBER",
):
    require(helper, rf"lv_keyboard_set_map\(\s*keyboard,\s*{mode}",
            f"shared helper restores {mode}")

# Only the lifecycle helper may mutate LVGL's global map slots.
for path in (
    "main/bsp_display_7b.c",
    "main/touch_logs_ui.c",
    "main/touch_manage_config_ui.c",
    "main/first_run_setup_ui.c",
    "main/touch_maintenance_ui.c",
):
    assert "lv_keyboard_set_map(" not in source(path), path

require(shell,
        r"open_keyboard_sheet.*?touch_keyboard_set_mode\(\s*s_keyboard,\s*"
        r"&TOUCH_KEYBOARD_LAYOUT_SHELL,\s*mode\)",
        "shell restores its layout before every open")
require(shell,
        r"keyboard_cb.*?TOUCH_KEYBOARD_LAYOUT_SHELL.*?"
        r"LV_KEYBOARD_MODE_SPECIAL",
        "shell restores its layout before a mode transition")
require(logs,
        r"render_search_sheet.*?touch_keyboard_apply_layout\(s_ui->keyboard,\s*"
        r"&TOUCH_KEYBOARD_LAYOUT_SHELL\).*?LV_OBJ_FLAG_HIDDEN",
        "Logs restores its compatible layout before becoming visible")
require(logs,
        r"keyboard_input_cb.*?TOUCH_KEYBOARD_LAYOUT_SHELL.*?"
        r"LV_KEYBOARD_MODE_SPECIAL",
        "Logs restores its layout before a mode transition")
require(manage,
        r"config_keyboard_layout.*?touch_keyboard_set_mode\(\s*"
        r"u->keyboard,\s*&config_keyboard_layout,\s*LV_KEYBOARD_MODE_TEXT_LOWER\)",
        "Manage applies its private layout when creating an editor")
require(manage,
        r"keyboard_input.*?touch_keyboard_set_mode\(\s*kb,\s*&config_keyboard_layout",
        "Manage restores its layout before mode transitions")
require(setup,
        r"make_keyboard.*?TOUCH_KEYBOARD_LAYOUT_DEFAULT",
        "first-run keyboards restore the LVGL-compatible layout")
require(maintenance,
        r"lv_keyboard_create.*?TOUCH_KEYBOARD_LAYOUT_DEFAULT",
        "firmware URL keyboard restores the LVGL-compatible layout")

print("touch keyboard lifecycle contract passed")
