#pragma once

#include "lvgl.h"

typedef struct {
    const char **lower_map;
    const lv_btnmatrix_ctrl_t *lower_ctrl;
    const char **upper_map;
    const lv_btnmatrix_ctrl_t *upper_ctrl;
    const char **special_map;
    const lv_btnmatrix_ctrl_t *special_ctrl;
    const char **number_map;
    const lv_btnmatrix_ctrl_t *number_ctrl;
} touch_keyboard_layout_t;

extern const touch_keyboard_layout_t TOUCH_KEYBOARD_LAYOUT_DEFAULT;
extern const touch_keyboard_layout_t TOUCH_KEYBOARD_LAYOUT_SHELL;

/* LVGL 8 stores keyboard maps globally by mode. Every consumer must restore
 * its complete layout before displaying a keyboard or changing its mode. */
void touch_keyboard_apply_layout(lv_obj_t *keyboard, const touch_keyboard_layout_t *layout);
void touch_keyboard_set_mode(lv_obj_t *keyboard,
                             const touch_keyboard_layout_t *layout,
                             lv_keyboard_mode_t mode);
